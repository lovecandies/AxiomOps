# Agent 评测说明

本项目的 Agent 评测遵循一个原则：不把模型输出的流畅程度当作效果，而是用固定故障集、Ground Truth、Evidence 引用和恢复验证来约束结论。

## 评测目标

评测关注四个问题：

1. RCA 是否命中已知根因。
2. RCA 是否严格引用当前 Incident 的 Evidence。
3. Independent Verifier 是否能阻止缺少证据支撑的结论。
4. 诊断结果是否能进入审批、恢复和恢复验证闭环。

## 对照组

| 模式 | 说明 | 价值 |
| --- | --- | --- |
| 固定闭环 | 按确定性顺序执行故障注入、证据采集、恢复和验证 | 验证后端控制面与实验环境是否可靠 |
| 单 Agent | 一个模型上下文完成 RCA | 作为低成本基线 |
| 多 Agent Graph | Commander、Investigator、RCA Synthesizer、Independent Verifier 分工协作 | 验证证据约束、职责隔离和独立核验 |

## 当前结果

当前比较使用 3 个 Ground Truth 场景，每个场景重复 3 次。

| 指标 | 单 Agent | 多 Agent |
| --- | ---: | ---: |
| 根因命中 | 9 / 9 | 9 / 9 |
| 严格 Evidence 引用覆盖 | 0 / 9 | 8 / 9 |
| 平均 confidence | 0.96 | 0.82 |
| 平均模型 Token | 1,268 | 10,555 |
| 平均延迟 | 3.06s | 20.28s |

## 如何解释结果

这个结果不说明多 Agent 在当前小规模确定性故障集上提高了根因命中率，因为单 Agent 和多 Agent 都能命中 9 / 9。

它真正说明的是：

- 多 Agent 把 RCA 从一次自由回答变成了可审计链路。
- Investigator 的子上下文让不同证据信号的职责更清楚。
- Citation Guard 和 Independent Verifier 提升了证据引用质量。
- 多 Agent 的代价是更高的延迟和 Token 成本，因此更适合高风险、强审计的 Incident。

## 评测数据摘要

机器可读摘要见 [benchmarks/agent-comparison-summary.json](benchmarks/agent-comparison-summary.json)。

## 复现方式

启动 Lab 和 Control Plane 后运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_phase7_evaluation.py
```

如需运行 Agent 对照实验，请先配置兼容 Chat Endpoint 的模型服务，再执行对应评测脚本。完整运行产物默认写入 ignored 的 `artifacts/` 目录，避免把本地实验日志提交到仓库。

## 当前边界

- 当前数据集规模较小，不宣称生产场景泛化准确率。
- Trace 和 Change 在本地 Lab 中以轻量快照形式实现，用于证明证据链路设计。
- Qdrant 中的历史 RCA 只作为参考记忆，不能作为当前 Incident 的证据引用。
