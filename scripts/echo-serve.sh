#!/bin/zsh
# Launchd / manual wrapper for Echo (no Flask reloader).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export FLASK_HOST="${FLASK_HOST:-0.0.0.0}"
export FLASK_PORT="${FLASK_PORT:-5050}"
# Always off under launchd / this wrapper (reloader forks break KeepAlive)
export FLASK_DEBUG=0

exec "$ROOT/.venv/bin/python" "$ROOT/server/app.py"
