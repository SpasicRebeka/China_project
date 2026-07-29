#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

command -v python3 >/dev/null || { echo "缺少 python3" >&2; exit 1; }
command -v node >/dev/null || { echo "缺少 Node.js 22+" >&2; exit 1; }

corepack enable
corepack pnpm install --frozen-lockfile

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r services/api/requirements.lock
.venv/bin/python -m pip install -e services/api --no-deps

corepack pnpm build
echo "构建完成。运行：make start；双屏模式：make kiosk"
