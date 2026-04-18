"""
Enhanced confidence scoring for LLM-generated Task objects.

This module implements sophisticated confidence scoring that goes beyond
basic completeness checks. It tracks historical accuracy per task type
and adjusts confidence scores based on past performance.

Performance Target: <20ms for confidence calculation
Accuracy Target: Confidence scores correlate >0.8 with actual success rate

Requirements: 17.5
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from Agent_Guru.reasoning.config.logging import get_logger
from Agent_Guru.reasoning.config.metrics import CONFIDENCE_SCORE_HISTOGRAM
from Agent_Guru.reasoning.models.task import Task, TaskType

logger = get_logger(__name__)


@dataclass
class HistoricalAccuracy:
    """
    Tracks historical accuracy for a specific task type.

    Attributes:
        task_type: Type of task being tracked
        total_attempts: Total number of attempts
        successful_attempts: Number of successful completions
        confidence_sum: Sum of confidence scores for calibration
        last_updated: Timestamp of last update
    """

    task_type: str
    total_attempts: int = 0
    successful_attempts: int = 0
    confidence_sum: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0-1.0)."""
        if self.total_attempts == 0:
            return 0.5  # Default to neutral
        return self.successful_attempts / self.total_attempts

    @property
    def average_confidence(self) -> float:
        """Calculate average confidence score."""
        if self.total_attempts == 0:
            return 0.5  # Default to neutral
        return self.confidence_sum / self.total_attempts

    @property
    def calibration_factor(self) -> float:
        """
        Calculate calibration factor to adjust confidence.

        If success rate > average confidence: increase confidence
        If success rate < average confidence: decrease confidence

        Returns:
            Multiplier to apply to confidence (0.5-1.5)
        """
        if self.total_attempts < 10:
            return 1.0  # Need more data for calibration

        avg_conf = self.average_confidence
        if avg_conf == 0:
            return 1.0

        # Calculate ratio, clamped to reasonable range
        ratio = self.success_rate / avg_conf
        return max(0.5, min(1.5, ratio))


