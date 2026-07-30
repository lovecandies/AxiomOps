import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST
from qdrant_client import QdrantClient

from axiom_ops.control_plane.checkpoint import redis_checkpointer
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
    ChangeEventToolInput,
    EvidenceView,
    FaultStateToolInput,
    HealthToolInput,
    IncidentCreate,
    IncidentView,
    MetricsToolInput,
    OrderFlowProbeInput,
    RecoveryApprovalView,
    RecoveryDecisionRequest,
    RecoveryExecutionView,
    RecoveryRequest,
    RcaReportView,
    RcaRunView,
    ToolSelectionPlan,
    TraceSnapshotToolInput,
)
from axiom_ops.control_plane.observability import (
    ControlPlaneObservability,
    observability_middleware,
)
from axiom_ops.control_plane.rca_model import DeepSeekRcaModel
from axiom_ops.control_plane.rca_memory import FastEmbedder, RcaMemoryStore
from axiom_ops.control_plane.rca_repository import RcaRepository
from axiom_ops.control_plane.rca_runtime import (
    RcaIncidentNotFound,
    RcaReportNotFound,
    RcaRunNotFound,
    RcaRunNotResumable,
    RcaRuntime,
)
from axiom_ops.control_plane.recovery_repository import RecoveryRepository
from axiom_ops.control_plane.recovery_service import (
    RecoveryNotFound,
    RecoveryPermissionError,
    RecoveryService,
    RecoveryTransitionError,
    SandboxRecoveryExecutor,
)
from axiom_ops.control_plane.repository import IdempotencyConflict, IncidentRepository
from axiom_ops.control_plane.typed_tools import (
    ChangeEventTool,
    MetricsSnapshotTool,
    InventoryFaultStateTool,
    OrderFlowProbeTool,
    ServiceHealthTool,
    TraceSnapshotTool,
    ToolExecutionError,
)
from starlette.responses import StreamingResponse


