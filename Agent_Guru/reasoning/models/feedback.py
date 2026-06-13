"""Feedback data models for online learning.

This module defines data structures for collecting user feedback on intent
predictions to enable continuous model improvement through online learning.

Performance Requirements:
- Time Complexity: O(1) for feedback storage
- Space Complexity: O(n) where n is number of feedback entries
- Latency: <50ms for feedback collection

Author: Kiro AI
Date: 2024
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FeedbackType(str, Enum):
    """Type of feedback provided by user."""

    INTENT_CORRECTION = "intent_correction"  # User corrected the intent
    ENTITY_CORRECTION = "entity_correction"  # User corrected entities
    POSITIVE = "positive"  # User confirmed prediction was correct
    NEGATIVE = "negative"  # User indicated prediction was wrong
    CORRECTION = "correction"  # Generic correction (used by FeedbackCollector)


class IntentFeedback(BaseModel):
    """Feedback on intent detection for online learning.

    Attributes:
        feedback_id: Unique identifier for feedback entry
        user_id: User who provided feedback
        timestamp: When feedback was provided
        original_input: Original user input text
        predicted_intent: Intent predicted by model
        predicted_entities: Entities extracted by model
        predicted_confidence: Model confidence score
        correct_intent: Correct intent (if provided)
        correct_entities: Correct entities (if provided)
        feedback_type: Type of feedback
        model_version: Version of model that made prediction
        metadata: Additional context

    """

    feedback_id: str = Field(..., description="Unique feedback identifier")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Feedback timestamp",
    )

    # Original prediction
    original_input: str = Field(..., min_length=1, description="Original user input")
    predicted_intent: str = Field(..., description="Predicted intent type")
    predicted_entities: dict[str, Any] = Field(
        default_factory=dict,
        description="Predicted entities",
    )
    predicted_confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence")

    # Corrections
    correct_intent: str | None = Field(None, description="Correct intent (if different)")
    correct_entities: dict[str, Any] | None = Field(
        None,
        description="Correct entities (if different)",
    )

    # Metadata
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    model_version: str = Field(..., description="Model version that made prediction")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @field_validator("original_input")
    @classmethod
    def validate_input(cls, v: str) -> str:
        """Validate input is not empty."""
        if not v or not v.strip():
            msg = "Original input cannot be empty"
            raise ValueError(msg)
        return v.strip()

    @field_validator("predicted_intent")
    @classmethod
    def validate_predicted_intent(cls, v: str) -> str:
        """Validate predicted intent is not empty."""
        if not v or not v.strip():
            msg = "Predicted intent cannot be empty"
            raise ValueError(msg)
        return v.strip()

    def is_correction(self) -> bool:
        """Check if feedback contains a correction."""
        return self.feedback_type in (
            FeedbackType.INTENT_CORRECTION,
            FeedbackType.ENTITY_CORRECTION,
            FeedbackType.NEGATIVE,
        )

    def was_correct(self) -> bool:
        """Check if prediction was correct."""
        return self.feedback_type == FeedbackType.POSITIVE

    def get_training_label(self) -> str:
        """Get the correct label for training."""
        if self.correct_intent:
            return self.correct_intent
        return self.predicted_intent


class ModelPerformanceMetrics(BaseModel):
    """Performance metrics for tracking model drift.

    Attributes:
        metric_id: Unique identifier
        model_version: Model version being tracked
        timestamp: When metrics were calculated
        total_predictions: Total number of predictions
        correct_predictions: Number of correct predictions
        accuracy: Overall accuracy
        intent_accuracies: Per-intent accuracy scores
        avg_confidence: Average confidence score
        low_confidence_rate: Rate of low confidence predictions
        correction_rate: Rate of user corrections
        metadata: Additional metrics

    """

    metric_id: str = Field(..., description="Unique metric identifier")
    model_version: str = Field(..., description="Model version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Metric timestamp",
    )

    # Performance metrics
    total_predictions: int = Field(..., ge=0, description="Total predictions")
    correct_predictions: int = Field(..., ge=0, description="Correct predictions")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Overall accuracy")

    # Detailed metrics
    intent_accuracies: dict[str, float] = Field(
        default_factory=dict,
        description="Per-intent accuracy",
    )
    avg_confidence: float = Field(..., ge=0.0, le=1.0, description="Average confidence")
    low_confidence_rate: float = Field(..., ge=0.0, le=1.0, description="Low confidence rate")
    correction_rate: float = Field(..., ge=0.0, le=1.0, description="Correction rate")

    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metrics")

    @field_validator("correct_predictions")
    @classmethod
    def validate_correct_predictions(cls, v: int, info) -> int:
        """Validate correct predictions <= total predictions."""
        if "total_predictions" in info.data and v > info.data["total_predictions"]:
            msg = "Correct predictions cannot exceed total predictions"
            raise ValueError(msg)
        return v

    def has_drift(self, baseline_accuracy: float, threshold: float = 0.05) -> bool:
        """Check if model has drifted from baseline.

        Args:
            baseline_accuracy: Baseline accuracy to compare against
            threshold: Drift threshold (default 5%)

        Returns:
            True if accuracy dropped by more than threshold

        """
        return (baseline_accuracy - self.accuracy) > threshold
