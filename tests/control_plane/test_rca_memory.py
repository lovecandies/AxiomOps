from datetime import UTC, datetime

from qdrant_client import QdrantClient

from axiom_ops.control_plane.models import (
    RcaReportView,
    VerificationDecision,
    VerificationResult,
)
from axiom_ops.control_plane.rca_memory import RcaMemoryStore


class FakeEmbedder:
    dimension = 3

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float("inventory" in text), 0.5] for text in texts]


def test_only_indexed_verified_report_is_recalled_for_another_incident() -> None:
    store = RcaMemoryStore(QdrantClient(":memory:"), FakeEmbedder(), "rca")
    report = RcaReportView(
        id="00000000-0000-0000-0000-000000000001",
        run_id="run-1",
        incident_id="incident-1",
        summary="Inventory latency increased.",
        root_cause="Inventory dependency degradation.",
        confidence=0.8,
        contributing_factors=[],
        rejected_hypotheses=[],
        evidence_ids=["evidence-1"],
        limitations=[],
        verification=VerificationResult(
            decision=VerificationDecision.APPROVED,
            rationale="Grounded.",
        ),
        created_at=datetime.now(UTC),
    )
    store.index(
        {"id": "incident-1", "service": "inventory-service", "severity": "SEV2"},
        report,
    )

    same_incident = store.search(
        {"id": "incident-1", "service": "inventory-service"}, 3
    )
    another_incident = store.search(
        {"id": "incident-2", "service": "inventory-service"}, 3
    )

    assert same_incident == []
    assert another_incident[0]["report_id"] == report.id
    assert another_incident[0]["notice"] == "historical hint only; not citable Evidence"
