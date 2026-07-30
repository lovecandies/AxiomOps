<p align="center">
  <img src="docs/assets/project-banner.svg" alt="AxiomOps banner" width="100%" />
</p>

<h1 align="center">AxiomOps</h1>

<p align="center">
  证据驱动的多 Agent 智能故障诊断与安全恢复系统。
</p>

<p align="center">
  <a href="docs/architecture.md">架构设计</a> ·
  <a href="docs/deployment.md">部署指南</a> ·
  <a href="docs/api.md">API 文档</a> ·
  <a href="docs/benchmarks.md">Benchmark</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3b6f85">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-control_plane-5a8f7b">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-multi_agent-b66a4a">
  <img alt="Docker" src="https://img.shields.io/badge/Docker_Compose-local_lab-6f6a5f">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-8b6f47">
</p>

## 项目定位

AxiomOps 是一个面向微服务故障场景的可复现实验环境与 Incident 控制面。它将告警转化为类型化 Evidence，通过受控的多 Agent RCA 工作流完成诊断，并在独立验证、人工审批和后端策略门禁之后执行安全恢复。

项目的核心边界很明确：Agent 负责读取证据、推理和生成结构化结论；恢复动作由可审计、可幂等、可回滚的后端流程执行。

## 背景与痛点

AxiomOps 的业务背景来自典型微服务故障处置：订单服务依赖库存服务，当库存接口出现 503、错误率升高或响应延迟变大时，订单链路会出现失败、超时或 SLO 下降。传统排障通常需要人工在告警、Prometheus 指标、服务健康检查、日志、变更记录和恢复脚本之间来回切换，排查链路长，证据容易散落，恢复动作也容易缺少审批和审计。

把大模型直接接入这类运维场景时，真正困难的不是“让模型给出一个答案”，而是让答案和动作都能被工程系统约束：

- 诊断依赖松散上下文，缺少可追溯 Evidence。
- 大模型容易把历史经验、猜测和当前事实混在一起，导致 RCA 难以证明。
- 推理和执行混在一起，恢复动作难以审批、审计、幂等和回滚。
- 只做聊天式 Demo 无法评估效果，缺少固定故障集、Ground Truth 和基线对照。

因此，AxiomOps 不是做一个“会聊天的运维机器人”，而是做一个证据驱动的故障处置控制面：先把故障实验、证据采集、Agent 推理、独立验证、人工审批、安全恢复和 Benchmark 都纳入同一条闭环，再让 Agent 在边界内发挥作用。

完整背景说明见 [项目背景与方案设计](docs/project-background.md)。

## 方案设计

AxiomOps 将一次故障处置拆成四层：

| 层级 | 设计方案 | 解决的问题 |
| --- | --- | --- |
| 故障实验层 | 构建 Order -> Inventory 微服务链路，提供延迟、错误率、依赖不可用三类 Ground Truth 场景 | 让 RCA 和恢复效果有可重复验证的事实基准 |
| Incident 控制层 | 使用 MySQL 保存 Incident、审计事件、Evidence、RCA、审批和执行记录；使用 Transactional Outbox + RocketMQ 做可靠调度 | 避免状态只存在内存中，保证事件投递、重试和幂等 |
| Agent 推理层 | 使用 LangGraph 编排 Commander、Investigators、RCA Synthesizer、Independent Verifier；所有结论必须引用已保存 Evidence | 降低自由文本幻觉，让多 Agent 分工、上下文隔离和独立核验可审计 |
| 安全恢复层 | 使用 Commander / Approver / Operator 角色隔离，恢复动作只允许审批后的 Sandbox 执行，并做健康与订单链路验证 | 防止 LLM 直接改系统，保证恢复动作可控、可回滚、可复盘 |

## 实现方法

项目围绕“可证明”和“可恢复”做工程设计：

