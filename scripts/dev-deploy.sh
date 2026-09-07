#!/usr/bin/env bash
# Launch a complete local development deployment with local SQLite demo data.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/run"
ENV_FILE="$ROOT_DIR/.env"
SEED_DEMO=true

if [[ "${1:-}" == "--no-seed" ]]; then
  SEED_DEMO=false
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--no-seed]" >&2
  exit 2
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then kill "$API_PID"; fi
  if [[ -n "${WEB_PID:-}" ]] && kill -0 "$WEB_PID" 2>/dev/null; then kill "$WEB_PID"; fi
  wait "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true
  exit "$exit_code"
}

wait_for_http() {
  local url="$1"
  local process_id="$2"
  for _ in {1..30}; do
    if curl --fail --silent "$url" >/dev/null 2>&1; then return 0; fi
    if ! kill -0 "$process_id" 2>/dev/null; then
      echo "Service exited before becoming ready. See the corresponding log in $RUN_DIR." >&2
      return 1
    fi
    sleep 1
  done
  echo "Timed out waiting for $url" >&2
  return 1
}

require_command python3
require_command npm
require_command curl

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  echo "Created .env from .env.example"
fi

mkdir -p "$RUN_DIR"

if [[ ! -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  echo "Creating Python virtual environment…"
  python3 -m venv "$BACKEND_DIR/.venv"
fi

if ! "$BACKEND_DIR/.venv/bin/python" -c "import alembic, fastapi, sqlalchemy" >/dev/null 2>&1; then
  echo "Installing backend dependencies…"
  "$BACKEND_DIR/.venv/bin/pip" install -q -e "$BACKEND_DIR[dev]"
fi

if [[ ! -d "$FRONTEND_DIR/node_modules/maplibre-gl" || ! -d "$FRONTEND_DIR/node_modules/pmtiles" ]]; then
  echo "Installing frontend dependencies…"
  (cd "$FRONTEND_DIR" && npm install)
fi

echo "Applying local SQLite migrations…"
(cd "$BACKEND_DIR" && .venv/bin/alembic upgrade head)

if [[ "$SEED_DEMO" == true ]]; then
  echo "Creating idempotent demo events…"
  (cd "$BACKEND_DIR" && .venv/bin/python scripts/seed_demo.py)
fi

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
trap cleanup EXIT INT TERM

echo "Starting API on http://127.0.0.1:$API_PORT"
(
  cd "$BACKEND_DIR"
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT"
) >"$RUN_DIR/api.log" 2>&1 &
API_PID=$!

wait_for_http "http://127.0.0.1:$API_PORT/api/v1/health" "$API_PID"

echo "Starting web app on http://127.0.0.1:$WEB_PORT"
(
  cd "$FRONTEND_DIR"
  VITE_MAP_STYLE_URL="${VITE_MAP_STYLE_URL:-https://gsi-cyberjapan.github.io/optimal_bvmap/style/std.json}" \
    npm run dev -- --force --host 127.0.0.1 --port "$WEB_PORT"
) >"$RUN_DIR/web.log" 2>&1 &
WEB_PID=$!

wait_for_http "http://127.0.0.1:$WEB_PORT" "$WEB_PID"

echo
echo "Local development deployment is ready."
echo "  Web: http://127.0.0.1:$WEB_PORT"
echo "  API: http://127.0.0.1:$API_PORT/docs"
echo "  Logs: $RUN_DIR/api.log and $RUN_DIR/web.log"
echo "Press Ctrl+C to stop both services."

wait "$API_PID" "$WEB_PID"
