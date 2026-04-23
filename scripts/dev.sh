#!/usr/bin/env bash
# dev.sh — Start both the FastAPI backend and Next.js frontend in development mode.
#
# Usage:
#   ./scripts/dev.sh
#
# Requirements:
#   - Python venv at .venv/ with uvicorn and all project dependencies installed.
#   - Node.js (>= 18) with npm or pnpm available.
#   - cd into the project root before running.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
FRONTEND="${ROOT}/frontend"
BACKEND_URL="http://127.0.0.1:8000"
FRONTEND_URL="http://localhost:3000"
PACKAGED_SIDECAR_PATTERN="Markdown Reader.app/Contents/MacOS/markdown-reader-backend"

BACKEND_PID=""
FRONTEND_PID=""

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
  if [ -n "${FRONTEND_PID}" ]; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  exit 0
}

trap cleanup SIGINT SIGTERM

# If a packaged desktop app is still running, its embedded sidecar backend can occupy port 8000.
# Stop it proactively so dev backend can start deterministically.
if pgrep -f "${PACKAGED_SIDECAR_PATTERN}" >/dev/null 2>&1; then
  echo "▶ Found packaged sidecar backend process; stopping it for dev mode…"
  pkill -f "${PACKAGED_SIDECAR_PATTERN}" || true
fi

# ── Start FastAPI backend ─────────────────────────────────────────────────────
if is_port_in_use 8000; then
  if curl -fsS "${BACKEND_URL}/api/health" >/dev/null 2>&1; then
    echo "▶ Reusing existing FastAPI backend on ${BACKEND_URL}"
  else
    echo "ERROR: Port 8000 is already in use, but it does not look like this app's backend."
    echo "Please stop the process using port 8000, then run ./scripts/dev.sh again."
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

# ── Start Next.js frontend ────────────────────────────────────────────────────
if is_port_in_use 3000; then
  if curl -fsS "${FRONTEND_URL}" >/dev/null 2>&1; then
    echo "▶ Reusing existing frontend on ${FRONTEND_URL}"
  else
    echo "ERROR: Port 3000 is already in use, but frontend is not reachable."
    echo "Please stop the process using port 3000, then run ./scripts/dev.sh again."
    cleanup
  fi
else
  echo "▶ Starting Next.js frontend on ${FRONTEND_URL} …"
  cd "$FRONTEND"
  if [ ! -f "package.json" ]; then
    echo "ERROR: frontend/package.json not found."
    cleanup
  fi
  if command -v pnpm &>/dev/null; then
    pnpm dev &
  else
    npm run dev &
  fi
  FRONTEND_PID=$!
  echo "  Frontend PID: $FRONTEND_PID"
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "ERROR: Frontend failed to start."
    cleanup
  fi
fi

echo ""
echo "✅ Services available."
echo "   Backend:  ${BACKEND_URL}"
echo "   Frontend: ${FRONTEND_URL}"
echo ""
echo "Press Ctrl+C to stop both."

wait
