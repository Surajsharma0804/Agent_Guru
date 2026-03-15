"""Verification Strategy Selector for the Verifier System.

Selects appropriate verification strategies based on task type and content.

Requirements: 6.1, 6.2, 6.3, 6.4
"""

from __future__ import annotations

import re
from typing import Any

# Task type patterns
_FACTUAL_PATTERNS = [
    re.compile(r"\b(what is|who is|when did|where is|how many|define|explain)\b", re.IGNORECASE),
    re.compile(r"\b(fact|statistic|data|number|date|year|history)\b", re.IGNORECASE),
]

_CODE_PATTERNS = [
    re.compile(r"\b(code|function|class|implement|program|script|algorithm)\b", re.IGNORECASE),
    re.compile(r"```|def |class |import |from .* import", re.IGNORECASE),
]

_TOOL_PATTERNS = [
    re.compile(r"\b(tool|api|call|execute|run|invoke|fetch|search)\b", re.IGNORECASE),
]

_CREATIVE_PATTERNS = [
    re.compile(r"\b(write|create|generate|compose|story|poem|essay)\b", re.IGNORECASE),
]


class VerificationStrategy:
    """A selected verification strategy."""

    def __init__(
        self,
        use_hallucination_detection: bool = True,
        use_output_validation: bool = True,
        use_tool_checking: bool = False,
        use_loop_detection: bool = True,
        use_confidence_scoring: bool = True,
        reason: str = "",
    ) -> None:
        self.use_hallucination_detection = use_hallucination_detection
        self.use_output_validation = use_output_validation
        self.use_tool_checking = use_tool_checking
        self.use_loop_detection = use_loop_detection
        self.use_confidence_scoring = use_confidence_scoring
        self.reason = reason


class VerificationStrategySelector:
    """Selects verification strategies based on task type and content.

    Requirements: 6.1, 6.2, 6.3, 6.4
    """

    def select_for_llm_response(
        self,
        response: str,
        context: dict[str, Any] | None = None,
        task_type: str | None = None,
    ) -> VerificationStrategy:
        """Select strategy for verifying an LLM response.

        Args:
            response: The LLM response text
            context: Optional context dict
            task_type: Optional explicit task type hint

        Returns:
            VerificationStrategy
        """
        detected_type = task_type or self._detect_task_type(response)

        if detected_type == "factual":
            return VerificationStrategy(
                use_hallucination_detection=True,
                use_output_validation=True,
                use_tool_checking=False,
                use_loop_detection=False,
                use_confidence_scoring=True,
                reason="Factual response requires hallucination detection",
            )
        elif detected_type == "code":
            return VerificationStrategy(
                use_hallucination_detection=False,
                use_output_validation=True,
                use_tool_checking=False,
                use_loop_detection=True,
                use_confidence_scoring=True,
                reason="Code response requires output validation",
            )
        elif detected_type == "tool_result":
            return VerificationStrategy(
                use_hallucination_detection=True,
                use_output_validation=True,
                use_tool_checking=True,
                use_loop_detection=True,
                use_confidence_scoring=True,
                reason="Tool result requires full verification",
            )
        elif detected_type == "creative":
            return VerificationStrategy(
                use_hallucination_detection=False,
                use_output_validation=False,
                use_tool_checking=False,
                use_loop_detection=False,
                use_confidence_scoring=True,
                reason="Creative content — minimal verification",
            )
        else:
            # Default: full verification
            return VerificationStrategy(
                use_hallucination_detection=True,
                use_output_validation=True,
                use_tool_checking=False,
                use_loop_detection=True,
                use_confidence_scoring=True,
                reason="Default full verification strategy",
            )

    def select_for_task_output(
        self,
        output: Any,
        expected_schema: dict[str, Any] | None = None,
    ) -> VerificationStrategy:
        """Select strategy for verifying a task output."""
        has_schema = expected_schema is not None
        return VerificationStrategy(
            use_hallucination_detection=isinstance(output, str),
            use_output_validation=has_schema or isinstance(output, (dict, list, str)),
            use_tool_checking=False,
            use_loop_detection=False,
            use_confidence_scoring=True,
            reason="Task output verification",
        )

    def _detect_task_type(self, text: str) -> str:
        """Detect task type from text content."""
        if any(p.search(text) for p in _CODE_PATTERNS):
            return "code"
        if any(p.search(text) for p in _TOOL_PATTERNS):
            return "tool_result"
        if any(p.search(text) for p in _FACTUAL_PATTERNS):
            return "factual"
        if any(p.search(text) for p in _CREATIVE_PATTERNS):
            return "creative"
        return "general"
