import asyncio
from collections import deque
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from axiom_ops.lab.config import LabSettings
from axiom_ops.lab.faults import FaultConfig, FaultMode, FaultState
from axiom_ops.lab.metrics import LabMetrics


class FaultRequest(BaseModel):
    mode: FaultMode
    delay_ms: int = Field(default=0, ge=0, le=10_000)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)


def create_lab_app(
    settings: LabSettings | None = None,
    inventory_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    active_settings = settings or LabSettings()
    fault_state = FaultState()
    metrics = LabMetrics(active_settings.service_name)
    traces: deque[dict[str, Any]] = deque(maxlen=50)
    changes: deque[dict[str, Any]] = deque(maxlen=50)

    application = FastAPI(
        title=f"AxiomOps Lab - {active_settings.service_name}",
        version="0.1.0",
    )

    @application.middleware("http")
    async def observe_request(request: Request, call_next: Any) -> Response:
        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            metrics.http_requests.labels(
                service=active_settings.service_name,
                method=request.method,
                path=path,
                status=str(status),
            ).inc()
            metrics.http_duration.labels(
                service=active_settings.service_name,
                path=path,
            ).observe(perf_counter() - started)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": active_settings.service_name,
            "role": active_settings.role,
        }

    @application.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        return Response(
            content=generate_latest(metrics.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    @application.get("/admin/traces")
    async def get_traces() -> dict[str, Any]:
        return {
            "service": active_settings.service_name,
            "spans": list(traces),
            "count": len(traces),
        }

    @application.get("/admin/changes")
    async def get_changes() -> dict[str, Any]:
        return {
            "service": active_settings.service_name,
            "changes": list(changes),
            "count": len(changes),
        }

    if active_settings.role == "inventory":

        @application.get("/inventory/{sku}")
        async def inventory(sku: str) -> dict[str, str | int]:
            fault, should_fail = await fault_state.next_request()
            if fault.mode == "latency" and fault.delay_ms:
                await asyncio.sleep(fault.delay_ms / 1000)
            if fault.mode == "unavailable":
                raise HTTPException(status_code=503, detail="inventory unavailable")
            if should_fail:
                raise HTTPException(status_code=500, detail="injected inventory error")
            return {"sku": sku, "available": 42, "service": active_settings.service_name}

        @application.get("/admin/faults")
        async def get_fault() -> dict[str, int | float | str]:
            return await fault_state.snapshot()

        @application.post("/admin/faults")
        async def set_fault(request: FaultRequest) -> dict[str, int | float | str]:
            config = FaultConfig(
                mode=request.mode,
                delay_ms=request.delay_ms,
                error_rate=request.error_rate,
            )
            result = await fault_state.configure(config)
            metrics.set_fault_mode(request.mode)
            changes.appendleft(
                {
                    "change_id": str(uuid4()),
                    "service": active_settings.service_name,
                    "change_type": "fault_injection",
                    "version": f"fault-{request.mode}",
                    "operator": "axiomops-lab",
                    "created_at": datetime.now(UTC).isoformat(),
                    "description": (
                        f"Configured inventory fault mode={request.mode}, "
                        f"delay_ms={request.delay_ms}, error_rate={request.error_rate}"
                    ),
                }
            )
            return result

        @application.post("/admin/faults/reset")
        async def reset_fault() -> dict[str, int | float | str]:
            result = await fault_state.reset()
            metrics.set_fault_mode("none")
            changes.appendleft(
                {
                    "change_id": str(uuid4()),
                    "service": active_settings.service_name,
                    "change_type": "fault_reset",
                    "version": "fault-none",
                    "operator": "axiomops-lab",
                    "created_at": datetime.now(UTC).isoformat(),
                    "description": "Reset inventory fault injection state",
                }
            )
            return result

    if active_settings.role == "order":

        @application.get("/orders/{sku}")
        async def create_order(sku: str) -> dict[str, Any]:
            trace_id = str(uuid4())
            root_started = perf_counter()
            downstream_status = "success"
            downstream_error: str | None = None
            downstream_duration_ms = 0.0
            try:
                async with httpx.AsyncClient(
                    transport=inventory_transport,
                    timeout=active_settings.downstream_timeout_seconds,
                ) as client:
                    downstream_started = perf_counter()
                    response = await client.get(
                        f"{active_settings.inventory_url}/inventory/{sku}"
                    )
                    downstream_duration_ms = round(
                        (perf_counter() - downstream_started) * 1000,
                        2,
                    )
            except httpx.TimeoutException as exc:
                downstream_status = "timeout"
                downstream_error = "inventory timeout"
                metrics.downstream_requests.labels(
                    service=active_settings.service_name,
                    target="inventory-service",
                    status="timeout",
                ).inc()
                traces.appendleft(
                    trace_record(
                        trace_id,
                        active_settings.service_name,
                        sku,
                        downstream_status,
                        downstream_duration_ms,
                        downstream_error,
                        root_started,
                    )
                )
                raise HTTPException(status_code=503, detail="inventory timeout") from exc
            except httpx.RequestError as exc:
                downstream_status = "connection_error"
                downstream_error = "inventory connection failed"
                metrics.downstream_requests.labels(
                    service=active_settings.service_name,
                    target="inventory-service",
                    status="connection_error",
                ).inc()
                traces.appendleft(
                    trace_record(
                        trace_id,
                        active_settings.service_name,
                        sku,
                        downstream_status,
                        downstream_duration_ms,
                        downstream_error,
                        root_started,
                    )
                )
                raise HTTPException(
                    status_code=503, detail="inventory connection failed"
                ) from exc

            if response.is_error:
                downstream_status = f"http_{response.status_code}"
                downstream_error = f"inventory returned {response.status_code}"
                metrics.downstream_requests.labels(
                    service=active_settings.service_name,
                    target="inventory-service",
                    status=f"http_{response.status_code}",
                ).inc()
                traces.appendleft(
                    trace_record(
                        trace_id,
                        active_settings.service_name,
                        sku,
                        downstream_status,
                        downstream_duration_ms,
                        downstream_error,
                        root_started,
                    )
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"inventory returned {response.status_code}",
                )

            metrics.downstream_requests.labels(
                service=active_settings.service_name,
                target="inventory-service",
                status="success",
            ).inc()
            traces.appendleft(
                trace_record(
                    trace_id,
                    active_settings.service_name,
                    sku,
                    downstream_status,
                    downstream_duration_ms,
                    downstream_error,
                    root_started,
                )
            )
            return {
                "status": "accepted",
                "sku": sku,
                "inventory": response.json(),
                "service": active_settings.service_name,
            }

    return application


def trace_record(
    trace_id: str,
    service: str,
    sku: str,
    downstream_status: str,
    downstream_duration_ms: float,
    downstream_error: str | None,
    root_started: float,
) -> dict[str, Any]:
    total_duration_ms = round((perf_counter() - root_started) * 1000, 2)
    return {
        "trace_id": trace_id,
        "root": {
            "span_id": f"{trace_id}:order",
            "service": service,
            "operation": "GET /orders/{sku}",
            "status": "error" if downstream_error else "success",
            "duration_ms": total_duration_ms,
            "sku": sku,
        },
        "downstream": {
            "span_id": f"{trace_id}:inventory",
            "parent_span_id": f"{trace_id}:order",
            "service": "inventory-service",
            "operation": "GET /inventory/{sku}",
            "status": downstream_status,
            "duration_ms": downstream_duration_ms,
            "error": downstream_error,
        },
        "created_at": datetime.now(UTC).isoformat(),
    }


app = create_lab_app()
