# 上游代码迁移清单

## 来源

- 仓库：https://github.com/bcefghj/multi-agent-aiops
- 审计提交：`1cf9c917747c0e82e5da11c3fae155140d2230ff`
- Git 远程：`upstream/main`

完整上游历史已经由当前仓库的 Git 对象保存，不再保留重复 clone。后续迁移统一从 `upstream/main` 读取；主分支只接收当前 Phase 需要且经过修正、测试的文件。

## 采用的业务概念

- 告警、调查、RCA、修复、审批的业务链。
- Incident 与 Event 的区分。
- 异常检测、服务拓扑、Runbook、风险等级和审计日志等领域概念。

## 迁移映射

| 上游模块 | 计划阶段 | 处理方式 |
|---|---|---|
| `python/models/time_series.py` | Phase 1 | 保留算法主体，修复接口并增加 Ground Truth 测试 |
| `python/config/prometheus.yml` | Phase 1 | 改造成故障实验环境的采集配置 |
| `python/models/events.py` | Phase 2 | 保留事件枚举思路，按 MySQL 最终事实模型重构 |
| `python/core/event_bus.py` | Phase 2 | 保留发布/订阅接口，底层替换为 RocketMQ + Outbox |
| `python/core/knowledge_graph.py` | Phase 3/4 | 保留拓扑遍历逻辑，数据源改为服务目录，不引入 Neo4j |
| `python/agents/base_agent.py` | Phase 4 | 仅保留指标统计思路，Agent 生命周期交给 LangGraph |
| `python/agents/monitor_agent.py` | Phase 1/3 | 拆成确定性检测器与 Typed Metrics Tool |
| `python/agents/rca_agent.py` | Phase 4 | 移除写死拓扑和伪贝叶斯，改为 Evidence 驱动 RCA |
| `python/core/orchestrator.py` | Phase 4/5 | 替换为 LangGraph StateGraph、Interrupt、Checkpoint、Resume |
| `python/agents/heal_agent.py` | Phase 6 | Playbook、熔断和爆炸半径概念迁入确定性节点 |
| `python/agents/change_agent.py` | Phase 6 | 改为真实人工审批、审计和 RBAC，不再自动冒充审批人 |
| `python/api/main.py` | 分阶段 | 业务端点逐步迁移到现有 FastAPI 应用工厂 |

## 不迁移到主线

- Java、Go 三语言副本；Java 后端能力通过 MySQL、RocketMQ、Outbox、幂等和事务设计展示。
- Kafka、Neo4j、Chroma 和 OpenAI 专属配置。
- 内存 Checkpoint、内存审批、模拟执行冒充真实恢复。
- 未经实验支撑的 MTTR、误报率和准确率数字。
- 面试话术先于真实测试结果的开发方式。

## 迁移命令

查看上游文件：

```powershell
git show upstream/main:python/models/time_series.py
```

每个 Phase 只迁移清单中对应文件；迁移后必须通过当前 Phase 的黑盒验证，不能整目录覆盖。
