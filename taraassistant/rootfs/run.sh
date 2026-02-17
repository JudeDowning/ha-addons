#!/usr/bin/with-contenv sh
set -eu

OPTIONS_FILE="/data/options.json"

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

if [ "$#" -eq 0 ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

exec "$@"
