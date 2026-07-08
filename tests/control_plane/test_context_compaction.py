import json

from axiom_ops.control_plane.context_compaction import compact_evidence


def test_compaction_preserves_evidence_identity_and_budget() -> None:
    evidence = [
        {
            "id": "evidence-1",
            "kind": "METRIC_SNAPSHOT",
            "source": "prometheus",
            "observed_at": "2026-07-08T00:00:00+00:00",
            "content_sha256": "a" * 64,
            "content": {
                "tool_name": "prometheus.metrics.snapshot",
                "data": {
                    "query": "up",
                    "response": {
                        "data": {"result": [{"values": ["x" * 3000]}]}
                    },
                },
            },
        }
    ]

    result = compact_evidence(evidence, total_chars=700, per_evidence_chars=500)

    assert result.capsules[0]["id"] == "evidence-1"
    assert result.capsules[0]["content_sha256"] == "a" * 64
    assert len(json.dumps(result.capsules, ensure_ascii=False, separators=(",", ":"))) <= 700
    assert result.compressed_bytes < result.original_bytes
