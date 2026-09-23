import threading

from speech_translator.audio.pcm import Audio


class FasterWhisperASR:
    def __init__(self, config, cache_dir):
        from faster_whisper import WhisperModel
        if config['engine'] != 'faster-whisper':
            raise ValueError(f'未対応のASR: {config["engine"]}')
        self.lock = threading.Lock()
        self.model = WhisperModel(config['model'], device=config['device'],
                                  compute_type=config['compute_type'], download_root=str(cache_dir))

    def transcribe(self, audio, sample_rate: int, language: str) -> str:
        pcm = Audio(audio, sample_rate).resampled(16000)
        pcm.validate()
        with self.lock:
            segments, _ = self.model.transcribe(pcm.samples, language=language, beam_size=5,
                                                vad_filter=False, condition_on_previous_text=False)
            return ' '.join(segment.text.strip() for segment in segments).strip()
