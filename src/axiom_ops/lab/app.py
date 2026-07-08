import asyncio
from time import perf_counter
from typing import Any

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
            return result

        @application.post("/admin/faults/reset")
        async def reset_fault() -> dict[str, int | float | str]:
            result = await fault_state.reset()
            metrics.set_fault_mode("none")
            return result

    if active_settings.role == "order":

        @application.get("/orders/{sku}")
        async def create_order(sku: str) -> dict[str, Any]:
            try:
                async with httpx.AsyncClient(
                    transport=inventory_transport,
                    timeout=active_settings.downstream_timeout_seconds,
                ) as client:
                    response = await client.get(
                        f"{active_settings.inventory_url}/inventory/{sku}"
                    )
            except httpx.TimeoutException as exc:
                metrics.downstream_requests.labels(
                    service=active_settings.service_name,
                    target="inventory-service",
                    status="timeout",
                ).inc()
                raise HTTPException(status_code=503, detail="inventory timeout") from exc
            except httpx.RequestError as exc:
                metrics.downstream_requests.labels(
                    service=active_settings.service_name,
                    target="inventory-service",
                    status="connection_error",
                ).inc()
                raise HTTPException(
                    status_code=503, detail="inventory connection failed"
                ) from exc

            if response.is_error:
                metrics.downstream_requests.labels(
                    service=active_settings.service_name,
                    target="inventory-service",
                    status=f"http_{response.status_code}",
                ).inc()
                raise HTTPException(
                    status_code=503,
                    detail=f"inventory returned {response.status_code}",
                )

            metrics.downstream_requests.labels(
                service=active_settings.service_name,
                target="inventory-service",
                status="success",
            ).inc()
            return {
                "status": "accepted",
                "sku": sku,
                "inventory": response.json(),
                "service": active_settings.service_name,
            }

    return application


app = create_lab_app()
