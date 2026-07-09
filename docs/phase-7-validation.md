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

## 当前边界

- 本阶段没有把 trace 数据发送到 Jaeger/Tempo，采用 W3C Trace Context header 作为最小可追踪实现。
- DeepSeek 真实质量评估仍未执行；Phase 7 只评估可重复故障实验和工程闭环。
- 消融实验比较的是确定性评测门禁，不是模型推理能力。
