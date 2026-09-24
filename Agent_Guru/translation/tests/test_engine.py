"""Tests for the real-time translation engine.

This package previously had no tests at all. These cover the four defects
found and fixed in the correction pipeline, plus the behaviour that must not
regress when the stub translator is replaced by a real model.

The defects:

1. CASCADING REPLACEMENT - corrections were applied as successive
   ``str.replace`` calls, so one correction's *output* could be re-matched by
   the next. With ``cat -> dog`` and ``dog -> bird`` recorded, "the cat sat"
   came out "the bird sat".
2. LOST SOURCE TEXT - ``translate()`` rebound ``text`` to the corrected form
   before storing it as ``TranslationResult.source_text``, so the field named
   for the user's input held something the user never said.
3. UNBOUNDED CORRECTIONS - ``_session_corrections`` grew for the life of the
   engine.
4. LATENCY PROPORTIONAL TO CORRECTION COUNT - N corrections meant N passes
   over the text on a path with a 300 ms budget, so the feature made itself
   slower the more it was used.
"""

from __future__ import annotations

import pytest

from Agent_Guru.translation.engine import (
    MAX_SESSION_CORRECTIONS,
    TRANSLATION_LATENCY_MS,
    TranslationEngine,
)


@pytest.fixture
def engine() -> TranslationEngine:
    return TranslationEngine()


class TestCorrectionsAreASubstitutionTable:
    """Defect 1: each input span is replaced exactly once."""

    def test_correction_output_is_not_re_corrected(
        self, engine: TranslationEngine
    ) -> None:
        engine.correct("cat", "dog")
        engine.correct("dog", "bird")
        result = engine.translate("the cat sat", "es")
        assert "the dog sat" in result.translated_text, (
            "a correction's output must not be re-matched by another "
            "correction; chained replacement is not a substitution table"
        )
        assert "bird" not in result.translated_text

    def test_independent_corrections_both_apply(
        self, engine: TranslationEngine
    ) -> None:
        engine.correct("teh", "the")
        engine.correct("recieve", "receive")
        result = engine.translate("teh recieve", "es")
        assert "the receive" in result.translated_text

    def test_longest_key_wins(self, engine: TranslationEngine) -> None:
        engine.correct("new", "NEW")
        engine.correct("new york", "NYC")
        result = engine.translate("new york city", "es")
        assert "NYC city" in result.translated_text, (
            "a longer key must take precedence over a shorter one it contains"
        )

    def test_substring_matching_semantics_are_preserved(
        self, engine: TranslationEngine
    ) -> None:
        """No word boundaries were applied before; none should be added.

        Changing this silently would alter every existing caller's results, so
        the single-pass rewrite deliberately keeps str.replace semantics.
        """
        engine.correct("cat", "X")
        assert "Xalog" in engine.translate("catalog", "es").translated_text

    def test_recording_the_same_phrase_twice_replaces_it(
        self, engine: TranslationEngine
    ) -> None:
        engine.correct("hi", "hello")
        engine.correct("hi", "greetings")
        result = engine.translate("hi there", "es")
        assert "greetings there" in result.translated_text
        assert "hello" not in result.translated_text

    def test_empty_source_phrase_is_ignored(self, engine: TranslationEngine) -> None:
        """An empty key matches at every position and would corrupt output."""
        engine.correct("", "JUNK")
        result = engine.translate("plain text", "es")
        assert "JUNK" not in result.translated_text
        assert "plain text" in result.translated_text

    def test_regex_metacharacters_are_literal(
        self, engine: TranslationEngine
    ) -> None:
        """Keys are user text, not patterns - they must be escaped."""
        engine.correct("c++", "cpp")
        engine.correct("a.b", "ab")
        result = engine.translate("c++ and a.b", "es")
        assert "cpp and ab" in result.translated_text

    def test_metacharacter_key_does_not_match_as_a_pattern(
        self, engine: TranslationEngine
    ) -> None:
        engine.correct("a.b", "MATCH")
        # "axb" would match the regex /a.b/ but is not the literal "a.b".
        assert "MATCH" not in engine.translate("axb", "es").translated_text

    def test_clear_corrections(self, engine: TranslationEngine) -> None:
        engine.correct("teh", "the")
        assert "the" in engine.translate("teh", "es").translated_text
        engine.clear_corrections()
        assert "teh" in engine.translate("teh", "es").translated_text


