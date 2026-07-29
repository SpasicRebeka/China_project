#!/usr/bin/env bash
set -euo pipefail

release_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$release_root"

port="${HERING_PORT:-8000}"
pid_file="data/hering.pid"
doctor_url="http://127.0.0.1:${port}/doctor/"

[[ -x .venv/bin/python ]] || {
  echo "Runtime is not installed. Run: bash install.sh" >&2
  exit 1
}

mkdir -p data logs

if [[ -f "$pid_file" ]]; then
  existing_pid="$(cat "$pid_file")"
  if kill -0 "$existing_pid" 2>/dev/null; then
    echo "The service is already running. PID: $existing_pid"
    exit 0
  fi
  rm -f "$pid_file"
fi

if command -v ss >/dev/null && ss -ltn "sport = :$port" | grep -q LISTEN; then
  echo "Port $port is already occupied." >&2
  exit 1
fi

nohup .venv/bin/python -m uvicorn app.main:app \
  --app-dir services/api \
  --host 127.0.0.1 \
  --port "$port" \
  >logs/server.out.log 2>logs/server.err.log &
server_pid=$!
printf '%s\n' "$server_pid" >"$pid_file"

ready=0
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:${port}/api/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

if [[ "$ready" != "1" ]]; then
  kill "$server_pid" 2>/dev/null || true
  rm -f "$pid_file"
  echo "Service startup failed. Check logs/server.err.log." >&2
  exit 1
fi

echo "Service ready: $doctor_url"
echo "PID: $server_pid"

if [[ "${HERING_OPEN_BROWSER:-1}" == "1" ]] && command -v xdg-open >/dev/null; then
  xdg-open "$doctor_url" >/dev/null 2>&1 || true
fi
