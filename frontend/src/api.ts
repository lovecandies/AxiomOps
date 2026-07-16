export const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:18000";

export type Incident = { id: string; title: string; service: string; severity: string; summary: string; status: string; created_at: string; events: { event_type: string; created_at: string }[]; outbox: { status: string; event_type: string }[] };
export type Evidence = { id: string; kind: string; tool_name: string; observed_at: string; content_sha256: string };
export type Run = { id: string; status: string; model: string; duration_ms: number | null; verification: { decision: string; rationale: string } | null; steps: { node_name: string; role: string | null }[] };
export type Report = { run_id: string; summary: string; root_cause: string; confidence: number; evidence_ids: string[]; verification: { decision: string; rationale: string } };
export type Approval = { id: string; status: string; requested_by: string; approved_by: string | null; action: string; reason: string };
export type Execution = { id: string; status: string; sandbox: boolean; verification: { passed?: boolean; inventory_health_status?: number; order_flow_status?: number }; before_state: Record<string, unknown>; rollback: Record<string, unknown> | null; error: string | null };
export type IncidentDraft = { title: string; service: string; severity: string; summary: string };

async function request<T>(path: string, init?: RequestInit): Promise<{ data: T; traceId: string | null }> {
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status})`);
  return { data: body as T, traceId: response.headers.get("X-AxiomOps-Trace-Id") };
}

export const api = {
  listIncidents: () => request<Incident[]>("/incidents"),
  createIncident: (draft: IncidentDraft) => request<Incident>("/incidents", { method: "POST", headers: { "Idempotency-Key": `console-${crypto.randomUUID()}` }, body: JSON.stringify(draft) }),
  evidence: (id: string) => request<Evidence[]>(`/incidents/${id}/evidence`),
  metrics: (id: string) => request<Evidence>(`/incidents/${id}/tools/metrics`, { method: "POST", body: JSON.stringify({ signal: "inventory_active_fault" }) }),
  health: (id: string) => request<Evidence>(`/incidents/${id}/tools/health`, { method: "POST", body: JSON.stringify({ service: "inventory-service" }) }),
  faultState: (id: string) => request<Evidence>(`/incidents/${id}/tools/fault-state`, { method: "POST", body: "{}" }),
  orderFlow: (id: string) => request<Evidence>(`/incidents/${id}/tools/order-flow`, { method: "POST", body: "{}" }),
  startRca: (id: string) => request<Run>(`/incidents/${id}/rca-runs`, { method: "POST" }),
  report: (id: string) => request<Report>(`/incidents/${id}/rca`),
  requestRecovery: (id: string, runId: string) => request<Approval>(`/incidents/${id}/recovery-approvals`, { method: "POST", headers: role("commander", "console-commander"), body: JSON.stringify({ run_id: runId, action: "reset_inventory_fault", reason: "Verified RCA identifies an active inventory fault." }) }),
  approve: (id: string) => request<Approval>(`/recovery-approvals/${id}/approve`, { method: "POST", headers: role("approver", "console-approver"), body: JSON.stringify({ comment: "Approved for sandbox recovery." }) }),
  execute: (id: string) => request<Execution>(`/recovery-approvals/${id}/execute`, { method: "POST", headers: role("operator", "console-operator") }),
};
function role(roleName: string, user: string) { return { "X-AxiomOps-Role": roleName, "X-AxiomOps-User": user }; }
