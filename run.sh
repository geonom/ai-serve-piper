#!/usr/bin/env bash
# Started by ai-serve (Apps & Services) on demand; listens on 127.0.0.1:$PORT.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then      # first start without setup.sh: just the small environment
    command -v uv >/dev/null || { echo "run ./setup.sh first (or install uv)" >&2; exit 1; }
    uv venv -q --python 3.12 .venv && uv pip install -q --python .venv/bin/python -r requirements.txt
fi
exec .venv/bin/python -m piper_plugin.app --port "${PORT:-8095}"