class ConfidenceScorer:
    """
    Enhanced confidence scorer for LLM-generated Task objects.

    This scorer combines multiple dimensions:
    1. LLM confidence indicators (if provided by LLM)
    2. Output completeness (all required fields present, no placeholders)
    3. Consistency with context (entities match, parameters valid)
    4. Historical accuracy (track success rate per task type)

    The scorer maintains historical accuracy data and uses it to calibrate
    confidence scores based on past performance.

    Features:
    - Multi-dimensional scoring (completeness, consistency, quality, historical)
    - Historical accuracy tracking per task type
    - Confidence calibration based on success rates
    - Detailed scoring breakdown for debugging
    - Fast scoring (<20ms target)

    Performance:
    - Target latency: <20ms for confidence calculation
    - Memory: O(n) where n = number of unique task types
    """

    def __init__(self):
        """Initialize confidence scorer with empty history."""
        self.logger = get_logger(__name__)

        # Historical accuracy tracking per task type
        self._history: dict[str, HistoricalAccuracy] = defaultdict(
            lambda: HistoricalAccuracy(task_type="unknown")
        )

        # Scoring weights (sum to 1.0)
        self.weights = {
            "llm_confidence": 0.35,  # LLM's own confidence
            "completeness": 0.25,  # Field completeness
            "consistency": 0.20,  # Internal consistency
            "quality": 0.10,  # Description quality
            "historical": 0.10,  # Historical accuracy
        }

    def score(
        self, task: Task, task_dict: dict[str, Any], context: dict[str, Any] | None = None
    ) -> float:
        """
        Calculate comprehensive confidence score for Task.

        Args:
            task: Validated Task object
            task_dict: Raw task dictionary from JSON (for completeness checks)
            context: Optional context for consistency checks (entities, etc.)

        Returns:
            Confidence score (0.0-1.0)

        Example:
            >>> scorer = ConfidenceScorer()
            >>> task = Task(goal="Set timer", ...)
            >>> confidence = scorer.score(task, task_dict)
            >>> print(f"Confidence: {confidence:.2f}")
        """
        start_time = time.time()

        # Calculate individual scores
        llm_score = self._score_llm_confidence(task)
        completeness_score = self._score_completeness(task, task_dict)
        consistency_score = self._score_consistency(task, context)
        quality_score = self._score_quality(task)
        historical_score = self._score_historical(task)

        # Weighted average
        raw_confidence = (
            llm_score * self.weights["llm_confidence"]
            + completeness_score * self.weights["completeness"]
            + consistency_score * self.weights["consistency"]
            + quality_score * self.weights["quality"]
            + historical_score * self.weights["historical"]
        )

        # Apply historical calibration
        calibrated_confidence = self._apply_calibration(task, raw_confidence)

        # Clamp to [0.0, 1.0]
        final_confidence = max(0.0, min(1.0, calibrated_confidence))

        # Track metrics
        latency_ms = (time.time() - start_time) * 1000
        CONFIDENCE_SCORE_HISTOGRAM.observe(final_confidence)

        self.logger.debug(
            "Calculated confidence score",
            extra={
                "task_type": task.task_type,
                "goal": task.goal[:50],
                "llm_score": llm_score,
                "completeness_score": completeness_score,
                "consistency_score": consistency_score,
                "quality_score": quality_score,
                "historical_score": historical_score,
                "raw_confidence": raw_confidence,
                "final_confidence": final_confidence,
                "latency_ms": latency_ms,
            },
        )

        return final_confidence

    def update_history(self, task: Task, success: bool, confidence: float) -> None:
        """
        Update historical accuracy data after task execution.

        This method should be called after each task execution to track
        success rates and calibrate future confidence scores.

        Args:
            task: Task that was executed
            success: Whether task completed successfully
            confidence: Confidence score that was assigned

        Example:
            >>> scorer = ConfidenceScorer()
            >>> task = Task(goal="Set timer", task_type="single_step", ...)
            >>> scorer.update_history(task, success=True, confidence=0.85)
        """
        task_type_key = task.task_type

        history = self._history[task_type_key]
        history.task_type = task_type_key
        history.total_attempts += 1
        if success:
            history.successful_attempts += 1
        history.confidence_sum += confidence
        history.last_updated = datetime.now(tz=timezone.utc)

        self.logger.info(
            "Updated historical accuracy",
            extra={
                "task_type": task_type_key,
                "success": success,
                "confidence": confidence,
                "total_attempts": history.total_attempts,
                "success_rate": history.success_rate,
                "calibration_factor": history.calibration_factor,
            },
        )

    def get_history(self, task_type: str) -> HistoricalAccuracy | None:
        """
        Get historical accuracy data for a task type.

        Args:
            task_type: Task type to query

        Returns:
            HistoricalAccuracy object or None if no history
        """
        return self._history.get(task_type)

    def get_all_history(self) -> dict[str, HistoricalAccuracy]:
        """
        Get all historical accuracy data.

        Returns:
            Dictionary mapping task types to HistoricalAccuracy objects
        """
        return dict(self._history)

    def clear_history(self) -> None:
        """Clear all historical accuracy data."""
        self._history.clear()
        self.logger.info("Cleared historical accuracy data")

    def _score_llm_confidence(self, task: Task) -> float:
        """
        Score based on LLM-provided confidence indicators.

        Uses the confidence field from the Task object, which may be
        provided by the LLM or set to a default value.

        Args:
            task: Task object

        Returns:
            LLM confidence score (0.0-1.0)
        """
        return task.confidence

    def _score_completeness(self, task: Task, task_dict: dict[str, Any]) -> float:
        """
        Score based on output completeness.

        Checks:
        - All required fields present
        - No placeholder values
        - Entities extracted
        - Step parameters populated
        - Descriptions provided

        Args:
            task: Task object
            task_dict: Raw task dictionary

        Returns:
            Completeness score (0.0-1.0)
        """
        score = 1.0

        # Check if entities are extracted
        if not task.entities:
            score -= 0.15

        # Check if all steps have parameters
        empty_params = sum(1 for step in task.steps if not step.parameters)
        if empty_params > 0:
            score -= 0.1 * min(empty_params, 3)  # Cap penalty at 0.3

        # Check if descriptions are meaningful (>10 chars)
        if len(task.goal) < 10:
            score -= 0.15

        short_descriptions = sum(1 for step in task.steps if len(step.description) < 10)
        if short_descriptions > 0:
            score -= 0.05 * min(short_descriptions, 3)  # Cap penalty at 0.15

        # Check for placeholder text
        placeholders = ["TODO", "TBD", "...", "placeholder", "example", "N/A"]
        for placeholder in placeholders:
            if placeholder.lower() in task.goal.lower():
                score -= 0.2
                break

        return max(0.0, score)

    def _score_consistency(self, task: Task, context: dict[str, Any] | None = None) -> float:
        """
        Score based on consistency with context.

        Checks:
        - Task type matches step count
        - Estimated durations are reasonable
        - Dependencies are valid
        - Entities match context (if provided)
        - Parameters are valid for tool types

        Args:
            task: Task object
            context: Optional context with entities, conversation state, etc.

        Returns:
            Consistency score (0.0-1.0)
        """
        score = 1.0

        # Check task type consistency
        if task.task_type == TaskType.SINGLE_STEP and len(task.steps) != 1:
            score -= 0.25
        elif task.task_type == TaskType.MULTI_STEP and not 2 <= len(task.steps) <= 5:
            score -= 0.25

        # Check duration consistency
        step_total = sum(step.estimated_duration for step in task.steps)
        if step_total > 0:
            duration_diff = abs(task.estimated_duration - step_total)
            if duration_diff > step_total * 0.3:  # >30% difference
                score -= 0.2

        # Check for reasonable durations (0.1s to 60s per step)
        unreasonable_durations = sum(
            1 for step in task.steps if not 0.1 <= step.estimated_duration <= 60.0
        )
        if unreasonable_durations > 0:
            score -= 0.1 * min(unreasonable_durations, 3)

        # Check dependencies are valid (no forward references)
        invalid_deps = sum(
            1 for step in task.steps for dep_id in step.depends_on if dep_id >= step.step_id
        )
        if invalid_deps > 0:
            score -= 0.15 * min(invalid_deps, 2)

        # Check context consistency if provided
        if context:
            score *= self._check_context_consistency(task, context)

        return max(0.0, score)

    def _check_context_consistency(self, task: Task, context: dict[str, Any]) -> float:
        """
        Check consistency with provided context.

        Args:
            task: Task object
            context: Context dictionary with entities, etc.

        Returns:
            Consistency multiplier (0.5-1.0)
        """
        multiplier = 1.0

        # Check if task entities match context entities
        context_entities = context.get("entities", {})
        if context_entities:
            # Check if task entities are subset of context entities
            task_entity_types = set(task.entities.keys())
            context_entity_types = set(context_entities.keys())

            # Penalize if task has entities not in context
            extra_entities = task_entity_types - context_entity_types
            if extra_entities:
                multiplier -= 0.1 * min(len(extra_entities), 3)

        return max(0.5, multiplier)

    def _score_quality(self, task: Task) -> float:
        """
        Score based on description quality.

        Checks:
        - Descriptions are clear and specific
        - No placeholder text
        - Proper capitalization
        - Reasonable length
        - No repetition

        Args:
            task: Task object

        Returns:
            Quality score (0.0-1.0)
        """
        score = 1.0

        # Check for proper capitalization (first letter uppercase)
        if task.goal and not task.goal[0].isupper():
            score -= 0.1

        # Check for reasonable length (not too short, not too long)
        if len(task.goal) < 5:
            score -= 0.2
        elif len(task.goal) > 200:
            score -= 0.1

        # Check step descriptions
        for step in task.steps:
            if len(step.description) < 5:
                score -= 0.1
            elif len(step.description) > 200:
                score -= 0.05

            # Check for proper capitalization
            if step.description and not step.description[0].isupper():
                score -= 0.05

        # Check for repetition (same description multiple times)
        descriptions = [step.description.lower() for step in task.steps]
        if len(descriptions) != len(set(descriptions)):
            score -= 0.15

        return max(0.0, score)

    def _score_historical(self, task: Task) -> float:
        """
        Score based on historical accuracy for this task type.

        Uses success rate from past executions to adjust confidence.
        If no history exists, returns neutral score (0.5).

        Args:
            task: Task object

        Returns:
            Historical score (0.0-1.0)
        """
        task_type_key = task.task_type
        history = self._history.get(task_type_key)

        if not history or history.total_attempts < 5:
            # Not enough data, return neutral
            return 0.5

        # Return success rate as historical score
        return history.success_rate

    def _apply_calibration(self, task: Task, raw_confidence: float) -> float:
        """
        Apply historical calibration to confidence score.

        Adjusts confidence based on how well past confidence scores
        correlated with actual success rates.

        Args:
            task: Task object
            raw_confidence: Uncalibrated confidence score

        Returns:
            Calibrated confidence score
        """
        task_type_key = task.task_type
        history = self._history.get(task_type_key)

        if not history or history.total_attempts < 10:
            # Not enough data for calibration
            return raw_confidence

        # Apply calibration factor
        calibration_factor = history.calibration_factor
        calibrated = raw_confidence * calibration_factor

        # Clamp to reasonable range
        return max(0.1, min(0.95, calibrated))


# Global scorer instance for convenience
_global_scorer: ConfidenceScorer | None = None


def get_confidence_scorer() -> ConfidenceScorer:
    """
    Get global confidence scorer instance.

    Returns:
        Global ConfidenceScorer instance
    """
    global _global_scorer
    if _global_scorer is None:
        _global_scorer = ConfidenceScorer()
    return _global_scorer


def score_task_confidence(
    task: Task, task_dict: dict[str, Any], context: dict[str, Any] | None = None
) -> float:
    """
    Convenience function to score task confidence.

    Args:
        task: Task object
        task_dict: Raw task dictionary
        context: Optional context

    Returns:
        Confidence score (0.0-1.0)
    """
    scorer = get_confidence_scorer()
    return scorer.score(task, task_dict, context)
