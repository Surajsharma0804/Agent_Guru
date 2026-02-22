"""
Error Response Generator

Generates user-friendly error responses with:
- Clear, non-technical error messages
- Suggested actions for recoverable errors
- Alternative options when available
- Context-aware guidance

Performance Requirements:
- Time Complexity: O(1) - dictionary lookup
- Space Complexity: O(1) - fixed error message registry
- Latency: <50ms (95th percentile)

Design:
- Error type to message mapping
- Recoverable errors include suggested actions
- Context-aware alternative suggestions
- No technical jargon or stack traces
"""

from dataclasses import dataclass
from typing import Any, Optional

from Agent_Guru.reasoning.config.logging import get_logger
from Agent_Guru.reasoning.models.error import Error, ErrorType, FallbackStrategy
from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.result import Response, ResponseModality

logger = get_logger(__name__)


@dataclass
class ErrorResponseTemplate:
    """
    Template for error responses.

    Attributes:
        user_message: User-friendly error message (no technical jargon)
        voice_message: Concise version for voice output
        suggested_actions: List of suggested actions for user
        alternatives: List of alternative approaches
        requires_clarification: Whether error needs user clarification
    """

    user_message: str
    voice_message: str
    suggested_actions: list[str]
    alternatives: list[str]
    requires_clarification: bool = False


