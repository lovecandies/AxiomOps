import threading

import pytest

from axiom_ops.control_plane.models import (
    InvestigationPlan,
    InvestigationTask,
    InvestigatorFinding,
    InvestigatorRole,
    RcaDraft,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.rca_graph import RcaGraphError, ReadOnlyRcaGraph


INCIDENT = {"id": "incident-1", "title": "Inventory latency"}
EVIDENCE = [
    {
        "id": "evidence-metric-1",
        "kind": "METRIC_SNAPSHOT",
        "source": "prometheus",
        "observed_at": "2026-07-08T00:00:00+00:00",
        "content_sha256": "a" * 64,
        "content": {"data": {"value": 42}},
    }
]


class ParallelScriptedModel:
    model_name = "scripted-rca"

    def __init__(self) -> None:
        self._calls = 0
        self.barrier = threading.Barrier(3, timeout=5)
        self.verifier_called = False

    @property
    def call_count(self) -> int:
        return self._calls

    @property
    def total_tokens(self) -> int:
        return 0

    def plan(self, incident, evidence_catalog) -> InvestigationPlan:
        self._calls += 1
        return InvestigationPlan(
            tasks=[
                InvestigationTask(
                    task_id="metrics",
                    role=InvestigatorRole.METRICS,
                    question="What metric evidence supports the incident?",
                ),
                InvestigationTask(
                    task_id="logs",
                    role=InvestigatorRole.LOGS_TRACE,
                    question="What do logs and traces show?",
                ),
                InvestigationTask(
                    task_id="changes",
                    role=InvestigatorRole.CHANGE,
                    question="What changes correlate with the incident?",
                ),
            ]
        )

    def investigate(self, incident, task, evidence) -> InvestigatorFinding:
        self.barrier.wait()
        self._calls += 1
        if task.role == InvestigatorRole.METRICS:
            return InvestigatorFinding(
                task_id=task.task_id,
                role=task.role,
                summary="Metric evidence is available.",
                observations=["Observed metric signal."],
                hypotheses=["Inventory degradation is plausible."],
                evidence_ids=[item["id"] for item in evidence],
            )
        return InvestigatorFinding(
            task_id=task.task_id,
            role=task.role,
            summary="No relevant evidence is available.",
            limitations=[f"No evidence for {task.role.value}."],
        )

    def synthesize(self, incident, findings) -> RcaDraft:
        self._calls += 1
        evidence_ids = [
            evidence_id for finding in findings for evidence_id in finding.evidence_ids
        ]
        return RcaDraft(
            summary="Inventory degradation is the leading explanation.",
            root_cause="Inventory service degradation.",
            confidence=0.72,
            evidence_ids=evidence_ids,
            limitations=["Logs, traces, and changes are unavailable."],
        )

    def verify(self, incident, draft, evidence) -> VerificationResult:
        self._calls += 1
        self.verifier_called = True
        return VerificationResult(
            decision=VerificationDecision.APPROVED,
            rationale="The limited conclusion is supported by the cited metric Evidence.",
        )


class InvalidCitationModel(ParallelScriptedModel):
    def synthesize(self, incident, findings) -> RcaDraft:
        self._calls += 1
        return RcaDraft(
            summary="Unsupported draft.",
            root_cause="Unsupported root cause.",
            confidence=0.9,
            evidence_ids=["evidence-from-another-incident"],
        )


class HallucinatingMissingEvidenceModel(ParallelScriptedModel):
    def investigate(self, incident, task, evidence) -> InvestigatorFinding:
        self.barrier.wait()
        self._calls += 1
        if task.role == InvestigatorRole.CHANGE:
            return InvestigatorFinding(
                task_id=task.task_id,
                role=task.role,
                summary="A deployment caused the incident.",
                hypotheses=["An unobserved deployment caused the failure."],
            )
        if task.role == InvestigatorRole.METRICS:
            return InvestigatorFinding(
                task_id=task.task_id,
                role=task.role,
                summary="Metric evidence is available.",
                evidence_ids=[item["id"] for item in evidence],
            )
        return InvestigatorFinding(
            task_id=task.task_id,
            role=task.role,
            summary="No relevant evidence is available.",
            limitations=["No logs or traces are available."],
        )


def test_graph_fans_out_investigators_and_approves_grounded_rca() -> None:
    model = ParallelScriptedModel()

    result = ReadOnlyRcaGraph(model).invoke(INCIDENT, EVIDENCE)

    findings = [InvestigatorFinding.model_validate(item) for item in result["findings"]]
    verification = VerificationResult.model_validate(result["verification"])
    assert len(findings) == 3
    assert {finding.role for finding in findings} == set(InvestigatorRole)
    assert verification.decision == VerificationDecision.APPROVED
    assert model.verifier_called is True
    assert sum(step["node_name"] == "investigate" for step in result["steps"]) == 3


def test_citation_guard_rejects_cross_incident_evidence_without_llm_verifier() -> None:
    model = InvalidCitationModel()

    result = ReadOnlyRcaGraph(model).invoke(INCIDENT, EVIDENCE)

    verification = VerificationResult.model_validate(result["verification"])
    assert verification.decision == VerificationDecision.REJECTED
    assert verification.invalid_evidence_ids == ["evidence-from-another-incident"]
    assert model.verifier_called is False


def test_investigator_cannot_claim_facts_without_role_evidence() -> None:
    model = HallucinatingMissingEvidenceModel()

    with pytest.raises(RcaGraphError, match="produced claims without Evidence"):
        ReadOnlyRcaGraph(model).invoke(INCIDENT, EVIDENCE)
