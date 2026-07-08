# AxiomOps 架构基线

## 目标闭环

```text
告警 -> 调查 -> Evidence -> RCA -> 独立验证 -> 策略 -> 审批 -> Sandbox 恢复 -> SLO 验证/回滚
```

## Agent Runtime

- Incident Commander
- Metrics Investigator
- Logs/Trace Investigator
- Change Investigator
- RCA Synthesizer
- Independent Verifier

审批、策略、执行、幂等、重试、SLO 判断和回滚是确定性工作流节点。

## 数据职责

| 组件 | 职责 |
|---|---|
| MySQL | Incident、Agent Run、Evidence 元数据、RCA、审批、执行、工作流快照和 Outbox |
| Redis | LangGraph Checkpoint、锁、进度、预算、限流、缓存和短期记忆 |
| RocketMQ | 业务级启动、恢复和执行调度 |
| Qdrant | Runbook、服务知识和已验证历史 Incident 的可重建向量索引 |
| 文件系统 | 原始日志、指标响应、Trace 和执行产物 |

## 参考模式

- DeerFlow：Lead Agent、动态 Sub-Agent、Task Capsule、Skills 渐进加载、Sandbox、上下文压缩和长期记忆。
- Claude Code：Plan -> Tool -> Observe、独立子上下文、工具权限、Pre/Post Hooks、预算和会话恢复。
- LangGraph：StateGraph、动态并行、Interrupt、Checkpoint 和 Resume，是唯一 Agent 编排依赖。

## 当前实现

Phase 1 已实现可重复故障实验。Phase 2 已增加可靠 Incident 控制面：

```text
POST /incidents
  -> MySQL: Incident + Audit Event + Outbox（同一事务）
  -> Outbox Relay（短租约、失败重试）
  -> RocketMQ 5 Proxy
  -> 幂等 Consumer
  -> INVESTIGATION_QUEUED
```

- 两个 FastAPI 实验服务共用一个版本化镜像。
- Prometheus 每秒采集 HTTP、延迟、下游状态和故障模式。
- 场景运行器在注入前后计算指标差值，并在恢复后检查正常请求。
- 每次运行保存 Ground Truth、请求、指标和结果。
- MySQL 保存 Incident 当前状态、只追加审计事件、Outbox 与消费幂等记录。
- RocketMQ 不可用时 API 仍可落库，恢复后 Relay 自动补发。
- 消费端只在 MySQL 事务提交后确认消息，重复消息不重复推进状态。
- Phase 3 增加 Prometheus Metrics 与服务 Health 两个白名单 Typed Tool。
- Tool Observation 以排他文件写入保存，MySQL 只保存可检索元数据与 SHA-256。
- Evidence 表由 Trigger 禁止更新和删除，内容读取前必须通过哈希校验。
- Phase 4 使用 LangGraph `StateGraph + Send` 动态并行三个 Investigator。
- 每个 Investigator 只接收按角色过滤的 Evidence 子上下文。
- RCA 必须先通过确定性引用校验，再由 Independent Verifier 审核。
- 只有 `APPROVED` Run 生成不可变 RCA Report；失败与拒绝均保留审计 Run。
- Phase 5 使用 MySQL Run ID 作为 Redis Checkpoint `thread_id`，失败后在同一 Run 上续跑。
- Evidence 先转换为确定性 Capsule，保留身份与哈希并执行上下文字符预算。
- Qdrant 只索引已验证 RCA；召回结果仅作为 Commander 的不可引用历史提示。

恢复动作、人工审批、Sandbox 和回滚将在 Phase 6 实现。
