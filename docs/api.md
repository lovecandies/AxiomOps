# API

The control plane exposes REST endpoints for incident workflow automation and the React console. All examples assume `http://127.0.0.1:18000`.

## Health

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process liveness |
| `GET` | `/ready` | Dependency readiness |
| `GET` | `/metrics` | Prometheus metrics |

## Incidents

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/incidents` | Create an incident |
| `GET` | `/incidents` | List incidents |
| `GET` | `/incidents/{incident_id}` | Read one incident |
| `GET` | `/incidents/{incident_id}/events` | SSE audit stream |

## Evidence Tools

| Method | Path | Evidence kind |
| --- | --- | --- |
| `POST` | `/incidents/{incident_id}/tools/metrics` | `METRIC_SNAPSHOT` |
| `POST` | `/incidents/{incident_id}/tools/health` | `SERVICE_HEALTH` |
| `POST` | `/incidents/{incident_id}/tools/fault-state` | `FAULT_STATE` |
| `POST` | `/incidents/{incident_id}/tools/order-flow` | `ORDER_FLOW_PROBE` |
| `POST` | `/incidents/{incident_id}/tools/trace` | `TRACE_SNAPSHOT` |
| `POST` | `/incidents/{incident_id}/tools/change` | `CHANGE_EVENT` |
| `GET` | `/incidents/{incident_id}/tools/selection-plan` | Planned missing allowlisted tools |
| `POST` | `/incidents/{incident_id}/tools/auto-collect` | Execute the current allowlisted selection plan |
| `GET` | `/incidents/{incident_id}/evidence` | List saved evidence |

Every tool response is persisted as immutable evidence with metadata and an integrity hash.

## RCA

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/incidents/{incident_id}/rca-runs` | Start a RCA run |
| `GET` | `/incidents/{incident_id}/rca-report` | Read latest RCA report |

The RCA report contains root cause, confidence, cited evidence IDs, model-call counters, verifier decision, and audit metadata.

## Recovery

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/incidents/{incident_id}/recovery-approvals` | Request recovery |
| `POST` | `/recovery-approvals/{approval_id}/approve` | Approve recovery |
| `POST` | `/recovery-approvals/{approval_id}/execute` | Execute approved recovery |

Recovery execution is idempotent per approval and stores verification results.
