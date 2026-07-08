import json
import threading
import time
from uuid import uuid4

import httpx

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.evidence_repository import EvidenceRepository
from axiom_ops.control_plane.evidence_service import EvidenceService
from axiom_ops.control_plane.evidence_storage import EvidenceStorage
from axiom_ops.control_plane.models import (
    InvestigationPlan,
    InvestigationTask,
    InvestigatorFinding,
    InvestigatorRole,
    HealthToolInput,
    MetricsToolInput,
    RcaDraft,
    RcaRunStatus,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.rca_repository import RcaRepository
from axiom_ops.control_plane.rca_runtime import RcaRuntime
from axiom_ops.control_plane.repository import IncidentRepository
from axiom_ops.control_plane.typed_tools import MetricsSnapshotTool, ServiceHealthTool


class EvaluationRcaModel:
    model_name = "scripted-grounded-evaluation"

    def __init__(self) -> None:
        self._calls = 0
        self._lock = threading.Lock()

    @property
    def call_count(self) -> int:
        with self._lock:
            return self._calls

    @property
    def total_tokens(self) -> int:
        return 0

    def _count(self) -> None:
        with self._lock:
            self._calls += 1

    def plan(self, incident, evidence_catalog) -> InvestigationPlan:
        self._count()
        return InvestigationPlan(
            tasks=[
                InvestigationTask(
                    task_id="metrics",
                    role=InvestigatorRole.METRICS,
                    question="Which metric and health signals support the incident?",
                ),
                InvestigationTask(
                    task_id="logs",
                    role=InvestigatorRole.LOGS_TRACE,
                    question="Do logs or traces support a causal mechanism?",
                ),
                InvestigationTask(
                    task_id="changes",
                    role=InvestigatorRole.CHANGE,
                    question="Did a recent change correlate with the incident?",
                ),
            ]
        )

    def investigate(self, incident, task, evidence) -> InvestigatorFinding:
        self._count()
        if task.role == InvestigatorRole.METRICS:
            return InvestigatorFinding(
                task_id=task.task_id,
                role=task.role,
                summary="Prometheus and health observations are available.",
                observations=[
                    "The metric snapshot was collected from Prometheus.",
                    "The inventory health endpoint returned successfully.",
                ],
                hypotheses=["Inventory degradation remains the leading hypothesis."],
                evidence_ids=[item["id"] for item in evidence],
            )
        return InvestigatorFinding(
            task_id=task.task_id,
            role=task.role,
            summary="The required evidence type is not available.",
            limitations=[f"No immutable Evidence exists for {task.role.value}."],
        )

    def synthesize(self, incident, findings) -> RcaDraft:
        self._count()
        evidence_ids = [
            evidence_id for finding in findings for evidence_id in finding.evidence_ids
        ]
        return RcaDraft(
            summary="Inventory degradation is the evidence-backed leading hypothesis.",
            root_cause="Inventory service degradation increased order-path risk.",
            confidence=0.72,
            contributing_factors=["The order path depends on inventory availability."],
            rejected_hypotheses=["No change-based cause can be established."],
            evidence_ids=evidence_ids,
            limitations=["Logs, traces, and change evidence are unavailable."],
        )

    def verify(self, incident, draft, evidence) -> VerificationResult:
        self._count()
        return VerificationResult(
            decision=VerificationDecision.APPROVED,
            rationale="The bounded conclusion cites only the supplied immutable Evidence.",
        )


class InvalidCitationEvaluationModel(EvaluationRcaModel):
    model_name = "scripted-invalid-citation-evaluation"

    def synthesize(self, incident, findings) -> RcaDraft:
        self._count()
        return RcaDraft(
            summary="This draft intentionally carries an invalid citation.",
            root_cause="Unsupported root cause.",
            confidence=0.99,
            evidence_ids=["evidence-from-another-incident"],
        )


def main() -> int:
    settings = ControlPlaneSettings()
    database = Database(settings)
    incident_repository = IncidentRepository(database)
    evidence_repository = EvidenceRepository(database)
    storage = EvidenceStorage(settings.evidence_root)
    evidence_service = EvidenceService(
        evidence_repository,
        storage,
        MetricsSnapshotTool(settings),
        ServiceHealthTool(settings),
    )

    with httpx.Client(base_url="http://127.0.0.1:18000", timeout=10) as client:
        httpx.get("http://127.0.0.1:18001/orders/rca-demo", timeout=5).raise_for_status()
        time.sleep(2)
        created = client.post(
            "/incidents",
            headers={"Idempotency-Key": f"rca-{uuid4()}"},
            json={
                "title": "Order path inventory degradation",
                "service": "inventory-service",
                "severity": "SEV2",
                "summary": "Generate a grounded read-only RCA",
            },
        )
        created.raise_for_status()
        incident_id = created.json()["id"]

        metric = evidence_service.execute_metrics(
            incident_id,
            MetricsToolInput(signal="order_duration_total"),
        )
        health = evidence_service.execute_health(
            incident_id,
            HealthToolInput(service="inventory-service"),
        )
        runtime = RcaRuntime(
            incident_repository,
            evidence_repository,
            storage,
            RcaRepository(database),
            EvaluationRcaModel,
        )
        run = runtime.run(incident_id)
        if run.status != RcaRunStatus.COMPLETED:
            raise RuntimeError(f"RCA run failed: {run.error or run.verification}")
        report_response = client.get(f"/incidents/{incident_id}/rca")
        report_response.raise_for_status()
        report = report_response.json()

        rejected_runtime = RcaRuntime(
            incident_repository,
            evidence_repository,
            storage,
            RcaRepository(database),
            InvalidCitationEvaluationModel,
        )
        rejected_run = rejected_runtime.run(incident_id)

    investigator_roles = {
        item.role for item in run.steps if item.node_name == "investigate"
    }
    if investigator_roles != {role.value for role in InvestigatorRole}:
        raise RuntimeError("not every investigator executed")
    expected_evidence = {metric.id, health.id}
    if set(report["evidence_ids"]) != expected_evidence:
        raise RuntimeError("RCA report did not preserve Evidence citations")
    if rejected_run.status != RcaRunStatus.REJECTED:
        raise RuntimeError("invalid cross-Incident citation was not rejected")
    connection = database.connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS count FROM rca_reports WHERE run_id=%s",
                (rejected_run.id,),
            )
            rejected_report_count = cursor.fetchone()["count"]
    finally:
        connection.close()
    if rejected_report_count != 0:
        raise RuntimeError("rejected run created an RCA report")

    print(
        json.dumps(
            {
                "passed": True,
                "incident_id": incident_id,
                "run_id": run.id,
                "status": run.status.value,
                "graph_version": run.graph_version,
                "model_calls": run.model_calls,
                "investigator_roles": sorted(investigator_roles),
                "verification": report["verification"]["decision"],
                "evidence_ids": report["evidence_ids"],
                "limitations": report["limitations"],
                "rejected_run_id": rejected_run.id,
                "invalid_citation_status": rejected_run.status.value,
                "rejected_report_count": rejected_report_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
