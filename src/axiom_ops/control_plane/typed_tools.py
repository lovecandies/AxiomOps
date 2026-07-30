from datetime import UTC, datetime
from time import perf_counter

import httpx

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.models import (
    ChangeEventToolInput,
    EvidenceKind,
    FaultStateToolInput,
    HealthToolInput,
    LabService,
    MetricSignal,
    MetricsToolInput,
    OrderFlowProbeInput,
    TraceSnapshotToolInput,
    ToolObservation,
)


METRIC_QUERIES = {
    MetricSignal.ORDER_DURATION_TOTAL: (
        'sum(axiomops_lab_http_request_duration_seconds_sum{service="order-service"})'
    ),
    MetricSignal.ORDER_DOWNSTREAM_FAILURES: (
        'sum(axiomops_lab_downstream_requests_total{service="order-service",status!="success"})'
    ),
    MetricSignal.INVENTORY_ACTIVE_FAULT: (
        'axiomops_lab_fault_mode{service="inventory-service"} == 1'
    ),
}


class ToolExecutionError(Exception):
    pass


class MetricsSnapshotTool:
    name = "prometheus.metrics.snapshot"
    kind = EvidenceKind.METRIC_SNAPSHOT

    def __init__(self, settings: ControlPlaneSettings) -> None:
        self.prometheus_url = settings.prometheus_url.rstrip("/")

    def execute(self, tool_input: MetricsToolInput) -> ToolObservation:
        query = METRIC_QUERIES[tool_input.signal]
        started = perf_counter()
        observed_at = datetime.now(UTC)
        try:
            response = httpx.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ToolExecutionError(f"Prometheus query failed: {exc}") from exc
        if data.get("status") != "success":
            raise ToolExecutionError("Prometheus returned a non-success response")
        return ToolObservation(
            tool_name=self.name,
            kind=self.kind,
            input=tool_input.model_dump(mode="json"),
            source=self.prometheus_url,
            observed_at=observed_at,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            data={"query": query, "response": data},
        )


class ServiceHealthTool:
    name = "http.service.health"
    kind = EvidenceKind.SERVICE_HEALTH

    def __init__(self, settings: ControlPlaneSettings) -> None:
        self.urls = {
            LabService.ORDER: settings.order_service_url.rstrip("/"),
            LabService.INVENTORY: settings.inventory_service_url.rstrip("/"),
        }

    def execute(self, tool_input: HealthToolInput) -> ToolObservation:
        source = self.urls[tool_input.service]
        started = perf_counter()
        observed_at = datetime.now(UTC)
        try:
            response = httpx.get(f"{source}/health", timeout=5)
            body: object
            try:
                body = response.json()
            except ValueError:
                body = response.text
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ToolExecutionError(f"health probe failed: {exc}") from exc
        return ToolObservation(
            tool_name=self.name,
            kind=self.kind,
            input=tool_input.model_dump(mode="json"),
            source=source,
            observed_at=observed_at,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            data={"status_code": response.status_code, "body": body},
        )


class InventoryFaultStateTool:
    name = "http.inventory.fault_state"
    kind = EvidenceKind.FAULT_STATE

    def __init__(self, settings: ControlPlaneSettings) -> None:
        self.source = settings.inventory_service_url.rstrip("/")

    def execute(self, tool_input: FaultStateToolInput) -> ToolObservation:
        started = perf_counter()
        observed_at = datetime.now(UTC)
        try:
            response = httpx.get(f"{self.source}/admin/faults", timeout=5)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ToolExecutionError(f"fault-state probe failed: {exc}") from exc
        return ToolObservation(tool_name=self.name, kind=self.kind, input=tool_input.model_dump(mode="json"), source=self.source, observed_at=observed_at, duration_ms=round((perf_counter() - started) * 1000, 2), data={"status_code": response.status_code, "body": body})


class OrderFlowProbeTool:
    name = "http.order.flow_probe"
    kind = EvidenceKind.ORDER_FLOW_PROBE

    def __init__(self, settings: ControlPlaneSettings) -> None:
        self.source = settings.order_service_url.rstrip("/")

    def execute(self, tool_input: OrderFlowProbeInput) -> ToolObservation:
        started = perf_counter()
        observed_at = datetime.now(UTC)
        try:
            response = httpx.get(f"{self.source}/orders/axiomops-rca-probe", timeout=5)
            try:
                body: object = response.json()
            except ValueError:
                body = response.text
        except httpx.HTTPError as exc:
            raise ToolExecutionError(f"order-flow probe failed: {exc}") from exc
        return ToolObservation(tool_name=self.name, kind=self.kind, input=tool_input.model_dump(mode="json"), source=self.source, observed_at=observed_at, duration_ms=round((perf_counter() - started) * 1000, 2), data={"status_code": response.status_code, "body": body})


class TraceSnapshotTool:
    name = "http.trace.snapshot"
    kind = EvidenceKind.TRACE_SNAPSHOT

    def __init__(self, settings: ControlPlaneSettings) -> None:
        self.urls = {
            LabService.ORDER: settings.order_service_url.rstrip("/"),
            LabService.INVENTORY: settings.inventory_service_url.rstrip("/"),
        }

    def execute(self, tool_input: TraceSnapshotToolInput) -> ToolObservation:
        source = self.urls[tool_input.service]
        started = perf_counter()
        observed_at = datetime.now(UTC)
        try:
            response = httpx.get(f"{source}/admin/traces", timeout=5)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ToolExecutionError(f"trace snapshot failed: {exc}") from exc
        return ToolObservation(
            tool_name=self.name,
            kind=self.kind,
            input=tool_input.model_dump(mode="json"),
            source=source,
            observed_at=observed_at,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            data={"status_code": response.status_code, "body": body},
        )


class ChangeEventTool:
    name = "http.change.events"
    kind = EvidenceKind.CHANGE_EVENT

    def __init__(self, settings: ControlPlaneSettings) -> None:
        self.urls = {
            LabService.ORDER: settings.order_service_url.rstrip("/"),
            LabService.INVENTORY: settings.inventory_service_url.rstrip("/"),
        }

    def execute(self, tool_input: ChangeEventToolInput) -> ToolObservation:
        source = self.urls[tool_input.service]
        started = perf_counter()
        observed_at = datetime.now(UTC)
        try:
            response = httpx.get(f"{source}/admin/changes", timeout=5)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ToolExecutionError(f"change event snapshot failed: {exc}") from exc
        return ToolObservation(
            tool_name=self.name,
            kind=self.kind,
            input=tool_input.model_dump(mode="json"),
            source=source,
            observed_at=observed_at,
            duration_ms=round((perf_counter() - started) * 1000, 2),
            data={"status_code": response.status_code, "body": body},
        )
