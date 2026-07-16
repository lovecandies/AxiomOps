import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Database,
  RefreshCw,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import {
  api,
  baseUrl,
  type Approval,
  type Evidence,
  type Execution,
  type Incident,
  type IncidentDraft,
  type Report,
  type Run,
} from "./api";

const FAULT_TYPES: Record<string, { name: string; impact: string; draft: IncidentDraft }> = {
  unavailable: { name: "库存服务不可用", impact: "库存依赖返回 503，订单链路可能被阻断。", draft: { title: "库存服务不可用", service: "inventory-service", severity: "SEV2", summary: "库存服务不可用：订单依赖调用将返回 503，需要核验故障状态与下游订单链路。" } },
  error_rate: { name: "库存服务错误率升高", impact: "库存调用出现间歇性失败，订单成功率可能下降。", draft: { title: "库存服务错误率升高", service: "inventory-service", severity: "SEV2", summary: "库存服务错误率升高：需要结合 Prometheus 错误指标和订单链路探测确认影响范围。" } },
  latency: { name: "库存服务响应延迟升高", impact: "库存调用耗时升高，可能推高订单端到端延迟。", draft: { title: "库存服务响应延迟升高", service: "inventory-service", severity: "SEV2", summary: "库存服务响应延迟升高：需要结合延迟指标和订单链路探测判断是否超过 SLO。" } },
};

