from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter, sleep
from typing import Any
from uuid import uuid4

import httpx

from axiom_ops.lab.scenarios import ScenarioDefinition, write_json


ORDER_PATH = "/orders/demo-sku"
FAILURE_QUERY = (
    "sum(axiomops_lab_downstream_requests_total"
    '{service="order-service",status!="success"})'
)
DURATION_QUERY = (
    "sum(axiomops_lab_http_request_duration_seconds_sum"
    '{service="order-service",path="/orders/{sku}"})'
)


def collect_requests(
    client: httpx.Client,
    order_base_url: str,
    count: int,
) -> list[dict[str, Any]]:
    observations = []
    for index in range(count):
        started = perf_counter()
        response = client.get(f"{order_base_url}{ORDER_PATH}")
        duration_ms = round((perf_counter() - started) * 1000, 2)
        try:
            body: object = response.json()
        except ValueError:
            body = response.text
        observations.append(
            {
                "index": index,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "body": body,
            }
        )
    return observations


def query_prometheus(
    client: httpx.Client,
    prometheus_url: str,
    query: str,
) -> dict[str, Any]:
    response = client.get(
        f"{prometheus_url}/api/v1/query",
        params={"query": query},
    )
    response.raise_for_status()
    return response.json()


def prometheus_value(payload: dict[str, Any]) -> float:
    results = payload.get("data", {}).get("result", [])
    if not results:
        return 0.0
    return float(results[0]["value"][1])


def wait_for_prometheus_series(
    client: httpx.Client,
    prometheus_url: str,
    query: str,
    timeout_seconds: float,
) -> None:
    deadline = perf_counter() + timeout_seconds
    while perf_counter() < deadline:
        payload = query_prometheus(client, prometheus_url, query)
        if payload.get("data", {}).get("result", []):
            return
        sleep(0.5)
    raise RuntimeError("Prometheus did not scrape the lab services in time")


def wait_for_fault_metrics(
    client: httpx.Client,
    prometheus_url: str,
    scenario: ScenarioDefinition,
    baseline_metrics: dict[str, float],
    timeout_seconds: float,
) -> dict[str, float]:
    deadline = perf_counter() + timeout_seconds
    observed = {
        "active_fault": 0.0,
        "downstream_failures": 0.0,
        "order_duration_seconds": 0.0,
    }
    while perf_counter() < deadline:
        observed = {
            "active_fault": prometheus_value(
                query_prometheus(
                    client,
                    prometheus_url,
                    (
                        "axiomops_lab_fault_mode"
                        f'{{service="inventory-service",mode="{scenario.fault.mode}"}}'
                    ),
                )
            ),
            "downstream_failures": prometheus_value(
                query_prometheus(client, prometheus_url, FAILURE_QUERY)
            ),
            "order_duration_seconds": prometheus_value(
                query_prometheus(client, prometheus_url, DURATION_QUERY)
            ),
        }
        if scenario.fault.mode == "latency":
            minimum_delta = (
                scenario.expected.minimum_average_latency_ms
                * scenario.request_count
                / 1000
            )
            signal_ready = (
                observed["order_duration_seconds"]
                - baseline_metrics["order_duration_seconds"]
                >= minimum_delta
            )
        else:
            signal_ready = (
                observed["downstream_failures"]
                - baseline_metrics["downstream_failures"]
                >= scenario.request_count
            )
        if observed["active_fault"] == 1.0 and signal_ready:
            return observed
        sleep(0.5)
    return observed


def evaluate_observations(
    scenario: ScenarioDefinition,
    fault_requests: list[dict[str, Any]],
    recovery_requests: list[dict[str, Any]],
    metric_deltas: dict[str, float] | None = None,
) -> dict[str, Any]:
    statuses = [request["status"] for request in fault_requests]
    durations = [request["duration_ms"] for request in fault_requests]
    average_latency_ms = round(mean(durations), 2) if durations else 0.0
    status_match = bool(statuses) and all(
        status in scenario.expected.statuses for status in statuses
    )
    latency_match = (
        average_latency_ms >= scenario.expected.minimum_average_latency_ms
    )
    recovery_match = bool(recovery_requests) and all(
        request["status"] == 200 for request in recovery_requests
    )
    metrics_match = True
    if metric_deltas is not None:
        active_fault_match = metric_deltas.get("active_fault", 0.0) == 1.0
        if scenario.fault.mode == "latency":
            minimum_duration_delta = (
                scenario.expected.minimum_average_latency_ms
                * scenario.request_count
                / 1000
            )
            signal_match = (
                metric_deltas.get("order_duration_seconds", 0.0)
                >= minimum_duration_delta
            )
        else:
            signal_match = (
                metric_deltas.get("downstream_failures", 0.0)
                >= scenario.request_count
            )
        metrics_match = active_fault_match and signal_match
    return {
        "passed": status_match and latency_match and recovery_match and metrics_match,
        "status_match": status_match,
        "latency_match": latency_match,
        "recovery_match": recovery_match,
        "metrics_match": metrics_match,
        "average_fault_latency_ms": average_latency_ms,
        "observed_statuses": statuses,
    }


