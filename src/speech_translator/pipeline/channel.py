import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from time import perf_counter

from speech_translator.audio.recorder import Recorder
from speech_translator.audio.player import Player


class ChannelState(Enum):
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()
    PLAYING = auto()
    ERROR = auto()


class Channel:
    def __init__(self, direction, input_device, output_device, source_language, target_language,
                 asr, translator, tts, config, logger, notify=lambda event: None,
                 recorder=None, player=None):
        self.direction = direction
        self.input_device, self.output_device = input_device, output_device
        self.source_language, self.target_language = source_language, target_language
        self.asr, self.translator, self.tts = asr, translator, tts
        self.config, self.logger, self.notify = config, logger, notify
        self.recorder = recorder or Recorder(input_device, config['audio']['max_recording_seconds'])
        self.player = player or Player(output_device)
        self.state = ChannelState.IDLE
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=direction)
        self.cancelled = threading.Event()
        self.closed = False

    def emit(self, **fields):
        self.notify({'direction': self.direction, **fields})

    def set_state(self, state):
        self.state = state
        self.emit(state=state.name)

    def toggle(self):
        if self.closed:
            return
        if self.state in (ChannelState.IDLE, ChannelState.ERROR):
            self.cancelled.clear()
            self.emit(asr_text='', translated_text='', error='', total_latency_sec=None)
            self.set_state(ChannelState.RECORDING)
            self.executor.submit(self._start)
        elif self.state == ChannelState.RECORDING:
            stopped_at = perf_counter()
            self.set_state(ChannelState.PROCESSING)
            self.executor.submit(self._stop_and_process, stopped_at)

    def _start(self):
        try:
            self.recorder.start()
        except Exception as exc:
            self._fail(exc)

    def _fail(self, exc, record=None):
        message = f'{type(exc).__name__}: {exc}'
        if 'memory' in message.lower() or 'cuda' in message.lower():
            message += ' — config.yamlのtranslation.gpu_layersを減らすか、他のGPUアプリを終了して再試行してください。'
        try:
            self.logger.write({**(record or self._record()), 'error': message})
        except Exception as log_error:
            message += f' / ログ保存失敗: {log_error}'
        self.emit(error=message)
        self.set_state(ChannelState.ERROR)

    def _record(self):
        return {'direction': self.direction, 'source_language': self.source_language,
                'target_language': self.target_language, 'input_device': self.input_device,
                'output_device': self.output_device}

    def _stop_and_process(self, stopped_at):
        try:
            audio = self.recorder.stop()
            self.process(audio, stopped_at)
        except Exception as exc:
            self._fail(exc)

    def check_cancelled(self):
        if self.cancelled.is_set():
            raise RuntimeError('処理を中止しました。')

    def process(self, audio, stopped_at=None):
        """Synchronous entry for CLI/file tests; GUI runs it on the channel worker."""
        started = perf_counter() if stopped_at is None else stopped_at
        record = self._record()
        try:
            self.set_state(ChannelState.PROCESSING)
            audio.validate()
            record['speech_duration_sec'] = audio.duration
            if self.config['debug']['save_recordings']:
                audio.save(Path(self.config['debug']['recording_directory']) /
                           f'{self.direction}_{datetime.now():%Y%m%d_%H%M%S_%f}.wav')
            pcm = audio.resampled(self.config['audio']['sample_rate'])
            self.check_cancelled()
            stage = perf_counter()
            text = self.asr.transcribe(pcm.samples, pcm.sample_rate, self.source_language).strip()
            record.update(asr_text=text, asr_latency_sec=perf_counter() - stage)
            if not text:
                raise ValueError('音声を認識できませんでした。もう一度話してください。')
            self.emit(asr_text=text)
            self.check_cancelled()
            stage = perf_counter()
            translated = self.translator.translate(text, self.source_language, self.target_language).strip()
            record.update(translated_text=translated, translation_latency_sec=perf_counter() - stage)
            if not translated:
                raise ValueError('翻訳結果が空です。')
            self.emit(translated_text=translated)
            self.check_cancelled()
            stage = perf_counter()
            result = self.tts.synthesize(translated, self.target_language)
            record['tts_latency_sec'] = perf_counter() - stage
            self.check_cancelled()

            def on_start():
                record['total_latency_sec'] = perf_counter() - started
                self.emit(total_latency_sec=record['total_latency_sec'])
                self.set_state(ChannelState.PLAYING)

            self.player.play(result, on_start=on_start)
            self.logger.write(record)
            self.emit(metrics=record)
            self.set_state(ChannelState.IDLE)
            return record
        except Exception as exc:
            self._fail(exc, record)
            return None

    def close(self):
        self.closed = True
        self.cancelled.set()
        self.player.cancel()
        future = self.executor.submit(self.recorder.close)
        self.executor.shutdown(wait=False)
        return future
