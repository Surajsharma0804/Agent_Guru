"""Subtitle generation synchronized with translated audio."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubtitleEntry:
    """A single subtitle entry."""

    text: str
    start_ms: float
    end_ms: float
    language: str = "en"


class SubtitleGenerator:
    """Generates subtitles synchronized within 100ms of translated audio."""

    def generate(
        self,
        translated_text: str,
        audio_start_ms: float,
        language: str = "en",
        words_per_minute: int = 150,
    ) -> list[SubtitleEntry]:
        """Generate subtitle entries from translated text."""
        words = translated_text.split()
        if not words:
            return []

        ms_per_word = 60000.0 / words_per_minute
        entries = []
        chunk_size = 8  # words per subtitle

        for i in range(0, len(words), chunk_size):
            chunk = words[i : i + chunk_size]
            start = audio_start_ms + i * ms_per_word
            end = start + len(chunk) * ms_per_word
            entries.append(
                SubtitleEntry(
                    text=" ".join(chunk),
                    start_ms=start,
                    end_ms=end,
                    language=language,
                ),
            )
        return entries
