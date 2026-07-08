from fastapi.testclient import TestClient

from axiom_ops.app import create_app
from axiom_ops.config import Settings


def test_health_reports_phase_zero() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "axiom-ops",
        "version": "0.1.0",
        "phase": "phase-0",
    }


def test_readiness_has_no_external_dependencies_in_phase_zero() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "environment": "test",
        "dependencies": {},
    }
