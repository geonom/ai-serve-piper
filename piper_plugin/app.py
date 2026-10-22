"""The plugin's HTTP side: the endpoints its manifest (llama-serve.service.json) declares. ai-serve starts this app on
demand (`./run.sh`) and calls only these paths on 127.0.0.1.

Piper itself (GPL-3.0) is a separate program in its own environment (`piper-venv/`, set up by setup.sh): this app runs
`piper-venv/bin/python -m piper` per request and reads the WAV it writes -- it never imports Piper. That keeps this
template's code MIT-licensed and makes the engine swappable: replace `synthesize()` for another one.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import Response

from piper_plugin import rules
from piper_plugin.voices import VOICES, download, installed

HERE = Path(__file__).resolve().parent.parent
VOICES_DIR = os.environ.get("PIPER_VOICES_DIR") or str(HERE / "voices")
PIPER_PYTHON = os.environ.get("PIPER_PYTHON") or str(HERE / "piper-venv" / "bin" / "python")
LOG = HERE / "logs" / "piper.log"
TIMEOUT_S = 300
ENGINE_ITEM = "piper-engine"

logger = logging.getLogger("ai-serve-piper")
app = FastAPI(title="Piper speech for ai-serve")
_busy = 0
_last_used = None
_installs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def engine_ready() -> bool:
    return os.access(PIPER_PYTHON, os.X_OK)


def installed_voices() -> List[str]:
    return [v.id for v in VOICES.values() if installed(v, VOICES_DIR)]


def synthesize(job: rules.Job) -> bytes:
    """Run Piper once: text on stdin, WAV into a temp file."""
    os.makedirs(LOG.parent, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.wav")
        cmd = [PIPER_PYTHON, "-m", "piper", "-m", os.path.join(VOICES_DIR, job.voice.model), "-f", out,
               "--length-scale", str(job.length_scale)]
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%H:%M:%S')} {job.voice.id} {len(job.text)} chars\n")
            log.flush()
            r = subprocess.run(cmd, input=job.text.encode("utf-8"), stdout=log, stderr=log, timeout=TIMEOUT_S)
        if r.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError(f"piper exited with {r.returncode}")
        with open(out, "rb") as f:
            return f.read()


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/v1/engines")
async def engines():
    return rules.catalog(installed_voices(), engine_ready())


@app.post("/v1/generate")
def generate(body: Any = Body(...)):
    global _busy, _last_used
    if not engine_ready():
        raise HTTPException(status_code=409, detail="Piper isn't set up yet -- download it under Downloads")
    try:
        job = rules.plan(body, installed_voices())
    except rules.RequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    with _lock:
        _busy += 1
    try:
        wav = synthesize(job)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
        logger.error(f"synthesis failed: {e}")
        raise HTTPException(status_code=500, detail="Piper failed -- see the plugin's log")
    finally:
        with _lock:
            _busy -= 1
        _last_used = time.time()
    return Response(content=wav, media_type="audio/wav")


@app.get("/plugin/status")
async def status():
    voices = installed_voices()
    facts = [{"label": "Piper", "value": "ready" if engine_ready() else "not set up"},
             {"label": "Voices", "value": ", ".join(voices) or "none yet"}]
    # no worker holds memory between requests (one short process per request), so there is nothing to list or free
    return {"busy": _busy > 0, "ready": engine_ready() and bool(voices), "workers": [], "facts": facts}


@app.post("/plugin/release")
async def release(body: Any = Body(default={})):
    return {"released": []}


@app.get("/plugin/logs")
async def logs(tail: int = 200):
    try:
        lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(tail, 5000)):]
    except OSError:
        lines = []
    return {"logs": "\n".join(lines)}


# ---------------------------------------------------------------- downloads (contract endpoint `install`)

def _item(key: str) -> Dict[str, Any]:
    st = _installs.get(key, {})
    if key == ENGINE_ITEM:
        there, label, desc, lic, size = (engine_ready(), "Piper", "The speech engine (its own Python environment)",
                                         "GPL-3.0", 60)
    else:
        v = VOICES[key]
        there, label, desc, lic, size = (installed(v, VOICES_DIR), f"Piper voice: {v.label}",
                                         f"Language {v.language}; training data: {v.data_license}",
                                         f"MIT (model), {v.data_license} (data)", v.size_mb)
    state = "installed" if there and st.get("state") != "downloading" else (st.get("state") or "missing")
    return {"id": key, "label": label, "description": desc, "license": lic, "size_mb": size, "state": state,
            "done_mb": (st.get("done", 0) >> 20) if state == "downloading" and key != ENGINE_ITEM else None,
            "error": st.get("error", "") if state == "failed" else ""}


def _run(key: str) -> None:
    try:
        if key == ENGINE_ITEM or not engine_ready():
            r = subprocess.run(["bash", str(HERE / "setup.sh"), "--engine"], cwd=str(HERE), capture_output=True,
                               text=True, stdin=subprocess.DEVNULL)
            if r.returncode != 0 or not engine_ready():
                tail = (r.stdout + r.stderr).strip().splitlines()
                raise RuntimeError(tail[-1] if tail else "setup.sh failed")
        if key != ENGINE_ITEM:
            def progress(n: int) -> None:
                _installs[key]["done"] = _installs[key].get("done", 0) + n
            download(VOICES[key], VOICES_DIR, progress)
        _installs[key] = {"state": "installed"}
    except Exception as e:
        _installs[key] = {"state": "failed", "error": str(e)[:300]}


@app.get("/plugin/install")
async def install_list():
    keys = ([ENGINE_ITEM] if not engine_ready() else []) + list(VOICES)
    return {"items": [_item(k) for k in keys]}


@app.post("/plugin/install", status_code=202)
async def install_start(body: Any = Body(...)):
    key = body.get("id") if isinstance(body, dict) else None
    if key != ENGINE_ITEM and key not in VOICES:     # only the id comes from the request -- files and hashes are ours
        raise HTTPException(status_code=404, detail="nothing to download under that id")
    with _lock:
        if _item(key)["state"] not in ("installed", "downloading"):
            _installs[key] = {"state": "downloading", "done": 0}
            threading.Thread(target=_run, args=(key,), daemon=True).start()
    return _item(key)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8095")))
    a = ap.parse_args()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    sys.exit(main())
