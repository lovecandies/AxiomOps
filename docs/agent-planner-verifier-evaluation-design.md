# 受控 Planner 与 Verifier 对抗评测设计

## 目标

在不扩大 Agent 权限的前提下，补强两项能力：

1. Agent 根据当前 Incident 和 Evidence 目录提出下一步只读调查工具。
2. Independent Verifier 拒绝“Evidence ID 合法，但因果结论没有被 Evidence 支撑”的 RCA。

## 边界

- Planner 只能从现有诊断工具白名单中选择工具，且只能使用预定义参数模板。
- 后端校验工具名称、参数、单次预算与重复调用；任何非法提议均不执行。
- 模型不可用、输出不合法或超预算时，系统回退到现有缺失 Evidence 补齐策略。
- Planner 不能执行恢复；恢复继续由审批和 Sandbox 后端流程处理。
- Verifier 的语义拒绝不替代 Citation Guard。前者检查因果支撑，后者检查引用归属。

## 数据流

```text
Incident + 已有 Evidence 目录
  -> Planner（结构化工具提议）
  -> 后端白名单 / 参数 / 预算校验
  -> Typed Tool 或 MCP Tool 执行
  -> 新 Evidence
  -> RCA Synthesizer
  -> Citation Guard（引用归属）
  -> Independent Verifier（因果支撑）
```

## 评测

| 评测 | 基线 | 完整链路 | 指标 |
| --- | --- | --- | --- |
| Planner 工具治理 | 规则缺失补齐 | LLM 提议 + 后端校验 | 工具白名单符合率、必要证据覆盖、冗余调用数、回退次数 |
| Verifier 语义对抗 | 仅 Citation Guard | Citation Guard + Verifier | 合法引用但无支撑结论的拦截率、错误发布率 |

评测案例与原始输出写入 `artifacts/evaluations/`；公开文档只保留口径和可复现命令。
