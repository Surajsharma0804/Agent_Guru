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

_UNCERTAINTY_PATTERNS = [
    re.compile(r"\b(I think|I believe|I'm not sure|I'm uncertain|probably|possibly|maybe|perhaps|might be|could be|I guess|I assume)\b", re.IGNORECASE),
    re.compile(r"\b(as far as I know|to the best of my knowledge|I recall|I remember)\b", re.IGNORECASE),
]

# Fabrication signal patterns
_FABRICATION_PATTERNS = [
    re.compile(r"\b(according to .{0,30}study|research shows|studies show|experts say|scientists found)\b", re.IGNORECASE),
    re.compile(r"\b(in \d{4}|on (January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2})\b", re.IGNORECASE),
    re.compile(r"\b\d+(\.\d+)?%\b"),  # Specific percentages
    re.compile(r"\$\d[\d,]*(\.\d+)?\b"),  # Specific dollar amounts
]

# Contradiction signal patterns
_CONTRADICTION_PATTERNS = [
    re.compile(r"\b(however|but|although|despite|on the other hand|in contrast|nevertheless|yet|while)\b", re.IGNORECASE),
]


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
            details="; ".join(details_parts) if details_parts else "No hallucination signals detected",
            techniques_used=techniques_used,
        )

    def _check_factual_consistency(
        self, text: str, expected_facts: list[str]
    ) -> dict[str, Any]:
        """Check if text contradicts known facts."""
        if not expected_facts:
            return {"flagged": False, "score": 0.9, "detail": ""}

        text_lower = text.lower()
        contradictions = 0
        for fact in expected_facts:
            fact_lower = fact.lower()
            # Simple negation check: if fact appears negated in text
            negation_patterns = [
                f"not {fact_lower}",
                f"never {fact_lower}",
                f"no {fact_lower}",
                f"isn't {fact_lower}",
                f"wasn't {fact_lower}",
            ]
            for neg in negation_patterns:
                if neg in text_lower:
                    contradictions += 1
                    break

        if contradictions > 0:
            score = max(0.1, 0.9 - contradictions * 0.3)
            return {
                "flagged": True,
                "score": score,
                "detail": f"Factual contradiction detected ({contradictions} facts contradicted)",
            }
        return {"flagged": False, "score": 0.9, "detail": ""}

    def _check_cross_reference(
        self, text: str, context: dict[str, Any]
    ) -> dict[str, Any]:
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
