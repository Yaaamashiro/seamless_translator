# Seamless Translator

A Windows app for two-way Japanese–English voice translation in face-to-face conversations. Each participant uses a separate microphone, and translated speech plays through the other participant's speaker or headphones.

**Windows 11 · Japanese ⇄ English · Local inference**

[Setup](#setup) · [Usage](#usage) · [Configuration](#configuration) · [Documentation](#documentation)

## Features

- **Automatic turn-based translation** — Detects the start and end of speech, then translates and reads it aloud.
- **Manual recording** — Starts and stops recording with a button or keyboard shortcut.
- **Separate audio devices** — Supports two microphones and two output devices, with saved device selections.
- **Transcripts and translations** — Displays recognized speech, translated text, and processing status in the GUI.
- **Local processing** — Runs speech recognition, translation, and speech synthesis on your PC without sending conversation audio to external APIs.

## How it works

| Participant | Input | Translation | Output |
|---|---|---|---|
| Japanese speaker (A) | Microphone A | Japanese → English | Speaker B |
| English speaker (B) | Microphone B | English → Japanese | Speaker A |

Each microphone has a fixed input language. The first microphone to detect speech takes the current turn. The app does not identify speakers or automatically detect the input language.

### Models

| Task | Default model or implementation | Execution |
|---|---|---|
| Voice activity detection | Silero VAD | CPU |
| Speech recognition | faster-whisper / Whisper small | CPU (int8) |
| Translation | Gemma 4 E4B IT (QAT Q4_0) | Vulkan GPU + CPU |
| Speech synthesis | Kokoro 82M v1.0 | NVIDIA GPU (CUDA) |

The GUI uses PySide6, and audio input/output uses sounddevice / PortAudio.

## Requirements

| Component | Requirement |
|---|---|
| OS | Windows 11 |
| Python | 3.13 |
| Tools | Git and [uv](https://docs.astral.sh/uv/getting-started/installation/) |
| GPU | NVIDIA GPU with CUDA and Vulkan support |
| Audio | Two microphones and two speaker or headphone outputs |

Tested on a GTX1650 with 4 GB of VRAM. The included GPU settings are tuned for this environment. An internet connection is required to download models during initial setup.

## Setup

### 1. Clone the repository

Run the following commands in PowerShell:

```powershell
git clone https://github.com/Yaaamashiro/seamless_translator.git
cd seamless_translator
uv sync --locked
```

### 2. Prepare the models

Follow the [model setup guide](docs/SETUP.md) to install the Gemma runtime and model, and set up Kokoro. Check the GPU configuration described in that guide as well.

Models and virtual environments are not included in the repository. Docker, WSL, and external API keys are not required.

### 3. Launch the app

```powershell
.\uv.ps1 run speech-translator
```

## Usage

The GUI currently uses mainly Japanese labels. The steps below include the labels shown in the app.

1. **Select audio devices** — Assign the Japanese speaker to A and the English speaker to B, then choose each participant's microphone and output device.
2. **Prepare the models** — Click **設定を保存して準備** (Save settings and prepare) and wait for initialization to finish.
3. **Start automatic translation** — Click **自動翻訳を開始（ターン制）** (Start automatic translation, turn-based).
4. **Speak one at a time** — After roughly 0.7 seconds of silence, the app finalizes the utterance and plays the translation. Wait until the status returns to **聞き取り中** (Listening) before speaking again.
5. **Stop** — Click **自動翻訳を停止** (Stop automatic translation).

For manual recording, stop automatic mode and use `Start A Recording` or `Start B Recording`. Click the same button again to stop recording. When the app has focus, keys `1` and `2` start or stop recording for A and B, respectively.

## Configuration

Edit [`config.yaml`](config.yaml) to change models, voices, or speech detection settings, then restart the app.

| Setting | Default behavior |
|---|---|
| Silence required to end an utterance | Approximately 0.7 seconds |
| Input exclusion period after playback | 0.6 seconds |
| Maximum utterance in automatic mode | 20 seconds; the entire utterance is discarded if exceeded |
| Voices | Japanese: `jf_alpha` / English: `af_heart` |
| Saved device selections | `config.local.json` |

**Source transcripts and translations are logged by default.** Set `application.save_logs: false` to disable logging. Audio recordings of normal conversations are not saved by default.

For detailed settings, switching to Qwen TTS, and selecting devices through the CLI, see the [configuration and CLI reference](docs/CONFIGURATION.md) and the [model setup guide](docs/SETUP.md).

## Limitations

- Participants must take turns. Simultaneous speech and streaming translation while someone is still speaking are not supported.
- Input is discarded during translation and playback, and for 0.6 seconds after playback ends. Speech during these periods is not translated.
- Acoustic echo cancellation (AEC) that removes playback audio from microphone input is not implemented. If both microphones pick up the same voice, the app may assign the turn to the wrong participant.
- Japanese–English processing has been checked with real models, and feedback-loop prevention has been tested with simulated input. Acceptance testing with two people, four physical audio devices, and room reverberation is still pending.

## Documentation

| Guide | Contents |
|---|---|
| [Model setup](docs/SETUP.md) | Downloads, runtimes, GPU settings, and alternative TTS engines |
| [Configuration and CLI reference](docs/CONFIGURATION.md) | Speech detection, device selection, commands, and stored data |
| [Development guide](docs/DEVELOPMENT.md) | Source layout, tests, and development scripts |
| [Validation notes](docs/VALIDATION.md) | Measurements and verification scope in the development environment |
| [Engine and model references](docs/REFERENCES.md) | Upstream sources and third-party license information |

## License

The original source code in this repository is licensed under the [MIT License](LICENSE). Third-party engines, models, and voices are subject to their respective licenses. See the [references](docs/REFERENCES.md) and the [third-party license notice](THIRD_PARTY/Mei-voice-license.txt).
