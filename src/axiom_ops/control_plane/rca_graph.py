import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from axiom_ops.control_plane.models import (
    InvestigationPlan,
    InvestigationTask,
    InvestigatorFinding,
    InvestigatorRole,
    RcaDraft,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.rca_model import RcaModel


GRAPH_VERSION = "phase5-v1"

ROLE_EVIDENCE_KINDS = {
    InvestigatorRole.METRICS: {"METRIC_SNAPSHOT", "SERVICE_HEALTH"},
    InvestigatorRole.LOGS_TRACE: {"LOG_SNAPSHOT", "TRACE_SNAPSHOT"},
    InvestigatorRole.CHANGE: {"CHANGE_EVENT"},
}


class RcaGraphError(Exception):
    pass


class RcaState(TypedDict, total=False):
    incident: dict[str, Any]
    evidence: list[dict[str, Any]]
    historical_memory: list[dict[str, Any]]
    plan: dict[str, Any]
    task: dict[str, Any]
    task_evidence: list[dict[str, Any]]
    findings: Annotated[list[dict[str, Any]], operator.add]
    draft: dict[str, Any]
    citation_errors: list[str]
    verification: dict[str, Any]
    steps: Annotated[list[dict[str, Any]], operator.add]


def step(node_name: str, output: dict[str, Any], role: str | None = None) -> dict:
    return {"node_name": node_name, "role": role, "output": output}


class ReadOnlyRcaGraph:
    def __init__(self, model: RcaModel, checkpointer=None) -> None:
        self.model = model
        self.graph = self._build(checkpointer)

    def _build(self, checkpointer=None):
        builder = StateGraph(RcaState)
        builder.add_node("load_context", self._load_context)
        builder.add_node("commander", self._commander)
        builder.add_node("investigate", self._investigate)
        builder.add_node("synthesize", self._synthesize)
        builder.add_node("citation_guard", self._citation_guard)
        builder.add_node("reject_citations", self._reject_citations)
        builder.add_node("verifier", self._verifier)
        builder.add_edge(START, "load_context")
        builder.add_edge("load_context", "commander")
        builder.add_conditional_edges("commander", self._fan_out, ["investigate"])
        builder.add_edge("investigate", "synthesize")
        builder.add_edge("synthesize", "citation_guard")
        builder.add_conditional_edges(
            "citation_guard",
            self._route_after_citation_guard,
            ["reject_citations", "verifier"],
        )
        builder.add_edge("reject_citations", END)
        builder.add_edge("verifier", END)
        return builder.compile(checkpointer=checkpointer)

    def _load_context(self, state: RcaState) -> dict[str, Any]:
        evidence_ids = [item["id"] for item in state["evidence"]]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise RcaGraphError("duplicate Evidence IDs in graph context")
        output = {"incident_id": state["incident"]["id"], "evidence_ids": evidence_ids}
        return {"steps": [step("load_context", output)]}

    def _commander(self, state: RcaState) -> dict[str, Any]:
        catalog = [
            {
                "id": item["id"],
                "kind": item["kind"],
                "source": item["source"],
                "observed_at": item["observed_at"],
            }
            for item in state["evidence"]
        ]
        commander_incident = dict(state["incident"])
        commander_incident["historical_memory"] = state.get("historical_memory", [])
        plan = self.model.plan(commander_incident, catalog)
        tasks = []
        for task in plan.tasks:
            allowed_kinds = ROLE_EVIDENCE_KINDS[task.role]
            assigned_ids = [
                item["id"] for item in state["evidence"] if item["kind"] in allowed_kinds
            ]
            tasks.append(task.model_copy(update={"evidence_ids": assigned_ids}))
        normalized = InvestigationPlan(tasks=tasks)
        output = normalized.model_dump(mode="json")
        return {"plan": output, "steps": [step("commander", output, "commander")]}

    def _fan_out(self, state: RcaState) -> list[Send]:
        plan = InvestigationPlan.model_validate(state["plan"])
        evidence_by_id = {item["id"]: item for item in state["evidence"]}
        return [
            Send(
                "investigate",
                {
                    "incident": state["incident"],
                    "task": task.model_dump(mode="json"),
                    "task_evidence": [
                        evidence_by_id[evidence_id]
                        for evidence_id in task.evidence_ids
                    ],
                },
            )
            for task in plan.tasks
        ]

    def _investigate(self, state: RcaState) -> dict[str, Any]:
        task = InvestigationTask.model_validate(state["task"])
        evidence = state.get("task_evidence", [])
        finding = self.model.investigate(state["incident"], task, evidence)
        if finding.task_id != task.task_id or finding.role != task.role:
            raise RcaGraphError("investigator returned the wrong task identity")
        allowed_ids = set(task.evidence_ids)
        invalid_ids = set(finding.evidence_ids) - allowed_ids
        if invalid_ids:
            raise RcaGraphError(
                f"investigator cited Evidence outside its subcontext: {sorted(invalid_ids)}"
            )
        if not allowed_ids and (
            finding.observations
            or finding.hypotheses
            or finding.evidence_ids
            or not finding.limitations
        ):
            raise RcaGraphError(
                f"{task.role.value} produced claims without Evidence"
            )
        output = finding.model_dump(mode="json")
        return {
            "findings": [output],
            "steps": [step("investigate", output, task.role.value)],
        }

    def _synthesize(self, state: RcaState) -> dict[str, Any]:
        findings = [InvestigatorFinding.model_validate(item) for item in state["findings"]]
        draft = self.model.synthesize(state["incident"], findings)
        output = draft.model_dump(mode="json")
        return {
            "draft": output,
            "steps": [step("synthesize", output, "rca_synthesizer")],
        }

    def _citation_guard(self, state: RcaState) -> dict[str, Any]:
        draft = RcaDraft.model_validate(state["draft"])
        available = {item["id"] for item in state["evidence"]}
        invalid = sorted(set(draft.evidence_ids) - available)
        errors = invalid.copy()
        output = {"valid": not errors, "invalid_evidence_ids": invalid}
        return {
            "citation_errors": errors,
            "steps": [step("citation_guard", output)],
        }

    @staticmethod
    def _route_after_citation_guard(state: RcaState) -> str:
        return "reject_citations" if state["citation_errors"] else "verifier"

    def _reject_citations(self, state: RcaState) -> dict[str, Any]:
        verification = VerificationResult(
            decision=VerificationDecision.REJECTED,
            rationale="RCA cited Evidence that does not belong to this Incident.",
            invalid_evidence_ids=state["citation_errors"],
            unsupported_claims=[],
        )
        output = verification.model_dump(mode="json")
        return {
            "verification": output,
            "steps": [step("reject_citations", output, "citation_guard")],
        }

    def _verifier(self, state: RcaState) -> dict[str, Any]:
        draft = RcaDraft.model_validate(state["draft"])
        cited = set(draft.evidence_ids)
        evidence = [item for item in state["evidence"] if item["id"] in cited]
        verification = self.model.verify(state["incident"], draft, evidence)
        if verification.invalid_evidence_ids or verification.unsupported_claims:
            verification = verification.model_copy(
                update={"decision": VerificationDecision.REJECTED}
            )
        output = verification.model_dump(mode="json")
        return {
            "verification": output,
            "steps": [step("verifier", output, "independent_verifier")],
        }

    def invoke(
        self,
        incident: dict[str, Any],
        evidence: list[dict[str, Any]],
        run_id: str | None = None,
        historical_memory: list[dict[str, Any]] | None = None,
    ) -> RcaState:
        config = {"configurable": {"thread_id": run_id}} if run_id else None
        return self.graph.invoke(
            {
                "incident": incident,
                "evidence": evidence,
                "historical_memory": historical_memory or [],
                "findings": [],
                "steps": [],
            },
            config=config,
        )

    def resume(self, run_id: str) -> RcaState:
        return self.graph.invoke(
            None,
            config={"configurable": {"thread_id": run_id}},
        )
