# Development Guide

Run all commands from the project root.

## Project layout

| Path | Purpose |
|---|---|
| `src/speech_translator/` | GUI, CLI, audio I/O, speech detection, recognition, translation, and synthesis |
| `tests/` | Unit tests that do not require model downloads or physical audio devices |
| `scripts/` | Model setup, integration checks, and benchmarks |
| `config.yaml` | Default Gemma and Kokoro configuration |
| `config.qwen.yaml` | Alternative configuration using Qwen TTS |
| `requirements-*.lock` | Locked dependencies for the separate TTS environments |
| `THIRD_PARTY/` | Bundled third-party license notices |

## Routine checks

```powershell
.\uv.ps1 sync --locked
.\uv.ps1 run python -m unittest discover -s tests -v
.\uv.ps1 run python scripts/preview_gui.py
```

The GUI tests run offscreen. The preview script writes `artifacts/gui.png`.

## GPU and model integration checks

Complete the [model setup](SETUP.md) first. Skip these checks in CPU-only CI.

```powershell
.\uv.ps1 run python scripts/check_kokoro.py
.\uv.ps1 run python scripts/check_automatic.py
```

`check_automatic.py` uses the Japanese and English WAV files produced by `check_kokoro.py`. It exercises the actual speech detector, recognizer, translator, and synthesizer with simulated microphone input and file output. Test acoustic feedback, room reverberation, and microphone placement separately using physical hardware.

`check_audio.py`, `check_gui_models.py`, `check_models.py`, and `check_gemma_qwen.py` cover individual devices, older configurations, or specific model combinations. Check each script's settings before running it. See [Validation Notes](VALIDATION.md) for recorded results.

## Model comparison scripts

The `compare_*` and `report_*` scripts, `review_tts_comparison.py`, `tts_comparison_worker.py`, `run_gpu_comparison.ps1`, and `prepare_*_comparison.py` support model selection experiments. Some experiments require additional models or results from earlier runs in `artifacts/`. These scripts are not needed to launch the app.

For routine setup, use `prepare_ollama_vulkan.py`, `prepare_gemma.py`, and `setup_kokoro.ps1` as described in the [model setup guide](SETUP.md). `prepare_gemma.py` reuses the download function from the comparison script.

## Repository contents

Keep models, virtual environments, runtime binaries, conversation logs, recordings, saved device selections, and generated measurements out of Git. Update the relevant lockfiles when adding dependencies.

The repository's original source code is licensed under the [MIT License](../LICENSE). See the [engine and model references](REFERENCES.md) for third-party sources and license information.
