#!/usr/bin/env bash
set -euo pipefail

release_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$release_root"

supported_versions=(3.14 3.13 3.12)
if [[ -f SUPPORTED_PYTHON ]]; then
  read -r -a supported_versions <SUPPORTED_PYTHON
fi

python_candidates=()
for version in "${supported_versions[@]}"; do
  python_candidates+=("python${version}")
done
python_candidates+=(python3)

python_executable=""
for candidate in "${python_candidates[@]}"; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  read -r detected_version detected_bits < <(
    "$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}", 64 if sys.maxsize > 2**32 else 32)' 2>/dev/null
  ) || continue
  if [[ "$detected_bits" == "64" && " ${supported_versions[*]} " == *" $detected_version "* ]]; then
    python_executable="$(command -v "$candidate")"
    break
  fi
done

if [[ -z "$python_executable" ]]; then
  echo "A supported 64-bit Python was not found. This package supports: ${supported_versions[*]}." >&2
  echo "Install a matching python3.x and python3.x-venv package, then run install.sh again." >&2
  exit 1
fi

echo "Using Python: $python_executable"
"$python_executable" -c 'import sys; print(sys.version)'

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating the isolated runtime..."
  "$python_executable" -m venv .venv
fi

if [[ -d wheelhouse ]] && compgen -G 'wheelhouse/*.whl' >/dev/null; then
  echo "Installing runtime dependencies from the offline ARM64 wheelhouse..."
  .venv/bin/python -m pip install --no-index --find-links wheelhouse -r requirements-runtime.lock
else
  echo "Offline wheelhouse not found; installing from the Python package index..."
  .venv/bin/python -m pip install -r requirements-runtime.lock
fi

.venv/bin/python -c 'import fastapi, pydantic, uvicorn; print("Runtime dependency check passed")'
mkdir -p data logs
chmod +x install.sh start.sh stop.sh status.sh ops/kiosk/start-kiosk.sh
echo "Installation complete. Run: ./start.sh"
