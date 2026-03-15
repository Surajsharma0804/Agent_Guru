"""Confidence Scorer for the Verifier System.

Aggregates component scores into a single confidence score with
threshold-based recommendations.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

from __future__ import annotations

from Agent_Guru.verifier.models import (
    ConfidenceScore,
    HallucinationDetectionResult,
    LoopDetectionResult,
    OutputValidationResult,
    ToolOutputCheckResult,
)

# Component weights for aggregation
_WEIGHTS = {
    "hallucination": 0.40,
    "validation": 0.25,
    "tool_check": 0.20,
    "loop_detection": 0.15,
}


class ConfidenceScorer:
    """Aggregates verification component scores into a confidence score.

    Score range: [0.0, 1.0]
    - 1.0 = fully confident, no issues
    - 0.0 = completely unreliable

    Recommendations:
    - >= 0.8: proceed
    - 0.6 - 0.8: proceed_with_caution
    - 0.4 - 0.6: request_review
    - < 0.4: reject
    """

    def __init__(self, min_threshold: float = 0.7) -> None:
        self._min_threshold = min_threshold

    def compute(
        self,
        hallucination: HallucinationDetectionResult | None = None,
        validation: OutputValidationResult | None = None,
        tool_check: ToolOutputCheckResult | None = None,
        loop_detection: LoopDetectionResult | None = None,
    ) -> ConfidenceScore:
        """Compute aggregated confidence score.

        Args:
            hallucination: Hallucination detection result
            validation: Output validation result
            tool_check: Tool output check result
            loop_detection: Loop detection result

        Returns:
            ConfidenceScore with aggregated score and recommendation
        """
        component_scores: dict[str, float] = {}
        total_weight = 0.0
        weighted_sum = 0.0

        if hallucination is not None:
            score = hallucination.confidence if not hallucination.detected else hallucination.confidence * 0.3
            component_scores["hallucination"] = score
            w = _WEIGHTS["hallucination"]
            weighted_sum += score * w
            total_weight += w

        if validation is not None:
            score = 1.0 if validation.valid else max(0.1, 1.0 - len(validation.violations) * 0.2)
            component_scores["validation"] = score
            w = _WEIGHTS["validation"]
            weighted_sum += score * w
            total_weight += w

        if tool_check is not None:
            score = 1.0 if tool_check.safe else 0.2
            if not tool_check.schema_valid:
                score = min(score, 0.4)
            if not tool_check.semantically_consistent:
                score = min(score, 0.3)
            component_scores["tool_check"] = score
            w = _WEIGHTS["tool_check"]
            weighted_sum += score * w
            total_weight += w

        if loop_detection is not None:
            if loop_detection.loop_detected:
                score = max(0.0, 0.5 - loop_detection.repetition_count * 0.1)
            else:
                score = 1.0
            component_scores["loop_detection"] = score
            w = _WEIGHTS["loop_detection"]
            weighted_sum += score * w
            total_weight += w

        # Compute final score
        if total_weight > 0:
            final_score = weighted_sum / total_weight
        else:
            final_score = 1.0  # No components = assume OK

        final_score = max(0.0, min(1.0, final_score))

        # Recommendation
        recommendation = self._get_recommendation(final_score)

        return ConfidenceScore(
            score=final_score,
            component_scores=component_scores,
            recommendation=recommendation,
        )

    def _get_recommendation(self, score: float) -> str:
        if score >= 0.8:
            return "proceed"
        elif score >= 0.6:
            return "proceed_with_caution"
        elif score >= 0.4:
            return "request_review"
        else:
            return "reject"

    def needs_additional_verification(self, score: ConfidenceScore) -> bool:
        """Return True if score is below threshold and needs more verification."""
        return score.score < self._min_threshold
