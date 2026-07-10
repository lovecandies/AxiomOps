# Phase 8：React 控制台与五分钟演示蓝图

## 目标

把已验证的 Incident → Evidence → RCA → 人工审批 → Sandbox 恢复 → 验证闭环，呈现在一个本地 React 控制台中。控制台不绕过后端权限或直接操作 Lab。

## 最小页面

1. Incident 列表：选择既有 Incident 或创建一个固定的 inventory 故障 Incident。
2. Incident 详情：显示状态时间线、Evidence、RCA、Trace ID。
3. Recovery 面板：按 Commander、Approver、Operator 三个身份依次请求、审批、执行，并展示验证结果。

## 接口边界

- 新增 `GET /incidents`：控制台列表数据。
- 新增 `GET /incidents/{id}/events`：SSE 推送 Incident 与 Outbox 状态变化；不承担 Agent 自由文本流。
- 原有恢复接口保持角色 Header 与自审批拦截，前端只负责传递演示身份。
- 新增两类只读 Evidence：`FAULT_STATE` 读取固定的库存故障状态，`ORDER_FLOW_PROBE` 探测固定订单链路；二者不允许浏览器传入任意目标地址。

## 当前批次与历史审计

- 每次“刷新当前证据批次”会采集 Metrics、Health、Fault State、Order Flow 四条新 Evidence。
- 前端仅展示每类最新 Evidence，历史记录默认折叠；MySQL 与文件产物不删除，继续满足不可变审计约束。
- RCA 仅在当前批次具备四类证据后允许发起。模型提示词要求高于 0.6 的置信度必须同时有故障状态与订单链路支持。

## 黑盒完成条件

1. 浏览器能打开列表并进入 Incident 详情。
2. 页面能创建 Incident、采集 Metrics/Health Evidence、发起 RCA。
3. 页面可显示已验证 RCA 后的审批/执行过程与恢复验证结果。
4. 浏览器打开 SSE 连接后，Incident 状态或 Outbox 状态变化会刷新时间线。
5. README 中的命令可在本地完成一次五分钟演示。
