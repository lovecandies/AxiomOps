"""Deterministic benchmarks for AxiomOps engineering optimizations."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from axiom_ops.control_plane.context_compaction import compact_evidence
from axiom_ops.control_plane.evidence_service import EvidenceService
from axiom_ops.control_plane.models import (
    EvidenceKind,
    InvestigationPlan,
    InvestigationTask,
    InvestigatorFinding,
    InvestigatorRole,
    RcaDraft,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.rca_graph import ReadOnlyRcaGraph


EVIDENCE_KINDS = (
    EvidenceKind.FAULT_STATE,
    EvidenceKind.ORDER_FLOW_PROBE,
    EvidenceKind.METRIC_SNAPSHOT,
    EvidenceKind.SERVICE_HEALTH,
    EvidenceKind.TRACE_SNAPSHOT,
    EvidenceKind.CHANGE_EVENT,
)


@dataclass
class _EvidenceRepository:
    kinds: tuple[EvidenceKind, ...]

    def incident_exists(self, incident_id: str) -> bool:
        return True

    def list_for_incident(self, incident_id: str) -> list[Any]:
        return [SimpleNamespace(kind=kind) for kind in self.kinds]


class _InvalidCitationModel:
    model_name = "optimization-fault-injection"

    def __init__(self) -> None:
        self._calls = 0
        self.verifier_called = False

    @property
    def call_count(self) -> int:
        return self._calls

    @property
    def total_tokens(self) -> int:
        return 0

    def plan(self, incident: dict[str, Any], catalog: list[dict[str, Any]]) -> InvestigationPlan:
        self._calls += 1
        return InvestigationPlan(
            tasks=[
                InvestigationTask(task_id="metrics", role=InvestigatorRole.METRICS, question="metrics"),
                InvestigationTask(task_id="trace", role=InvestigatorRole.LOGS_TRACE, question="trace"),
                InvestigationTask(task_id="change", role=InvestigatorRole.CHANGE, question="change"),
            ]
        )

    def investigate(
        self, incident: dict[str, Any], task: InvestigationTask, evidence: list[dict[str, Any]]
    ) -> InvestigatorFinding:
        self._calls += 1
        return InvestigatorFinding(
            task_id=task.task_id,
            role=task.role,
            summary="Observed assigned evidence.",
            evidence_ids=[item["id"] for item in evidence],
        )

    def synthesize(self, incident: dict[str, Any], findings: list[InvestigatorFinding]) -> RcaDraft:
        self._calls += 1
        return RcaDraft(
            summary="Injected invalid citation.",
            root_cause="Injected fault for Citation Guard evaluation.",
            confidence=0.9,
            evidence_ids=["evidence-from-another-incident"],
        )

    def verify(
        self, incident: dict[str, Any], draft: RcaDraft, evidence: list[dict[str, Any]]
    ) -> VerificationResult:
        self._calls += 1
        self.verifier_called = True
        return VerificationResult(decision=VerificationDecision.APPROVED, rationale="unreachable")


class _FailAtSynthesisModel(_InvalidCitationModel):
    def synthesize(self, incident: dict[str, Any], findings: list[InvestigatorFinding]) -> RcaDraft:
        self._calls += 1
        raise RuntimeError("benchmark interruption")


class _ResumeAtSynthesisModel(_InvalidCitationModel):
    def plan(self, incident: dict[str, Any], catalog: list[dict[str, Any]]) -> InvestigationPlan:
        raise AssertionError("checkpoint resume repeated commander")

    def investigate(
        self, incident: dict[str, Any], task: InvestigationTask, evidence: list[dict[str, Any]]
    ) -> InvestigatorFinding:
        raise AssertionError("checkpoint resume repeated investigator")

    def synthesize(self, incident: dict[str, Any], findings: list[InvestigatorFinding]) -> RcaDraft:
        self._calls += 1
        return RcaDraft(
            summary="Recovered synthesis.",
            root_cause="Known benchmark fault.",
            confidence=0.7,
            evidence_ids=[evidence_id for finding in findings for evidence_id in finding.evidence_ids],
        )

    def verify(
        self, incident: dict[str, Any], draft: RcaDraft, evidence: list[dict[str, Any]]
    ) -> VerificationResult:
        self._calls += 1
        return VerificationResult(decision=VerificationDecision.APPROVED, rationale="Grounded benchmark RCA.")


def _evidence() -> list[dict[str, Any]]:
    return [
        {
            "id": "metric-1",
            "kind": EvidenceKind.METRIC_SNAPSHOT.value,
            "source": "benchmark",
            "observed_at": "2026-07-31T00:00:00+00:00",
            "content_sha256": "a" * 64,
            "content": {"tool_name": "metrics", "data": {"response": {"data": {"result": [{"payload": "x" * 9000}]}}}},
        },
        {
            "id": "trace-1",
            "kind": EvidenceKind.TRACE_SNAPSHOT.value,
            "source": "benchmark",
            "observed_at": "2026-07-31T00:00:00+00:00",
            "content_sha256": "b" * 64,
            "content": {"tool_name": "trace", "data": {"spans": "y" * 9000}},
        },
        {
            "id": "change-1",
            "kind": EvidenceKind.CHANGE_EVENT.value,
            "source": "benchmark",
            "observed_at": "2026-07-31T00:00:00+00:00",
            "content_sha256": "c" * 64,
            "content": {"tool_name": "change", "data": {"events": "z" * 9000}},
        },
    ]


def citation_guard_benchmark(case_count: int = 12) -> dict[str, Any]:
    rejections = 0
    for _ in range(case_count):
        model = _InvalidCitationModel()
        result = ReadOnlyRcaGraph(model).invoke({"id": "incident-1"}, _evidence())
        verification = VerificationResult.model_validate(result["verification"])
        rejections += int(
            verification.decision == VerificationDecision.REJECTED and not model.verifier_called
        )
    return {
        "case_count": case_count,
        "baseline_unsafe_release_rate": 1.0,
        "guarded_unsafe_release_rate": round(1 - rejections / case_count, 4),
        "invalid_citation_interception_rate": round(rejections / case_count, 4),
    }


def tool_completion_benchmark() -> dict[str, Any]:
    fixed_calls = 0
    selected_calls = 0
    complete_after_selection = 0
    cases = []
    for existing_count in range(len(EVIDENCE_KINDS) + 1):
        service = EvidenceService(
            _EvidenceRepository(EVIDENCE_KINDS[:existing_count]), None, None, None
        )
        plan = service.plan_tool_selection("incident-1")
        fixed_calls += len(EVIDENCE_KINDS)
        selected_calls += len(plan.selections)
        complete_after_selection += int(existing_count + len(plan.selections) == len(EVIDENCE_KINDS))
        cases.append({"existing_evidence_kinds": existing_count, "selected_tool_calls": len(plan.selections)})
    return {
        "case_count": len(cases),
        "fixed_all_tools_calls": fixed_calls,
        "missing_only_tool_calls": selected_calls,
        "tool_call_reduction_rate": round(1 - selected_calls / fixed_calls, 4),
        "required_evidence_coverage": round(complete_after_selection / len(cases), 4),
        "cases": cases,
    }


def context_compaction_benchmark() -> dict[str, Any]:
    evidence = _evidence()
    compacted = compact_evidence(evidence, total_chars=12000, per_evidence_chars=4000)
    identities_preserved = all(
        capsule["id"] == item["id"] and capsule["content_sha256"] == item["content_sha256"]
        for capsule, item in zip(compacted.capsules, evidence, strict=True)
    )
    return {
        "original_bytes": compacted.original_bytes,
        "compacted_bytes": compacted.compressed_bytes,
        "context_reduction_rate": round(1 - compacted.compressed_bytes / compacted.original_bytes, 4),
        "evidence_identity_preserved": identities_preserved,
    }


def checkpoint_resume_benchmark() -> dict[str, Any]:
    checkpointer = InMemorySaver()
    run_id = "optimization-checkpoint-run"
    try:
        ReadOnlyRcaGraph(_FailAtSynthesisModel(), checkpointer).invoke(
            {"id": "incident-1"}, _evidence(), run_id
        )
    except RuntimeError as exc:
        if str(exc) != "benchmark interruption":
            raise
    else:
        raise AssertionError("benchmark interruption did not occur")
    resumed_model = _ResumeAtSynthesisModel()
    resumed = ReadOnlyRcaGraph(resumed_model, checkpointer).resume(run_id)
    steps = resumed["steps"]
    completed_nodes_skipped = sum(
        sum(step["node_name"] == name for step in steps) == expected
        for name, expected in (("commander", 1), ("investigate", 3))
    )
    return {
        "restart_model_calls": 6,
        "resume_new_model_calls": resumed_model.call_count,
        "reexecution_avoidance_rate": round(4 / 6, 4),
        "completed_branches_preserved": completed_nodes_skipped == 2,
        "resumed_status": VerificationResult.model_validate(resumed["verification"]).decision.value,
    }


def build_optimization_report() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "evaluation": "engineering-optimization-benchmark",
        "citation_guard": citation_guard_benchmark(),
        "tool_completion": tool_completion_benchmark(),
        "context_compaction": context_compaction_benchmark(),
        "checkpoint_resume": checkpoint_resume_benchmark(),
    }