class TestSourceTextIsPreserved:
    """Defect 2: the result must report what the user actually said."""

    def test_source_text_is_the_uncorrected_input(
        self, engine: TranslationEngine
    ) -> None:
        engine.correct("recieve", "receive")
        result = engine.translate("i recieve mail", "es")
        assert result.source_text == "i recieve mail", (
            "source_text must be the user's input; the corrected form belongs "
            "in translated_text"
        )
        assert "receive" in result.translated_text

    def test_source_text_unchanged_without_corrections(
        self, engine: TranslationEngine
    ) -> None:
        result = engine.translate("hello world", "fr")
        assert result.source_text == "hello world"


class TestCorrectionsAreBounded:
    """Defect 3: memory must not grow with conversation length."""

    def test_corrections_are_capped(self, engine: TranslationEngine) -> None:
        for i in range(MAX_SESSION_CORRECTIONS * 4):
            engine.correct(f"word{i}", f"fix{i}")
        assert len(engine._session_corrections) == MAX_SESSION_CORRECTIONS

    def test_retained_size_does_not_track_correction_count(self) -> None:
        few, many = TranslationEngine(), TranslationEngine()
        for i in range(MAX_SESSION_CORRECTIONS + 1):
            few.correct(f"w{i}", f"f{i}")
        for i in range(MAX_SESSION_CORRECTIONS * 20):
            many.correct(f"w{i}", f"f{i}")
        assert len(few._session_corrections) == len(many._session_corrections)

    def test_eviction_is_least_recently_used(self, engine: TranslationEngine) -> None:
        """A phrase the user keeps correcting must survive a burst of one-offs."""
        engine.correct("important", "IMPORTANT")
        for i in range(MAX_SESSION_CORRECTIONS - 1):
            engine.correct(f"filler{i}", f"F{i}")
        # Refresh it, then push in enough one-offs to evict a stale entry.
        engine.correct("important", "IMPORTANT")
        for i in range(10):
            engine.correct(f"late{i}", f"L{i}")

        assert "important" in engine._session_corrections
        result = engine.translate("something important", "es")
        assert "IMPORTANT" in result.translated_text

    def test_oldest_correction_is_the_one_dropped(
        self, engine: TranslationEngine
    ) -> None:
        engine.correct("first", "FIRST")
        for i in range(MAX_SESSION_CORRECTIONS):
            engine.correct(f"w{i}", f"F{i}")
        assert "first" not in engine._session_corrections
        assert f"w{MAX_SESSION_CORRECTIONS - 1}" in engine._session_corrections


class TestLatencyIsIndependentOfCorrectionCount:
    """Defect 4: translation must not slow down as corrections accumulate."""

    @pytest.mark.performance
    def test_latency_does_not_scale_with_corrections(self) -> None:
        import time

        text = "the quick brown fox jumps over the lazy dog " * 20

        def best_of_three(correction_count: int) -> float:
            engine = TranslationEngine()
            for i in range(correction_count):
                engine.correct(f"zzq{i}", f"yyr{i}")
            engine.translate(text, "es")  # warm the compiled replacer
            timings = []
            for _ in range(3):
                start = time.perf_counter()
                for _ in range(20):
                    engine.translate(text, "es")
                timings.append((time.perf_counter() - start) / 20)
            return min(timings)

        baseline = best_of_three(0)
        loaded = best_of_three(MAX_SESSION_CORRECTIONS)

        # The old implementation was ~15x slower at this correction count and
        # grew without limit. Allow generous headroom for a loaded CI machine;
        # what is being asserted is "flat", not a specific nanosecond count.
        assert loaded < baseline * 4 + 0.001, (
            f"translate() took {loaded * 1000:.3f} ms with "
            f"{MAX_SESSION_CORRECTIONS} corrections vs "
            f"{baseline * 1000:.3f} ms with none; cost must not scale with "
            "the number of corrections"
        )

    def test_one_compile_serves_many_translations(
        self, engine: TranslationEngine
    ) -> None:
        """Structural proof, independent of any timing measurement."""
        engine.correct("a", "A")
        first = engine._correction_table()
        engine.translate("a", "es")
        engine.translate("a", "es")
        assert engine._correction_table() is first, (
            "the replacer must be reused across translations, not rebuilt"
        )

        engine.correct("b", "B")
        assert engine._correction_table() is not first, (
            "recording a correction must invalidate the compiled replacer"
        )


