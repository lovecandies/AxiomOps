import json
from typing import Any
from uuid import uuid4

from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.models import (
    RecoveryAction,
    RecoveryApprovalView,
    RecoveryExecutionStatus,
    RecoveryExecutionView,
)


class RecoveryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_approval(
        self,
        incident_id: str,
        run_id: str,
        action: RecoveryAction,
        reason: str,
        requested_by: str,
    ) -> RecoveryApprovalView:
        approval_id = str(uuid4())
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO recovery_approvals
                        (id, incident_id, run_id, action, status, reason, requested_by)
                    VALUES (%s, %s, %s, %s, 'PENDING', %s, %s)
                    """,
                    (
                        approval_id,
                        incident_id,
                        run_id,
                        action.value,
                        reason,
                        requested_by,
                    ),
                )
        approval = self.get_approval(approval_id)
        assert approval is not None
        return approval

    def approve(
        self,
        approval_id: str,
        approved_by: str,
        approval_comment: str,
    ) -> RecoveryApprovalView:
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE recovery_approvals
                    SET status='APPROVED', approved_by=%s, approval_comment=%s,
                        approved_at=UTC_TIMESTAMP(6)
                    WHERE id=%s AND status='PENDING'
                    """,
                    (approved_by, approval_comment, approval_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"recovery approval is not pending: {approval_id}")
        approval = self.get_approval(approval_id)
        assert approval is not None
        return approval

    def create_execution(
        self,
        approval_id: str,
        action: RecoveryAction,
        status: RecoveryExecutionStatus,
        executed_by: str,
        sandbox: bool,
        before_state: dict[str, Any],
        action_result: dict[str, Any],
        verification: dict[str, Any],
        rollback: dict[str, Any] | None,
        error: str | None,
    ) -> RecoveryExecutionView:
        execution_id = str(uuid4())
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO recovery_executions
                        (id, approval_id, action, status, executed_by, sandbox,
                         before_state, action_result, verification, rollback, error)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        execution_id,
                        approval_id,
                        action.value,
                        status.value,
                        executed_by,
                        sandbox,
                        json.dumps(before_state, ensure_ascii=False),
                        json.dumps(action_result, ensure_ascii=False),
                        json.dumps(verification, ensure_ascii=False),
                        json.dumps(rollback, ensure_ascii=False)
                        if rollback is not None
                        else None,
                        error[:4000] if error else None,
                    ),
                )
        execution = self.get_execution(execution_id)
        assert execution is not None
        return execution

    @staticmethod
    def _load_json(value: str | dict | list | None) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    def get_approval(self, approval_id: str) -> RecoveryApprovalView | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM recovery_approvals WHERE id=%s",
                    (approval_id,),
                )
                approval = cursor.fetchone()
            return RecoveryApprovalView.model_validate(approval) if approval else None
        finally:
            connection.close()

    def get_execution_for_approval(
        self,
        approval_id: str,
    ) -> RecoveryExecutionView | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM recovery_executions
                    WHERE approval_id=%s ORDER BY started_at DESC LIMIT 1
                    """,
                    (approval_id,),
                )
                execution = cursor.fetchone()
            return self._to_execution(execution)
        finally:
            connection.close()

    def get_execution(self, execution_id: str) -> RecoveryExecutionView | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM recovery_executions WHERE id=%s",
                    (execution_id,),
                )
                execution = cursor.fetchone()
            return self._to_execution(execution)
        finally:
            connection.close()

    def _to_execution(self, execution: dict[str, Any] | None) -> RecoveryExecutionView | None:
        if execution is None:
            return None
        for key in ("before_state", "action_result", "verification", "rollback"):
            execution[key] = self._load_json(execution[key])
        return RecoveryExecutionView.model_validate(execution)
