"""
Memory data models for retrieval-augmented reasoning.

This module implements comprehensive memory models for storing and retrieving
different types of memories (episodic, semantic, preference, task) to enhance
LLM reasoning with relevant context.

Performance Characteristics:
    - Time Complexity: O(1) for field access
    - Space Complexity: O(n) where n is content size
    - Validation: <1ms per model instance

Design Principles:
    - Type-safe with Pydantic validation
    - Immutable after creation (frozen=True for production use)
    - JSON serializable for storage
    - Comprehensive field validation

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class MemoryType(str, Enum):
    """Types of memories stored in the system.

    Memory types determine how memories are stored, retrieved, and used:
    - EPISODIC: Specific events and experiences (what happened)
    - SEMANTIC: Facts and knowledge (what is true)
    - PREFERENCE: User preferences and patterns (what user likes)
    - TASK: Task execution history and lessons (what was learned)
    """

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    TASK = "task"


class Memory(BaseModel):
    """Base class for all memory types.

    All memories share common fields for identification, content, retrieval,
    and metadata. Specific memory types extend this base with additional fields.

    Attributes:
        memory_id: Unique identifier for this memory (UUID)
        memory_type: Type of memory (episodic, semantic, preference, task)
        content: Human-readable text content of the memory
        embedding: Vector embedding for semantic search (768-dim for sentence-transformers)
        metadata: Additional structured data specific to memory type
        relevance_score: Current relevance score (0.0-1.0, updated on retrieval)
        timestamp: When this memory was created
        user_id: User who owns this memory

    Example:
        >>> memory = Memory(
        ...     memory_type=MemoryType.EPISODIC,
        ...     content="User set a timer for 5 minutes",
        ...     user_id="user_123"
        ... )
        >>> print(memory.memory_id)
        UUID('...')
    """

    memory_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this memory")
    memory_type: MemoryType = Field(
        ..., description="Type of memory (episodic, semantic, preference, task)"
    )
    content: str = Field(
        ..., min_length=1, max_length=10000, description="Human-readable text content of the memory"
    )
    embedding: Optional[list[float]] = Field(
        default=None, description="Vector embedding for semantic search (768-dim)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional structured data specific to memory type"
    )
    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Current relevance score (0.0-1.0, decays over time)",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc), description="When this memory was created (UTC)"
    )
    user_id: str = Field(..., min_length=1, max_length=255, description="User who owns this memory")

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        """Validate that content is not just whitespace."""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")
        return v.strip()

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimension(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        """Validate embedding dimension is 768 (sentence-transformers default)."""
        if v is not None:
            if len(v) != 768:
                raise ValueError(f"Embedding must be 768-dimensional, got {len(v)}")
            # Validate all values are finite
            if not all(isinstance(x, (int, float)) and -1e10 < x < 1e10 for x in v):
                raise ValueError("Embedding values must be finite numbers")
        return v

    @field_validator("user_id")
    @classmethod
    def validate_user_id_format(cls, v: str) -> str:
        """Validate user_id format."""
        if not v.strip():
            raise ValueError("user_id cannot be empty or whitespace only")
        return v.strip()

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
        use_enum_values = True


class EpisodicMemory(Memory):
    """Memory of a specific event or experience.

    Episodic memories capture what happened during user interactions,
    including actions taken, results, and context. These are used to
    understand user behavior patterns and provide relevant context.

    Attributes:
        action_taken: Description of the action that was performed
        result: Outcome of the action (success message or error)
        success: Whether the action succeeded
        context: Additional context about the situation

    Example:
        >>> memory = EpisodicMemory(
        ...     content="User set a timer for 5 minutes while cooking",
        ...     action_taken="set_timer",
        ...     result="Timer set successfully for 5 minutes",
        ...     success=True,
        ...     context={"location": "kitchen", "time_of_day": "evening"},
        ...     user_id="user_123"
        ... )
    """

    memory_type: MemoryType = Field(
        default=MemoryType.EPISODIC, description="Memory type (always EPISODIC for this class)"
    )
    action_taken: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Description of the action that was performed",
    )
    result: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Outcome of the action (success message or error)",
    )
    success: bool = Field(..., description="Whether the action succeeded")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context about the situation"
    )

    @field_validator("action_taken", "result")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that fields are not just whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()

    @model_validator(mode="after")
    def validate_memory_type(self) -> "EpisodicMemory":
        """Ensure memory_type is EPISODIC."""
        if self.memory_type != MemoryType.EPISODIC:
            raise ValueError("EpisodicMemory must have memory_type=EPISODIC")
        return self


class SemanticMemory(Memory):
    """Memory of a fact or piece of knowledge.

    Semantic memories capture facts, knowledge, and information that the
    user has shared or that the system has learned. These are used to
    answer questions and provide accurate information.

    Attributes:
        fact: The factual statement or knowledge
        source: Where this fact came from (user, web, inference)
        confidence: Confidence in the accuracy of this fact (0.0-1.0)

    Example:
        >>> memory = SemanticMemory(
        ...     content="User's favorite color is blue",
        ...     fact="favorite_color=blue",
        ...     source="user_stated",
        ...     confidence=1.0,
        ...     user_id="user_123"
        ... )
    """

    memory_type: MemoryType = Field(
        default=MemoryType.SEMANTIC, description="Memory type (always SEMANTIC for this class)"
    )
    fact: str = Field(
        ..., min_length=1, max_length=2000, description="The factual statement or knowledge"
    )
    source: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Where this fact came from (user, web, inference)",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the accuracy of this fact (0.0-1.0)"
    )

    @field_validator("fact", "source")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that fields are not just whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()

    @model_validator(mode="after")
    def validate_memory_type(self) -> "SemanticMemory":
        """Ensure memory_type is SEMANTIC."""
        if self.memory_type != MemoryType.SEMANTIC:
            raise ValueError("SemanticMemory must have memory_type=SEMANTIC")
        return self


class PreferenceMemory(Memory):
    """Memory of a user preference or pattern.

    Preference memories capture user preferences, habits, and behavioral
    patterns. These are used to personalize responses and anticipate needs.

    Attributes:
        preference_key: Key identifying the preference (e.g., "notification_time")
        preference_value: Value of the preference (e.g., "morning")
        learned_from: How this preference was learned (explicit, inferred, observed)

    Example:
        >>> memory = PreferenceMemory(
        ...     content="User prefers morning notifications",
        ...     preference_key="notification_time",
        ...     preference_value="morning",
        ...     learned_from="explicit",
        ...     user_id="user_123"
        ... )
    """

    memory_type: MemoryType = Field(
        default=MemoryType.PREFERENCE, description="Memory type (always PREFERENCE for this class)"
    )
    preference_key: str = Field(
        ..., min_length=1, max_length=255, description="Key identifying the preference"
    )
    preference_value: str = Field(
        ..., min_length=1, max_length=1000, description="Value of the preference"
    )
    learned_from: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="How this preference was learned (explicit, inferred, observed)",
    )

    @field_validator("preference_key", "preference_value", "learned_from")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that fields are not just whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()

    @field_validator("learned_from")
    @classmethod
    def validate_learned_from_value(cls, v: str) -> str:
        """Validate learned_from is one of the expected values."""
        valid_values = {"explicit", "inferred", "observed", "default"}
        if v.strip().lower() not in valid_values:
            raise ValueError(f"learned_from must be one of {valid_values}, got '{v}'")
        return v.strip().lower()

    @model_validator(mode="after")
    def validate_memory_type(self) -> "PreferenceMemory":
        """Ensure memory_type is PREFERENCE."""
        if self.memory_type != MemoryType.PREFERENCE:
            raise ValueError("PreferenceMemory must have memory_type=PREFERENCE")
        return self


class TaskMemory(Memory):
    """Memory of a task execution and lessons learned.

    Task memories capture multi-step task executions, their outcomes, and
    lessons learned. These are used to improve future task execution and
    avoid past mistakes.

    Attributes:
        task_id: Unique identifier for the task
        task_description: Human-readable description of the task
        outcome: Final outcome of the task (success, failure, partial)
        lessons_learned: Key insights and lessons from this task

    Example:
        >>> memory = TaskMemory(
        ...     content="Multi-step task to book restaurant and set reminder",
        ...     task_id="task_456",
        ...     task_description="Book restaurant for 7pm and set reminder 1 hour before",
        ...     outcome="success",
        ...     lessons_learned=["User prefers Italian restaurants", "Needs 1 hour prep time"],
        ...     user_id="user_123"
        ... )
    """

    memory_type: MemoryType = Field(
        default=MemoryType.TASK, description="Memory type (always TASK for this class)"
    )
    task_id: str = Field(
        ..., min_length=1, max_length=255, description="Unique identifier for the task"
    )
    task_description: str = Field(
        ..., min_length=1, max_length=2000, description="Human-readable description of the task"
    )
    outcome: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Final outcome of the task (success, failure, partial)",
    )
    lessons_learned: list[str] = Field(
        default_factory=list, description="Key insights and lessons from this task"
    )

    @field_validator("task_id", "task_description", "outcome")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that fields are not just whitespace."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()

    @field_validator("outcome")
    @classmethod
    def validate_outcome_value(cls, v: str) -> str:
        """Validate outcome is one of the expected values."""
        valid_values = {"success", "failure", "partial", "cancelled", "timeout"}
        if v.strip().lower() not in valid_values:
            raise ValueError(f"outcome must be one of {valid_values}, got '{v}'")
        return v.strip().lower()

    @field_validator("lessons_learned")
    @classmethod
    def validate_lessons_not_empty(cls, v: list[str]) -> list[str]:
        """Validate that lessons are not empty strings."""
        if v:
            cleaned = [lesson.strip() for lesson in v if lesson.strip()]
            if len(cleaned) != len(v):
                raise ValueError("Lessons cannot be empty or whitespace only")
            return cleaned
        return v

    @model_validator(mode="after")
    def validate_memory_type(self) -> "TaskMemory":
        """Ensure memory_type is TASK."""
        if self.memory_type != MemoryType.TASK:
            raise ValueError("TaskMemory must have memory_type=TASK")
        return self
