# Phase 1–5 完整性审计

- 日期：2026-07-09
- 范围：故障实验、Incident 控制面、Evidence、只读 RCA、Checkpoint 与长期记忆
- 未纳入：真实 DeepSeek 质量评测（尚未提供 API Key）

## 审计发现与修复

### 1. Phase 1 冷启动 Prometheus 抓取竞态

首次冷启动后，`inventory_error_rate` 的 HTTP 故障与恢复均正确，但固定等待 2 秒时 Prometheus 尚未完成首次有效抓取，造成指标差值假阴性。

修复：

- baseline 请求后等待 Order 指标时序真正出现。
- 故障请求后轮询 `active_fault` 与场景信号，最长 15 秒。
- 超时仍按实际指标判定失败，不伪造通过。

### 2. Phase 4/5 缺 Key 失败关闭顺序

缺少 `DEEPSEEK_API_KEY` 时，运行时原先会先初始化 Qdrant/FastEmbed 查询，导致本应快速失败的 API 请求超时。

修复：

- MySQL 创建 Agent Run 后立即执行模型配置预检。
- 缺 Key 直接记录 `FAILED` Run，不初始化 embedding。
- Qdrant 集合为空时直接返回无历史记忆。

## 黑盒复验结果

| 阶段 | 复验结果 | 关键记录 |
|---|---|---|
| Phase 1 | 三个场景冷启动全部通过 | `inventory_error_rate-20260708T164248Z-61256a43` |
| Phase 2 | 幂等创建、Outbox 投递、RocketMQ 中断恢复通过 | `f84f4a57-2c19-491d-b3ca-33af5c92a4a1` / `089aea64-39a2-4cb1-a4fc-8bd5f6ad8fe4` |
| Phase 3 | Typed Tools、SHA-256、SQL 不可变、文件篡改 409 通过 | `8ffe9f04-bd78-4fe5-b2d7-8aac3915fbf9` / `cef08c00-a422-4474-b77a-5f3e016c2bdc` |
| Phase 4 | 三 Investigator、引用门、Verifier、缺 Key 快速失败通过 | `d84c324c-c337-4326-b3f5-dbad5b5c8e26` / `7baba824-8f52-470a-b1c6-4d0730a986cb` |
| Phase 5 | Redis 重启续跑、Qdrant 重启召回、REJECTED 不索引通过 | `c3e94657-94ed-4c75-888c-0b266e391033` / `fbb6df11-d8b0-4672-b25e-b6237422bcbb` |

## 自动检查

```text
pytest: 31 passed
compileall: passed
pip check: passed
lab compose config: passed
control-plane compose config: passed
secret scan: no credential found
runtime fatal/traceback log scan: clean
```

FastAPI/Starlette TestClient 仍产生一条上游弃用提示，不影响项目功能与测试结果。

## 审计结论

Phase 1–5 的已声明功能现在均有可重复黑盒路径和保存记录。当前唯一明确未完成项仍是真实 DeepSeek API 调用、RCA 质量与延迟评测；在提供 Key 前不得将这些指标写入简历。
