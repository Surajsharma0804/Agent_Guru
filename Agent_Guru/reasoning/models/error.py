"""Error handling data models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ErrorType(str, Enum):
    """Enumeration of error types."""

    # Input Errors
    INVALID_INPUT = "invalid_input"
    MALFORMED_INPUT = "malformed_input"

    # Intent Detection Errors
    INTENT_DETECTION_FAILED = "intent_detection_failed"
    AMBIGUOUS_INTENT = "ambiguous_intent"
    UNKNOWN_INTENT = "unknown_intent"

    # Reasoning Errors
    REASONING_FAILED = "reasoning_failed"
    REASONING_TIMEOUT = "reasoning_timeout"
    INVALID_REASONING_PLAN = "invalid_reasoning_plan"

    # Tool Selection Errors
    NO_TOOL_FOUND = "no_tool_found"
    TOOL_UNAVAILABLE = "tool_unavailable"
    INVALID_PARAMETERS = "invalid_parameters"

    # Safety Errors
    PERMISSION_DENIED = "permission_denied"
    SENSITIVE_ACTION_BLOCKED = "sensitive_action_blocked"
    CONFIRMATION_REQUIRED = "confirmation_required"

    # Execution Errors
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_TIMEOUT = "execution_timeout"
    TOOL_ERROR = "tool_error"

    # LLM Errors
    LLM_UNAVAILABLE = "llm_unavailable"
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_INVALID_RESPONSE = "llm_invalid_response"

    # System Errors
    SYSTEM_ERROR = "system_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    CONFIGURATION_ERROR = "configuration_error"

    # Network Errors
    NETWORK_ERROR = "network_error"
    SERVICE_UNAVAILABLE = "service_unavailable"


class FallbackStrategy(str, Enum):
    """Enumeration of fallback strategies."""

    # LLM Fallbacks
    CLOUD_TO_LOCAL_LLM = "cloud_to_local_llm"
    LOCAL_TO_CLOUD_LLM = "local_to_cloud_llm"
    LLM_TO_RULE_BASED = "llm_to_rule_based"

    # Tool Fallbacks
    ALTERNATIVE_TOOL = "alternative_tool"
    SIMPLIFIED_REQUEST = "simplified_request"

    # Execution Fallbacks
    SYNC_TO_ASYNC = "sync_to_async"
    PARTIAL_RESULTS = "partial_results"

    # General Fallbacks
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    USER_NOTIFICATION = "user_notification"
    GRACEFUL_DEGRADATION = "graceful_degradation"

    # No Fallback
    NONE = "none"


class Error(BaseModel):
    """Represents an error that occurred during processing."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error_code": "ERR_INTENT_001",
            "error_type": "intent_detection_failed",
            "message": "Failed to detect intent from input",
            "details": {"input": "mumble mumble", "confidence": 0.12},
            "recoverable": True,
            "suggested_fallback": "user_notification",
            "user_message": "I didn't understand that. Could you rephrase?",
        }
    })

    error_code: str = Field(..., description="Error code for identification")
    error_type: ErrorType = Field(..., description="Type of error")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error details",
    )
    recoverable: bool = Field(
        default=True,
        description="Whether error is recoverable",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp",
    )
    stack_trace: Optional[str] = Field(
        default=None,
        description="Stack trace for debugging",
    )
    suggested_fallback: Optional[FallbackStrategy] = Field(
        default=None,
        description="Suggested fallback strategy",
    )
    user_message: Optional[str] = Field(
        default=None,
        description="User-friendly error message",
    )

    @field_validator("error_code")
    @classmethod
    def validate_error_code(cls, v: str) -> str:
        """Validate error code is not empty."""
        if not v or not v.strip():
            raise ValueError("Error code cannot be empty")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate error message is not empty."""
        if not v or not v.strip():
            raise ValueError("Error message cannot be empty")
        return v

    def is_timeout_error(self) -> bool:
        """
        Check if error is a timeout error.

        Returns:
            True if error is timeout-related
        """
        return self.error_type in {
            ErrorType.REASONING_TIMEOUT,
            ErrorType.EXECUTION_TIMEOUT,
            ErrorType.LLM_TIMEOUT,
        }

    def is_llm_error(self) -> bool:
        """
        Check if error is LLM-related.

        Returns:
            True if error is LLM-related
        """
        return self.error_type in {
            ErrorType.LLM_UNAVAILABLE,
            ErrorType.LLM_TIMEOUT,
            ErrorType.LLM_RATE_LIMIT,
            ErrorType.LLM_INVALID_RESPONSE,
        }

    def is_safety_error(self) -> bool:
        """
        Check if error is safety-related.

        Returns:
            True if error is safety-related
        """
        return self.error_type in {
            ErrorType.PERMISSION_DENIED,
            ErrorType.SENSITIVE_ACTION_BLOCKED,
            ErrorType.CONFIRMATION_REQUIRED,
        }

    def should_retry(self) -> bool:
        """
        Check if error should trigger a retry.

        Returns:
            True if retry is recommended
        """
        return (
            self.recoverable
            and self.error_type in {
                ErrorType.LLM_TIMEOUT,
                ErrorType.EXECUTION_TIMEOUT,
                ErrorType.NETWORK_ERROR,
                ErrorType.SERVICE_UNAVAILABLE,
                ErrorType.LLM_RATE_LIMIT,
            }
        )

    def get_user_friendly_message(self) -> str:
        """
        Get user-friendly error message.

        Returns:
            User-friendly error message
        """
        if self.user_message:
            return self.user_message

        # Default user-friendly messages
        user_messages = {
            ErrorType.INVALID_INPUT: "I didn't understand that. Could you rephrase?",
            ErrorType.AMBIGUOUS_INTENT: "I'm not sure what you mean. Could you be more specific?",
            ErrorType.UNKNOWN_INTENT: "I'm not sure how to help with that.",
            ErrorType.NO_TOOL_FOUND: "I don't have the capability to do that yet.",
            ErrorType.PERMISSION_DENIED: "I don't have permission to do that.",
            ErrorType.EXECUTION_TIMEOUT: "That's taking longer than expected. Please try again.",
            ErrorType.LLM_UNAVAILABLE: "I'm having trouble thinking right now. Please try again.",
            ErrorType.SYSTEM_ERROR: "Something went wrong. Please try again.",
        }

        return user_messages.get(
            self.error_type,
            "I encountered an error. Please try again.",
        )

    def __eq__(self, other: object) -> bool:
        """Check equality based on error code and type."""
        if not isinstance(other, Error):
            return False
        return (
            self.error_code == other.error_code
            and self.error_type == other.error_type
        )

    def __hash__(self) -> int:
        """Generate hash for error."""
        return hash((self.error_code, self.error_type))
