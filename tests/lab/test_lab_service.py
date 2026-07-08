import httpx
from fastapi.testclient import TestClient

from axiom_ops.lab.app import create_lab_app
from axiom_ops.lab.config import LabSettings


def test_inventory_fault_can_be_injected_and_reset() -> None:
    client = TestClient(
        create_lab_app(
            LabSettings(service_name="inventory-service", role="inventory")
        )
    )

    injected = client.post(
        "/admin/faults",
        json={"mode": "error_rate", "delay_ms": 0, "error_rate": 1.0},
    )
    failed = client.get("/inventory/demo")
    reset = client.post("/admin/faults/reset")
    recovered = client.get("/inventory/demo")

    assert injected.status_code == 200
    assert failed.status_code == 500
    assert reset.json()["mode"] == "none"
    assert recovered.status_code == 200


def test_inventory_unavailable_fault_is_observable() -> None:
    client = TestClient(
        create_lab_app(
            LabSettings(service_name="inventory-service", role="inventory")
        )
    )

    client.post(
        "/admin/faults",
        json={"mode": "unavailable", "delay_ms": 0, "error_rate": 0.0},
    )

    assert client.get("/inventory/demo").status_code == 503
    metrics = client.get("/metrics").text
    assert 'axiomops_lab_fault_mode{mode="unavailable",service="inventory-service"} 1.0' in metrics


def test_order_service_calls_inventory() -> None:
    def inventory_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/inventory/demo"
        return httpx.Response(
            200,
            json={"sku": "demo", "available": 42, "service": "inventory-service"},
        )

    client = TestClient(
        create_lab_app(
            LabSettings(
                service_name="order-service",
                role="order",
                inventory_url="http://inventory",
            ),
            inventory_transport=httpx.MockTransport(inventory_handler),
        )
    )

    response = client.get("/orders/demo")

    assert response.status_code == 200
    assert response.json()["inventory"]["available"] == 42


def test_order_service_maps_downstream_error_to_503() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(503))
    client = TestClient(
        create_lab_app(
            LabSettings(
                service_name="order-service",
                role="order",
                inventory_url="http://inventory",
            ),
            inventory_transport=transport,
        )
    )

    response = client.get("/orders/demo")

    assert response.status_code == 503
    assert response.json()["detail"] == "inventory returned 503"
