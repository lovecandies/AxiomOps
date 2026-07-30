import httpx

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.models import (
    ChangeEventToolInput,
    HealthToolInput,
    MetricsToolInput,
    TraceSnapshotToolInput,
)
from axiom_ops.control_plane.typed_tools import (
    ChangeEventTool,
    METRIC_QUERIES,
    MetricsSnapshotTool,
    ServiceHealthTool,
    TraceSnapshotTool,
)
from axiom_ops.control_plane.models import MetricSignal


def test_metrics_tool_uses_allowlisted_query(monkeypatch) -> None:
    captured: dict = {}

    def fake_get(url: str, **kwargs) -> httpx.Response:
        captured.update({"url": url, **kwargs})
        return httpx.Response(
            200,
            json={"status": "success", "data": {"result": []}},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    tool = MetricsSnapshotTool(ControlPlaneSettings())

    observation = tool.execute(
        MetricsToolInput(signal="order_downstream_failures")
    )

    assert captured["params"]["query"] == observation.data["query"]
    assert 'status!="success"' in observation.data["query"]


def test_health_tool_uses_service_allowlist(monkeypatch) -> None:
    captured: dict = {}

    def fake_get(url: str, **kwargs) -> httpx.Response:
        captured.update({"url": url, **kwargs})
        return httpx.Response(
            200,
            json={"status": "ok"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    tool = ServiceHealthTool(ControlPlaneSettings())

    observation = tool.execute(HealthToolInput(service="inventory-service"))

    assert captured["url"].endswith("18002/health")
    assert observation.data["status_code"] == 200


def test_active_fault_query_preserves_fault_mode_label() -> None:
    query = METRIC_QUERIES[MetricSignal.INVENTORY_ACTIVE_FAULT]

    assert "== 1" in query
    assert not query.startswith("max(")


def test_trace_tool_reads_allowlisted_lab_endpoint(monkeypatch) -> None:
    captured: dict = {}

    def fake_get(url: str, **kwargs) -> httpx.Response:
        captured.update({"url": url, **kwargs})
        return httpx.Response(
            200,
            json={"service": "order-service", "spans": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    tool = TraceSnapshotTool(ControlPlaneSettings())

    observation = tool.execute(TraceSnapshotToolInput(service="order-service"))

    assert captured["url"].endswith("18001/admin/traces")
    assert observation.kind == "TRACE_SNAPSHOT"


def test_change_tool_reads_allowlisted_lab_endpoint(monkeypatch) -> None:
    captured: dict = {}

    def fake_get(url: str, **kwargs) -> httpx.Response:
        captured.update({"url": url, **kwargs})
        return httpx.Response(
            200,
            json={"service": "inventory-service", "changes": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    tool = ChangeEventTool(ControlPlaneSettings())

    observation = tool.execute(ChangeEventToolInput(service="inventory-service"))

    assert captured["url"].endswith("18002/admin/changes")
    assert observation.kind == "CHANGE_EVENT"
