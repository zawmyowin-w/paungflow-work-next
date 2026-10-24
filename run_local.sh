#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.12+ and try again." >&2
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

# Keep the pip cache and the temporary files on the project drive so that a full
# system drive cannot break the dependency installation.
export PIP_CACHE_DIR="$PWD/.pip-cache"
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/setup_local_env.py

# Do not inherit hosted credentials or a shared database URL into this local instance.
unset APP_MODE LOCAL_AUTH_ENABLED LOCAL_ADMIN_USERNAME LOCAL_ADMIN_PASSWORD LOCAL_SESSION_SECRET DATABASE_URL

echo "Starting Lower Paung-Luang dashboard at http://127.0.0.1:3000"
exec .venv/bin/python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 3000
