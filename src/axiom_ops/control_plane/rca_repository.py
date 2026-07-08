import json
from typing import Any
from uuid import uuid4

from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.models import (
    RcaDraft,
    RcaReportView,
    RcaRunStatus,
    RcaRunView,
    VerificationDecision,
    VerificationResult,
)


class RcaRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_run(
        self,
        run_id: str,
        incident_id: str,
        model: str,
        graph_version: str,
        evidence_ids: list[str],
    ) -> None:
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO agent_runs
                        (id, incident_id, status, model, graph_version, evidence_ids)
                    VALUES (%s, %s, 'RUNNING', %s, %s, %s)
                    """,
                    (
                        run_id,
                        incident_id,
                        model,
                        graph_version,
                        json.dumps(evidence_ids),
                    ),
                )

    def finish_run(
        self,
        run_id: str,
        incident_id: str,
        draft: RcaDraft,
        verification: VerificationResult,
        steps: list[dict[str, Any]],
        model_calls: int,
        total_tokens: int,
        duration_ms: int,
    ) -> None:
        status = (
            RcaRunStatus.COMPLETED
            if verification.decision == VerificationDecision.APPROVED
            else RcaRunStatus.REJECTED
        )
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                for item in steps:
                    cursor.execute(
                        """
                        INSERT INTO agent_run_steps (run_id, node_name, role, output)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            run_id,
                            item["node_name"],
                            item.get("role"),
                            json.dumps(item["output"], ensure_ascii=False),
                        ),
                    )
                cursor.execute(
                    """
                    UPDATE agent_runs
                    SET status=%s, verification=%s, model_calls=%s, total_tokens=%s,
                        duration_ms=%s, completed_at=UTC_TIMESTAMP(6)
                    WHERE id=%s AND status='RUNNING'
                    """,
                    (
                        status.value,
                        json.dumps(verification.model_dump(mode="json"), ensure_ascii=False),
                        model_calls,
                        total_tokens,
                        duration_ms,
                        run_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"RCA run is not RUNNING: {run_id}")
                if status == RcaRunStatus.COMPLETED:
                    cursor.execute(
                        """
                        INSERT INTO rca_reports
                            (id, run_id, incident_id, summary, root_cause, confidence,
                             contributing_factors, rejected_hypotheses, evidence_ids,
                             limitations, verification)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid4()),
                            run_id,
                            incident_id,
                            draft.summary,
                            draft.root_cause,
                            draft.confidence,
                            json.dumps(draft.contributing_factors, ensure_ascii=False),
                            json.dumps(draft.rejected_hypotheses, ensure_ascii=False),
                            json.dumps(draft.evidence_ids),
                            json.dumps(draft.limitations, ensure_ascii=False),
                            json.dumps(
                                verification.model_dump(mode="json"),
                                ensure_ascii=False,
                            ),
                        ),
                    )

    def fail_run(
        self,
        run_id: str,
        error: str,
        model_calls: int,
        total_tokens: int,
        duration_ms: int,
    ) -> None:
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE agent_runs
                    SET status='FAILED', error=%s, model_calls=%s, total_tokens=%s,
                        duration_ms=%s, completed_at=UTC_TIMESTAMP(6)
                    WHERE id=%s AND status='RUNNING'
                    """,
                    (error[:4000], model_calls, total_tokens, duration_ms, run_id),
                )

    @staticmethod
    def _load_json(value: str | dict | list | None) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    def get_run(self, run_id: str) -> RcaRunView | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM agent_runs WHERE id=%s", (run_id,))
                run = cursor.fetchone()
                if run is None:
                    return None
                cursor.execute(
                    """
                    SELECT node_name, role, output, created_at
                    FROM agent_run_steps WHERE run_id=%s ORDER BY id
                    """,
                    (run_id,),
                )
                steps = cursor.fetchall()
            run["evidence_ids"] = self._load_json(run["evidence_ids"])
            run["verification"] = self._load_json(run["verification"])
            for item in steps:
                item["output"] = self._load_json(item["output"])
            run["steps"] = steps
            return RcaRunView.model_validate(run)
        finally:
            connection.close()

    def get_latest_report(self, incident_id: str) -> RcaReportView | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM rca_reports
                    WHERE incident_id=%s ORDER BY created_at DESC LIMIT 1
                    """,
                    (incident_id,),
                )
                report = cursor.fetchone()
            if report is None:
                return None
            for key in (
                "contributing_factors",
                "rejected_hypotheses",
                "evidence_ids",
                "limitations",
                "verification",
            ):
                report[key] = self._load_json(report[key])
            return RcaReportView.model_validate(report)
        finally:
            connection.close()
