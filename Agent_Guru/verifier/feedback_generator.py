"""Self-Correction Feedback Generator for the Verifier System.

Generates actionable feedback when verification fails, enabling
agents to self-correct their outputs.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

from __future__ import annotations

from Agent_Guru.verifier.models import (
    HallucinationDetectionResult,
    HallucinationType,
    LoopDetectionResult,
    OutputValidationResult,
    SelfCorrectionFeedback,
    ToolOutputCheckResult,
    ValidationFailureType,
)


class SelfCorrectionFeedbackGenerator:
    """Generates actionable self-correction feedback from verification failures.

    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
    """

    def generate(
        self,
        hallucination: HallucinationDetectionResult | None = None,
        validation: OutputValidationResult | None = None,
        tool_check: ToolOutputCheckResult | None = None,
        loop_detection: LoopDetectionResult | None = None,
    ) -> SelfCorrectionFeedback:
        """Generate feedback from all verification results.

        Returns:
            SelfCorrectionFeedback with issues and actionable suggestions

        """
        issues: list[str] = []
        suggestions: list[str] = []
        severity = "low"

        # Hallucination feedback
        if hallucination and hallucination.detected:
            h_issues, h_suggestions, h_severity = self._hallucination_feedback(hallucination)
            issues.extend(h_issues)
            suggestions.extend(h_suggestions)
            severity = self._max_severity(severity, h_severity)

        # Validation feedback
        if validation and not validation.valid:
            v_issues, v_suggestions, v_severity = self._validation_feedback(validation)
            issues.extend(v_issues)
            suggestions.extend(v_suggestions)
            severity = self._max_severity(severity, v_severity)

        # Tool check feedback
        if tool_check and not tool_check.safe:
            t_issues, t_suggestions, t_severity = self._tool_feedback(tool_check)
            issues.extend(t_issues)
            suggestions.extend(t_suggestions)
            severity = self._max_severity(severity, t_severity)

        # Loop detection feedback
        if loop_detection and loop_detection.loop_detected:
            l_issues, l_suggestions, l_severity = self._loop_feedback(loop_detection)
            issues.extend(l_issues)
            suggestions.extend(l_suggestions)
            severity = self._max_severity(severity, l_severity)

        has_feedback = len(issues) > 0

        return SelfCorrectionFeedback(
            has_feedback=has_feedback,
            issues=issues,
            suggestions=suggestions,
            severity=severity,
        )

    def _hallucination_feedback(
        self,
        result: HallucinationDetectionResult,
    ) -> tuple[list[str], list[str], str]:
        issues: list[str] = []
        suggestions: list[str] = []

        for h_type in result.hallucination_types:
            if h_type == HallucinationType.FACTUAL_INCONSISTENCY:
                issues.append("Factual inconsistency detected in response")
                suggestions.append(
                    "Verify all factual claims against reliable sources before responding",
                )
            elif h_type == HallucinationType.CROSS_REFERENCE_FAILURE:
                issues.append("Response contradicts provided context")
                suggestions.append(
                    "Re-read the provided context and ensure your response is consistent with it",
                )
            elif h_type == HallucinationType.LOW_CONFIDENCE_SIGNAL:
                issues.append("Response contains excessive uncertainty language")
                suggestions.append(
                    "If uncertain, explicitly state your uncertainty rather than guessing",
                )
            elif h_type == HallucinationType.PATTERN_MATCH:
                issues.append("Response contains patterns associated with fabricated information")
                suggestions.append(
                    "Avoid citing specific statistics, dates, or studies unless you are certain they are accurate",
                )

        severity = "high" if len(result.hallucination_types) >= 2 else "medium"

        return issues, suggestions, severity

    def _validation_feedback(
        self,
        result: OutputValidationResult,
    ) -> tuple[list[str], list[str], str]:
        issues: list[str] = []
        suggestions: list[str] = []

        for violation in result.violations[:5]:  # Limit to 5 violations
            if violation.failure_type == ValidationFailureType.MISSING_FIELD:
                issues.append(f"Missing required field: '{violation.field}'")
                suggestions.append(f"Add the required field '{violation.field}' to your output")
            elif violation.failure_type == ValidationFailureType.TYPE_MISMATCH:
                issues.append(
                    f"Type mismatch at '{violation.field}': expected {violation.expected}, got {violation.actual}",
                )
                suggestions.append(f"Change '{violation.field}' to type {violation.expected}")
            elif violation.failure_type == ValidationFailureType.FORMAT_ERROR:
                issues.append(f"Format error: {violation.message}")
                suggestions.append("Ensure your output is valid " + result.format_detected)
            elif violation.failure_type == ValidationFailureType.CONSTRAINT_VIOLATION:
                issues.append(f"Constraint violation at '{violation.field}': {violation.message}")
                suggestions.append(f"Adjust '{violation.field}' to satisfy: {violation.expected}")

        severity = "high" if len(result.violations) > 3 else "medium"

        return issues, suggestions, severity

    def _tool_feedback(self, result: ToolOutputCheckResult) -> tuple[list[str], list[str], str]:
        issues: list[str] = []
        suggestions: list[str] = []

        if result.error_indicators:
            issues.append(f"Tool output contains error indicators: {result.error_indicators[:3]}")
            suggestions.append("Check tool execution logs and retry with corrected parameters")

        if not result.schema_valid:
            issues.append("Tool output does not match expected schema")
            suggestions.append("Verify the tool is returning the expected output format")

        if not result.semantically_consistent:
            issues.append("Tool output is semantically inconsistent with input parameters")
            suggestions.append(
                "Review input parameters and ensure they are compatible with the tool's requirements",
            )

        severity = "high" if result.error_indicators else "medium"
        return issues, suggestions, severity

    def _loop_feedback(self, result: LoopDetectionResult) -> tuple[list[str], list[str], str]:
        issues = [f"Infinite loop detected: state repeated {result.repetition_count} times"]
        suggestions = [
            "Break the loop by introducing a different approach or termination condition",
            "Consider whether the goal has already been achieved",
            "Try a completely different strategy to avoid repeating the same state",
        ]
        return issues, suggestions, "critical"

    @staticmethod
    def _max_severity(a: str, b: str) -> str:
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return a if order.get(a, 0) >= order.get(b, 0) else b
