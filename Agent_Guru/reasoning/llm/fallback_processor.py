"""
Fallback processor for rule-based task generation when LLM is unavailable.

This module provides a fallback mechanism that uses the Fast Intent Router
for pattern matching and creates simple Task objects without requiring LLM
inference. This ensures the system continues functioning when the LLM is
unavailable due to timeout, error, or service unavailability.

Requirements: 16.5, 16.7
"""

import time
from datetime import datetime, timezone
from typing import Optional

from Agent_Guru.reasoning.config.metrics import MetricsCollector
from Agent_Guru.reasoning.intent.fast_router import FastIntentRouter, PatternMatch
from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskStep, TaskType


class FallbackMetrics:
    """Metrics for fallback processor usage."""

    def __init__(self) -> None:
        """Initialize fallback metrics."""
        self.total_fallbacks: int = 0
        self.successful_fallbacks: int = 0
        self.failed_fallbacks: int = 0
        self.total_latency_ms: float = 0.0

    def record_fallback(self, success: bool, latency_ms: float) -> None:
        """Record a fallback attempt."""
        self.total_fallbacks += 1
        if success:
            self.successful_fallbacks += 1
        else:
            self.failed_fallbacks += 1
        self.total_latency_ms += latency_ms

    def get_fallback_rate(self) -> float:
        """Calculate fallback success rate."""
        if self.total_fallbacks == 0:
            return 0.0
        return (self.successful_fallbacks / self.total_fallbacks) * 100.0

    def get_average_latency(self) -> float:
        """Calculate average fallback latency."""
        if self.total_fallbacks == 0:
            return 0.0
        return self.total_latency_ms / self.total_fallbacks

    def reset(self) -> None:
        """Reset all metrics."""
        self.total_fallbacks = 0
        self.successful_fallbacks = 0
        self.failed_fallbacks = 0
        self.total_latency_ms = 0.0


