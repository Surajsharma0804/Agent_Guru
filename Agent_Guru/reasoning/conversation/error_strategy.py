"""Error response strategies for conversation.

This module implements:
- Error classification (user error, system error, external error)
- Response templates per error type
- Actionable suggestions for recoverable errors
- Empathetic language for user errors

Requirements: 19.5, 26.4
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from Agent_Guru.reasoning.models.error import Error, ErrorType


class ErrorCategory(Enum):
    """High-level error categories."""

    USER_ERROR = "user_error"  # User made a mistake
    SYSTEM_ERROR = "system_error"  # Internal system error
    EXTERNAL_ERROR = "external_error"  # External service/resource error


@dataclass
class ErrorResponse:
    """Structured error response."""

    message: str
    suggestions: list[str]
    is_recoverable: bool
    category: ErrorCategory
    empathy_level: float  # 0.0 to 1.0


class ErrorClassifier:
    """Classifies errors into categories."""

    # Mapping of ErrorType to ErrorCategory
    ERROR_CATEGORY_MAP = {
        # User errors
        ErrorType.INVALID_INPUT: ErrorCategory.USER_ERROR,
        ErrorType.MALFORMED_INPUT: ErrorCategory.USER_ERROR,
        ErrorType.AMBIGUOUS_INTENT: ErrorCategory.USER_ERROR,
        ErrorType.UNKNOWN_INTENT: ErrorCategory.USER_ERROR,
        ErrorType.INVALID_PARAMETERS: ErrorCategory.USER_ERROR,
        # System errors
        ErrorType.SYSTEM_ERROR: ErrorCategory.SYSTEM_ERROR,
        ErrorType.LLM_UNAVAILABLE: ErrorCategory.SYSTEM_ERROR,
        ErrorType.NO_TOOL_FOUND: ErrorCategory.SYSTEM_ERROR,
        ErrorType.REASONING_FAILED: ErrorCategory.SYSTEM_ERROR,
        ErrorType.CONFIGURATION_ERROR: ErrorCategory.SYSTEM_ERROR,
        # External errors
        ErrorType.NETWORK_ERROR: ErrorCategory.EXTERNAL_ERROR,
        ErrorType.TOOL_UNAVAILABLE: ErrorCategory.EXTERNAL_ERROR,
        ErrorType.EXECUTION_TIMEOUT: ErrorCategory.EXTERNAL_ERROR,
        ErrorType.EXECUTION_FAILED: ErrorCategory.EXTERNAL_ERROR,
        ErrorType.SERVICE_UNAVAILABLE: ErrorCategory.EXTERNAL_ERROR,
        # Permission errors (user error)
        ErrorType.PERMISSION_DENIED: ErrorCategory.USER_ERROR,
        ErrorType.CONFIRMATION_REQUIRED: ErrorCategory.USER_ERROR,
        ErrorType.SENSITIVE_ACTION_BLOCKED: ErrorCategory.USER_ERROR,
    }

    @staticmethod
    def classify_error(error: Error) -> ErrorCategory:
        """Classify error into high-level category.

        Args:
            error: The error to classify

        Returns:
            Error category

        """
        # Try to map from error type
        if error.error_type in ErrorClassifier.ERROR_CATEGORY_MAP:
            return ErrorClassifier.ERROR_CATEGORY_MAP[error.error_type]

        # Default to system error
        return ErrorCategory.SYSTEM_ERROR

    @staticmethod
    def is_recoverable(error: Error) -> bool:
        """Determine if error is recoverable.

        Args:
            error: The error

        Returns:
            True if recoverable

        """
        # Check error's own recoverable flag
        if hasattr(error, "recoverable"):
            return error.recoverable

        # Recoverable error types
        recoverable_types = {
            ErrorType.AMBIGUOUS_INTENT,
            ErrorType.INVALID_PARAMETERS,
            ErrorType.EXECUTION_TIMEOUT,
            ErrorType.NETWORK_ERROR,
            ErrorType.TOOL_UNAVAILABLE,
            ErrorType.CONFIRMATION_REQUIRED,
            ErrorType.SERVICE_UNAVAILABLE,
        }

        return error.error_type in recoverable_types

    @staticmethod
    def get_empathy_level(category: ErrorCategory) -> float:
        """Get appropriate empathy level for error category.

        Args:
            category: Error category

        Returns:
            Empathy level (0.0 to 1.0)

        """
        if category == ErrorCategory.USER_ERROR:
            return 0.8  # High empathy for user errors
        if category == ErrorCategory.EXTERNAL_ERROR:
            return 0.6  # Medium empathy for external errors
        return 0.4  # Lower empathy for system errors


class ErrorResponseStrategy:
    """Generates appropriate error responses."""

    # Templates by error type and category
    TEMPLATES = {
        # User error templates (empathetic)
        (ErrorType.INVALID_INPUT, ErrorCategory.USER_ERROR): [
            "I didn't quite understand that. {suggestion}",
            "That doesn't seem right. {suggestion}",
        ],
        (ErrorType.AMBIGUOUS_INTENT, ErrorCategory.USER_ERROR): [
            "I'm not sure what you mean. {suggestion}",
            "Could you clarify? {suggestion}",
        ],
        (ErrorType.INVALID_PARAMETERS, ErrorCategory.USER_ERROR): [
            "I need a bit more information. {suggestion}",
            "Could you tell me {missing}?",
        ],
        (ErrorType.PERMISSION_DENIED, ErrorCategory.USER_ERROR): [
            "I don't have permission to do that. {suggestion}",
            "You'll need to grant permission first. {suggestion}",
        ],
        # System error templates (apologetic)
        (ErrorType.SYSTEM_ERROR, ErrorCategory.SYSTEM_ERROR): [
            "Sorry, something went wrong on my end. {suggestion}",
            "I encountered an error. {suggestion}",
        ],
        (ErrorType.LLM_UNAVAILABLE, ErrorCategory.SYSTEM_ERROR): [
            "My reasoning system is temporarily unavailable. {suggestion}",
            "I'm having trouble processing that right now. {suggestion}",
        ],
        (ErrorType.NO_TOOL_FOUND, ErrorCategory.SYSTEM_ERROR): [
            "I don't have the capability to do that. {suggestion}",
            "That feature isn't available. {suggestion}",
        ],
        # External error templates (informative)
        (ErrorType.NETWORK_ERROR, ErrorCategory.EXTERNAL_ERROR): [
            "I'm having trouble connecting. {suggestion}",
            "Network connection failed. {suggestion}",
        ],
        (ErrorType.TOOL_UNAVAILABLE, ErrorCategory.EXTERNAL_ERROR): [
            "That service is currently unavailable. {suggestion}",
            "{tool} isn't responding. {suggestion}",
        ],
        (ErrorType.EXECUTION_TIMEOUT, ErrorCategory.EXTERNAL_ERROR): [
            "That's taking longer than expected. {suggestion}",
            "The operation timed out. {suggestion}",
        ],
        (ErrorType.EXECUTION_FAILED, ErrorCategory.EXTERNAL_ERROR): [
            "I couldn't complete that action. {suggestion}",
            "The operation failed. {suggestion}",
        ],
    }

    # Suggestions by error type
    SUGGESTIONS = {
        ErrorType.INVALID_INPUT: [
            "Could you rephrase that?",
            "Try saying it differently.",
        ],
        ErrorType.AMBIGUOUS_INTENT: [
            "Could you be more specific?",
            "What exactly would you like me to do?",
        ],
        ErrorType.INVALID_PARAMETERS: [
            "Please provide the missing details.",
            "I need more information to proceed.",
        ],
        ErrorType.PERMISSION_DENIED: [
            "You can grant permission in settings.",
            "Would you like to enable this permission?",
        ],
        ErrorType.SYSTEM_ERROR: [
            "Please try again in a moment.",
            "Let me know if this keeps happening.",
        ],
        ErrorType.LLM_UNAVAILABLE: [
            "I'll use a simpler approach.",
            "Try again in a moment.",
        ],
        ErrorType.NO_TOOL_FOUND: [
            "Here's what I can do instead: {alternatives}",
            "Would you like to try something else?",
        ],
        ErrorType.NETWORK_ERROR: [
            "Check your internet connection.",
            "I'll try again automatically.",
        ],
        ErrorType.TOOL_UNAVAILABLE: [
            "I'll try again in a moment.",
            "Would you like to try an alternative?",
        ],
        ErrorType.EXECUTION_TIMEOUT: [
            "I can continue in the background and notify you.",
            "Would you like me to try again?",
        ],
        ErrorType.EXECUTION_FAILED: [
            "Here's what went wrong: {details}",
            "Would you like to try again?",
        ],
    }

    def __init__(self) -> None:
        """Initialize error response strategy."""
        self.classifier = ErrorClassifier()

    def generate_error_response(
        self,
        error: Error,
        context: dict[str, Any] | None = None,
    ) -> ErrorResponse:
        """Generate appropriate error response.

        Args:
            error: The error
            context: Optional context information

        Returns:
            ErrorResponse with message and suggestions

        """
        # Classify error
        category = self.classifier.classify_error(error)
        is_recoverable = self.classifier.is_recoverable(error)
        empathy_level = self.classifier.get_empathy_level(category)

        # Generate message
        message = self._generate_message(error, category, context)

        # Generate suggestions
        suggestions = self._generate_suggestions(error, is_recoverable, context)

        return ErrorResponse(
            message=message,
            suggestions=suggestions,
            is_recoverable=is_recoverable,
            category=category,
            empathy_level=empathy_level,
        )

    def _generate_message(
        self,
        error: Error,
        category: ErrorCategory,
        context: dict[str, Any] | None,
    ) -> str:
        """Generate error message.

        Args:
            error: The error
            category: Error category
            context: Optional context

        Returns:
            Error message string

        """
        # Get template
        template_key = (error.error_type, category)
        templates = self.TEMPLATES.get(template_key, ["An error occurred. {suggestion}"])
        template = templates[0]

        # Get suggestion text
        suggestion = self._get_first_suggestion(error, context)

        # Format template
        try:
            message = template.format(
                suggestion=suggestion,
                missing=self._extract_missing(error),
                tool=self._extract_tool(error),
                details=error.message,
            )
        except KeyError:
            # Fallback
            message = f"{error.message} {suggestion}"

        return message

    def _generate_suggestions(
        self,
        error: Error,
        is_recoverable: bool,
        context: dict[str, Any] | None,
    ) -> list[str]:
        """Generate actionable suggestions.

        Args:
            error: The error
            is_recoverable: Whether error is recoverable
            context: Optional context

        Returns:
            List of suggestions

        """
        if not is_recoverable:
            return []

        # Get suggestions for error type
        suggestions = self.SUGGESTIONS.get(error.error_type, [])

        # Format suggestions with context
        formatted = []
        for suggestion in suggestions:
            try:
                formatted_suggestion = suggestion.format(
                    alternatives=self._get_alternatives(context),
                    details=error.message,
                )
                formatted.append(formatted_suggestion)
            except KeyError:
                formatted.append(suggestion)

        return formatted

    def _get_first_suggestion(self, error: Error, context: dict[str, Any] | None) -> str:
        """Get first suggestion for inline use.

        Args:
            error: The error
            context: Optional context

        Returns:
            First suggestion string

        """
        suggestions = self._generate_suggestions(error, True, context)
        return suggestions[0] if suggestions else "Please try again."

    def _extract_missing(self, error: Error) -> str:
        """Extract missing entity description from error."""
        if hasattr(error, "details") and "missing_entity" in error.details:
            return error.details["missing_entity"]
        return "more information"

    def _extract_tool(self, error: Error) -> str:
        """Extract tool name from error."""
        if hasattr(error, "details") and "tool_id" in error.details:
            return error.details["tool_id"]
        return "the service"

    def _get_alternatives(self, context: dict[str, Any] | None) -> str:
        """Get alternative actions from context."""
        if context and "alternatives" in context:
            alternatives = context["alternatives"]
            if alternatives:
                return ", ".join(alternatives[:3])
        return "other options"

    def adapt_for_tone(
        self,
        response: ErrorResponse,
        empathy_multiplier: float = 1.0,
    ) -> ErrorResponse:
        """Adapt error response for tone preferences.

        Args:
            response: Original error response
            empathy_multiplier: Multiplier for empathy level

        Returns:
            Adapted error response

        """
        # Adjust empathy level
        adjusted_empathy = min(1.0, response.empathy_level * empathy_multiplier)

        # Modify message based on empathy
        message = response.message
        if adjusted_empathy > 0.7:  # noqa: PLR2004 - Threshold value

            # Add empathetic prefix
            if not message.startswith(("Sorry", "I apologize")):
                message = f"I'm sorry, {message[0].lower()}{message[1:]}"
        elif adjusted_empathy < 0.3:  # noqa: PLR2004 - Threshold value

            # Remove empathetic language
            message = message.replace("Sorry, ", "").replace("I'm sorry, ", "")

        return ErrorResponse(
            message=message,
            suggestions=response.suggestions,
            is_recoverable=response.is_recoverable,
            category=response.category,
            empathy_level=adjusted_empathy,
        )
