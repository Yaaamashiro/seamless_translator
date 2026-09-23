import threading
from pathlib import Path

import numpy as np

from speech_translator.audio.pcm import Audio


class LocalTTS:
    def __init__(self, config, cache_dir, progress=lambda message: None):
        if config['ja_engine'] not in ('auto', 'openjtalk') or config['en_engine'] not in ('auto', 'piper'):
            raise ValueError('TTSはja_engine: openjtalk / en_engine: piperを指定してください。')
        import pyopenjtalk
        from huggingface_hub import hf_hub_download
        from piper import PiperVoice
        self.jtalk = pyopenjtalk
        self.lock = threading.Lock()
        progress('Japanese TTS: ロード中')
        self.synthesize('準備ができました。', 'ja')
        progress('✓ Japanese TTS (Open JTalk)')
        voice = config['en_voice']
        # Use HF's atomic cache downloader, so interrupted downloads cannot become valid models.
        language, speaker, quality = voice.split('-')
        folder = f'{language.split("_")[0]}/{language}/{speaker}/{quality}'
        progress('English TTS: ロード中')
        root = Path(cache_dir)
        model = hf_hub_download('rhasspy/piper-voices', f'{folder}/{voice}.onnx', local_dir=root)
        metadata = hf_hub_download('rhasspy/piper-voices', f'{folder}/{voice}.onnx.json', local_dir=root)
        self.piper = PiperVoice.load(model, config_path=metadata)
        self.synthesize('Ready.', 'en')
        progress('✓ English TTS (Piper)')

    def synthesize(self, text: str, language: str) -> Audio:
        if not text.strip():
            raise ValueError('音声合成のテキストが空です。')
        with self.lock:
            if language == 'ja':
                samples, rate = self.jtalk.tts(text)
                audio = Audio((samples / 32768.0).astype('float32'), int(rate))
            elif language == 'en':
                chunks = list(self.piper.synthesize(text))
                if not chunks:
                    raise ValueError('英語TTSが音声を生成しませんでした。')
                audio = Audio(np.concatenate([c.audio_float_array for c in chunks]), chunks[0].sample_rate)
            else:
                raise ValueError(f'未対応のTTS言語: {language}')
        audio.validate()
        return audio
