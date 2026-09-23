"""Streaming Silero state and bounded speech segmentation (16 kHz / 512 samples)."""
from collections import deque
import math
import numpy as np
from speech_translator.audio.pcm import Audio

RATE = 16000
FRAME = 512

class StreamingVAD:
    def __init__(self, session):
        self.session = session
        self.reset()

    def reset(self):
        self.h = np.zeros((1, 1, 128), dtype='float32')
        self.c = np.zeros_like(self.h)
        self.context = np.zeros(64, dtype='float32')

    def probability(self, frame):
        output, self.h, self.c = self.session.run(None, {
            'input': np.concatenate((self.context, frame))[None, :],
            'h': self.h, 'c': self.c})
        self.context = frame[-64:].copy()
        return float(output.reshape(-1)[0])

class SpeechSegmenter:
    def __init__(self, config):
        self.config = config
        self.start_frames = math.ceil(config['start_ms'] / 32)
        self.end_frames = math.ceil(config['silence_ms'] / 32)
        self.min_frames = math.ceil(config['min_speech_ms'] / 32)
        self.max_frames = math.ceil(config['max_utterance_seconds'] * RATE / FRAME)
        self.pre_frames = math.ceil(config['pre_roll_ms'] / 32) + self.start_frames
        self.reset()

    def reset(self):
        self.pre = deque(maxlen=self.pre_frames)
        self.chunks = []
        self.active = False
        self.speech_count = self.consecutive = self.quiet = self.elapsed = 0
        self.discarding = False

    def feed(self, frame, probability):
        speech = probability >= self.config['threshold']
        if not self.active:
            self.pre.append(frame.copy())
            self.consecutive = self.consecutive + 1 if speech else 0
            if self.consecutive < self.start_frames:
                return None, None
            self.active = True
            self.chunks = list(self.pre)
            self.speech_count = self.consecutive
            self.elapsed = self.consecutive
            return 'start', None
        self.elapsed += 1
        self.quiet = 0 if speech else self.quiet + 1
        if speech:
            self.speech_count += 1
        if not self.discarding:
            self.chunks.append(frame.copy())
        if self.elapsed >= self.max_frames and not self.discarding:
            self.discarding = True
            self.chunks.clear()
            return 'too_long', None
        if self.quiet < self.end_frames:
            return None, None
        if self.discarding or self.speech_count < self.min_frames:
            self.reset()
            return 'discard', None
        # Keep a little trailing silence, rather than passing all endpoint waiting to ASR.
        trim = max(0, self.quiet - 3)
        chunks = self.chunks[:-trim] if trim else self.chunks
        audio = Audio(np.concatenate(chunks), RATE)
        self.reset()
        return 'end', audio
