from datetime import UTC, datetime
from pathlib import Path

import pytest

from axiom_ops.control_plane.evidence_service import EvidenceService, IncidentNotFound
from axiom_ops.control_plane.evidence_storage import (
    EvidenceIntegrityError,
    EvidenceStorage,
)
from axiom_ops.control_plane.models import HealthToolInput, MetricsToolInput


class MissingIncidentRepository:
    def incident_exists(self, incident_id: str) -> bool:
        return False


class FailingIfExecutedTool:
    name = "must-not-run"
    kind = type("Kind", (), {"value": "METRIC_SNAPSHOT"})()

    def execute(self, tool_input: object) -> tuple[datetime, dict]:
        raise AssertionError("tool executed before incident validation")


def test_evidence_storage_is_write_once_and_hash_verified(tmp_path: Path) -> None:
    storage = EvidenceStorage(tmp_path)
    content = {"tool_name": "test", "data": {"value": 42}}

    artifact = storage.write("incident-1", "evidence-1", content)

    assert storage.read_verified(
        artifact.relative_path,
        artifact.content_sha256,
    ) == content
    with pytest.raises(FileExistsError):
        storage.write("incident-1", "evidence-1", content)


def test_evidence_storage_detects_tampering(tmp_path: Path) -> None:
    storage = EvidenceStorage(tmp_path)
    artifact = storage.write("incident-1", "evidence-1", {"value": 42})
    (tmp_path / artifact.relative_path).write_text('{"value":43}', encoding="utf-8")

    with pytest.raises(EvidenceIntegrityError, match="hash mismatch"):
        storage.read_verified(artifact.relative_path, artifact.content_sha256)


@pytest.mark.parametrize(
    ("method", "tool_input"),
    [
        ("execute_metrics", MetricsToolInput(signal="order_duration_total")),
        ("execute_health", HealthToolInput(service="order-service")),
    ],
)
def test_missing_incident_is_rejected_before_tool_execution(
    tmp_path: Path,
    method: str,
    tool_input: object,
) -> None:
    tool = FailingIfExecutedTool()
    service = EvidenceService(
        MissingIncidentRepository(),
        EvidenceStorage(tmp_path),
        tool,
        tool,
    )

    with pytest.raises(IncidentNotFound):
        getattr(service, method)("missing", tool_input)
