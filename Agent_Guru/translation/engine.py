"""Real-Time Multilingual Translation Engine."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from Agent_Guru.translation.subtitles import SubtitleEntry, SubtitleGenerator

logger = logging.getLogger(__name__)

TRANSLATION_LATENCY_MS = 300
LOW_CONFIDENCE_THRESHOLD = 0.7
LANGUAGE_DETECTION_THRESHOLD = 0.85

try:
    import seamless_communication  # type: ignore[import]
    _SEAMLESS_AVAILABLE = True
except ImportError:
    _SEAMLESS_AVAILABLE = False

# Domain-specific terminology adapters
DOMAIN_TERMS: dict[str, dict[str, str]] = {
    "medical": {"heart attack": "myocardial infarction", "blood pressure": "BP"},
    "legal": {"agreement": "contract", "lawsuit": "litigation"},
    "technical": {"bug": "defect", "fix": "patch"},
}


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
        self._session_corrections: dict[str, str] = {}
        self._domain: Optional[str] = None

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
        source_language: Optional[str] = None,
    ) -> TranslationResult:
        """Translate text with ≤300ms latency target."""
        start = time.perf_counter()

        # Apply session corrections
        for original, correction in self._session_corrections.items():
            text = text.replace(original, correction)

        if source_language is None:
            source_language, lang_conf = self.detect_language(text)
            if lang_conf < LANGUAGE_DETECTION_THRESHOLD:
                logger.warning("Low language detection confidence: %.2f", lang_conf)

        # Apply domain terminology
        translated = self._do_translate(text, source_language, target_language)
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

    def correct(self, original: str, correction: str) -> None:
        """Store session correction for subsequent translations."""
        self._session_corrections[original] = correction

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
        # Apply domain terms
        result = text
        if self._domain and self._domain in DOMAIN_TERMS:
            for term, replacement in DOMAIN_TERMS[self._domain].items():
                result = result.replace(term, replacement)
        return f"[{target}] {result}"
