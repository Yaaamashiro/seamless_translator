"""Hands-free turn taking. No new audio is admitted during inference/playback/tail."""
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import sounddevice as sd
from speech_translator.audio.pcm import Audio
from speech_translator.audio.vad import FRAME, StreamingVAD, SpeechSegmenter
from speech_translator.pipeline.channel import ChannelState

class AutomaticConversation:
    def __init__(self, channels, config, notify=lambda running, message: None):
        self.channels = channels
        self.config = config['automatic']
        self.notify = notify
        self.stopping = threading.Event()
        self.accepting = threading.Event()
        self.queue = queue.Queue(maxsize=20)
        self.capture_error = None
        self.accept_since = float('inf')
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='automatic-vad')
        self.future = None
        self.processing = None

    def start(self):
        if self.future is not None:
            raise RuntimeError('自動翻訳は起動済みです。')
        self.future = self.executor.submit(self._run)
        self.executor.shutdown(wait=False)
        return self.future

    def stop(self):
        self.stopping.set()
        self.accepting.clear()
        for channel in self.channels.values():
            channel.cancelled.set()
            channel.player.cancel()

    def _callback(self, direction, rate):
        def callback(data, frames, timing, status):
            if status:
                self.capture_error = 'マイク入力が欠落しました: ' + str(status)
            if not self.accepting.is_set() or self.stopping.is_set():
                return
            # Reject buffered audio acquired before reopening the listening window.
            captured = time.perf_counter() - max(0, timing.currentTime - timing.inputBufferAdcTime)
            if captured < self.accept_since:
                return
            try:
                self.queue.put_nowait((direction, rate, captured, data.mean(axis=1).copy()))
            except queue.Full:
                self.capture_error = '音声処理が入力に追いつきません。自動翻訳を停止しました。'
        return callback

    def _clear_queue(self):
        while True:
            try: self.queue.get_nowait()
            except queue.Empty: break

    def _listen(self, detectors, segmenters, pending):
        self.accepting.clear()
        self._clear_queue()
        for key in self.channels:
            detectors[key].reset()
            segmenters[key].reset()
            pending[key] = np.empty(0, dtype='float32')
        self.accept_since = time.perf_counter()
        if not self.stopping.is_set():
            self.accepting.set()
            self.notify(True, '聞き取り中：どちらか一人ずつ話してください。')

    def _run(self):
        streams = []
        active = None
        failure = None
        try:
            self.notify(True, '自動翻訳を準備中…')
            from faster_whisper.vad import get_vad_model
            session = get_vad_model().session
            detectors = {key: StreamingVAD(session) for key in self.channels}
            segmenters = {key: SpeechSegmenter(self.config) for key in self.channels}
            pending = {}
            for key, channel in self.channels.items():
                if self.stopping.is_set(): return
                channel.cancelled.clear()
                info = sd.query_devices(channel.input_device, 'input')
                rate = int(info['default_samplerate'])
                stream = sd.InputStream(device=channel.input_device, samplerate=rate,
                    channels=int(info['max_input_channels']), dtype='float32',
                    blocksize=round(rate / 10), callback=self._callback(key, rate))
                streams.append(stream)
                stream.start()
            self._listen(detectors, segmenters, pending)
            resume_at = None
            while not self.stopping.is_set():
                if self.capture_error:
                    raise RuntimeError(self.capture_error)
                if any(not stream.active for stream in streams):
                    raise RuntimeError('マイク入力が停止しました。デバイス接続を確認してください。')
                if self.processing is not None:
                    if not self.processing.done():
                        self.stopping.wait(.02)
                        continue
                    self.processing.result()
                    self.processing = None
                    resume_at = time.perf_counter() + self.config['playback_guard_ms'] / 1000
                    self.notify(True, '再生後の余韻待ち…')
                if resume_at is not None:
                    if time.perf_counter() < resume_at:
                        self.stopping.wait(.02)
                        continue
                    resume_at = None
                    active = None
                    self._listen(detectors, segmenters, pending)
                try:
                    key, rate, captured, pcm = self.queue.get(timeout=.1)
                except queue.Empty:
                    continue
                if captured < self.accept_since or (active is not None and key != active):
                    continue
                frames = Audio(pcm, rate).resampled(16000).samples
                pending[key] = np.concatenate((pending[key], frames))
                while len(pending[key]) >= FRAME and not self.stopping.is_set():
                    frame, pending[key] = pending[key][:FRAME], pending[key][FRAME:]
                    event, audio = segmenters[key].feed(frame, detectors[key].probability(frame))
                    if event == 'start':
                        active = key
                        channel = self.channels[key]
                        channel.emit(asr_text='', translated_text='', error='', total_latency_sec=None)
                        channel.set_state(ChannelState.RECORDING)
                        self.notify(True, ('A（日本語）' if key == 'A_TO_B' else 'B（英語）') + 'の発話を検出。話し終わると自動で翻訳します。')
                    elif event == 'too_long':
                        self.notify(True, '発話が長すぎるため破棄します。一度話すのを止め、短く話してください。')
                    elif event == 'discard':
                        self.channels[key].set_state(ChannelState.IDLE)
                        active = None
                        self._listen(detectors, segmenters, pending)
                        break
                    elif event == 'end':
                        self.accepting.clear()
                        self._clear_queue()
                        channel = self.channels[key]
                        channel.set_state(ChannelState.PROCESSING)
                        self.notify(True, '翻訳・再生中：次の発話は聞き取り再開後にお願いします。')
                        self.processing = channel.executor.submit(channel.process, audio)
                        break
        except Exception as exc:
            failure = f'自動翻訳停止: {type(exc).__name__}: {exc}'
        finally:
            self.accepting.clear()
            for stream in streams:
                try:
                    stream.abort()
                    stream.close()
                except Exception as exc:
                    failure = failure or f'入力終了エラー: {exc}'
            # Never allow manual mode/new capture while a previous pipeline still runs.
            if self.processing is not None:
                for channel in self.channels.values():
                    channel.cancelled.set()
                    channel.player.cancel()
                try: self.processing.result()
                except Exception as exc: failure = failure or str(exc)
            for channel in self.channels.values():
                if channel.state == ChannelState.RECORDING:
                    channel.set_state(ChannelState.IDLE)
            self._clear_queue()
            self.notify(False, failure or '自動翻訳を停止しました。')
