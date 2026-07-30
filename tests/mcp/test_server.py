import asyncio
from datetime import UTC, datetime

import pytest

from axiom_ops.control_plane.models import (
    EvidenceKind,
    EvidenceView,
    RecoveryAction,
    RecoveryExecutionStatus,
    RecoveryExecutionView,
)
from axiom_ops.mcp.server import McpServiceIdentity, create_axiomops_mcp


class FakeEvidenceService:
    def execute_metrics(self, incident_id: str, tool_input: object) -> EvidenceView:
        return self._evidence(incident_id, "prometheus.metrics.snapshot", EvidenceKind.METRIC_SNAPSHOT)

    def execute_health(self, incident_id: str, tool_input: object) -> EvidenceView:
        return self._evidence(incident_id, "http.service.health", EvidenceKind.SERVICE_HEALTH)

    def execute_fault_state(self, incident_id: str, tool_input: object) -> EvidenceView:
        return self._evidence(incident_id, "http.inventory.fault_state", EvidenceKind.FAULT_STATE)

    def execute_order_flow(self, incident_id: str, tool_input: object) -> EvidenceView:
        return self._evidence(incident_id, "http.order.flow_probe", EvidenceKind.ORDER_FLOW_PROBE)

    @staticmethod
    def _evidence(incident_id: str, tool_name: str, kind: EvidenceKind) -> EvidenceView:
        now = datetime.now(UTC)
        return EvidenceView(
            id="evidence-1",
            incident_id=incident_id,
            kind=kind,
            tool_name=tool_name,
            tool_input={},
            source="test",
            artifact_path="incident-1/evidence-1.json",
            content_sha256="a" * 64,
            byte_size=10,
            observed_at=now,
            created_at=now,
        )


class FakeRecoveryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def execute(self, approval_id: str, executed_by: str) -> RecoveryExecutionView:
        self.calls.append((approval_id, executed_by))
        now = datetime.now(UTC)
        return RecoveryExecutionView(
            id="execution-1",
            approval_id=approval_id,
            action=RecoveryAction.RESET_INVENTORY_FAULT,
            status=RecoveryExecutionStatus.SUCCEEDED,
            executed_by=executed_by,
            sandbox=True,
            before_state={},
            action_result={},
            verification={"passed": True},
            rollback=None,
            error=None,
            started_at=now,
            completed_at=now,
        )


def test_mcp_exposes_only_allowlisted_diagnostic_and_recovery_tools() -> None:
    server = create_axiomops_mcp(FakeEvidenceService(), FakeRecoveryService())

    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == {
        "collect_metrics",
        "check_service_health",
        "inspect_inventory_fault",
        "probe_order_flow",
        "execute_approved_recovery",
    }


def test_mcp_read_only_tool_returns_persisted_evidence() -> None:
    server = create_axiomops_mcp(FakeEvidenceService(), FakeRecoveryService())

    result = asyncio.run(
        server.call_tool(
            "collect_metrics",
            {"incident_id": "incident-1", "signal": "inventory_active_fault"},
        )
    )

    assert result[1]["incident_id"] == "incident-1"
    assert result[1]["kind"] == "METRIC_SNAPSHOT"


def test_mcp_recovery_is_rejected_without_operator_process_identity() -> None:
    recovery_service = FakeRecoveryService()
    server = create_axiomops_mcp(
        FakeEvidenceService(),
        recovery_service,
        McpServiceIdentity(user="mcp-reader", role="investigator"),
    )

    with pytest.raises(Exception, match="operator role"):
        asyncio.run(server.call_tool("execute_approved_recovery", {"approval_id": "approval-1"}))
    assert recovery_service.calls == []


def test_mcp_recovery_uses_fixed_operator_identity() -> None:
    recovery_service = FakeRecoveryService()
    server = create_axiomops_mcp(
        FakeEvidenceService(),
        recovery_service,
        McpServiceIdentity(user="mcp-operator", role="operator"),
    )

    result = asyncio.run(
        server.call_tool("execute_approved_recovery", {"approval_id": "approval-1"})
    )

    assert result[1]["executed_by"] == "mcp-operator"
    assert recovery_service.calls == [("approval-1", "mcp-operator")]
