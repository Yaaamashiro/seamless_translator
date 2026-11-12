# Model Setup

[Back to README](../README.md)

Run these commands in PowerShell from the repository root. First run `uv sync --locked` to create the main Python environment. Initial setup requires an internet connection.

## Gemma and Kokoro

Download the Vulkan runtime, verify the signatures of the downloaded executables and libraries, then prepare the models and launch the app:

```powershell
.\uv.ps1 run python scripts/prepare_ollama_vulkan.py
Get-ChildItem .tools/ollama-v0.34.2-vulkan -Recurse -File |
  Where-Object { $_.Extension -in '.exe', '.dll' } |
  ForEach-Object {
    $signature = Get-AuthenticodeSignature -LiteralPath $_.FullName
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Ollama') {
      throw "Runtime signature verification failed: $($_.FullName)"
    }
  }
.\uv.ps1 run python scripts/prepare_gemma.py
.\setup_kokoro.ps1
.\uv.ps1 run speech-translator
```

The app runs Gemma directly using the signed Vulkan runtime from the official Ollama distribution. You do not need to start an Ollama service.

Kokoro runs in `.venv-kokoro`, with dependencies pinned in `requirements-kokoro.lock`. For Windows and Python 3.13 compatibility, the setup script replaces two character width conversions in misaki 0.9.4 with equivalent jaconv calls.

The setup scripts download pinned model revisions and verify the SHA-256 hashes of the weights. Inference runs locally after setup. The app warms up both speech directions during initialization to reduce the wait on the first turn. It shuts down the translation server and speech synthesis worker when it exits. Setup does not change Windows security settings.

## GPU settings

`translation.gpu_device: Vulkan1` in [`config.yaml`](../config.yaml) selects the GTX 1650 on the test PC. GPU enumeration differs between systems, so change the setting to match the device you want to use. The default `translation.gpu_layers: 8` is also tuned for the test PC. Kokoro uses `tts.device: cuda:0`.

## Alternative engines

To use Qwen TTS, run `setup_qwen.ps1` and launch with `--settings config.qwen.yaml`. To use the earlier configuration, set `translation.engine: opus` and `tts.engine: legacy`.

## Audio processing and limits

The app records at the device's default sample rate and supported channel count, then converts the audio to mono float32. It resamples recognition input to 16 kHz and playback audio to the selected output device's default sample rate.

Manual recordings default to a 120-second limit. Recordings that exceed the limit and text that exceeds the translation model's input limit are rejected rather than silently truncated. Silence, empty text, model errors, and recording or playback failures are shown as `ERROR`. Start another recording to retry.

## Offline launch

After downloading and preparing the models, you can launch offline:

```powershell
$env:HF_HUB_OFFLINE = '1'
.\uv.ps1 run speech-translator
```
