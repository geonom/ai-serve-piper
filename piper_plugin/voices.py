"""The voices this plugin offers and how they get onto the disk -- pure data plus one small download function.

Each voice is two files from Hugging Face's rhasspy/piper-voices (the model and its config), pinned by path, size and
sha256 at one commit of that repository, so a download is checked byte for byte. Only voices whose training data has
a clear license are listed (public domain, CC0, CC-BY); the voice models themselves are MIT (piper-voices).
Add a voice: append it here with its files' size and sha256 (README.md, "Adding a voice")."""
from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

REPO = "rhasspy/piper-voices"
REVISION = "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd"   # pinned: the hashes below belong to this commit


@dataclass(frozen=True)
class VoiceFile:
    path: str      # in the repo
    size: int
    sha256: str

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{REPO}/resolve/{REVISION}/{self.path}"


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    language: str          # short code, as ai-serve sends it ("de", "en" ...)
    data_license: str      # the training data's license (the model itself: MIT)
    files: Tuple[VoiceFile, ...]

    @property
    def model(self) -> str:
        return next(f.name for f in self.files if f.name.endswith(".onnx"))

    @property
    def size_mb(self) -> int:
        return sum(f.size for f in self.files) >> 20


VOICES: Dict[str, Voice] = {
    "en_US-ljspeech-medium": Voice("en_US-ljspeech-medium", "LJSpeech (US English, female)", "en", "public domain (LJ Speech)", (
            VoiceFile("en/en_US/ljspeech/medium/en_US-ljspeech-medium.onnx", 63531379, "6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22"),
            VoiceFile("en/en_US/ljspeech/medium/en_US-ljspeech-medium.onnx.json", 4972, "141d612cc0a95ed7efc1ca936b845c2364967f2e9217c5dbfcf69fc4d6c65860"),
        )),
    "en_GB-cori-medium": Voice("en_GB-cori-medium", "Cori (UK English, female)", "en", "public domain (LibriVox)", (
            VoiceFile("en/en_GB/cori/medium/en_GB-cori-medium.onnx", 63531379, "1899f98e5fb8310154f3c2973f4b8a929ba7245e722b3d3a85680b833d95f10d"),
            VoiceFile("en/en_GB/cori/medium/en_GB-cori-medium.onnx.json", 4966, "e262c16d7f192f69d4edd6b4ef8a5915379e67495fcc402f1ab15eeb33da3d36"),
        )),
    "de_DE-thorsten-medium": Voice("de_DE-thorsten-medium", "Thorsten (German, male)", "de", "CC0 (Thorsten-Voice)", (
            VoiceFile("de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx", 63201294, "7e64762d8e5118bb578f2eea6207e1a35a8e0c30595010b666f983fc87bb7819"),
            VoiceFile("de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json", 4819, "974adee790533adb273a1ac88f49027d2a1b8f0f2cf4905954a4791e79264e85"),
        )),
    "de_DE-kerstin-low": Voice("de_DE-kerstin-low", "Kerstin (German, female)", "de", "CC0", (
            VoiceFile("de/de_DE/kerstin/low/de_DE-kerstin-low.onnx", 63104526, "d352a7641892cebf2903859af94e9ba81a141110215fe3943bcda7f7da401b7a"),
            VoiceFile("de/de_DE/kerstin/low/de_DE-kerstin-low.onnx.json", 4158, "56e708556b7b9b7a53c4f8957e021421e69f11a600962bba554cffbe72cf2d47"),
        )),
    # four more German speakers (2026-10-24, owner: six different voices per engine where possible)
    "de_DE-eva_k-x_low": Voice("de_DE-eva_k-x_low", "Eva K (German, female)", "de", "M-AILABS (see caito.de)", (
            VoiceFile("de/de_DE/eva_k/x_low/de_DE-eva_k-x_low.onnx", 20628813, "e88cf290fbfb768bf111330d2e8a46e376b0d85e3423a28bfebbc863a260dad8"),
            VoiceFile("de/de_DE/eva_k/x_low/de_DE-eva_k-x_low.onnx.json", 4158, "ef14b3dcb279ab4b18422a7a132877bee7a148821bd91152fb7ae9c4b3d79625"),
        )),
    "de_DE-karlsson-low": Voice("de_DE-karlsson-low", "Karlsson (German, male)", "de", "M-AILABS (see caito.de)", (
            VoiceFile("de/de_DE/karlsson/low/de_DE-karlsson-low.onnx", 63104526, "f9793bf7e461a472b3916cf260774bfc9812e9eb72601b147ed649d01064e8fe"),
            VoiceFile("de/de_DE/karlsson/low/de_DE-karlsson-low.onnx.json", 4159, "3b2095adbfeede316f22007a0a09d4bfc25514b7189850740b06800a6cfb9838"),
        )),
    "de_DE-ramona-low": Voice("de_DE-ramona-low", "Ramona (German, female)", "de", "M-AILABS (see caito.de)", (
            VoiceFile("de/de_DE/ramona/low/de_DE-ramona-low.onnx", 63104526, "a1068592532aad8c49bf3d1a01b8749c11d7dba726689ee28ad64e7b627ae4c5"),
            VoiceFile("de/de_DE/ramona/low/de_DE-ramona-low.onnx.json", 4157, "64906ab7a050ac685fa3dcea044baa798f67ed77be164f9c668a69298c6487d2"),
        )),
    "de_DE-pavoque-low": Voice("de_DE-pavoque-low", "Pavoque (German, male; non-commercial)", "de",
                               "CC-BY-NC-SA-4.0 (PAVOQUE) -- not for commercial use", (
            VoiceFile("de/de_DE/pavoque/low/de_DE-pavoque-low.onnx", 63104526, "96cd41fe2303dfe4745422a2580658bdbc5f935b7ee67640a94da7435a502a26"),
            VoiceFile("de/de_DE/pavoque/low/de_DE-pavoque-low.onnx.json", 4158, "07d43d8946e869209a12d9b4fd780e3f277fe9afb305c21491a68bd97e01b74f"),
        )),
    "fr_FR-siwis-medium": Voice("fr_FR-siwis-medium", "Siwis (French, female)", "fr", "CC-BY-4.0 (SIWIS)", (
            VoiceFile("fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx", 63201294, "641d1ab097da2b81128c076810edb052b385decc8be3381814802a64a73baf99"),
            VoiceFile("fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json", 4875, "39479916c2db192b5ac9764daddd0c744d83e023ad890c6976c0633ae4df8959"),
        )),
    "es_ES-davefx-medium": Voice("es_ES-davefx-medium", "Davefx (Spanish, male)", "es", "CC0", (
            VoiceFile("es/es_ES/davefx/medium/es_ES-davefx-medium.onnx", 63201294, "6658b03b1a6c316ee4c265a9896abc1393353c2d9e1bca7d66c2c442e222a917"),
            VoiceFile("es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json", 4817, "0e0dda87c732f6f38771ff274a6380d9252f327dca77aa2963d5fbdf9ec54842"),
        )),
}


