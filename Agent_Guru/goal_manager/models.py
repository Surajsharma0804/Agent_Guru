"""Data models for Goal Manager.

Defines core data structures using Pydantic for validation.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GoalStatus(str, Enum):
    """Goal execution status."""

    PENDING = "pending"
    DECOMPOSING = "decomposing"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    COMPLETED = "complete"  # Alias for COMPLETE
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class Priority(str, Enum):
    """Goal priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Alias for backward compatibility with tests
GoalPriority = Priority


class GoalType(str, Enum):
    """Goal type classification."""

    TASK = "task"
    PROJECT = "project"
    MILESTONE = "milestone"
    OBJECTIVE = "objective"


class Goal(BaseModel):
    """A goal with hierarchical structure.

    Attributes:
        id: Unique identifier (UUID)
        description: High-level goal description
        status: Current execution status
        priority: Priority level
        goal_type: Type of goal (task, project, milestone, objective)
        progress: Completion progress (0.0 to 1.0)
        created_at: Creation timestamp
        started_at: Start timestamp (None if not started)
        completed_at: Completion timestamp (None if not completed)
        deadline: Optional deadline timestamp
        parent_id: Parent goal ID (None for root goals)
        sub_goal_ids: List of sub-goal IDs
        dependency_ids: List of dependency goal IDs
        dependencies: Alias for dependency_ids
        metadata: Additional metadata
        error_message: Error message if failed (None otherwise)
        retry_count: Number of retry attempts

    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(min_length=1)
    status: GoalStatus = Field(default=GoalStatus.PENDING)
    priority: Priority = Field(default=Priority.MEDIUM)
    goal_type: GoalType = Field(default=GoalType.TASK)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    deadline: datetime | None = None
    parent_id: str | None = None
    sub_goal_ids: list[str] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    retry_count: int = Field(default=0)

    @property
    def dependencies(self) -> list[str]:
        """Alias for dependency_ids."""
        return self.dependency_ids

    @field_validator("progress")
    @classmethod
    def validate_progress(cls, v: float) -> float:
        """Validate progress is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            msg = f"Progress must be between 0.0 and 1.0, got {v}"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_timestamp_ordering(self) -> "Goal":
        """Validate that timestamps are in chronological order."""
        if self.started_at is not None and self.created_at is not None:
            if self.started_at < self.created_at:
                msg = f"started_at ({self.started_at}) must not be before created_at ({self.created_at})"
                raise ValueError(
                    msg,
                )
        if self.completed_at is not None and self.started_at is not None:
            if self.completed_at < self.started_at:
                msg = f"completed_at ({self.completed_at}) must not be before started_at ({self.started_at})"
                raise ValueError(
                    msg,
                )
        return self

    model_config = ConfigDict(use_enum_values=True)


class ExecutionResult:
    """Result of a goal execution attempt."""

    def __init__(
        self,
        success: bool,
        goal_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.success = success
        self.goal_id = goal_id
        self.error = error
