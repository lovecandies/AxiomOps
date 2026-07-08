from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from axiom_ops import __version__
from axiom_ops.config import Settings, get_settings


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    phase: str = "phase-0"


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"
    environment: str
    dependencies: dict[str, str]


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()

    application = FastAPI(
        title="AxiomOps",
        description="Evidence-driven multi-agent AIOps incident diagnosis and safe recovery system",
        version=__version__,
    )

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            service=active_settings.service_name,
            version=__version__,
        )

    @application.get("/ready", response_model=ReadinessResponse)
    async def ready() -> ReadinessResponse:
        return ReadinessResponse(
            environment=active_settings.environment,
            dependencies={},
        )

    return application


app = create_app()
