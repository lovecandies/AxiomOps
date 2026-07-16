from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest


TRACEPARENT_VERSION_LENGTH = 2
TRACE_ID_LENGTH = 32


class ControlPlaneObservability:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.http_requests = Counter(
            "axiomops_control_http_requests_total",
            "HTTP requests handled by the AxiomOps control plane.",
            ("method", "path", "status"),
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "axiomops_control_http_request_duration_seconds",
            "HTTP request duration in the AxiomOps control plane.",
            ("method", "path"),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry,
        )
        self.business_events = Counter(
            "axiomops_control_business_events_total",
            "Business events emitted by the AxiomOps control plane.",
            ("event_type", "result"),
            registry=self.registry,
        )

    def observe_response(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        self.http_requests.labels(
            method=method,
            path=path,
            status=str(status_code),
        ).inc()
        self.http_duration.labels(method=method, path=path).observe(duration_seconds)

    def record_event(self, event_type: str, result: str) -> None:
        self.business_events.labels(event_type=event_type, result=result).inc()

    def render(self) -> bytes:
        return generate_latest(self.registry)


def trace_id_from_request(request: Request) -> str:
    incoming = request.headers.get("traceparent")
    if incoming:
        parts = incoming.split("-")
        if (
            len(parts) == 4
            and len(parts[0]) == TRACEPARENT_VERSION_LENGTH
            and len(parts[1]) == TRACE_ID_LENGTH
            and parts[1] != "0" * TRACE_ID_LENGTH
        ):
            return parts[1]
    existing = request.headers.get("X-AxiomOps-Trace-Id")
    if existing and len(existing) <= 64:
        return existing
    return uuid4().hex


def traceparent(trace_id: str) -> str:
    span_id = uuid4().hex[:16]
    return f"00-{trace_id[:TRACE_ID_LENGTH]}-{span_id}-01"


async def observability_middleware(
    request: Request,
    call_next,
    observability: ControlPlaneObservability,
) -> Response:
    started = perf_counter()
    trace_id = trace_id_from_request(request)
    request.state.trace_id = trace_id
    status_code = 500
    response: Response | None = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        if path != "/metrics":
            observability.observe_response(
                request.method,
                path,
                status_code,
                perf_counter() - started,
            )
        if response is not None:
            response.headers["X-AxiomOps-Trace-Id"] = trace_id
            response.headers["traceparent"] = traceparent(trace_id)
