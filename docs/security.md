# Security

SelfHealOps performs automated actions against CI/CD systems, so its security model is
deliberately conservative. This document explains the threat model and the safeguards
that are enforced in code (and tested).

## Principles

1. **Least privilege** — only the fixed, minimum set of actions can ever run.
2. **No arbitrary execution** — there is no code path that runs shell commands, eval,
   or user-supplied scripts.
3. **Human-in-the-loop** — risky actions require explicit approval, enforced on the
   server.
4. **Fail closed** — when validation or verification is inconclusive, nothing mutates.
5. **Auditability** — every decision leaves a durable record.

## Threat model & mitigations

### Arbitrary command execution
- **Risk:** A remediation that executes attacker-controlled input.
- **Mitigation:** Remediations are selected from a hard-coded allowlist
  (`app/remediation/registry.py`). Parameters are typed and length-bounded. There is
  no shell, `subprocess`, or `eval` path in the execution flow. The single
  side-effecting action, `RERUN_WORKFLOW`, calls one fixed GitHub REST endpoint for an
  existing run id.

### SSRF / malicious repository URL
- **Risk:** A crafted repository URL causes the server to call an internal service.
- **Mitigation:** Repository URLs are validated against a strict pattern requiring
  `https://github.com/<owner>/<repository>`. Only the GitHub API base URL is used for
  outbound calls.

### Approval bypass
- **Risk:** A client executes a plan without (or with stale) approval.
- **Mitigation:** The execute endpoint re-loads the plan and, when
  `requires_approval` is set, requires `status == approved` **and** a matching
  approval whose `plan_hash` equals the current plan hash. A mismatch invalidates the
  plan (status `invalidated`) and returns `409`. The client UI is convenience only;
  enforcement is server-side.

### Replay / duplicate execution
- **Risk:** Executing the same approved plan repeatedly.
- **Mitigation:** The execute endpoint checks for an existing successful execution and
  returns `409 Conflict` before doing any work.

### Secret leakage
- **Risk:** Tokens or secrets appear in logs, API responses, or the database.
- **Mitigation:**
  - The GitHub token is read from configuration and used only to build the
    `Authorization` header. It is never persisted or returned by the API.
  - `app/security.py` redacts secrets from log content and truncates logs to
    `MAX_LOG_CHARS`.
  - `.gitignore`/`.dockerignore` exclude `.env` files; `.env.example` documents
    configuration without real values.

### Oversized payloads / log flooding
- **Risk:** Huge request bodies or gigantic workflow logs exhaust memory.
- **Mitigation:** A middleware rejects bodies larger than `MAX_REQUEST_BODY_BYTES`
  (HTTP 413). Logs are truncated to `MAX_LOG_CHARS`.

### Cross-origin abuse
- **Risk:** A malicious site drives the local API.
- **Mitigation:** CORS is restricted to `CORS_ORIGINS`; credentials are disabled.

### Prompt injection via logs (LLM provider)
- **Risk:** Untrusted log content influences an LLM to propose unsafe actions.
- **Mitigation:** The LLM never chooses actions — planning is driven by the
  deterministic classifier and the fixed registry. The LLM only enriches diagnosis
  text and is always optional, with a rules fallback. Even a fully compromised LLM
  output cannot introduce a non-allowlisted action.

## What SelfHealOps will *not* do

- Run arbitrary shell/CLI commands.
- Modify repository code automatically. `RECOMMEND_*` actions only record reviewable
  recommendations.
- Execute without server-side approval for medium/high/critical risk plans.
- Return or log secrets/tokens.

## Operational hardening checklist

- [ ] Provide `GITHUB_TOKEN` with the minimum scopes (`public_repo`/`repo`,
      `actions:read`, and `actions:write` only if you need re-runs).
- [ ] Keep `POLL_INTERVAL_SECONDS` at a sane value; `0` disables background polling.
- [ ] Restrict `CORS_ORIGINS` to trusted origins in production.
- [ ] Terminate TLS in front of the app (nginx/reverse proxy) and avoid exposing the
      backend port publicly.
- [ ] Back up the SQLite volume (`backend-data`) if you rely on incident history.
- [ ] Review executed actions via `/api/v1/executions` and decisions via
      `/api/v1/audit-logs`.

## Relevant code

- `backend/app/security.py` — redaction and log truncation helpers.
- `backend/app/remediation/registry.py` — action allowlist, parameter schemas, plan
  hashing.
- `backend/app/services/remediation_service.py` — approval + hash + duplicate checks,
  allowlist dispatch.
- `backend/app/api/v1/remediations.py` — endpoint-level enforcement and status codes.
- `backend/tests/test_security.py`, `backend/tests/test_remediation_safety.py` — tests
  covering these guarantees.
