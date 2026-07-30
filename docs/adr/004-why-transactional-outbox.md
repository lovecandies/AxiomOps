# ADR 004：为何通过 Transactional Outbox 发布 Incident 工作

## 背景

向 MySQL 写入 Incident 与向 RocketMQ 发布消息属于两个独立故障域；双写可能丢失工作或产生不一致。

## 决策

在同一数据库事务内保存 Incident 事件和 Outbox 记录，再通过 Relay 重试投递到 RocketMQ，消费者保持幂等。

## 影响

系统选择最终投递，而非跨系统同步事务。作为交换，已持久化的 Incident 可恢复，调查分发也可审计。
