#!/usr/bin/env bash
# SelfHealOps local development launcher.
# Starts the FastAPI backend and the Vite dev server, then cleans up on exit.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

log()  { printf '\033[1;34m[dev  ]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

[[ -x "$VENV_DIR/bin/python" ]] || die "Backend venv missing. Run ./scripts/setup.sh first."
[[ -d "$FRONTEND_DIR/node_modules" ]] || die "Frontend deps missing. Run ./scripts/setup.sh first."
[[ -f "$ROOT_DIR/.env" ]] || { cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"; log "Created .env from example"; }

PIDS=()
cleanup() {
  log "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

log "Starting backend on http://localhost:8000 ..."
( cd "$BACKEND_DIR" && "$VENV_DIR/bin/python" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 ) &
PIDS+=($!)

log "Starting frontend on http://localhost:5173 ..."
( cd "$FRONTEND_DIR" && npm run dev ) &
PIDS+=($!)

log "Services running. Press Ctrl+C to stop."
wait