- **Typed Tools**：将 Prometheus 指标、服务健康、故障注入状态和订单链路探测封装为固定输入/输出的工具，避免 Agent 自由访问系统。
- **不可变 Evidence**：每次工具调用的原始 JSON 落盘，MySQL 保存元数据与 SHA-256；数据库 Trigger 拒绝 Evidence 更新和删除。
- **LangGraph 多 Agent**：Commander 负责规划，Metrics / Logs-Trace / Change Investigator 分工调查，RCA Synthesizer 合成结构化 RCA，Independent Verifier 检查证据引用和结论支撑。
- **上下文与记忆**：Redis 保存 Checkpoint 支持失败恢复；Qdrant 只索引通过 Verifier 的历史 RCA，历史经验只能作为参考，不能冒充当前 Evidence。
- **可靠后端控制面**：MySQL 作为最终事实源，Outbox 与 RocketMQ 负责可靠事件投递，恢复审批与执行记录保证幂等。
- **黑盒验证体系**：用固定故障集、Prometheus 指标、恢复验证脚本和 Benchmark 报告验证完整链路，而不是只看一次模型输出。

## 工程效果

当前项目已经形成从故障注入到恢复验证的闭环，并保存了可复现评测结果：

| 指标 | 结果 | 说明 |
| --- | --- | --- |
| 确定性故障闭环 | 3 / 3 通过 | 三类库存故障均可触发、诊断、审批、恢复和验证 |
| Prometheus Evidence 覆盖率 | 100% | 每个场景均能采集指标证据 |
| 恢复验证通过率 | 100% | Sandbox 恢复后同时验证库存服务和订单链路 |
| 多 Agent 根因命中 | 9 / 9 | 3 个 Ground Truth 场景各重复 3 次 |
| 多 Agent 严格 Evidence 引用覆盖 | 8 / 9 | 相比单 Agent 的 0 / 9，显著提升结论可追溯性 |
| 多 Agent 平均延迟 | 20.28s | 相比单 Agent 3.06s，换取更强审计与验证能力 |

这个结果说明：多 Agent 并不是在小型确定性场景里简单提高“根因命中率”，而是把 RCA 从一次自由回答变成一条可审计的工程链路。它的核心价值是证据约束、职责隔离、独立验证和安全恢复，适合高风险、强审计要求的故障场景。

## 核心能力

| 模块 | 能力 |
| --- | --- |
| 故障实验环境 | 提供 Order -> Inventory 微服务链路，支持延迟、错误率、依赖不可用三类故障注入 |
| Incident 控制面 | 基于 MySQL 管理 Incident 状态、审计事件和 Transactional Outbox |
| Typed Tools | 采集 Prometheus 指标、服务健康、故障注入状态和订单链路探测 |
| 不可变 Evidence | 原始 JSON 落盘，MySQL 保存元数据和 SHA-256 完整性校验 |
| 多 Agent RCA | Commander、Investigator、RCA Synthesizer、Independent Verifier 分工协作 |
| 上下文与记忆 | Redis Checkpoint 支持恢复，Qdrant 索引已验证历史 RCA |
| 安全恢复 | Commander / Approver / Operator 角色隔离，审批后执行 Sandbox 恢复并验证 |
| 可观测与评测 | Prometheus 指标、Trace Header、SSE 时间线和可复现实验报告 |

## 技术栈

| 层级 | 技术 |
| --- | --- |
| Agent Runtime | Python、FastAPI、LangGraph、DeepSeek 兼容 Chat Endpoint |
| 控制面基础设施 | MySQL、Redis、RocketMQ、Qdrant |
| 可观测性 | Prometheus、W3C Trace Header、结构化审计记录 |
| 故障实验 | Docker Compose、FastAPI 微服务、脚本化故障注入 |
| 前端控制台 | React、TypeScript、SSE、Lucide Icons |
| 验证体系 | pytest、场景 Runner、Benchmark 脚本 |

## 架构图

