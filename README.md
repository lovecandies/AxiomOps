# AxiomOps

AxiomOps 是一个面向微服务故障场景的证据驱动多 Agent 智能诊断与安全恢复系统。

当前已完成 **Phase 3：Typed Tools 与不可变 Evidence**。系统还没有接入 LLM；现阶段已建立可重复故障实验、可靠 Incident 调度，以及可校验的外部事实采集链路。

## 当前能力

- `GET /health`：进程存活检查。
- `GET /ready`：当前阶段就绪检查。
- 环境变量配置加载。
- `order-service -> inventory-service` 可观测调用链。
- 延迟、确定性 5xx、依赖不可用三类故障注入与恢复。
- Prometheus 指标采集与场景指标差值验证。
- Ground Truth、请求、指标、结果四类实验产物。
- Incident 创建、查询和请求幂等冲突检测。
- MySQL 同一事务写入 Incident、审计事件与 Outbox。
- Outbox 租约、失败重试、RocketMQ 5 gRPC 投递与幂等消费。
- RocketMQ 暂停期间可靠落库，恢复后自动补发。
- Prometheus Metrics 与服务 Health 两个只读 Typed Tool。
- Evidence 原始内容写入持久化文件卷，MySQL 保存元数据与 SHA-256。
- 数据库 Trigger 拒绝 Evidence 更新/删除，读取时检测文件篡改。
- pytest 单元与契约测试。

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

## 运行故障实验

确保 Docker Desktop 已启动，然后执行：

```powershell
.\scripts\start_lab.ps1
.\.venv\Scripts\python.exe scripts\run_scenario.py --all
```

服务地址：

- Order API：`http://127.0.0.1:18001/docs`
- Inventory API：`http://127.0.0.1:18002/docs`
- Prometheus：`http://127.0.0.1:19090`

实验结果保存到被 Git 忽略的 `artifacts/lab/<run-id>/`：

```text
ground-truth.json
requests.json
metrics.json
result.json
```

停止实验环境：

```powershell
.\scripts\stop_lab.ps1
```

## 运行 Incident 控制面

```powershell
.\scripts\start_control_plane.ps1
.\.venv\Scripts\python.exe scripts\verify_control_plane.py
.\scripts\verify_outbox_recovery.ps1
```

控制面 API：`http://127.0.0.1:18000/docs`。

停止环境但保留 MySQL 数据：

```powershell
.\scripts\stop_control_plane.ps1
```

需要重新执行初始化 SQL 时，删除实验数据卷：

```powershell
docker compose -f ops-control-plane/docker-compose.yml down -v
```

## 运行 Evidence 验证

同时启动 Phase 1 Lab 与控制面：

```powershell
.\scripts\start_lab.ps1
.\scripts\start_control_plane.ps1
.\.venv\Scripts\python.exe scripts\verify_evidence.py
.\scripts\verify_evidence_immutability.ps1
```

最后一条命令会创建专用验证 Evidence，确认数据库拒绝 UPDATE/DELETE，并故意篡改该验证文件以确认读取返回 `409`。

## 最终技术栈

- Agent：Python、FastAPI、LangGraph、DeepSeek
- 基础设施：MySQL、Redis、RocketMQ、Qdrant
- 观测与实验：Prometheus、OpenTelemetry、Docker Compose
- 前端：React、TypeScript、SSE

## 上游代码基线

项目直接以 [`bcefghj/multi-agent-aiops`](https://github.com/bcefghj/multi-agent-aiops) 为上游代码基线，已配置为 Git 远程 `upstream`。上游模块按 AxiomOps 的技术栈和执行 Phase 逐步迁移，不同时保留 Python、Java、Go 三套实现。

项目仓库：[`lovecandies/AxiomOps`](https://github.com/lovecandies/AxiomOps)

详细取舍见 [上游迁移清单](docs/upstream-audit.md)、[架构基线](docs/architecture.md)、[Phase 2 蓝图](docs/phase-2-blueprint.md) 和 [Phase 3 蓝图](docs/phase-3-blueprint.md)。
