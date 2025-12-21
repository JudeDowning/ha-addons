#!/usr/bin/env bash
set -euo pipefail

APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
DATA_DIR="${DATA_DIR:-/data}"
LOG_DIR="${LOG_DIR:-${DATA_DIR}/logs}"
FAMLY_PROFILE_DIR="${FAMLY_PROFILE_DIR:-${DATA_DIR}/famly-profile}"
BABYCONNECT_PROFILE_DIR="${BABYCONNECT_PROFILE_DIR:-${DATA_DIR}/babyconnect-profile}"

mkdir -p "${DATA_DIR}" "${LOG_DIR}" "${FAMLY_PROFILE_DIR}" "${BABYCONNECT_PROFILE_DIR}"

# Load Home Assistant add-on options if present so we can configure runtime env vars.
OPTIONS_PATH="/data/options.json"
if [ -f "${OPTIONS_PATH}" ]; then
  FAMLY_CHILD_ID_OPTION="$(python3 - "${OPTIONS_PATH}" <<'PY'
import json, sys
path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except FileNotFoundError:
    data = {}
value = data.get("famly_child_id") or ""
print(value.strip())
PY
)"
  if [ -n "${FAMLY_CHILD_ID_OPTION}" ]; then
    export FAMLY_CHILD_ID="${FAMLY_CHILD_ID_OPTION}"
  fi
fi

exec uvicorn backend.api.main:app --host "${APP_HOST}" --port "${APP_PORT}"
