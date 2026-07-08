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

## 当前阶段：Phase 0

本阶段只允许完成：

1. 项目骨架。
2. 配置加载。
3. FastAPI 应用工厂。
4. Liveness/Readiness 健康检查。
5. 最小自动化测试与本地启动文档。

MySQL、Redis、RocketMQ、Qdrant、LangGraph、DeepSeek、故障实验和前端均不在本阶段实现。
