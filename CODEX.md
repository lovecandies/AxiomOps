# AxiomOps 协作基线

## 项目目标

AxiomOps 是一个面向微服务故障场景的证据驱动多 Agent 智能诊断与安全恢复系统。所有实现都服务于 Java 后端开发与 Agent 开发岗位面试，功能必须可演示、可测试、可量化。

当前已完成到 Phase 7。后续开发必须基于现有闭环继续推进，不要回退到早期 PostgreSQL、Kafka、Neo4j、Spring AI 或多 Agent 框架叠加方案。

## 固定技术栈

- Agent Runtime：Python、FastAPI、LangGraph、DeepSeek Adapter
- 基础设施：MySQL、Redis、RocketMQ、Qdrant
- 观测与实验：Prometheus、Trace Header、Docker Compose
- 前端规划：React、TypeScript、SSE、Lucide Icons

## 架构边界

- MySQL 是 Incident、Evidence 元数据、Agent Run、RCA、审批、执行审计、上下文 Capsule 和 Outbox 的最终事实源。
- Redis 只保存 LangGraph Checkpoint 等短期可恢复状态。
- RocketMQ 只承载业务级调度消息，不承载 Agent 自由聊天。
- Qdrant 只保存已验证 RCA 的可重建向量索引。
- 文件系统保存 Evidence 原始 JSON、实验产物和评测报告。
- Agent 负责不确定性推理；审批、策略、执行、幂等、重试、恢复验证和回滚必须是确定性节点。

## 已完成阶段

| Phase | 内容 |
| --- | --- |
| Phase 0 | 项目骨架、配置、应用工厂、健康检查和基础测试 |
| Phase 1 | 双服务故障实验、Prometheus、三个 Ground Truth 场景和实验产物 |
| Phase 2 | MySQL Incident 控制面、Transactional Outbox、RocketMQ 调度和幂等消费 |
| Phase 3 | 白名单 Typed Tools、不可变 Evidence 元数据、持久化原始内容和哈希校验 |
| Phase 4 | LangGraph 多 Agent RCA、DeepSeek 结构化适配、Evidence 引用安全门 |
| Phase 5 | Redis Checkpoint、确定性 Evidence Capsule、Qdrant 已验证记忆 |
| Phase 6 | Commander/Approver/Operator 角色隔离、Sandbox 恢复、验证与回滚 |
| Phase 7 | 控制面 Prometheus 指标、Trace Header、故障集与消融实验 |

## 当前验证基线

最近完整验证结果：

- `pytest`: 39 passed
- `compileall`: passed
- `pip check`: No broken requirements found
- `docker compose config`: lab/control-plane 均通过
- Phase 6 Docker 黑盒：自审批 403、Sandbox 恢复成功、订单链路 200、重复执行幂等
- Phase 7 Docker 黑盒：trace header 返回、控制面 `/metrics` 可用、Prometheus scrape 控制面 `up=1`
- Phase 7 故障集：3/3 场景通过，closed-loop pass rate = 1.0

DeepSeek 真实质量、延迟和成本评测仍未完成；未提供 API Key 前不得把真实模型指标写入简历或文档。

## 开发纪律

1. 先定义黑盒验收，再写实现。
2. 只做当前 Phase 目标要求的最小实现，不提前铺大抽象。
3. 不删除或重构无关历史代码。
4. 新增恢复动作必须经过权限、审批、执行审计、验证和回滚设计。
5. 新增简历数字必须来自 `artifacts/` 中保存的评测报告。
6. 文档必须同步更新 README、architecture、phase blueprint/validation 和完整技术详解。

## 关键文档

- `docs/architecture.md`：最新架构基线。
- `docs/AxiomOps-Phase0-7-完整技术详解.md`：从零到 Phase 7 的完整技术说明。
- `docs/execution-roadmap.md`：阶段路线。
- `docs/phase-6-blueprint.md` / `docs/phase-6-validation.md`：安全恢复。
- `docs/phase-7-blueprint.md` / `docs/phase-7-validation.md`：观测与评测。

## 下一阶段建议

下一阶段默认是 Phase 8：React 控制台与五分钟面试演示。重点应该是把已有闭环可视化，不新增复杂恢复能力。
