"""
Tool Intelligence Engine for learning and optimizing tool performance.

This module implements intelligent tool tracking, ranking, and learning based on:
- Success rates and reliability
- Execution latency and performance
- User preferences and feedback
- Degradation detection and recovery
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class FailurePattern(str, Enum):
    """Common failure patterns for tools."""

    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PERMISSION_DENIED = "permission_denied"
    INVALID_PARAMETERS = "invalid_parameters"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    UNKNOWN = "unknown"


class ToolStats(BaseModel):
    """Statistics and performance metrics for a tool.

    Tracks execution history, success rates, latency, user feedback,
    and degradation status for intelligent tool selection.

    Attributes:
        tool_id: Unique tool identifier
        success_rate: Success rate (0.0-1.0)
        avg_latency: Average execution latency in milliseconds
        total_executions: Total number of executions
        successful_executions: Number of successful executions
        failed_executions: Number of failed executions
        failure_patterns: Dictionary of failure pattern → count
        user_rating: Average user rating (0.0-5.0)
        user_feedback_count: Number of user feedback entries
        is_degraded: Whether tool is currently degraded
        degradation_reason: Reason for degradation if applicable
        consecutive_failures: Number of consecutive failures
        last_execution_time: Timestamp of last execution
        last_success_time: Timestamp of last successful execution
        created_at: Timestamp when stats were created
        updated_at: Timestamp when stats were last updated
    """

    tool_id: str = Field(..., description="Unique tool identifier")
    success_rate: float = Field(
        default=1.0, description="Success rate (0.0-1.0)", ge=0.0, le=1.0
    )
    avg_latency: float = Field(
        default=0.0, description="Average execution latency in milliseconds", ge=0.0
    )
    total_executions: int = Field(
        default=0, description="Total number of executions", ge=0
    )
    successful_executions: int = Field(
        default=0, description="Number of successful executions", ge=0
    )
    failed_executions: int = Field(
        default=0, description="Number of failed executions", ge=0
    )
    failure_patterns: Dict[str, int] = Field(
        default_factory=dict, description="Dictionary of failure pattern → count"
    )
    user_rating: float = Field(
        default=0.0, description="Average user rating (0.0-5.0)", ge=0.0, le=5.0
    )
    user_feedback_count: int = Field(
        default=0, description="Number of user feedback entries", ge=0
    )
    is_degraded: bool = Field(
        default=False, description="Whether tool is currently degraded"
    )
    degradation_reason: Optional[str] = Field(
        default=None, description="Reason for degradation if applicable"
    )
    consecutive_failures: int = Field(
        default=0, description="Number of consecutive failures", ge=0
    )
    last_execution_time: Optional[datetime] = Field(
        default=None, description="Timestamp of last execution"
    )
    last_success_time: Optional[datetime] = Field(
        default=None, description="Timestamp of last successful execution"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when stats were created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when stats were last updated",
    )

    @field_validator("total_executions", mode="after")
    @classmethod
    def validate_total_executions(cls, v: int, info: Any) -> int:
        """Validate that total executions equals sum of successful and failed."""
        # Access validated data from the model
        data = info.data
        if "successful_executions" in data and "failed_executions" in data:
            expected = data["successful_executions"] + data["failed_executions"]
            if v != expected:
                raise ValueError(
                    f"total_executions ({v}) must equal successful_executions "
                    f"({data['successful_executions']}) + failed_executions "
                    f"({data['failed_executions']})"
                )
        return v

    @model_validator(mode="after")
    def validate_execution_counts(self) -> "ToolStats":
        """Validate execution counts are consistent."""
        expected_total = self.successful_executions + self.failed_executions
        if self.total_executions != expected_total:
            raise ValueError(
                f"total_executions ({self.total_executions}) must equal "
                f"successful_executions ({self.successful_executions}) + "
                f"failed_executions ({self.failed_executions})"
            )
        return self

    def calculate_success_rate(self) -> float:
        """Calculate success rate from execution counts.

        Returns:
            Success rate (0.0-1.0)
        """
        if self.total_executions == 0:
            return 1.0  # No executions yet, assume perfect
        return self.successful_executions / self.total_executions

    def update_success_rate(self) -> None:
        """Update success rate based on current execution counts."""
        self.success_rate = self.calculate_success_rate()

    def record_success(self, latency_ms: float) -> None:
        """Record a successful execution.

        Args:
            latency_ms: Execution latency in milliseconds
        """
        self.successful_executions += 1
        self.total_executions += 1
        self.consecutive_failures = 0
        self.last_execution_time = datetime.utcnow()
        self.last_success_time = datetime.utcnow()

        # Update average latency (exponential moving average)
        if self.avg_latency == 0.0:
            self.avg_latency = latency_ms
        else:
            # EMA with alpha=0.2 (gives more weight to recent values)
            self.avg_latency = 0.8 * self.avg_latency + 0.2 * latency_ms

        self.update_success_rate()
        self.updated_at = datetime.utcnow()

        # Check if tool should be re-enabled after degradation
        if self.is_degraded and self.consecutive_failures == 0:
            self.is_degraded = False
            self.degradation_reason = None

    def record_failure(self, failure_pattern: FailurePattern) -> None:
        """Record a failed execution.

        Args:
            failure_pattern: Type of failure that occurred
        """
        self.failed_executions += 1
        self.total_executions += 1
        self.consecutive_failures += 1
        self.last_execution_time = datetime.utcnow()

        # Track failure pattern
        pattern_key = failure_pattern.value
        self.failure_patterns[pattern_key] = self.failure_patterns.get(pattern_key, 0) + 1

        self.update_success_rate()
        self.updated_at = datetime.utcnow()

        # Check if tool should be marked as degraded
        # Only mark as degraded if we have enough data (at least 5 executions)
        if not self.is_degraded and self.total_executions >= 5:
            # Check consecutive failures first (higher priority)
            if self.consecutive_failures >= 3:
                self.is_degraded = True
                self.degradation_reason = f"Consecutive failures: {self.consecutive_failures}"
            elif self.success_rate < 0.7:
                self.is_degraded = True
                self.degradation_reason = f"Success rate below threshold: {self.success_rate:.2%}"

    def record_user_feedback(self, rating: float) -> None:
        """Record user feedback rating.

        Args:
            rating: User rating (0.0-5.0)
        """
        if not 0.0 <= rating <= 5.0:
            raise ValueError(f"Rating must be between 0.0 and 5.0, got {rating}")

        # Update average rating (exponential moving average)
        if self.user_feedback_count == 0:
            self.user_rating = rating
        else:
            # EMA with alpha=0.3 (gives more weight to recent feedback)
            self.user_rating = 0.7 * self.user_rating + 0.3 * rating

        self.user_feedback_count += 1
        self.updated_at = datetime.utcnow()

    def get_most_common_failure(self) -> Optional[str]:
        """Get the most common failure pattern.

        Returns:
            Most common failure pattern or None if no failures
        """
        if not self.failure_patterns:
            return None

        return max(self.failure_patterns.items(), key=lambda x: x[1])[0]

    def get_reliability_score(self) -> float:
        """Calculate reliability score (0.0-1.0).

        Considers success rate and degradation status.

        Returns:
            Reliability score (0.0-1.0)
        """
        if self.is_degraded:
            return self.success_rate * 0.5  # Penalize degraded tools
        return self.success_rate

    def get_speed_score(self, max_latency: float = 5000.0) -> float:
        """Calculate speed score (0.0-1.0).

        Args:
            max_latency: Maximum expected latency in milliseconds

        Returns:
            Speed score (0.0-1.0)
        """
        if self.avg_latency == 0.0:
            return 1.0  # No executions yet, assume fast

        # Score = 1.0 - (latency / max_latency), clamped to [0.0, 1.0]
        score = 1.0 - (self.avg_latency / max_latency)
        return max(0.0, min(1.0, score))

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "tool_id": "timer.set",
                "success_rate": 0.95,
                "avg_latency": 150.0,
                "total_executions": 100,
                "successful_executions": 95,
                "failed_executions": 5,
                "failure_patterns": {"timeout": 3, "invalid_parameters": 2},
                "user_rating": 4.5,
                "user_feedback_count": 20,
                "is_degraded": False,
                "degradation_reason": None,
                "consecutive_failures": 0,
            }
        }
