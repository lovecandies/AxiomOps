# AxiomOps 文档总览

这里存放 AxiomOps 的公开项目文档。文档表达面向真实工程和产品能力，不包含本地私人笔记或运行产物。

## 文档索引

| 文档 | 用途 |
| --- | --- |
| [项目背景与方案设计](project-background.md) | 说明项目解决什么问题、如何设计、达到什么效果 |
| [架构设计](architecture.md) | 说明运行组件、数据职责、Agent 边界和恢复边界 |
| [五分钟演示脚本](demo-script.md) | 提供一条稳定的端到端展示路径 |
| [故障案例说明](demo-cases.md) | 说明三个可复现实验场景与 Evidence 映射 |
| [Agent 评测说明](agent-evaluation.md) | 说明单 Agent / 多 Agent 对照、指标和结论解释 |
| [部署指南](deployment.md) | 本地 Docker Compose 启动与运行命令 |
| [API 文档](api.md) | 控制台和脚本使用的主要 REST Endpoint |
| [Benchmark](benchmarks.md) | 当前可复现实验结果和复现方式 |
| [优化效果评测](optimization-evaluation.md) | 说明 Citation Guard、Evidence 补齐、上下文压缩与 Checkpoint 的对照口径 |
| [架构决策记录](adr/) | 说明 Agentic Workflow、Evidence、恢复门禁、Outbox、Memory 与多 Agent 的关键取舍 |

## 推荐阅读顺序

1. 先阅读根目录 [README](../README.md)，理解项目定位。
2. 阅读 [项目背景与方案设计](project-background.md)，理解业务痛点和整体方案。
3. 阅读 [架构设计](architecture.md)，理解控制面、多 Agent 和数据边界。
4. 按 [部署指南](deployment.md) 启动本地环境。
5. 使用 [五分钟演示脚本](demo-script.md) 跑通端到端链路。
6. 阅读 [Agent 评测说明](agent-evaluation.md) 和 [Benchmark](benchmarks.md)，理解当前实验结果与边界。
7. 阅读 [优化效果评测](optimization-evaluation.md)，理解工程优化指标的基线和适用边界。
8. 阅读 [架构决策记录](adr/)，了解关键工程取舍。
