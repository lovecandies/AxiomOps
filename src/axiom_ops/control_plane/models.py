from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


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


class EvidenceKind(StrEnum):
    METRIC_SNAPSHOT = "METRIC_SNAPSHOT"
    SERVICE_HEALTH = "SERVICE_HEALTH"


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
