"""The plugin's rules (piper_plugin/rules.py): the catalog ai-serve reads and how a request is checked."""
import pytest

from piper_plugin import rules
from piper_plugin.rules import RequestError

DE, EN = "de_DE-thorsten-medium", "en_US-ljspeech-medium"


def test_catalog_lists_installed_voices_languages_and_speed():
    cat = rules.catalog([DE, EN], engine_ready=True)
    e = cat["engines"][0]
    assert cat["default_engine"] == "piper" and e["id"] == "piper" and e["installed"] is True
    assert e["languages"] == ["de", "en"]
    mode = e["modes"][0]
    assert mode["speakers"] == [EN, DE]           # in the order of VOICES
    assert mode["inputs"] == {"speaker": "optional"} and mode["params"][0]["name"] == "speed"


def test_catalog_without_engine_or_voices_says_so():
    e = rules.catalog([], engine_ready=True)
    assert e["engines"][0]["installed"] is False and e["errors"]
    assert rules.catalog([DE], engine_ready=False)["engines"][0]["installed"] is False


def test_a_request_becomes_a_job():
    job = rules.plan({"engine": "piper", "text": " Hallo ", "language": "de", "params": {"speed": 2.0}}, [DE, EN])
    assert job.voice.id == DE and job.text == "Hallo" and job.length_scale == 0.5
    assert rules.plan({"text": "Hi", "speaker": EN}, [DE, EN]).voice.id == EN
    assert rules.plan({"text": "Hi"}, [DE, EN]).voice.id == EN          # no language: English


@pytest.mark.parametrize("body,why", [
    ({"text": "x", "ref_audio_base64": "AAA"}, "clone"),
    ({"text": "x", "instruct": "sad"}, "instruction"),
    ({"text": "x", "engine": "cosyvoice"}, "only runs"),
    ({"text": ""}, "required"),
    ({"text": "x" * 5001}, "longer"),
    ({"text": "x", "language": "ja"}, "no installed voice"),
    ({"text": "x", "speaker": "nope"}, "unknown"),
    ({"text": "x", "params": {"speed": 9}}, "speed"),
    ({"text": "x", "params": {"temperature": 1}}, "one parameter"),
    ({"text": "x", "path": "/etc/passwd"}, "unknown fields"),
    ({"text": "x", "response_format": "mp3"}, "wav"),
    ("not json", "JSON object"),
])
def test_what_piper_cannot_do_is_refused(body, why):
    with pytest.raises(RequestError) as e:
        rules.plan(body, [DE, EN])
    assert why in str(e.value)


def test_nothing_installed():
    with pytest.raises(RequestError):
        rules.plan({"text": "x"}, [])
