import threading

import numpy as np
import sounddevice as sd


class Player:
    def __init__(self, device: int):
        self.device = device
        self.cancelled = threading.Event()

    def play(self, audio, on_start=lambda: None):
        audio.validate()
        self.cancelled.clear()
        info = sd.query_devices(self.device, 'output')
        rate = int(info['default_samplerate'])
        channels = min(2, int(info['max_output_channels']))
        audio = audio.resampled(rate)
        mono = audio.samples if audio.samples.ndim == 1 else audio.samples.mean(axis=1)
        pcm = np.repeat(mono[:, None], channels, axis=1).astype('float32')
        # Per-instance streams avoid sounddevice.play()'s global playback state.
        with sd.OutputStream(device=self.device, samplerate=rate, channels=channels,
                             dtype='float32') as stream:
            on_start()
            for offset in range(0, len(pcm), 2048):
                if self.cancelled.is_set():
                    stream.abort()
                    raise RuntimeError('再生を中止しました。')
                if stream.write(pcm[offset:offset + 2048]):
                    raise RuntimeError('再生が途切れました（出力バッファ不足）。')

    def cancel(self):
        self.cancelled.set()