const format = (value?: string) =>
  value
    ? new Intl.DateTimeFormat("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date(value))
    : "—";

export function App() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selected, setSelected] = useState<Incident>();
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [run, setRun] = useState<Run>();
  const [report, setReport] = useState<Report>();
  const [approval, setApproval] = useState<Approval>();
  const [execution, setExecution] = useState<Execution>();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [trace, setTrace] = useState<string | null>(null);
  const [message, setMessage] = useState("请选择一个演示 Incident，系统会告诉你下一步该做什么。");
  const [busy, setBusy] = useState(false);
  const [faultType, setFaultType] = useState("unavailable");

  const load = async () => {
    try {
      const result = await api.listIncidents();
      const unique = uniqueIncidents(result.data);
      setIncidents(unique);
      setTrace(result.traceId);
      if (!selected && unique[0]) await choose(unique[0]);
    } catch (error) {
      setMessage(`控制面不可用：${String(error)}`);
    }
  };

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!selected) return;
    const source = new EventSource(`${baseUrl}/incidents/${selected.id}/events`);
    source.addEventListener("incident", (event) => {
      const next = JSON.parse((event as MessageEvent).data) as Incident;
      setSelected(next);
      setIncidents((items) => [next, ...items.filter((item) => item.id !== next.id)]);
    });
    return () => source.close();
  }, [selected?.id]);

  async function choose(incident: Incident) {
    setSelected(incident); setEvidence([]); setRun(undefined); setReport(undefined); setApproval(undefined); setExecution(undefined); setHistoryOpen(false);
    try {
      const result = await api.evidence(incident.id);
      setEvidence(result.data); setTrace(result.traceId);
      try { const latest = await api.report(incident.id); setReport(latest.data); } catch { /* RCA is optional until prepared */ }
    } catch (error) { setMessage(String(error)); }
  }

  async function action<T>(label: string, work: () => Promise<{ data: T; traceId: string | null }>, apply: (data: T) => void) {
    setBusy(true);
    try {
      const result = await work(); apply(result.data); setTrace(result.traceId); setMessage(`${label}已完成，请继续查看下一步指引。`);
    } catch (error) {
      setMessage(`${label}失败：${error instanceof Error ? error.message : String(error)}`);
    } finally { setBusy(false); }
  }

  async function refreshEvidence() {
    if (!selected) return;
    setBusy(true);
    try {
      const round = await Promise.all([
        api.metrics(selected.id), api.health(selected.id), api.faultState(selected.id), api.orderFlow(selected.id),
      ]);
      setEvidence((items) => [...items, ...round.map((item) => item.data)]);
      setTrace(round.at(-1)?.traceId ?? null);
      setHistoryOpen(false);
      setMessage("已刷新当前证据批次：指标、健康、故障状态和订单链路均已保存为不可变审计 Evidence。");
    } catch (error) {
      setMessage(`刷新证据失败：${error instanceof Error ? error.message : String(error)}`);
    } finally { setBusy(false); }
  }

  const currentEvidence = latestEvidenceByKind(evidence);
  const historicalEvidence = evidence.filter((item) => !currentEvidence.some((current) => current.id === item.id));
  const activeStep = execution ? 4 : approval?.status === "APPROVED" ? 4 : approval ? 3 : report ? 3 : currentEvidence.length >= 4 ? 2 : 1;
  const timeline = useMemo(() => selected?.events ?? [], [selected]);

  return <main className="shell">
    <header>
      <div><p className="eyebrow">AXIOMOPS / SAFE RECOVERY DEMO</p><h1>故障处置工作台</h1><p className="subtle">按步骤完成一次可审计、可验证的 Sandbox 恢复。</p></div>
      <button className="ghost" onClick={() => void load()} disabled={busy}><RefreshCw size={16}/>刷新列表</button>
    </header>

    <section className="guide"><div className="guide-icon"><ChevronRight size={20}/></div><div><strong>当前建议</strong><p>{guideText(activeStep, report, approval, execution)}</p></div></section>

    <section className="workspace">
      <div className="toolbar">
        <label className="incident-picker"><span>选择 Incident</span>
          <select value={selected?.id ?? ""} onChange={(event) => { const item = incidents.find((incident) => incident.id === event.target.value); if (item) void choose(item); }}>
            <option value="" disabled>请选择一个 Incident</option>
            {incidents.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.severity}</option>)}
          </select>
        </label>
        <label className="fault-picker"><span>故障类型</span>
          <select value={faultType} onChange={(event) => setFaultType(event.target.value)}>{Object.entries(FAULT_TYPES).map(([key, item]) => <option key={key} value={key}>{item.name}</option>)}</select>
          <small className="fault-help">{FAULT_TYPES[faultType].impact}</small>
        </label>
        <button className="create-incident" disabled={busy} onClick={() => void action("创建故障 Incident", () => api.createIncident(FAULT_TYPES[faultType].draft), (item) => { setIncidents((items) => [item, ...items]); void choose(item); })}>创建并进入调查</button>
        <span className="trace">Trace ID：{trace ?? "等待 API 响应"}</span>
      </div>

      {!selected ? <div className="empty hero-empty">请先运行演示预置脚本，或从上方选择已有 Incident。</div> : <>
        <div className="incident-summary"><div><p className="eyebrow">{selected.severity} · {selected.status}</p><h2>{selected.title}</h2><div className="fault-description"><strong>故障含义 · {faultDescription(selected).name}</strong><p>{faultDescription(selected).impact}</p><small>调查重点：{selected.summary}</small></div></div><span>{selected.service}</span></div>
        <StepBar active={activeStep}/>

        <div className="flow">
          <Panel number="1" title="刷新当前故障证据" hint="一次刷新会采集指标、健康、故障注入状态和订单链路。旧 Evidence 不删除，默认收起为审计历史。" icon={<Database size={19}/>} done={currentEvidence.length >= 4}>
            <div className="actions"><button disabled={busy} onClick={() => void refreshEvidence()}>刷新当前证据批次（4 项）</button><button className="secondary" disabled={busy || historicalEvidence.length === 0} onClick={() => setHistoryOpen((open) => !open)}>{historyOpen ? "收起" : "查看"}历史审计（{historicalEvidence.length} 项）</button></div>
            <p className="helper">当前批次只展示每类最新的一条证据，避免历史记录堆积；所有历史数据仍可审计、不可篡改。</p>
            <EvidenceList items={currentEvidence}/>
            {historyOpen && <div className="history"><strong>历史审计记录（只读）</strong><EvidenceList items={historicalEvidence}/></div>}
          </Panel>

          <Panel number="2" title="生成并核验 RCA" hint="多 Agent 分工调查，独立验证器只允许引用已保存的 Evidence。" icon={<ShieldCheck size={19}/>} done={Boolean(report)}>
            {report ? <div className="report"><strong>已核验 · 置信度 {Math.round(report.confidence * 100)}%</strong><p>{report.root_cause}</p><small>{report.verification.rationale}</small></div> : <><p className="helper">高置信 RCA 需要“故障状态 + Prometheus 指标 + 订单链路”共同支持；证据不足时验证器会拒绝猜测。</p><button disabled={busy || currentEvidence.length < 4} onClick={() => void action("RCA", () => api.startRca(selected.id), (item) => { setRun(item); void action("读取 RCA 报告", () => api.report(selected.id), setReport); })}>使用当前证据开始多 Agent 调查</button></>}
            {run && <p className="status">本次 Run：{run.status} · {run.verification?.decision ?? "等待验证"}</p>}
          </Panel>

          <Panel number="3" title="人工审批恢复动作" hint="请求人不能审批自己的恢复请求，这是后端强制执行的角色隔离。" icon={<ClipboardCheck size={19}/>} done={approval?.status === "APPROVED"}>
            <div className="actions"><button disabled={busy || !report || Boolean(approval)} onClick={() => void action("恢复请求", () => api.requestRecovery(selected.id, report!.run_id), setApproval)}>1. Commander 请求恢复</button><button className="secondary" disabled={busy || approval?.status !== "PENDING"} onClick={() => void action("人工审批", () => api.approve(approval!.id), setApproval)}>2. Approver 审批</button></div>
            {approval && <p className="status">审批状态：{approval.status} · 动作：{approval.action}</p>}
          </Panel>

          <Panel number="4" title="执行 Sandbox 恢复并验证" hint="执行后必须同时检查库存服务与订单链路；失败会留下回滚审计记录。" icon={<Wrench size={19}/>} done={execution?.status === "SUCCEEDED"}>
            <button disabled={busy || approval?.status !== "APPROVED" || Boolean(execution)} onClick={() => void action("Sandbox 恢复", () => api.execute(approval!.id), setExecution)}>3. Operator 执行恢复</button>
            {execution && <div className={`execution ${execution.status === "SUCCEEDED" ? "success" : "failure"}`}><CheckCircle2 size={19}/><div><strong>{execution.status} · Sandbox={String(execution.sandbox)}</strong><p>恢复验证：库存服务 {execution.verification.inventory_health_status}，订单链路 {execution.verification.order_flow_status}，通过={String(execution.verification.passed)}</p>{execution.rollback && <small>已记录回滚：{JSON.stringify(execution.rollback)}</small>}</div></div>}
          </Panel>
        </div>

        <Panel number="事件" title="实时审计时间线" hint="此区域通过 SSE 接收 Incident 与 Outbox 状态变化。" icon={<Activity size={19}/>} done={false}>
          <div className="timeline">{timeline.map((event, index) => <div key={`${event.event_type}-${index}`}><span></span><strong>{event.event_type}</strong><small>{format(event.created_at)}</small></div>)}</div>
        </Panel>
      </>}
    </section>
    <p className="notice"><Activity size={16}/>{message}</p>
  </main>;
}

