<p align="center">
  <img src="docs/assets/project-banner.svg" alt="AxiomOps banner" width="100%" />
</p>

<h1 align="center">AxiomOps</h1>

<p align="center">
  证据驱动的多 Agent 智能故障诊断与安全恢复系统
</p>

<p align="center">
  <a href="docs/project-background.md">项目背景</a> ·
  <a href="docs/architecture.md">架构设计</a> ·
  <a href="docs/demo-script.md">五分钟演示</a> ·
  <a href="docs/agent-evaluation.md">Agent 评测</a> ·
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

AxiomOps 是一个面向微服务故障场景的 Incident 控制面。它把告警转化为类型化 Evidence，通过 LangGraph 编排的多 Agent RCA 流程完成诊断，并在独立验证、人工审批和后端策略门禁之后执行安全恢复。

项目边界很明确：Agent 负责读取证据、推理和生成结构化结论；恢复动作由可审计、可幂等、可回滚的后端流程执行。

## 背景与痛点

在典型微服务链路中，订单服务依赖库存服务。当库存接口出现 503、错误率升高或响应延迟变大时，订单链路会失败、超时或触发 SLO 风险。传统排障通常需要人工在告警、Prometheus 指标、服务健康检查、调用链路、变更记录和恢复脚本之间来回切换。

直接把大模型接入这类场景并不够，真正困难的是：

- 诊断证据分散，RCA 结论难以追溯。
- 模型容易把当前事实、历史经验和猜测混在一起。
- 诊断和恢复如果混在一个模型输出里，动作很难审批、审计和回滚。
- 如果没有固定故障集和 Ground Truth，项目只能展示“看起来会回答”，无法验证效果。

AxiomOps 的思路是：先构建可复现实验环境和确定性证据，再让 Agent 在受控边界内完成调查、合成和核验。

## 核心能力矩阵

| 模块 | 能力 |
| --- | --- |
| 故障实验环境 | 构建 Order → Inventory 微服务链路，支持延迟、错误率、依赖不可用三类故障注入 |
| Incident 控制面 | 使用 MySQL 管理 Incident、审计事件、Evidence、RCA、审批和恢复记录 |
| 可靠调度 | 基于 Transactional Outbox + RocketMQ 处理业务级事件投递、重试和幂等 |
| 受控工具选择 | Planner 根据当前 Incident 已有 Evidence 自动补齐缺失证据，只允许调用白名单工具 |
| Typed Tools | 采集 Prometheus 指标、服务健康、故障状态、订单链路探测、Trace 快照和 Change 事件 |
| 不可变 Evidence | 原始 JSON 落盘，MySQL 保存元数据和 SHA-256，数据库 Trigger 阻止修改和删除 |
| 多 Agent RCA | Commander、Investigator、RCA Synthesizer、Independent Verifier 分工协作 |
| 上下文与记忆 | Redis Checkpoint 支持恢复，Qdrant 只索引已验证历史 RCA |
| 安全恢复 | Commander / Approver / Operator 角色隔离，审批后执行 Sandbox 恢复并验证结果 |
| 可观测与评测 | Prometheus 指标、Trace Header、SSE 时间线和可复现实验报告 |

## 技术栈

| 层级 | 技术 |
| --- | --- |
| Agent Runtime | Python、FastAPI、LangGraph、DeepSeek 兼容 Chat Endpoint |
| 控制面基础设施 | MySQL、Redis、RocketMQ、Qdrant |
| 可观测性 | Prometheus、W3C Trace Header、结构化审计记录 |
| 故障实验 | Docker Compose、FastAPI 微服务、脚本化故障注入 |
| 前端控制台 | React、TypeScript、SSE、Lucide Icons |
| Agent 工具协议 | MCP Server / Client、Pydantic Schema、固定进程身份与审批门禁 |
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
2. 在控制台创建 Incident。
3. 通过受控工具选择自动补齐指标、健康状态、故障状态、订单链路、Trace 和 Change Evidence。
4. 启动 LangGraph 多 Agent RCA 工作流。
5. 由 Independent Verifier 拒绝缺少 Evidence 支撑的结论。
6. Commander 发起恢复请求，Approver 完成人工审批。
7. Operator 执行受限 Sandbox 恢复动作。
8. 同时验证服务健康与业务链路，并保存审计事件、指标和实验报告。

推荐演示路径见 [docs/demo-script.md](docs/demo-script.md)，故障案例说明见 [docs/demo-cases.md](docs/demo-cases.md)。

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

详细说明见 [docs/agent-evaluation.md](docs/agent-evaluation.md) 和 [docs/benchmarks.md](docs/benchmarks.md)。

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

### MCP Agent 工具

安装 Python 包后，通过 stdio 启动本地 MCP Server：

```powershell
python -m axiom_ops.mcp.server
```

它暴露 4 个只读 Evidence 工具（`collect_metrics`、`check_service_health`、`inspect_inventory_fault`、`probe_order_flow`）与 1 个受门禁约束的恢复工具（`execute_approved_recovery`）。恢复默认禁用；仅在既有恢复审批完成后，才启动独立受信任进程并设置 `AXIOMOPS_MCP_ROLE=operator`。

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
- [五分钟演示脚本](docs/demo-script.md)
- [故障案例说明](docs/demo-cases.md)
- [Agent 评测说明](docs/agent-evaluation.md)
- [部署指南](docs/deployment.md)
- [API 文档](docs/api.md)
- [Benchmark](docs/benchmarks.md)
- [优化效果评测](docs/optimization-evaluation.md)
- [架构决策记录](docs/adr/)

## 安全说明

- 不要提交本地凭据、运行产物或实验日志。
- Agent 只负责诊断推理，恢复动作由后端策略和角色门禁执行。
- Evidence 与 RCA 持久化保存，并带完整性校验。
- 默认恢复动作只作用于本地 Sandbox 实验环境。

## License

MIT. See [LICENSE](LICENSE).
