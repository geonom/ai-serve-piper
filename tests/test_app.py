"""The plugin over HTTP (piper_plugin/app.py) with a fake Piper that writes a WAV -- no Piper, no network needed."""
import os
import stat
import sys
import time

import pytest
from fastapi.testclient import TestClient

from piper_plugin import app as plugin
from piper_plugin.voices import VOICES

FAKE_PIPER = f"""#!{sys.executable}
import sys, wave
args = sys.argv[1:]
out = args[args.index("-f") + 1]
text = sys.stdin.read()
with wave.open(out, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\\0\\0" * len(text))
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    piper = tmp_path / "python"
    piper.write_text(FAKE_PIPER)
    piper.chmod(piper.stat().st_mode | stat.S_IEXEC)
    voices = tmp_path / "voices"
    voices.mkdir()
    for f in VOICES["de_DE-thorsten-medium"].files:       # an "installed" voice: right names and sizes
        with open(voices / f.name, "wb") as out:
            out.truncate(f.size)
    monkeypatch.setattr(plugin, "PIPER_PYTHON", str(piper))
    monkeypatch.setattr(plugin, "VOICES_DIR", str(voices))
    monkeypatch.setattr(plugin, "LOG", tmp_path / "logs" / "piper.log")
    return TestClient(plugin.app)


def test_catalog_and_status(client):
    e = client.get("/v1/engines").json()["engines"][0]
    assert e["installed"] and e["languages"] == ["de"] and e["modes"][0]["speakers"] == ["de_DE-thorsten-medium"]
    s = client.get("/plugin/status").json()
    assert s["ready"] and s["busy"] is False and s["workers"] == []


def test_generate_returns_wav(client):
    r = client.post("/v1/generate", json={"engine": "piper", "text": "Hallo Welt", "language": "de"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF"
    assert "de_DE-thorsten-medium" in client.get("/plugin/logs").json()["logs"]


def test_requests_piper_cannot_serve_are_400(client):
    r = client.post("/v1/generate", json={"text": "Hallo", "ref_audio_base64": "AAAA"})
    assert r.status_code == 400 and "clone" in r.json()["detail"]
    r = client.post("/v1/generate", json={"text": "Hi", "language": "en"})
    assert r.status_code == 400 and "language" in r.json()["detail"]


def test_without_piper_it_says_so(client, monkeypatch):
    monkeypatch.setattr(plugin, "PIPER_PYTHON", "/nonexistent/python")
    assert client.post("/v1/generate", json={"text": "Hallo"}).status_code == 409
    ids = [i["id"] for i in client.get("/plugin/install").json()["items"]]
    assert ids[0] == "piper-engine"


def test_install_takes_only_known_ids(client, monkeypatch):
    started = []
    monkeypatch.setattr(plugin, "_run", lambda key: started.append(key))
    assert client.post("/plugin/install", json={"id": "../../etc"}).status_code == 404
    assert client.post("/plugin/install", json={"id": "fr_FR-siwis-medium"}).status_code == 202
    for _ in range(50):
        if started:
            break
        time.sleep(0.02)
    assert started == ["fr_FR-siwis-medium"]
    items = {i["id"]: i for i in client.get("/plugin/install").json()["items"]}
    assert items["de_DE-thorsten-medium"]["state"] == "installed" and "CC0" in items["de_DE-thorsten-medium"]["license"]
