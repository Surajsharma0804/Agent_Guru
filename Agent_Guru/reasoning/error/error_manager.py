"""
Error Manager for comprehensive error handling and classification.

Provides centralized error management with:
- Error classification and categorization
- Error context capture
- Structured error responses
- Error tracking and metrics
"""

import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorType(str, Enum):
    """Error type categories."""

    # Input errors
    INVALID_INPUT = "invalid_input"
    MALFORMED_INPUT = "malformed_input"
    UNSUPPORTED_INPUT = "unsupported_input"

    # Intent detection errors
    INTENT_DETECTION_FAILED = "intent_detection_failed"
    AMBIGUOUS_INTENT = "ambiguous_intent"
    UNKNOWN_INTENT = "unknown_intent"

    # Reasoning errors
    REASONING_FAILED = "reasoning_failed"
    PLAN_GENERATION_FAILED = "plan_generation_failed"
    PLAN_VALIDATION_FAILED = "plan_validation_failed"

    # Tool errors
    TOOL_NOT_FOUND = "tool_not_found"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_UNAVAILABLE = "tool_unavailable"

    # Permission errors
    PERMISSION_DENIED = "permission_denied"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CONFIRMATION_DENIED = "confirmation_denied"

    # LLM errors
    LLM_UNAVAILABLE = "llm_unavailable"
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_INVALID_RESPONSE = "llm_invalid_response"

    # System errors
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"

    # External errors
    NETWORK_ERROR = "network_error"
    EXTERNAL_API_ERROR = "external_api_error"
    EXTERNAL_API_TIMEOUT = "external_api_timeout"


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    LOW = "low"  # Minor issue, system can continue
    MEDIUM = "medium"  # Significant issue, degraded functionality
    HIGH = "high"  # Critical issue, operation failed
    CRITICAL = "critical"  # System-level failure


class ErrorContext(BaseModel):
    """Context information for an error."""

    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_id: Optional[str] = None
    input_text: Optional[str] = None
    intent_type: Optional[str] = None
    action_id: Optional[str] = None
    tool_id: Optional[str] = None
    stack_trace: Optional[str] = None
    additional_data: dict[str, Any] = Field(default_factory=dict)


class StructuredError(BaseModel):
    """Structured error with classification and context."""

    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    user_message: str  # User-friendly message
    context: ErrorContext
    recoverable: bool = True
    suggested_actions: list[str] = Field(default_factory=list)
    error_id: Optional[str] = None


