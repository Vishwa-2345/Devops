#!/usr/bin/env bash
# SelfHealOps test runner — backend (pytest) + frontend (vitest).
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

log() { printf '\033[1;34m[test ]\033[0m %s\n' "$*"; }
RC=0

if [[ -x "$VENV_DIR/bin/python" ]]; then
  log "Running backend tests (pytest)..."
  ( cd "$BACKEND_DIR" && "$VENV_DIR/bin/python" -m pytest -q ) || RC=1
else
  log "SKIP backend tests: venv not found (run ./scripts/setup.sh)"
fi

if [[ -d "$FRONTEND_DIR/node_modules" ]]; then
  log "Running frontend tests (vitest)..."
  ( cd "$FRONTEND_DIR" && npm run test -- --run ) || RC=1
else
  log "SKIP frontend tests: node_modules not found (run ./scripts/setup.sh)"
fi

if [[ "$RC" -eq 0 ]]; then
  log "All tests passed."
else
  log "Some tests failed."
fi
exit "$RC"
