"""Subtitle generation synchronized with translated audio."""

from __future__ import annotations

from dataclasses import dataclass

#: Words shown per subtitle entry.
CHUNK_SIZE = 8


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
        """Generate subtitle entries from translated text.

        Args:
            translated_text: Text to lay out as subtitles.
            audio_start_ms: Offset of the first word in the audio stream.
            language: Language tag recorded on each entry.
            words_per_minute: Assumed reading/speaking rate. Must be positive.

        Returns:
            Contiguous subtitle entries, each covering at most CHUNK_SIZE words.

        Raises:
            ValueError: If words_per_minute is not positive.

        """
        # DEFECT FIX: words_per_minute went straight into `60000.0 / wpm` with
        # no guard. Zero raised a bare ZeroDivisionError from inside subtitle
        # generation - an unhelpful failure for a caller-supplied rate - and a
        # negative value silently produced entries whose end_ms preceded their
        # start_ms, i.e. subtitles no player can render, with no error at all.
        # The second case is the dangerous one: invalid output, no signal.
        if words_per_minute <= 0:
            msg = f"words_per_minute must be positive, got {words_per_minute}"
            raise ValueError(msg)

        words = translated_text.split()
        if not words:
            return []

        ms_per_word = 60000.0 / words_per_minute
        entries = []

        for i in range(0, len(words), CHUNK_SIZE):
            chunk = words[i : i + CHUNK_SIZE]
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