class ErrorResponseGenerator:
    """
    Generate user-friendly error responses.

    Time Complexity: O(1) - dictionary lookup
    Space Complexity: O(1) - fixed error message registry
    Latency Target: <50ms (95th percentile)

    Example:
        >>> generator = ErrorResponseGenerator()
        >>> error = Error(
        ...     error_code="ERR_001",
        ...     error_type=ErrorType.PERMISSION_DENIED,
        ...     message="Permission denied",
        ...     recoverable=True
        ... )
        >>> response = generator.generate_error_response(
        ...     error,
        ...     ResponseModality.VOICE
        ... )
        >>> print(response.text)
        "I don't have permission to do that"
    """

    def __init__(self) -> None:
        """Initialize error response generator with templates."""
        self._error_templates: dict[ErrorType, ErrorResponseTemplate] = {}
        self._load_error_templates()
        logger.info(
            "ErrorResponseGenerator initialized",
            extra={"template_count": len(self._error_templates)},
        )

    def generate_error_response(
        self,
        error: Error,
        modality: ResponseModality,
        intent: Optional[Intent] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> Response:
        """
        Generate user-friendly error response.

        Time Complexity: O(1) - dictionary lookup
        Space Complexity: O(1) - fixed response size

        Args:
            error: Error object to generate response for
            modality: Response modality (VOICE, TEXT, BOTH)
            intent: Optional original intent for context
            context: Optional additional context

        Returns:
            Response object with user-friendly error message
        """
        # Get error template
        template = self._get_error_template(error.error_type)

        # Select message based on modality
        if modality == ResponseModality.VOICE:
            message = template.voice_message
        else:
            message = template.user_message

        # Add context-specific details if available
        message = self._add_context_details(message, error, intent, context)

        # Generate suggestions based on error recoverability
        suggestions = self._generate_error_suggestions(error, template, intent, context)

        # Create response
        response = Response(
            text=message,
            modality=modality,
            metadata={
                "error_type": error.error_type.value,
                "error_code": error.error_code,
                "recoverable": error.recoverable,
                "generation_method": "error_response",
                "requires_clarification": template.requires_clarification,
            },
            suggestions=suggestions,
        )

        logger.info(
            "Error response generated",
            extra={
                "error_type": error.error_type.value,
                "modality": modality.value,
                "recoverable": error.recoverable,
                "suggestion_count": len(suggestions),
            },
        )

        return response

    def _get_error_template(self, error_type: ErrorType) -> ErrorResponseTemplate:
        """
        Get error template for error type.

        Time Complexity: O(1) - dictionary lookup

        Args:
            error_type: Type of error

        Returns:
            Error response template
        """
        return self._error_templates.get(
            error_type, self._error_templates[ErrorType.SYSTEM_ERROR]  # Default fallback
        )

    def _add_context_details(
        self,
        message: str,
        error: Error,
        intent: Optional[Intent],
        context: Optional[dict[str, Any]],
    ) -> str:
        """
        Add context-specific details to error message.

        Args:
            message: Base error message
            error: Error object
            intent: Optional intent
            context: Optional context

        Returns:
            Enhanced error message with context
        """
        # Add intent-specific context
        if intent and error.error_type == ErrorType.NO_TOOL_FOUND:
            intent_type_str = str(intent.intent_type)
            if "timer" in intent_type_str.lower():
                message += " Timer functionality is not available right now."
            elif "weather" in intent_type_str.lower():
                message += " Weather information is not available right now."
            elif "message" in intent_type_str.lower():
                message += " Messaging is not available right now."

        # Add error details if helpful (non-technical)
        if error.details and error.error_type == ErrorType.INVALID_PARAMETERS:
            missing = error.details.get("missing_parameters", [])
            if missing:
                message += f" I need more information: {', '.join(missing)}."

        return message

    def _generate_error_suggestions(
        self,
        error: Error,
        template: ErrorResponseTemplate,
        intent: Optional[Intent],
        context: Optional[dict[str, Any]],
    ) -> list[str]:
        """
        Generate suggestions for error recovery.

        Args:
            error: Error object
            template: Error template
            intent: Optional intent
            context: Optional context

        Returns:
            List of suggested actions
        """
        suggestions = []

        # Add template suggestions
        if error.recoverable:
            suggestions.extend(template.suggested_actions)

        # Add alternatives
        suggestions.extend(template.alternatives)

        # Add intent-specific alternatives
        if intent:
            intent_alternatives = self._get_intent_alternatives(intent, error)
            suggestions.extend(intent_alternatives)

        # Add fallback-specific suggestions
        if error.suggested_fallback:
            fallback_suggestions = self._get_fallback_suggestions(error.suggested_fallback)
            suggestions.extend(fallback_suggestions)

        # Limit to 3 suggestions
        return suggestions[:3]

    def _get_intent_alternatives(self, intent: Intent, error: Error) -> list[str]:
        """
        Get alternative suggestions based on intent.

        Args:
            intent: User intent
            error: Error that occurred

        Returns:
            List of alternative suggestions
        """
        alternatives = []
        intent_type_str = str(intent.intent_type)

        # Timer alternatives
        if "timer" in intent_type_str.lower():
            if error.error_type == ErrorType.TOOL_UNAVAILABLE:
                alternatives.append("Use phone's built-in timer")
                alternatives.append("Set a reminder instead")

        # Weather alternatives
        elif "weather" in intent_type_str.lower():
            if error.error_type == ErrorType.NETWORK_ERROR:
                alternatives.append("Check weather app")
                alternatives.append("Try again when online")

        # Messaging alternatives
        elif "message" in intent_type_str.lower():
            if error.error_type == ErrorType.PERMISSION_DENIED:
                alternatives.append("Grant messaging permission")
                alternatives.append("Open messaging app manually")

        # Music alternatives
        elif "music" in intent_type_str.lower():
            if error.error_type == ErrorType.TOOL_UNAVAILABLE:
                alternatives.append("Open music app")
                alternatives.append("Try a different music service")

        return alternatives

    def _get_fallback_suggestions(self, fallback_strategy: FallbackStrategy) -> list[str]:
        """
        Get suggestions based on fallback strategy.

        Args:
            fallback_strategy: Suggested fallback strategy

        Returns:
            List of suggestions
        """
        fallback_suggestions = {
            FallbackStrategy.RETRY_WITH_BACKOFF: ["Try again in a moment"],
            FallbackStrategy.ALTERNATIVE_TOOL: ["Try a different approach"],
            FallbackStrategy.SIMPLIFIED_REQUEST: ["Try a simpler request"],
            FallbackStrategy.USER_NOTIFICATION: ["Check system settings"],
            FallbackStrategy.GRACEFUL_DEGRADATION: ["Use basic features"],
        }

        return fallback_suggestions.get(fallback_strategy, [])

    def _load_error_templates(self) -> None:
        """
        Load error response templates.

        Time Complexity: O(1) - fixed number of templates
        """
        # Input Errors
        self._error_templates[ErrorType.INVALID_INPUT] = ErrorResponseTemplate(
            user_message="I didn't understand that. Could you rephrase your request?",
            voice_message="I didn't get that. Can you rephrase?",
            suggested_actions=["Rephrase your request", "Be more specific"],
            alternatives=["Try a different command", "Ask for help"],
            requires_clarification=True,
        )

        self._error_templates[ErrorType.MALFORMED_INPUT] = ErrorResponseTemplate(
            user_message="I couldn't process that input. Please try again.",
            voice_message="Input error. Try again?",
            suggested_actions=["Try again", "Check your input"],
            alternatives=["Use a different format"],
            requires_clarification=True,
        )

        # Intent Detection Errors
        self._error_templates[ErrorType.INTENT_DETECTION_FAILED] = ErrorResponseTemplate(
            user_message="I'm not sure what you want me to do. Could you be more specific?",
            voice_message="I'm not sure what you mean",
            suggested_actions=["Be more specific", "Try a different phrase"],
            alternatives=["Ask for available commands", "Try a simpler request"],
            requires_clarification=True,
        )

        self._error_templates[ErrorType.AMBIGUOUS_INTENT] = ErrorResponseTemplate(
            user_message="I'm not sure which action you want. Could you clarify?",
            voice_message="Which did you mean?",
            suggested_actions=["Clarify your request", "Choose one option"],
            alternatives=["Be more specific", "Try again"],
            requires_clarification=True,
        )

        self._error_templates[ErrorType.UNKNOWN_INTENT] = ErrorResponseTemplate(
            user_message="I don't know how to help with that yet.",
            voice_message="I can't do that yet",
            suggested_actions=["Try a different request", "Ask what I can do"],
            alternatives=["Check available features", "Try something else"],
            requires_clarification=False,
        )

        # Reasoning Errors
        self._error_templates[ErrorType.REASONING_FAILED] = ErrorResponseTemplate(
            user_message="I had trouble figuring out how to do that. Could you simplify your request?",
            voice_message="That's too complex. Try simpler?",
            suggested_actions=["Simplify your request", "Break into smaller steps"],
            alternatives=["Try a different approach", "Ask for help"],
            requires_clarification=True,
        )

        self._error_templates[ErrorType.REASONING_TIMEOUT] = ErrorResponseTemplate(
            user_message="That's taking longer than expected. Let me try a simpler approach.",
            voice_message="That's taking too long",
            suggested_actions=["Try again", "Simplify request"],
            alternatives=["Wait a moment", "Try later"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.INVALID_REASONING_PLAN] = ErrorResponseTemplate(
            user_message="I couldn't figure out how to complete that task. Could you rephrase?",
            voice_message="I can't figure that out",
            suggested_actions=["Rephrase request", "Break into steps"],
            alternatives=["Try a different approach", "Simplify"],
            requires_clarification=True,
        )

        # Tool Selection Errors
        self._error_templates[ErrorType.NO_TOOL_FOUND] = ErrorResponseTemplate(
            user_message="I don't have the capability to do that yet.",
            voice_message="I can't do that yet",
            suggested_actions=["Try a different request", "Check available features"],
            alternatives=["Use a different app", "Try manually"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.TOOL_UNAVAILABLE] = ErrorResponseTemplate(
            user_message="That feature is currently unavailable. Please try again later.",
            voice_message="That's not available right now",
            suggested_actions=["Try again later", "Use alternative"],
            alternatives=["Check system status", "Try different feature"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.INVALID_PARAMETERS] = ErrorResponseTemplate(
            user_message="I need more information to complete that request.",
            voice_message="I need more details",
            suggested_actions=["Provide missing information", "Be more specific"],
            alternatives=["Try with more details", "Rephrase"],
            requires_clarification=True,
        )

        # Safety Errors
        self._error_templates[ErrorType.PERMISSION_DENIED] = ErrorResponseTemplate(
            user_message="I don't have permission to do that. Please grant the necessary permissions.",
            voice_message="Permission denied",
            suggested_actions=["Grant permission in settings", "Check permissions"],
            alternatives=["Do it manually", "Try different approach"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.SENSITIVE_ACTION_BLOCKED] = ErrorResponseTemplate(
            user_message="That action requires confirmation for safety. Would you like to proceed?",
            voice_message="Confirm this action?",
            suggested_actions=["Confirm action", "Cancel"],
            alternatives=["Review details first", "Try safer alternative"],
            requires_clarification=True,
        )

        self._error_templates[ErrorType.CONFIRMATION_REQUIRED] = ErrorResponseTemplate(
            user_message="This action needs your confirmation. Please confirm to proceed.",
            voice_message="Confirm to proceed?",
            suggested_actions=["Confirm", "Cancel"],
            alternatives=["Review details", "Try different action"],
            requires_clarification=True,
        )

        # Execution Errors
        self._error_templates[ErrorType.EXECUTION_FAILED] = ErrorResponseTemplate(
            user_message="I couldn't complete that action. Please try again.",
            voice_message="That didn't work. Try again?",
            suggested_actions=["Try again", "Check if it's possible"],
            alternatives=["Try different approach", "Do it manually"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.EXECUTION_TIMEOUT] = ErrorResponseTemplate(
            user_message="That's taking longer than expected. Would you like to wait or try again?",
            voice_message="That's taking too long",
            suggested_actions=["Wait a bit longer", "Try again"],
            alternatives=["Cancel and retry", "Try simpler version"],
            requires_clarification=True,
        )

        self._error_templates[ErrorType.TOOL_ERROR] = ErrorResponseTemplate(
            user_message="There was a problem with that feature. Please try again.",
            voice_message="Feature error. Try again?",
            suggested_actions=["Try again", "Report issue"],
            alternatives=["Use alternative feature", "Try later"],
            requires_clarification=False,
        )

        # LLM Errors
        self._error_templates[ErrorType.LLM_UNAVAILABLE] = ErrorResponseTemplate(
            user_message="I'm having trouble thinking right now. Please try again in a moment.",
            voice_message="I'm having trouble. Try again?",
            suggested_actions=["Try again in a moment", "Try simpler request"],
            alternatives=["Use basic commands", "Try later"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.LLM_TIMEOUT] = ErrorResponseTemplate(
            user_message="I'm thinking too slowly. Let me try a faster approach.",
            voice_message="Thinking too slow. Trying faster way",
            suggested_actions=["Wait a moment", "Try simpler request"],
            alternatives=["Use basic commands", "Try again"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.LLM_RATE_LIMIT] = ErrorResponseTemplate(
            user_message="I'm getting too many requests right now. Please wait a moment and try again.",
            voice_message="Too many requests. Wait a moment",
            suggested_actions=["Wait a moment", "Try again soon"],
            alternatives=["Use basic commands", "Try later"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.LLM_INVALID_RESPONSE] = ErrorResponseTemplate(
            user_message="I got confused. Let me try that again.",
            voice_message="I got confused. Trying again",
            suggested_actions=["Trying again automatically", "Simplify if it fails"],
            alternatives=["Use basic commands", "Rephrase"],
            requires_clarification=False,
        )

        # System Errors
        self._error_templates[ErrorType.SYSTEM_ERROR] = ErrorResponseTemplate(
            user_message="Something went wrong. Please try again.",
            voice_message="Something went wrong",
            suggested_actions=["Try again", "Restart if problem persists"],
            alternatives=["Report issue", "Try later"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.RESOURCE_EXHAUSTED] = ErrorResponseTemplate(
            user_message="System resources are low. Please try a simpler request or wait a moment.",
            voice_message="Resources low. Try simpler request",
            suggested_actions=["Try simpler request", "Wait a moment"],
            alternatives=["Close other apps", "Try later"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.CONFIGURATION_ERROR] = ErrorResponseTemplate(
            user_message="There's a configuration issue. Please check your settings.",
            voice_message="Configuration error",
            suggested_actions=["Check settings", "Reset to defaults"],
            alternatives=["Contact support", "Reinstall"],
            requires_clarification=False,
        )

        # Network Errors
        self._error_templates[ErrorType.NETWORK_ERROR] = ErrorResponseTemplate(
            user_message="Network connection failed. Please check your connection and try again.",
            voice_message="Network error. Check connection",
            suggested_actions=["Check internet connection", "Try again when online"],
            alternatives=["Use offline features", "Try later"],
            requires_clarification=False,
        )

        self._error_templates[ErrorType.SERVICE_UNAVAILABLE] = ErrorResponseTemplate(
            user_message="That service is currently unavailable. Please try again later.",
            voice_message="Service unavailable",
            suggested_actions=["Try again later", "Check service status"],
            alternatives=["Use alternative service", "Try offline"],
            requires_clarification=False,
        )
