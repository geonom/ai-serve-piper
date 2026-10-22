#!/usr/bin/env bash
# Set up the plugin: its own small environment (.venv: FastAPI) and Piper's (piper-venv: piper-tts, GPL-3.0 -- run as
# a separate program, never imported). Optionally voices:
#   ./setup.sh                      both environments
#   ./setup.sh --engine             only Piper's environment (what the Downloads button runs)
#   ./setup.sh --voices de_DE-thorsten-medium,en_US-ljspeech-medium
# Needs uv (https://docs.astral.sh/uv/) or python3 with venv. Re-running is fine.
set -euo pipefail
cd "$(dirname "$0")"
ENGINE_ONLY=""; VOICES=""
while [ $# -gt 0 ]; do
    case "$1" in
        --engine) ENGINE_ONLY=1; shift ;;
        --voices) VOICES="${2:-}"; shift 2 ;;
        *) echo "unknown option $1" >&2; exit 2 ;;
    esac
done
venv() {   # venv <dir> <packages...>
    local dir="$1"; shift
    if command -v uv >/dev/null; then
        [ -x "$dir/bin/python" ] || uv venv -q --python 3.12 "$dir"
        uv pip install -q --python "$dir/bin/python" "$@"
    else
        [ -x "$dir/bin/python" ] || python3 -m venv "$dir"
        "$dir/bin/pip" install -q "$@"
    fi
}
if [ -z "$ENGINE_ONLY" ]; then
    echo "== the plugin's environment (.venv)"
    venv .venv -r requirements.txt
fi
echo "== Piper (piper-venv)"
venv piper-venv "piper-tts>=1.3,<2"
if [ -n "$VOICES" ]; then
    echo "== voices: $VOICES"
    .venv/bin/python - "$VOICES" <<'PY'
import sys
from piper_plugin.voices import VOICES, download
for vid in sys.argv[1].split(","):
    download(VOICES[vid], "voices", lambda n: None)
    print("  " + vid + " -- checked")
PY
fi
echo "ok"
