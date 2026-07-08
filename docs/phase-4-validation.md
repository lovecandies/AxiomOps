# Phase 4 验证记录

- 日期：2026-07-08
- 编排：LangGraph 1.2.8 `StateGraph + Send`
- 生产模型适配：DeepSeek JSON Output

## 自动化检查

```text
pytest: 26 passed
compileall: passed
docker compose config: passed
```

测试依赖层有一条 FastAPI/Starlette TestClient 弃用提示，不影响项目代码与测试结果。

## 多 Agent RCA 闭环

评测 Incident：`3e447f37-0bf5-45bd-899a-971f073b318f`。

```text
Run: 8e0cb59a-5e46-4456-98f5-99ec094a6b5f
status: COMPLETED
graph_version: phase4-v1
model_calls: 6
recorded steps: 8
investigator steps: 3
verification: APPROVED
Evidence citations: 2
```

三个 Investigator 均执行；Metrics Agent 引用真实 Phase 3 Evidence，Logs/Trace 与 Change Agent 明确记录证据缺失。评测模型名为 `scripted-grounded-evaluation`，不作为 DeepSeek 效果指标。

## 引用与不可变安全门

```text
cross-Incident citation Run: 2f6b432f-b209-42db-b1e9-66b57cfc6111
status: REJECTED
final RCA report count: 0
RCA SQL UPDATE: rejected
RCA SQL DELETE: rejected
restart persistence: passed
```

## DeepSeek 生产路径

- HTTP 适配器已验证 `response_format=json_object`、JSON Schema 解析、token 统计和调用预算。
- 当前环境未提供 `DEEPSEEK_API_KEY`，因此没有伪造真实模型调用结果。
- 缺 Key 的 API Run `86fa1e66-a7bf-417b-bfc7-064b6c44d0cb` 正确标记为 `FAILED`，错误被审计，最终 RCA 返回 `404`。

## 阶段结论

Phase 4 已满足“图编排可执行、子上下文隔离、并行调查可证明、引用越界可拒绝、独立验证可审计、模型失败不污染最终 RCA”的工程完成条件。真实 DeepSeek 质量评测需由有效 API Key 单独执行并记录。

2026-07-09 复审修正了缺 Key 时的预检顺序。Run `7baba824-8f52-470a-b1c6-4d0730a986cb` 在不初始化 embedding 的情况下快速返回 `FAILED` 并保留完整错误审计。
