"""Behavioral learning data models.

This module defines data structures for tracking user behavior patterns,
command frequency, preferences, and proactive suggestions.

Performance Requirements:
- Time Complexity: O(1) for field access
- Space Complexity: O(1) per instance
- Validation: <1ms per model

Author: Kiro AI
Date: 2024
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CommandFrequency(BaseModel):
    """Tracks frequency and success rate of user commands.

    Attributes:
        command: The command text or intent type
        user_id: User identifier
        frequency: Number of times command was used
        last_used: Last time command was executed
        success_rate: Success rate (0.0-1.0)
        total_executions: Total number of executions
        successful_executions: Number of successful executions
        avg_latency: Average execution latency in seconds
        metadata: Additional tracking data

    """

    command: str = Field(..., description="Command text or intent type")
    user_id: str = Field(..., description="User identifier")
    frequency: int = Field(default=0, ge=0, description="Usage frequency")
    last_used: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Last usage time",
    )
    success_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Success rate")
    total_executions: int = Field(default=0, ge=0, description="Total executions")
    successful_executions: int = Field(default=0, ge=0, description="Successful executions")
    avg_latency: float = Field(default=0.0, ge=0.0, description="Average latency in seconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("successful_executions")
    @classmethod
    def validate_successful_executions(cls, v: int, info) -> int:  # noqa: ANN001
        """Validate successful executions <= total executions."""
        if "total_executions" in info.data and v > info.data["total_executions"]:
            msg = "successful_executions cannot exceed total_executions"
            raise ValueError(msg)
        return v

    def update_execution(self, success: bool, latency: float) -> None:
        """Update execution statistics.

        Args:
            success: Whether execution was successful
            latency: Execution latency in seconds

        """
        self.total_executions += 1
        if success:
            self.successful_executions += 1

        # Update success rate
        self.success_rate = self.successful_executions / self.total_executions

        # Update average latency (exponential moving average)
        alpha = 0.2  # Smoothing factor
        self.avg_latency = alpha * latency + (1 - alpha) * self.avg_latency

        # Update frequency and last used
        self.frequency += 1
        self.last_used = datetime.now(tz=UTC)


class PatternType(str, Enum):
    """Type of behavioral pattern."""

    TIME_OF_DAY = "time_of_day"  # Morning routine, evening routine
    DAY_OF_WEEK = "day_of_week"  # Weekly meetings, weekend activities
    LOCATION = "location"  # Home, work, commute
    ACTIVITY = "activity"  # Exercise, work, leisure
    SEQUENCE = "sequence"  # Command sequences


class TimePattern(BaseModel):
    """Time-based behavioral pattern.

    Attributes:
        pattern_id: Unique pattern identifier
        user_id: User identifier
        pattern_type: Type of pattern
        command: Command or action
        time_of_day: Hour of day (0-23) or None
        day_of_week: Day of week (0-6, Monday=0) or None
        frequency: Number of occurrences
        confidence: Pattern confidence (0.0-1.0)
        last_occurrence: Last time pattern occurred
        metadata: Additional pattern data

    """

    pattern_id: str = Field(..., description="Unique pattern identifier")
    user_id: str = Field(..., description="User identifier")
    pattern_type: PatternType = Field(..., description="Type of pattern")
    command: str = Field(..., description="Command or action")
    time_of_day: int | None = Field(default=None, ge=0, le=23, description="Hour of day (0-23)")
    day_of_week: int | None = Field(
        default=None,
        ge=0,
        le=6,
        description="Day of week (0-6, Monday=0)",
    )
    frequency: int = Field(default=1, ge=1, description="Number of occurrences")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Pattern confidence")
    last_occurrence: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Last occurrence time",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def update_occurrence(self) -> None:
        """Update pattern with new occurrence."""
        self.frequency += 1
        self.last_occurrence = datetime.now(tz=UTC)

        # Update confidence based on frequency
        # More occurrences = higher confidence (asymptotic to 1.0)
        self.confidence = min(0.95, 1.0 - (1.0 / (1.0 + self.frequency * 0.1)))


class AppUsage(BaseModel):
    """Application usage tracking.

    Attributes:
        app_id: Application identifier
        user_id: User identifier
        app_name: Application name
        open_count: Number of times app was opened
        total_duration: Total usage duration in seconds
        avg_duration: Average session duration in seconds
        last_used: Last time app was used
        usage_patterns: Time-based usage patterns
        metadata: Additional usage data

    """

    app_id: str = Field(..., description="Application identifier")
    user_id: str = Field(..., description="User identifier")
    app_name: str = Field(..., description="Application name")
    open_count: int = Field(default=0, ge=0, description="Number of opens")
    total_duration: float = Field(default=0.0, ge=0.0, description="Total duration in seconds")
    avg_duration: float = Field(default=0.0, ge=0.0, description="Average duration in seconds")
    last_used: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Last usage time",
    )
    usage_patterns: list[str] = Field(default_factory=list, description="Time-based usage patterns")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def update_usage(self, duration: float) -> None:
        """Update usage statistics.

        Args:
            duration: Session duration in seconds

        """
        self.open_count += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.open_count
        self.last_used = datetime.now(tz=UTC)


class PreferenceType(str, Enum):
    """Type of user preference."""

    TONE = "tone"  # Professional vs casual
    CONFIRMATION = "confirmation"  # Always confirm vs trust
    TOOL = "tool"  # Preferred tools/services
    VERBOSITY = "verbosity"  # Concise vs detailed
    PROACTIVITY = "proactivity"  # Proactive suggestions on/off


class UserPreference(BaseModel):
    """Learned user preference.

    Attributes:
        preference_id: Unique preference identifier
        user_id: User identifier
        preference_type: Type of preference
        preference_key: Preference key (e.g., "music_service")
        preference_value: Preference value (e.g., "spotify")
        confidence: Confidence in preference (0.0-1.0)
        learned_from: How preference was learned
        sample_count: Number of samples used to learn
        last_updated: Last time preference was updated
        metadata: Additional preference data

    """

    preference_id: str = Field(..., description="Unique preference identifier")
    user_id: str = Field(..., description="User identifier")
    preference_type: PreferenceType = Field(..., description="Type of preference")
    preference_key: str = Field(..., description="Preference key")
    preference_value: Any = Field(..., description="Preference value")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score")
    learned_from: str = Field(..., description="How preference was learned")
    sample_count: int = Field(default=1, ge=1, description="Number of samples")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Last update time",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def update_preference(self, new_value: Any, weight: float = 0.2) -> None:  # noqa: ANN401
        """Update preference with new observation.

        Uses exponential moving average for numeric values,
        voting for categorical values.

        Args:
            new_value: New observed value
            weight: Weight for new value (0.0-1.0)

        """
        self.sample_count += 1

        # For numeric values, use exponential moving average
        if isinstance(self.preference_value, (int, float)) and isinstance(new_value, (int, float)):
            self.preference_value = weight * new_value + (1 - weight) * self.preference_value

        # For categorical values, update if new value is different
        else:
            if new_value != self.preference_value:
                # Lower confidence when values differ
                self.confidence *= 0.9
            else:
                # Increase confidence when values match
                self.confidence = min(0.95, self.confidence + 0.05)

            # Update value if confidence drops below threshold
            if self.confidence < 0.5:  # noqa: PLR2004 - Threshold value

                self.preference_value = new_value
                self.confidence = 0.5

        self.last_updated = datetime.now(tz=UTC)


class ProactiveSuggestion(BaseModel):
    """Proactive suggestion based on learned patterns.

    Attributes:
        suggestion_id: Unique suggestion identifier
        user_id: User identifier
        suggestion_text: Suggestion text
        command: Suggested command
        confidence: Confidence in suggestion (0.0-1.0)
        relevance: Relevance score (0.0-1.0)
        based_on: What pattern this is based on
        context: Current context that triggered suggestion
        created_at: When suggestion was created
        expires_at: When suggestion expires
        accepted: Whether user accepted suggestion
        metadata: Additional suggestion data

    """

    suggestion_id: str = Field(..., description="Unique suggestion identifier")
    user_id: str = Field(..., description="User identifier")
    suggestion_text: str = Field(..., description="Suggestion text")
    command: str = Field(..., description="Suggested command")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    based_on: str = Field(..., description="Pattern this is based on")
    context: dict[str, Any] = Field(..., description="Current context")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Creation time",
    )
    expires_at: datetime = Field(..., description="Expiration time")
    accepted: bool | None = Field(default=None, description="Whether accepted")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def is_expired(self) -> bool:
        """Check if suggestion has expired."""
        return datetime.now(tz=UTC) > self.expires_at

    def calculate_score(self) -> float:
        """Calculate overall suggestion score.

        Returns:
            Combined score (0.0-1.0)

        """
        # Weighted combination of confidence and relevance
        return 0.6 * self.confidence + 0.4 * self.relevance


class BehavioralStats(BaseModel):
    """Aggregate behavioral statistics for a user.

    Attributes:
        user_id: User identifier
        total_commands: Total number of commands executed
        unique_commands: Number of unique commands
        most_frequent_commands: Top 10 most frequent commands
        detected_patterns: Number of detected patterns
        learned_preferences: Number of learned preferences
        suggestion_acceptance_rate: Rate of accepted suggestions
        last_updated: Last time stats were updated
        metadata: Additional statistics

    """

    user_id: str = Field(..., description="User identifier")
    total_commands: int = Field(default=0, ge=0, description="Total commands")
    unique_commands: int = Field(default=0, ge=0, description="Unique commands")
    most_frequent_commands: list[tuple[str, int]] = Field(
        default_factory=list,
        description="Top commands with counts",
    )
    detected_patterns: int = Field(default=0, ge=0, description="Number of patterns")
    learned_preferences: int = Field(default=0, ge=0, description="Number of preferences")
    suggestion_acceptance_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Acceptance rate",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Last update",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional stats")
