"""
Core data models for Agent Orchestration System.

Defines agents, tasks, performance records, and evolution events using Pydantic
for validation and type safety.

Performance Characteristics:
- Time Complexity: O(1) for model creation and validation
- Space Complexity: O(1) per model instance
- Memory: <1KB per agent, <500 bytes per task

Design Decisions:
- Pydantic for automatic validation and serialization
- Immutable fields where appropriate (id, created_at)
- Type hints for all fields (mypy strict compliance)
- Enums for status fields (type safety)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class AgentStatus(str, Enum):
    """Agent lifecycle status.

    Lifecycle flow:
    CREATED -> ACTIVE -> SPECIALIZING -> ACTIVE
                      -> MERGING -> MERGED
                      -> SPLITTING -> SPLIT
                      -> RETIRING -> RETIRED
    """
    CREATED = "created"
    ACTIVE = "active"
    SPECIALIZING = "specializing"
    MERGING = "merging"
    SPLITTING = "splitting"
    RETIRING = "retiring"
    RETIRED = "retired"
    MERGED = "merged"  # Terminal state after merge
    SPLIT = "split"    # Terminal state after split


class TaskType(str, Enum):
    """Task type categories.

    Note: These are NOT agent roles. Task types describe the nature of work,
    not the agent performing it. Agents dynamically specialize in task types
    based on performance patterns.
    """
    # Analysis and understanding
    ANALYSIS = "analysis"
    RESEARCH = "research"
    INVESTIGATION = "investigation"

    # Design and planning
    DESIGN = "design"
    ARCHITECTURE = "architecture"
    PLANNING = "planning"

    # Implementation
    CODING = "coding"
    IMPLEMENTATION = "implementation"
    INTEGRATION = "integration"

    # Quality assurance
    TESTING = "testing"
    REVIEW = "review"
    VERIFICATION = "verification"

    # Documentation
    DOCUMENTATION = "documentation"
    EXPLANATION = "explanation"

    # Optimization
    OPTIMIZATION = "optimization"
    REFACTORING = "refactoring"

    # Debugging
    DEBUGGING = "debugging"
    TROUBLESHOOTING = "troubleshooting"

    # Generic
    GENERIC = "generic"


class PerformanceRecord(BaseModel):
    """Record of agent performance on a task.

    Tracks success/failure, timing, and resource usage for performance analysis
    and specialization scoring.
    """
    task_id: str = Field(..., description="Unique task identifier")
    task_type: TaskType = Field(..., description="Type of task performed")
    success: bool = Field(..., description="Whether task succeeded")
    completion_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Task completion time in milliseconds"
    )
    resource_usage: dict[str, float] = Field(
        default_factory=dict,
        description="Resource usage metrics (cpu_ms, memory_mb, api_calls)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When task was completed"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if task failed"
    )

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Agent(BaseModel):
    """An agent with capabilities and performance history.

    Agents are dynamically created entities that emerge from task patterns.
    They are NOT pre-defined roles like "researcher" or "coder".

    Key Properties:
    - Unique identifier (UUID)
    - Dynamic capabilities that evolve with experience
    - Specializations based on task success patterns
    - Complete performance history for learning

    Performance Characteristics:
    - Memory: ~1KB per agent (excluding history)
    - Creation: O(1)
    - Serialization: O(n) where n = history size
    """
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique agent identifier (UUID)"
    )
    status: AgentStatus = Field(
        default=AgentStatus.CREATED,
        description="Current lifecycle status"
    )
    capabilities: dict[str, float] = Field(
        default_factory=dict,
        description="Capability name -> proficiency (0.0-1.0)"
    )
    specializations: dict[str, float] = Field(
        default_factory=dict,
        description="Task type -> specialization score (0.0-1.0)"
    )
    performance_history: list[PerformanceRecord] = Field(
        default_factory=list,
        description="Historical performance records"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When agent was created"
    )
    last_active: datetime = Field(
        default_factory=datetime.now,
        description="Last activity timestamp"
    )
    total_tasks: int = Field(
        default=0,
        ge=0,
        description="Total tasks attempted"
    )
    successful_tasks: int = Field(
        default=0,
        ge=0,
        description="Successfully completed tasks"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (creation reason, merge history, etc.)"
    )

    @field_validator("capabilities", "specializations")
    @classmethod
    def validate_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that all scores are in range [0.0, 1.0]."""
        for key, value in v.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"Score for '{key}' must be between 0.0 and 1.0, got {value}"
                )
        return v

    @field_validator("successful_tasks")
    @classmethod
    def validate_successful_tasks(cls, v: int, info) -> int:
        """Validate that successful_tasks <= total_tasks."""
        # Note: info.data contains already-validated fields
        total = info.data.get("total_tasks", 0)
        if v > total:
            raise ValueError(
                f"successful_tasks ({v}) cannot exceed total_tasks ({total})"
            )
        return v

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Task(BaseModel):
    """A task to be executed by an agent.

    Tasks are units of work with requirements, dependencies, and success criteria.
    They can be decomposed into sub-tasks for parallel execution.
    """
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique task identifier (UUID)"
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Human-readable task description"
    )
    task_type: TaskType = Field(
        ...,
        description="Type of task"
    )
    requirements: dict[str, Any] = Field(
        default_factory=dict,
        description="Task requirements and constraints"
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria for task success"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Task priority (1=lowest, 10=highest)"
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Task IDs this task depends on"
    )
    parent_task_id: Optional[str] = Field(
        None,
        description="Parent task ID if this is a sub-task"
    )
    assigned_agent_id: Optional[str] = Field(
        None,
        description="Agent ID assigned to this task"
    )
    status: str = Field(
        default="pending",
        description="Task status (pending, assigned, in_progress, completed, failed)"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When task was created"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When task was completed"
    )
    result: Optional[Any] = Field(
        None,
        description="Task result if completed"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EvolutionEvent(BaseModel):
    """Record of agent evolution event.

    Tracks agent creation, merging, splitting, and retirement for GitHub sync
    and system-wide learning.
    """
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique event identifier (UUID)"
    )
    event_type: str = Field(
        ...,
        description="Event type (creation, merge, split, retirement)"
    )
    agent_ids: list[str] = Field(
        ...,
        description="Agent IDs involved in event"
    )
    reason: str = Field(
        ...,
        description="Reason for evolution event"
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When event occurred"
    )
    synced_to_github: bool = Field(
        default=False,
        description="Whether event has been synced to GitHub"
    )

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
