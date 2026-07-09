from axiom_ops.evaluation.phase7_report import build_phase7_report


def result(
    scenario_id: str,
    passed: bool,
    metrics_match: bool,
    recovery_match: bool,
) -> dict:
    return {
        "run_id": f"{scenario_id}-run",
        "scenario_id": scenario_id,
        "passed": passed,
        "artifact_directory": f"artifacts/lab/{scenario_id}",
        "evaluation": {
            "status_match": True,
            "latency_match": True,
            "recovery_match": recovery_match,
            "metrics_match": metrics_match,
            "average_fault_latency_ms": 123.4,
            "observed_statuses": [503],
        },
    }


def test_phase7_report_computes_closed_loop_and_ablation_rates() -> None:
    report = build_phase7_report(
        [
            result("full", True, True, True),
            result("missing_metrics", False, False, True),
            result("missing_recovery", False, True, False),
        ]
    )

    assert report["scenario_count"] == 3
    assert report["metrics"]["closed_loop_pass_rate"] == 0.3333
    assert report["metrics"]["prometheus_evidence_coverage"] == 0.6667
    assert report["metrics"]["recovery_verification_rate"] == 0.6667
    assert report["ablations"]["without_prometheus_evidence_gate"]["passed"] == 2
    assert report["ablations"]["without_recovery_verification_gate"]["passed"] == 2
