# Validation Notes

[Back to README](../README.md) · [Development Guide](DEVELOPMENT.md)

These measurements describe the development environment and are not performance guarantees. Files under `artifacts/` are generated locally and are not included in the repository. Run these commands from the repository root:

```powershell
.\uv.ps1 run python -m unittest discover -s tests -v
.\uv.ps1 run python scripts/check_kokoro.py
.\uv.ps1 run python scripts/check_automatic.py
```

## Automated tests

All 46 tests passed in the recorded run. Coverage includes input buffer isolation, audio routing, resampling, silence handling, error recovery, GUI controls, and saved device selections. The tests also cover incomplete translations, invalid audio, worker timeouts, and cleanup after startup failures.

## Gemma and Kokoro

The GPU check translated two short sentences, synthesized the translated speech, and transcribed the generated audio to check it.

| Direction | Translation | Translation time | Synthesis time |
|---|---|---:|---:|
| Japanese → English | Where is the station? | 1.06 s | 0.14 s |
| English → Japanese | 明日の午後3時に2階の受付で会いましょう。 (“Let's meet at the reception desk on the second floor tomorrow at 3 p.m.”) | 4.09 s | 0.44 s |

Initialization took about 19.5 seconds. The Japanese audio correctly pronounced `2階` (“second floor”) as *nikai*. Speech recognition transcribed it as the homophone `2回` (“twice”).

Measurements and generated WAV files are in `artifacts/kokoro-check/`. This check does not establish long-run stability or correct pronunciation for all expressions. The earlier GPU comparison with Qwen is recorded in `artifacts/tts-comparison/RESULTS.md`. The Kokoro configuration used in that comparison predates the Japanese pronunciation fix.

## Earlier OPUS, Open JTalk, and Piper configuration

This check used synthesized examples as inputs to the recognition, translation, and synthesis pipeline. These timings do not describe Gemma or Qwen performance.

| Direction | Transcript | Translation | Example processing time |
|---|---|---|---:|
| A → B | こんにちは。今日は沖縄から来ました。 | Hi. I'm from Okinawa today. | About 3.5 s |
| B → A | Nice to meet you. | 初めまして | About 2.9 s |

The timings end at file output and do not measure physical speaker latency. See `artifacts/model-check/results.json` and the corresponding `A_translated.wav` and `B_translated.wav` files.

## Device and GUI checks

The hardware check opened inputs 25 and 26 and wrote a low-volume test tone to outputs 20 and 23. Both inputs returned silence. In a separate GUI check, the models loaded and the app reached the ready-to-record state in about 21 seconds. The GUI continued to process events, though a gap of up to about 2.5 seconds between Python events during initial library loading could briefly delay interaction.

**Acceptance testing with two people taking turns on four physical audio devices is still pending.** Select the devices, then use the [recording and playback CLI checks](CONFIGURATION.md#cli-checks) to verify them.

## Automatic mode

The automatic check ran one turn in each language using the actual Silero VAD, speech recognition, Gemma, and Kokoro. Feeding the synthesized playback audio into both simulated microphone callbacks did not trigger an extra translation. Results are in `artifacts/automatic-check/results.json`.

Room reverberation has not been tested with physical microphones and speakers. Acoustic echo cancellation, streaming translation within an utterance, and simultaneous speech are not supported.
