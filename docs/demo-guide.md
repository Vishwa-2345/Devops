# Demo Guide

A guided walkthrough that exercises the full self-healing loop end to end. It works
with **public** repositories without any credentials. Providing a `GITHUB_TOKEN`
unlocks logs and the `RERUN_WORKFLOW` action (which is required for execution).

## 0. Start the app

### Docker

```bash
cp .env.example .env
# Optional but recommended for a full demo:
#   GITHUB_TOKEN=ghp_...        (scopes: repo, actions:read, actions:write)
#   LLM_PROVIDER=rules          (or ollama)
docker compose up --build
```

Open <http://localhost:8080>.

### Local development

```bash
./scripts/setup.sh
./scripts/dev.sh
```

Open <http://localhost:5173>.

## 1. Connect a repository

1. Go to **Repositories**.
2. Enter a canonical URL, e.g. `https://github.com/octocat/hello-world`.
3. Click **Connect**.

> The URL is validated: only `https://github.com/owner/repo` is accepted. An invalid
> URL shows an inline error and is not submitted.

You can also demonstrate validation by trying `https://gitlab.com/foo/bar` — it is
rejected.

## 2. Synchronize workflow runs

On the **Repositories** page, click **Sync** for the repository (or open the
repository detail and click **Sync now**).

- The response reports how many runs were fetched and how many incidents were created.
- **Workflows** shows all runs; toggle **Show failed only** to isolate failures.
- **Incidents** lists detected failures with a classified category and severity.

> Public repositories may have many or few failed runs. To guarantee failures for a
> demo, pick a repository with visible failing Actions runs, or connect your own repo
> with a deliberately failing workflow.

## 3. Analyze an incident

1. Open an incident from **Incidents** (or the dashboard).
2. Click **Run analysis**.

The agent graph runs monitoring → diagnosis → planning → risk → approval gate and
records events. On the incident page you will see:

- **Diagnosis** — category, confidence, summary, probable cause, suggested next step,
  and evidence.
- **Remediation plan** — action id, risk level, parameters, and whether approval is
  required.

> Note: analysis never executes anything. Execution is always a separate step.

## 4. Plan remediation (optional separate step)

If you want to (re)generate a plan from an existing diagnosis, click **Plan
remediation**. This runs planning → risk → approval gate only.

## 5. Approve

If the plan requires approval (`medium`/`high`/`critical`), the incident page and the
**Approvals** page show it as **Awaiting approval**.

- Click **Approve** (or **Reject**).

Approvals are bound to the exact plan via a plan hash. If the plan changes afterward,
the approval is invalidated and re-approval is required.

## 6. Execute and verify

Once a plan is approved, click **Execute remediation** on the incident page and
confirm. The server re-checks approval and the plan hash, dispatches the allowlisted
action, and records an execution.

- **Executions** lists every attempt with its status and verification status.
- Execution success is reported only after verification.
- Re-executing an already-successful plan returns `409 Conflict`.

> The only externally-mutating action is `RERUN_WORKFLOW`, which requires a token with
> `actions:write`. Without a token, execution is expected to fail verification — this
> is the safe, fail-closed behavior.

## 7. Observe agent activity

Open **Agent Activity** to see the chronological event stream emitted by each agent
(monitoring, diagnosis, planning, risk_evaluation, approval_gate, remediation,
verification). Filter by agent to follow a single incident's trace.

## 8. Review settings & security posture

**Settings** shows GitHub and LLM integration status, runtime details (version,
environment, storage, polling, backend health), and a summary of the security
posture.

## Demo checklist

- [ ] Connected a repository (invalid URL rejected).
- [ ] Synchronized runs; incidents appeared.
- [ ] Ran analysis; diagnosis + plan produced.
- [ ] Saw the agent event stream.
- [ ] Approved (or rejected) a plan.
- [ ] Executed and verified a plan (or observed fail-closed without a token).
- [ ] Confirmed duplicate execution is blocked.

## Suggested failing-repository setup (optional)

If you own a repository, add a workflow that fails deterministically, for example:

```yaml
name: demo-fail
on: [push, workflow_dispatch]
jobs:
  fail:
    runs-on: ubuntu-latest
    steps:
      - run: echo "npm ERR! missing dependency"; exit 1
```

Then connect that repository, sync, and run the flow above. The classifier will
categorize the failure and the planner will propose a corresponding action.
