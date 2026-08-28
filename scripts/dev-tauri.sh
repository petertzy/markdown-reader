#!/usr/bin/env bash
# dev-tauri.sh — Start FastAPI backend and Tauri desktop shell in development mode.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="${ROOT}/frontend"
BACKEND_PORT="${MARKDOWN_READER_BACKEND_PORT:-8000}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"

BACKEND_PID=""
PYTHON_RUNNER=()

echo "▶ Preparing Markdown Reader development environment…"

resolve_python_runner() {
  if [ -x "${ROOT}/.venv/bin/python" ]; then
    PYTHON_RUNNER=("${ROOT}/.venv/bin/python")
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    PYTHON_RUNNER=("uv" "run" "python")
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    PYTHON_RUNNER=("python3")
    return 0
  fi

  return 1
}

backend_healthy() {
  curl --connect-timeout 1 --max-time 2 -fsS "$1/api/health" >/dev/null 2>&1
}

start_backend() {
  local port="$1"
  local url="http://127.0.0.1:${port}"

  if backend_healthy "${url}"; then
    BACKEND_PORT="${port}"
    BACKEND_URL="${url}"
    echo "▶ Reusing existing FastAPI backend on ${BACKEND_URL}"
    return 0
  fi

  echo "▶ Starting FastAPI backend on ${url} …"
  cd "$ROOT"
  "${PYTHON_RUNNER[@]}" -m uvicorn backend.main:app --host 127.0.0.1 --port "${port}" --reload &
  BACKEND_PID=$!
  sleep 1

  if kill -0 "$BACKEND_PID" 2>/dev/null; then
    BACKEND_PORT="${port}"
    BACKEND_URL="${url}"
    echo "  Backend PID: $BACKEND_PID"
    return 0
  fi

  BACKEND_PID=""
  return 1
}

wait_for_backend() {
  local url="$1"
  local attempt
  for attempt in $(seq 1 20); do
    if backend_healthy "${url}"; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

cleanup() {
  echo ""
  echo "⏹ Stopping…"
  if [ -n "${BACKEND_PID}" ]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT
trap 'trap - EXIT; cleanup; exit 130' SIGINT SIGTERM

if ! resolve_python_runner; then
  echo "ERROR: Python is not available. Install dependencies with 'uv sync --extra dev' or install Python 3.11+."
  exit 1
fi

if ! "${PYTHON_RUNNER[@]}" -c "import uvicorn" >/dev/null 2>&1; then
  echo "ERROR: Python dependencies are not installed. Run 'uv sync --extra dev' from the project root."
  exit 1
fi

if ! start_backend "${BACKEND_PORT}"; then
  echo "▶ Backend port ${BACKEND_PORT} is unavailable; trying nearby ports…"
  for candidate_port in $(seq 8001 8020); do
    if start_backend "${candidate_port}"; then
      break
    fi
  done
fi

if ! wait_for_backend "${BACKEND_URL}"; then
  echo "ERROR: Backend failed to start."
  exit 1
fi

echo ""
echo "▶ Launching Tauri desktop shell in development mode …"
echo "   Frontend dev server will be started by Tauri via frontend/src-tauri/tauri.conf.json"
echo "   Backend is ${BACKEND_URL} in debug mode"
echo ""

cd "$FRONTEND"
MARKDOWN_READER_BACKEND_PORT="${BACKEND_PORT}" \
NEXT_PUBLIC_API_BASE_URL="${BACKEND_URL}" \
npx tauri dev
