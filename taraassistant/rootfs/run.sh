#!/bin/sh
set -eu

OPTIONS_FILE="/data/options.json"

read_s6_env_file() {
  key="$1"
  path="/run/s6/container_environment/$key"
  if [ -f "$path" ]; then
    cat "$path"
  else
    printf ""
  fi
}

read_option() {
  key="$1"
  python3 - "$OPTIONS_FILE" "$key" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
if not path.exists():
    print("")
    sys.exit(0)

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("")
    sys.exit(0)

value = data.get(key, "")
if value is None:
    value = ""
print(str(value))
PY
}

if [ -f "$OPTIONS_FILE" ]; then
  opt_token="$(read_option home_assistant_token)"
  opt_url="$(read_option home_assistant_url)"
  opt_log_level="$(read_option log_level)"

  if [ -n "$opt_token" ] && [ -z "${HOME_ASSISTANT_TOKEN:-}" ]; then
    export HOME_ASSISTANT_TOKEN="$opt_token"
  fi

  if [ -n "$opt_url" ] && [ -z "${HOME_ASSISTANT_URL:-}" ]; then
    export HOME_ASSISTANT_URL="$opt_url"
  fi

  if [ -n "$opt_log_level" ] && [ -z "${LOG_LEVEL:-}" ]; then
    export LOG_LEVEL="$opt_log_level"
  fi
fi

# If no manual token is configured, fallback to HA's internal supervisor token.
if [ -z "${HOME_ASSISTANT_TOKEN:-}" ] && [ -n "${SUPERVISOR_TOKEN:-}" ]; then
  export HOME_ASSISTANT_TOKEN="$SUPERVISOR_TOKEN"
fi

# Older HA environments can expose HASSIO_TOKEN instead.
if [ -z "${HOME_ASSISTANT_TOKEN:-}" ] && [ -n "${HASSIO_TOKEN:-}" ]; then
  export HOME_ASSISTANT_TOKEN="$HASSIO_TOKEN"
fi

# Some images expose env only via s6 env files.
if [ -z "${HOME_ASSISTANT_TOKEN:-}" ]; then
  s6_supervisor_token="$(read_s6_env_file SUPERVISOR_TOKEN)"
  if [ -n "$s6_supervisor_token" ]; then
    export HOME_ASSISTANT_TOKEN="$s6_supervisor_token"
  fi
fi

if [ -z "${HOME_ASSISTANT_TOKEN:-}" ]; then
  s6_hassio_token="$(read_s6_env_file HASSIO_TOKEN)"
  if [ -n "$s6_hassio_token" ]; then
    export HOME_ASSISTANT_TOKEN="$s6_hassio_token"
  fi
fi

# Keep compatibility with apps expecting HA_TOKEN.
if [ -z "${HA_TOKEN:-}" ] && [ -n "${HOME_ASSISTANT_TOKEN:-}" ]; then
  export HA_TOKEN="$HOME_ASSISTANT_TOKEN"
fi

# Provide a default core API URL if none was set.
if [ -z "${HOME_ASSISTANT_URL:-}" ]; then
  export HOME_ASSISTANT_URL="http://supervisor/core"
fi

if [ -z "${HOME_ASSISTANT_TOKEN:-}" ]; then
  echo "ERROR: No Home Assistant token available from add-on options or supervisor env." >&2
fi

if [ "$#" -eq 0 ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

exec "$@"
