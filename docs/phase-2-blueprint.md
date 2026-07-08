# Phase 2：可靠 Incident 控制面蓝图

## 阶段目标

把一次告警可靠地转成可追踪的 Incident，并通过 Transactional Outbox 投递“开始调查”命令。MySQL 是唯一事实源；RocketMQ 只负责业务调度。Phase 2 不接入 Agent、Redis、Qdrant 或前端。

## 最小业务闭环

```text
POST /incidents
  -> MySQL 同一事务写 incidents + incident_events + outbox_events
  -> Outbox Relay 租约待发送事件
  -> RocketMQ: incident.investigation.requested
  -> 幂等消费者写 processed_messages
  -> Incident: RECEIVED -> INVESTIGATION_QUEUED
  -> GET /incidents/{id} 可观察最终状态与审计事件
```

## 关键决策

- `Idempotency-Key` 是创建 Incident 的业务幂等键；相同键和相同请求返回原 Incident，不同请求返回 `409`。
- Outbox Relay 不持有数据库事务发送网络消息。它先用短事务申请租约，再发送，最后标记成功。
- Relay 若在“发送成功、落库失败”之间崩溃，允许重复投递；消费者以 Outbox `event_id` 去重。
- 消费确认只发生在 MySQL 状态推进与幂等记录同一事务提交之后。
- 状态流转使用乐观版本字段和显式允许列表，不实现通用工作流引擎。

## 数据表

- `incidents`：Incident 当前状态与版本。
- `incident_events`：只追加的状态审计记录。
- `outbox_events`：消息内容、租约、重试次数和投递结果。
- `processed_messages`：消费组与事件 ID 的唯一幂等记录。

## 目录边界

```text
src/axiom_ops/control_plane/  # API、事务仓储、Relay、Consumer、RocketMQ 适配
ops-control-plane/            # MySQL/RocketMQ/应用容器与初始化 SQL
tests/control_plane/          # 状态机、事务和接口黑盒测试
scripts/                      # 启停与 Phase 2 黑盒验证入口
```

## 黑盒完成条件

1. 首次创建返回 `201`；相同幂等键重放不产生第二条 Incident 或 Outbox。
2. Outbox 最终进入 `PUBLISHED`，Incident 最终进入 `INVESTIGATION_QUEUED`。
3. 同一事件重复消费不会生成重复状态事件。
4. RocketMQ 暂停期间 Incident 仍成功落库；恢复后积压 Outbox 自动投递。
5. 重启 API、Relay 或 Consumer 后，MySQL 中的事实与审计链保持一致。
