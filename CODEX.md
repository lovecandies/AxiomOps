# AxiomOps 协作约束

## 项目目标

AxiomOps 是一个面向微服务故障场景的证据驱动多 Agent 智能诊断与安全恢复系统。所有实现都服务于 Java 后端与 Agent 开发岗位面试，功能必须可演示、可测试、可量化。

## 固定技术栈

- Agent Runtime：Python、FastAPI、LangGraph、DeepSeek
- 基础设施：MySQL、Redis、RocketMQ、Qdrant
- 观测与实验：Prometheus、OpenTelemetry、Docker Compose
- 前端：React、TypeScript、SSE、Lucide Icons

明确不使用 PostgreSQL、pgvector、Kafka、Neo4j、Spring AI 或额外多 Agent 框架。

## 架构边界

- MySQL 是 Incident、Agent Run、Evidence 元数据、RCA、审批、执行、工作流快照和 Outbox 的最终事实源。
- Redis 只保存 Checkpoint、锁、进度、预算、限流、缓存和短期记忆。
- RocketMQ 只承载业务级启动、恢复和执行调度，不承载 Agent 自由聊天。
- Qdrant 保存可重建的 Runbook、服务知识和已验证历史 Incident 向量索引。
- 原始日志、指标响应、Trace 与执行产物保存在文件系统。
- Agent 负责不确定性推理；审批、策略、执行、幂等、重试、SLO 判断和回滚必须是确定性节点。

## 开发纪律

- 严格按 Phase 推进；当前 Phase 未完成时不提前铺设后续抽象。
- 先构建带 Ground Truth 的故障实验，再开发 Agent。
- 只实现当前目标所需的最少代码，不同时维护多语言版本。
- 新功能必须定义用户可见的黑盒验证目标。
- 简历中的数字只能来自保存的评测报告。
- 上游代码统一来自 Git 远程 `upstream/main`，按 Phase 迁移并记录实质改造。
- 不复制参考仓库的宣传指标，简历只描述自己完成和验证的改造。
- 写操作默认拒绝；任何恢复操作都必须经过权限检查、风险策略和必要的人工审批。

## 已完成阶段

- Phase 0：项目骨架、配置、应用工厂、健康检查和基础测试。
- Phase 1：双服务故障实验、Prometheus、三个 Ground Truth 场景和实验产物。
- Phase 2：MySQL Incident 控制面、Transactional Outbox、RocketMQ 调度和幂等消费。
- Phase 3：白名单 Typed Tools、不可变 Evidence 元数据、持久化原始内容和哈希校验。
- Phase 4：LangGraph 动态多 Agent、DeepSeek 结构化适配、Evidence 引用安全门和只读 RCA。

## 下一阶段：Phase 5

Phase 5 只实现 Redis Checkpoint、上下文压缩和 Qdrant 记忆。恢复执行和前端仍不得提前引入。

Phase 4 的图结构、安全门与验证结果分别保存在 `docs/phase-4-blueprint.md` 和 `docs/phase-4-validation.md`。

Phase 3 的工具白名单、Evidence 契约、取舍与验证结果分别保存在 `docs/phase-3-blueprint.md` 和 `docs/phase-3-validation.md`。

Phase 2 的事务边界、状态机、消息语义和验证结果分别保存在 `docs/phase-2-blueprint.md` 与 `docs/phase-2-validation.md`。
