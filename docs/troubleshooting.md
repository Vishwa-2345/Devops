# Troubleshooting

Common issues and how to resolve them.

## The frontend says "Unable to reach the SelfHealOps backend"

The SPA could not reach `/api/v1`.

- **Docker:** confirm both containers are up: `docker compose ps`. The frontend must
  wait for the backend to be healthy (`depends_on: condition: service_healthy`).
  Check backend logs: `docker compose logs backend`.
- **Local dev:** make sure the backend is running on port 8000 (`./scripts/dev.sh`).
  The Vite dev server proxies `/api` and `/health` to `http://localhost:8000`.
- Verify directly: `curl http://localhost:8000/health` should return
  `{"status":"ok",...}`.

## Backend container is unhealthy

- Inspect logs: `docker compose logs backend`.
- The healthcheck calls the container's `/health`. If startup fails, look for a
  database error — the `/data` volume must be writable by the unprivileged `app` user.
- Reset a corrupt volume (destroys data):

  ```bash
  docker compose down -v
  docker compose up --build
  ```

## Port already in use

- Default ports: backend `8000`, frontend `8080`, Vite dev `5173`.
- Override with environment variables before `docker compose up`:

  ```bash
  BACKEND_PORT=8010 FRONTEND_PORT=8090 docker compose up --build
  ```

- For local dev, stop whatever holds the port or change the backend `--port` and the
  Vite proxy target.

## `./scripts/setup.sh` fails

- Ensure Python 3.11–3.13, Node 20+, and npm are on `PATH`.
- `uv` is optional; the script falls back to `python3 -m venv` + `pip`.
- If `backend/.venv` is broken, remove it and re-run:

  ```bash
  rm -rf backend/.venv backend/selfhealops_backend.egg-info
  ./scripts/setup.sh
  ```

## GitHub errors during sync

- **404 / "Not Found":** the repository is private and no token is configured, or the
  owner/name is wrong. Set `GITHUB_TOKEN` in `.env`.
- **403 rate limit:** unauthenticated requests are heavily rate-limited. Configure a
  token to raise the limit.
- **Logs are empty / re-run unavailable:** fetching logs and re-running runs requires a
  token with the right scopes (`actions:read`, `actions:write`). Without a token this
  is expected.
- **URL rejected:** only `https://github.com/owner/repo` URLs are accepted; other hosts
  or malformed URLs are intentionally rejected.

## Execution fails or reports "unverified"

- `RERUN_WORKFLOW` requires a token with `actions:write`. Without it, the action cannot
  mutate GitHub state and verification fails — this is the fail-closed behavior.
- Executing a plan that requires approval before approving returns **403**.
- Re-executing an already-successful plan returns **409 Conflict**.
- If a plan was changed after approval, execution returns **409** and invalidates the
  plan; re-approve and try again.

## Ollama / LLM issues

- Default `LLM_PROVIDER=rules` needs no external service. If you set
  `LLM_PROVIDER=ollama`:
  - Ensure Ollama is running at `OLLAMA_BASE_URL` (default `http://localhost:11434`).
  - Set `OLLAMA_MODEL`.
  - In Docker, the host Ollama is reachable at `http://host.docker.internal:11434`
    (the compose file maps `host.docker.internal` via `extra_hosts`).
- Any Ollama failure automatically falls back to the deterministic rules provider, so
  diagnosis still works.

## Dashboard shows zeros / no incidents

- Connect a repository and run a **Sync** first.
- Public repositories may have few failed runs. Try a repository with failing Actions
  runs, or use the deliberately failing workflow in the
  [demo guide](demo-guide.md#suggested-failing-repository-setup-optional).
- The dashboard counts reflect only synchronized data.

## Resetting the database

- **Local:** stop the backend and delete `backend/data/selfhealops.db`, then restart.
- **Docker:** `docker compose down -v` removes the `backend-data` volume.

## Tests

Run the full gate:

```bash
./scripts/check.sh    # ruff format/lint, pytest, tsc, vite build, vitest
```

- Backend tests use an isolated temporary SQLite database and mock GitHub via
  `httpx.MockTransport`; no network or credentials are required.
- If frontend tests fail with `ResizeObserver is not defined`, ensure
  `vitest.setup.ts` is present (it stubs `ResizeObserver` for Recharts).
- `./scripts/check.sh` **fails** (non-zero exit) if `backend/.venv` or
  `frontend/node_modules` is missing, and names the failing check. Run
  `./scripts/setup.sh` first on a fresh clone.

## Where to look next

- API/OpenAPI: <http://localhost:8000/docs>
- Architecture: [`architecture.md`](architecture.md)
- Security model: [`security.md`](security.md)
