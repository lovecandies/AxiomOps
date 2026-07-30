from typing import Any
from collections.abc import Callable
from uuid import uuid4

from axiom_ops.control_plane.evidence_repository import EvidenceRepository
from axiom_ops.control_plane.evidence_storage import EvidenceStorage
from axiom_ops.control_plane.models import (
    ChangeEventToolInput,
    DiagnosticToolName,
    EvidenceKind,
    EvidenceView,
    FaultStateToolInput,
    HealthToolInput,
    LabService,
    MetricSignal,
    MetricsToolInput,
    OrderFlowProbeInput,
    ToolSelectionItem,
    ToolSelectionPlan,
    TraceSnapshotToolInput,
    ToolObservation,
)
from axiom_ops.control_plane.typed_tools import (
    ChangeEventTool,
    InventoryFaultStateTool,
    MetricsSnapshotTool,
    OrderFlowProbeTool,
    ServiceHealthTool,
    TraceSnapshotTool,
)
from axiom_ops.control_plane.tool_planner import ToolPlanner


class EvidenceNotFound(Exception):
    pass


class IncidentNotFound(Exception):
    pass


class EvidenceService:
    def __init__(
        self,
        repository: EvidenceRepository,
        storage: EvidenceStorage,
        metrics_tool: MetricsSnapshotTool,
        health_tool: ServiceHealthTool,
        fault_state_tool: InventoryFaultStateTool | None = None,
        order_flow_tool: OrderFlowProbeTool | None = None,
        trace_tool: TraceSnapshotTool | None = None,
        change_tool: ChangeEventTool | None = None,
        tool_planner_factory: Callable[[], ToolPlanner] | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.metrics_tool = metrics_tool
        self.health_tool = health_tool
        self.fault_state_tool = fault_state_tool
        self.order_flow_tool = order_flow_tool
        self.trace_tool = trace_tool
        self.change_tool = change_tool
        self.tool_planner_factory = tool_planner_factory

    def _ensure_incident(self, incident_id: str) -> None:
        if not self.repository.incident_exists(incident_id):
            raise IncidentNotFound(incident_id)

    def _persist(
        self,
        incident_id: str,
        observation: ToolObservation,
    ) -> EvidenceView:
        evidence_id = str(uuid4())
        content = observation.model_dump(mode="json")
        artifact = self.storage.write(incident_id, evidence_id, content)
        return self.repository.create(
            evidence_id,
            incident_id,
            observation.kind.value,
            observation.tool_name,
            observation.input,
            observation.source,
            observation.observed_at,
            artifact,
        )

    def execute_metrics(
        self,
        incident_id: str,
        tool_input: MetricsToolInput,
    ) -> EvidenceView:
        self._ensure_incident(incident_id)
        observation = self.metrics_tool.execute(tool_input)
        return self._persist(incident_id, observation)

    def execute_health(
        self,
        incident_id: str,
        tool_input: HealthToolInput,
    ) -> EvidenceView:
        self._ensure_incident(incident_id)
        observation = self.health_tool.execute(tool_input)
        return self._persist(incident_id, observation)

    def execute_fault_state(
        self, incident_id: str, tool_input: FaultStateToolInput
    ) -> EvidenceView:
        self._ensure_incident(incident_id)
        if self.fault_state_tool is None:
            raise RuntimeError("fault-state tool is not configured")
        return self._persist(incident_id, self.fault_state_tool.execute(tool_input))

    def execute_order_flow(
        self, incident_id: str, tool_input: OrderFlowProbeInput
    ) -> EvidenceView:
        self._ensure_incident(incident_id)
        if self.order_flow_tool is None:
            raise RuntimeError("order-flow tool is not configured")
        return self._persist(incident_id, self.order_flow_tool.execute(tool_input))

    def execute_trace_snapshot(
        self, incident_id: str, tool_input: TraceSnapshotToolInput
    ) -> EvidenceView:
        self._ensure_incident(incident_id)
        if self.trace_tool is None:
            raise RuntimeError("trace tool is not configured")
        return self._persist(incident_id, self.trace_tool.execute(tool_input))

    def execute_change_events(
        self, incident_id: str, tool_input: ChangeEventToolInput
    ) -> EvidenceView:
        self._ensure_incident(incident_id)
        if self.change_tool is None:
            raise RuntimeError("change tool is not configured")
        return self._persist(incident_id, self.change_tool.execute(tool_input))

    def _missing_evidence_plan(self, existing_kinds: set[EvidenceKind]) -> ToolSelectionPlan:
        selections: list[ToolSelectionItem] = []
        desired = [
            (
                EvidenceKind.FAULT_STATE,
                DiagnosticToolName.FAULT_STATE,
                {},
                "Confirm the current injected fault before reasoning about cause.",
            ),
            (
                EvidenceKind.ORDER_FLOW_PROBE,
                DiagnosticToolName.ORDER_FLOW,
                {},
                "Probe the business order path to verify user-visible impact.",
            ),
            (
                EvidenceKind.METRIC_SNAPSHOT,
                DiagnosticToolName.METRICS,
                {"signal": MetricSignal.ORDER_DOWNSTREAM_FAILURES.value},
                "Collect downstream failure metrics for the affected order path.",
            ),
            (
                EvidenceKind.SERVICE_HEALTH,
                DiagnosticToolName.HEALTH,
                {"service": LabService.INVENTORY.value},
                "Check whether the dependent inventory service is reachable.",
            ),
            (
                EvidenceKind.TRACE_SNAPSHOT,
                DiagnosticToolName.TRACE,
                {"service": LabService.ORDER.value},
                "Inspect recent order-to-inventory spans for failure or latency.",
            ),
            (
                EvidenceKind.CHANGE_EVENT,
                DiagnosticToolName.CHANGE,
                {"service": LabService.INVENTORY.value},
                "Check recent inventory changes that may explain the incident.",
            ),
        ]
        for kind, tool, tool_input, reason in desired:
            if kind not in existing_kinds:
                selections.append(
                    ToolSelectionItem(
                        tool=tool,
                        reason=reason,
                        tool_input=tool_input,
                    )
                )
        return ToolSelectionPlan(
            objective="Collect missing, allowlisted Evidence for this Incident.",
            selections=selections,
            strategy="deterministic_fallback",
        )

    def plan_tool_selection(self, incident_id: str) -> ToolSelectionPlan:
        self._ensure_incident(incident_id)
        evidence = self.repository.list_for_incident(incident_id)
        existing_kinds = {item.kind for item in evidence}
        fallback = self._missing_evidence_plan(existing_kinds)
        if self.tool_planner_factory is None:
            return fallback
        try:
            proposed = self.tool_planner_factory().plan_tools(
                {"id": incident_id},
                [
                    {"id": item.id, "kind": item.kind.value, "source": item.source}
                    for item in evidence
                ],
            )
        except Exception:
            return fallback
        allowed = {item.tool: item for item in fallback.selections}
        selections: list[ToolSelectionItem] = []
        rejected = 0
        for item in proposed.selections:
            canonical = allowed.get(item.tool)
            if canonical is None or any(selected.tool == item.tool for selected in selections):
                rejected += 1
                continue
            selections.append(canonical)
        if not selections and fallback.selections:
            return fallback.model_copy(update={"rejected_proposals": rejected})
        return ToolSelectionPlan(
            objective=proposed.objective,
            selections=selections,
            strategy="model",
            rejected_proposals=rejected,
        )

    def execute_tool_selection(self, incident_id: str) -> list[EvidenceView]:
        plan = self.plan_tool_selection(incident_id)
        collected: list[EvidenceView] = []
        for selection in plan.selections:
            collected.append(self._execute_selected_tool(incident_id, selection))
        return collected

    def _execute_selected_tool(
        self, incident_id: str, selection: ToolSelectionItem
    ) -> EvidenceView:
        if selection.tool == DiagnosticToolName.METRICS:
            return self.execute_metrics(
                incident_id,
                MetricsToolInput.model_validate(selection.tool_input),
            )
        if selection.tool == DiagnosticToolName.HEALTH:
            return self.execute_health(
                incident_id,
                HealthToolInput.model_validate(selection.tool_input),
            )
        if selection.tool == DiagnosticToolName.FAULT_STATE:
            return self.execute_fault_state(
                incident_id,
                FaultStateToolInput.model_validate(selection.tool_input),
            )
        if selection.tool == DiagnosticToolName.ORDER_FLOW:
            return self.execute_order_flow(
                incident_id,
                OrderFlowProbeInput.model_validate(selection.tool_input),
            )
        if selection.tool == DiagnosticToolName.TRACE:
            return self.execute_trace_snapshot(
                incident_id,
                TraceSnapshotToolInput.model_validate(selection.tool_input),
            )
        if selection.tool == DiagnosticToolName.CHANGE:
            return self.execute_change_events(
                incident_id,
                ChangeEventToolInput.model_validate(selection.tool_input),
            )
        raise RuntimeError(f"unsupported selected tool: {selection.tool}")

    def list_for_incident(self, incident_id: str) -> list[EvidenceView]:
        self._ensure_incident(incident_id)
        return self.repository.list_for_incident(incident_id)

    def read_content(self, evidence_id: str) -> dict[str, Any]:
        evidence = self.repository.get(evidence_id)
        if evidence is None:
            raise EvidenceNotFound(evidence_id)
        return self.storage.read_verified(
            evidence.artifact_path,
            evidence.content_sha256,
        )
