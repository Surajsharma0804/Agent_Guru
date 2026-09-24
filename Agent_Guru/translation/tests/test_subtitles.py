"""Tests for subtitle generation.

Covers the two unguarded-input defects fixed in SubtitleGenerator.generate:
``words_per_minute=0`` raised a bare ZeroDivisionError from inside the
generator, and a negative rate silently produced entries whose ``end_ms``
preceded their ``start_ms`` - subtitles no player can render, with no error
raised at all.
"""

from __future__ import annotations

import pytest

from Agent_Guru.translation.subtitles import CHUNK_SIZE, SubtitleEntry, SubtitleGenerator


@pytest.fixture
def generator() -> SubtitleGenerator:
    return SubtitleGenerator()


class TestRateValidation:
    @pytest.mark.parametrize("wpm", [0, -1, -150])
    def test_rejects_non_positive_rate(
        self, generator: SubtitleGenerator, wpm: int
    ) -> None:
        with pytest.raises(ValueError, match="words_per_minute must be positive"):
            generator.generate("hello world", 0.0, "en", words_per_minute=wpm)

    def test_valid_rate_accepted(self, generator: SubtitleGenerator) -> None:
        assert generator.generate("hello world", 0.0, "en", words_per_minute=1)


class TestTimings:
    def test_entries_have_positive_duration(
        self, generator: SubtitleGenerator
    ) -> None:
        entries = generator.generate("a b c d e f g h i j", 0.0, "en")
        assert entries
        for entry in entries:
            assert entry.end_ms > entry.start_ms, (
                "a subtitle that ends before it starts cannot be rendered"
            )

    def test_entries_are_contiguous_and_ordered(
        self, generator: SubtitleGenerator
    ) -> None:
        entries = generator.generate(" ".join(str(i) for i in range(25)), 0.0, "en")
        assert len(entries) > 1
        for earlier, later in zip(entries, entries[1:], strict=False):
            assert later.start_ms == pytest.approx(earlier.end_ms), (
                "gaps or overlaps between entries break audio sync"
            )

    def test_first_entry_starts_at_the_audio_offset(
        self, generator: SubtitleGenerator
    ) -> None:
        entries = generator.generate("hello world", 1234.5, "en")
        assert entries[0].start_ms == pytest.approx(1234.5)

    def test_duration_scales_with_word_count(
        self, generator: SubtitleGenerator
    ) -> None:
        one = generator.generate("word", 0.0, "en")[0]
        four = generator.generate("word word word word", 0.0, "en")[0]
        assert four.end_ms == pytest.approx((one.end_ms - one.start_ms) * 4)

    def test_faster_rate_means_shorter_entries(
        self, generator: SubtitleGenerator
    ) -> None:
        slow = generator.generate("a b c d", 0.0, "en", words_per_minute=60)[0]
        fast = generator.generate("a b c d", 0.0, "en", words_per_minute=240)[0]
        assert fast.end_ms < slow.end_ms


class TestChunking:
    def test_empty_text_yields_no_entries(
        self, generator: SubtitleGenerator
    ) -> None:
        assert generator.generate("", 0.0, "en") == []

    def test_whitespace_only_yields_no_entries(
        self, generator: SubtitleGenerator
    ) -> None:
        assert generator.generate("   \n\t ", 0.0, "en") == []

    def test_no_entry_exceeds_the_chunk_size(
        self, generator: SubtitleGenerator
    ) -> None:
        entries = generator.generate(" ".join(str(i) for i in range(50)), 0.0, "en")
        assert all(len(e.text.split()) <= CHUNK_SIZE for e in entries)

    def test_every_word_appears_exactly_once(
        self, generator: SubtitleGenerator
    ) -> None:
        words = [f"w{i}" for i in range(37)]
        entries = generator.generate(" ".join(words), 0.0, "en")
        assert [w for e in entries for w in e.text.split()] == words

    def test_exact_multiple_of_chunk_size(
        self, generator: SubtitleGenerator
    ) -> None:
        entries = generator.generate(" ".join("w" * 1 for _ in range(CHUNK_SIZE * 3)), 0.0, "en")
        assert len(entries) == 3

    def test_single_word(self, generator: SubtitleGenerator) -> None:
        entries = generator.generate("hello", 0.0, "en")
        assert len(entries) == 1
        assert entries[0].text == "hello"

    def test_runs_of_whitespace_are_collapsed(
        self, generator: SubtitleGenerator
    ) -> None:
        entries = generator.generate("a     b\n\nc", 0.0, "en")
        assert entries[0].text == "a b c"


class TestLanguageTag:
    def test_language_recorded_on_every_entry(
        self, generator: SubtitleGenerator
    ) -> None:
        entries = generator.generate(" ".join(str(i) for i in range(20)), 0.0, "de")
        assert entries
        assert all(e.language == "de" for e in entries)

    def test_language_defaults_to_english(
        self, generator: SubtitleGenerator
    ) -> None:
        assert generator.generate("hello", 0.0)[0].language == "en"

    def test_entries_are_subtitle_entries(
        self, generator: SubtitleGenerator
    ) -> None:
        assert all(
            isinstance(e, SubtitleEntry) for e in generator.generate("a b", 0.0)
        )
