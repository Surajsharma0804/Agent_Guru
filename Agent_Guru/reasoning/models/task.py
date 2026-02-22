"""
Task data models for structured LLM output parsing.

This module defines the Task and TaskStep data models that represent
the structured output from the Semantic LLM Interpreter. These models
are used to convert natural language requests into executable tasks.

Requirements: 16.2, 17.2, 17.3, 17.5, 28.1, 28.2
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class TaskType(str, Enum):
    """
    Type of task to be executed.

    - single_step: One action to complete (e.g., "set timer", "play music")
    - multi_step: 2-5 sequential actions (e.g., "check weather and remind me if raining")
    - conversational: Requires dialogue, no immediate action (e.g., "tell me about yourself")
    - memory_query: Retrieves information from memory (e.g., "when did I last call John?")
    """

    SINGLE_STEP = "single_step"
    MULTI_STEP = "multi_step"
    CONVERSATIONAL = "conversational"
    MEMORY_QUERY = "memory_query"


class TaskStatus(str, Enum):
    """
    Execution status of a task or task step.

    - pending: Not yet started
    - running: Currently executing
    - completed: Successfully finished
    - failed: Execution failed
    - cancelled: Cancelled by user or system
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStep(BaseModel):
    """
    A single step in a task execution plan.

    Each step represents one atomic action that can be executed by a tool.
    Steps can depend on previous steps and have their own status tracking.

    Attributes:
        step_id: Unique identifier for this step (1-indexed)
        description: Human-readable description of what this step does
        tool_id: ID of the tool to execute this step
        parameters: Parameters to pass to the tool
        depends_on: List of step IDs this step depends on (for multi-step tasks)
        estimated_duration: Estimated execution time in seconds
        status: Current execution status
        result: Result data from execution (populated after completion)
        error: Error message if execution failed
        started_at: Timestamp when execution started
        completed_at: Timestamp when execution completed
    """

    step_id: int = Field(..., ge=1, description="Step ID (1-indexed)")
    description: str = Field(..., min_length=1, description="Step description")
    tool_id: str = Field(..., min_length=1, description="Tool to execute")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    depends_on: list[int] = Field(default_factory=list, description="Dependent step IDs")
    estimated_duration: float = Field(
        default=1.0, gt=0, description="Estimated duration in seconds"
    )
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Execution status")
    result: Optional[Any] = Field(default=None, description="Execution result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")

    @field_validator("depends_on")
    @classmethod
    def validate_depends_on(cls, v: list[int], info) -> list[int]:
        """Validate that dependencies reference valid step IDs."""
        if v:
            step_id = info.data.get("step_id")
            if step_id is not None:
                # Dependencies must reference earlier steps
                for dep_id in v:
                    if dep_id >= step_id:
                        raise ValueError(
                            f"Step {step_id} cannot depend on step {dep_id} "
                            f"(dependencies must reference earlier steps)"
                        )
        return v

    @field_validator("estimated_duration")
    @classmethod
    def validate_duration(cls, v: float) -> float:
        """Validate duration is reasonable (0.1s to 60s)."""
        if not 0.1 <= v <= 60.0:
            raise ValueError(f"estimated_duration must be 0.1-60.0 seconds, got {v}")
        return v


