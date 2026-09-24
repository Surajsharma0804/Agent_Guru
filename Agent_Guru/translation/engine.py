"""Real-Time Multilingual Translation Engine."""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import lru_cache

from Agent_Guru.translation.subtitles import SubtitleEntry, SubtitleGenerator

logger = logging.getLogger(__name__)

TRANSLATION_LATENCY_MS = 300
LOW_CONFIDENCE_THRESHOLD = 0.7
LANGUAGE_DETECTION_THRESHOLD = 0.85

try:
    import seamless_communication  # type: ignore[import]  # noqa: F401

    _SEAMLESS_AVAILABLE = True
except ImportError:
    _SEAMLESS_AVAILABLE = False

# Domain-specific terminology adapters
DOMAIN_TERMS: dict[str, dict[str, str]] = {
    "medical": {"heart attack": "myocardial infarction", "blood pressure": "BP"},
    "legal": {"agreement": "contract", "lawsuit": "litigation"},
    "technical": {"bug": "defect", "fix": "patch"},
}

#: Upper bound on session corrections retained per engine instance.
#:
#: Corrections come from the user and were previously kept in an unbounded
#: dict for the life of the engine, so a long conversation grew memory without
#: limit AND made every later translation slower (see _build_replacer).
MAX_SESSION_CORRECTIONS = 500


def _build_replacer(
    mapping: tuple[tuple[str, str], ...],
) -> tuple[re.Pattern[str], dict[str, str]] | None:
    """Compile a substitution table into one single-pass regex.

    CORRECTNESS: the previous code applied ``str.replace`` once per entry, in
    insertion order, each pass over the *output* of the last. That chains:
    with ``cat -> dog`` and ``dog -> bird`` recorded, "the cat sat" came out as
    "the bird sat", because the second rule re-matched the first rule's own
    output. One alternation pass replaces each span of the input exactly once,
    which is what a substitution table means.

    PERFORMANCE: it also collapses N passes over the text into one. The old
    loop was O(len(mapping) x len(text)) on a path with a 300 ms latency
    budget, so translation slowed down in proportion to how much the user had
    corrected it - the feature degraded itself the more it was used.

    Alternatives are sorted longest-first so that a longer key always wins over
    a shorter one it contains ("blood pressure" over "blood"). No word
    boundaries are applied, preserving ``str.replace`` semantics exactly.
    """
    if not mapping:
        return None
    table = dict(mapping)
    keys = sorted((k for k in table if k), key=len, reverse=True)
    if not keys:
        return None
    pattern = re.compile("|".join(re.escape(key) for key in keys))
    return pattern, table


@lru_cache(maxsize=len(DOMAIN_TERMS) + 8)
def _domain_replacer(domain: str) -> tuple[re.Pattern[str], dict[str, str]] | None:
    """Compiled replacer for a domain's terminology, built at most once."""
    terms = DOMAIN_TERMS.get(domain)
    if not terms:
        return None
    return _build_replacer(tuple(terms.items()))


def _apply(replacer: tuple[re.Pattern[str], dict[str, str]] | None, text: str) -> str:
    """Apply a compiled replacer to text."""
    if replacer is None:
        return text
    pattern, table = replacer
    return pattern.sub(lambda m: table[m.group(0)], text)


@dataclass
class TranslationResult:
    """Result of a translation operation."""

    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence: float
    alternatives: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    subtitles: list[SubtitleEntry] = field(default_factory=list)


