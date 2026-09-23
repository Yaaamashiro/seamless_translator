from typing import Protocol


class ASREngine(Protocol):
    def transcribe(self, audio, sample_rate: int, language: str) -> str: ...
