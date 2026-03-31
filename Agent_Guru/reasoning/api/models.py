"""
API request and response models.

This module defines Pydantic models for API requests and responses with
comprehensive validation and documentation.

Performance Characteristics:
    - Time Complexity: O(1) for validation
    - Space Complexity: O(n) where n is data size

Design Principles:
    - Type-safe with Pydantic
    - Comprehensive validation
    - Clear error messages
    - OpenAPI documentation

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProcessRequest(BaseModel):
    """Request model for processing user input.

    Attributes:
        text: User input text
        user_id: User identifier
        conversation_id: Optional conversation ID for context
        source: Input source (voice, text, system_event)
        metadata: Additional request metadata
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "text": "set a timer for 5 minutes",
            "user_id": "user_123",
            "conversation_id": "conv_456",
            "source": "text",
            "metadata": {},
        }
    })

    text: str = Field(
        ...,
        description="User input text to process",
        min_length=1,
        max_length=10000,
        examples=["set a timer for 5 minutes"],
    )
    user_id: str = Field(
        ...,
        description="Unique user identifier",
        min_length=1,
        max_length=256,
        examples=["user_123"],
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation ID for context",
        max_length=256,
        examples=["conv_456"],
    )
    source: str = Field(
        default="text",
        description="Input source type",
        pattern="^(voice|text|system_event)$",
        examples=["text"],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional request metadata",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Validate text is not empty after stripping."""
        if not v.strip():
            raise ValueError("Text cannot be empty or whitespace only")
        return v.strip()


class ProcessResponse(BaseModel):
    """Response model for processed requests.

    Attributes:
        response: Generated response text
        confidence: Confidence score (0.0-1.0)
        intent_type: Detected intent type
        success: Whether processing succeeded
        fast_path: Whether fast-path was used
        latency_ms: Total processing latency
        stage_latencies: Latency per pipeline stage
        trace_id: Distributed trace ID
        timestamp: Response timestamp
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "response": "Timer set for 5 minutes",
            "confidence": 0.98,
            "intent_type": "set_timer",
            "success": True,
            "fast_path": True,
            "latency_ms": 234.5,
            "stage_latencies": {
                "intent_detection": 50.2,
                "tool_selection": 12.3,
            },
            "trace_id": "abc123def456",
            "timestamp": "2024-01-01T12:00:00Z",
        }
    })

    response: str = Field(
        ...,
        description="Generated response text",
        examples=["Timer set for 5 minutes"],
    )
    confidence: float = Field(
        ...,
        description="Confidence score (0.0-1.0)",
        ge=0.0,
        le=1.0,
        examples=[0.98],
    )
    intent_type: Optional[str] = Field(
        default=None,
        description="Detected intent type",
        examples=["set_timer"],
    )
    success: bool = Field(
        ...,
        description="Whether processing succeeded",
        examples=[True],
    )
    fast_path: bool = Field(
        default=False,
        description="Whether fast-path was used",
        examples=[True],
    )
    latency_ms: float = Field(
        ...,
        description="Total processing latency in milliseconds",
        ge=0.0,
        examples=[234.5],
    )
    stage_latencies: dict[str, float] = Field(
        default_factory=dict,
        description="Latency per pipeline stage",
        examples=[{"intent_detection": 50.2, "tool_selection": 12.3}],
    )
    trace_id: Optional[str] = Field(
        default=None,
        description="Distributed trace ID",
        examples=["abc123def456"],
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp",
    )


class ConversationResponse(BaseModel):
    """Response model for conversation queries.

    Attributes:
        conversation_id: Conversation identifier
        user_id: User identifier
        turn_count: Number of turns in conversation
        recent_turns: Recent conversation turns
        entities: Tracked entities
        created_at: Conversation creation timestamp
        updated_at: Last update timestamp
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "conversation_id": "conv_456",
            "user_id": "user_123",
            "turn_count": 5,
            "recent_turns": [],
            "entities": {},
            "created_at": "2024-01-01T12:00:00Z",
            "updated_at": "2024-01-01T12:05:00Z",
        }
    })

    conversation_id: str = Field(
        ...,
        description="Conversation identifier",
        examples=["conv_456"],
    )
    user_id: str = Field(
        ...,
        description="User identifier",
        examples=["user_123"],
    )
    turn_count: int = Field(
        ...,
        description="Number of turns in conversation",
        ge=0,
        examples=[5],
    )
    recent_turns: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent conversation turns",
    )
    entities: dict[str, Any] = Field(
        default_factory=dict,
        description="Tracked entities",
    )
    created_at: datetime = Field(
        ...,
        description="Conversation creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )


class TaskStatusResponse(BaseModel):
    """Response model for async task status.

    Attributes:
        task_id: Task identifier
        status: Task status (queued, running, completed, failed)
        progress: Progress percentage (0.0-1.0)
        result: Task result if completed
        error: Error message if failed
        created_at: Task creation timestamp
        updated_at: Last update timestamp
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_789",
            "status": "running",
            "progress": 0.65,
            "result": None,
            "error": None,
            "created_at": "2024-01-01T12:00:00Z",
            "updated_at": "2024-01-01T12:00:30Z",
        }
    })

    task_id: str = Field(
        ...,
        description="Task identifier",
        examples=["task_789"],
    )
    status: str = Field(
        ...,
        description="Task status",
        pattern="^(queued|running|completed|failed)$",
        examples=["running"],
    )
    progress: float = Field(
        default=0.0,
        description="Progress percentage (0.0-1.0)",
        ge=0.0,
        le=1.0,
        examples=[0.65],
    )
    result: Optional[Any] = Field(
        default=None,
        description="Task result if completed",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed",
    )
    created_at: datetime = Field(
        ...,
        description="Task creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )


class ErrorResponse(BaseModel):
    """Response model for errors.

    Attributes:
        error: Error message
        error_code: Error code
        details: Additional error details
        timestamp: Error timestamp
        trace_id: Distributed trace ID
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "Invalid request: text cannot be empty",
            "error_code": "VALIDATION_ERROR",
            "details": {"field": "text"},
            "timestamp": "2024-01-01T12:00:00Z",
            "trace_id": "abc123def456",
        }
    })

    error: str = Field(
        ...,
        description="Error message",
        examples=["Invalid request: text cannot be empty"],
    )
    error_code: str = Field(
        ...,
        description="Error code",
        examples=["VALIDATION_ERROR"],
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error details",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp",
    )
    trace_id: Optional[str] = Field(
        default=None,
        description="Distributed trace ID",
    )
