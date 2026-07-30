from axiom_ops.evaluation.optimization_benchmark import build_optimization_report


def test_optimization_benchmark_reports_measured_tradeoffs() -> None:
    report = build_optimization_report()

    assert report["citation_guard"]["invalid_citation_interception_rate"] == 1.0
    assert report["citation_guard"]["guarded_unsafe_release_rate"] == 0.0
    assert report["tool_completion"]["tool_call_reduction_rate"] == 0.5
    assert report["tool_completion"]["required_evidence_coverage"] == 1.0
    assert report["context_compaction"]["context_reduction_rate"] > 0.5
    assert report["context_compaction"]["evidence_identity_preserved"] is True
    assert report["checkpoint_resume"]["reexecution_avoidance_rate"] == 0.6667
    assert report["checkpoint_resume"]["completed_branches_preserved"] is True
