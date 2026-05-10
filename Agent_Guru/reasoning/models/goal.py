"""Persistent goal and trigger data models.

This module defines data structures for persistent goals that can be triggered
automatically based on time, location, events, or conditions.

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


class TriggerType(str, Enum):
    """Type of goal trigger."""

    TIME_BASED = "time_based"  # Triggered at specific time
    LOCATION_BASED = "location_based"  # Triggered at location
    EVENT_BASED = "event_based"  # Triggered by system event
    CONDITIONAL = "conditional"  # Triggered by condition


class GoalStatus(str, Enum):
    """Status of persistent goal."""

    ACTIVE = "active"  # Goal is active and being evaluated
    PAUSED = "paused"  # Goal is paused by user
    COMPLETED = "completed"  # Goal has been completed
    CANCELLED = "cancelled"  # Goal was cancelled by user


class TimeBasedTrigger(BaseModel):
    """Time-based trigger configuration.

    Attributes:
        time_of_day: Hour and minute (HH:MM format)
        day_of_week: Day of week (0-6, Monday=0) or None for every day
        day_of_month: Day of month (1-31) or None
        recurrence: Recurrence pattern (daily, weekly, monthly)

    """

    time_of_day: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Time in HH:MM format")
    day_of_week: int | None = Field(
        default=None,
        ge=0,
        le=6,
        description="Day of week (0-6, Monday=0)",
    )
    day_of_month: int | None = Field(default=None, ge=1, le=31, description="Day of month (1-31)")
    recurrence: str = Field(
        default="daily",
        pattern=r"^(daily|weekly|monthly|once)$",
        description="Recurrence pattern",
    )


class LocationBasedTrigger(BaseModel):
    """Location-based trigger configuration.

    Attributes:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        radius: Radius in meters
        trigger_on: When to trigger (enter, exit, dwell)

    """

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
    radius: float = Field(..., gt=0.0, description="Radius in meters")
    trigger_on: str = Field(
        default="enter",
        pattern=r"^(enter|exit|dwell)$",
        description="Trigger condition",
    )


class EventBasedTrigger(BaseModel):
    """Event-based trigger configuration.

    Attributes:
        event_type: Type of event to listen for
        event_filter: Filter criteria for event

    """

    event_type: str = Field(..., description="Type of event")
    event_filter: dict[str, Any] = Field(
        default_factory=dict,
        description="Filter criteria for event",
    )


class ConditionalTrigger(BaseModel):
    """Conditional trigger configuration.

    Attributes:
        condition_expression: Boolean expression to evaluate
        check_interval: How often to check condition (seconds)

    """

    condition_expression: str = Field(..., description="Boolean expression")
    check_interval: int = Field(default=60, ge=10, description="Check interval in seconds")


class PersistentGoal(BaseModel):
    """Persistent goal with automatic triggering.

    Attributes:
        goal_id: Unique goal identifier
        user_id: User identifier
        description: Human-readable goal description
        trigger_type: Type of trigger
        trigger_condition: Trigger configuration (type depends on trigger_type)
        action_plan: Action to execute when triggered
        status: Current goal status
        created_at: When goal was created
        last_evaluated: Last time trigger was evaluated
        last_triggered: Last time goal was triggered
        trigger_count: Number of times goal has been triggered
        notify_before_execution: Whether to notify user before executing
        notification_sent: Whether notification was sent
        metadata: Additional goal data

    """

    goal_id: str = Field(..., description="Unique goal identifier")
    user_id: str = Field(..., description="User identifier")
    description: str = Field(..., description="Goal description")
    trigger_type: TriggerType = Field(..., description="Type of trigger")
    trigger_condition: dict[str, Any] = Field(..., description="Trigger configuration")
    action_plan: dict[str, Any] = Field(..., description="Action to execute")
    status: GoalStatus = Field(default=GoalStatus.ACTIVE, description="Goal status")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Creation time",
    )
    last_evaluated: datetime | None = Field(default=None, description="Last evaluation time")
    last_triggered: datetime | None = Field(default=None, description="Last trigger time")
    trigger_count: int = Field(default=0, ge=0, description="Trigger count")
    notify_before_execution: bool = Field(default=True, description="Notify before executing")
    notification_sent: bool = Field(default=False, description="Notification sent")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("trigger_condition")
    @classmethod
    def validate_trigger_condition(cls, v: dict, info) -> dict:
        """Validate trigger condition matches trigger type."""
        if "trigger_type" not in info.data:
            return v

        trigger_type = info.data["trigger_type"]

        # Validate based on trigger type
        if trigger_type == TriggerType.TIME_BASED:
            TimeBasedTrigger(**v)  # Validate structure
        elif trigger_type == TriggerType.LOCATION_BASED:
            LocationBasedTrigger(**v)
        elif trigger_type == TriggerType.EVENT_BASED:
            EventBasedTrigger(**v)
        elif trigger_type == TriggerType.CONDITIONAL:
            ConditionalTrigger(**v)

        return v

    def is_active(self) -> bool:
        """Check if goal is active."""
        return self.status == GoalStatus.ACTIVE

    def can_trigger(self, min_interval_seconds: int = 3600) -> bool:
        """Check if goal can be triggered.

        Args:
            min_interval_seconds: Minimum interval between triggers

        Returns:
            True if goal can be triggered

        """
        if not self.is_active():
            return False

        if self.last_triggered is None:
            return True

        # Check minimum interval
        elapsed = (datetime.now(tz=UTC) - self.last_triggered).total_seconds()
        return elapsed >= min_interval_seconds

    def mark_triggered(self) -> None:
        """Mark goal as triggered."""
        self.last_triggered = datetime.now(tz=UTC)
        self.trigger_count += 1
        self.notification_sent = False

    def mark_evaluated(self) -> None:
        """Mark goal as evaluated."""
        self.last_evaluated = datetime.now(tz=UTC)


class GoalExecutionResult(BaseModel):
    """Result of goal execution.

    Attributes:
        goal_id: Goal identifier
        success: Whether execution was successful
        result_data: Execution result data
        error: Error message if failed
        execution_time: Execution duration in seconds
        timestamp: When execution occurred

    """

    goal_id: str = Field(..., description="Goal identifier")
    success: bool = Field(..., description="Execution success")
    result_data: dict[str, Any] | None = Field(default=None, description="Result data")
    error: str | None = Field(default=None, description="Error message")
    execution_time: float = Field(..., ge=0.0, description="Execution time in seconds")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Execution time",
    )
