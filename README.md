# ai-serve-piper

Fast speech output on the CPU with [Piper](https://github.com/OHF-Voice/piper1-gpl) for
[ai-serve](https://github.com/geonom/ai-serve) – no GPU needed, runs on Linux, a Mac or a Raspberry Pi – **and a small,
complete example of an ai-serve plugin** you can copy to build your own (MIT).

```bash
# in your ai-serve folder
./ai-serve plugin add https://github.com/geonom/ai-serve-piper     # clones into plugins/, runs setup.sh after you confirm
./ai-serve restart
```

Then download a voice in the dashboard (*Compute & models → Downloads*) or the Playground (*Speech*), or right away:
`plugins/ai-serve-piper/setup.sh --voices de_DE-thorsten-medium,en_US-ljspeech-medium`. Piper shows up as the engine
`piper` everywhere ai-serve offers speech – the Playground, `/api/tts/generate`, and OpenAI's `/v1/audio/speech`
(`"model": "piper"`, `"voice"`: one of the voice ids below, or anything else for the language's first voice).

| Voice | Language | Training data |
|---|---|---|
| `en_US-ljspeech-medium` | English (US) | public domain |
| `en_GB-cori-medium` | English (UK) | public domain |
| `de_DE-thorsten-medium` | German | CC0 |
| `de_DE-kerstin-low` | German | CC0 |
| `fr_FR-siwis-medium` | French | CC-BY-4.0 |
| `es_ES-davefx-medium` | Spanish | CC0 |

Every file is pinned by size and sha256 at one commit of
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) and checked while downloading. Piper has many more
voices; these are the ones whose training data has a clear license. No cloning, no style instructions – for that, use
an engine of tts-serve. Tried on Linux (x86_64); a Mac and a Raspberry Pi are expected to work but untried.

## Licenses

This plugin's code: **MIT** (`LICENSE`) – copy it freely, also into plugins under other licenses. **Piper** itself is
**GPL-3.0**: `setup.sh` installs it (`piper-tts`) into its own environment, `piper-venv/`, and the plugin runs it as a
separate program per request – it never imports it. Voice models: MIT; their training data: see the table.

## Use it as a template

An ai-serve plugin is just a small web app on 127.0.0.1 plus a manifest saying what it provides. ai-serve finds it
under `plugins/`, starts it when it's needed, and calls only the paths the manifest names. The whole plugin:

| File | What it does | For your own plugin |
|---|---|---|
| `llama-serve.service.json` | The manifest: id, port, how to start, and `provides` – capability (`tts`) and its endpoints | change id, name, port, capability, endpoints |
| `piper_plugin/rules.py` | **Pure** rules: the catalog ai-serve reads (engines, languages, modes, params) and the check of a request | rewrite for your engine – it's the interesting part |
| `piper_plugin/voices.py` | What can be downloaded, pinned by sha256, and the download | your models / files |
| `piper_plugin/app.py` | The endpoints: catalog, generate, status, release, logs, install | usually only `synthesize()` changes |
| `setup.sh`, `run.sh` | Environments; start command (`$PORT` from ai-serve) | keep the shape |
| `tests/` | Rules, downloads and the HTTP side with a fake engine (no Piper, no network) | keep testing the same three things |
| `.github/workflows/tests.yml` | The tests on Linux and macOS for every push | as is |

**The contract** (ai-serve's [docs/plugins.md](https://github.com/geonom/ai-serve/blob/main/docs/plugins.md)):
- `catalog` – `GET` → `{"engines": [{"id", "name", "description", "license", "installed", "languages",
  "modes": [{"variant", "label", "inputs", "speakers", "params"}]}], "default_engine", "errors"}`. `inputs` says what a
  request may (`optional`) or must (`required`) carry: `speaker`, `reference` (a recording to clone), `ref_text`,
  `instruct`; `params` are numbers with `min`/`max`/`default`. The Playground builds its form from exactly this.
- `generate` – `POST` the request (`engine, text, language, variant, speaker, params, instruct, ref_audio_base64,
  ref_text, keep_alive, response_format`) → WAV bytes; what the engine can't do → `400` with a reason.
- `status` → `{"busy", "ready", "facts", "workers"}` – `workers` are processes holding memory (none here: Piper runs
  per request); `release` frees them (`409` while busy); `logs` → `{"logs"}`.
- `install` – `GET` → what can still be downloaded (`id`s in lowercase letters, digits, `.`, `_`, `-`), `POST {"id"}`
  starts it in the background. The request carries **only the id**: which files, from where and with which checksum
  is the plugin's own business.
- `gpu` in the manifest: `none` here; a plugin that loads models onto a GPU says `shared` and asks ai-serve first
  (`POST /api/coordination/gpu-preflight`) – see the contract.

Other capabilities (`image`, `stt`, `llm`, `video`, …) work the same way with their own catalog and request; the
contract lists them. Run the tests: `uv venv .venv && uv pip install --python .venv/bin/python -r
requirements-dev.txt && .venv/bin/python -m pytest -q`.

### Adding a voice

Find it in [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices), check the license of its training
data (its `MODEL_CARD`), and add it to `VOICES` in `piper_plugin/voices.py` with both files' size and sha256 (for the
`.onnx`, Hugging Face shows the sha256; download the small `.onnx.json` once and hash it). Keep `REVISION` – or move
it and re-check every hash.
