# AxiomOps

AxiomOps 是一个面向微服务故障场景的证据驱动多 Agent 智能诊断与安全恢复系统。

当前仓库处于 **Phase 0：项目骨架与健康检查**。本阶段只建立可运行、可测试的 FastAPI 基线，不提前接入 Agent 或后端基础设施。

## 当前能力

- `GET /health`：进程存活检查。
- `GET /ready`：当前阶段就绪检查。
- 环境变量配置加载。
- pytest 黑盒 API 测试。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn axiom_ops.app:app --reload
```

打开 `http://127.0.0.1:8000/docs`，或执行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 最终技术栈

- Agent：Python、FastAPI、LangGraph、DeepSeek
- 基础设施：MySQL、Redis、RocketMQ、Qdrant
- 观测与实验：Prometheus、OpenTelemetry、Docker Compose
- 前端：React、TypeScript、SSE

## 上游代码基线

项目直接以 [`bcefghj/multi-agent-aiops`](https://github.com/bcefghj/multi-agent-aiops) 为上游代码基线，已配置为 Git 远程 `upstream`。上游模块按 AxiomOps 的技术栈和执行 Phase 逐步迁移，不同时保留 Python、Java、Go 三套实现。

项目仓库：[`lovecandies/AxiomOps`](https://github.com/lovecandies/AxiomOps)

详细取舍见 [上游迁移清单](docs/upstream-audit.md) 和 [架构基线](docs/architecture.md)。
