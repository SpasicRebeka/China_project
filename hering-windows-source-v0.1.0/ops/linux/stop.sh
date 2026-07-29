#!/usr/bin/env bash
set -euo pipefail

release_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$release_root"
pid_file="data/hering.pid"

if [[ ! -f "$pid_file" ]]; then
  echo "No running service was found."
  exit 0
fi

server_pid="$(cat "$pid_file")"
if kill -0 "$server_pid" 2>/dev/null; then
  command_line="$(tr '\0' ' ' <"/proc/$server_pid/cmdline" 2>/dev/null || true)"
  if [[ "$command_line" != *"uvicorn"* || "$command_line" != *"services/api"* ]]; then
    echo "PID $server_pid does not match this service; stop was cancelled." >&2
    exit 1
  fi
  kill "$server_pid"
  for _ in {1..20}; do
    kill -0 "$server_pid" 2>/dev/null || break
    sleep 0.1
  done
fi

rm -f "$pid_file"
echo "Service stopped."
