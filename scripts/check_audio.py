"""Explicit device smoke test; short recording, then low-volume test tone."""
import argparse
import time

import numpy as np

from speech_translator.audio.pcm import Audio
from speech_translator.audio.recorder import Recorder
from speech_translator.audio.player import Player

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=int, required=True)
parser.add_argument('--output', type=int, required=True)
args = parser.parse_args()
recorder = Recorder(args.input)
try:
    recorder.start()
    time.sleep(.5)
    audio = recorder.stop()
    print(f'Input {args.input}: {audio.duration:.3f}s; peak={np.abs(audio.samples).max():.6f}')
except ValueError as exc:
    print(f'Input {args.input}: {exc}')
finally:
    recorder.close()
t = np.arange(4800) / 48000
tone = (.01 * np.sin(2 * np.pi * 440 * t) * np.sin(np.pi * np.arange(4800) / 4800) ** 2).astype('float32')
Player(args.output).play(Audio(tone, 48000))
print(f'Output {args.output}: stream write completed (audibility requires human confirmation)')
