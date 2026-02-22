"""
Main Conversation Strategy Engine.

This module integrates all conversation strategy components:
- Clarification generation
- Confirmation handling
- Tone adaptation
- Error response generation
- Proactive suggestions

This is the main interface for conversation strategy.
"""

from datetime import datetime
from typing import Any, Optional

from Agent_Guru.reasoning.conversation.clarification import (
    ClarificationGenerator,
    ClarificationRequest,
)
from Agent_Guru.reasoning.conversation.confirmation import (
    ConfirmationGenerator,
    ConfirmationParser,
    ConfirmationRequest,
    ConfirmationResponse,
)
from Agent_Guru.reasoning.conversation.error_strategy import (
    ErrorResponse,
    ErrorResponseStrategy,
)
from Agent_Guru.reasoning.conversation.suggestions import (
    ProactiveSuggestionGenerator,
    Suggestion,
)
from Agent_Guru.reasoning.conversation.tone import (
    ContextualFactors,
    ResponseTemplateSelector,
    ToneAdapter,
    ToneProfile,
)
from Agent_Guru.reasoning.models.conversation import ConversationState
from Agent_Guru.reasoning.models.error import Error
from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.result import ExecutionResult
from Agent_Guru.reasoning.models.task import Task


class ConversationStrategyEngine:
    """
    Main conversation strategy engine.

    Coordinates all conversation strategy components to provide:
    - Intelligent clarification requests
    - Confirmation handling for sensitive actions
    - Tone-adapted responses
    - User-friendly error messages
    - Proactive suggestions
    """

    def __init__(self):
        """Initialize conversation strategy engine."""
        self.clarification_generator = ClarificationGenerator()
        self.confirmation_generator = ConfirmationGenerator()
        self.confirmation_parser = ConfirmationParser()
        self.tone_adapter = ToneAdapter()
        self.error_strategy = ErrorResponseStrategy()
        self.suggestion_generator = ProactiveSuggestionGenerator()

    # Clarification methods

    def should_clarify(
        self, intent: Optional[Intent], task: Optional[Task], confidence: float
    ) -> bool:
        """
        Check if clarification is needed.

        Args:
            intent: Detected intent
            task: Generated task
            confidence: Overall confidence

        Returns:
            True if clarification needed
        """
        should_clarify, _ = self.clarification_generator.rules.should_clarify(
            intent, task, confidence
        )
        return should_clarify

    def generate_clarification(
        self,
        intent: Optional[Intent],
        task: Optional[Task],
        confidence: float,
        alternative_intents: Optional[list[tuple[str, float]]] = None,
    ) -> Optional[ClarificationRequest]:
        """
        Generate clarification request.

        Args:
            intent: Detected intent
            task: Generated task
            confidence: Overall confidence
            alternative_intents: Alternative interpretations

        Returns:
            ClarificationRequest or None
        """
        return self.clarification_generator.generate_clarification(
            intent, task, confidence, alternative_intents
        )

    # Confirmation methods

    def requires_confirmation(self, task: Task, tool_id: Optional[str] = None) -> bool:
        """
        Check if task requires confirmation.

        Args:
            task: The task
            tool_id: Optional tool ID

        Returns:
            True if confirmation required
        """
        requires, _ = self.confirmation_generator.rules.requires_confirmation(task, tool_id)
        return requires

    def generate_confirmation(
        self, task: Task, tool_id: Optional[str] = None
    ) -> Optional[ConfirmationRequest]:
        """
        Generate confirmation request.

        Args:
            task: The task
            tool_id: Optional tool ID

        Returns:
            ConfirmationRequest or None
        """
        return self.confirmation_generator.generate_confirmation(task, tool_id)

    def parse_confirmation(self, user_response: str) -> ConfirmationResponse:
        """
        Parse user's confirmation response.

        Args:
            user_response: User's text response

        Returns:
            ConfirmationResponse
        """
        return self.confirmation_parser.parse_confirmation(user_response)

    # Tone adaptation methods

    def get_tone_profile(
        self, user_id: str, context: Optional[ContextualFactors] = None
    ) -> ToneProfile:
        """
        Get user's tone profile with contextual adjustments.

        Args:
            user_id: User identifier
            context: Contextual factors

        Returns:
            Tone profile
        """
        return self.tone_adapter.get_tone_profile(user_id, context)

    def adapt_response_tone(
        self, response: str, user_id: str, context: Optional[ContextualFactors] = None
    ) -> str:
        """
        Adapt response to user's tone preferences.

        Args:
            response: Original response
            user_id: User identifier
            context: Contextual factors

        Returns:
            Tone-adapted response
        """
        tone_profile = self.get_tone_profile(user_id, context)
        return self.tone_adapter.adapt_response(response, tone_profile)

    def select_response_template(
        self, template_type: str, user_id: str, context: Optional[ContextualFactors] = None
    ) -> str:
        """
        Select appropriate response template.

        Args:
            template_type: Type of template ("success" or "error")
            user_id: User identifier
            context: Contextual factors

        Returns:
            Template string
        """
        tone_profile = self.get_tone_profile(user_id, context)
        return ResponseTemplateSelector.select_template(template_type, tone_profile)

    # Error response methods

    def generate_error_response(
        self, error: Error, user_id: str, context: Optional[dict[str, Any]] = None
    ) -> ErrorResponse:
        """
        Generate user-friendly error response.

        Args:
            error: The error
            user_id: User identifier
            context: Optional context

        Returns:
            ErrorResponse
        """
        # Generate base error response
        error_response = self.error_strategy.generate_error_response(error, context)

        # Adapt for user's tone preferences
        tone_profile = self.get_tone_profile(user_id)

        # Adjust empathy based on tone warmth
        empathy_multiplier = 0.5 + (tone_profile.warmth * 0.5)

        return self.error_strategy.adapt_for_tone(error_response, empathy_multiplier)

    # Suggestion methods

    def generate_follow_up_suggestions(
        self, task: Task, result: ExecutionResult, conversation_state: ConversationState
    ) -> list[Suggestion]:
        """
        Generate follow-up suggestions after action.

        Args:
            task: Completed task
            result: Execution result
            conversation_state: Conversation state

        Returns:
            List of suggestions
        """
        suggestions = self.suggestion_generator.generate_follow_up_suggestions(
            task, result, conversation_state
        )
        return self.suggestion_generator.rank_suggestions(suggestions)

    def generate_proactive_suggestions(
        self,
        user_id: str,
        conversation_state: ConversationState,
        current_time: Optional[datetime] = None,
    ) -> list[Suggestion]:
        """
        Generate proactive suggestions based on patterns.

        Args:
            user_id: User identifier
            conversation_state: Conversation state
            current_time: Current time

        Returns:
            List of suggestions
        """
        suggestions = self.suggestion_generator.generate_proactive_suggestions(
            user_id, conversation_state, current_time
        )
        return self.suggestion_generator.rank_suggestions(suggestions)

    def generate_alternative_suggestions(
        self, task: Task, error: Optional[Error] = None
    ) -> list[Suggestion]:
        """
        Generate alternative suggestions when action fails.

        Args:
            task: Failed task
            error: Optional error

        Returns:
            List of suggestions
        """
        suggestions = self.suggestion_generator.generate_alternative_suggestions(task, error)
        return self.suggestion_generator.rank_suggestions(suggestions)

    # Learning methods

    def learn_tone_preference(self, user_id: str, dimension: str, value: float) -> None:
        """
        Learn user's tone preference.

        Args:
            user_id: User identifier
            dimension: Personality dimension
            value: Observed value
        """
        from Agent_Guru.reasoning.conversation.tone import PersonalityDimension

        dim_enum = PersonalityDimension(dimension)
        self.tone_adapter.learn_preference(user_id, dim_enum, value)

    def learn_action_pattern(self, user_id: str, action: str, context: dict[str, Any]) -> None:
        """
        Learn user's action pattern for proactive suggestions.

        Args:
            user_id: User identifier
            action: Action performed
            context: Context information
        """
        self.suggestion_generator.learn_pattern(user_id, action, context)

    # Utility methods

    def create_contextual_factors(
        self,
        time_of_day: Optional[datetime] = None,
        battery_level: Optional[float] = None,
        conversation_length: int = 0,
    ) -> ContextualFactors:
        """
        Create contextual factors for tone adaptation.

        Args:
            time_of_day: Current time
            battery_level: Battery level (0.0 to 1.0)
            conversation_length: Number of turns

        Returns:
            ContextualFactors
        """
        is_work_hours = False
        if time_of_day:
            is_work_hours = ToneAdapter.is_work_hours(time_of_day)

        return ContextualFactors(
            time_of_day=time_of_day,
            is_work_hours=is_work_hours,
            battery_level=battery_level,
            conversation_length=conversation_length,
        )
