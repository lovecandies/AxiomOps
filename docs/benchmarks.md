# Benchmarks

AxiomOps keeps benchmark claims tied to repeatable local fault scenarios.

## Scenario Set

| Scenario | Ground truth |
| --- | --- |
| `inventory_error_rate` | Inventory returns deterministic failures |
| `inventory_latency` | Inventory response latency increases |
| `inventory_unavailable` | Inventory dependency returns unavailable |

## Deterministic Closed Loop

| Metric | Result |
| --- | --- |
| Fault scenarios passed | 3 / 3 |
| Prometheus evidence coverage | 100% |
| Recovery verification rate | 100% |

This validates the backend workflow, evidence collection, and sandbox recovery path.

## Agent Runtime Comparison

The current comparison uses the same three scenarios with three repeats each. A machine-readable summary is available at [benchmarks/agent-comparison-summary.json](benchmarks/agent-comparison-summary.json).

| Metric | Single-agent baseline | Multi-agent graph |
| --- | ---: | ---: |
| Root-cause match | 9 / 9 | 9 / 9 |
| Strict evidence citation coverage | 0 / 9 | 8 / 9 |
| Mean confidence | 0.96 | 0.82 |
| Mean model tokens | 1,268 | 10,555 |
| Mean latency | 3.06s | 20.28s |

## Interpretation

The small deterministic dataset does not show a root-cause accuracy lift. The value of the multi-agent workflow is stricter evidence discipline, role separation, and independent verification. The cost is higher latency and model usage, so the full graph is intended for incidents where traceability matters more than fastest possible response.

## Reproducing

Start the lab and control plane, then run:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase7_evaluation.py
```

Reports are written under the ignored `artifacts/` directory.

For the design rationale behind these metrics, see [Agent Evaluation](agent-evaluation.md).
