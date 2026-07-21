"""Type stubs for pvporcupine (Picovoice wake word engine)."""
from typing import Sequence

KEYWORDS: list[str]

class Porcupine:
    frame_length: int
    sample_rate: int
    def process(self, pcm: Sequence[int]) -> int: ...
    def delete(self) -> None: ...

def create(
    access_key: str,
    keywords: list[str] | None = None,
    keyword_paths: list[str] | None = None,
    sensitivities: list[float] | None = None,
    model_path: str | None = None,
) -> Porcupine: ...
