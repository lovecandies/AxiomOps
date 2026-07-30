from datetime import UTC, datetime
from pathlib import Path

import pytest

from axiom_ops.control_plane.evidence_service import EvidenceService, IncidentNotFound
from axiom_ops.control_plane.evidence_storage import (
    EvidenceIntegrityError,
    EvidenceStorage,
)
from axiom_ops.control_plane.models import (
    DiagnosticToolName,
    EvidenceView,
    HealthToolInput,
    MetricsToolInput,
    ToolSelectionItem,
    ToolSelectionPlan,
)


class MissingIncidentRepository:
    def incident_exists(self, incident_id: str) -> bool:
        return False


class FailingIfExecutedTool:
    name = "must-not-run"
    kind = type("Kind", (), {"value": "METRIC_SNAPSHOT"})()

    def execute(self, tool_input: object) -> tuple[datetime, dict]:
        raise AssertionError("tool executed before incident validation")


class ExistingEvidenceRepository:
    def __init__(self, kinds: list[str]) -> None:
        self.kinds = kinds

    def incident_exists(self, incident_id: str) -> bool:
        return True

    def list_for_incident(self, incident_id: str) -> list[EvidenceView]:
        now = datetime.now(UTC)
        return [
            EvidenceView.model_validate(
                {
                    "id": f"evidence-{index}",
                    "incident_id": incident_id,
                    "kind": kind,
                    "tool_name": "test",
                    "tool_input": {},
                    "source": "test",
                    "artifact_path": "test.json",
                    "content_sha256": "0" * 64,
                    "byte_size": 2,
                    "observed_at": now,
                    "created_at": now,
                }
            )
            for index, kind in enumerate(self.kinds)
        ]


class ProposalPlanner:
    def plan_tools(self, incident, evidence_catalog) -> ToolSelectionPlan:
        return ToolSelectionPlan(
            objective="Collect causal evidence.",
            selections=[
                ToolSelectionItem(tool=DiagnosticToolName.METRICS, reason="valid"),
                ToolSelectionItem(tool=DiagnosticToolName.METRICS, reason="duplicate"),
                ToolSelectionItem(tool=DiagnosticToolName.FAULT_STATE, reason="already exists"),
            ],
        )


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


def test_tool_selection_plans_only_missing_allowlisted_evidence(tmp_path: Path) -> None:
    tool = FailingIfExecutedTool()
    service = EvidenceService(
        ExistingEvidenceRepository(["FAULT_STATE", "ORDER_FLOW_PROBE"]),
        EvidenceStorage(tmp_path),
        tool,
        tool,
    )

    plan = service.plan_tool_selection("incident-1")

    assert [selection.tool for selection in plan.selections] == [
        "metrics",
        "health",
        "trace",
        "change",
    ]
    assert all(selection.reason for selection in plan.selections)


def test_model_tool_plan_is_canonicalized_and_rejects_duplicates(tmp_path: Path) -> None:
    tool = FailingIfExecutedTool()
    service = EvidenceService(
        ExistingEvidenceRepository(["FAULT_STATE", "ORDER_FLOW_PROBE"]),
        EvidenceStorage(tmp_path),
        tool,
        tool,
        tool_planner_factory=ProposalPlanner,
    )

    plan = service.plan_tool_selection("incident-1")

    assert plan.strategy == "model"
    assert [item.tool for item in plan.selections] == ["metrics"]
    assert plan.selections[0].tool_input == {"signal": "order_downstream_failures"}
    assert plan.rejected_proposals == 2
