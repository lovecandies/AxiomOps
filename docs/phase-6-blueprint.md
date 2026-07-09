# Phase 6：权限、人工审批、Sandbox 恢复验证与回滚蓝图

## 目标

把 Phase 4/5 产生的已验证 RCA 接到一个受控恢复闭环中。Agent 仍然只负责诊断与建议，真正的恢复动作由确定性控制面执行，避免“LLM 直接改系统”的面试硬伤。

## 最小业务闭环

```text
已验证 RCA
  -> Commander 申请恢复
  -> Approver 人工审批
  -> Operator 执行 Sandbox 恢复
  -> 控制面验证订单链路
  -> 成功记录 SUCCEEDED，失败记录 FAILED/ROLLED_BACK
```

## 角色权限

| 角色 | 允许动作 | 禁止动作 |
| --- | --- | --- |
| `commander` | 创建恢复审批申请 | 审批、执行 |
| `approver` | 审批恢复申请 | 申请后自批、执行 |
| `operator` | 执行已审批恢复 | 创建申请、审批 |

请求通过两个 Header 显式携带身份：

```text
X-AxiomOps-User: alice
X-AxiomOps-Role: commander | approver | operator
```

## 恢复动作边界

当前只开放一个动作：

```text
reset_inventory_fault
```

它只作用于 Phase 1 实验环境中的 `inventory-service`，执行流程为：

1. 读取恢复前故障状态：`GET /admin/faults`
2. 执行恢复动作：`POST /admin/faults/reset`
3. 验证服务健康与订单链路：`GET /health`、`GET /orders/phase6-recovery-check`
4. 如果验证失败，则按恢复前状态重新写回 `POST /admin/faults`

## 数据模型

- `recovery_approvals`：恢复申请、审批人、审批意见和审批时间。
- `recovery_executions`：执行结果、sandbox 标记、恢复前状态、动作结果、验证结果、回滚结果和错误。

`recovery_executions` 由数据库 Trigger 禁止 `UPDATE` 和 `DELETE`，保证执行审计不可变。

## API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/incidents/{incident_id}/recovery-approvals` | 基于已验证 RCA 申请恢复 |
| `GET` | `/recovery-approvals/{approval_id}` | 查看审批状态 |
| `POST` | `/recovery-approvals/{approval_id}/approve` | 人工审批 |
| `POST` | `/recovery-approvals/{approval_id}/execute` | 执行已审批恢复 |
| `GET` | `/recovery-executions/{execution_id}` | 查看执行审计 |

## 黑盒完成条件

1. 未带正确角色 Header 时，恢复申请、审批和执行会返回 `403`。
2. 申请人不能审批自己的恢复申请。
3. 没有已验证 RCA 时不能申请恢复。
4. 未审批的恢复申请不能执行。
5. Sandbox 执行会保存恢复前状态、动作结果和验证结果。
6. 验证成功时状态为 `SUCCEEDED`。
7. 验证失败时写入 rollback 记录，状态为 `ROLLED_BACK` 或 `FAILED`。
8. 重复执行同一个已审批申请返回同一个执行记录，不重复执行动作。