class FallbackProcessor:
    """
    Fallback processor for rule-based task generation.

    This processor uses the Fast Intent Router to detect intents via pattern
    matching and creates simple Task objects without LLM inference. It serves
    as a fallback when the LLM is unavailable, ensuring graceful degradation.

    Time Complexity: O(n) where n is the number of words in input (trie traversal)
    Space Complexity: O(1) - reuses existing router and creates single Task object

    Attributes:
        router: Fast Intent Router for pattern matching
        metrics: Fallback usage metrics
        metrics_collector: Global metrics collector for observability
    """

    def __init__(
        self,
        router: Optional[FastIntentRouter] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        """
        Initialize fallback processor.

        Args:
            router: Fast Intent Router instance (creates new if None)
            metrics_collector: Global metrics collector for observability
        """
        self.router = router or FastIntentRouter()
        self.metrics = FallbackMetrics()
        self.metrics_collector = metrics_collector

    def detect_llm_unavailable(self, error: Exception) -> bool:
        """
        Detect if error indicates LLM is unavailable.

        Checks for common error patterns that indicate LLM service issues:
        - Timeout errors
        - Connection errors
        - Service unavailable errors
        - Rate limit errors

        Args:
            error: Exception from LLM call

        Returns:
            True if error indicates LLM unavailability, False otherwise

        Time Complexity: O(1) - simple string matching
        """
        error_str = str(error).lower()

        # Common error patterns indicating LLM unavailability
        unavailable_patterns = [
            "timeout",
            "timed out",
            "connection",
            "unavailable",
            "service unavailable",
            "rate limit",
            "too many requests",
            "503",
            "504",
            "connection refused",
            "connection reset",
            "network error",
        ]

        return any(pattern in error_str for pattern in unavailable_patterns)

    def create_task_from_match(self, match: PatternMatch, original_input: str) -> Task:
        """
        Create a simple Task object from pattern match.

        Converts a Fast Intent Router pattern match into a Task object
        with a single step. This bypasses the full LLM reasoning pipeline
        and creates a minimal but executable task.

        Args:
            match: Pattern match from Fast Intent Router
            original_input: Original user input text

        Returns:
            Task object with single step

        Time Complexity: O(1) - creates fixed-size objects
        Space Complexity: O(1) - single Task and TaskStep

        Example:
            >>> match = PatternMatch(
            ...     intent_type="set_timer",
            ...     entities={"duration": "5 minutes"},
            ...     confidence=0.95,
            ...     quality=MatchQuality.HIGH
            ... )
            >>> task = processor.create_task_from_match(match, "set timer 5 minutes")
            >>> assert task.task_type == TaskType.SINGLE_STEP
            >>> assert len(task.steps) == 1
        """
        # Determine task type based on intent
        task_type = self._determine_task_type(match.intent_type)

        # Create single execution step
        step = TaskStep(
            step_id=1,
            description=f"Execute {match.intent_type} with parameters",
            tool_id=match.intent_type,  # Tool ID matches intent type
            parameters=match.entities,
            depends_on=[],
            estimated_duration=1.0,  # Default 1 second
            status=TaskStatus.PENDING,
        )

        # Create task with single step
        task = Task(
            goal=original_input,
            task_type=task_type,
            entities=match.entities,
            steps=[step],
            confidence=match.confidence,
            requires_confirmation=self._requires_confirmation(match.intent_type),
            estimated_duration=1.0,
            status=TaskStatus.PENDING,
            retry_count=0,
            created_at=datetime.now(tz=timezone.utc),
        )

        return task

    def _determine_task_type(self, intent_type: str) -> TaskType:
        """
        Determine task type from intent type.

        Args:
            intent_type: Intent type from pattern match

        Returns:
            TaskType enum value

        Time Complexity: O(1) - dictionary lookup
        """
        # Conversational intents (no action required)
        conversational_intents = {
            "greeting",
            "farewell",
            "thank_you",
            "help",
            "about",
            "capabilities",
        }

        # Memory query intents
        memory_query_intents = {
            "query_history",
            "query_memory",
            "when_did_i",
            "how_often",
            "who_did_i",
        }

        if intent_type in conversational_intents:
            return TaskType.CONVERSATIONAL
        elif intent_type in memory_query_intents:
            return TaskType.MEMORY_QUERY
        else:
            # Default to single-step for action intents
            return TaskType.SINGLE_STEP

    def _requires_confirmation(self, intent_type: str) -> bool:
        """
        Determine if intent requires user confirmation.

        Sensitive actions require confirmation before execution.

        Args:
            intent_type: Intent type from pattern match

        Returns:
            True if confirmation required, False otherwise

        Time Complexity: O(1) - set membership check
        """
        # Sensitive intents requiring confirmation
        sensitive_intents = {
            "delete_file",
            "send_message",
            "send_email",
            "make_payment",
            "transfer_money",
            "delete_account",
            "factory_reset",
            "uninstall_app",
        }

        return intent_type in sensitive_intents

    def process_with_fallback(self, input_text: str) -> Optional[Task]:
        """
        Process input using rule-based fallback.

        Attempts to match input against patterns and create a Task object.
        Records metrics for fallback usage tracking.

        Args:
            input_text: User input text

        Returns:
            Task object if match found, None otherwise

        Time Complexity: O(n) where n is number of words (trie traversal)
        Space Complexity: O(1) - single Task object

        Example:
            >>> processor = FallbackProcessor()
            >>> task = processor.process_with_fallback("set timer for 5 minutes")
            >>> assert task is not None
            >>> assert task.task_type == TaskType.SINGLE_STEP
        """
        start_time = time.perf_counter()

        try:
            # Try pattern matching with Fast Intent Router
            match = self.router.match(input_text)

            if match is None:
                # No pattern match found
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.metrics.record_fallback(success=False, latency_ms=latency_ms)

                if self.metrics_collector:
                    self.metrics_collector.increment_errors("fallback_no_match")

                return None

            # Create Task from match
            task = self.create_task_from_match(match, input_text)

            # Record successful fallback
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.record_fallback(success=True, latency_ms=latency_ms)

            if self.metrics_collector:
                self.metrics_collector.record_stage_latency("fallback_processing", latency_ms)

            return task

        except Exception as e:
            # Record failed fallback
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.record_fallback(success=False, latency_ms=latency_ms)

            if self.metrics_collector:
                self.metrics_collector.increment_errors(f"fallback_error_{type(e).__name__}")

            # Re-raise exception for upstream handling
            raise

    def get_metrics(self) -> dict[str, float]:
        """
        Get fallback usage metrics.

        Returns:
            Dictionary with fallback metrics:
            - total_fallbacks: Total fallback attempts
            - successful_fallbacks: Successful fallback attempts
            - failed_fallbacks: Failed fallback attempts
            - fallback_success_rate: Success rate percentage
            - average_latency_ms: Average fallback latency

        Time Complexity: O(1)
        """
        return {
            "total_fallbacks": float(self.metrics.total_fallbacks),
            "successful_fallbacks": float(self.metrics.successful_fallbacks),
            "failed_fallbacks": float(self.metrics.failed_fallbacks),
            "fallback_success_rate": self.metrics.get_fallback_rate(),
            "average_latency_ms": self.metrics.get_average_latency(),
        }

    def reset_metrics(self) -> None:
        """Reset fallback metrics."""
        self.metrics.reset()
