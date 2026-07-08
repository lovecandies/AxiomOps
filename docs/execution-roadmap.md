# AxiomOps 执行路线

1. Phase 0：项目骨架与健康检查。`completed`
2. Phase 1：可重复微服务故障实验，保存 Ground Truth。`completed`
3. Phase 2：MySQL + Outbox + RocketMQ 可靠 Incident 控制面。`completed`
4. Phase 3：Typed Tools 与 Evidence。`completed`
5. Phase 4：LangGraph 多 Agent 只读 RCA。`completed`
6. Phase 5：Redis Checkpoint、上下文压缩、Qdrant 记忆。
7. Phase 6：权限、人工审批、Sandbox、恢复验证与回滚。
8. Phase 7：OpenTelemetry/Prometheus、故障集与消融实验。
9. Phase 8：React 控制台与五分钟演示。
10. Phase 9：README、真实量化简历与面试题库。

每个 Phase 必须先定义黑盒完成条件，上一阶段未通过验证时不进入下一阶段。
