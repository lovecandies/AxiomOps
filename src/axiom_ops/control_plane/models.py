from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class IncidentStatus(StrEnum):
    RECEIVED = "RECEIVED"
    INVESTIGATION_QUEUED = "INVESTIGATION_QUEUED"


class Severity(StrEnum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    service: str = Field(min_length=1, max_length=128)
    severity: Severity
    summary: str = Field(min_length=1, max_length=2000)


class IncidentEvent(BaseModel):
    event_type: str
    from_status: IncidentStatus | None
    to_status: IncidentStatus
    created_at: datetime


class OutboxState(BaseModel):
    event_id: str
    event_type: str
    status: str
    attempts: int
    broker_message_id: str | None


class IncidentView(BaseModel):
    id: str
    idempotency_key: str
    title: str
    service: str
    severity: Severity
    summary: str
    status: IncidentStatus
    version: int
    created_at: datetime
    updated_at: datetime
    events: list[IncidentEvent]
    outbox: list[OutboxState]


class ClaimedOutboxEvent(BaseModel):
    id: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]


class MetricSignal(StrEnum):
    ORDER_DURATION_TOTAL = "order_duration_total"
    ORDER_DOWNSTREAM_FAILURES = "order_downstream_failures"
    INVENTORY_ACTIVE_FAULT = "inventory_active_fault"


class LabService(StrEnum):
    ORDER = "order-service"
    INVENTORY = "inventory-service"


class MetricsToolInput(BaseModel):
    signal: MetricSignal


class HealthToolInput(BaseModel):
    service: LabService


class FaultStateToolInput(BaseModel):
    """No caller-controlled target: only the inventory Lab fault state is readable."""


class OrderFlowProbeInput(BaseModel):
    """No caller-controlled target: only the fixed Lab order probe is readable."""


class TraceSnapshotToolInput(BaseModel):
    service: LabService = LabService.ORDER


class ChangeEventToolInput(BaseModel):
    service: LabService = LabService.INVENTORY


class EvidenceKind(StrEnum):
    METRIC_SNAPSHOT = "METRIC_SNAPSHOT"
    SERVICE_HEALTH = "SERVICE_HEALTH"
    FAULT_STATE = "FAULT_STATE"
    ORDER_FLOW_PROBE = "ORDER_FLOW_PROBE"
    TRACE_SNAPSHOT = "TRACE_SNAPSHOT"
    CHANGE_EVENT = "CHANGE_EVENT"


class DiagnosticToolName(StrEnum):
    METRICS = "metrics"
    HEALTH = "health"
    FAULT_STATE = "fault_state"
    ORDER_FLOW = "order_flow"
    TRACE = "trace"
    CHANGE = "change"


class ToolSelectionItem(BaseModel):
    tool: DiagnosticToolName
    reason: str = Field(min_length=1, max_length=500)
    tool_input: dict[str, Any] = Field(default_factory=dict)


class ToolSelectionPlan(BaseModel):
    objective: str = Field(min_length=1, max_length=500)
    selections: list[ToolSelectionItem] = Field(default_factory=list, max_length=10)


class EvidenceView(BaseModel):
    id: str
    incident_id: str
    kind: EvidenceKind
    tool_name: str
    tool_input: dict[str, Any]
    source: str
    artifact_path: str
    content_sha256: str
    byte_size: int
    observed_at: datetime
    created_at: datetime


class StoredArtifact(BaseModel):
    relative_path: str
    content_sha256: str
    byte_size: int


class ToolObservation(BaseModel):
    schema_version: Literal[1] = 1
    tool_name: str
    kind: EvidenceKind
    input: dict[str, Any]
    source: str
    observed_at: datetime
    duration_ms: float = Field(ge=0)
    data: dict[str, Any]


class InvestigatorRole(StrEnum):
    METRICS = "metrics_investigator"
    LOGS_TRACE = "logs_trace_investigator"
    CHANGE = "change_investigator"


class InvestigationTask(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    role: InvestigatorRole
    question: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationPlan(BaseModel):
    tasks: list[InvestigationTask] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def require_all_roles(self) -> "InvestigationPlan":
        roles = {task.role for task in self.tasks}
        if roles != set(InvestigatorRole):
            raise ValueError("plan must contain exactly one task for every investigator")
        if len({task.task_id for task in self.tasks}) != len(self.tasks):
            raise ValueError("task ids must be unique")
        return self


class InvestigatorFinding(BaseModel):
    task_id: str
    role: InvestigatorRole
    summary: str = Field(min_length=1, max_length=2000)
    observations: list[str] = Field(default_factory=list, max_length=20)
    hypotheses: list[str] = Field(default_factory=list, max_length=10)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class RcaDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    root_cause: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    contributing_factors: list[str] = Field(default_factory=list, max_length=20)
    rejected_hypotheses: list[str] = Field(default_factory=list, max_length=20)
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class VerificationDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VerificationResult(BaseModel):
    decision: VerificationDecision
    rationale: str = Field(min_length=1, max_length=3000)
    invalid_evidence_ids: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=20)


class RcaRunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class RcaRunStep(BaseModel):
    node_name: str
    role: str | None
    output: dict[str, Any]
    created_at: datetime


class RcaContextView(BaseModel):
    original_bytes: int
    compressed_bytes: int
    capsules: list[dict[str, Any]]
    created_at: datetime


class RcaRunView(BaseModel):
    id: str
    incident_id: str
    status: RcaRunStatus
    model: str
    graph_version: str
    evidence_ids: list[str]
    verification: VerificationResult | None
    error: str | None
    model_calls: int
    total_tokens: int
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None
    steps: list[RcaRunStep]
    context: RcaContextView | None = None


class RcaReportView(BaseModel):
    id: str
    run_id: str
    incident_id: str
    summary: str
    root_cause: str
    confidence: float
    contributing_factors: list[str]
    rejected_hypotheses: list[str]
    evidence_ids: list[str]
    limitations: list[str]
    verification: VerificationResult
    created_at: datetime


class RecoveryAction(StrEnum):
    RESET_INVENTORY_FAULT = "reset_inventory_fault"


class RecoveryApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"


class RecoveryExecutionStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class RecoveryRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=36)
    action: RecoveryAction
    reason: str = Field(min_length=1, max_length=1000)


class RecoveryDecisionRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=1000)


class RecoveryApprovalView(BaseModel):
    id: str
    incident_id: str
    run_id: str
    action: RecoveryAction
    status: RecoveryApprovalStatus
    reason: str
    requested_by: str
    approved_by: str | None
    approval_comment: str | None
    requested_at: datetime
    approved_at: datetime | None


class RecoveryExecutionView(BaseModel):
    id: str
    approval_id: str
    action: RecoveryAction
    status: RecoveryExecutionStatus
    executed_by: str
    sandbox: bool
    before_state: dict[str, Any]
    action_result: dict[str, Any]
    verification: dict[str, Any]
    rollback: dict[str, Any] | None
    error: str | None
    started_at: datetime
    completed_at: datetime
