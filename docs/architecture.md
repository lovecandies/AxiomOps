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

Phase 0 只有 FastAPI 配置、应用工厂、健康检查和自动化测试。其余组件按路线逐步加入。
