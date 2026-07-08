from datetime import UTC, datetime

from fastapi.testclient import TestClient

from axiom_ops.control_plane.app import create_control_plane_app
from axiom_ops.control_plane.models import IncidentCreate, IncidentView
from axiom_ops.control_plane.repository import IdempotencyConflict


class ReadyDatabase:
    def verify_schema(self) -> None:
        return None


class MemoryRepository:
    def __init__(self) -> None:
        self.incidents: dict[str, IncidentView] = {}
        self.requests: dict[str, IncidentCreate] = {}

    def create_incident(
        self,
        idempotency_key: str,
        request: IncidentCreate,
    ) -> tuple[IncidentView, bool]:
        if idempotency_key in self.incidents:
            if self.requests[idempotency_key] != request:
                raise IdempotencyConflict(idempotency_key)
            return self.incidents[idempotency_key], False
        now = datetime.now(UTC)
        incident = IncidentView.model_validate(
            {
                "id": f"incident-{len(self.incidents) + 1}",
                "idempotency_key": idempotency_key,
                **request.model_dump(),
                "status": "RECEIVED",
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "events": [
                    {
                        "event_type": "incident.received",
                        "from_status": None,
                        "to_status": "RECEIVED",
                        "created_at": now,
                    }
                ],
                "outbox": [
                    {
                        "event_id": "event-1",
                        "event_type": "incident.investigation.requested",
                        "status": "PENDING",
                        "attempts": 0,
                        "broker_message_id": None,
                    }
                ],
            }
        )
        self.requests[idempotency_key] = request
        self.incidents[idempotency_key] = incident
        return incident, True

    def get_incident(self, incident_id: str) -> IncidentView | None:
        return next(
            (item for item in self.incidents.values() if item.id == incident_id),
            None,
        )


def payload(summary: str = "latency threshold exceeded") -> dict[str, str]:
    return {
        "title": "Inventory latency",
        "service": "inventory-service",
        "severity": "SEV2",
        "summary": summary,
    }


def test_create_incident_is_idempotent() -> None:
    client = TestClient(
        create_control_plane_app(MemoryRepository(), ReadyDatabase())
    )
    headers = {"Idempotency-Key": "alert-20260708-001"}

    created = client.post("/incidents", headers=headers, json=payload())
    repeated = client.post("/incidents", headers=headers, json=payload())

    assert created.status_code == 201
    assert repeated.status_code == 200
    assert repeated.json()["id"] == created.json()["id"]
    assert len(repeated.json()["outbox"]) == 1


def test_reusing_key_for_another_request_returns_conflict() -> None:
    client = TestClient(
        create_control_plane_app(MemoryRepository(), ReadyDatabase())
    )
    headers = {"Idempotency-Key": "alert-20260708-002"}

    client.post("/incidents", headers=headers, json=payload())
    conflict = client.post(
        "/incidents",
        headers=headers,
        json=payload("another payload"),
    )

    assert conflict.status_code == 409


def test_incident_can_be_read_and_missing_incident_is_404() -> None:
    client = TestClient(
        create_control_plane_app(MemoryRepository(), ReadyDatabase())
    )
    created = client.post(
        "/incidents",
        headers={"Idempotency-Key": "alert-20260708-003"},
        json=payload(),
    )

    found = client.get(f"/incidents/{created.json()['id']}")
    missing = client.get("/incidents/missing")

    assert found.status_code == 200
    assert found.json()["status"] == "RECEIVED"
    assert missing.status_code == 404


def test_typed_tool_rejects_values_outside_allowlist() -> None:
    client = TestClient(
        create_control_plane_app(MemoryRepository(), ReadyDatabase())
    )

    invalid_metric = client.post(
        "/incidents/missing/tools/metrics",
        json={"signal": "arbitrary_promql"},
    )
    invalid_service = client.post(
        "/incidents/missing/tools/health",
        json={"service": "unknown-service"},
    )

    assert invalid_metric.status_code == 422
    assert invalid_service.status_code == 422
