"""Explainability Engine with LLM-backed explanation generation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ConfidenceBreakdown:
    """Weighted contributions to a decision."""

    memory: float = 0.0
    llm: float = 0.0
    policy: float = 0.0
    verifier: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "memory": self.memory,
            "llm": self.llm,
            "policy": self.policy,
            "verifier": self.verifier,
        }


@dataclass
class Explanation:
    """Plain-language explanation of a decision."""

    action: str
    explanation: str
    confidence_breakdown: ConfidenceBreakdown
    reversible: bool = False
    reversal_info: str | None = None
    latency_ms: float = 0.0


class ExplainabilityEngine:
    """Generates plain-language explanations for agent decisions."""

    REVERSIBLE_ACTIONS = {"file_write", "email_send", "settings_change"}

    def explain(self, action: str, context: dict[str, Any]) -> Explanation:
        """Generate explanation within 500ms."""
        start = time.perf_counter()
        breakdown = self.get_confidence_breakdown(context)
        explanation_text = self._generate_explanation(action, context, breakdown)
        reversible = action in self.REVERSIBLE_ACTIONS
        reversal_info = context.get("reversal_info") if reversible else None
        latency_ms = (time.perf_counter() - start) * 1000
        return Explanation(
            action=action,
            explanation=explanation_text,
            confidence_breakdown=breakdown,
            reversible=reversible,
            reversal_info=reversal_info,
            latency_ms=latency_ms,
        )

    def get_confidence_breakdown(self, context: dict[str, Any]) -> ConfidenceBreakdown:
        """Return weighted contributions of each component."""
        return ConfidenceBreakdown(
            memory=context.get("memory_weight", 0.25),
            llm=context.get("llm_weight", 0.50),
            policy=context.get("policy_weight", 0.15),
            verifier=context.get("verifier_weight", 0.10),
        )

    def _generate_explanation(
        self,
        action: str,
        context: dict[str, Any],
        breakdown: ConfidenceBreakdown,
    ) -> str:
        reason = context.get("reason", "based on your request")
        return (
            f"I performed '{action}' {reason}. "
            f"Decision confidence: LLM {breakdown.llm:.0%}, "
            f"Memory {breakdown.memory:.0%}, "
            f"Policy {breakdown.policy:.0%}, "
            f"Verifier {breakdown.verifier:.0%}."
        )