class TestDomainTerminology:
    def test_domain_terms_applied(self, engine: TranslationEngine) -> None:
        engine.set_domain("medical")
        result = engine.translate("check the blood pressure", "es")
        assert "BP" in result.translated_text

    def test_longest_domain_term_wins(self, engine: TranslationEngine) -> None:
        engine.set_domain("medical")
        result = engine.translate("he had a heart attack", "es")
        assert "myocardial infarction" in result.translated_text

    def test_unknown_domain_is_a_no_op(self, engine: TranslationEngine) -> None:
        engine.set_domain("underwater-basket-weaving")
        result = engine.translate("bug report", "es")
        assert "bug report" in result.translated_text

    def test_no_domain_leaves_text_alone(self, engine: TranslationEngine) -> None:
        result = engine.translate("fix the bug", "es")
        assert "fix the bug" in result.translated_text

    def test_domain_applies_after_corrections(
        self, engine: TranslationEngine
    ) -> None:
        engine.set_domain("technical")
        engine.correct("buhg", "bug")
        result = engine.translate("a buhg here", "es")
        assert "defect" in result.translated_text


class TestTranslateContract:
    def test_reports_requested_languages(self, engine: TranslationEngine) -> None:
        result = engine.translate("hello", "de", source_language="en")
        assert result.source_language == "en"
        assert result.target_language == "de"

    def test_detects_source_language_when_omitted(
        self, engine: TranslationEngine
    ) -> None:
        result = engine.translate("hola señor", "en")
        assert result.source_language == "es"

    def test_latency_recorded_and_within_budget(
        self, engine: TranslationEngine
    ) -> None:
        result = engine.translate("a short sentence", "es")
        assert result.latency_ms >= 0.0
        assert result.latency_ms < TRANSLATION_LATENCY_MS

    @pytest.mark.parametrize("text", ["", "   ", "\n\t "])
    def test_blank_input_produces_no_output(
        self, engine: TranslationEngine, text: str
    ) -> None:
        """Translating nothing must yield nothing, not a language tag.

        The stub translator prefixes every result with "[<target>] ", so blank
        input used to come back as a non-empty string and generate a subtitle
        entry holding that tag alone - a caption shown over silence.
        """
        result = engine.translate(text, "es")
        assert result.source_text == text
        assert result.translated_text == ""
        assert result.subtitles == []
        assert result.confidence == 0.0

    def test_blank_input_skips_corrections(
        self, engine: TranslationEngine
    ) -> None:
        engine.correct(" ", "SPACE")
        assert engine.translate("   ", "es").translated_text == ""

    def test_subtitles_generated(self, engine: TranslationEngine) -> None:
        result = engine.translate("one two three four five", "es")
        assert result.subtitles
        assert all(s.language == "es" for s in result.subtitles)

    def test_bidirectional_translates_both_sides(
        self, engine: TranslationEngine
    ) -> None:
        a, b = engine.translate_bidirectional("hello", "hola", "en", "es")
        assert a.target_language == "es"
        assert b.target_language == "en"


class TestLanguageDetection:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("plain english text", "en"),
            ("el niño pequeño", "es"),
            ("français très bien", "fr"),
        ],
    )
    def test_detects_language(
        self, engine: TranslationEngine, text: str, expected: str
    ) -> None:
        language, confidence = engine.detect_language(text)
        assert language == expected
        assert 0.0 <= confidence <= 1.0
