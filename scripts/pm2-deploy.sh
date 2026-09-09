#!/usr/bin/env bash
# Build and deploy the API, exhibition worker, and frontend with PM2.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
ENV_FILE="$ROOT_DIR/.env"
PYTHON="$BACKEND_DIR/.venv/bin/python"
PIP="$BACKEND_DIR/.venv/bin/pip"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

restart_if_running() {
  local process_name="$1"
  if pm2 describe "$process_name" >/dev/null 2>&1; then
    pm2 restart "$process_name" --update-env
    return 0
  fi
  return 1
}

require_command python3
require_command npm
require_command pm2

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE; copy .env.example to .env and configure production values." >&2
  exit 1
fi

# Export deployment settings for Vite's build and the PM2-managed processes.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

API_NAME="${PM2_API_NAME:-tokyo-event-map-api}"
WORKER_NAME="${PM2_WORKER_NAME:-tokyo-event-map-worker}"
WEB_NAME="${PM2_WEB_NAME:-tokyo-event-map-web}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "$BACKEND_DIR/.venv"
fi

echo "Installing backend dependencies..."
"$PIP" install -q -e "$BACKEND_DIR[translation]"
(
  cd "$BACKEND_DIR"
  "$PYTHON" scripts/translate_supabase_content.py --install-models
)

echo "Applying database migrations..."
(
  cd "$BACKEND_DIR"
  .venv/bin/alembic upgrade head
)

echo "Installing and building frontend dependencies..."
(
  cd "$FRONTEND_DIR"
  npm ci
  npm run build
)

echo "Deploying API on port $API_PORT..."
restart_if_running "$API_NAME" || pm2 start "$BACKEND_DIR/.venv/bin/uvicorn" \
  --name "$API_NAME" \
  --cwd "$BACKEND_DIR" \
  --interpreter none \
  -- app.main:app --host 0.0.0.0 --port "$API_PORT"

echo "Deploying exhibition worker..."
restart_if_running "$WORKER_NAME" || pm2 start "$PYTHON" \
  --name "$WORKER_NAME" \
  --cwd "$BACKEND_DIR" \
  --interpreter none \
  -- -m worker.main

echo "Deploying frontend on port $WEB_PORT..."
restart_if_running "$WEB_NAME" || pm2 serve "$FRONTEND_DIR/dist" "$WEB_PORT" \
  --name "$WEB_NAME" \
  --spa

pm2 save
pm2 status

echo "PM2 deployment complete."
echo "  Web: http://127.0.0.1:$WEB_PORT"
echo "  API: http://127.0.0.1:$API_PORT/docs"
