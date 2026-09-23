from typing import Protocol


class Translator(Protocol):
    def translate(self, text: str, source_language: str, target_language: str) -> str: ...
