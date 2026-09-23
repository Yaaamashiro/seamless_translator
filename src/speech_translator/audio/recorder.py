import threading

import numpy as np
import sounddevice as sd

from speech_translator.audio.pcm import Audio


class Recorder:
    def __init__(self, device: int, max_seconds=120):
        self.device = device
        self.max_seconds = max_seconds
        self.stream = None
        self.lock = threading.Lock()
        self.chunks = []
        self.error = None
        self.frames = 0

    def start(self):
        if self.stream is not None:
            raise RuntimeError('すでに録音中です。')
        self.chunks = []
        self.error = None
        self.frames = 0
        info = sd.query_devices(self.device, 'input')
        self.rate = int(info['default_samplerate'])
        # Some WASAPI endpoints only accept their native channel count.
        channels = int(info['max_input_channels'])
        sd.check_input_settings(device=self.device, samplerate=self.rate,
                                channels=channels, dtype='float32')
        self.stream = sd.InputStream(device=self.device, samplerate=self.rate,
                                     channels=channels, dtype='float32', callback=self._callback)
        try:
            self.stream.start()
        except Exception:
            self.close()
            raise

    def _callback(self, data, frames, time_info, status):
        with self.lock:
            if status:
                self.error = f'録音データが欠落しました: {status}'
            if self.frames + frames > self.rate * self.max_seconds:
                self.error = f'録音上限（{self.max_seconds}秒）を超えました。短く録音してください。'
                raise sd.CallbackAbort
            self.chunks.append(data.mean(axis=1).copy())
            self.frames += frames

    def stop(self):
        if self.stream is None:
            raise RuntimeError('録音していません。')
        inactive = not self.stream.active
        self.close()
        with self.lock:
            chunks, self.chunks = self.chunks, []
        if self.error:
            raise RuntimeError(self.error)
        if inactive:
            raise RuntimeError('録音が中断されました。デバイスの接続を確認してください。')
        audio = Audio(np.concatenate(chunks) if chunks else np.empty(0, dtype='float32'), self.rate)
        audio.validate()
        return audio

    def close(self):
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
