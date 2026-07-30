"""A safe MCP facade over AxiomOps evidence and recovery services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.evidence_repository import EvidenceRepository
from axiom_ops.control_plane.evidence_service import EvidenceService
from axiom_ops.control_plane.evidence_storage import EvidenceStorage
from axiom_ops.control_plane.models import (
    FaultStateToolInput,
    HealthToolInput,
    LabService,
    MetricSignal,
    MetricsToolInput,
    OrderFlowProbeInput,
)
from axiom_ops.control_plane.recovery_repository import RecoveryRepository
from axiom_ops.control_plane.recovery_service import RecoveryService, SandboxRecoveryExecutor
from axiom_ops.control_plane.rca_repository import RcaRepository
from axiom_ops.control_plane.repository import IncidentRepository
from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.typed_tools import (
    InventoryFaultStateTool,
    MetricsSnapshotTool,
    OrderFlowProbeTool,
    ServiceHealthTool,
)


@dataclass(frozen=True)
class McpServiceIdentity:
    """Trusted process identity, intentionally not controlled by tool input."""

    user: str = "axiomops-mcp"
    role: str = "investigator"


def _as_json(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json")


def create_axiomops_mcp(
    evidence_service: EvidenceService,
    recovery_service: RecoveryService,
    identity: McpServiceIdentity = McpServiceIdentity(),
) -> FastMCP:
    """Create the MCP server without coupling it to a transport or database setup."""

    server = FastMCP(
        "AxiomOps Control Plane",
        instructions=(
            "Use read-only diagnostic tools to collect evidence. "
            "Recovery may only execute against an already approved approval ID."
        ),
        json_response=True,
    )

    def tool_error(action: str, exc: Exception) -> ToolError:
        return ToolError(f"{action} rejected: {exc}")

    @server.tool(name="collect_metrics")
    def collect_metrics(incident_id: str, signal: MetricSignal) -> dict[str, Any]:
        """Collect one allowlisted Prometheus signal and persist it as incident evidence."""
        try:
            return _as_json(
                evidence_service.execute_metrics(
                    incident_id, MetricsToolInput(signal=signal)
                )
            )
        except Exception as exc:
            raise tool_error("metrics collection", exc) from exc

    @server.tool(name="check_service_health")
    def check_service_health(
        incident_id: str, service: LabService
    ) -> dict[str, Any]:
        """Run an allowlisted health probe and persist the result as incident evidence."""
        try:
            return _as_json(
                evidence_service.execute_health(
                    incident_id, HealthToolInput(service=service)
                )
            )
        except Exception as exc:
            raise tool_error("health check", exc) from exc

    @server.tool(name="inspect_inventory_fault")
    def inspect_inventory_fault(incident_id: str) -> dict[str, Any]:
        """Read the fixed inventory Lab fault state and persist it as evidence."""
        try:
            return _as_json(
                evidence_service.execute_fault_state(incident_id, FaultStateToolInput())
            )
        except Exception as exc:
            raise tool_error("fault-state inspection", exc) from exc

    @server.tool(name="probe_order_flow")
    def probe_order_flow(incident_id: str) -> dict[str, Any]:
        """Probe the fixed order-to-inventory flow and persist the result as evidence."""
        try:
            return _as_json(
                evidence_service.execute_order_flow(incident_id, OrderFlowProbeInput())
            )
        except Exception as exc:
            raise tool_error("order-flow probe", exc) from exc

    @server.tool(name="execute_approved_recovery")
    def execute_approved_recovery(approval_id: str) -> dict[str, Any]:
        """Execute a pre-approved sandbox recovery as the fixed MCP operator identity."""
        if identity.role != "operator":
            raise ToolError("recovery execution requires an MCP process with operator role")
        try:
            return _as_json(recovery_service.execute(approval_id, identity.user))
        except Exception as exc:
            raise tool_error("recovery execution", exc) from exc

    return server


def create_default_axiomops_mcp() -> FastMCP:
    """Build the stdio server with the same concrete services as the control plane."""
    settings = ControlPlaneSettings()
    database = Database(settings)
    evidence_service = EvidenceService(
        EvidenceRepository(database),
        EvidenceStorage(settings.evidence_root),
        MetricsSnapshotTool(settings),
        ServiceHealthTool(settings),
        InventoryFaultStateTool(settings),
        OrderFlowProbeTool(settings),
    )
    recovery_service = RecoveryService(
        IncidentRepository(database),
        RcaRepository(database),
        RecoveryRepository(database),
        SandboxRecoveryExecutor(settings),
    )
    return create_axiomops_mcp(
        evidence_service,
        recovery_service,
        McpServiceIdentity(
            user=os.getenv("AXIOMOPS_MCP_USER", "axiomops-mcp"),
            role=os.getenv("AXIOMOPS_MCP_ROLE", "investigator"),
        ),
    )


def main() -> None:
    create_default_axiomops_mcp().run(transport="stdio")


if __name__ == "__main__":
    main()
