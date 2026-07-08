import json
from datetime import datetime
from typing import Any

from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.models import EvidenceView, StoredArtifact


class EvidenceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def incident_exists(self, incident_id: str) -> bool:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM incidents WHERE id=%s", (incident_id,))
                return cursor.fetchone() is not None
        finally:
            connection.close()

    def create(
        self,
        evidence_id: str,
        incident_id: str,
        kind: str,
        tool_name: str,
        tool_input: dict[str, Any],
        source: str,
        observed_at: datetime,
        artifact: StoredArtifact,
    ) -> EvidenceView:
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO evidence
                        (id, incident_id, kind, tool_name, tool_input, source,
                         artifact_path, content_sha256, byte_size, observed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        evidence_id,
                        incident_id,
                        kind,
                        tool_name,
                        json.dumps(tool_input, ensure_ascii=False),
                        source,
                        artifact.relative_path,
                        artifact.content_sha256,
                        artifact.byte_size,
                        observed_at,
                    ),
                )
        evidence = self.get(evidence_id)
        assert evidence is not None
        return evidence

    def get(self, evidence_id: str) -> EvidenceView | None:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM evidence WHERE id=%s", (evidence_id,))
                row = cursor.fetchone()
            if row is None:
                return None
            row["tool_input"] = json.loads(row["tool_input"])
            return EvidenceView.model_validate(row)
        finally:
            connection.close()

    def list_for_incident(self, incident_id: str) -> list[EvidenceView]:
        connection = self.database.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM evidence WHERE incident_id=%s ORDER BY created_at, id",
                    (incident_id,),
                )
                rows = cursor.fetchall()
            for row in rows:
                row["tool_input"] = json.loads(row["tool_input"])
            return [EvidenceView.model_validate(row) for row in rows]
        finally:
            connection.close()
