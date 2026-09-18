"""Hallucination Detector for the Verifier System.

Multi-technique approach:
1. Factual consistency checking (contradiction detection)
2. Cross-reference validation (claim vs context)
3. Confidence signal analysis (hedging language)
4. Pattern-based detection (known hallucination patterns)

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

from __future__ import annotations

import re
from typing import Any

from Agent_Guru.verifier.models import (
    HallucinationDetectionResult,
    HallucinationType,
)

# ---------------------------------------------------------------------------
# Confidence signal patterns (hedging / uncertainty language)
# ---------------------------------------------------------------------------

_UNCERTAINTY_PATTERNS = (
    re.compile(
        r"\b(I think|I believe|I'm not sure|I'm uncertain|probably|possibly|maybe|perhaps|might be|could be|I guess|I assume)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(as far as I know|to the best of my knowledge|I recall|I remember)\b",
        re.IGNORECASE,
    ),
)

# Fabrication signal patterns
_FABRICATION_PATTERNS = (
    re.compile(
        r"\b(according to .{0,30}study|research shows|studies show|experts say|scientists found)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(in \d{4}|on (January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d+(\.\d+)?%\b"),  # Specific percentages
    re.compile(r"\$\d[\d,]*(\.\d+)?\b"),  # Specific dollar amounts
)

# Negators recognised by _check_factual_consistency().
_NEGATORS = ("not", "never", "no", "isn't", "wasn't")


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _negated_mention(text_lower: str, fact_lower: str) -> bool:
    """True if *text_lower* contains "<negator> <fact>" as whole words.

    PRECISION FIX. _check_factual_consistency() formatted plain strings
    (f"no {fact}") and asked `in text_lower` -- unanchored substring matching,
    which produced concrete false positives:

      * fact "rain" against "there is no rainbow today" matched "no rain"
        inside "rainbow", reporting a correct answer as contradicting a known
        fact.
      * an EMPTY entry in expected_facts produced the pattern "not ", which
        occurs in almost any English sentence, so a single blank fact flagged
        essentially every response as a hallucination.

    That matters because this feeds the confidence score the assistant uses to
    judge its own answer.

    PERFORMANCE NOTE: the obvious fix -- one compiled regex per fact with \b
    anchors -- was measured at 14x SLOWER than the substring form (4.94 ms vs
    0.35 ms for 50 facts against a 6.6 KB response), because str.find is a
    tuned C scan while an alternation of five negators plus word boundaries
    makes the regex engine try every branch at every position. So the fast
    scan is kept and the boundary is checked in O(1) at each candidate hit
    instead: non-matching facts still cost one failed find() per negator,
    exactly as before.
    """
    fact_lower = fact_lower.strip()
    if not fact_lower:
        # Nothing meaningful to look for; matching "<negator> " alone would
        # match almost any sentence.
        return False

    check_tail = _is_word_char(fact_lower[-1])
    n = len(text_lower)

    for negator in _NEGATORS:
        needle = f"{negator} {fact_lower}"
        index = text_lower.find(needle)
        while index != -1:
            end = index + len(needle)
            before_ok = index == 0 or not _is_word_char(text_lower[index - 1])
            after_ok = (not check_tail) or end == n or not _is_word_char(text_lower[end])
            if before_ok and after_ok:
                return True
            index = text_lower.find(needle, index + 1)

    return False


# Contradiction signal patterns
_CONTRADICTION_PATTERNS = (
    re.compile(
        r"\b(however|but|although|despite|on the other hand|in contrast|nevertheless|yet|while)\b",
        re.IGNORECASE,
    ),
)


class HallucinationDetector:
    """Multi-technique hallucination detector.

    Applies four techniques in parallel and aggregates results.
    False positive rate target: <5%
    False negative rate target: <2%
    """

    def __init__(self, confidence_threshold: float = 0.6) -> None:
        self._threshold = confidence_threshold

    def detect(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        expected_facts: list[str] | None = None,
    ) -> HallucinationDetectionResult:
        """Detect hallucinations using all techniques.

        Args:
            text: The text to analyze
            context: Optional context for cross-reference validation
            expected_facts: Optional list of known facts for consistency checking

        Returns:
            HallucinationDetectionResult with aggregated findings

        """
        if not text or not text.strip():
            return HallucinationDetectionResult(
                detected=False,
                confidence=1.0,
                details="Empty text — no hallucination possible",
                techniques_used=["empty_check"],
            )

        hallucination_types: list[HallucinationType] = []
        technique_scores: list[float] = []
        techniques_used: list[str] = []
        details_parts: list[str] = []

        # Technique 1: Factual consistency
        fc_result = self._check_factual_consistency(text, expected_facts or [])
        techniques_used.append("factual_consistency")
        technique_scores.append(fc_result["score"])
        if fc_result["flagged"]:
            hallucination_types.append(HallucinationType.FACTUAL_INCONSISTENCY)
            details_parts.append(fc_result["detail"])

        # Technique 2: Cross-reference validation
        cr_result = self._check_cross_reference(text, context or {})
        techniques_used.append("cross_reference")
        technique_scores.append(cr_result["score"])
        if cr_result["flagged"]:
            hallucination_types.append(HallucinationType.CROSS_REFERENCE_FAILURE)
            details_parts.append(cr_result["detail"])

        # Technique 3: Confidence signal analysis
        cs_result = self._analyze_confidence_signals(text)
        techniques_used.append("confidence_signals")
        technique_scores.append(cs_result["score"])
        if cs_result["flagged"]:
            hallucination_types.append(HallucinationType.LOW_CONFIDENCE_SIGNAL)
            details_parts.append(cs_result["detail"])

        # Technique 4: Pattern-based detection
        pb_result = self._check_fabrication_patterns(text)
        techniques_used.append("pattern_detection")
        technique_scores.append(pb_result["score"])
        if pb_result["flagged"]:
            hallucination_types.append(HallucinationType.PATTERN_MATCH)
            details_parts.append(pb_result["detail"])

        # Aggregate: confidence = mean of technique scores
        # Lower score = more likely hallucination
        avg_score = sum(technique_scores) / len(technique_scores)
        detected = avg_score < self._threshold or len(hallucination_types) >= 2

        return HallucinationDetectionResult(
            detected=detected,
            hallucination_types=hallucination_types,
            confidence=avg_score,
            details="; ".join(details_parts)
            if details_parts
            else "No hallucination signals detected",
            techniques_used=techniques_used,
        )

    def _check_factual_consistency(self, text: str, expected_facts: list[str]) -> dict[str, Any]:
        """Check if text contradicts known facts."""
        if not expected_facts:
            return {"flagged": False, "score": 0.9, "detail": ""}

        text_lower = text.lower()
        contradictions = 0
        for fact in expected_facts:
            # Whole-word negation check -- see _negated_mention() for the
            # false positives plain substring matching produced, and for why
            # this is not a regex.
            if _negated_mention(text_lower, fact.lower()):
                contradictions += 1

        if contradictions > 0:
            score = max(0.1, 0.9 - contradictions * 0.3)
            return {
                "flagged": True,
                "score": score,
                "detail": f"Factual contradiction detected ({contradictions} facts contradicted)",
            }
        return {"flagged": False, "score": 0.9, "detail": ""}

    def _check_cross_reference(self, text: str, context: dict[str, Any]) -> dict[str, Any]:
        """Validate claims against provided context."""
        if not context:
            return {"flagged": False, "score": 0.85, "detail": ""}

        context_str = str(context).lower()

        # Check for claims in text that contradict context
        # Look for contradiction markers followed by context-relevant terms
        contradiction_count = 0
        for pattern in _CONTRADICTION_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                contradiction_count += len(matches)

        # High contradiction density relative to text length is suspicious
        words = len(text.split())
        contradiction_density = contradiction_count / max(words, 1)

        if contradiction_density > 0.1:  # >10% contradiction markers
            return {
                "flagged": True,
                "score": max(0.2, 0.8 - contradiction_density),
                "detail": f"High contradiction density ({contradiction_density:.2f})",
            }

        # Check if text makes claims not supported by context
        # Simple heuristic: specific numbers/dates not in context
        specific_claims = re.findall(r"\b\d{4}\b|\b\d+%\b|\$\d+", text)
        unsupported = [c for c in specific_claims if c not in context_str]
        if len(unsupported) > 2:
            return {
                "flagged": True,
                "score": max(0.3, 0.85 - len(unsupported) * 0.1),
                "detail": f"Unsupported specific claims: {unsupported[:3]}",
            }

        return {"flagged": False, "score": 0.85, "detail": ""}

    def _analyze_confidence_signals(self, text: str) -> dict[str, Any]:
        """Detect hedging/uncertainty language indicating low confidence."""
        uncertainty_count = 0
        for pattern in _UNCERTAINTY_PATTERNS:
            matches = pattern.findall(text)
            uncertainty_count += len(matches)

        words = len(text.split())
        uncertainty_density = uncertainty_count / max(words, 1)

        # High uncertainty density suggests the model is guessing
        if uncertainty_density > 0.05:  # >5% uncertainty markers
            score = max(0.3, 0.8 - uncertainty_density * 2)
            return {
                "flagged": True,
                "score": score,
                "detail": f"High uncertainty signal density ({uncertainty_count} markers in {words} words)",
            }

        return {"flagged": False, "score": 0.9, "detail": ""}

    def _check_fabrication_patterns(self, text: str) -> dict[str, Any]:
        """Detect patterns commonly associated with fabricated information."""
        fabrication_count = 0
        matched_patterns: list[str] = []

        for pattern in _FABRICATION_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                fabrication_count += len(matches)
                matched_patterns.extend([str(m) for m in matches[:2]])

        # Fabrication patterns alone aren't conclusive — need density
        words = len(text.split())
        fabrication_density = fabrication_count / max(words, 1)

        if fabrication_density > 0.08:  # >8% fabrication markers
            score = max(0.2, 0.85 - fabrication_density * 2)
            return {
                "flagged": True,
                "score": score,
                "detail": f"High fabrication pattern density: {matched_patterns[:3]}",
            }

        return {"flagged": False, "score": 0.88, "detail": ""}
