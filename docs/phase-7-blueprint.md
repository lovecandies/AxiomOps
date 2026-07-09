# Phase 7：OpenTelemetry/Prometheus、故障集与消融实验蓝图

## 目标

把 AxiomOps 从“能跑通闭环”推进到“能被量化评估”。本阶段不评估真实 DeepSeek 质量，因为尚未提供 Key；只评估工程闭环是否具备可观测性、可追踪性和可重复实验数据。

## 可观测性范围

控制面新增：

- `/metrics`：Prometheus 格式指标。
- `X-AxiomOps-Trace-Id`：每个 API 响应返回 trace id。
- `traceparent`：兼容 W3C Trace Context 的 trace header。

Prometheus 指标包括：

| 指标 | 含义 |
| --- | --- |
| `axiomops_control_http_requests_total` | 控制面 HTTP 请求计数 |
| `axiomops_control_http_request_duration_seconds` | 控制面 HTTP 请求耗时 |
| `axiomops_control_business_events_total` | Incident、RCA、Recovery 等业务事件计数 |

Lab Prometheus 配置增加 `axiomops-control-plane` scrape job，用于采集控制面指标。

## Trace 设计

如果请求带入合法 `traceparent`，控制面复用其中的 trace id；否则生成新的 trace id。

响应会返回：

```text
X-AxiomOps-Trace-Id: <trace-id>
traceparent: 00-<trace-id>-<span-id>-01
```

这不是完整分布式 Trace 后端，但已经满足面试里最关键的工程点：跨 API 调用可以用同一个 trace id 关联日志、请求和执行结果。

## 故障集

复用 Phase 1 的三个 Ground Truth 场景：

1. `inventory_latency`
2. `inventory_error_rate`
3. `inventory_unavailable`

每个场景保留：

- 故障注入参数。
- 请求状态和延迟。
- Prometheus 指标 delta。
- 恢复请求结果。
- `result.json` 黑盒判定。

## 消融实验

Phase 7 报告包含三组对比：

| 实验 | 门禁 |
| --- | --- |
| `full_pipeline` | 请求结果 + Prometheus 证据 + 恢复验证 |
| `without_prometheus_evidence_gate` | 移除 Prometheus 证据门禁 |
| `without_recovery_verification_gate` | 移除恢复验证门禁 |

这样可以回答面试中的关键问题：

- 为什么不能只看 HTTP 状态？
- 为什么 RCA 通过不代表故障真正恢复？
- 为什么需要可观测指标作为 Evidence？

## 黑盒完成条件

1. `/health` 响应返回 `X-AxiomOps-Trace-Id` 和 `traceparent`。
2. `/metrics` 返回控制面 Prometheus 指标。
3. Prometheus 可以 scrape 控制面和 Lab 服务。
4. `scripts/run_phase7_evaluation.py` 可以跑完整故障集。
5. 评测报告保存到 `artifacts/evaluations/phase7-*.json`。
6. 报告包含 closed-loop pass rate、Prometheus evidence coverage、recovery verification rate 和 ablation 对比。