def installed(voice: Voice, voices_dir: str) -> bool:
    return all(os.path.isfile(os.path.join(voices_dir, f.name)) and
               os.path.getsize(os.path.join(voices_dir, f.name)) == f.size for f in voice.files)


def download(voice: Voice, voices_dir: str, progress: Optional[Callable[[int], None]] = None,
             opener: Optional[Callable[[str], object]] = None) -> None:
    """Fetch the voice's missing files; each is written to a temp file, hashed while writing and moved into place only
    when its sha256 matches. Raises ValueError on a mismatch (nothing is kept)."""
    opener = opener or (lambda url: urllib.request.urlopen(urllib.request.Request(
        url, headers={"User-Agent": "ai-serve-piper"}), timeout=60))
    os.makedirs(voices_dir, exist_ok=True)
    for f in voice.files:
        target = os.path.join(voices_dir, f.name)
        if os.path.isfile(target) and os.path.getsize(target) == f.size:
            if progress:
                progress(f.size)
            continue
        h = hashlib.sha256()
        with opener(f.url) as r, tempfile.NamedTemporaryFile(dir=voices_dir, delete=False, prefix=".part-") as out:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                if progress:
                    progress(len(chunk))
            tmp = out.name
        if h.hexdigest() != f.sha256:
            os.unlink(tmp)
            raise ValueError(f"{f.name}: checksum mismatch -- nothing kept")
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
