#!/usr/bin/env bash
# SelfHealOps quality gate — lint, format check, typecheck, build, tests.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
RC=0

log()   { printf '\033[1;34m[check]\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31m[fail ]\033[0m %s\n' "$*"; RC=1; }

run() { # run <label> <workdir> <cmd...>
  local label="$1" workdir="$2"; shift 2
  log "$label"
  if ( cd "$workdir" && "$@" ); then :; else fail "$label"; fi
}

if [[ -x "$VENV_DIR/bin/python" ]]; then
  PY="$VENV_DIR/bin/python"
  run "ruff format check" "$BACKEND_DIR" "$PY" -m ruff format --check .
  run "ruff lint"         "$BACKEND_DIR" "$PY" -m ruff check .
  run "backend tests"     "$BACKEND_DIR" "$PY" -m pytest -q
else
  fail "backend checks: virtualenv missing at backend/.venv — run ./scripts/setup.sh first"
fi

if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
  run "frontend typecheck" "$FRONTEND_DIR" npm run typecheck
  run "frontend build"     "$FRONTEND_DIR" npm run build
  run "frontend tests"     "$FRONTEND_DIR" npm run test -- --run
else
  fail "frontend checks: node_modules missing — run ./scripts/setup.sh first"
fi

if [[ "$RC" -eq 0 ]]; then log "All checks passed."; else log "Some checks failed."; fi
exit "$RC"
