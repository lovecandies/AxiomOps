# Phase 2 验证记录

- 日期：2026-07-08
- 环境：Docker Desktop 29.5.2、Docker Compose 5.1.4
- 基础设施：MySQL 8.4、RocketMQ 5.3.2 + Proxy、Python SDK 5.1.1

## 自动化检查

```text
pytest: 13 passed
compileall: passed
docker compose config: passed
```

测试依赖层有一条 FastAPI/Starlette TestClient 弃用提示，不影响项目代码与测试结果。

## 正常消息闭环

```text
首次 POST /incidents: 201
相同 Idempotency-Key 重放: 200，同一 Incident ID
Outbox: PENDING -> SENDING -> PUBLISHED
Incident: RECEIVED -> INVESTIGATION_QUEUED
Outbox attempts: 1
```

验证 Incident：`c19e204a-3ad6-4831-946c-750d16a3e29d`。

## RocketMQ 中断恢复

主动停止 Proxy 后创建 Incident：

```text
HTTP: 201
Incident: RECEIVED
Outbox: 保留待发送事件
```

恢复 Proxy 后：

```text
Incident: INVESTIGATION_QUEUED
Outbox: PUBLISHED
delivery attempts: 3
```

验证 Incident：`9e85646f-5eb5-415f-8047-10ca8a459800`。

## 幂等与持久性

- 对同一 Outbox `event_id` 再次执行消费，返回 `False`。
- 重复消费前后均为 2 条 Incident 审计事件、1 条消费幂等记录。
- 重启 MySQL、API、Relay 与 Consumer 后，原 Incident 仍为版本 2、`INVESTIGATION_QUEUED / PUBLISHED`。

## 阶段结论

Phase 2 已满足“事实可靠落库、消息最终投递、重复消费无副作用、进程重启不丢状态”的完成条件，可以进入 Phase 3。