```mermaid
flowchart LR
    Alert["故障实验 / 告警"] --> CP["FastAPI 控制面"]
    CP --> DB["MySQL 最终事实源"]
    CP --> Evidence["不可变 Evidence 存储"]
    CP --> Tools["Typed Tools"]
    Tools --> Prom["Prometheus"]
    Tools --> Lab["Order / Inventory Lab"]
    DB --> Outbox["Transactional Outbox"]
    Outbox --> MQ["RocketMQ"]
    MQ --> Runtime["LangGraph RCA Runtime"]
    Runtime --> Agents["Commander + Investigators + Synthesizer"]
    Agents --> Verifier["Independent Verifier"]
    Verifier --> RCA["Verified RCA"]
    RCA --> Approval["人工审批门禁"]
    Approval --> Recovery["Sandbox 恢复"]
    Recovery --> Check["健康检查 + 订单链路验证"]
    Runtime --> Redis["Redis Checkpoint"]
    Runtime --> Qdrant["Qdrant Verified Memory"]
```

## 全流程链路

1. 在本地 Inventory 服务注入已知故障。
2. 在控制面创建 Incident。
3. 通过 Typed Tools 采集指标、健康状态、故障状态和订单链路 Evidence。
4. 启动 LangGraph 多 Agent RCA 工作流。
5. 由 Independent Verifier 拒绝缺少 Evidence 支撑的结论。
6. Commander 发起恢复请求，Approver 完成人工审批。
7. Operator 执行受限 Sandbox 恢复动作。
8. 同时验证服务健康与业务链路，并保存审计事件、指标和实验报告。

## Benchmark 摘要

当前评测使用 3 个 Ground Truth 故障场景，每个场景重复 3 次。

| 指标 | 结果 |
| --- | --- |
| 确定性故障闭环 | 3 / 3 通过 |
| Prometheus Evidence 覆盖率 | 100% |
| 恢复验证通过率 | 100% |
| 多 Agent 根因命中 | 9 / 9 |
| 单 Agent 根因命中 | 9 / 9 |
| 多 Agent 严格 Evidence 引用覆盖 | 8 / 9 |
| 单 Agent 严格 Evidence 引用覆盖 | 0 / 9 |
| 多 Agent 平均延迟 | 20.28s |
| 单 Agent 平均延迟 | 3.06s |

这个结果没有夸大为“准确率提升”。在当前小规模确定性故障集上，单 Agent 和多 Agent 都能命中根因；多 Agent 的价值主要体现在 Evidence 约束、职责隔离和独立验证，代价是更高的延迟与模型调用成本。因此完整多 Agent 链路更适合高风险、强审计要求的 Incident。

详细说明见 [docs/benchmarks.md](docs/benchmarks.md)。

## 快速启动

前置环境：

- Python 3.11+
- Docker Desktop
- Node.js 20+

安装 Python 依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

启动本地故障实验环境和控制面：

```powershell
.\scripts\start_lab.ps1
.\scripts\start_control_plane.ps1
```

运行后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

启动前端控制台：

```powershell
cd frontend
npm install
npm run dev
```

打开 Vite 输出的本地地址，创建 Incident，并按页面指引完成证据采集、RCA、审批和恢复验证。

## 仓库结构

```text
src/axiom_ops/              Python package
src/axiom_ops/control_plane Incident、Evidence、RCA、Recovery、Observability
src/axiom_ops/lab           故障注入微服务实验环境
frontend/                   React 运维控制台
ops-control-plane/          Docker Compose 与 MySQL 迁移脚本
ops-lab/                    实验服务、Prometheus 配置与故障场景
scripts/                    本地启动、验证和评测脚本
tests/                      单元测试与契约测试
docs/                       公开项目文档
```

## 文档索引

- [文档总览](docs/README.md)
- [项目背景与方案设计](docs/project-background.md)
- [架构设计](docs/architecture.md)
- [部署指南](docs/deployment.md)
- [API 文档](docs/api.md)
- [Benchmark](docs/benchmarks.md)

## 安全说明

- 不要提交本地凭据、运行产物或实验日志。
- Agent 只负责诊断推理，恢复动作由后端策略和角色门禁执行。
- Evidence 与 RCA 持久化保存，并带完整性校验。
- 默认恢复动作只作用于本地 Sandbox 实验环境。

## License

MIT. See [LICENSE](LICENSE).