class TranslationEngine:
    """SeamlessM4T v2-based translation with stub fallback."""

    def __init__(self) -> None:
        self._subtitle_gen = SubtitleGenerator()
        # Bounded LRU: the oldest correction is dropped once the cap is hit,
        # and re-correcting a phrase refreshes its recency.
        self._session_corrections: OrderedDict[str, str] = OrderedDict()
        self._domain: str | None = None
        # Lazily compiled from _session_corrections; invalidated by correct().
        self._correction_replacer: tuple[re.Pattern[str], dict[str, str]] | None = None
        self._correction_replacer_valid = True

    def set_domain(self, domain: str) -> None:
        """Set domain for terminology adaptation."""
        self._domain = domain

    def detect_language(self, text: str) -> tuple[str, float]:
        """Detect language with confidence. Prompts user if < 85%."""
        # Stub: simple heuristic
        if any(c in text for c in "áéíóúñ"):
            return "es", 0.90
        if any(c in text for c in "àâçèêëîïôùûü"):
            return "fr", 0.88
        return "en", 0.95

    def translate(
        self,
        text: str,
        target_language: str,
        source_language: str | None = None,
    ) -> TranslationResult:
        """Translate text with ≤300ms latency target."""
        start = time.perf_counter()

        # DEFECT FIX: empty or whitespace-only input used to be fed straight
        # through the translator, which produced a non-empty string (the stub's
        # "[es] " language tag, and whatever a real backend emits for empty
        # input) and then a spurious subtitle entry containing that tag alone -
        # a caption displayed over silence. Translating nothing yields nothing,
        # and short-circuiting also keeps empty turns off the latency budget.
        if not text or not text.strip():
            return TranslationResult(
                source_text=text,
                translated_text="",
                source_language=source_language or "und",
                target_language=target_language,
                confidence=0.0,
                latency_ms=(time.perf_counter() - start) * 1000,
            )

        # Apply session corrections in a single pass. `text` is deliberately
        # not rebound: TranslationResult.source_text must carry what the user
        # actually said, and the old code overwrote it with the corrected form
        # before returning, losing the original input for good.
        corrected = _apply(self._correction_table(), text)

        if source_language is None:
            source_language, lang_conf = self.detect_language(corrected)
            if lang_conf < LANGUAGE_DETECTION_THRESHOLD:
                logger.warning("Low language detection confidence: %.2f", lang_conf)

        # Apply domain terminology
        translated = self._do_translate(corrected, source_language, target_language)
        confidence = 0.85

        alternatives: list[str] = []
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            alternatives = [f"[alt1: {translated}]", f"[alt2: {translated}]"]

        latency_ms = (time.perf_counter() - start) * 1000
        subtitles = self._subtitle_gen.generate(translated, 0.0, target_language)

        return TranslationResult(
            source_text=text,
            translated_text=translated,
            source_language=source_language,
            target_language=target_language,
            confidence=confidence,
            alternatives=alternatives,
            latency_ms=latency_ms,
            subtitles=subtitles,
        )

    def translate_bidirectional(
        self,
        speaker_a_text: str,
        speaker_b_text: str,
        lang_a: str = "en",
        lang_b: str = "es",
    ) -> tuple[TranslationResult, TranslationResult]:
        """Bidirectional translation for two-speaker mode."""
        result_a = self.translate(speaker_a_text, lang_b, lang_a)
        result_b = self.translate(speaker_b_text, lang_a, lang_b)
        return result_a, result_b

    def _correction_table(self) -> tuple[re.Pattern[str], dict[str, str]] | None:
        """Return the compiled correction replacer, rebuilding only if stale."""
        if not self._correction_replacer_valid:
            self._correction_replacer = _build_replacer(
                tuple(self._session_corrections.items())
            )
            self._correction_replacer_valid = True
        return self._correction_replacer

    def correct(self, original: str, correction: str) -> None:
        """Store a session correction applied to subsequent translations.

        Corrections form a substitution table over the *input*: each one is
        applied to the text the user supplied, never to another correction's
        output. Recording the same phrase again replaces the earlier entry.

        An empty ``original`` is ignored - it would match at every position.
        """
        if not original:
            logger.warning("Ignoring session correction with an empty source phrase")
            return

        # move_to_end keeps this an LRU rather than a plain FIFO, so a phrase
        # the user keeps correcting is not evicted by a burst of one-offs.
        if original in self._session_corrections:
            self._session_corrections.move_to_end(original)
        self._session_corrections[original] = correction
        while len(self._session_corrections) > MAX_SESSION_CORRECTIONS:
            evicted, _ = self._session_corrections.popitem(last=False)
            logger.debug("Evicted oldest session correction: %r", evicted)

        self._correction_replacer_valid = False

    def clear_corrections(self) -> None:
        """Drop every session correction (e.g. when a conversation ends)."""
        self._session_corrections.clear()
        self._correction_replacer = None
        self._correction_replacer_valid = True

    def generate_subtitles(
        self,
        translated_text: str,
        audio_start_ms: float,
        language: str,
    ) -> list[SubtitleEntry]:
        """Generate subtitles synchronized within 100ms."""
        return self._subtitle_gen.generate(translated_text, audio_start_ms, language)

    def _do_translate(self, text: str, source: str, target: str) -> str:
        """Stub translation (in production uses SeamlessM4T v2 or NLLB-200)."""
        if _SEAMLESS_AVAILABLE:
            pass  # Would use seamless_communication here
        # Apply domain terms in one pass, from a replacer compiled once per
        # domain rather than looped per term on every call. Same chaining fix
        # as session corrections: a replacement must not be re-matched by a
        # later term in the same table.
        result = _apply(_domain_replacer(self._domain), text) if self._domain else text
        return f"[{target}] {result}"
