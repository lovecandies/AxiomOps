# Phase 4：LangGraph 多 Agent 只读 RCA 蓝图

## 阶段目标

把 Incident 与不可变 Evidence 转换成一份经过独立验证、引用可追踪的 RCA 报告。Agent 只能推理和读取证据；不得修改 Evidence、注入故障或执行恢复。

## Graph

```text
load_context（确定性）
  -> Incident Commander（规划）
  -> Send 动态并行
       -> Metrics Investigator
       -> Logs/Trace Investigator
       -> Change Investigator
  -> RCA Synthesizer
  -> citation_guard（确定性）
  -> Independent Verifier
  -> persist_result（确定性）
```

- Commander 只能从固定 Investigator 枚举中选择任务。
- 每个 Investigator 使用独立输入状态，只看到与角色相关的 Evidence。
- `findings` 使用 reducer 合并并行结果。
- 本阶段不配置 Checkpointer；Redis Checkpoint 属于 Phase 5。

## 角色职责

- Incident Commander：根据 Incident 与 Evidence 清单拆解调查任务，不直接给出根因。
- Metrics Investigator：分析 `METRIC_SNAPSHOT` 与 `SERVICE_HEALTH`。
- Logs/Trace Investigator：只分析日志/Trace Evidence；当前缺失时必须报告限制。
- Change Investigator：只分析变更 Evidence；当前缺失时必须报告限制。
- RCA Synthesizer：生成候选根因、置信度、贡献因素、反证与限制。
- Independent Verifier：独立判断结论是否被引用 Evidence 支撑。

## 结构化契约

- `InvestigationPlan`：任务角色、问题、允许的 Evidence ID。
- `InvestigatorFinding`：观察、假设、Evidence 引用、限制。
- `RcaDraft`：根因、摘要、置信度、贡献因素、反证、引用、限制。
- `VerificationResult`：`APPROVED/REJECTED`、理由、无效引用、未支撑声明。

所有模型响应都必须先通过 Pydantic 校验。DeepSeek 使用 JSON Output；空响应、截断、非法 JSON 或 Schema 不匹配均使运行失败，不保存为已验证 RCA。

## 确定性安全门

1. Investigator 任务只能引用 Commander 被分配的 Evidence。
2. RCA 引用必须属于当前 Incident。
3. RCA 至少引用一条 Evidence 才能进入 LLM Verifier。
4. Verifier `REJECTED` 时保存失败 Run 与反馈，但不创建最终 RCA Report。
5. Agent 节点不持有数据库写入、故障注入或恢复工具。

## 持久化

- `agent_runs`：运行状态、模型、图版本、输入 Evidence 快照、错误和耗时。
- `agent_run_steps`：每个角色的结构化输出和顺序审计。
- `rca_reports`：仅保存 Verifier `APPROVED` 的最终 RCA。

## API

- `POST /incidents/{id}/rca-runs`：同步执行一次只读 RCA。
- `GET /rca-runs/{id}`：查看运行、步骤与验证结果。
- `GET /incidents/{id}/rca`：获取最近一份已验证 RCA。

## 黑盒完成条件

1. LangGraph 实际执行 Commander、动态并行 Investigator、Synthesizer 和 Verifier。
2. Metrics Investigator 能引用真实 Phase 3 Evidence；缺失数据角色明确报告限制。
3. 不存在或跨 Incident 的 Evidence 引用被确定性拒绝。
4. Verifier 拒绝时不生成最终 RCA；批准时报告可按 Evidence ID 回溯。
5. DeepSeek 未配置、超时或返回非法结构时 Run 标记 `FAILED`，Incident/Evidence 保持不变。