class Task(BaseModel):
    """
    Structured task representation from LLM output.

    A Task represents a complete user request that has been parsed and
    structured by the Semantic LLM Interpreter. It contains all information
    needed to execute the request, including goals, entities, execution steps,
    and metadata.

    Attributes:
        goal: Clear, concise description of what the user wants to achieve
        task_type: Type of task (single_step, multi_step, conversational, memory_query)
        entities: Extracted entities and parameters from user input
        steps: List of execution steps (1-5 steps)
        confidence: Confidence score for task interpretation (0.0-1.0)
        requires_confirmation: Whether user confirmation is needed before execution
        estimated_duration: Total estimated execution time in seconds
        status: Current execution status
        retry_count: Number of retry attempts (max 3)
        created_at: Timestamp when task was created
        started_at: Timestamp when execution started
        completed_at: Timestamp when execution completed
        error: Error message if task failed
    """

    goal: str = Field(..., min_length=1, description="Task goal description")
    task_type: TaskType = Field(..., description="Type of task")
    entities: dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    steps: list[TaskStep] = Field(
        ..., min_items=1, max_items=5, description="Execution steps (1-5)"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    requires_confirmation: bool = Field(default=False, description="Requires user confirmation")
    estimated_duration: float = Field(..., gt=0, description="Total estimated duration in seconds")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Execution status")
    retry_count: int = Field(default=0, ge=0, le=3, description="Retry attempts (max 3)")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: list[TaskStep], info) -> list[TaskStep]:
        """Validate steps are properly structured."""
        if not v:
            raise ValueError("Task must have at least one step")

        if len(v) > 5:
            raise ValueError(f"Task cannot have more than 5 steps, got {len(v)}")

        # Validate step IDs are sequential starting from 1
        expected_ids = list(range(1, len(v) + 1))
        actual_ids = [step.step_id for step in v]
        if actual_ids != expected_ids:
            raise ValueError(
                f"Step IDs must be sequential starting from 1, "
                f"expected {expected_ids}, got {actual_ids}"
            )

        # Validate no circular dependencies
        for step in v:
            if step.step_id in step.depends_on:
                raise ValueError(f"Step {step.step_id} cannot depend on itself")

        # Validate task type consistency
        task_type = info.data.get("task_type")
        if task_type is not None:
            # Single-step tasks must have exactly 1 step
            if task_type == TaskType.SINGLE_STEP and len(v) != 1:
                raise ValueError(f"single_step task must have exactly 1 step, got {len(v)}")

            # Multi-step tasks must have 2-5 steps
            if task_type == TaskType.MULTI_STEP and not 2 <= len(v) <= 5:
                raise ValueError(f"multi_step task must have 2-5 steps, got {len(v)}")

        return v

    @field_validator("estimated_duration")
    @classmethod
    def validate_total_duration(cls, v: float, info) -> float:
        """Validate total duration matches sum of step durations."""
        steps = info.data.get("steps", [])

        if steps:
            step_total = sum(step.estimated_duration for step in steps)
            # Allow 10% tolerance for rounding
            if abs(v - step_total) > step_total * 0.1:
                raise ValueError(
                    f"estimated_duration ({v}s) should approximately match "
                    f"sum of step durations ({step_total}s)"
                )

        # Validate duration is reasonable (0.1s to 300s = 5 minutes)
        if not 0.1 <= v <= 300.0:
            raise ValueError(f"estimated_duration must be 0.1-300.0 seconds, got {v}")

        return v

    @field_validator("retry_count")
    @classmethod
    def validate_retry_count(cls, v: int) -> int:
        """Validate retry count is within limits."""
        if v > 3:
            raise ValueError(f"retry_count cannot exceed 3, got {v}")
        return v

    def increment_retry(self) -> None:
        """Increment retry count (max 3)."""
        if self.retry_count >= 3:
            raise ValueError("Maximum retry count (3) exceeded")
        self.retry_count += 1

    def mark_started(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark task as failed with error message."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error

    def mark_cancelled(self) -> None:
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.status == TaskStatus.FAILED and self.retry_count < 3

    def is_complete(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]

    def get_next_pending_step(self) -> Optional[TaskStep]:
        """Get the next pending step that has all dependencies completed."""
        for step in self.steps:
            if step.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are completed
            if step.depends_on:
                deps_completed = all(
                    self.steps[dep_id - 1].status == TaskStatus.COMPLETED
                    for dep_id in step.depends_on
                )
                if not deps_completed:
                    continue

            return step

        return None

    def get_completed_steps(self) -> list[TaskStep]:
        """Get all completed steps."""
        return [step for step in self.steps if step.status == TaskStatus.COMPLETED]

    def get_failed_steps(self) -> list[TaskStep]:
        """Get all failed steps."""
        return [step for step in self.steps if step.status == TaskStatus.FAILED]

    def calculate_progress(self) -> float:
        """Calculate task progress as percentage (0.0-1.0)."""
        if not self.steps:
            return 0.0

        completed = len(self.get_completed_steps())
        return completed / len(self.steps)

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat() if v else None}
        use_enum_values = True