def create_control_plane_app(
    repository: IncidentRepository | None = None,
    database: Database | None = None,
    evidence_service: EvidenceService | None = None,
    rca_runtime: RcaRuntime | None = None,
    recovery_service: RecoveryService | None = None,
) -> FastAPI:
    settings = ControlPlaneSettings()
    active_database = database or Database(settings)
    active_repository = repository or IncidentRepository(active_database)
    active_evidence_service = evidence_service or EvidenceService(
        EvidenceRepository(active_database),
        EvidenceStorage(settings.evidence_root),
        MetricsSnapshotTool(settings),
        ServiceHealthTool(settings),
        InventoryFaultStateTool(settings),
        OrderFlowProbeTool(settings),
        TraceSnapshotTool(settings),
        ChangeEventTool(settings),
        lambda: DeepSeekRcaModel(settings),
        active_repository.get_incident,
    )
    active_rca_runtime = rca_runtime or RcaRuntime(
        active_repository,
        EvidenceRepository(active_database),
        EvidenceStorage(settings.evidence_root),
        RcaRepository(active_database),
        lambda: DeepSeekRcaModel(settings),
        lambda: redis_checkpointer(settings.redis_url),
        RcaMemoryStore(
            QdrantClient(url=settings.qdrant_url),
            FastEmbedder(
                settings.memory_embedding_model,
                settings.memory_embedding_dimension,
            ),
            settings.qdrant_collection,
        ),
        settings.context_total_chars,
        settings.context_evidence_chars,
        settings.memory_top_k,
    )
    active_recovery_service = recovery_service or RecoveryService(
        active_repository,
        RcaRepository(active_database),
        RecoveryRepository(active_database),
        SandboxRecoveryExecutor(settings),
    )
    observability = ControlPlaneObservability()
    application = FastAPI(title="AxiomOps Incident Control Plane", version="0.5.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def observe_request(request: Request, call_next) -> Response:
        return await observability_middleware(request, call_next, observability)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "incident-control-plane"}

    @application.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(
            content=observability.render(),
            media_type=CONTENT_TYPE_LATEST,
        )

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
            observability.record_event("incident.create", "conflict")
            raise HTTPException(
                status_code=409,
                detail="idempotency key was already used with another request",
            ) from exc
        response.status_code = 201 if created else 200
        observability.record_event(
            "incident.create",
            "created" if created else "idempotent_replay",
        )
        return incident

    @application.get("/incidents/{incident_id}", response_model=IncidentView)
    def get_incident(incident_id: str) -> IncidentView:
        incident = active_repository.get_incident(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return incident

    @application.get("/incidents", response_model=list[IncidentView])
    def list_incidents() -> list[IncidentView]:
        return active_repository.list_incidents()

    @application.get("/incidents/{incident_id}/events")
    async def incident_events(incident_id: str) -> StreamingResponse:
        if active_repository.get_incident(incident_id) is None:
            raise HTTPException(status_code=404, detail="incident not found")

        async def stream() -> AsyncIterator[str]:
            previous = ""
            while True:
                incident = active_repository.get_incident(incident_id)
                if incident is None:
                    return
                payload = incident.model_dump(mode="json")
                encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if encoded != previous:
                    previous = encoded
                    yield f"event: incident\\ndata: {encoded}\\n\\n"
                else:
                    yield "event: heartbeat\\ndata: {}\\n\\n"
                await asyncio.sleep(1)

        return StreamingResponse(stream(), media_type="text/event-stream")

    def execute_tool(action: Callable[[], Any]) -> Any:
        try:
            return action()
        except IncidentNotFound as exc:
            raise HTTPException(status_code=404, detail="incident not found") from exc
        except ToolExecutionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def require_role(actual: str, expected: str) -> None:
        if actual != expected:
            raise HTTPException(
                status_code=403,
                detail=f"requires X-AxiomOps-Role: {expected}",
            )

    def translate_recovery_error(action: Callable[[], object]) -> object:
        try:
            return action()
        except RecoveryNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RecoveryPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RecoveryTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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

    @application.post(
        "/incidents/{incident_id}/tools/fault-state",
        response_model=EvidenceView,
        status_code=201,
    )
    def execute_fault_state(
        incident_id: str, tool_input: FaultStateToolInput
    ) -> EvidenceView:
        return execute_tool(
            lambda: active_evidence_service.execute_fault_state(incident_id, tool_input)
        )

    @application.post(
        "/incidents/{incident_id}/tools/order-flow",
        response_model=EvidenceView,
        status_code=201,
    )
    def execute_order_flow(
        incident_id: str, tool_input: OrderFlowProbeInput
    ) -> EvidenceView:
        return execute_tool(
            lambda: active_evidence_service.execute_order_flow(incident_id, tool_input)
        )

    @application.post(
        "/incidents/{incident_id}/tools/trace",
        response_model=EvidenceView,
        status_code=201,
    )
    def execute_trace_snapshot(
        incident_id: str, tool_input: TraceSnapshotToolInput
    ) -> EvidenceView:
        return execute_tool(
            lambda: active_evidence_service.execute_trace_snapshot(
                incident_id,
                tool_input,
            )
        )

    @application.post(
        "/incidents/{incident_id}/tools/change",
        response_model=EvidenceView,
        status_code=201,
    )
    def execute_change_events(
        incident_id: str, tool_input: ChangeEventToolInput
    ) -> EvidenceView:
        return execute_tool(
            lambda: active_evidence_service.execute_change_events(
                incident_id,
                tool_input,
            )
        )

    @application.get(
        "/incidents/{incident_id}/tools/selection-plan",
        response_model=ToolSelectionPlan,
    )
    def plan_tool_selection(incident_id: str) -> ToolSelectionPlan:
        try:
            return active_evidence_service.plan_tool_selection(incident_id)
        except IncidentNotFound as exc:
            raise HTTPException(status_code=404, detail="incident not found") from exc

    @application.post(
        "/incidents/{incident_id}/tools/auto-collect",
        response_model=list[EvidenceView],
        status_code=201,
    )
    def auto_collect_evidence(incident_id: str) -> list[EvidenceView]:
        return execute_tool(
            lambda: active_evidence_service.execute_tool_selection(incident_id)
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

    @application.post(
        "/incidents/{incident_id}/rca-runs",
        response_model=RcaRunView,
        status_code=201,
    )
    def start_rca_run(incident_id: str) -> RcaRunView:
        try:
            run = active_rca_runtime.run(incident_id)
            observability.record_event("rca.run", run.status.value.lower())
            return run
        except RcaIncidentNotFound as exc:
            observability.record_event("rca.run", "incident_not_found")
            raise HTTPException(status_code=404, detail="incident not found") from exc

    @application.get("/rca-runs/{run_id}", response_model=RcaRunView)
    def get_rca_run(run_id: str) -> RcaRunView:
        try:
            return active_rca_runtime.get_run(run_id)
        except RcaRunNotFound as exc:
            raise HTTPException(status_code=404, detail="RCA run not found") from exc

    @application.post("/rca-runs/{run_id}/resume", response_model=RcaRunView)
    def resume_rca_run(run_id: str) -> RcaRunView:
        try:
            run = active_rca_runtime.resume(run_id)
            observability.record_event("rca.resume", run.status.value.lower())
            return run
        except RcaRunNotFound as exc:
            observability.record_event("rca.resume", "not_found")
            raise HTTPException(status_code=404, detail="RCA run not found") from exc
        except RcaRunNotResumable as exc:
            observability.record_event("rca.resume", "not_resumable")
            raise HTTPException(status_code=409, detail="RCA run is not resumable") from exc

    @application.get("/incidents/{incident_id}/rca", response_model=RcaReportView)
    def get_latest_rca(incident_id: str) -> RcaReportView:
        try:
            return active_rca_runtime.get_latest_report(incident_id)
        except RcaIncidentNotFound as exc:
            raise HTTPException(status_code=404, detail="incident not found") from exc
        except RcaReportNotFound as exc:
            raise HTTPException(status_code=404, detail="verified RCA not found") from exc

    @application.post(
        "/incidents/{incident_id}/recovery-approvals",
        response_model=RecoveryApprovalView,
        status_code=201,
    )
    def request_recovery(
        incident_id: str,
        request: RecoveryRequest,
        x_axiomops_user: str = Header(
            min_length=1,
            max_length=128,
            alias="X-AxiomOps-User",
        ),
        x_axiomops_role: str = Header(alias="X-AxiomOps-Role"),
    ) -> RecoveryApprovalView:
        require_role(x_axiomops_role, "commander")
        approval = translate_recovery_error(
            lambda: active_recovery_service.request_recovery(
                incident_id,
                request,
                x_axiomops_user,
            )
        )
        observability.record_event("recovery.request", "created")
        return approval

    @application.get(
        "/recovery-approvals/{approval_id}",
        response_model=RecoveryApprovalView,
    )
    def get_recovery_approval(approval_id: str) -> RecoveryApprovalView:
        return translate_recovery_error(
            lambda: active_recovery_service.get_approval(approval_id)
        )

    @application.post(
        "/recovery-approvals/{approval_id}/approve",
        response_model=RecoveryApprovalView,
    )
    def approve_recovery(
        approval_id: str,
        decision: RecoveryDecisionRequest,
        x_axiomops_user: str = Header(
            min_length=1,
            max_length=128,
            alias="X-AxiomOps-User",
        ),
        x_axiomops_role: str = Header(alias="X-AxiomOps-Role"),
    ) -> RecoveryApprovalView:
        require_role(x_axiomops_role, "approver")
        approval = translate_recovery_error(
            lambda: active_recovery_service.approve(
                approval_id,
                x_axiomops_user,
                decision.comment,
            )
        )
        observability.record_event("recovery.approve", "approved")
        return approval

    @application.post(
        "/recovery-approvals/{approval_id}/execute",
        response_model=RecoveryExecutionView,
    )
    def execute_recovery(
        approval_id: str,
        x_axiomops_user: str = Header(
            min_length=1,
            max_length=128,
            alias="X-AxiomOps-User",
        ),
        x_axiomops_role: str = Header(alias="X-AxiomOps-Role"),
    ) -> RecoveryExecutionView:
        require_role(x_axiomops_role, "operator")
        execution = translate_recovery_error(
            lambda: active_recovery_service.execute(approval_id, x_axiomops_user)
        )
        observability.record_event(
            "recovery.execute",
            execution.status.value.lower(),
        )
        return execution

    @application.get(
        "/recovery-executions/{execution_id}",
        response_model=RecoveryExecutionView,
    )
    def get_recovery_execution(execution_id: str) -> RecoveryExecutionView:
        return translate_recovery_error(
            lambda: active_recovery_service.get_execution(execution_id)
        )

    return application


app = create_control_plane_app()