class ErrorClassifier:
    """Classifier for error types and severity."""

    # Mapping of exception types to error types
    EXCEPTION_MAPPINGS = {
        ValueError: ErrorType.INVALID_INPUT,
        TypeError: ErrorType.MALFORMED_INPUT,
        KeyError: ErrorType.INTERNAL_ERROR,
        TimeoutError: ErrorType.TIMEOUT,
        ConnectionError: ErrorType.NETWORK_ERROR,
        PermissionError: ErrorType.PERMISSION_DENIED,
    }

    # Severity mappings
    SEVERITY_MAPPINGS = {
        ErrorType.INVALID_INPUT: ErrorSeverity.LOW,
        ErrorType.MALFORMED_INPUT: ErrorSeverity.LOW,
        ErrorType.UNSUPPORTED_INPUT: ErrorSeverity.MEDIUM,
        ErrorType.INTENT_DETECTION_FAILED: ErrorSeverity.MEDIUM,
        ErrorType.AMBIGUOUS_INTENT: ErrorSeverity.LOW,
        ErrorType.UNKNOWN_INTENT: ErrorSeverity.MEDIUM,
        ErrorType.REASONING_FAILED: ErrorSeverity.HIGH,
        ErrorType.PLAN_GENERATION_FAILED: ErrorSeverity.HIGH,
        ErrorType.PLAN_VALIDATION_FAILED: ErrorSeverity.MEDIUM,
        ErrorType.TOOL_NOT_FOUND: ErrorSeverity.MEDIUM,
        ErrorType.TOOL_EXECUTION_FAILED: ErrorSeverity.MEDIUM,
        ErrorType.TOOL_TIMEOUT: ErrorSeverity.MEDIUM,
        ErrorType.TOOL_UNAVAILABLE: ErrorSeverity.MEDIUM,
        ErrorType.PERMISSION_DENIED: ErrorSeverity.LOW,
        ErrorType.CONFIRMATION_REQUIRED: ErrorSeverity.LOW,
        ErrorType.CONFIRMATION_DENIED: ErrorSeverity.LOW,
        ErrorType.LLM_UNAVAILABLE: ErrorSeverity.HIGH,
        ErrorType.LLM_TIMEOUT: ErrorSeverity.MEDIUM,
        ErrorType.LLM_RATE_LIMIT: ErrorSeverity.MEDIUM,
        ErrorType.LLM_INVALID_RESPONSE: ErrorSeverity.MEDIUM,
        ErrorType.TIMEOUT: ErrorSeverity.MEDIUM,
        ErrorType.RESOURCE_EXHAUSTED: ErrorSeverity.HIGH,
        ErrorType.INTERNAL_ERROR: ErrorSeverity.CRITICAL,
        ErrorType.SERVICE_UNAVAILABLE: ErrorSeverity.HIGH,
        ErrorType.NETWORK_ERROR: ErrorSeverity.MEDIUM,
        ErrorType.EXTERNAL_API_ERROR: ErrorSeverity.MEDIUM,
        ErrorType.EXTERNAL_API_TIMEOUT: ErrorSeverity.MEDIUM,
    }

    @staticmethod
    def classify_exception(exception: Exception) -> ErrorType:
        """Classify an exception into an error type.

        Args:
            exception: Exception to classify

        Returns:
            Error type
        """
        # Check direct mapping
        exc_type = type(exception)
        if exc_type in ErrorClassifier.EXCEPTION_MAPPINGS:
            return ErrorClassifier.EXCEPTION_MAPPINGS[exc_type]

        # Check exception message for keywords
        message = str(exception).lower()

        if "timeout" in message:
            return ErrorType.TIMEOUT
        elif "permission" in message or "denied" in message:
            return ErrorType.PERMISSION_DENIED
        elif "network" in message or "connection" in message:
            return ErrorType.NETWORK_ERROR
        elif "llm" in message or "model" in message:
            return ErrorType.LLM_UNAVAILABLE
        elif "tool" in message:
            return ErrorType.TOOL_EXECUTION_FAILED
        else:
            return ErrorType.INTERNAL_ERROR

    @staticmethod
    def get_severity(error_type: ErrorType) -> ErrorSeverity:
        """Get severity for an error type.

        Args:
            error_type: Error type

        Returns:
            Error severity
        """
        return ErrorClassifier.SEVERITY_MAPPINGS.get(
            error_type, ErrorSeverity.MEDIUM
        )

    @staticmethod
    def is_recoverable(error_type: ErrorType) -> bool:
        """Check if an error type is recoverable.

        Args:
            error_type: Error type

        Returns:
            True if recoverable
        """
        # Non-recoverable errors
        non_recoverable = {
            ErrorType.INTERNAL_ERROR,
            ErrorType.RESOURCE_EXHAUSTED,
            ErrorType.PERMISSION_DENIED,
            ErrorType.CONFIRMATION_DENIED,
        }

        return error_type not in non_recoverable


