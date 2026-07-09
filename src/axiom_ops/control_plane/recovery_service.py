from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.models import (
    RecoveryAction,
    RecoveryApprovalView,
    RecoveryExecutionStatus,
    RecoveryExecutionView,
    RecoveryRequest,
)
from axiom_ops.control_plane.rca_repository import RcaRepository
from axiom_ops.control_plane.recovery_repository import RecoveryRepository
from axiom_ops.control_plane.repository import IncidentRepository


class RecoveryNotFound(Exception):
    pass


class RecoveryPermissionError(Exception):
    pass


class RecoveryTransitionError(Exception):
    pass


@dataclass(frozen=True)
class RecoveryOutcome:
    status: RecoveryExecutionStatus
    sandbox: bool
    before_state: dict
    action_result: dict
    verification: dict
    rollback: dict | None = None
    error: str | None = None


class RecoveryExecutor(Protocol):
    def execute(self, action: RecoveryAction) -> RecoveryOutcome:
        pass


class SandboxRecoveryExecutor:
    def __init__(self, settings: ControlPlaneSettings) -> None:
        self.inventory_url = settings.inventory_service_url.rstrip("/")
        self.order_url = settings.order_service_url.rstrip("/")

    def execute(self, action: RecoveryAction) -> RecoveryOutcome:
        if action != RecoveryAction.RESET_INVENTORY_FAULT:
            raise RecoveryTransitionError(f"unsupported recovery action: {action}")
        before_state: dict = {}
        action_result: dict = {}
        rollback: dict | None = None
        try:
            with httpx.Client(timeout=8) as client:
                before_state = self._get_fault_state(client)
                action_result = self._reset_inventory_fault(client)
                verification = self._verify_order_flow(client)
                if verification.get("passed") is True:
                    return RecoveryOutcome(
                        status=RecoveryExecutionStatus.SUCCEEDED,
                        sandbox=True,
                        before_state=before_state,
                        action_result=action_result,
                        verification=verification,
                    )
                rollback = self._restore_fault_state(client, before_state)
        except Exception as exc:
            if before_state and action_result and rollback is None:
                try:
                    with httpx.Client(timeout=8) as client:
                        rollback = self._restore_fault_state(client, before_state)
                except Exception as rollback_exc:
                    rollback = {"restored": False, "error": str(rollback_exc)}
            return RecoveryOutcome(
                status=RecoveryExecutionStatus.FAILED,
                sandbox=True,
                before_state=before_state,
                action_result=action_result,
                verification={"passed": False},
                rollback=rollback,
                error=str(exc),
            )
        return RecoveryOutcome(
            status=RecoveryExecutionStatus.ROLLED_BACK,
            sandbox=True,
            before_state=before_state,
            action_result=action_result,
            verification=verification,
            rollback=rollback,
            error="post-recovery verification failed",
        )

    def _get_fault_state(self, client: httpx.Client) -> dict:
        response = client.get(f"{self.inventory_url}/admin/faults")
        response.raise_for_status()
        return response.json()

    def _reset_inventory_fault(self, client: httpx.Client) -> dict:
        response = client.post(f"{self.inventory_url}/admin/faults/reset")
        response.raise_for_status()
        return response.json()

    def _verify_order_flow(self, client: httpx.Client) -> dict:
        health = client.get(f"{self.inventory_url}/health")
        order = client.get(f"{self.order_url}/orders/phase6-recovery-check")
        passed = health.status_code == 200 and order.status_code == 200
        return {
            "passed": passed,
            "inventory_health_status": health.status_code,
            "order_flow_status": order.status_code,
        }

    def _restore_fault_state(self, client: httpx.Client, before_state: dict) -> dict:
        payload = {
            "mode": before_state.get("mode", "none"),
            "delay_ms": before_state.get("delay_ms", 0),
            "error_rate": before_state.get("error_rate", 0.0),
        }
        response = client.post(f"{self.inventory_url}/admin/faults", json=payload)
        response.raise_for_status()
        return {"restored": True, "state": response.json()}


class RecoveryService:
    def __init__(
        self,
        incidents: IncidentRepository,
        rca_repository: RcaRepository,
        recovery_repository: RecoveryRepository,
        executor: RecoveryExecutor,
    ) -> None:
        self.incidents = incidents
        self.rca_repository = rca_repository
        self.recovery_repository = recovery_repository
        self.executor = executor

    def request_recovery(
        self,
        incident_id: str,
        request: RecoveryRequest,
        requested_by: str,
    ) -> RecoveryApprovalView:
        if self.incidents.get_incident(incident_id) is None:
            raise RecoveryNotFound("incident not found")
        report = self.rca_repository.get_report_for_run(request.run_id)
        if report is None or report.incident_id != incident_id:
            raise RecoveryTransitionError("recovery requires a verified RCA for this incident")
        return self.recovery_repository.create_approval(
            incident_id,
            request.run_id,
            request.action,
            request.reason,
            requested_by,
        )

    def approve(
        self,
        approval_id: str,
        approved_by: str,
        approval_comment: str,
    ) -> RecoveryApprovalView:
        approval = self.recovery_repository.get_approval(approval_id)
        if approval is None:
            raise RecoveryNotFound("recovery approval not found")
        if approval.requested_by == approved_by:
            raise RecoveryPermissionError("requester cannot approve their own recovery")
        if approval.status != "PENDING":
            raise RecoveryTransitionError("recovery approval is not pending")
        return self.recovery_repository.approve(
            approval_id,
            approved_by,
            approval_comment,
        )

    def execute(self, approval_id: str, executed_by: str) -> RecoveryExecutionView:
        approval = self.recovery_repository.get_approval(approval_id)
        if approval is None:
            raise RecoveryNotFound("recovery approval not found")
        if approval.status != "APPROVED":
            raise RecoveryTransitionError("recovery approval is not approved")
        existing = self.recovery_repository.get_execution_for_approval(approval_id)
        if existing is not None:
            return existing
        outcome = self.executor.execute(approval.action)
        return self.recovery_repository.create_execution(
            approval_id=approval.id,
            action=approval.action,
            status=outcome.status,
            executed_by=executed_by,
            sandbox=outcome.sandbox,
            before_state=outcome.before_state,
            action_result=outcome.action_result,
            verification=outcome.verification,
            rollback=outcome.rollback,
            error=outcome.error,
        )

    def get_approval(self, approval_id: str) -> RecoveryApprovalView:
        approval = self.recovery_repository.get_approval(approval_id)
        if approval is None:
            raise RecoveryNotFound("recovery approval not found")
        return approval

    def get_execution(self, execution_id: str) -> RecoveryExecutionView:
        execution = self.recovery_repository.get_execution(execution_id)
        if execution is None:
            raise RecoveryNotFound("recovery execution not found")
        return execution
