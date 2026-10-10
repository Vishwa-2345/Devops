# Architecture

This document describes how SelfHealOps is structured, how data flows through the
system, and how the agent workflow behaves.

## Component overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Browser (React SPA)                          │
│  Pages: Overview · Repositories · Workflows · Incidents · Approvals  │
│         Remediations · Executions · Agent Activity · Settings       │
│  Data layer: @tanstack/react-query  ·  Charts: Recharts              │
└───────────────────────────────┬──────────────────────────────────────┘
                                 │  HTTP/JSON  (fetch → /api/v1)
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         FastAPI application                          │
│  Middleware: CORS · request body size limit                          │
│  Error handlers: validation · HTTP · unhandled (consistent JSON)     │
│                                                                      │
│  Routers (/api/v1): health · dashboard · repositories · workflows    │
│                     incidents · remediations · agents · settings    │
│                                                                      │
│  Services: sync · github_provider · remediation_service ·            │
│            monitoring · audit                                        │
│                                                                      │
│  Agent layer: LangGraph state graph + nodes                          │
│  Integrations: GitHub REST (httpx) · LLM provider (rules | ollama)   │
│  Persistence: SQLAlchemy ORM → SQLite                                │
└──────────────────────────────────────────────────────────────────────┘
```

## Layers

### API layer (`app/api/v1`)

Thin HTTP handlers that validate input (Pydantic), call services/agents, and shape
responses. They never contain business logic beyond orchestration and status codes.

### Service layer (`app/services`)

- `sync.py` — fetches GitHub workflow runs, upserts them, and creates/updates
  incidents for failed runs.
- `github_provider.py` — provides a cached, injectable `GitHubClient` (also
  overridable in tests).
- `remediation_service.py` — the safety core: validates plans against the allowlist,
  enforces approval and plan-hash integrity, prevents duplicate execution, dispatches
  the single side-effecting action, and records verification.
- `monitoring.py` — optional background scheduler that periodically synchronizes
  repositories (disabled when `POLL_INTERVAL_SECONDS=0`).
- `audit.py` — writes `AuditLog` rows for decisions.

### Agent layer (`app/agents`)

LangGraph `StateGraph` over a typed `AgentState`. Nodes emit `AgentEvent` rows so the
entire reasoning trace is inspectable.

```
START → entry ─┬─(monitoring)──▶ monitoring → diagnosis → planning → risk
               │                                                     │
               │                                                     ▼
               │                                              approval_gate
               │                                              ┌──────┴───────┐
               │                       (approved / not required)      (pending /
               │                                              ▼         rejected /
               │                                        remediation     invalidated)
               │                                              │              │
               └─(remediation)───────────────────────────────┘            END
                                                              │
                                                              ▼
                                                        verification → END
```

**Invocation modes** (`graph.py`):

| Function | Entry | `execute_now` | Behavior |
| --- | --- | --- | --- |
| `run_analysis(incident_id)` | monitoring | `False` | detect → diagnose → plan → risk → approval gate. Never executes. |
| `run_planning(incident_id)` | planning | `False` | plan → risk → approval gate using an existing diagnosis. |
| `run_execution(incident_id, plan_id, actor)` | remediation | `True` | execute an approved plan → verify. |
| `run_full(incident_id, actor)` | monitoring | `True` | full pipeline; stops at the gate for approval-required plans. |

The split is intentional: **analysis never executes**. Execution only happens when
`execute_now` is true, which is set exclusively by `run_execution` / `run_full`.

### Integration layer

- **GitHub** (`app/github/client.py`, `normalizer.py`) — minimal REST client using
  `httpx`, with pagination limits, timeouts, and normalization from GitHub payloads to
  internal schema. Tests inject an `httpx.MockTransport`.
- **LLM** (`app/llm/`) — a provider interface with two implementations:
  - `rules.py` — deterministic rule-based diagnosis (always available).
  - `ollama.py` — optional local LLM enrichment; falls back to rules on any failure.
  - `factory.py` — selects the provider from `LLM_PROVIDER`.

## Data model

Nine tables (`app/models.py`):

| Table | Purpose |
| --- | --- |
| `repositories` | Connected GitHub repositories. |
| `workflow_runs` | Normalized GitHub Actions runs (unique per repo + GitHub run id). |
| `incidents` | Failures detected from failed runs, with category/severity/status. |
| `diagnoses` | Agent diagnoses (summary, probable cause, evidence, confidence). |
| `remediation_plans` | Proposed actions with parameters, risk level, status, plan hash. |
| `approvals` | Human decisions bound to a plan hash. |
| `executions` | Execution attempts with result and verification status. |
| `agent_events` | Chronological agent event log. |
| `audit_logs` | Decisions and actions for auditing. |

## End-to-end flow

1. **Connect** a repository (`POST /repositories`) — URL is validated against a strict
   GitHub pattern.
2. **Sync** (`POST /repositories/{id}/sync`) — workflow runs are fetched and stored;
   failed runs create incidents.
3. **Analyze** (`POST /incidents/{id}/analyze`) — the graph runs monitoring → diagnosis
   → planning → risk → approval gate. A diagnosis and a remediation plan are stored.
4. **Approve/Reject** (`POST /remediations/{id}/approve|reject`) — for approval-required
   plans, a human decision is recorded.
5. **Execute** (`POST /remediations/{id}/execute`) — server re-validates approval and
   the plan hash, then dispatches the allowlisted action and verifies the result.
6. **Observe** — the SPA surfaces incidents, plans, approvals, executions, and the
   agent activity stream.

## Failure classification

`app/classifier.py` maps raw log/run evidence to one of 12 categories:

`k8s_oomkilled`, `k8s_crashloopbackoff`, `missing_npm_dependencies`, `typescript_error`,
`test_failure`, `docker_build_failure`, `container_failure`, `missing_env_var`,
`authentication_failure`, `configuration_error`, `build_failure`, `unknown`.

Each match carries a severity, a probable cause, a suggested next step, and an
`automatable` flag that informs planning.

## Remediation registry

`app/remediation/registry.py` is the **only** source of executable actions:

| Action ID | Risk | Mutates external state | Notes |
| --- | --- | --- | --- |
| `RERUN_WORKFLOW` | medium | yes | Re-runs an existing GitHub Actions run (fixed endpoint). |
| `RECOMMEND_DEPENDENCY_FIX` | low | no | Records a reviewable dependency recommendation. |
| `RECOMMEND_CONFIG_FIX` | low | no | Records a reviewable configuration recommendation. |
| `RECOMMEND_ENV_VAR_FIX` | low | no | Records a reviewable env/secret recommendation. |

`compute_plan_hash(action_id, parameters, risk_level)` binds an approval to an exact
plan; if the plan changes, the previous approval is invalidated.

## Configuration & persistence

- Settings load from environment variables / `.env` (`app/config.py`).
- SQLite is the default store; Docker mounts a named volume at `/data`.
- `init_db()` runs during application lifespan startup.

## Frontend

- React 18 + TypeScript + Vite, React Router v6, React Query for server state,
  Recharts for the dashboard chart, Tailwind CSS for styling, lucide-react icons.
- `src/api/client.ts` is a typed fetch wrapper with a consistent `ApiError`.
- Shared UI primitives live in `src/components/ui.tsx` and `StatusBadge.tsx`.
