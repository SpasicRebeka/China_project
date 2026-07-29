#!/usr/bin/env bash
set -euo pipefail

release_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_executable="$release_root/.venv/bin/python"
port="${HERING_PORT:-8000}"
base_url="http://127.0.0.1:${port}"

[[ -x "$python_executable" ]] || {
  echo "Runtime is not installed. Run: bash install.sh" >&2
  exit 1
}

health_json="$(curl -fsS "$base_url/api/health")" || {
  echo "Service status: stopped or unavailable" >&2
  exit 1
}
knowledge_json="$(curl -fsS "$base_url/api/v1/knowledge-graph")"

"$python_executable" - "$health_json" "$knowledge_json" "$base_url" <<'PY'
import json
import sys

health = json.loads(sys.argv[1])
knowledge = json.loads(sys.argv[2])
base_url = sys.argv[3]
print("Service status: ready")
print(f"Application version: {health['version']}")
print(f"Knowledge base version: {knowledge['kb_version']}")
print(f"Chief complaint count: {len(knowledge['symptoms'])}")
print(f"Doctor UI: {base_url}/doctor/")
PY
