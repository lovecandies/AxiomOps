from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def build_phase7_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    summaries = []
    full_passed = 0
    request_only_passed = 0
    no_recovery_gate_passed = 0
    metrics_evidence_count = 0
    recovery_verified_count = 0

    for result in results:
        evaluation = result["evaluation"]
        scenario_passed = bool(result["passed"])
        request_only = bool(
            evaluation["status_match"]
            and evaluation["latency_match"]
            and evaluation["recovery_match"]
        )
        no_recovery_gate = bool(
            evaluation["status_match"]
            and evaluation["latency_match"]
            and evaluation["metrics_match"]
        )
        full_passed += int(scenario_passed)
        request_only_passed += int(request_only)
        no_recovery_gate_passed += int(no_recovery_gate)
        metrics_evidence_count += int(evaluation["metrics_match"])
        recovery_verified_count += int(evaluation["recovery_match"])
        summaries.append(
            {
                "scenario_id": result["scenario_id"],
                "run_id": result["run_id"],
                "passed": scenario_passed,
                "average_fault_latency_ms": evaluation["average_fault_latency_ms"],
                "status_match": evaluation["status_match"],
                "metrics_match": evaluation["metrics_match"],
                "recovery_match": evaluation["recovery_match"],
                "observed_statuses": evaluation["observed_statuses"],
                "artifact_directory": result["artifact_directory"],
            }
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "scenario_count": total,
        "scenarios": summaries,
        "metrics": {
            "closed_loop_pass_rate": _rate(full_passed, total),
            "prometheus_evidence_coverage": _rate(metrics_evidence_count, total),
            "recovery_verification_rate": _rate(recovery_verified_count, total),
        },
        "ablations": {
            "full_pipeline": {
                "passed": full_passed,
                "total": total,
                "pass_rate": _rate(full_passed, total),
                "gates": ["request_outcome", "prometheus_evidence", "recovery_verification"],
            },
            "without_prometheus_evidence_gate": {
                "passed": request_only_passed,
                "total": total,
                "pass_rate": _rate(request_only_passed, total),
                "risk": "HTTP-only evaluation cannot prove the fault signal was observable.",
            },
            "without_recovery_verification_gate": {
                "passed": no_recovery_gate_passed,
                "total": total,
                "pass_rate": _rate(no_recovery_gate_passed, total),
                "risk": "Diagnosis-only evaluation can pass without proving the service recovered.",
            },
        },
    }
