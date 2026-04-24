#!/usr/bin/env bash
# dev-tauri.sh — Start FastAPI backend and Tauri desktop shell in development mode.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
FRONTEND="${ROOT}/frontend"
BACKEND_URL="http://127.0.0.1:8000"
PACKAGED_SIDECAR_PATTERN="Markdown Reader.app/Contents/MacOS/markdown-reader-backend"

BACKEND_PID=""

is_port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

cleanup() {
  echo ""
  echo "⏹ Stopping…"
  if [ -n "${BACKEND_PID}" ]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
}

trap cleanup SIGINT SIGTERM EXIT

if pgrep -f "${PACKAGED_SIDECAR_PATTERN}" >/dev/null 2>&1; then
  echo "▶ Found packaged sidecar backend process; stopping it for Tauri dev mode…"
  pkill -f "${PACKAGED_SIDECAR_PATTERN}" || true
fi

if is_port_in_use 8000; then
  if curl -fsS "${BACKEND_URL}/api/health" >/dev/null 2>&1; then
    echo "▶ Reusing existing FastAPI backend on ${BACKEND_URL}"
  else
    echo "ERROR: Port 8000 is already in use, but it does not look like this app's backend."
    echo "Please stop the process using port 8000, then run ./scripts/dev-tauri.sh again."
    exit 1
  fi
else
  echo "▶ Starting FastAPI backend on ${BACKEND_URL} …"
  cd "$ROOT"
  "$PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload &
  BACKEND_PID=$!
  echo "  Backend PID: $BACKEND_PID"
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "ERROR: Backend failed to start."
    exit 1
  fi
fi

echo ""
echo "▶ Launching Tauri desktop shell in development mode …"
echo "   Frontend dev server will be started by Tauri via frontend/src-tauri/tauri.conf.json"
echo "   Backend is fixed at ${BACKEND_URL} in debug mode"
echo ""

cd "$FRONTEND"
npx tauri dev