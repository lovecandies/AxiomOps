# ADR 005：为何 Memory 不能替代 Incident Evidence

## 背景

Qdrant 可能召回语义相似但根因或环境不同的历史 RCA。

## 决策

已验证历史 RCA 只用于提出假设。当前结论仍须引用当前 Incident 的 Evidence ID，并经 Verifier 批准。

## 影响

Memory 可以加快调查，但不能悄然成为事实来源。Phase 12 会显式度量历史 Memory 误导行为。
