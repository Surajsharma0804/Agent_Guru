"""Online learning manager for continuous model improvement.

This module coordinates feedback collection, performance tracking, drift detection,
and periodic model retraining to continuously improve intent detection accuracy.

Performance Requirements:
- Time Complexity: O(1) for feedback collection, O(n) for metrics calculation
- Space Complexity: O(n) where n is number of feedback entries
- Latency: <50ms for feedback collection, <500ms for metrics calculation

Author: Kiro AI
Date: 2024
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from Agent_Guru.reasoning.learning.feedback_store import FeedbackStore
from Agent_Guru.reasoning.models.feedback import (
    FeedbackType,
    IntentFeedback,
    ModelPerformanceMetrics,
)


class OnlineLearner:
    """Online learning manager for continuous model improvement.

    Coordinates:
    - Feedback collection from user corrections
    - Performance metrics tracking
    - Model drift detection
    - Periodic retraining triggers

    Time Complexity: O(1) for feedback, O(n) for metrics
    Space Complexity: O(n) where n is feedback entries

    Example:
        >>> learner = OnlineLearner(model_version="v1.0")
        >>> await learner.initialize()
        >>> await learner.collect_feedback(...)
        >>> metrics = await learner.calculate_metrics()

    """

    def __init__(
        self,
        model_version: str,
        db_path: str = "feedback.db",
        baseline_accuracy: float = 0.95,
        drift_threshold: float = 0.05,
        retraining_threshold: int = 100,
    ) -> None:
        """Initialize online learner.

        Args:
            model_version: Current model version
            db_path: Path to feedback database
            baseline_accuracy: Baseline accuracy for drift detection
            drift_threshold: Accuracy drop threshold for drift (default 5%)
            retraining_threshold: Min feedback count to trigger retraining

        """
        self.model_version = model_version
        self.baseline_accuracy = baseline_accuracy
        self.drift_threshold = drift_threshold
        self.retraining_threshold = retraining_threshold

        self.store = FeedbackStore(db_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize online learner."""
        if self._initialized:
            return

        await self.store.initialize()
        self._initialized = True

    async def collect_feedback(
        self,
        user_id: str,
        original_input: str,
        predicted_intent: str,
        predicted_entities: dict,
        predicted_confidence: float,
        correct_intent: str | None = None,
        correct_entities: dict | None = None,
        feedback_type: FeedbackType = FeedbackType.POSITIVE,
        metadata: dict | None = None,
    ) -> IntentFeedback:
        """Collect user feedback on intent prediction.

        Time Complexity: O(1)

        Args:
            user_id: User identifier
            original_input: Original user input
            predicted_intent: Intent predicted by model
            predicted_entities: Entities extracted by model
            predicted_confidence: Model confidence score
            correct_intent: Correct intent (if different)
            correct_entities: Correct entities (if different)
            feedback_type: Type of feedback
            metadata: Additional context

        Returns:
            Created feedback entry

        """
        if not self._initialized:
            await self.initialize()

        feedback = IntentFeedback(
            feedback_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=datetime.now(tz=UTC),
            original_input=original_input,
            predicted_intent=predicted_intent,
            predicted_entities=predicted_entities,
            predicted_confidence=predicted_confidence,
            correct_intent=correct_intent,
            correct_entities=correct_entities,
            feedback_type=feedback_type,
            model_version=self.model_version,
            metadata=metadata or {},
        )

        await self.store.store_feedback(feedback)
        return feedback

    async def calculate_metrics(self, since: datetime | None = None) -> ModelPerformanceMetrics:
        """Calculate performance metrics from feedback.

        Time Complexity: O(n) where n is number of feedback entries

        Args:
            since: Calculate metrics for feedback after this time
                   (default: last 7 days)

        Returns:
            Performance metrics

        """
        if not self._initialized:
            await self.initialize()

        # Default to last 7 days
        if since is None:
            since = datetime.now(tz=UTC) - timedelta(days=7)

        # Get feedback entries
        feedback_list = await self.store.get_feedback_since(
            since=since,
            model_version=self.model_version,
        )

        if not feedback_list:
            # No feedback, return default metrics
            return ModelPerformanceMetrics(
                metric_id=str(uuid.uuid4()),
                model_version=self.model_version,
                timestamp=datetime.now(tz=UTC),
                total_predictions=0,
                correct_predictions=0,
                accuracy=0.0,
                intent_accuracies={},
                avg_confidence=0.0,
                low_confidence_rate=0.0,
                correction_rate=0.0,
                metadata={},
            )

        # Calculate metrics
        total = len(feedback_list)
        correct = sum(1 for f in feedback_list if f.was_correct())
        corrections = sum(1 for f in feedback_list if f.is_correction())

        # Per-intent accuracy
        intent_counts: dict[str, int] = defaultdict(int)
        intent_correct: dict[str, int] = defaultdict(int)

        for feedback in feedback_list:
            intent = feedback.predicted_intent
            intent_counts[intent] += 1
            if feedback.was_correct():
                intent_correct[intent] += 1

        intent_accuracies = {
            intent: intent_correct[intent] / count for intent, count in intent_counts.items()
        }

        # Confidence metrics
        confidences = [f.predicted_confidence for f in feedback_list]
        avg_confidence = sum(confidences) / len(confidences)
        low_confidence_count = sum(1 for c in confidences if c < 0.8)  # noqa: PLR2004 - Threshold value

        low_confidence_rate = low_confidence_count / total

        # Create metrics object
        metrics = ModelPerformanceMetrics(
            metric_id=str(uuid.uuid4()),
            model_version=self.model_version,
            timestamp=datetime.now(tz=UTC),
            total_predictions=total,
            correct_predictions=correct,
            accuracy=correct / total,
            intent_accuracies=intent_accuracies,
            avg_confidence=avg_confidence,
            low_confidence_rate=low_confidence_rate,
            correction_rate=corrections / total,
            metadata={
                "period_start": since.isoformat(),
                "period_end": datetime.now(tz=UTC).isoformat(),
            },
        )

        # Store metrics
        await self.store.store_metrics(metrics)

        return metrics

    async def detect_drift(self) -> tuple[bool, ModelPerformanceMetrics | None]:
        """Detect if model has drifted from baseline performance.

        Time Complexity: O(n) where n is feedback entries

        Returns:
            Tuple of (has_drifted, current_metrics)

        """
        if not self._initialized:
            await self.initialize()

        # Calculate current metrics
        metrics = await self.calculate_metrics()

        # Check for drift
        has_drifted = metrics.has_drift(
            baseline_accuracy=self.baseline_accuracy,
            threshold=self.drift_threshold,
        )

        return has_drifted, metrics

    async def should_retrain(self) -> tuple[bool, str]:
        """Check if model should be retrained.

        Time Complexity: O(n) where n is feedback entries

        Returns:
            Tuple of (should_retrain, reason)

        """
        if not self._initialized:
            await self.initialize()

        # Check feedback count
        feedback_count = await self.store.get_feedback_count(model_version=self.model_version)

        if feedback_count < self.retraining_threshold:
            return False, f"Insufficient feedback ({feedback_count}/{self.retraining_threshold})"

        # Check for drift
        has_drifted, metrics = await self.detect_drift()

        if has_drifted and metrics:
            return True, f"Model drift detected (accuracy: {metrics.accuracy:.2%})"

        # Check correction rate
        if metrics and metrics.correction_rate > 0.10:  # >10% corrections  # noqa: PLR2004 (Threshold value)

            return True, f"High correction rate ({metrics.correction_rate:.2%})"

        # Check low confidence rate
        if metrics and metrics.low_confidence_rate > 0.20:  # >20% low confidence  # noqa: PLR2004 (Threshold value)

            return True, f"High low-confidence rate ({metrics.low_confidence_rate:.2%})"

        return False, "Model performance acceptable"

    async def get_training_data(self, limit: int | None = None) -> list[tuple[str, str]]:
        """Get training data from feedback corrections.

        Time Complexity: O(n) where n is number of corrections

        Args:
            limit: Maximum number of examples to return

        Returns:
            List of (input, label) tuples for training

        """
        if not self._initialized:
            await self.initialize()

        # Get corrections
        corrections = await self.store.get_corrections_for_training(
            model_version=self.model_version,
            limit=limit,
        )

        # Convert to training format
        return [
            (feedback.original_input, feedback.get_training_label()) for feedback in corrections
        ]

    async def get_performance_summary(self) -> dict:
        """Get summary of model performance.

        Time Complexity: O(n) where n is feedback entries

        Returns:
            Performance summary dictionary

        """
        if not self._initialized:
            await self.initialize()

        # Get latest metrics
        metrics = await self.calculate_metrics()

        # Get feedback counts
        total_feedback = await self.store.get_feedback_count(model_version=self.model_version)
        recent_feedback = await self.store.get_feedback_count(
            model_version=self.model_version,
            since=datetime.now(tz=UTC) - timedelta(days=7),
        )

        # Check retraining status
        should_retrain, reason = await self.should_retrain()

        return {
            "model_version": self.model_version,
            "baseline_accuracy": self.baseline_accuracy,
            "current_accuracy": metrics.accuracy,
            "accuracy_delta": metrics.accuracy - self.baseline_accuracy,
            "total_feedback": total_feedback,
            "recent_feedback": recent_feedback,
            "correction_rate": metrics.correction_rate,
            "low_confidence_rate": metrics.low_confidence_rate,
            "avg_confidence": metrics.avg_confidence,
            "should_retrain": should_retrain,
            "retraining_reason": reason,
            "intent_accuracies": metrics.intent_accuracies,
            "last_updated": metrics.timestamp.isoformat(),
        }
