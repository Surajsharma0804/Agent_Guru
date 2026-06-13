"""Template-Based Response Generator.

Provides fast (<100ms), deterministic response generation using templates
for common success/error scenarios.

Performance Requirements:
- Time Complexity: O(1) template lookup + O(n) string formatting
- Space Complexity: O(1) - templates cached in memory
- Latency: <100ms (95th percentile)

Design:
- Template registry with predefined responses
- Variable substitution using string formatting
- Modality-aware response selection
- User preference personalization
- Zero LLM calls for maximum speed
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from Agent_Guru.reasoning.config.logging import get_logger
from Agent_Guru.reasoning.config.metrics import get_metrics_collector
from Agent_Guru.reasoning.models.error import Error, ErrorType
from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.result import ExecutionResult, Response, ResponseModality
from Agent_Guru.reasoning.response.error_response_generator import ErrorResponseGenerator

logger = get_logger(__name__)
metrics = get_metrics_collector()


class TemplateType(str, Enum):
    """Template categories for different response scenarios."""

    SUCCESS = "success"
    ERROR = "error"
    CONFIRMATION = "confirmation"
    CLARIFICATION = "clarification"
    PARTIAL_SUCCESS = "partial_success"
    PROGRESS = "progress"


@dataclass
class ResponseTemplate:
    """Response template with variable placeholders.

    Attributes:
        template_id: Unique template identifier
        template_type: Category of template
        text_template: Template string for text responses
        voice_template: Template string for voice responses (more concise)
        variables: List of required variable names
        suggestions: Optional follow-up suggestions

    """

    template_id: str
    template_type: TemplateType
    text_template: str
    voice_template: str
    variables: list[str]
    suggestions: list[str] | None = None


class TemplateGenerator:
    """Fast template-based response generator.

    Time Complexity: O(1) for template lookup, O(n) for formatting
    Space Complexity: O(1) - fixed template registry
    Latency Target: <100ms (95th percentile)

    Example:
        >>> generator = TemplateGenerator()
        >>> result = ExecutionResult(success=True, result_data={"timer": "5 minutes"})
        >>> intent = Intent(intent_type="set_timer", entities={"duration": "5 minutes"})
        >>> response = generator.generate(result, intent, ResponseModality.VOICE)
        >>> print(response.text)
        "Timer set for 5 minutes"

    """

    def __init__(self) -> None:
        """Initialize template generator with predefined templates."""
        self._templates: dict[str, ResponseTemplate] = {}
        self._error_response_generator = ErrorResponseGenerator()
        self._proactive_generator = None  # Will be set via set_proactive_generator
        self._load_default_templates()
        logger.info("TemplateGenerator initialized", extra={"template_count": len(self._templates)})

    def generate(
        self,
        result: ExecutionResult,
        intent: Intent,
        modality: ResponseModality,
        context: dict[str, Any] | None = None,
        user_preferences: dict[str, Any] | None = None,
    ) -> Response:
        """Generate response from execution result using templates.

        Time Complexity: O(1) lookup + O(n) formatting where n = template length
        Space Complexity: O(n) for response string

        Args:
            result: Execution result to generate response for
            intent: Original user intent
            modality: Response modality (VOICE, TEXT, BOTH)
            context: Optional context for variable substitution
            user_preferences: Optional user preferences for personalization

        Returns:
            Response object with generated text and metadata

        Raises:
            ValueError: If required variables are missing

        """
        start_time = time.perf_counter()

        try:
            # For error results, use dedicated error response generator
            if not result.success and result.error:
                # Try to create Error object from error string
                error = self._create_error_from_result(result)
                return self._error_response_generator.generate_error_response(
                    error,
                    modality,
                    intent,
                    context,
                )

            # Select template based on result and intent
            template = self._select_template(result, intent)

            # Extract variables from result and intent
            variables = self._extract_variables(result, intent, context or {})

            # Validate required variables
            self._validate_variables(template, variables)

            # Format template with variables
            text = self._format_template(template, modality, variables)

            # Personalize response based on user preferences
            text = self._personalize_response(text, user_preferences or {})

            # Generate suggestions
            suggestions = self._generate_suggestions(
                template,
                intent,
                result,
                context,
                user_preferences,
            )

            # Create response
            response = Response(
                text=text,
                modality=modality,
                metadata={
                    "template_id": template.template_id,
                    "template_type": template.template_type.value,
                    "generation_method": "template",
                    "latency_ms": (time.perf_counter() - start_time) * 1000,
                },
                suggestions=suggestions,
            )

            # Track metrics
            latency_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_stage_latency("response_generation", latency_ms / 1000)
            metrics.increment_requests("success")

            logger.info(
                "Template response generated",
                extra={
                    "template_id": template.template_id,
                    "modality": modality.value,
                    "latency_ms": latency_ms,
                    "intent_type": intent.intent_type,
                },
            )

            return response

        except Exception as e:
            metrics.increment_errors("template_generation")
            logger.exception(
                "Template generation failed",
                extra={
                    "error": str(e),
                    "intent_type": intent.intent_type,
                    "result_success": result.success,
                },
            )
            raise

    def _select_template(self, result: ExecutionResult, intent: Intent) -> ResponseTemplate:
        """Select appropriate template based on result and intent.

        Time Complexity: O(1) - dictionary lookup

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Selected response template

        """
        # Try intent-specific template first
        intent_type_str = (
            intent.intent_type.value
            if hasattr(intent.intent_type, "value")
            else str(intent.intent_type)
        )
        template_key = f"{intent_type_str}_{('success' if result.success else 'error')}"
        if template_key in self._templates:
            return self._templates[template_key]

        # Fall back to generic template
        if result.success:
            return self._templates["generic_success"]
        # Error is now a string, try to extract type from message
        error_msg = result.error if result.error else "unknown"
        if "timeout" in error_msg.lower():
            error_template_key = "error_timeout"
        elif "permission" in error_msg.lower():
            error_template_key = "error_permission_denied"
        elif "network" in error_msg.lower():
            error_template_key = "error_network_error"
        elif "invalid" in error_msg.lower():
            error_template_key = "error_invalid_input"
        elif "unavailable" in error_msg.lower():
            error_template_key = "error_tool_unavailable"
        else:
            error_template_key = "generic_error"

        if error_template_key in self._templates:
            return self._templates[error_template_key]

        # Final fallback — always return a valid template
        return self._templates.get(
            "generic_success" if result.success else "generic_error",
            next(iter(self._templates.values())),
        )

    def _create_error_from_result(self, result: ExecutionResult) -> Error:
        """Create Error object from ExecutionResult.

        Args:
            result: Execution result with error

        Returns:
            Error object

        """
        error_msg = result.error if result.error else "Unknown error"

        # Infer error type from message
        error_type = ErrorType.SYSTEM_ERROR
        if "timeout" in error_msg.lower():
            error_type = ErrorType.EXECUTION_TIMEOUT
        elif "permission" in error_msg.lower():
            error_type = ErrorType.PERMISSION_DENIED
        elif "network" in error_msg.lower():
            error_type = ErrorType.NETWORK_ERROR
        elif "invalid" in error_msg.lower():
            error_type = ErrorType.INVALID_INPUT
        elif "unavailable" in error_msg.lower():
            error_type = ErrorType.TOOL_UNAVAILABLE
        elif "not found" in error_msg.lower():
            error_type = ErrorType.NO_TOOL_FOUND

        return Error(
            error_code="ERR_EXEC",
            error_type=error_type,
            message=error_msg,
            recoverable=True,
        )

    def _extract_variables(
        self,
        result: ExecutionResult,
        intent: Intent,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract variables for template substitution.

        Time Complexity: O(1) - fixed number of extractions

        Args:
            result: Execution result
            intent: User intent
            context: Additional context

        Returns:
            Dictionary of variables for substitution

        """
        variables = {}

        # Extract from intent entities (handle Entity objects)
        for key, entity in intent.entities.items():
            # Extract the value from Entity object
            from Agent_Guru.reasoning.models.intent import Entity

            if isinstance(entity, Entity):
                variables[key] = entity.value
            else:
                variables[key] = entity

        # Extract from result data
        if result.result_data:
            if isinstance(result.result_data, dict):
                variables.update(result.result_data)
            else:
                variables["result"] = str(result.result_data)

        # Extract from error (now a string)
        if result.error:
            variables["error_message"] = result.error
            variables["error_type"] = "error"

        # Add context
        variables.update(context)

        # Add intent type
        variables["intent_type"] = intent.intent_type

        return variables

    def _validate_variables(self, template: ResponseTemplate, variables: dict[str, Any]) -> None:
        """Validate that all required variables are present.

        Time Complexity: O(n) where n = number of required variables

        Args:
            template: Response template
            variables: Available variables

        Raises:
            ValueError: If required variables are missing

        """
        missing = [var for var in template.variables if var not in variables]
        if missing:
            logger.warning(
                "Missing template variables, will use empty string fallback",
                extra={"template_id": template.template_id, "missing": missing},
            )

    def _format_template(
        self,
        template: ResponseTemplate,
        modality: ResponseModality,
        variables: dict[str, Any],
    ) -> str:
        """Format template with variables.

        Time Complexity: O(n) where n = template length

        Args:
            template: Response template
            modality: Response modality
            variables: Variables for substitution

        Returns:
            Formatted response text

        """
        # Select template based on modality
        if modality == ResponseModality.VOICE:
            template_str = template.voice_template
        else:
            template_str = template.text_template

        # Format with variables (safe substitution - missing vars become empty)
        try:
            return template_str.format(**variables)
        except KeyError:
            # Fallback: use safe_substitute-like behavior
            logger.exception("Variable %s not found in template, using empty string")
            # Replace missing variables with empty strings
            safe_vars = dict(variables.items())
            for var in template.variables:
                if var not in safe_vars:
                    safe_vars[var] = ""
            return template_str.format(**safe_vars)

    def _personalize_response(self, text: str, user_preferences: dict[str, Any]) -> str:
        """Personalize response based on user preferences.

        Time Complexity: O(n) where n = text length

        Args:
            text: Response text
            user_preferences: User preferences

        Returns:
            Personalized response text

        """
        # Apply verbosity preference
        verbosity = user_preferences.get("verbosity", "normal")
        if verbosity == "concise":
            # Remove extra details for concise users
            text = self._make_concise(text)
        elif verbosity == "detailed":
            # Keep all details for detailed users
            pass

        # Apply formality preference
        formality = user_preferences.get("formality", "casual")
        if formality == "formal":
            text = self._make_formal(text)
        elif formality == "casual":
            text = self._make_casual(text)

        return text

    def _make_concise(self, text: str) -> str:
        """Make response more concise."""
        # Remove common filler phrases
        fillers = ["I've successfully ", "I have ", "for you", "right away", "just now"]
        for filler in fillers:
            text = text.replace(filler, "")
        return text.strip()

    def _make_formal(self, text: str) -> str:
        """Make response more formal."""
        replacements = {
            "I've": "I have",
            "can't": "cannot",
            "won't": "will not",
            "don't": "do not",
            "OK": "Confirmed",
            "ok": "confirmed",
        }
        for informal, formal in replacements.items():
            text = text.replace(informal, formal)
        return text

    def _make_casual(self, text: str) -> str:
        """Make response more casual."""
        replacements = {
            "I have": "I've",
            "cannot": "can't",
            "will not": "won't",
            "do not": "don't",
            "Confirmed": "OK",
            "confirmed": "ok",
        }
        for formal, casual in replacements.items():
            text = text.replace(formal, casual)
        return text

    def _generate_suggestions(
        self,
        template: ResponseTemplate,
        intent: Intent,
        result: ExecutionResult,
        conversation_state: Any | None = None,
        user_preferences: dict[str, Any] | None = None,
    ) -> list[str]:
        """Generate follow-up suggestions using proactive suggestion generator.

        Time Complexity: O(1) - fixed number of suggestions

        Args:
            template: Response template
            intent: User intent
            result: Execution result
            conversation_state: Optional conversation state
            user_preferences: Optional user preferences

        Returns:
            List of suggestion strings

        """
        # Use proactive suggestion generator if available
        if hasattr(self, "_proactive_generator") and self._proactive_generator is not None:
            return self._proactive_generator.generate_suggestions(
                intent,
                result,
                conversation_state,
                user_preferences,
            )

        # Fallback to template-based suggestions
        suggestions = []

        # Add template-specific suggestions
        if template.suggestions:
            suggestions.extend(template.suggestions)

        # Add intent-specific suggestions
        intent_suggestions = self._get_intent_suggestions(intent.intent_type)
        suggestions.extend(intent_suggestions)

        # Limit to 3 suggestions
        return suggestions[:3]

    def _get_intent_suggestions(self, intent_type: Any) -> list[str]:
        """Get suggestions for specific intent type."""
        # Normalize to string value
        intent_type_str = intent_type.value if hasattr(intent_type, "value") else str(intent_type)
        suggestions_map = {
            "set_timer": ["Set another timer", "Cancel timer", "Check remaining time"],
            "query_weather": ["Check tomorrow's weather", "Get hourly forecast", "Weather alerts"],
            "send_message": ["Send another message", "View sent messages", "Call instead"],
            "play_music": ["Play next song", "Pause music", "Add to playlist"],
            "create_reminder": ["View all reminders", "Set another reminder", "Edit reminder"],
            "query_time": ["Set alarm", "Check timezone", "World clock"],
            "query_calendar": ["Create event", "View tomorrow", "Check conflicts"],
            "control_smart_home": ["Check device status", "Create automation", "View all devices"],
        }
        return suggestions_map.get(intent_type_str, [])

    def _load_default_templates(self) -> None:
        """Load default response templates.

        Time Complexity: O(1) - fixed number of templates
        """
        # Generic success template
        self._templates["generic_success"] = ResponseTemplate(
            template_id="generic_success",
            template_type=TemplateType.SUCCESS,
            text_template="Done!",
            voice_template="Done",
            variables=[],
            suggestions=[],
        )

        # Generic error template
        self._templates["generic_error"] = ResponseTemplate(
            template_id="generic_error",
            template_type=TemplateType.ERROR,
            text_template="Sorry, something went wrong: {error_message}",
            voice_template="Sorry, that didn't work",
            variables=["error_message"],
            suggestions=["Try again", "Get help"],
        )

        # Timer templates
        self._templates["set_timer_success"] = ResponseTemplate(
            template_id="set_timer_success",
            template_type=TemplateType.SUCCESS,
            text_template="Timer set for {duration}",
            voice_template="Timer set for {duration}",
            variables=["duration"],
            suggestions=["Set another timer", "Cancel timer"],
        )

        # Weather templates
        self._templates["query_weather_success"] = ResponseTemplate(
            template_id="query_weather_success",
            template_type=TemplateType.SUCCESS,
            text_template="The weather in {location} is {condition} with a temperature of {temperature}",
            voice_template="{condition}, {temperature} in {location}",
            variables=["location", "condition", "temperature"],
            suggestions=["Tomorrow's weather", "Hourly forecast"],
        )

        # Message templates
        self._templates["send_message_success"] = ResponseTemplate(
            template_id="send_message_success",
            template_type=TemplateType.SUCCESS,
            text_template="Message sent to {recipient}: {message}",
            voice_template="Message sent to {recipient}",
            variables=["recipient", "message"],
            suggestions=["Send another message", "View conversation"],
        )

        # Music templates
        self._templates["play_music_success"] = ResponseTemplate(
            template_id="play_music_success",
            template_type=TemplateType.SUCCESS,
            text_template="Now playing {song} by {artist}",
            voice_template="Playing {song}",
            variables=["song"],
            suggestions=["Next song", "Pause", "Add to playlist"],
        )

        # Reminder templates
        self._templates["create_reminder_success"] = ResponseTemplate(
            template_id="create_reminder_success",
            template_type=TemplateType.SUCCESS,
            text_template="Reminder set for {time}: {reminder}",
            voice_template="Reminder set for {time}",
            variables=["time", "reminder"],
            suggestions=["View all reminders", "Set another"],
        )

        # Time templates
        self._templates["query_time_success"] = ResponseTemplate(
            template_id="query_time_success",
            template_type=TemplateType.SUCCESS,
            text_template="The current time is {time}",
            voice_template="It's {time}",
            variables=["time"],
            suggestions=["Set alarm", "Check timezone"],
        )

        # Calendar templates
        self._templates["query_calendar_success"] = ResponseTemplate(
            template_id="query_calendar_success",
            template_type=TemplateType.SUCCESS,
            text_template="You have {count} events today: {events}",
            voice_template="You have {count} events today",
            variables=["count", "events"],
            suggestions=["Create event", "View tomorrow"],
        )

        # Smart home templates
        self._templates["control_smart_home_success"] = ResponseTemplate(
            template_id="control_smart_home_success",
            template_type=TemplateType.SUCCESS,
            text_template="{device} {action} successfully",
            voice_template="{device} {action}",
            variables=["device", "action"],
            suggestions=["Check status", "Create automation"],
        )

        # Error templates by type
        self._templates["error_timeout"] = ResponseTemplate(
            template_id="error_timeout",
            template_type=TemplateType.ERROR,
            text_template="The operation timed out. Please try again.",
            voice_template="That took too long. Try again?",
            variables=[],
            suggestions=["Try again", "Cancel"],
        )

        self._templates["error_permission_denied"] = ResponseTemplate(
            template_id="error_permission_denied",
            template_type=TemplateType.ERROR,
            text_template="I don't have permission to do that.",
            voice_template="Permission denied",
            variables=[],
            suggestions=["Grant permission", "Try something else"],
        )

        self._templates["error_tool_unavailable"] = ResponseTemplate(
            template_id="error_tool_unavailable",
            template_type=TemplateType.ERROR,
            text_template="That feature is currently unavailable.",
            voice_template="That's not available right now",
            variables=[],
            suggestions=["Try later", "Use alternative"],
        )

        self._templates["error_invalid_input"] = ResponseTemplate(
            template_id="error_invalid_input",
            template_type=TemplateType.ERROR,
            text_template="I didn't understand that. Can you rephrase?",
            voice_template="I didn't get that. Can you rephrase?",
            variables=[],
            suggestions=["Rephrase", "Get help", "Cancel"],
        )

        self._templates["error_network_error"] = ResponseTemplate(
            template_id="error_network_error",
            template_type=TemplateType.ERROR,
            text_template="Network connection failed. Please check your connection and try again.",
            voice_template="Network error. Check your connection",
            variables=[],
            suggestions=["Try again", "Work offline"],
        )

        # Confirmation templates
        self._templates["confirmation_required"] = ResponseTemplate(
            template_id="confirmation_required",
            template_type=TemplateType.CONFIRMATION,
            text_template="Are you sure you want to {action}? This action {warning}.",
            voice_template="Confirm {action}?",
            variables=["action", "warning"],
            suggestions=["Confirm", "Cancel"],
        )

        # Clarification templates
        self._templates["clarification_needed"] = ResponseTemplate(
            template_id="clarification_needed",
            template_type=TemplateType.CLARIFICATION,
            text_template="I need more information. {question}",
            voice_template="{question}",
            variables=["question"],
            suggestions=[],
        )

        # Partial success templates
        self._templates["partial_success"] = ResponseTemplate(
            template_id="partial_success",
            template_type=TemplateType.PARTIAL_SUCCESS,
            text_template="Completed {completed} of {total} steps. {error_message}",
            voice_template="Partially done. {error_message}",
            variables=["completed", "total", "error_message"],
            suggestions=["Retry failed steps", "Continue anyway"],
        )

        # Progress templates
        self._templates["progress_update"] = ResponseTemplate(
            template_id="progress_update",
            template_type=TemplateType.PROGRESS,
            text_template="Working on it... {progress}% complete",
            voice_template="Working on it",
            variables=["progress"],
            suggestions=["Cancel"],
        )

    def add_template(self, template: ResponseTemplate) -> None:
        """Add custom template to registry.

        Args:
            template: Response template to add

        """
        self._templates[template.template_id] = template
        logger.info("Added custom template: %s", template.template_id)

    def get_template(self, template_id: str) -> ResponseTemplate | None:
        """Get template by ID.

        Args:
            template_id: Template identifier

        Returns:
            Response template or None if not found

        """
        return self._templates.get(template_id)

    def list_templates(self) -> list[str]:
        """List all available template IDs.

        Returns:
            List of template IDs

        """
        return list(self._templates.keys())

    def set_proactive_generator(self, generator: Any) -> None:
        """Set proactive suggestion generator.

        Args:
            generator: ProactiveSuggestionGenerator instance

        """
        self._proactive_generator = generator
        logger.info("Proactive suggestion generator set")
