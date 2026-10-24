"""What the plugin tells ai-serve and how a request becomes a Piper call -- pure (no I/O), so it is easy to test
(tests/test_rules.py). This is the part to rewrite for another engine; app.py around it stays almost the same.

ai-serve's `tts` contract (docs/plugins.md in ai-serve):
- catalog: {"engines": [engine], "default_engine", "errors"} -- one entry per engine with its languages and modes
  (what a request may or must carry; `speakers` = the choices for `speaker`; `params` = numbers with a range).
- generate: {"engine", "text", "language", "variant", "speaker", "params", "instruct", "ref_audio_base64",
  "ref_text", "keep_alive", "response_format"} -> WAV bytes. Anything the engine can't do is a 400 with a reason.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from piper_plugin.voices import VOICES, Voice

ENGINE = "piper"
MAX_TEXT = 5000
SPEED = {"name": "speed", "label": "Speed", "min": 0.5, "max": 2.0, "step": 0.05, "default": 1.0}
KNOWN_FIELDS = {"engine", "text", "language", "variant", "speaker", "params", "instruct", "ref_audio_base64",
                "ref_text", "keep_alive", "response_format"}


class RequestError(ValueError):
    """Becomes a 400 with this message."""


@dataclass(frozen=True)
class Job:
    voice: Voice
    text: str
    length_scale: float      # Piper's speed knob: < 1 faster, > 1 slower


def catalog(installed: Iterable[str], engine_ready: bool) -> Dict[str, Any]:
    """installed: ids of the voices on disk; engine_ready: Piper itself is set up."""
    have = [v for v in VOICES.values() if v.id in set(installed)]
    return {"engines": [{
        "id": ENGINE, "name": "Piper", "aliases": ["piper-tts"],
        "description": "Fast speech on the CPU (no GPU needed), one voice per language; no cloning.",
        "license": "GPL-3.0 (Piper) · voices: MIT models, data licenses per voice",
        "installed": engine_ready and bool(have),
        "status": "idle" if engine_ready and have else "unloaded", "loaded": False,
        "default_reference": False, "gpu": None,
        "languages": sorted({v.language for v in have}),
        "variants": ["voice"],
        "modes": [{
            "variant": "voice", "label": "Voice",
            "description": "One of the installed voices; without one, the first voice for the language.",
            "inputs": {"speaker": "optional"},
            "speakers": [v.id for v in have],
            "params": [SPEED],
        }],
    }], "default_engine": ENGINE, "errors": [] if have or not engine_ready else
        ["no voice installed yet -- download one (Downloads in the dashboard or the Playground)"]}


def plan(body: Any, installed: Iterable[str]) -> Job:
    """An untrusted generate request -> a Job, or RequestError."""
    if not isinstance(body, dict):
        raise RequestError("send a JSON object")
    unknown = set(body) - KNOWN_FIELDS
    if unknown:
        raise RequestError(f"unknown fields: {', '.join(sorted(unknown))}")
    if (body.get("engine") or ENGINE) != ENGINE:
        raise RequestError(f"this plugin only runs the engine {ENGINE!r}")
    if body.get("ref_audio_base64") or body.get("ref_text"):
        raise RequestError("Piper can't clone a voice -- choose one of its voices (speaker)")
    if body.get("instruct"):
        raise RequestError("Piper takes no style instruction")
    if body.get("variant") not in (None, "voice"):
        raise RequestError("Piper has one mode: voice")
    if body.get("response_format") not in (None, "wav"):
        raise RequestError("only response_format wav")
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RequestError("text is required")
    if len(text) > MAX_TEXT:
        raise RequestError(f"text is longer than {MAX_TEXT} characters")
    voice = pick_voice(body.get("speaker"), body.get("language"), installed)
    params = body.get("params") or {}
    if not isinstance(params, dict) or set(params) - {"speed"}:
        raise RequestError("Piper takes one parameter: speed")
    speed = params.get("speed", SPEED["default"])
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not SPEED["min"] <= speed <= SPEED["max"]:
        raise RequestError(f"speed must be {SPEED['min']}..{SPEED['max']}")
    return Job(voice, text.strip(), round(1.0 / float(speed), 3))


def pick_voice(speaker: Optional[str], language: Optional[str], installed: Iterable[str]) -> Voice:
    have: List[Voice] = [v for v in VOICES.values() if v.id in set(installed)]
    if not have:
        raise RequestError("no Piper voice is installed yet -- download one first")
    if speaker:
        match = next((v for v in have if v.id == speaker), None)
        if match is None:
            raise RequestError(f"unknown or not installed voice {speaker!r}; installed: {', '.join(v.id for v in have)}")
        return match
    lang = (language or "en").split("-")[0].split("_")[0].lower()
    match = next((v for v in have if v.language == lang), None)
    if match is None:
        raise RequestError(f"no installed voice for language {lang!r}; installed: "
                           f"{', '.join(sorted({v.language for v in have}))} (download one more under Downloads)")
    return match
