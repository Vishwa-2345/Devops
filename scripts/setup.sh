#!/usr/bin/env bash
# SelfHealOps setup — creates venv, installs deps, prepares .env.
# Does NOT require sudo and never overwrites an existing .env.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"

log()  { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn ]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

check_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command '$1' not found in PATH."
}

log "Checking prerequisites..."
check_cmd python3
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
log "Found python3 ($PY_VER)"
[[ "$PY_VER" == "3.12" || "$PY_VER" == "3.11" || "$PY_VER" == "3.13" ]] || \
  warn "Python $PY_VER detected; SelfHealOps targets 3.11–3.13."

check_cmd node
check_cmd npm
log "Found node $(node --version) and npm $(npm --version)"

UV="$(command -v uv || true)"
if [[ -z "$UV" ]]; then
  warn "'uv' not found; falling back to 'python3 -m venv' + pip."
fi

# --- Backend virtual environment ---
if [[ -d "$VENV_DIR" ]]; then
  log "Reusing existing virtual environment at backend/.venv"
else
  log "Creating virtual environment at backend/.venv"
  if [[ -n "$UV" ]]; then
    (cd "$BACKEND_DIR" && uv venv --python 3.12 .venv) || \
      (cd "$BACKEND_DIR" && uv venv .venv)
  else
    python3 -m venv "$VENV_DIR"
  fi
fi

PY="$VENV_DIR/bin/python"
[[ -x "$PY" ]] || die "Virtual environment interpreter not found at $PY"

# --- Backend dependencies ---
log "Installing backend dependencies..."
if [[ -n "$UV" ]]; then
  (cd "$BACKEND_DIR" && uv pip install --python "$VENV_DIR/bin/python" -e ".[dev]")
else
  "$PY" -m pip install --upgrade pip
  (cd "$BACKEND_DIR" && "$PY" -m pip install -e ".[dev]")
fi

# --- Frontend dependencies ---
# Prefer a reproducible install when a lockfile is present.
if [[ -f "$FRONTEND_DIR/package-lock.json" ]]; then
  log "Installing frontend dependencies (npm ci)..."
  (cd "$FRONTEND_DIR" && npm ci --no-audit --no-fund)
else
  log "Installing frontend dependencies (npm install, no lockfile found)..."
  (cd "$FRONTEND_DIR" && npm install --no-audit --no-fund)
fi
[[ -d "$FRONTEND_DIR/node_modules" ]] || die "Frontend dependency install failed (node_modules missing)."

# --- Environment file ---
if [[ -f "$ROOT_DIR/.env" ]]; then
  log "Existing .env found — leaving it untouched."
else
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  log "Created .env from .env.example"
fi

# --- Configuration checks ---
log "Running configuration checks..."
"$PY" - <<'PYEOF'
import importlib.util
import sys

mods = ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "httpx", "langgraph"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    sys.exit("Missing backend modules: " + ", ".join(missing))
print("  backend dependencies OK")
PYEOF

node -e "require('fs').accessSync('$FRONTEND_DIR/node_modules'); console.log('  frontend dependencies OK')" \
  || die "Frontend dependencies are not usable (node_modules missing)."

log "Setup complete."
log "Next: ./scripts/dev.sh   (or)   docker compose up --build"
