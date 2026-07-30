# 五分钟演示脚本

这条演示路径用于快速展示 AxiomOps 的完整故障处置闭环：从故障注入、证据采集、多 Agent RCA，到审批恢复和恢复验证。

## 演示目标

在五分钟内证明三件事：

1. 系统不是只生成一段文本，而是围绕 Incident 保存证据、审计和恢复记录。
2. Agent 的诊断结论必须引用真实 Evidence，并经过独立验证。
3. 恢复动作不由模型直接执行，而是经过审批、角色门禁和后端验证。

## 准备环境

```powershell
.\scripts\start_lab.ps1
.\scripts\start_control_plane.ps1
cd frontend
npm run dev
```

打开 Vite 输出的本地地址，进入 AxiomOps 控制台。

## 推荐演示：库存服务不可用

### 1. 选择故障

在控制台选择“库存服务不可用”，页面会自动填充故障描述：

```text
库存依赖返回 503，订单链路可能被阻断。
```

期望现象：

- 页面展示 Incident 严重级别。
- 右侧提示当前要创建并进入调查。

### 2. 创建 Incident

点击“创建并进入调查”。

期望现象：

- 页面生成 Trace ID。
- Incident 状态进入接收或调查阶段。
- SSE 时间线开始刷新审计事件。

### 3. 自动采集 Evidence

点击证据采集或刷新按钮。

系统会补齐六类 Evidence：

| Evidence | 说明 |
| --- | --- |
| 指标快照 | 从 Prometheus 读取错误率、延迟或下游失败信号 |
| 服务健康 | 检查目标服务是否可访问 |
| 故障状态 | 读取 Lab 中当前注入的 Ground Truth 状态 |
| 订单链路探测 | 真实访问订单接口，观察下游影响 |
| 调用链路快照 | 记录订单服务调用库存服务的轻量 Trace |
| 变更事件快照 | 记录故障注入或恢复操作的 Change Event |

期望现象：

- Evidence 列表出现 6 类当前批次证据。
- 历史 Evidence 不堆积在主界面，但仍保留在审计数据中。

### 4. 启动 RCA

点击启动 RCA。

期望现象：

- Commander 读取 Incident 与 Evidence Capsule。
- Metrics / Logs-Trace / Change Investigator 分工调查。
- RCA Synthesizer 生成结构化根因。
- Independent Verifier 检查证据引用和因果支撑。

最终 RCA 应围绕库存服务不可用或库存下游异常展开，而不是凭空给出泛化结论。

### 5. 审批与恢复

在 RCA 通过后，发起恢复请求并完成审批。

期望现象：

- 系统拒绝自审批。
- 只有通过审批后，Operator 才能执行受限恢复动作。
- 恢复执行记录写入控制面。

### 6. 验证恢复

执行恢复后，系统验证：

- Inventory 健康检查恢复。
- Order → Inventory 订单链路恢复。
- 恢复审计事件与验证结果保存。

## 讲解顺序

推荐按下面顺序讲，不要先陷入代码细节：

1. 先讲业务问题：微服务故障排查证据分散，恢复动作有风险。
2. 再讲系统边界：Agent 诊断，后端执行，Evidence 约束二者。
3. 然后讲 Agent：Commander 规划，Investigator 分工，Synthesizer 合成，Verifier 核验。
4. 接着讲后端：MySQL 最终事实源，Outbox + RocketMQ 可靠调度，Redis Checkpoint，Qdrant 已验证记忆。
5. 最后讲结果：固定故障集、可重复闭环、Evidence 引用覆盖和恢复验证。

## 常见演示风险

| 风险 | 处理方式 |
| --- | --- |
| 模型 Key 未配置 | 只展示 Evidence 采集、受控工具选择和恢复闭环；RCA 可说明需要兼容 Chat Endpoint |
| Docker 服务未完全启动 | 先访问健康检查接口，确认 Lab 和 Control Plane 均 ready |
| 前端无刷新 | 检查 Vite 地址、Control Plane 地址和浏览器控制台请求 |
| Evidence 历史较多 | 使用当前批次视图展示主链路，历史记录保留用于审计 |
