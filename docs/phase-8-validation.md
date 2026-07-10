# Phase 8：React 控制台与五分钟演示验证记录

## 已通过

- `npm install && npm run build`：通过。Vite 生产构建生成 `frontend/dist/`。
- `python -m pytest`：40 passed。
- `python -m compileall -q src scripts`：通过。
- 浏览器访问 `http://127.0.0.1:5173`：成功显示“安全恢复控制台”、Incident 空状态和“新建演示”入口。
- 真实 DeepSeek RCA：四类 Evidence 下完成 6 次模型调用、10091 tokens；Independent Verifier 批准，RCA confidence 为 0.8。
- Docker 黑盒：`FAULT_STATE` 与 `ORDER_FLOW_PROBE` 已写入不可变 Evidence；Sandbox 恢复后库存与订单链路均返回 200。

## 完整演示前置条件

本机 Docker Desktop 必须启动，Lab 与控制面依赖其中的 MySQL、Redis、RocketMQ、Qdrant 和实验微服务。验证时 Docker daemon 不可连接，因此未伪造完整恢复通过结果。

```powershell
.\scripts\start_lab.ps1
.\scripts\start_control_plane.ps1
.\scripts\start_console.ps1
.\.venv\Scripts\python.exe scripts\seed_phase8_demo.py
```

打开 `http://127.0.0.1:5173`，按下列顺序演示：

1. 运行 `seed_phase8_demo.py`，它只注入故障、采集 Evidence 并预置明确标记的确定性 RCA，绝不恢复。
2. 在控制台选择最新的 `Inventory unavailable — console demo` Incident。
3. 确认 Evidence 和已验证 RCA 报告。
4. 按“请求恢复 → 审批 → 执行恢复”完成三角色隔离。
5. 确认执行卡片为 `SUCCEEDED`，并显示 inventory/order 验证状态码。
6. 保持详情页打开，观察 SSE 更新的 Incident 时间线。

`start_control_plane.ps1` 会在项目根目录存在 `.env` 时显式将它传给 Docker Compose。不要提交该文件；其中的 `DEEPSEEK_API_KEY` 只用于本地真实模型运行。

## 不纳入本阶段

- 不在浏览器实现授权、审批策略、幂等或回滚；这些继续由控制面确定性执行。
- 不将 EventSource 用于 Agent 自由文本聊天；SSE 仅推送 Incident/Outbox 状态快照。
