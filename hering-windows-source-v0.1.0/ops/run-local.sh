#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

exec .venv/bin/python -m uvicorn app.main:app \
  --app-dir services/api \
  --host 127.0.0.1 \
  --port "${HERING_PORT:-8000}"

