# Phase 5 蓝图：Checkpoint、上下文压缩与已验证记忆

## 目标

让只读 RCA 工作流具备可恢复执行、可审计的上下文预算，以及只来源于已验证历史 RCA 的相似案例记忆。

## 明确边界

- MySQL 继续作为 Incident、Agent Run、Evidence 和 RCA 的最终事实源。
- Redis 只保存 LangGraph Checkpoint；同一 `run_id` 同时作为 `thread_id`。
- Qdrant 只保存 `APPROVED` RCA 的可重建向量索引，索引失败不得篡改已提交 RCA。
- 历史记忆只能作为 Commander 的非证据提示，不能被引用、不能提高置信度、不能绕过 Citation Guard。
- Evidence Capsule 由确定性代码生成，必须保留 Evidence ID、类型、来源、时间和 SHA-256；不使用 LLM 压缩。
- 本阶段不实现恢复执行、人工审批、Sandbox、前端或新的 Agent。
- DeepSeek 真实 API 验证因尚未提供 Key，继续标记为待完成。

## 运行流

1. 创建 RCA Run，并在 MySQL 固化本次 Evidence ID 快照。
2. 校验原始 Evidence 文件哈希，生成有字符预算的 Evidence Capsule。
3. 从 Qdrant 查询同服务的历史已验证 RCA，排除当前 Incident。
4. 使用 `run_id` 作为 Redis Checkpoint `thread_id` 启动 LangGraph。
5. 节点异常时 MySQL 标记 `FAILED`，Redis 保留已完成节点状态。
6. 调用 Resume 接口后，将同一 Run 恢复为 `RUNNING`，从 Redis 最新 Checkpoint 续跑。
7. Citation Guard 与独立 Verifier 通过后，MySQL 原子提交 RCA。
8. 已提交且 `APPROVED` 的 RCA 以可重建形式写入 Qdrant。

## 数据与目录改动

- `ops-control-plane/mysql/004_phase5.sql`：保存每次 Run 的上下文压缩清单。
- `context_compaction.py`：确定性 Evidence Capsule 与预算统计。
- `checkpoint.py`：RedisSaver 生命周期与初始化。
- `rca_memory.py`：FastEmbed + Qdrant 的已验证历史记忆。
- `rca_graph.py`：接收 Checkpointer 和只给 Commander 可见的历史提示。
- `rca_runtime.py`：启动、失败、同 Run Resume 和成功后的记忆索引。
- `POST /rca-runs/{run_id}/resume`：只允许恢复 `FAILED` Run。

## 黑盒完成条件

1. 在 Synthesizer 人为失败后，同一 `run_id` 能从 Redis 继续并完成，已完成节点不重复调用。
2. Redis 容器重启后仍能恢复该 Run。
3. Capsule 总量不超过配置预算，且每条 Evidence 的 ID 与 SHA-256 完整保留。
4. `APPROVED` RCA 能被相似 Incident 召回；`REJECTED` 和 `FAILED` Run 不进入 Qdrant。
5. Qdrant 重启后召回结果仍存在。
6. 全量自动化测试、Compose 配置检查和 Phase 5 黑盒脚本通过。
