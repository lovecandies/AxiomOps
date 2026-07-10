# Phase 6 验证记录

## 范围

- 权限 Header：`X-AxiomOps-User`、`X-AxiomOps-Role`
- 人工审批：申请人与审批人分离
- Sandbox 恢复：`reset_inventory_fault`
- 恢复验证：库存健康检查与订单链路检查
- 回滚记录：验证失败时保存恢复前状态并尝试恢复
- 执行幂等：同一审批只生成一条执行记录

## 黑盒验证命令

同时启动 Phase 1 Lab 与控制面：

```powershell
.\scripts\start_lab.ps1
.\scripts\start_control_plane.ps1
.\.venv\Scripts\python.exe scripts\verify_phase6.py
```

脚本会执行：

1. 注入 `inventory-service` 不可用故障。
2. 创建 Incident 并采集不可变 Evidence。
3. 写入一份明确标记为 `scripted-phase6-seed` 的已验证 RCA。
4. 用 `commander` 角色申请恢复。
5. 验证申请人自审批被 `403` 拦截。
6. 用 `approver` 角色审批。
7. 用 `operator` 角色执行 sandbox 恢复。
8. 验证库存故障已重置、订单链路恢复。
9. 重复执行同一审批，确认返回同一执行记录。

成功输出示例：

```json
{
  "passed": true,
  "execution_status": "SUCCEEDED",
  "self_approval_status": 403,
  "idempotent_execute": true
}
```

## 2026-07-09 实际黑盒验证结果

Docker Desktop 启动后，已重新启动 Phase 1 Lab 与控制面并执行：

```powershell
.\.venv\Scripts\python.exe scripts\verify_phase6.py
```

实际输出：

```json
{
  "passed": true,
  "incident_id": "b8621e95-dcef-4cde-ae3c-f61c440ce719",
  "run_id": "55d32f75-86f9-4835-b042-14c5e9b53d38",
  "approval_id": "e1dec54a-311e-47ac-849a-43be7f3e7df7",
  "execution_id": "703a361e-18f7-4c0f-b6a2-5c29faed7a3a",
  "execution_status": "SUCCEEDED",
  "self_approval_status": 403,
  "before_state": {
    "mode": "unavailable",
    "delay_ms": 0,
    "error_rate": 0.0,
    "request_count": 0
  },
  "verification": {
    "passed": true,
    "order_flow_status": 200,
    "inventory_health_status": 200
  },
  "idempotent_execute": true
}
```

结论：

- 自审批被 `403` 拦截。
- Sandbox 恢复执行成功。
- 恢复后库存健康检查和订单链路均返回 `200`。
- 同一审批重复执行返回同一执行记录，幂等语义成立。

## 单元验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests\control_plane\test_recovery.py
```

覆盖点：

- 申请人不能自审批。
- 已审批恢复执行后再次执行保持幂等。
- 验证失败时记录 rollback。
- API 角色不匹配时返回 `403`。

## 当前边界

- 本阶段只支持实验环境里的 `reset_inventory_fault`，不接真实生产 Kubernetes、SSH 或云厂商 API。
- 恢复动作不是 Agent 节点，而是确定性控制面节点。
- DeepSeek 真实质量仍未验证；Phase 6 脚本为了验证恢复链路，会写入明确标记的 deterministic RCA seed，不冒充真实模型效果。
