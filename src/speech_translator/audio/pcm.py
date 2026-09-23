from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


@dataclass
class Audio:
    samples: np.ndarray
    sample_rate: int

    @property
    def duration(self):
        return len(self.samples) / self.sample_rate

    def resampled(self, rate: int):
        if rate == self.sample_rate:
            return self
        divisor = gcd(rate, self.sample_rate)
        return Audio(resample_poly(self.samples, rate // divisor,
                                   self.sample_rate // divisor, axis=0).astype('float32'), rate)

    def validate(self, silence_threshold=0.0001):
        if self.sample_rate <= 0 or len(self.samples) == 0:
            raise ValueError('空の音声です。録音時間とマイク接続を確認してください。')
        if not np.isfinite(self.samples).all():
            raise ValueError('音声に不正なPCM値が含まれています。')
        if np.sqrt(np.mean(np.square(self.samples, dtype=np.float64))) < silence_threshold:
            raise ValueError('無音です。マイクの接続・ミュート・入力音量を確認してください。')

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), self.samples, self.sample_rate, subtype='PCM_16')

    @classmethod
    def load(cls, path):
        data, rate = sf.read(str(path), dtype='float32', always_2d=True)
        return cls(data.mean(axis=1), rate)
