"""Integration hooks for LLM Runtime, Agent Orchestration, and Memory System.

These classes provide the concrete integration points that other Agent_Guru
components use to interact with the Verifier System.

Requirements: 8.1-8.5, 9.1-9.5, 10.1-10.5, 11.1-11.5
"""

from __future__ import annotations

import logging
from datetime import UTC
from typing import Any

from Agent_Guru.verifier.models import VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)


class LLMRuntimeIntegration:
    """Integration hooks for LLM Runtime.

    Intercepts LLM responses before they are forwarded to agents.
    Blocks on verification failure and provides feedback for retry.

    Requirements: 8.1, 8.2, 8.3, 8.5
    """

    def __init__(self, verifier: Any) -> None:
        self._verifier = verifier

    async def intercept_response(
        self,
        response: str,
        context: dict[str, Any] | None = None,
        expected_format: str | None = None,
        session_id: str | None = None,
    ) -> tuple[bool, VerificationResult]:
        """Intercept and verify an LLM response.

        Returns:
            (should_forward, result) - if should_forward=False, use result.feedback

        """
        result = await self._verifier.verify_llm_response(
            response,
            context=context,
            expected_format=expected_format,
            session_id=session_id,
        )
        should_forward = result.status != VerificationStatus.FAILED
        if not should_forward:
            logger.warning(
                "LLM response blocked by verifier: %s (confidence=%.2f)",
                result.status.value,
                result.confidence,
            )
        return should_forward, result


class AgentOrchestrationIntegration:
    """Integration hooks for Agent Orchestration.

    Validates task outputs before marking tasks complete.
    Provides retry feedback and escalates on exhaustion.

    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
    """

    def __init__(self, verifier: Any, max_retries: int = 3) -> None:
        self._verifier = verifier
        self._max_retries = max_retries
        # task_id -> retry count
        self._retry_counts: dict[str, int] = {}

    async def validate_task_output(
        self,
        task_id: str,
        output: Any,
        expected_schema: dict[str, Any] | None = None,
    ) -> tuple[bool, VerificationResult, bool]:
        """Validate task output before completion.

        Returns:
            (is_valid, result, should_escalate)
            - is_valid: True if output passes verification
            - result: Full verification result with feedback
            - should_escalate: True if retries exhausted

        """
        result = await self._verifier.verify_task_output(task_id, output, expected_schema)
        is_valid = result.status == VerificationStatus.PASSED

        should_escalate = False
        if not is_valid:
            self._retry_counts[task_id] = self._retry_counts.get(task_id, 0) + 1
            if self._retry_counts[task_id] >= self._max_retries:
                should_escalate = True
                logger.error(
                    "Task %s failed verification %d times - escalating",
                    task_id,
                    self._retry_counts[task_id],
                )

        return is_valid, result, should_escalate

    def get_retry_count(self, task_id: str) -> int:
        return self._retry_counts.get(task_id, 0)

    def reset_retries(self, task_id: str) -> None:
        self._retry_counts.pop(task_id, None)


class MemorySystemIntegration:
    """Integration hooks for Memory System.

    Prevents hallucinated information from being stored.
    Attaches confidence metadata to stored information.
    Flags old information for re-verification.

    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
    """

    def __init__(self, verifier: Any, reverification_age_days: float = 30.0) -> None:
        self._verifier = verifier
        self._reverification_age_days = reverification_age_days
        # content_id -> (timestamp, confidence)
        self._stored_metadata: dict[str, dict[str, Any]] = {}

    async def verify_before_storage(
        self,
        content: str,
        content_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[bool, VerificationResult]:
        """Verify content before storing in Memory System.

        Returns:
            (should_store, result)
            - should_store: False if hallucination detected

        """
        result = await self._verifier.verify_before_storage(content, metadata)
        should_store = result.status != VerificationStatus.FAILED

        if should_store:
            from datetime import datetime

            self._stored_metadata[content_id] = {
                "stored_at": datetime.now(tz=UTC).isoformat(),
                "confidence": result.confidence,
                "result_id": str(result.result_id),
            }
        else:
            logger.warning(
                "Storage blocked for content_id=%s (confidence=%.2f)",
                content_id,
                result.confidence,
            )

        return should_store, result

    def get_confidence_metadata(self, content_id: str) -> dict[str, Any] | None:
        """Get confidence metadata for stored content (Requirement 10.4)."""
        return self._stored_metadata.get(content_id)

    def needs_reverification(self, content_id: str) -> bool:
        """Check if stored content is old enough to need re-verification (Req 10.5)."""
        meta = self._stored_metadata.get(content_id)
        if not meta:
            return False
        from datetime import datetime

        stored_at = datetime.fromisoformat(meta["stored_at"])
        age_days = (datetime.now(tz=UTC) - stored_at).total_seconds() / 86400
        return age_days >= self._reverification_age_days


class SelfImprovementIntegration:
    """Integration with Self-Improvement Engine.

    Reports verification failures for learning and improvement.

    Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
    """

    def __init__(self, verifier: Any) -> None:
        self._verifier = verifier
        self._reported_patterns: list[dict[str, Any]] = []

    def get_failure_report(self) -> dict[str, Any]:
        """Get aggregated failure report for Self-Improvement Engine."""
        reports = self._verifier.get_failure_reports()
        if not reports:
            return {"total_failures": 0, "patterns": [], "success_rate": 1.0}

        # Aggregate by context type
        by_type: dict[str, int] = {}
        for r in reports:
            ct = r.get("context_type", "unknown")
            by_type[ct] = by_type.get(ct, 0) + 1

        metrics = self._verifier.get_accuracy_metrics()
        total = metrics.get("total", 0)
        failures = len(reports)

        return {
            "total_failures": failures,
            "failure_by_context": by_type,
            "success_rate": 1.0 - (failures / total) if total > 0 else 1.0,
            "patterns": self._extract_patterns(reports),
            "p95_latency_ms": metrics.get("p95_latency_ms", 0.0),
        }

    def _extract_patterns(self, reports: list[dict[str, Any]]) -> list[str]:
        """Extract common failure patterns from reports."""
        all_issues: list[str] = []
        for r in reports:
            all_issues.extend(r.get("issues", []))

        # Count issue frequency
        counts: dict[str, int] = {}
        for issue in all_issues:
            # Normalize to first 50 chars as pattern key
            key = issue[:50]
            counts[key] = counts.get(key, 0) + 1

        # Return top patterns
        sorted_patterns = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [p for p, _ in sorted_patterns[:5]]

    def get_historical_data(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get historical verification data for analysis (Requirement 11.4, 11.5)."""
        return self._verifier.get_failure_reports()[-limit:]
