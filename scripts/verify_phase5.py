import argparse
import json
import threading

from qdrant_client import QdrantClient

from axiom_ops.control_plane.checkpoint import redis_checkpointer
from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.evidence_repository import EvidenceRepository
from axiom_ops.control_plane.evidence_storage import EvidenceStorage
from axiom_ops.control_plane.models import (
    InvestigationPlan,
    InvestigationTask,
    InvestigatorFinding,
    InvestigatorRole,
    RcaDraft,
    RcaRunStatus,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.rca_memory import RcaMemoryStore
from axiom_ops.control_plane.rca_repository import RcaRepository
from axiom_ops.control_plane.rca_runtime import RcaRuntime
from axiom_ops.control_plane.repository import IncidentRepository


class ValidationEmbedder:
    dimension = 3

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float("inventory" in text.lower()), 0.5] for text in texts]


class BaseModel:
    model_name = "phase5-scripted-validation"

    def __init__(self) -> None:
        self.calls = 0
        self.barrier = threading.Barrier(3, timeout=10)

    @property
    def call_count(self) -> int:
        return self.calls

    @property
    def total_tokens(self) -> int:
        return 0

    def plan(self, incident, evidence_catalog) -> InvestigationPlan:
        self.calls += 1
        return InvestigationPlan(
            tasks=[
                InvestigationTask(task_id="metrics", role=InvestigatorRole.METRICS, question="metrics?"),
                InvestigationTask(task_id="logs", role=InvestigatorRole.LOGS_TRACE, question="logs?"),
                InvestigationTask(task_id="changes", role=InvestigatorRole.CHANGE, question="changes?"),
            ]
        )

    def investigate(self, incident, task, evidence) -> InvestigatorFinding:
        self.barrier.wait()
        self.calls += 1
        if evidence:
            return InvestigatorFinding(
                task_id=task.task_id,
                role=task.role,
                summary="Assigned immutable Evidence was inspected.",
                observations=["Evidence is available."],
                evidence_ids=[item["id"] for item in evidence],
            )
        return InvestigatorFinding(
            task_id=task.task_id,
            role=task.role,
            summary="No assigned Evidence exists.",
            limitations=["No Evidence exists for this role."],
        )

    def synthesize(self, incident, findings) -> RcaDraft:
        self.calls += 1
        evidence_ids = [item for finding in findings for item in finding.evidence_ids]
        return RcaDraft(
            summary="A bounded evidence-backed diagnosis was produced.",
            root_cause="Inventory service degradation is the leading cause.",
            confidence=0.7,
            evidence_ids=evidence_ids,
            limitations=["No unsupported claims were added."],
        )

    def verify(self, incident, draft, evidence) -> VerificationResult:
        self.calls += 1
        return VerificationResult(
            decision=VerificationDecision.APPROVED,
            rationale="Every claim is bounded by cited immutable Evidence.",
        )


class FailAtSynthesisModel(BaseModel):
    def synthesize(self, incident, findings) -> RcaDraft:
        self.calls += 1
        raise RuntimeError("phase5 synthetic crash")


class ResumeModel(BaseModel):
    def plan(self, incident, evidence_catalog) -> InvestigationPlan:
        raise AssertionError("commander reran after checkpoint resume")

    def investigate(self, incident, task, evidence) -> InvestigatorFinding:
        raise AssertionError("investigator reran after checkpoint resume")


class InvalidCitationModel(BaseModel):
    def synthesize(self, incident, findings) -> RcaDraft:
        self.calls += 1
        return RcaDraft(
            summary="Intentionally invalid citation.",
            root_cause="Unsupported.",
            confidence=0.9,
            evidence_ids=["evidence-from-another-incident"],
        )


def dependencies():
    settings = ControlPlaneSettings()
    database = Database(settings)
    repository = RcaRepository(database)
    memory = RcaMemoryStore(
        QdrantClient(url=settings.qdrant_url),
        ValidationEmbedder(),
        "phase5_validation_memory",
    )
    return settings, database, repository, memory


