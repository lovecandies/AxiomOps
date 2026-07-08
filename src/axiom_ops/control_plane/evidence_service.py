from typing import Any
from uuid import uuid4

from axiom_ops.control_plane.evidence_repository import EvidenceRepository
from axiom_ops.control_plane.evidence_storage import EvidenceStorage
from axiom_ops.control_plane.models import (
    EvidenceView,
    HealthToolInput,
    MetricsToolInput,
    ToolObservation,
)
from axiom_ops.control_plane.typed_tools import MetricsSnapshotTool, ServiceHealthTool


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
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.metrics_tool = metrics_tool
        self.health_tool = health_tool

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
