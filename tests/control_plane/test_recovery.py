from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from axiom_ops.control_plane.app import create_control_plane_app
from axiom_ops.control_plane.models import (
    IncidentView,
    RecoveryAction,
    RecoveryApprovalView,
    RecoveryExecutionStatus,
    RecoveryExecutionView,
    RecoveryRequest,
    RcaReportView,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.recovery_service import (
    RecoveryOutcome,
    RecoveryPermissionError,
    RecoveryService,
)
from axiom_ops.control_plane.repository import IncidentRepository


def incident_view() -> IncidentView:
    now = datetime.now(UTC)
    return IncidentView.model_validate(
        {
            "id": "incident-1",
            "idempotency_key": "alert-1",
            "title": "Inventory unavailable",
            "service": "inventory-service",
            "severity": "SEV2",
            "summary": "inventory returns 503",
            "status": "INVESTIGATION_QUEUED",
            "version": 2,
            "created_at": now,
            "updated_at": now,
            "events": [],
            "outbox": [],
        }
    )


def rca_report() -> RcaReportView:
    now = datetime.now(UTC)
    return RcaReportView(
        id="report-1",
        run_id="run-1",
        incident_id="incident-1",
        summary="Inventory fault is active.",
        root_cause="Injected inventory fault.",
        confidence=0.91,
        contributing_factors=[],
        rejected_hypotheses=[],
        evidence_ids=["evidence-1"],
        limitations=[],
        verification=VerificationResult(
            decision=VerificationDecision.APPROVED,
            rationale="supported",
        ),
        created_at=now,
    )


class FakeIncidentRepository:
    def get_incident(self, incident_id: str) -> IncidentView | None:
        return incident_view() if incident_id == "incident-1" else None


class FakeRcaRepository:
    def get_report_for_run(self, run_id: str) -> RcaReportView | None:
        return rca_report() if run_id == "run-1" else None


class FakeRecoveryRepository:
    def __init__(self) -> None:
        self.approval: RecoveryApprovalView | None = None
        self.execution: RecoveryExecutionView | None = None

    def create_approval(
        self,
        incident_id: str,
        run_id: str,
        action: RecoveryAction,
        reason: str,
        requested_by: str,
    ) -> RecoveryApprovalView:
        now = datetime.now(UTC)
        self.approval = RecoveryApprovalView(
            id="approval-1",
            incident_id=incident_id,
            run_id=run_id,
            action=action,
            status="PENDING",
            reason=reason,
            requested_by=requested_by,
            approved_by=None,
            approval_comment=None,
            requested_at=now,
            approved_at=None,
        )
        return self.approval

    def get_approval(self, approval_id: str) -> RecoveryApprovalView | None:
        if self.approval is None or approval_id != self.approval.id:
            return None
        return self.approval

    def approve(
        self,
        approval_id: str,
        approved_by: str,
        approval_comment: str,
    ) -> RecoveryApprovalView:
        assert self.approval is not None
        self.approval = self.approval.model_copy(
            update={
                "status": "APPROVED",
                "approved_by": approved_by,
                "approval_comment": approval_comment,
                "approved_at": datetime.now(UTC),
            }
        )
        return self.approval

    def get_execution_for_approval(
        self,
        approval_id: str,
    ) -> RecoveryExecutionView | None:
        return self.execution if self.execution and approval_id == "approval-1" else None

    def create_execution(
        self,
        approval_id: str,
        action: RecoveryAction,
        status: RecoveryExecutionStatus,
        executed_by: str,
        sandbox: bool,
        before_state: dict,
        action_result: dict,
        verification: dict,
        rollback: dict | None,
        error: str | None,
    ) -> RecoveryExecutionView:
        now = datetime.now(UTC)
        self.execution = RecoveryExecutionView(
            id="execution-1",
            approval_id=approval_id,
            action=action,
            status=status,
            executed_by=executed_by,
            sandbox=sandbox,
            before_state=before_state,
            action_result=action_result,
            verification=verification,
            rollback=rollback,
            error=error,
            started_at=now,
            completed_at=now,
        )
        return self.execution


class FakeExecutor:
    def __init__(self, status: RecoveryExecutionStatus) -> None:
        self.status = status

    def execute(self, action: RecoveryAction) -> RecoveryOutcome:
        return RecoveryOutcome(
            status=self.status,
            sandbox=True,
            before_state={"mode": "unavailable", "delay_ms": 0, "error_rate": 0.0},
            action_result={"mode": "none", "delay_ms": 0, "error_rate": 0.0},
            verification={"passed": self.status == RecoveryExecutionStatus.SUCCEEDED},
            rollback={"restored": True}
            if self.status == RecoveryExecutionStatus.ROLLED_BACK
            else None,
            error="post-recovery verification failed"
            if self.status == RecoveryExecutionStatus.ROLLED_BACK
            else None,
        )


class FailingAfterActionExecutor:
    def execute(self, action: RecoveryAction) -> RecoveryOutcome:
        return RecoveryOutcome(
            status=RecoveryExecutionStatus.FAILED,
            sandbox=True,
            before_state={"mode": "unavailable", "delay_ms": 0, "error_rate": 0.0},
            action_result={"mode": "none", "delay_ms": 0, "error_rate": 0.0},
            verification={"passed": False},
            rollback={"restored": True, "state": {"mode": "unavailable"}},
            error="verification request failed",
        )


def recovery_service(status: RecoveryExecutionStatus) -> RecoveryService:
    return RecoveryService(
        FakeIncidentRepository(),
        FakeRcaRepository(),
        FakeRecoveryRepository(),
        FakeExecutor(status),
    )


def failing_recovery_service() -> RecoveryService:
    return RecoveryService(
        FakeIncidentRepository(),
        FakeRcaRepository(),
        FakeRecoveryRepository(),
        FailingAfterActionExecutor(),
    )


def test_recovery_requires_separate_requester_and_approver() -> None:
    service = recovery_service(RecoveryExecutionStatus.SUCCEEDED)
    approval = service.request_recovery(
        "incident-1",
        RecoveryRequest(
            run_id="run-1",
            action="reset_inventory_fault",
            reason="RCA identified an active inventory fault",
        ),
        "alice",
    )

    with pytest.raises(RecoveryPermissionError):
        service.approve(approval.id, "alice", "approved by same user")


def test_approved_recovery_executes_once_and_is_idempotent() -> None:
    service = recovery_service(RecoveryExecutionStatus.SUCCEEDED)
    approval = service.request_recovery(
        "incident-1",
        RecoveryRequest(
            run_id="run-1",
            action="reset_inventory_fault",
            reason="RCA identified an active inventory fault",
        ),
        "alice",
    )
    service.approve(approval.id, "bob", "safe to recover in sandbox")

    first = service.execute(approval.id, "carol")
    repeated = service.execute(approval.id, "carol")

    assert first.id == repeated.id
    assert first.status == RecoveryExecutionStatus.SUCCEEDED
    assert first.sandbox is True
    assert first.before_state["mode"] == "unavailable"


def test_failed_verification_records_rollback() -> None:
    service = recovery_service(RecoveryExecutionStatus.ROLLED_BACK)
    approval = service.request_recovery(
        "incident-1",
        RecoveryRequest(
            run_id="run-1",
            action="reset_inventory_fault",
            reason="RCA identified an active inventory fault",
        ),
        "alice",
    )
    service.approve(approval.id, "bob", "safe to try")

    execution = service.execute(approval.id, "carol")

    assert execution.status == RecoveryExecutionStatus.ROLLED_BACK
    assert execution.rollback == {"restored": True}
    assert execution.verification == {"passed": False}


def test_action_failure_after_mutation_records_rollback_attempt() -> None:
    service = failing_recovery_service()
    approval = service.request_recovery(
        "incident-1",
        RecoveryRequest(
            run_id="run-1",
            action="reset_inventory_fault",
            reason="RCA identified an active inventory fault",
        ),
        "alice",
    )
    service.approve(approval.id, "bob", "safe to try")

    execution = service.execute(approval.id, "carol")

    assert execution.status == RecoveryExecutionStatus.FAILED
    assert execution.rollback == {"restored": True, "state": {"mode": "unavailable"}}
    assert execution.error == "verification request failed"


def test_recovery_routes_enforce_roles() -> None:
    client = TestClient(
        create_control_plane_app(
            repository=IncidentRepository.__new__(IncidentRepository),
            database=object(),
            recovery_service=recovery_service(RecoveryExecutionStatus.SUCCEEDED),
        )
    )

    response = client.post(
        "/incidents/incident-1/recovery-approvals",
        headers={"X-AxiomOps-User": "alice", "X-AxiomOps-Role": "operator"},
        json={
            "run_id": "run-1",
            "action": "reset_inventory_fault",
            "reason": "RCA identified an active inventory fault",
        },
    )

    assert response.status_code == 403
