from typing import Protocol
from speech_translator.audio.pcm import Audio


class TTSEngine(Protocol):
    def synthesize(self, text: str, language: str) -> Audio: ...
