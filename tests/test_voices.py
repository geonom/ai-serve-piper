"""Voice downloads (piper_plugin/voices.py): pinned files, checked by sha256, nothing kept on a mismatch."""
import hashlib
import io

import pytest

from piper_plugin import voices
from piper_plugin.voices import Voice, VoiceFile


def _opener(content):
    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): self.close()
    return lambda url: R(content)


def test_every_voice_is_pinned():
    for v in voices.VOICES.values():
        assert v.model.endswith(".onnx") and len(v.files) == 2
        assert all(len(f.sha256) == 64 and f.size > 0 and voices.REVISION in f.url for f in v.files)


def test_download_checks_each_file(tmp_path):
    data = b"onnx bytes"
    v = Voice("t", "T", "de", "CC0", (VoiceFile("de/t.onnx", len(data), hashlib.sha256(data).hexdigest()),))
    voices.download(v, str(tmp_path), opener=_opener(data))
    assert (tmp_path / "t.onnx").read_bytes() == data and voices.installed(v, str(tmp_path))


def test_a_wrong_file_is_not_kept(tmp_path):
    v = Voice("t", "T", "de", "CC0", (VoiceFile("de/t.onnx", 3, "0" * 64),))
    with pytest.raises(ValueError):
        voices.download(v, str(tmp_path), opener=_opener(b"bad"))
    assert list(tmp_path.iterdir()) == []
