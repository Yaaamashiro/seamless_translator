# Configuration and CLI Reference

[Back to README](../README.md)

## Automatic translation

Microphone A is assigned to Japanese and microphone B to English. The first microphone on which speech is detected takes the turn. The app does not identify speakers or detect the input language. If both microphones pick up the same speaker, the app may choose the wrong direction. Adjust microphone placement, distance, and input levels to reduce this.

The app uses the Silero voice activity detector (VAD) bundled with faster-whisper. It runs on the CPU and distinguishes speech from other sounds rather than relying on volume alone. After about 0.7 seconds of silence, the app recognizes, translates, synthesizes, and plays back the utterance. It discards input from both microphones during translation and playback and for 0.6 seconds after playback ends. Speech during this period is not queued for the next turn. Wait until the app shows **聞き取り中** (Listening) before speaking.

This timing guard helps prevent feedback loops. The app does not use acoustic echo cancellation (AEC) to match and remove playback audio, so long reverberation can still be picked up. Automatic mode handles one speaker at a time. It opens both input streams when started and closes them when stopped.

Adjust these values under `automatic` in [`config.yaml`](../config.yaml):

| Setting | Default | Description |
|---|---:|---|
| `threshold` | 0.6 | VAD speech probability threshold |
| `start_ms` | 96 | Consecutive speech detection required to start a turn, in milliseconds |
| `min_speech_ms` | 256 | Minimum speech duration to translate, in milliseconds |
| `silence_ms` | 704 | Silence required to end an utterance, in milliseconds |
| `pre_roll_ms` | 320 | Audio buffered before detection to preserve the start of the utterance, in milliseconds |
| `playback_guard_ms` | 600 | Period after playback during which input is ignored, in milliseconds |
| `max_utterance_seconds` | 20 | Utterance limit in seconds. If exceeded, the app discards the entire utterance and waits for silence before listening again. |

Manual recording and device changes are disabled while automatic mode is active. Stop automatic mode to use manual recording again.

## Device selection and routing

The app stores each selected device's index, name, and host API in `config.local.json`. On startup, it restores devices by matching their names and host APIs, even if their indices have changed. Select a device again if there is no match or more than one match.

You can also select devices when launching the GUI. The indices below are examples; use the current device list to find yours.

```powershell
.\uv.ps1 run speech-translator --list-devices
.\uv.ps1 run speech-translator --mic-a 25 --mic-b 26 --speaker-a 23 --speaker-b 20
.\uv.ps1 run speech-translator --configure
```

`--configure` prompts for roles omitted on the command line. Press Enter to reuse a saved selection. Use `--config <path>` to change where device selections are saved, and `--settings <path>` to select a different YAML settings file.

A device can appear more than once under MME, DirectSound, WASAPI, or WDM-KS. The list shows WASAPI entries first. The app rejects assigning the same device index to both participants, but it cannot tell whether entries under different APIs refer to the same hardware. Do not count Sound Mapper, which follows the Windows default device, or a virtual input as a separate physical device. If reconnecting a USB device and refreshing the list does not show it, restart the app.

## CLI checks

Replace the example device indices below with values from `--list-devices`. For recording tests, press Enter to start, then Enter again to stop. The app saves the WAV files specified in the commands.

```powershell
# Steps 1–2: Check Python and list devices
.\uv.ps1 run python --version
.\uv.ps1 run python -m speech_translator.main --list-devices --json

# Step 3: Test each microphone separately
.\uv.ps1 run speech-translator --test-record --input 25 --output-wav debug_audio/A.wav
.\uv.ps1 run speech-translator --test-record --input 26 --output-wav debug_audio/B.wav

# Step 4: Play a recording through the selected output
.\uv.ps1 run speech-translator --test-play debug_audio/A.wav --output 20
.\uv.ps1 run speech-translator --test-play debug_audio/B.wav --output 23

# Step 5: Select devices, record, and play the original audio to the other participant
.\uv.ps1 run speech-translator --cross-route A
.\uv.ps1 run speech-translator --cross-route B

# Step 6: Transcribe a WAV file
.\uv.ps1 run speech-translator --asr debug_audio/A.wav --language ja
.\uv.ps1 run speech-translator --asr debug_audio/B.wav --language en

# Step 7: Translate text
.\uv.ps1 run speech-translator --translate 'こんにちは。今日は沖縄から来ました。' --source-language ja
.\uv.ps1 run speech-translator --translate 'Nice to meet you.' --source-language en

# Step 8: Synthesize speech
.\uv.ps1 run speech-translator --tts 'Hello.' --language en --output-wav debug_audio/en.wav
.\uv.ps1 run speech-translator --tts 'はじめまして。' --language ja --output-wav debug_audio/ja.wav

# Step 9: Translate a WAV file and play the result through the selected output
.\uv.ps1 run speech-translator --pipeline debug_audio/A.wav --direction A --output 20
.\uv.ps1 run speech-translator --pipeline debug_audio/B.wav --direction B --output 23

# Run a turn-based conversation in the CLI, check model loading, or launch the GUI
.\uv.ps1 run speech-translator --cli
.\uv.ps1 run speech-translator --check-models
.\uv.ps1 run speech-translator --gui
```

## Models and voices

Edit [`config.yaml`](../config.yaml) and restart the app to apply changes. The GUI and CLI use the same settings.

| Component | Default |
|---|---|
| Speech recognition | faster-whisper small, CPU / int8 |
| Japanese–English translation | Gemma 4 E4B IT, official QAT Q4_0 GGUF, Vulkan GPU + CPU |
| Japanese and English speech synthesis | Kokoro 82M v1.0, CUDA / FP32 |
| Japanese voice | `jf_alpha` |
| English voice | `af_heart` |
| Audio I/O and GUI | sounddevice / PortAudio and PySide6 |

The default engines are `translation.engine: gemma4` and `tts.engine: kokoro`. The configuration offloads 8 of Gemma's 43 layers to `Vulkan1`, the GTX 1650 on the test PC. Kokoro synthesizes speech on `cuda:0` and does not automatically fall back to CPU.

For Japanese speech, Open JTalk determines how to read numbers and counters in context before passing the pronunciation to Kokoro. It does not replace specific words or hard-code the reading of `2階` (“second floor”). Readings of proper names and numbers can still be incorrect.

Speech synthesis rejects phoneme sequences longer than 510 characters. Break long utterances into shorter turns. Set `tts.ja_speaker` and `tts.en_speaker` to choose voices, and place the corresponding voice files in `models/kokoro-82m/voices/`.

## Stored files

- `config.local.json`: Saved device selections.
- `models/`: Model files for speech recognition, Gemma, Kokoro, and other engines.
- `logs/session_*.jsonl`: Translation direction, device indices, transcripts, translations, utterance lengths, processing times, and errors. Set `application.save_logs: false` to disable session logs.
- `debug_audio/`: Normal conversation audio is saved only when `debug.save_recordings: true`. This setting is off by default and does not affect WAV files explicitly requested through the CLI.
- `artifacts/`: Synthesized audio, model test results, and GUI screenshots from development checks.

`total_latency_sec` measures the time from stopping a manual recording or from the VAD finalizing an utterance to the start of the output stream. It excludes the automatic mode's wait for silence and the audio device's playback latency.

Log and recording paths are resolved relative to the directory containing the settings YAML file.