def run_scenario(
    scenario: ScenarioDefinition,
    artifact_root: Path,
    order_base_url: str = "http://127.0.0.1:18001",
    inventory_base_url: str = "http://127.0.0.1:18002",
    prometheus_url: str = "http://127.0.0.1:19090",
    scrape_timeout_seconds: float = 15.0,
) -> tuple[Path, dict[str, Any]]:
    run_id = (
        f"{scenario.scenario_id}-"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-"
        f"{uuid4().hex[:8]}"
    )
    artifact_directory = artifact_root / run_id
    artifact_directory.mkdir(parents=True, exist_ok=False)

    fault_requests: list[dict[str, Any]] = []
    recovery_requests: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    execution_error: str | None = None

    with httpx.Client(timeout=5.0) as client:
        try:
            client.post(f"{inventory_base_url}/admin/faults/reset").raise_for_status()
            baseline = collect_requests(client, order_base_url, 2)
            if not all(request["status"] == 200 for request in baseline):
                raise RuntimeError("lab baseline is not healthy")
            wait_for_prometheus_series(
                client,
                prometheus_url,
                DURATION_QUERY,
                scrape_timeout_seconds,
            )
            baseline_metrics = {
                "downstream_failures": prometheus_value(
                    query_prometheus(client, prometheus_url, FAILURE_QUERY)
                ),
                "order_duration_seconds": prometheus_value(
                    query_prometheus(client, prometheus_url, DURATION_QUERY)
                ),
            }

            client.post(
                f"{inventory_base_url}/admin/faults",
                json=scenario.fault.model_dump(),
            ).raise_for_status()
            fault_requests = collect_requests(
                client,
                order_base_url,
                scenario.request_count,
            )

            observed_metrics = wait_for_fault_metrics(
                client,
                prometheus_url,
                scenario,
                baseline_metrics,
                scrape_timeout_seconds,
            )
            metrics = {
                "baseline": baseline_metrics,
                "observed": observed_metrics,
                "delta": {
                    "active_fault": observed_metrics["active_fault"],
                    "downstream_failures": round(
                        observed_metrics["downstream_failures"]
                        - baseline_metrics["downstream_failures"],
                        6,
                    ),
                    "order_duration_seconds": round(
                        observed_metrics["order_duration_seconds"]
                        - baseline_metrics["order_duration_seconds"],
                        6,
                    ),
                },
            }
        except Exception as exc:  # The failure is persisted in result.json.
            execution_error = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                client.post(
                    f"{inventory_base_url}/admin/faults/reset"
                ).raise_for_status()
                recovery_requests = collect_requests(client, order_base_url, 3)
            except Exception as exc:
                if execution_error is None:
                    execution_error = f"{type(exc).__name__}: {exc}"

    evaluation = evaluate_observations(
        scenario,
        fault_requests,
        recovery_requests,
        metrics.get("delta") if metrics else None,
    )
    if execution_error is not None:
        evaluation["passed"] = False
    result = {
        "run_id": run_id,
        "scenario_id": scenario.scenario_id,
        "passed": evaluation["passed"],
        "execution_error": execution_error,
        "evaluation": evaluation,
        "artifact_directory": str(artifact_directory),
    }

    write_json(artifact_directory / "ground-truth.json", scenario.model_dump())
    write_json(
        artifact_directory / "requests.json",
        {
            "fault": fault_requests,
            "recovery": recovery_requests,
        },
    )
    write_json(artifact_directory / "metrics.json", metrics)
    write_json(artifact_directory / "result.json", result)
    return artifact_directory, result
