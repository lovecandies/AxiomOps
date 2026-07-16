from typing import Any, Protocol

from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

from axiom_ops.control_plane.models import RcaReportView


class Embedder(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    def __init__(self, model_name: str, dimension: int) -> None:
        self.model_name = model_name
        self._model: TextEmbedding | None = None
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._model = TextEmbedding(model_name=self.model_name)
        return [vector.tolist() for vector in self._model.embed(texts)]


class RcaMemoryStore:
    def __init__(
        self,
        client: QdrantClient,
        embedder: Embedder,
        collection: str,
    ) -> None:
        self.client = client
        self.embedder = embedder
        self.collection = collection

    def setup(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=self.embedder.dimension,
                    distance=models.Distance.COSINE,
                ),
            )

    @staticmethod
    def incident_text(incident: dict[str, Any]) -> str:
        return "\n".join(
            str(incident.get(key, ""))
            for key in ("service", "severity", "title", "summary")
        )

    def index(self, incident: dict[str, Any], report: RcaReportView) -> None:
        self.setup()
        text = "\n".join(
            [self.incident_text(incident), report.summary, report.root_cause]
        )
        vector = self.embedder.embed([text])[0]
        self.client.upsert(
            collection_name=self.collection,
            wait=True,
            points=[
                models.PointStruct(
                    id=report.id,
                    vector=vector,
                    payload={
                        "report_id": report.id,
                        "run_id": report.run_id,
                        "incident_id": report.incident_id,
                        "service": incident.get("service"),
                        "severity": str(incident.get("severity", "")),
                        "summary": report.summary,
                        "root_cause": report.root_cause,
                        "limitations": report.limitations,
                        "evidence_ids": report.evidence_ids,
                        "verified": True,
                    },
                )
            ],
        )

    def search(self, incident: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        self.setup()
        if self.client.count(self.collection, exact=True).count == 0:
            return []
        vector = self.embedder.embed([self.incident_text(incident)])[0]
        result = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="service",
                        match=models.MatchValue(value=incident.get("service")),
                    ),
                    models.FieldCondition(
                        key="verified",
                        match=models.MatchValue(value=True),
                    ),
                ],
                must_not=[
                    models.FieldCondition(
                        key="incident_id",
                        match=models.MatchValue(value=incident.get("id")),
                    )
                ],
            ),
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "score": point.score,
                "report_id": point.payload["report_id"],
                "incident_id": point.payload["incident_id"],
                "summary": point.payload["summary"],
                "root_cause": point.payload["root_cause"],
                "limitations": point.payload.get("limitations", []),
                "notice": "historical hint only; not citable Evidence",
            }
            for point in result.points
            if point.payload is not None
        ]
