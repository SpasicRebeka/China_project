#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/../.." && pwd)"
config_file="$script_dir/kiosk.env"

if [[ -f "$config_file" ]]; then
  # shellcheck disable=SC1090
  source "$config_file"
else
  echo "提示：未找到 $config_file，使用双 1024×600 横向屏幕默认值。" >&2
fi

base_url="${HERING_BASE_URL:-http://127.0.0.1:8000}"
port="${HERING_PORT:-8000}"
doctor_output="${DOCTOR_OUTPUT:-HDMI-1}"
patient_output="${PATIENT_OUTPUT:-HDMI-2}"
doctor_position="${DOCTOR_WINDOW_POSITION:-0,0}"
patient_position="${PATIENT_WINDOW_POSITION:-1024,0}"
doctor_size="${DOCTOR_WINDOW_SIZE:-1024,600}"
patient_size="${PATIENT_WINDOW_SIZE:-1024,600}"

cd "$project_root"
[[ -x .venv/bin/python ]] || { echo "缺少 .venv，请先运行 bash ops/build-release.sh" >&2; exit 1; }
[[ -f services/api/static/doctor/index.html ]] || { echo "缺少前端构建产物，请先运行 make build" >&2; exit 1; }
[[ -f services/api/static/patient/index.html ]] || { echo "缺少前端构建产物，请先运行 make build" >&2; exit 1; }

if [[ "${XDG_SESSION_TYPE:-unknown}" != "x11" ]]; then
  echo "警告：当前不是 Xorg 会话，窗口位置参数可能被 Wayland 忽略，需要手动摆放。" >&2
fi

if [[ -n "${CHROMIUM_BIN:-}" ]]; then
  browser="$CHROMIUM_BIN"
elif command -v chromium-browser >/dev/null; then
  browser="$(command -v chromium-browser)"
elif command -v chromium >/dev/null; then
  browser="$(command -v chromium)"
elif command -v google-chrome >/dev/null; then
  browser="$(command -v google-chrome)"
else
  echo "未找到 Chromium/Chrome。" >&2
  exit 1
fi

api_pid=""
cleanup() {
  if [[ -n "$api_pid" ]]; then
    kill "$api_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if ! curl -fsS "$base_url/api/health" >/dev/null 2>&1; then
  mkdir -p data
  .venv/bin/python -m uvicorn app.main:app \
    --app-dir services/api --host 127.0.0.1 --port "$port" \
    >data/api.log 2>&1 &
  api_pid=$!
  for _ in {1..40}; do
    curl -fsS "$base_url/api/health" >/dev/null 2>&1 && break
    sleep 0.25
  done
fi
curl -fsS "$base_url/api/health" >/dev/null || { echo "本地服务启动失败，请查看 data/api.log" >&2; exit 1; }

session_json="$(curl -fsS -X POST "$base_url/api/v1/sessions")"
readarray -t credentials < <(
  printf '%s' "$session_json" | .venv/bin/python -c \
    'import json,sys; d=json.load(sys.stdin); print(d["session_id"]); print(d["doctor_token"]); print(d["patient_token"])'
)
session_id="${credentials[0]}"
doctor_token="${credentials[1]}"
patient_token="${credentials[2]}"
doctor_url="$base_url/doctor/?session=$session_id&token=$doctor_token"
patient_url="$base_url/patient/?session=$session_id&token=$patient_token"

if command -v xinput >/dev/null && command -v xrandr >/dev/null; then
  if [[ -n "${DOCTOR_TOUCH_DEVICE:-}" ]]; then
    xinput map-to-output "$DOCTOR_TOUCH_DEVICE" "$doctor_output" || true
  fi
  if [[ -n "${PATIENT_TOUCH_DEVICE:-}" ]]; then
    xinput map-to-output "$PATIENT_TOUCH_DEVICE" "$patient_output" || true
  fi
fi

mkdir -p data/kiosk-doctor data/kiosk-patient
common_args=(
  --no-first-run
  --disable-session-crashed-bubble
  --disable-infobars
  --overscroll-history-navigation=0
  --kiosk
)

"$browser" "${common_args[@]}" \
  --user-data-dir="$project_root/data/kiosk-doctor" \
  --window-position="$doctor_position" --window-size="$doctor_size" \
  "$doctor_url" &
doctor_pid=$!

"$browser" "${common_args[@]}" \
  --user-data-dir="$project_root/data/kiosk-patient" \
  --window-position="$patient_position" --window-size="$patient_size" \
  "$patient_url" &
patient_pid=$!

echo "双屏会话已启动：${session_id:0:8}"
wait "$doctor_pid" "$patient_pid"
