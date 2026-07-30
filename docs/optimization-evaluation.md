# 优化效果评测

本评测用于量化 AxiomOps 中可复现的工程优化，不将确定性闭环通过率当作 Agent 效果，也不从单次模型文本推断结论。

## 对照组与指标

| 优化点 | 基线 | 优化后 | 指标 |
| --- | --- | --- | --- |
| Evidence 引用防线 | 不经过 Citation Guard 的 RCA 草稿 | Citation Guard 拒绝跨 Incident 或不存在的引用 | 非法引用拦截率、错误发布率 |
| Evidence 补齐策略 | 每次固定采集 6 类诊断证据 | 仅采集当前 Incident 缺失的允许证据 | 平均工具调用数、冗余调用削减率、必要证据覆盖率 |
| 上下文压缩 | 原始 Evidence 原文直接进入图 | Evidence Capsule 保留身份与关键信号 | 上下文字节数、压缩率、Evidence 身份保留率 |
| Checkpoint 恢复 | 中断后重新执行完整图 | 从 Redis/LangGraph Checkpoint 恢复 | 已完成节点免重跑率、恢复后新增模型调用数 |

## 评测案例

1. 对 12 个跨 Incident 或虚构 Evidence ID 的 RCA 草稿进行故障注入；仅当完整图拒绝发布且基线会放行该草稿时，计为成功拦截。
2. 使用 7 个 Evidence 完整度状态（已存在 0 至 6 类证据），对比固定全量采集与缺失补齐策略。该项是受控后端策略评测，不宣称模型自主规划能力。
3. 使用固定的大型 Evidence 语料测量压缩前后字节数；Capsule 必须保留 Evidence ID、类型、采集时间和 SHA-256。
4. 在 Synthesize 节点注入一次失败，验证恢复时 Commander 与 3 个 Investigator 不会重跑。

## 结果解释

- 安全拦截率体现的是系统防线强度，不等同于模型准确率。
- 工具调用削减仅适用于 Incident 已经存在部分 Evidence 的续查场景。
- Checkpoint 节省的是中断后的重复工作；正常首次运行不产生该收益。
- 指标报告必须保存输入案例和机器可读 JSON，简历只引用有对应产物的数字。
