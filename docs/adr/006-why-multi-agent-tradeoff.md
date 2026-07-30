# ADR 006：为何仅在验证收益覆盖成本时采用多 Agent

## 背景

Benchmark 表明，在当前确定性故障集上，单 Agent 与多 Agent 的根因命中相同，而多 Agent 图消耗更多时间和 Token。

## 决策

仅在需要证据纪律与职责隔离的 Incident 中保留 Commander、Investigator、Synthesizer 和独立 Verifier 角色；不声称多 Agent 总会提高诊断准确率。

## 影响

系统为高风险 Incident 优化可追溯性，同时保留更简单的低延迟、低成本路径。
