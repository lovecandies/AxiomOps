# Phase 3：Typed Tools 与不可变 Evidence 蓝图

## 阶段目标

让后续 Agent 只能通过有类型、可审计、只读的工具获取外部事实，并把每次原始观察保存为可校验的 Evidence。本阶段不做推理、RCA 或恢复动作。

## 最小业务闭环

```text
Incident
  -> POST /incidents/{id}/tools/metrics
  -> Typed Input 校验 + 固定 PromQL 模板
  -> Prometheus 原始响应
  -> 文件卷原子写入 JSON
  -> MySQL Evidence 元数据 + SHA-256
  -> GET /evidence/{id}/content 重新验 hash 后返回
```

服务健康工具沿用同一执行与保存路径，只替换数据源和输入类型。

## 工具边界

### Metrics Snapshot Tool

- 输入：`signal` 枚举，而不是任意 PromQL。
- 信号：Order 总耗时、Order 下游失败、Inventory 当前故障模式。
- 输出：执行过的 PromQL、Prometheus 原始响应、采集时间和耗时。

### Service Health Tool

- 输入：`service` 枚举，只允许 Order 或 Inventory。
- 输出：目标 URL、HTTP 状态、响应体、采集时间和耗时。

两个工具均只读；不允许工具修改 Incident、注入故障或执行恢复。

## Evidence 契约

- MySQL 保存：Evidence ID、Incident ID、类型、工具名、输入、来源、文件路径、字节数、SHA-256、采集时间。
- 文件系统保存：完整 Tool Observation JSON。
- 文件使用排他创建和同目录原子替换，已存在目标拒绝覆盖。
- MySQL Trigger 拒绝 `UPDATE` 与 `DELETE` Evidence。
- 读取原始内容时重新计算 SHA-256；不一致返回完整性错误。

## 一致性取舍

文件系统与 MySQL 无法共享本地事务，因此采用“先原子写文件、再插入元数据”。数据库失败可能留下无引用孤儿文件，但不会产生指向缺失内容的 Evidence；孤儿可安全扫描清理。本阶段不增加分布式事务。

## 黑盒完成条件

1. 创建 Incident 后，两个 Typed Tool 都能从真实 Phase 1 Lab 生成 Evidence。
2. Evidence 列表只返回元数据；内容端点校验哈希后返回原始观察。
3. 非法 signal/service 在访问数据源前返回 `422`。
4. SQL `UPDATE`/`DELETE` Evidence 被数据库 Trigger 拒绝。
5. 修改 Evidence 文件后，内容端点返回完整性冲突而不是静默返回。
