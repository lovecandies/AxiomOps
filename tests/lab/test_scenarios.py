from pathlib import Path

from axiom_ops.lab import scenario_runner
from axiom_ops.lab.scenario_runner import evaluate_observations, wait_for_fault_metrics
from axiom_ops.lab.scenarios import load_scenarios


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIRECTORY = ROOT / "ops-lab" / "scenarios"


def test_ground_truth_scenarios_are_valid_and_unique() -> None:
    scenarios = load_scenarios(SCENARIO_DIRECTORY)

    assert len(scenarios) == 3
    assert len({scenario.scenario_id for scenario in scenarios}) == 3
    assert all(scenario.root_cause for scenario in scenarios)
    assert all("reset_fault" in scenario.allowed_actions for scenario in scenarios)


def test_latency_scenario_evaluation_requires_recovery() -> None:
    scenario = next(
        scenario
        for scenario in load_scenarios(SCENARIO_DIRECTORY)
        if scenario.scenario_id == "inventory_latency"
    )
    fault_requests = [
        {"status": 200, "duration_ms": 810.0},
        {"status": 200, "duration_ms": 790.0},
    ]

    passed = evaluate_observations(
        scenario,
        fault_requests,
        [{"status": 200, "duration_ms": 10.0}],
    )
    failed_recovery = evaluate_observations(
        scenario,
        fault_requests,
        [{"status": 503, "duration_ms": 10.0}],
    )

    assert passed["passed"] is True
    assert failed_recovery["passed"] is False


def test_scenario_evaluation_requires_prometheus_evidence() -> None:
    scenario = next(
        scenario
        for scenario in load_scenarios(SCENARIO_DIRECTORY)
        if scenario.scenario_id == "inventory_error_rate"
    )
    fault_requests = [
        {"status": 503, "duration_ms": 10.0}
        for _ in range(scenario.request_count)
    ]
    recovery_requests = [{"status": 200, "duration_ms": 10.0}]

    passed = evaluate_observations(
        scenario,
        fault_requests,
        recovery_requests,
        {
            "active_fault": 1.0,
            "downstream_failures": float(scenario.request_count),
            "order_duration_seconds": 0.1,
        },
    )
    missing_metrics = evaluate_observations(
        scenario,
        fault_requests,
        recovery_requests,
        {
            "active_fault": 0.0,
            "downstream_failures": 0.0,
            "order_duration_seconds": 0.1,
        },
    )

    assert passed["passed"] is True
    assert missing_metrics["passed"] is False
    assert missing_metrics["metrics_match"] is False


def test_fault_metric_collection_polls_until_scrape_contains_signal(monkeypatch) -> None:
    scenario = next(
        scenario
        for scenario in load_scenarios(SCENARIO_DIRECTORY)
        if scenario.scenario_id == "inventory_error_rate"
    )
    failure_values = iter((2.0, 5.0))

    def fake_query(client, prometheus_url, query):
        if "fault_mode" in query:
            value = 1.0
        elif "downstream_requests" in query:
            value = next(failure_values)
        else:
            value = 0.1
        return {"data": {"result": [{"value": [0, str(value)]}]}}

    monkeypatch.setattr(scenario_runner, "query_prometheus", fake_query)
    monkeypatch.setattr(scenario_runner, "sleep", lambda _: None)

    observed = wait_for_fault_metrics(
        object(),
        "http://prometheus",
        scenario,
        {"downstream_failures": 0.0, "order_duration_seconds": 0.0},
        1.0,
    )

    assert observed["active_fault"] == 1.0
    assert observed["downstream_failures"] == 5.0