class ErrorManager:
    """Manager for error handling and classification."""

    def __init__(self):
        """Initialize error manager."""
        self._error_count = 0
        self._error_history: list[StructuredError] = []

    def create_error(
        self,
        error_type: ErrorType,
        message: str,
        context: Optional[ErrorContext] = None,
        exception: Optional[Exception] = None,
    ) -> StructuredError:
        """Create a structured error.

        Args:
            error_type: Error type
            message: Technical error message
            context: Error context
            exception: Original exception (optional)

        Returns:
            Structured error
        """
        self._error_count += 1

        # Create context if not provided
        if context is None:
            context = ErrorContext()

        # Add stack trace if exception provided
        if exception:
            context.stack_trace = "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )

        # Get severity and recoverability
        severity = ErrorClassifier.get_severity(error_type)
        recoverable = ErrorClassifier.is_recoverable(error_type)

        # Generate user-friendly message
        user_message = self._generate_user_message(error_type, message)

        # Generate suggested actions
        suggested_actions = self._generate_suggested_actions(error_type)

        # Create error
        error = StructuredError(
            error_type=error_type,
            severity=severity,
            message=message,
            user_message=user_message,
            context=context,
            recoverable=recoverable,
            suggested_actions=suggested_actions,
            error_id=f"ERR-{self._error_count:06d}",
        )

        # Store in history
        self._error_history.append(error)

        # Keep only last 1000 errors
        if len(self._error_history) > 1000:
            self._error_history = self._error_history[-1000:]

        return error

    def handle_exception(
        self,
        exception: Exception,
        context: Optional[ErrorContext] = None,
    ) -> StructuredError:
        """Handle an exception and create structured error.

        Args:
            exception: Exception to handle
            context: Error context

        Returns:
            Structured error
        """
        # Classify exception
        error_type = ErrorClassifier.classify_exception(exception)

        # Create error
        return self.create_error(
            error_type=error_type,
            message=str(exception),
            context=context,
            exception=exception,
        )

    def _generate_user_message(
        self, error_type: ErrorType, technical_message: str
    ) -> str:
        """Generate user-friendly error message.

        Args:
            error_type: Error type
            technical_message: Technical error message

        Returns:
            User-friendly message
        """
        # User-friendly messages per error type
        messages = {
            ErrorType.INVALID_INPUT: "I didn't understand that. Could you rephrase?",
            ErrorType.MALFORMED_INPUT: "I couldn't process that input. Please try again.",
            ErrorType.UNSUPPORTED_INPUT: "I don't support that type of input yet.",
            ErrorType.INTENT_DETECTION_FAILED: "I'm not sure what you want me to do.",
            ErrorType.AMBIGUOUS_INTENT: "That's a bit ambiguous. Could you be more specific?",
            ErrorType.UNKNOWN_INTENT: "I don't know how to do that yet.",
            ErrorType.REASONING_FAILED: "I had trouble figuring out how to do that.",
            ErrorType.PLAN_GENERATION_FAILED: "I couldn't create a plan for that.",
            ErrorType.PLAN_VALIDATION_FAILED: "The plan I created doesn't look right.",
            ErrorType.TOOL_NOT_FOUND: "I don't have the right tool for that.",
            ErrorType.TOOL_EXECUTION_FAILED: "Something went wrong while doing that.",
            ErrorType.TOOL_TIMEOUT: "That took too long. Let me try a different approach.",
            ErrorType.TOOL_UNAVAILABLE: "That feature isn't available right now.",
            ErrorType.PERMISSION_DENIED: "I don't have permission to do that.",
            ErrorType.CONFIRMATION_REQUIRED: "I need your confirmation to do that.",
            ErrorType.CONFIRMATION_DENIED: "Okay, I won't do that.",
            ErrorType.LLM_UNAVAILABLE: "My reasoning engine is unavailable. Using fallback.",
            ErrorType.LLM_TIMEOUT: "Reasoning took too long. Using simpler approach.",
            ErrorType.LLM_RATE_LIMIT: "I'm being rate limited. Please wait a moment.",
            ErrorType.LLM_INVALID_RESPONSE: "I got a confusing response. Let me try again.",
            ErrorType.TIMEOUT: "That took too long. Please try again.",
            ErrorType.RESOURCE_EXHAUSTED: "System resources are exhausted.",
            ErrorType.INTERNAL_ERROR: "Something went wrong internally. Please try again.",
            ErrorType.SERVICE_UNAVAILABLE: "A required service is unavailable.",
            ErrorType.NETWORK_ERROR: "Network connection issue. Please check your connection.",
            ErrorType.EXTERNAL_API_ERROR: "An external service had an error.",
            ErrorType.EXTERNAL_API_TIMEOUT: "An external service timed out.",
        }

        return messages.get(error_type, "An error occurred. Please try again.")

    def _generate_suggested_actions(self, error_type: ErrorType) -> list[str]:
        """Generate suggested actions for error recovery.

        Args:
            error_type: Error type

        Returns:
            List of suggested actions
        """
        suggestions = {
            ErrorType.INVALID_INPUT: [
                "Try rephrasing your request",
                "Be more specific about what you want",
            ],
            ErrorType.AMBIGUOUS_INTENT: [
                "Clarify what you want me to do",
                "Provide more details",
            ],
            ErrorType.UNKNOWN_INTENT: [
                "Try a different command",
                "Ask what I can do",
            ],
            ErrorType.TOOL_EXECUTION_FAILED: [
                "Try again",
                "Try a different approach",
            ],
            ErrorType.TOOL_TIMEOUT: [
                "Try again with a simpler request",
                "Break it into smaller steps",
            ],
            ErrorType.PERMISSION_DENIED: [
                "Grant the required permission",
                "Try a different action",
            ],
            ErrorType.LLM_UNAVAILABLE: [
                "Wait a moment and try again",
                "Use simpler commands",
            ],
            ErrorType.NETWORK_ERROR: [
                "Check your internet connection",
                "Try again in a moment",
            ],
        }

        return suggestions.get(error_type, ["Try again", "Contact support if issue persists"])

    def get_error_statistics(self) -> dict[str, Any]:
        """Get error statistics.

        Returns:
            Statistics dictionary
        """
        if not self._error_history:
            return {
                "total_errors": 0,
                "by_type": {},
                "by_severity": {},
            }

        # Count by type
        by_type: dict[str, int] = {}
        for error in self._error_history:
            error_type = error.error_type.value
            by_type[error_type] = by_type.get(error_type, 0) + 1

        # Count by severity
        by_severity: dict[str, int] = {}
        for error in self._error_history:
            severity = error.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total_errors": len(self._error_history),
            "by_type": by_type,
            "by_severity": by_severity,
        }


# Global error manager instance
_global_manager: Optional[ErrorManager] = None


def get_error_manager() -> ErrorManager:
    """Get the global error manager instance.

    Returns:
        Global ErrorManager instance
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = ErrorManager()
    return _global_manager
