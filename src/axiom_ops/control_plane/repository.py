from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pymysql.err import IntegrityError

from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.models import (
    ClaimedOutboxEvent,
    IncidentCreate,
    IncidentView,
)


INVESTIGATION_REQUESTED = "incident.investigation.requested"


class IdempotencyConflict(Exception):
    pass


class IncidentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _fingerprint(request: IncidentCreate) -> str:
        canonical = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def create_incident(
        self,
        idempotency_key: str,
        request: IncidentCreate,
    ) -> tuple[IncidentView, bool]:
        fingerprint = self._fingerprint(request)
        incident_id = str(uuid4())
        event_id = str(uuid4())
        payload = {
            "event_id": event_id,
            "event_type": INVESTIGATION_REQUESTED,
            "incident_id": incident_id,
            "incident": request.model_dump(mode="json"),
        }
        try:
            with self.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO incidents
                            (id, idempotency_key, request_fingerprint, title,
                             service, severity, summary, status, version)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'RECEIVED', 1)
                        """,
                        (
                            incident_id,
                            idempotency_key,
                            fingerprint,
                            request.title,
                            request.service,
                            request.severity.value,
                            request.summary,
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT INTO incident_events
                            (incident_id, event_type, from_status, to_status, metadata)
                        VALUES (%s, 'incident.received', NULL, 'RECEIVED', %s)
                        """,
                        (incident_id, json.dumps({"idempotency_key": idempotency_key})),
                    )
                    cursor.execute(
                        """
                        INSERT INTO outbox_events
                            (id, aggregate_type, aggregate_id, event_type, payload,
                             status, available_at)
                        VALUES (%s, 'Incident', %s, %s, %s, 'PENDING', UTC_TIMESTAMP(6))
                        """,
                        (
                            event_id,
                            incident_id,
                            INVESTIGATION_REQUESTED,
                            json.dumps(payload, ensure_ascii=False),
                        ),
                    )
        except IntegrityError as exc:
            existing = self.get_incident_by_idempotency_key(idempotency_key)
            if existing is None:
                raise
            if self._stored_fingerprint(idempotency_key) != fingerprint:
                raise IdempotencyConflict(idempotency_key) from exc
            return existing, False
        view = self.get_incident(incident_id)
        assert view is not None
        return view, True

    def _stored_fingerprint(self, idempotency_key: str) -> str | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT request_fingerprint FROM incidents WHERE idempotency_key=%s",
                    (idempotency_key,),
                )
                row = cursor.fetchone()
                return row["request_fingerprint"] if row else None
        finally:
            connection.close()

    def get_incident_by_idempotency_key(self, key: str) -> IncidentView | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM incidents WHERE idempotency_key=%s", (key,))
                row = cursor.fetchone()
            return self.get_incident(row["id"]) if row else None
        finally:
            connection.close()

    def get_incident(self, incident_id: str) -> IncidentView | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM incidents WHERE id=%s", (incident_id,))
                incident = cursor.fetchone()
                if incident is None:
                    return None
                cursor.execute(
                    """
                    SELECT event_type, from_status, to_status, created_at
                    FROM incident_events WHERE incident_id=%s ORDER BY id
                    """,
                    (incident_id,),
                )
                events = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT id AS event_id, event_type, status, attempts, broker_message_id
                    FROM outbox_events WHERE aggregate_id=%s ORDER BY created_at
                    """,
                    (incident_id,),
                )
                outbox = cursor.fetchall()
            return IncidentView.model_validate(
                {**incident, "events": events, "outbox": outbox}
            )
        finally:
            connection.close()

    def list_incidents(self, limit: int = 50) -> list[IncidentView]:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM incidents ORDER BY created_at DESC LIMIT %s", (limit,)
                )
                incident_ids = [row["id"] for row in cursor.fetchall()]
            return [
                incident
                for incident_id in incident_ids
                if (incident := self.get_incident(incident_id)) is not None
            ]
        finally:
            connection.close()

    def claim_outbox(
        self,
        worker_id: str,
        lease_seconds: int,
        limit: int = 10,
    ) -> list[ClaimedOutboxEvent]:
        lease_expired_before = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            seconds=lease_seconds
        )
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, aggregate_id, event_type, payload
                    FROM outbox_events
                    WHERE available_at <= UTC_TIMESTAMP(6)
                      AND (status='PENDING' OR (status='SENDING' AND locked_at < %s))
                    ORDER BY created_at
                    LIMIT %s FOR UPDATE SKIP LOCKED
                    """,
                    (lease_expired_before, limit),
                )
                rows = cursor.fetchall()
                if rows:
                    ids = [row["id"] for row in rows]
                    placeholders = ",".join(["%s"] * len(ids))
                    cursor.execute(
                        f"""
                        UPDATE outbox_events
                        SET status='SENDING', locked_by=%s, locked_at=UTC_TIMESTAMP(6),
                            attempts=attempts+1
                        WHERE id IN ({placeholders})
                        """,
                        (worker_id, *ids),
                    )
        return [
            ClaimedOutboxEvent(
                id=row["id"],
                aggregate_id=row["aggregate_id"],
                event_type=row["event_type"],
                payload=json.loads(row["payload"]),
            )
            for row in rows
        ]

    def mark_published(
        self,
        event_id: str,
        worker_id: str,
        broker_message_id: str,
    ) -> None:
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE outbox_events
                    SET status='PUBLISHED', broker_message_id=%s,
                        published_at=UTC_TIMESTAMP(6), locked_by=NULL, locked_at=NULL,
                        last_error=NULL
                    WHERE id=%s AND status='SENDING' AND locked_by=%s
                    """,
                    (broker_message_id, event_id, worker_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"outbox lease lost: {event_id}")

    def mark_failed(
        self,
        event_id: str,
        worker_id: str,
        error: str,
        retry_seconds: int,
    ) -> None:
        available_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            seconds=retry_seconds
        )
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE outbox_events
                    SET status='PENDING', available_at=%s, locked_by=NULL, locked_at=NULL,
                        last_error=%s
                    WHERE id=%s AND status='SENDING' AND locked_by=%s
                    """,
                    (available_at, error[:2000], event_id, worker_id),
                )

    def consume_investigation_requested(
        self,
        consumer_group: str,
        event_id: str,
        incident_id: str,
        broker_message_id: str,
    ) -> bool:
        try:
            with self.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO processed_messages
                            (consumer_group, event_id, broker_message_id)
                        VALUES (%s, %s, %s)
                        """,
                        (consumer_group, event_id, broker_message_id),
                    )
                    cursor.execute(
                        "SELECT status FROM incidents WHERE id=%s FOR UPDATE",
                        (incident_id,),
                    )
                    incident = cursor.fetchone()
                    if incident is None:
                        raise RuntimeError(f"incident not found: {incident_id}")
                    if incident["status"] == "RECEIVED":
                        cursor.execute(
                            """
                            UPDATE incidents
                            SET status='INVESTIGATION_QUEUED', version=version+1
                            WHERE id=%s AND status='RECEIVED'
                            """,
                            (incident_id,),
                        )
                        cursor.execute(
                            """
                            INSERT INTO incident_events
                                (incident_id, event_type, from_status, to_status, metadata)
                            VALUES (%s, 'incident.investigation.queued', 'RECEIVED',
                                    'INVESTIGATION_QUEUED', %s)
                            """,
                            (incident_id, json.dumps({"event_id": event_id})),
                        )
            return True
        except IntegrityError:
            return False
