#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
backend_python="$repo_root/.venv/bin/python"
frontend_dir="$repo_root/provenance-frontend"

if [[ ! -f "$repo_root/.env" ]]; then
  echo "Missing .env. Copy .env.example to .env and add DATABASE_URL and MISTRAL_API_KEY."
  exit 1
fi

if [[ ! -x "$backend_python" ]]; then
  echo "Missing backend environment. Create .venv and install backend/requirements.txt."
  exit 1
fi

if [[ ! -d "$frontend_dir/node_modules" ]]; then
  echo "Missing frontend dependencies. Run: npm --prefix provenance-frontend ci"
  exit 1
fi

backend_pid=""
frontend_pid=""

cleanup() {
  [[ -n "$backend_pid" ]] && kill "$backend_pid" 2>/dev/null || true
  [[ -n "$frontend_pid" ]] && kill "$frontend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$repo_root"
"$backend_python" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000 &
backend_pid=$!

npm --prefix "$frontend_dir" run dev -- --host 127.0.0.1 --port 5173 &
frontend_pid=$!

echo "Provenance: http://127.0.0.1:5173"
echo "FastAPI docs: http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to stop both services."

wait "$backend_pid" "$frontend_pid"
