"""Execution result and response data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ResponseModality(str, Enum):
    """Enumeration of response modalities."""

    VOICE = "voice"  # Voice-only response
    TEXT = "text"  # Text-only response
    BOTH = "both"  # Both voice and text
    VISUAL = "visual"  # Visual/UI response (cards, images)
    MULTIMODAL = "multimodal"  # Multiple modalities


class ExecutionResult(BaseModel):
    """Represents the result of an action execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    result_data: Optional[Any] = Field(
        default=None,
        description="Result data from successful execution",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed",
    )
    execution_time: float = Field(
        ...,
        description="Actual execution time in seconds",
    )
    action_id: str = Field(..., description="ID of executed action")
    tool_id: str = Field(..., description="ID of tool that was executed")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Execution timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata",
    )

    @field_validator("execution_time")
    @classmethod
    def validate_execution_time(cls, v: float) -> float:
        """Validate execution time is non-negative."""
        if v < 0:
            raise ValueError("Execution time must be non-negative")
        return v

    @field_validator("action_id")
    @classmethod
    def validate_action_id(cls, v: str) -> str:
        """Validate action ID is not empty."""
        if not v:
            raise ValueError("Action ID cannot be empty")
        return v

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, v: str) -> str:
        """Validate tool ID is not empty."""
        if not v:
            raise ValueError("Tool ID cannot be empty")
        return v

    def is_timeout(self) -> bool:
        """
        Check if execution resulted in timeout.

        Returns:
            True if execution timed out
        """
        if not self.success and self.error:
            return "timeout" in self.error.lower()
        return False

    def __eq__(self, other: object) -> bool:
        """Check equality based on action ID and success status."""
        if not isinstance(other, ExecutionResult):
            return False
        return (
            self.action_id == other.action_id
            and self.success == other.success
        )

    def __hash__(self) -> int:
        """Generate hash for execution result."""
        return hash((self.action_id, self.success))

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "result_data": {"timer_id": "timer_123", "duration": 300},
                "error": None,
                "execution_time": 0.045,
                "action_id": "action_123",
                "tool_id": "set_timer",
                "metadata": {"user_id": "user_456"},
            }
        }


class Response(BaseModel):
    """Represents a response to be delivered to the user."""

    text: str = Field(..., description="Response text")
    modality: ResponseModality = Field(
        default=ResponseModality.TEXT,
        description="Response modality",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Proactive follow-up suggestions",
    )
    rich_content: Optional[dict[str, Any]] = Field(
        default=None,
        description="Structured data for UI (cards, images, buttons)",
    )
    requires_user_action: bool = Field(
        default=False,
        description="Whether response requires user action",
    )
    action_options: list[str] = Field(
        default_factory=list,
        description="Available action options for user",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response generation timestamp",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Validate response text is not empty."""
        if not v or not v.strip():
            raise ValueError("Response text cannot be empty")
        return v

    @field_validator("suggestions")
    @classmethod
    def validate_suggestions(cls, v: list[str]) -> list[str]:
        """Validate suggestions are not empty strings."""
        if any(not s.strip() for s in v):
            raise ValueError("Suggestions cannot contain empty strings")
        return v

    @field_validator("action_options")
    @classmethod
    def validate_action_options(cls, v: list[str]) -> list[str]:
        """Validate action options are not empty strings."""
        if any(not opt.strip() for opt in v):
            raise ValueError("Action options cannot contain empty strings")
        return v

    def is_voice_compatible(self) -> bool:
        """
        Check if response is compatible with voice output.

        Returns:
            True if response can be spoken
        """
        return self.modality in {
            ResponseModality.VOICE,
            ResponseModality.BOTH,
            ResponseModality.MULTIMODAL,
        }

    def is_text_compatible(self) -> bool:
        """
        Check if response is compatible with text output.

        Returns:
            True if response can be displayed as text
        """
        return self.modality in {
            ResponseModality.TEXT,
            ResponseModality.BOTH,
            ResponseModality.MULTIMODAL,
        }

    def has_rich_content(self) -> bool:
        """
        Check if response has rich content.

        Returns:
            True if response has rich content
        """
        return self.rich_content is not None and len(self.rich_content) > 0

    def __eq__(self, other: object) -> bool:
        """Check equality based on text and modality."""
        if not isinstance(other, Response):
            return False
        return self.text == other.text and self.modality == other.modality

    def __hash__(self) -> int:
        """Generate hash for response."""
        return hash((self.text, self.modality))

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "text": "Timer set for 5 minutes",
                "modality": "both",
                "metadata": {"intent_type": "set_timer"},
                "suggestions": [
                    "Set another timer",
                    "Cancel timer",
                ],
                "rich_content": {
                    "type": "card",
                    "title": "Timer Active",
                    "body": "5:00 remaining",
                },
                "requires_user_action": False,
                "action_options": [],
            }
        }
