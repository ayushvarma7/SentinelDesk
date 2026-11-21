#!/usr/bin/env bash
# Start the SentinelDesk API (:8000) and the Vite frontend (:5173).
#   ./run_dev.sh             mock mode (SD_MOCK=1, default)
#   SD_MOCK=0 ./run_dev.sh   try the real pipeline (needs requirements.txt + artifacts/)
set -euo pipefail
cd "$(dirname "$0")"

export SD_MOCK="${SD_MOCK:-1}"

if [ ! -x .venv/bin/python ]; then
  PY="$(command -v python3.12 || command -v python3.11 || true)"
  [ -z "$PY" ] && { echo "Need python3.12 or 3.11 on PATH to create .venv"; exit 1; }
  "$PY" -m venv .venv
fi
.venv/bin/python -c "import fastapi, uvicorn" 2>/dev/null || .venv/bin/pip install -q -r api/requirements.txt
[ -d frontend/node_modules ] || (cd frontend && npm install)

echo "API  -> http://localhost:8000  (SD_MOCK=$SD_MOCK, docs at /docs)"
echo "UI   -> http://localhost:5173"
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir api &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT INT TERM
cd frontend && npm run dev -- --host 127.0.0.1
