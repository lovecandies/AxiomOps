# Phase 1 验证记录

- 日期：2026-07-08
- 环境：Docker Desktop 29.5.2、Docker Compose 5.1.4
- 实验拓扑：`order-service -> inventory-service`
- Prometheus 抓取周期：1 秒

## 自动化检查

```text
pytest: 9 passed
compileall: passed
docker compose config: passed
```

测试依赖层仍有一条 FastAPI/Starlette TestClient 弃用提示，不影响项目代码与测试结果。

## 容器黑盒检查

```text
inventory-service: healthy
order-service: healthy
prometheus: running
Prometheus targets up: 2
```

## Ground Truth 场景

| 场景 | 请求结果 | Prometheus 证据 | 恢复 | 结果 |
|---|---|---|---|---|
| `inventory_error_rate` | 5/5 返回 503 | 下游失败计数 +5 | 3/3 返回 200 | passed |
| `inventory_latency` | 5/5 返回 200，平均 816.09ms | Order 总耗时 +4.067323s | 3/3 返回 200 | passed |
| `inventory_unavailable` | 5/5 返回 503 | 下游失败计数 +5 | 3/3 返回 200 | passed |

三个场景的 `active_fault` Prometheus 指标均为 `1.0`，说明请求表现与监控证据同时命中。

## 最新验证 Run ID

```text
inventory_error_rate-20260708T075158Z-695db857
inventory_latency-20260708T075202Z-0b64243f
inventory_unavailable-20260708T075211Z-ca50e3f8
```

每个 Run 均生成：

```text
ground-truth.json
requests.json
metrics.json
result.json
```

## 已修复的环境问题

- Windows 非 ASCII 项目路径会导致 BuildKit gRPC header 错误。
- `scripts/start_lab.ps1` 使用经典构建器规避该问题。
- `.dockerignore` 将构建上下文从约 16MB 降至约 11KB。

## 阶段结论

Phase 1 已满足“故障可重复、指标可观察、Ground Truth 可保存、恢复可验证”的完成条件，可以进入 Phase 2。
