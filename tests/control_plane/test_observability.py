from datetime import UTC, datetime

from fastapi.testclient import TestClient

from axiom_ops.control_plane.app import create_control_plane_app
from axiom_ops.control_plane.models import IncidentCreate, IncidentView


class ReadyDatabase:
    def verify_schema(self) -> None:
        return None


class MemoryRepository:
    def __init__(self) -> None:
        self.incident: IncidentView | None = None

    def create_incident(
        self,
        idempotency_key: str,
        request: IncidentCreate,
    ) -> tuple[IncidentView, bool]:
        now = datetime.now(UTC)
        self.incident = IncidentView.model_validate(
            {
                "id": "incident-observability",
                "idempotency_key": idempotency_key,
                **request.model_dump(),
                "status": "RECEIVED",
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "events": [],
                "outbox": [],
            }
        )
        return self.incident, True

    def get_incident(self, incident_id: str) -> IncidentView | None:
        return self.incident if self.incident and self.incident.id == incident_id else None


def client() -> TestClient:
    return TestClient(create_control_plane_app(MemoryRepository(), ReadyDatabase()))


def test_trace_id_is_returned_and_traceparent_is_respected() -> None:
    trace_id = "1234567890abcdef1234567890abcdef"
    response = client().get(
        "/health",
        headers={"traceparent": f"00-{trace_id}-1234567890abcdef-01"},
    )

    assert response.status_code == 200
    assert response.headers["X-AxiomOps-Trace-Id"] == trace_id
    assert response.headers["traceparent"].startswith(f"00-{trace_id}-")


def test_control_plane_metrics_include_http_and_business_events() -> None:
    test_client = client()
    created = test_client.post(
        "/incidents",
        headers={"Idempotency-Key": "observability-001"},
        json={
            "title": "Inventory latency",
            "service": "inventory-service",
            "severity": "SEV2",
            "summary": "measure control-plane observability",
        },
    )
    assert created.status_code == 201

    metrics = test_client.get("/metrics")

    assert metrics.status_code == 200
    assert "axiomops_control_http_requests_total" in metrics.text
    assert 'path="/incidents"' in metrics.text
    assert "axiomops_control_business_events_total" in metrics.text
    assert 'event_type="incident.create",result="created"' in metrics.text
