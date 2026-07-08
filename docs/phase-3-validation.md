# Phase 3 验证记录

- 日期：2026-07-08
- 数据源：Phase 1 Inventory、Order 与 Prometheus
- 存储：MySQL Evidence 元数据 + Docker 持久化文件卷

## 自动化检查

```text
pytest: 21 passed
compileall: passed
docker compose config: passed
```

测试依赖层有一条 FastAPI/Starlette TestClient 弃用提示，不影响项目代码与测试结果。

## Typed Tool 闭环

验证 Incident：`d862bcc0-ea3d-4213-bc7a-fc9dd45f2792`。

```text
prometheus.metrics.snapshot: passed，真实 Prometheus result series = 1
http.service.health: passed，Inventory HTTP 200
Evidence metadata count: 2
内容 SHA-256 重新计算: matched
非法 signal: HTTP 422
```

## 不可变验证

验证 Incident：`fbed39d7-0217-4f5c-bbc3-aa32c19ef00b`。

```text
SQL UPDATE Evidence: rejected
SQL DELETE Evidence: rejected
文件内容被篡改后读取: HTTP 409
控制面重启后未篡改 Evidence: hash matched
```

## 迁移验证

- `mysql-migrate` 使用独立 root 迁移身份创建表与 Trigger。
- API、Relay 与 Consumer 仍使用权限较低的 `axiomops` 运行身份。
- 重复执行迁移不会重复建表，控制面只在迁移成功后启动。

## 阶段结论

Phase 3 已满足“工具输入受控、外部事实真实采集、原始证据可追溯、修改可拒绝、篡改可发现”的完成条件，可以进入 Phase 4。
