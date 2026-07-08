# Phase 5 验证记录

- 日期：2026-07-08
- Checkpoint：LangGraph RedisSaver + Redis 8.2.7 AOF
- 长期记忆：Qdrant 1.18.0
- 生产向量模型：FastEmbed `paraphrase-multilingual-MiniLM-L12-v2`

## 自动化检查

```text
pytest: 29 passed
compileall: passed
docker compose config: passed
control-plane readiness: passed
```

测试依赖层仍有一条 FastAPI/Starlette TestClient 弃用提示，不影响项目代码与结果。

## Redis Checkpoint 与同 Run Resume

验证 Run：`0fb1e755-af9a-4556-a0b9-f1d2b7c3fad0`。

```text
synthetic failure node: synthesize
initial status: FAILED
initial model calls: 5
Redis restart with AOF: passed
resumed status: COMPLETED
same run_id: passed
cumulative model calls: 7
graph_version: phase5-v1
recorded steps: 8
commander: 1
investigators: 3
synthesizer: 1
verifier: 1
```

Redis 重启后使用同一个 MySQL Run ID 作为 LangGraph `thread_id` 完成恢复。已完成的 Commander 与 Investigator 没有重复调用。对已完成 Run 再调用 Resume API 返回 `409`。

## Evidence Capsule

- 自动化用大体积指标响应验证字符预算与压缩结果。
- 每个 Capsule 保留 Evidence ID、类型、来源、观测时间和 SHA-256。
- 验证 Run 的 Capsule 清单已写入不可变 `agent_run_contexts`；SQL UPDATE 被 Trigger 以 `45000` 拒绝。
- 小体积验证样本原文为 470 bytes，带完整审计元数据的 Capsule 为 550 bytes；本数字不作为压缩率指标。

## Qdrant 已验证记忆

```text
persisted approved RCA points: 2
Qdrant restart persistence: passed
similar incident recall: 2
historical hint marked non-citable: passed
production FastEmbed vectors: 2 x 384 dimensions
```

REJECTED Run `b3608730-737b-447c-9c14-d5f18069f33d` 未生成 RCA Report，Qdrant 点数在运行前后均为 2。

## 尚未完成

当前仍未提供 `DEEPSEEK_API_KEY`。因此真实 DeepSeek API 调用、RCA 质量和模型延迟没有测试，也不得写入简历量化结果。FastEmbed 生产多语言模型已真实加载并生成中英文 384 维向量；Qdrant 容器闭环使用确定性测试向量隔离验证索引、过滤与持久化语义。

## 阶段结论

Phase 5 已满足“故障后同 Run 可恢复、已完成节点不重复、上下文预算可审计、Evidence 身份不丢失、只有已验证 RCA 可进入持久化记忆”的工程完成条件。
