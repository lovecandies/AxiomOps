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

The current comparison uses the same three scenarios with three repeats each.

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

## Agent 安全性评测（Phase 12）

Agent 安全性报告分别度量三类失败模式。指标不从模型生成文本中推断；每个案例均记录可观察、经复核的结果及对应工件路径。

| 指标 | 期望方向 | 含义 |
| --- | --- | --- |
| 缺失证据拒答率 | 越高越好 | Agent 请求补充 Evidence，而非强行断言根因。 |
| 历史 Memory 误导率 | 越低越好 | 不将历史 RCA 当作当前 Incident 的事实。 |
| 工具选择准确率 | 越高越好 | Agent 从白名单中选中 Ground Truth 指定的下一项诊断工具。 |

使用经复核的案例记录生成报告：

```powershell
.\.venv\Scripts\python.exe scripts\run_agent_safety_evaluation.py artifacts\evaluations\agent-safety-cases.json --output artifacts\evaluations\agent-safety-report.json
```

在 Phase 10 合并前，工具选择案例仅是评测数据契约；在受控 Tool Selection Runtime 生成真实案例之前，不得据此指标作任何 Benchmark 声称。