function guideText(step: number, report?: Report, approval?: Approval, execution?: Execution) {
  if (execution) return execution.status === "SUCCEEDED" ? "闭环已完成：请查看恢复验证结果与 Trace ID。" : "恢复未成功：请检查执行记录中的验证与回滚信息。";
  if (approval?.status === "APPROVED") return "审批已通过：现在由 Operator 执行受限的 Sandbox 恢复。";
  if (approval) return "恢复请求已创建：请使用独立 Approver 身份完成审批。";
  if (report) return "RCA 已核验：请由 Commander 发起恢复请求，进入人工审批门禁。";
  return step === 1 ? "请先采集两类 Evidence；它们是 RCA 和恢复审批的依据。" : "Evidence 已具备：请运行 RCA，或选择已预置 RCA 的演示 Incident。";
}
function StepBar({ active }: { active: number }) { return <ol className="stepbar">{["收集证据", "核验 RCA", "人工审批", "恢复验证"].map((label, index) => <li className={index + 1 <= active ? "active" : ""} key={label}><span>{index + 1}</span>{label}</li>)}</ol>; }
function Panel({ number, title, hint, icon, done, children }: { number: string; title: string; hint: string; icon: ReactNode; done: boolean; children: ReactNode }) { return <article className={`panel ${done ? "done" : ""}`}><div className="panel-head"><span className="panel-number">{number}</span><div><h3>{icon}{title}{done && <em>已完成</em>}</h3><p>{hint}</p></div></div>{children}</article>; }
function uniqueIncidents(items: Incident[]) { const seen = new Set<string>(); return items.filter((item) => { const key = `${item.title}|${item.service}|${item.severity}`; if (seen.has(key)) return false; seen.add(key); return true; }); }
function latestEvidenceByKind(items: Evidence[]) { return Object.values(items.reduce<Record<string, Evidence>>((latest, item) => { if (!latest[item.kind] || item.observed_at > latest[item.kind].observed_at) latest[item.kind] = item; return latest; }, {})); }
function EvidenceList({ items }: { items: Evidence[] }) { return <ul className="evidence">{items.length ? items.map((item) => <li key={item.id}><span>{evidenceName(item.kind)}</span><small>{item.tool_name} · {item.id.slice(0, 8)}</small></li>) : <li className="helper">尚未采集 Evidence。</li>}</ul>; }
function evidenceName(kind: string) { return ({ METRIC_SNAPSHOT: "Prometheus 指标快照", SERVICE_HEALTH: "服务健康检查", FAULT_STATE: "故障注入状态", ORDER_FLOW_PROBE: "订单链路探测" } as Record<string, string>)[kind] ?? kind; }
function faultDescription(incident: Incident) { const text = `${incident.title} ${incident.summary}`.toLowerCase(); if (text.includes("延迟") || text.includes("latency")) return FAULT_TYPES.latency; if (text.includes("错误率") || text.includes("error rate")) return FAULT_TYPES.error_rate; return FAULT_TYPES.unavailable; }