def incident_with_evidence(database: Database) -> str:
    connection = database.connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT i.id FROM incidents i
                WHERE EXISTS (SELECT 1 FROM evidence e WHERE e.incident_id=i.id)
                ORDER BY i.created_at DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("Phase 5 validation needs an Incident with Evidence")
    return row["id"]


def runtime(model_factory, settings, database, repository, memory) -> RcaRuntime:
    return RcaRuntime(
        IncidentRepository(database),
        EvidenceRepository(database),
        EvidenceStorage(settings.evidence_root),
        repository,
        model_factory,
        lambda: redis_checkpointer(settings.redis_url),
        memory,
        settings.context_total_chars,
        settings.context_evidence_chars,
        settings.memory_top_k,
    )


def fail() -> None:
    settings, database, repository, memory = dependencies()
    run = runtime(FailAtSynthesisModel, settings, database, repository, memory).run(
        incident_with_evidence(database)
    )
    if str(run.status) != RcaRunStatus.FAILED.value or run.context is None:
        raise RuntimeError(f"expected checkpointed FAILED run, got {run.status}")
    print(json.dumps({"run_id": run.id, "status": run.status.value, "model_calls": run.model_calls}))


def resume(run_id: str) -> None:
    settings, database, repository, memory = dependencies()
    run = runtime(ResumeModel, settings, database, repository, memory).resume(run_id)
    if str(run.status) != RcaRunStatus.COMPLETED.value:
        raise RuntimeError(f"resume failed: {run.error}")
    node_counts = {
        name: sum(step.node_name == name for step in run.steps)
        for name in ("commander", "investigate", "synthesize", "verifier")
    }
    if node_counts != {"commander": 1, "investigate": 3, "synthesize": 1, "verifier": 1}:
        raise RuntimeError(f"completed nodes repeated: {node_counts}")
    if run.context is None or any(
        not item.get("id") or not item.get("content_sha256")
        for item in run.context.capsules
    ):
        raise RuntimeError("Evidence capsule identity was not preserved")
    print(
        json.dumps(
            {
                "run_id": run.id,
                "status": run.status.value,
                "node_counts": node_counts,
                "original_bytes": run.context.original_bytes,
                "compressed_bytes": run.context.compressed_bytes,
            }
        )
    )


def check_memory(run_id: str) -> None:
    settings, database, repository, memory = dependencies()
    run = repository.get_run(run_id)
    if run is None:
        raise RuntimeError("run not found")
    incident = IncidentRepository(database).get_incident(run.incident_id)
    assert incident is not None
    query = incident.model_dump(mode="json")
    query["id"] = "00000000-0000-0000-0000-000000000099"
    matches = memory.search(query, 3)
    if not matches or matches[0]["notice"] != "historical hint only; not citable Evidence":
        raise RuntimeError("verified RCA memory was not recalled")
    print(json.dumps({"run_id": run_id, "memory_matches": len(matches), "report_id": matches[0]["report_id"]}))


def reject() -> None:
    settings, database, repository, memory = dependencies()
    memory.setup()
    before = memory.client.count(memory.collection, exact=True).count
    run = runtime(InvalidCitationModel, settings, database, repository, memory).run(
        incident_with_evidence(database)
    )
    after = memory.client.count(memory.collection, exact=True).count
    if str(run.status) != RcaRunStatus.REJECTED.value or after != before:
        raise RuntimeError(
            f"rejected run changed memory index: status={run.status}, {before}->{after}"
        )
    print(json.dumps({"run_id": run.id, "status": run.status.value, "memory_points": after}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("fail", "resume", "check-memory", "reject"))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action == "fail":
        fail()
    elif args.action == "reject":
        reject()
    elif not args.run_id:
        parser.error("--run-id is required")
    elif args.action == "resume":
        resume(args.run_id)
    else:
        check_memory(args.run_id)


if __name__ == "__main__":
    main()
