from collections.abc import Callable

from fastapi import FastAPI, Header, HTTPException, Response

from axiom_ops.control_plane.config import ControlPlaneSettings
from axiom_ops.control_plane.database import Database
from axiom_ops.control_plane.evidence_repository import EvidenceRepository
from axiom_ops.control_plane.evidence_service import (
    EvidenceNotFound,
    EvidenceService,
    IncidentNotFound,
)
from axiom_ops.control_plane.evidence_storage import (
    EvidenceIntegrityError,
    EvidenceStorage,
)
from axiom_ops.control_plane.models import (
    EvidenceView,
    HealthToolInput,
    IncidentCreate,
    IncidentView,
    MetricsToolInput,
)
from axiom_ops.control_plane.repository import IdempotencyConflict, IncidentRepository
from axiom_ops.control_plane.typed_tools import (
    MetricsSnapshotTool,
    ServiceHealthTool,
    ToolExecutionError,
)


def create_control_plane_app(
    repository: IncidentRepository | None = None,
    database: Database | None = None,
    evidence_service: EvidenceService | None = None,
) -> FastAPI:
    settings = ControlPlaneSettings()
    active_database = database or Database(settings)
    active_repository = repository or IncidentRepository(active_database)
    active_evidence_service = evidence_service or EvidenceService(
        EvidenceRepository(active_database),
        EvidenceStorage(settings.evidence_root),
        MetricsSnapshotTool(settings),
        ServiceHealthTool(settings),
    )
    application = FastAPI(title="AxiomOps Incident Control Plane", version="0.3.0")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "incident-control-plane"}

    @application.get("/ready")
    def ready() -> dict[str, str]:
        try:
            active_database.verify_schema()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="mysql unavailable") from exc
        return {"status": "ready", "mysql": "up"}

    @application.post("/incidents", response_model=IncidentView, status_code=201)
    def create_incident(
        request: IncidentCreate,
        response: Response,
        idempotency_key: str = Header(
            min_length=8,
            max_length=128,
            alias="Idempotency-Key",
        ),
    ) -> IncidentView:
        try:
            incident, created = active_repository.create_incident(
                idempotency_key,
                request,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail="idempotency key was already used with another request",
            ) from exc
        response.status_code = 201 if created else 200
        return incident

    @application.get("/incidents/{incident_id}", response_model=IncidentView)
    def get_incident(incident_id: str) -> IncidentView:
        incident = active_repository.get_incident(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return incident

    def execute_tool(action: Callable[[], EvidenceView]) -> EvidenceView:
        try:
            return action()
        except IncidentNotFound as exc:
            raise HTTPException(status_code=404, detail="incident not found") from exc
        except ToolExecutionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.post(
        "/incidents/{incident_id}/tools/metrics",
        response_model=EvidenceView,
        status_code=201,
    )
    def execute_metrics(
        incident_id: str,
        tool_input: MetricsToolInput,
    ) -> EvidenceView:
        return execute_tool(
            lambda: active_evidence_service.execute_metrics(incident_id, tool_input)
        )

    @application.post(
        "/incidents/{incident_id}/tools/health",
        response_model=EvidenceView,
        status_code=201,
    )
    def execute_health(
        incident_id: str,
        tool_input: HealthToolInput,
    ) -> EvidenceView:
        return execute_tool(
            lambda: active_evidence_service.execute_health(incident_id, tool_input)
        )

    @application.get(
        "/incidents/{incident_id}/evidence",
        response_model=list[EvidenceView],
    )
    def list_evidence(incident_id: str) -> list[EvidenceView]:
        try:
            return active_evidence_service.list_for_incident(incident_id)
        except IncidentNotFound as exc:
            raise HTTPException(status_code=404, detail="incident not found") from exc

    @application.get("/evidence/{evidence_id}/content")
    def read_evidence_content(evidence_id: str) -> dict:
        try:
            return active_evidence_service.read_content(evidence_id)
        except EvidenceNotFound as exc:
            raise HTTPException(status_code=404, detail="evidence not found") from exc
        except EvidenceIntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return application


app = create_control_plane_app()
