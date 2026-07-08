from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

from axiom_ops.control_plane.evidence_repository import EvidenceRepository
from axiom_ops.control_plane.evidence_storage import EvidenceStorage
from axiom_ops.control_plane.models import (
    RcaDraft,
    RcaReportView,
    RcaRunView,
    VerificationResult,
)
from axiom_ops.control_plane.rca_graph import GRAPH_VERSION, ReadOnlyRcaGraph
from axiom_ops.control_plane.rca_model import RcaModel
from axiom_ops.control_plane.rca_repository import RcaRepository
from axiom_ops.control_plane.repository import IncidentRepository


class RcaIncidentNotFound(Exception):
    pass


class RcaRunNotFound(Exception):
    pass


class RcaReportNotFound(Exception):
    pass


class RcaRuntime:
    def __init__(
        self,
        incident_repository: IncidentRepository,
        evidence_repository: EvidenceRepository,
        evidence_storage: EvidenceStorage,
        rca_repository: RcaRepository,
        model_factory: Callable[[], RcaModel],
    ) -> None:
        self.incident_repository = incident_repository
        self.evidence_repository = evidence_repository
        self.evidence_storage = evidence_storage
        self.rca_repository = rca_repository
        self.model_factory = model_factory

    def run(self, incident_id: str) -> RcaRunView:
        incident = self.incident_repository.get_incident(incident_id)
        if incident is None:
            raise RcaIncidentNotFound(incident_id)
        metadata = self.evidence_repository.list_for_incident(incident_id)
        model = self.model_factory()
        run_id = str(uuid4())
        evidence_ids = [item.id for item in metadata]
        self.rca_repository.create_run(
            run_id,
            incident_id,
            model.model_name,
            GRAPH_VERSION,
            evidence_ids,
        )
        started = perf_counter()
        try:
            if not metadata:
                raise RuntimeError("RCA requires at least one verified Evidence")
            evidence = [
                {
                    "id": item.id,
                    "kind": item.kind.value,
                    "source": item.source,
                    "observed_at": item.observed_at.isoformat(),
                    "content_sha256": item.content_sha256,
                    "content": self.evidence_storage.read_verified(
                        item.artifact_path,
                        item.content_sha256,
                    ),
                }
                for item in metadata
            ]
            graph = ReadOnlyRcaGraph(model)
            result = graph.invoke(incident.model_dump(mode="json"), evidence)
            draft = RcaDraft.model_validate(result["draft"])
            verification = VerificationResult.model_validate(result["verification"])
            duration_ms = round((perf_counter() - started) * 1000)
            self.rca_repository.finish_run(
                run_id,
                incident_id,
                draft,
                verification,
                result["steps"],
                model.call_count,
                model.total_tokens,
                duration_ms,
            )
        except Exception as exc:
            duration_ms = round((perf_counter() - started) * 1000)
            self.rca_repository.fail_run(
                run_id,
                f"{type(exc).__name__}: {exc}",
                model.call_count,
                model.total_tokens,
                duration_ms,
            )
        run = self.rca_repository.get_run(run_id)
        assert run is not None
        return run

    def get_run(self, run_id: str) -> RcaRunView:
        run = self.rca_repository.get_run(run_id)
        if run is None:
            raise RcaRunNotFound(run_id)
        return run

    def get_latest_report(self, incident_id: str) -> RcaReportView:
        if self.incident_repository.get_incident(incident_id) is None:
            raise RcaIncidentNotFound(incident_id)
        report = self.rca_repository.get_latest_report(incident_id)
        if report is None:
            raise RcaReportNotFound(incident_id)
        return report
