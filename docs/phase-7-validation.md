# Phase 7 验证记录

## 单元与配置验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests\control_plane\test_observability.py tests\evaluation\test_phase7_report.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall -q src scripts
docker compose -f ops-control-plane\docker-compose.yml config --quiet
docker compose -f ops-lab\docker-compose.yml config --quiet
```

## 控制面可观测性黑盒验证

启动 Lab 和控制面：

```powershell
.\scripts\start_lab.ps1
.\scripts\start_control_plane.ps1
```

检查 trace header：

```powershell
Invoke-WebRequest http://127.0.0.1:18000/health
```

应能看到：

```text
X-AxiomOps-Trace-Id: <trace-id>
traceparent: 00-<trace-id>-<span-id>-01
```

检查控制面指标：

```powershell
Invoke-RestMethod http://127.0.0.1:18000/metrics
```

应包含：

```text
axiomops_control_http_requests_total
axiomops_control_http_request_duration_seconds
axiomops_control_business_events_total
```

## 2026-07-09 实际可观测性验证结果

Trace Header：

```json
{
  "Status": 200,
  "TraceId": "077e07b26a924c36b83abb68e91a7e63",
  "TraceParent": "00-077e07b26a924c36b83abb68e91a7e63-c16514d7d4d94a6d-01"
}
```

控制面 `/metrics`：

```text
control-plane metrics: passed
```

Prometheus 抓取控制面：

```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "__name__": "up",
          "instance": "host.docker.internal:18000",
          "job": "axiomops-control-plane"
        },
        "value": [1783568971.036, "1"]
      }
    ]
  }
}
```

## 故障集与消融实验

```powershell
.\.venv\Scripts\python.exe scripts\run_phase7_evaluation.py
```

成功后会输出并保存：

```text
artifacts/evaluations/phase7-<timestamp>.json
```

报告关键字段：

- `metrics.closed_loop_pass_rate`
- `metrics.prometheus_evidence_coverage`
- `metrics.recovery_verification_rate`
- `ablations.full_pipeline`
- `ablations.without_prometheus_evidence_gate`
- `ablations.without_recovery_verification_gate`

## 2026-07-09 实际故障集评测结果

执行：

```powershell
.\.venv\Scripts\python.exe scripts\run_phase7_evaluation.py
```

报告路径：

```text
artifacts/evaluations/phase7-20260709T034947Z.json
```

汇总结果：

```json
{
  "scenario_count": 3,
  "metrics": {
    "closed_loop_pass_rate": 1.0,
    "prometheus_evidence_coverage": 1.0,
    "recovery_verification_rate": 1.0
  }
}
```

场景结果：

| 场景 | Run ID | 结果 | 关键观测 |
| --- | --- | --- | --- |
| `inventory_error_rate` | `inventory_error_rate-20260709T034939Z-7f6392b9` | passed | 故障期 5 次均为 `503` |
| `inventory_latency` | `inventory_latency-20260709T034941Z-be134201` | passed | 平均故障延迟 `812.74ms` |
| `inventory_unavailable` | `inventory_unavailable-20260709T034946Z-83b640eb` | passed | 故障期 5 次均为 `503` |

消融报告中的三个分支均为 `3/3`，但这不代表可删除门禁。它说明在本次正常数据下门禁都通过；消融字段用于记录如果移除 Prometheus 证据或恢复验证，会失去哪些工程保证。

## 当前边界

- 本阶段没有把 trace 数据发送到 Jaeger/Tempo，采用 W3C Trace Context header 作为最小可追踪实现。
- DeepSeek 真实质量评估仍未执行；Phase 7 只评估可重复故障实验和工程闭环。
- 消融实验比较的是确定性评测门禁，不是模型推理能力。
