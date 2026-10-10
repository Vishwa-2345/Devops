# SelfHealOps

**Agentic AI-based self-healing DevOps automation.**

SelfHealOps watches GitHub Actions workflow runs, detects failures, diagnoses their
root cause, proposes **allowlisted** remediations, enforces a **human approval gate**
for risky changes, executes the remediation, and verifies the result — all backed by
an auditable agent-event log.

It is designed as a practical, safe reference implementation: real GitHub REST
integration (no mock data in production), a deterministic rules-based diagnostic
engine that works with **no external services**, an optional local LLM (Ollama)
enrichment path, and a strict security model that never runs arbitrary shell
commands.

---

## Table of contents

1. [Overview](#1-overview)
2. [Problem statement](#2-problem-statement)
3. [Architecture](#3-architecture)
4. [Main features](#4-main-features)
5. [Technology stack](#5-technology-stack)
6. [Repository structure](#6-repository-structure)
7. [Prerequisites](#7-prerequisites)
8. [First-time installation](#8-first-time-installation)
9. [Local development](#9-local-development)
10. [Docker Compose deployment](#10-docker-compose-deployment)
11. [Environment variables](#11-environment-variables)
12. [GitHub token configuration](#12-github-token-configuration)
13. [GitHub permissions required per operation](#13-github-permissions-required-per-operation)
14. [How to connect a repository](#14-how-to-connect-a-repository)
15. [Workflow monitoring and failure analysis](#15-workflow-monitoring-and-failure-analysis)
16. [Diagnosis and remediation workflow](#16-diagnosis-and-remediation-workflow)
17. [Approval and risk-safety model](#17-approval-and-risk-safety-model)
18. [Verification and incident lifecycle](#18-verification-and-incident-lifecycle)
19. [How to run tests](#19-how-to-run-tests)
20. [Troubleshooting](#20-troubleshooting)
21. [Known limitations](#21-known-limitations)
22. [Moving the project to another computer](#22-moving-the-project-to-another-computer)
23. [Data persistence and backup](#23-data-persistence-and-backup)
24. [Security notes](#24-security-notes)

---

## 1. Overview

SelfHealOps turns a failing GitHub Actions run into a reviewed, auditable,
human-approved remediation. It never mutates anything on its own: analysis and
planning stop at an approval gate, and the only externally-mutating action it can
perform is re-running a workflow.

- Backend: FastAPI + SQLAlchemy (SQLite) + LangGraph agent orchestration.
- Frontend: React + TypeScript SPA served by nginx in Docker, Vite in development.
- No external services are required. A GitHub token and Ollama are both optional.

## 2. Problem statement

CI failures are common but the response loop is manual: someone notices a red
build, opens the logs, guesses at a cause, decides whether it is safe to retry,
executes a fix, and confirms it worked. That loop is slow, inconsistent, and
usually unaudited.

SelfHealOps automates the *safe* parts of that loop — detection, log retrieval,
classification, remediation proposals, approval bookkeeping, execution and
verification — while keeping humans firmly in control of anything that changes
external state. It is a reference for how to build an agentic operations tool
without handing an LLM a shell.

## 3. Architecture

```
React + TS (Vite)  ──HTTP/JSON──▶  FastAPI (/api/v1)
      │                                  │
      │                                  ├─ LangGraph agent workflow
      │                                  │     entry → monitoring → diagnosis
      │                                  │          → planning → risk → approval
      │                                  │          → remediation → verification
      │                                  │
      │                                  ├─ GitHub REST client (httpx)
      │                                  │
      │                                  └─ SQLAlchemy → SQLite (/data volume)
```

Layers:

- **API layer** — `backend/app/api/v1/` (repositories, workflows, incidents,
  remediations, agents, executions, audit logs, settings, health).
- **Service layer** — `backend/app/services/` (sync, remediation, monitoring
  scheduler, audit, GitHub provider).
- **Agent layer** — `backend/app/agents/` (LangGraph state graph and nodes).
- **Integration layer** — `backend/app/github/` (REST client + response normalizer)
  and `backend/app/llm/` (rules / ollama providers).

See [`docs/architecture.md`](docs/architecture.md) for the full design and data
flow.

## 4. Main features

- **Repository monitoring** — connect canonical GitHub HTTPS URLs, synchronize
  workflow runs, and detect failed runs.
- **Incident management** — failed runs become persistent incidents with a
  classified failure category and severity.
- **Agentic diagnosis** — a deterministic rules engine classifies failures into 12
  categories with evidence and confidence; an optional LLM provider (Ollama)
  enriches the diagnosis and always falls back to rules.
- **Allowlisted remediation** — plans are built from a fixed registry of 4 actions;
  parameters are schema-validated. No arbitrary commands exist anywhere in the
  codebase.
- **Human-in-the-loop approval** — medium/high/critical risk plans require explicit
  approval, enforced **server-side** with plan-hash invalidation.
- **Execution + verification** — execution is dispatched only through the allowlist,
  and success is reported only after an observable state change confirms it.
- **Full auditability** — every agent step emits an `AgentEvent`; every decision
  writes an `AuditLog`.
- **Dashboard** — a React/TypeScript SPA for repositories, workflows, incidents,
  remediation proposals, approvals, executions, agent activity, and settings.

## 5. Technology stack

| Layer | Technology |
| --- | --- |
| Backend framework | FastAPI, Uvicorn |
| Data | SQLAlchemy 2.x, SQLite (WAL) |
| Agents | LangGraph state graph |
| HTTP client | httpx (GitHub REST) |
| Config | pydantic-settings, `.env` |
| Frontend | React 18, TypeScript, Vite 5 |
| Server state | TanStack React Query |
| Routing | React Router 6 |
| Styling | Tailwind CSS 3, lucide-react, Recharts |
| Tests | pytest (backend), Vitest + Testing Library (frontend) |
| Lint/format | Ruff (backend), `tsc` (frontend) |
| Packaging | Docker, Docker Compose; nginx for the SPA |

## 6. Repository structure

```
.
├── backend/                 # FastAPI service
│   ├── app/
│   │   ├── agents/          # LangGraph workflow + nodes
│   │   ├── api/v1/          # REST endpoints
│   │   ├── github/          # GitHub REST client + normalizer
│   │   ├── llm/             # rules + ollama providers
│   │   ├── remediation/     # action allowlist registry
│   │   ├── services/        # sync, remediation, monitoring, audit
│   │   ├── classifier.py    # failure classification
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── security.py      # secret redaction / log sanitization
│   │   └── main.py          # app entrypoint
│   ├── tests/               # pytest suite (mocked GitHub, isolated DB)
│   ├── data/                # local SQLite DB lives here (git-ignored)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                # React + TypeScript SPA
│   ├── src/{api,components,pages,lib,tests}
│   ├── nginx.conf           # SPA fallback + /api proxy
│   └── Dockerfile
├── docs/                    # architecture, security, demo, troubleshooting
├── scripts/                 # setup / dev / test / check
├── .github/workflows/       # CI
├── .env.example             # tracked template (copy to .env)
├── docker-compose.yml
└── LICENSE
```

## 7. Prerequisites

| Tool | Version | Required? |
| --- | --- | --- |
| Python | 3.11–3.13 (**3.12 recommended**) | Yes |
| Node.js | 20+ | Yes |
| npm | 10+ | Yes |
| Docker + Compose plugin | any recent | Optional (only for container deployment) |
| `uv` | any | Optional (faster Python installs) |

No `sudo` and no system package manager commands are used by any script.

Installing `uv` without `sudo` (optional):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# then restart your shell, or: export PATH="$HOME/.local/bin:$PATH"
```

## 8. First-time installation

Exact flow on a fresh Linux computer:

```bash
# 1. Clone and enter the project
git clone <your-repository-url> selfhealops
cd selfhealops

# 2. Set up backend + frontend dependencies and create .env
./scripts/setup.sh

# 3. Configure (optional but recommended for a full demo)
#    Edit .env and set GITHUB_TOKEN=... and/or LLM_PROVIDER=ollama
#    The file is created from .env.example only if it does not already exist.

# 4. Run the full quality gate
./scripts/check.sh

# 5a. Docker deployment (recommended)
docker compose up --build
#   or, detached:
docker compose up --build -d

# 5b. ...or local development without Docker
./scripts/dev.sh

# 6. Open the frontend and verify the backend
#   Frontend:  http://localhost:8080      (Docker)  /  http://localhost:5173  (dev)
#   Backend:   http://localhost:8000/health
#   API docs:  http://localhost:8000/docs
curl http://localhost:8000/health   # expect {"status":"ok","version":"..."}
```

`./scripts/setup.sh` never overwrites an existing `.env`, never prints secret
values, and requires no `sudo`. It reuses `backend/.venv` if present.

## 9. Local development

```bash
./scripts/dev.sh
```

This starts:

- the backend on <http://localhost:8000> (uvicorn, `--reload`), and
- the Vite dev server on <http://localhost:5173>, which proxies `/api` and
  `/health` to the backend.

Stop both with `Ctrl+C`. The SQLite database is written to
`backend/data/selfhealops.db` (created automatically).

## 10. Docker Compose deployment

```bash
cp .env.example .env    # optional: edit GITHUB_TOKEN / LLM_PROVIDER
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend (nginx) | <http://localhost:8080> |
| Backend API | <http://localhost:8000> |
| OpenAPI docs | <http://localhost:8000/docs> |

Notes:

- The frontend container proxies `/api/` and `/health` to the `backend` service on
  the Compose network, so the browser only ever talks to `:8080`.
- The backend waits for nothing and the frontend waits for the backend's healthcheck
  (`depends_on: condition: service_healthy`), so startup ordering is reliable.
- The SQLite database is stored on the **named volume** `backend-data`, mounted at
  `/data` inside the container. The container runs as an unprivileged `app` user
  that owns `/data`.
- `.env` is read by Compose for variable substitution and is **not** baked into
  either image (all `.dockerignore` files exclude `.env`, `.env.*` except
  `.env.example`, plus `*.db`, `node_modules`, `dist`, `.venv`, caches).
- `docker compose down -v` deletes the volume and **all application data**. Avoid it
  unless you intend to wipe everything.

## 11. Environment variables

All configuration is via environment variables (see [`.env.example`](.env.example)).

| Variable | Default | Purpose |
| --- | --- | --- |
| `BACKEND_HOST` | `0.0.0.0` | API bind host. |
| `BACKEND_PORT` | `8000` | Host port published for the backend. |
| `FRONTEND_PORT` | `8080` | Compose only: host port for the frontend. |
| `DATABASE_URL` | `sqlite:///./data/selfhealops.db` | SQLAlchemy URL. Docker uses `sqlite:////data/selfhealops.db`. |
| `CORS_ORIGINS` | `http://localhost:8080,http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed browser origins. |
| `ENVIRONMENT` | `production` (Compose) | Label reported by `/api/v1/settings/status`. |
| `GITHUB_TOKEN` | *(empty)* | Optional. Enables private repos, log fetching and re-runs. |
| `GITHUB_API_BASE_URL` | `https://api.github.com` | GitHub REST base URL. |
| `LLM_PROVIDER` | `rules` | `rules` (deterministic) or `ollama` (falls back to rules). |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL (Docker uses `host.docker.internal`). |
| `OLLAMA_MODEL` | *(empty)* | Ollama model name. |
| `POLL_INTERVAL_SECONDS` | `0` | Background sync interval; `0` disables polling. |
| `MAX_LOG_CHARS` | `60000` | Workflow log truncation limit. |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | Max accepted request body size. |
| `VITE_API_BASE_URL` | `/api/v1` | Frontend only. Vite reads this from `frontend/.env` or the shell, **not** from the root `.env`. The default is correct for both modes. |

## 12. GitHub token configuration

Create a token at <https://github.com/settings/tokens> and put it **only** in
`.env` (`GITHUB_TOKEN=...`). The application reads it from the environment at
runtime.

Where a token may **never** appear:

- frontend source code or frontend environment variables,
- README or documentation examples,
- Docker image layers or `docker-compose.yml` defaults,
- any committed configuration file.

`/api/v1/settings/status` reports only a boolean (`configured: true/false`) plus
human-readable text. It never returns the token value, and the token is never
written to the database. Workflow logs are passed through a redaction filter
before storage.

Without a token the app works against **public** repositories, but job-log
fetching and re-runs are unavailable (the UI states this explicitly). Re-runs
fail closed.

## 13. GitHub permissions required by each operation

| Operation | Endpoint used | Credential required |
| --- | --- | --- |
| Track a repository / read metadata | `GET /repos/{owner}/{repo}` | none (public); `repo` (private) |
| List workflow runs | `GET /repos/{owner}/{repo}/actions/runs` | none (public); `repo` (private) |
| Re-check a run during verification | `GET /repos/{owner}/{repo}/actions/runs/{id}` | as above |
| List jobs for a run | `GET .../actions/runs/{id}/jobs` | `repo` / `actions:read` |
| Fetch failure logs | `GET .../actions/jobs/{id}/logs` | `actions:read` |
| **Re-run a workflow** (`RERUN_WORKFLOW`) | `POST .../actions/runs/{id}/rerun` | `actions:write` |

Practical minimum scopes: `public_repo` (or `repo` for private repositories),
`actions:read`, and `actions:write` **only** if you want the re-run action to work.

## 14. How to connect a repository

1. Open the frontend and go to **Repositories**.
2. Enter a canonical URL such as `https://github.com/octocat/hello-world`.
3. Click **Connect**.

The URL is validated server-side: only `https://github.com/<owner>/<repo>` is
accepted. Anything else (`https://gitlab.com/...`, embedded credentials, extra
path segments) is rejected with `422`. Duplicates return `409`.

You can also use the API directly:

```bash
curl -X POST http://localhost:8000/api/v1/repositories \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://github.com/octocat/hello-world"}'
```

Removing a repository (`DELETE /api/v1/repositories/{id}`) removes its tracked
runs, incidents and plans.

## 15. Workflow monitoring and failure analysis

- **Manual sync** — `POST /api/v1/repositories/{id}/sync` (or the **Sync** button)
  paginates the Actions runs list and upserts them into the local database.
- **Failure detection** — runs whose conclusion is `failure`, `timed_out`,
  `startup_failure` or `cancelled` generate an incident (idempotently: re-syncing
  does not duplicate incidents).
- **Failure logs** — for a failed run, the monitoring agent lists the run's jobs,
  downloads the logs of up to 5 failed jobs, truncates them to `MAX_LOG_CHARS`, and
  redacts secrets before storing them for the diagnosis agent. Without
  `actions:read`, log retrieval degrades gracefully and records why.
- **Background polling** — set `POLL_INTERVAL_SECONDS` to an interval (e.g. `300`)
  to sync all tracked repositories automatically. The default `0` disables the
  scheduler entirely; the UI/API still supports manual synchronization. When
  enabled, the first sync happens after one full interval elapses.

## 16. Diagnosis and remediation workflow

The agent graph is a real LangGraph `StateGraph` compiled in
`backend/app/agents/graph.py`:

`entry → monitoring → diagnosis → planning → risk_evaluation → approval_gate →
remediation → verification`

- **Diagnosis** — the rules provider (`LLM_PROVIDER=rules`) matches log signatures
  against 12 categories (`missing_npm_dependencies`, `test_failure`,
  `typescript_error`, `build_failure`, `docker_build_failure`,
  `k8s_oomkilled`, `k8s_crashloopbackoff`, `container_failure`,
  `configuration_error`, `missing_env_var`, `authentication_failure`, plus
  `unknown`), and returns a category, confidence, probable cause, suggested next
  step and **evidence**. Setting `LLM_PROVIDER=ollama` lets a local Ollama model
  enrich the output; on any failure (no model, unreachable, malformed output) it
  falls back to the rules provider.
- **Planning** — a plan is built **only** from the fixed registry
  (`backend/app/remediation/registry.py`): `RERUN_WORKFLOW`,
  `RECOMMEND_DEPENDENCY_FIX`, `RECOMMEND_CONFIG_FIX`, `RECOMMEND_ENV_VAR_FIX`.
  Parameters are validated against the action's typed schema.
- **Execution is never implicit** — `POST /incidents/{id}/analyze` and
  `/plan-remediation` stop at the approval gate. Execution is a separate,
  explicit call.

Trigger analysis from the UI (incident detail → **Run analysis**) or:

```bash
curl -X POST http://localhost:8000/api/v1/incidents/1/analyze
```

## 17. Approval and risk-safety model

- **Risk is independent of the LLM.** `backend/app/agents/nodes/risk.py` derives the
  risk level solely from the action definition plus a fixed escalation ladder. The
  LLM cannot set, raise or lower risk, and cannot introduce an action.
- **Approval is enforced server-side.** `execute_plan` re-checks that the plan is in
  `approved` state and that a matching `approved` `Approval` row exists — regardless
  of who calls it.
- **Plan-hash invalidation.** Every plan has a hash over action + parameters + risk.
  If a plan changes after approval, its hash no longer matches, the approval is
  invalidated, the plan is marked `invalidated`, and execution returns `409`.
- **Allowlist only.** `get_action()` raises for any action not in the registry;
  `validate_parameters()` rejects unknown keys, missing required keys, wrong types
  and oversized values. There is **no shell, subprocess, `eval` or command-execution
  path anywhere in the codebase**.
- **Duplicate protection.** A plan that already has a successful execution returns
  `409` on re-execution.
- **Audit trail.** Approvals, rejections, executions and analyses are written to
  `/api/v1/audit-logs`; every agent step is an `AgentEvent` visible under
  `/api/v1/agents/activity`.

## 18. Verification and incident lifecycle

Status transitions (`Incident.status`):

```
open → diagnosing → diagnosed → planned
     → awaiting_approval → approved          (high/medium/critical risk)
     → executing → verifying
     → resolved    (verified + observed success)
     → failed      (execution or verification failed)
```

Verification is a **separate** step from execution. A successful API response is
*not* treated as success:

- `RERUN_WORKFLOW` — verification re-fetches the run from GitHub. A queued /
  in-progress re-run is `verified` (`rerun_accepted`); a completed + successful run
  is `verified` (`success`) and resolves the incident; anything else is `unverified`
  (`not_confirmed`) and fails the incident. Without credentials, verification
  reports `unverified` (`unknown`) — fail closed.
- `RECOMMEND_*` actions — these record a recommendation and mutate nothing
  externally, so they cannot be auto-verified. They are marked `unverified`
  (`manual_review_required`) and the incident is returned to `open` for a human to
  action.

## 19. How to run tests

```bash
./scripts/test.sh    # backend pytest + frontend vitest
./scripts/check.sh   # full gate: ruff format/lint, pytest, tsc, build, vitest
```

`check.sh` exits non-zero if any check fails and names the failing check. It also
**fails** (instead of silently passing) if `backend/.venv` or
`frontend/node_modules` is missing, telling you to run `./scripts/setup.sh`.

### What the tests actually cover — read this before citing "verified"

| Category | Status |
| --- | --- |
| **Automated tests using mocks** | Backend tests use `httpx.MockTransport` to simulate GitHub REST responses and run against an isolated temporary SQLite database. **No network, no credentials.** This covers the API surface, the real LangGraph orchestration, the classifier, the LLM provider fallbacks, allowlist/param rejection, approval enforcement, plan-hash invalidation, verification state transitions, the polling scheduler, and secret-leakage assertions. Frontend tests mock the API client. |
| **Tests against local containers** | Compose images build and start; both healthchecks pass; `/health`, `/api/v1/settings/status`, the nginx `/api` proxy, and the SPA fallback were verified against a running stack. |
| **Successful live GitHub integration tests** | **None automated.** There is no integration test that calls the real GitHub API. A manual, unauthenticated, **read-only** probe (`GET /repos/...`, `GET .../actions/runs`) was performed to confirm the client and normalizer work against live data. |
| **Features that remain incomplete or simulated** | `RECOMMEND_*` actions record text and do not change anything externally. Verification of a recommendation is necessarily `unverified`. Ollama enrichment was not exercised in this environment. Re-run verification against a real workflow requires a token with `actions:write`. |

## 20. Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for the full list. Common
cases:

- **"Unable to reach the SelfHealOps backend"** — confirm both containers are up
  (`docker compose ps`), the backend is healthy, and `curl
  http://localhost:8000/health` returns 200.
- **Backend container unhealthy** — check `docker compose logs backend`; the `/data`
  volume must be writable by the unprivileged `app` user.
- **Port already in use** — set `BACKEND_PORT` / `FRONTEND_PORT` in `.env`.
- **`./scripts/check.sh` fails with "virtualenv missing"** — run `./scripts/setup.sh`.
- **Public repository shows no logs** — job logs require a token with
  `actions:read`.

## 21. Known limitations

- **No authentication or authorization on the API.** SelfHealOps is a single-user
  tool for a trusted network. Do not expose it to the public internet; put it behind
  a reverse proxy / VPN and restrict `CORS_ORIGINS`.
- **Request body size limit inspects `Content-Length` only.** A chunked request
  without that header bypasses the limit.
- **SQLite is single-writer.** Fine for a single instance; use WAL (already
  enabled). For multi-instance deployments, move to a client/server database.
- **Polling is disabled by default** (`POLL_INTERVAL_SECONDS=0`); the first
  scheduled sync occurs after one full interval, not immediately at startup.
- **No automated live-GitHub test**, so live rate-limit behaviour, private-repo
  access and re-run verification are not CI-verified.
- **Only re-running a workflow is executable.** Dependency/config/env-var fixes are
  recommendations for a human, not automated edits to repository code.
- **LLM enrichment is optional and unverified here**; the rules provider is the
  supported default.

## 22. Moving the project to another computer

`.env` and Docker volumes **do not transfer through GitHub** — both are ignored on
purpose (see [Security notes](#24-security-notes)).

On the new machine:

```bash
git clone <your-repository-url> selfhealops
cd selfhealops
./scripts/setup.sh          # creates backend/.venv, installs deps, creates .env
cp .env.example .env        # (setup.sh already did this if .env was missing)
# Edit .env and re-enter GITHUB_TOKEN / LLM settings manually — they are not in git.
./scripts/check.sh
docker compose up --build
```

If you want to carry over existing incident history, copy the data separately:

```bash
# On the old machine: export the volume to a tarball
docker run --rm -v selfhealops_backend-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/selfhealops-data.tar.gz -C /data .

# Copy selfhealops-data.tar.gz to the new machine, then import it
docker volume create selfhealops_backend-data
docker run --rm -v selfhealops_backend-data:/data -v "$PWD":/backup alpine \
  tar xzf /backup/selfhealops-data.tar.gz -C /data
```

The volume name is prefixed with the Compose project name (default `selfhealops`),
so it is **local to each computer** and never shared through the repository.

## 23. Data persistence and backup

| Mode | Location | Survives |
| --- | --- | --- |
| Docker Compose | named volume `backend-data` → `/data/selfhealops.db` | container restarts, image rebuilds |
| Local development | `backend/data/selfhealops.db` | restarts (git-ignored) |
| Tests | throwaway temp-file SQLite DB | nothing (recreated per run) |

Back up by copying the volume (see [§22](#22-moving-the-project-to-another-computer))
or, for local development, copying `backend/data/selfhealops.db` plus its `-wal`
and `-shm` files while the backend is stopped.

**Warning:** `docker compose down -v` removes the named volume and all application
data. Use `docker compose down` (without `-v`) to keep it.

## 24. Security notes

- **Secrets live only in the environment.** `GITHUB_TOKEN` is read from `.env` /
  the process environment, held in memory by the GitHub client, and never persisted,
  returned by the API, or logged unredacted.
- **`.env` is never committed.** `.gitignore` excludes `.env` and `.env.*` (while
  explicitly tracking `.env.example`), and every `.dockerignore` excludes `.env`
  from build contexts. Note that `.gitignore` cannot protect a secret that was
  already committed — keep tokens out of the repository from the start, and rotate
  any credential that is ever committed.
- **No secrets in images.** Backend and frontend images copy only source and
  manifests; caches, databases, tests and `.env` are excluded.
- **The frontend holds no secrets.** Only relative URLs are used; there is no
  frontend-side credential to leak, and `VITE_*` variables are not a place for
  server secrets.
- **Redaction.** `backend/app/security.py` masks `Authorization` headers, GitHub
  PATs (`ghp_`, `gho_`, `github_pat_`), `token`/`password`/`api_key` assignments and
  private-key blocks, and truncates oversized logs.
- **Fail closed.** Missing credentials, unknown actions, unknown parameters, missing
  approvals and hash mismatches all reject rather than proceed.
- **Tests assert these guarantees** (`test_security.py`,
  `test_settings_secrets.py`, `test_remediation_safety.py`).
- **Note on GitHub push protection.** A few backend test fixtures intentionally use
  strings shaped like GitHub tokens (`ghp_...`) so the redaction tests are realistic.
  They are fixed, obviously-fake values and are not credentials, but GitHub's push
  protection may flag them. If your push is blocked, confirm in the push-protection
  prompt that they are test fixtures.

See [`docs/security.md`](docs/security.md) for the threat model and hardening
checklist.

---

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — system design and data flow.
- [`docs/security.md`](docs/security.md) — threat model and safeguards.
- [`docs/demo-guide.md`](docs/demo-guide.md) — a guided end-to-end demo.
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — common issues and fixes.

## API reference

Base path: `/api/v1`. Interactive docs at `/docs` (Swagger) and `/redoc`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness/readiness check. |
| `GET` | `/dashboard/summary` | Dashboard counts, recent incidents/events, workflow stats. |
| `GET` | `/settings/status` | Integration and runtime status (never exposes tokens). |
| `GET` | `/repositories` | List tracked repositories. |
| `POST` | `/repositories` | Connect a repository (`{"url": "https://github.com/owner/repo"}`). |
| `GET` | `/repositories/{id}` | Repository detail. |
| `DELETE` | `/repositories/{id}` | Remove a repository and its data. |
| `POST` | `/repositories/{id}/sync` | Synchronize workflow runs from GitHub. |
| `GET` | `/repositories/{id}/workflows` | Workflow runs for a repository. |
| `GET` | `/workflows` | All workflow runs (`?only_failed=true` supported). |
| `GET` | `/incidents` | List incidents (`?status=`, `?repository_id=`). |
| `GET` | `/incidents/{id}` | Incident detail (diagnoses + plans). |
| `POST` | `/incidents/{id}/analyze` | Run the diagnosis agent (stops before execution). |
| `POST` | `/incidents/{id}/plan-remediation` | Generate a remediation plan. |
| `GET` | `/remediations` | List remediation plans. |
| `GET` | `/remediations/{id}` | Remediation plan detail. |
| `POST` | `/remediations/{id}/approve` | Approve a plan. |
| `POST` | `/remediations/{id}/reject` | Reject a plan. |
| `POST` | `/remediations/{id}/execute` | Execute an approved plan. |
| `GET` | `/agents/activity` | Agent event stream. |
| `GET` | `/executions` | Execution history. |
| `GET` | `/audit-logs` | Audit log. |

## License

MIT — see [LICENSE](LICENSE).
