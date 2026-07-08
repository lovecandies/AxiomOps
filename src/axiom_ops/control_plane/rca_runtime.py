import logging
from collections.abc import Callable
from contextlib import nullcontext
from time import perf_counter
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver

from axiom_ops.control_plane.context_compaction import compact_evidence
from axiom_ops.control_plane.evidence_repository import EvidenceRepository
from axiom_ops.control_plane.evidence_storage import EvidenceStorage
from axiom_ops.control_plane.models import (
    RcaDraft,
    RcaReportView,
    RcaRunStatus,
    RcaRunView,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.rca_graph import GRAPH_VERSION, ReadOnlyRcaGraph
from axiom_ops.control_plane.rca_memory import RcaMemoryStore
from axiom_ops.control_plane.rca_model import RcaModel
from axiom_ops.control_plane.rca_repository import RcaRepository
from axiom_ops.control_plane.repository import IncidentRepository


LOGGER = logging.getLogger(__name__)


class RcaIncidentNotFound(Exception):
    pass


class RcaRunNotFound(Exception):
    pass


class RcaReportNotFound(Exception):
    pass


class RcaRunNotResumable(Exception):
    pass


class RcaRuntime:
    def __init__(
        self,
        incident_repository: IncidentRepository,
        evidence_repository: EvidenceRepository,
        evidence_storage: EvidenceStorage,
        rca_repository: RcaRepository,
        model_factory: Callable[[], RcaModel],
        checkpoint_factory: Callable[[], Any] | None = None,
        memory_store: RcaMemoryStore | None = None,
        context_total_chars: int = 12000,
        context_evidence_chars: int = 4000,
        memory_top_k: int = 3,
    ) -> None:
        self.incident_repository = incident_repository
        self.evidence_repository = evidence_repository
        self.evidence_storage = evidence_storage
        self.rca_repository = rca_repository
        self.model_factory = model_factory
        self._memory_checkpointer = InMemorySaver()
        self.checkpoint_factory = checkpoint_factory or (
            lambda: nullcontext(self._memory_checkpointer)
        )
        self.memory_store = memory_store
        self.context_total_chars = context_total_chars
        self.context_evidence_chars = context_evidence_chars
        self.memory_top_k = memory_top_k

    @staticmethod
    def _validate_model(model: RcaModel) -> None:
        validate = getattr(model, "validate_configuration", None)
        if callable(validate):
            validate()

    def _historical_memory(self, incident: dict[str, Any]) -> list[dict[str, Any]]:
        if self.memory_store is None:
            return []
        try:
            return self.memory_store.search(incident, self.memory_top_k)
        except Exception:
            LOGGER.warning("Qdrant memory lookup failed; continuing without hints", exc_info=True)
            return []

    def _index_verified_report(self, incident: dict[str, Any], run_id: str) -> None:
        if self.memory_store is None:
            return
        report = self.rca_repository.get_report_for_run(run_id)
        if report is None or report.verification.decision != VerificationDecision.APPROVED:
            return
        try:
            self.memory_store.index(incident, report)
        except Exception:
            LOGGER.warning("Qdrant indexing failed; RCA remains committed", exc_info=True)

    def _finish(
        self,
        run_id: str,
        incident: dict[str, Any],
        result: dict[str, Any],
        model: RcaModel,
        previous_calls: int,
        previous_tokens: int,
        previous_duration_ms: int,
        started: float,
    ) -> None:
        draft = RcaDraft.model_validate(result["draft"])
        verification = VerificationResult.model_validate(result["verification"])
        duration_ms = previous_duration_ms + round((perf_counter() - started) * 1000)
        self.rca_repository.finish_run(
            run_id,
            incident["id"],
            draft,
            verification,
            result["steps"],
            previous_calls + model.call_count,
            previous_tokens + model.total_tokens,
            duration_ms,
        )
        if verification.decision == VerificationDecision.APPROVED:
            self._index_verified_report(incident, run_id)

    def run(self, incident_id: str) -> RcaRunView:
        incident_view = self.incident_repository.get_incident(incident_id)
        if incident_view is None:
            raise RcaIncidentNotFound(incident_id)
        metadata = self.evidence_repository.list_for_incident(incident_id)
        model = self.model_factory()
        run_id = str(uuid4())
        self.rca_repository.create_run(
            run_id,
            incident_id,
            model.model_name,
            GRAPH_VERSION,
            [item.id for item in metadata],
        )
        started = perf_counter()
        try:
            self._validate_model(model)
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
            compacted = compact_evidence(
                evidence,
                self.context_total_chars,
                self.context_evidence_chars,
            )
            self.rca_repository.create_context(
                run_id,
                compacted.original_bytes,
                compacted.compressed_bytes,
                compacted.capsules,
            )
            incident = incident_view.model_dump(mode="json")
            memory = self._historical_memory(incident)
            with self.checkpoint_factory() as checkpointer:
                graph = ReadOnlyRcaGraph(model, checkpointer)
                result = graph.invoke(incident, compacted.capsules, run_id, memory)
            self._finish(run_id, incident, result, model, 0, 0, 0, started)
        except Exception as exc:
            self.rca_repository.fail_run(
                run_id,
                f"{type(exc).__name__}: {exc}",
                model.call_count,
                model.total_tokens,
                round((perf_counter() - started) * 1000),
            )
        run = self.rca_repository.get_run(run_id)
        assert run is not None
        return run

    def resume(self, run_id: str) -> RcaRunView:
        previous = self.rca_repository.get_run(run_id)
        if previous is None:
            raise RcaRunNotFound(run_id)
        if previous.status != RcaRunStatus.FAILED:
            raise RcaRunNotResumable(run_id)
        incident_view = self.incident_repository.get_incident(previous.incident_id)
        if incident_view is None:
            raise RcaIncidentNotFound(previous.incident_id)
        model = self.model_factory()
        self.rca_repository.resume_run(run_id)
        started = perf_counter()
        try:
            self._validate_model(model)
            with self.checkpoint_factory() as checkpointer:
                graph = ReadOnlyRcaGraph(model, checkpointer)
                result = graph.resume(run_id)
            self._finish(
                run_id,
                incident_view.model_dump(mode="json"),
                result,
                model,
                previous.model_calls,
                previous.total_tokens,
                previous.duration_ms or 0,
                started,
            )
        except Exception as exc:
            self.rca_repository.fail_run(
                run_id,
                f"{type(exc).__name__}: {exc}",
                previous.model_calls + model.call_count,
                previous.total_tokens + model.total_tokens,
                (previous.duration_ms or 0)
                + round((perf_counter() - started) * 1000),
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
