"""Proactive suggestion generation for conversation strategy.

This module implements:
- Follow-up suggestions based on context
- Proactive suggestions based on learned patterns
- Alternative suggestions when primary action fails
- Suggestion ranking by relevance and confidence

Requirements: 19.3, 27.4
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from Agent_Guru.reasoning.models.conversation import ConversationState
from Agent_Guru.reasoning.models.result import ExecutionResult
from Agent_Guru.reasoning.models.task import Task


@dataclass
class Suggestion:
    """A proactive suggestion."""

    description: str
    action: str
    confidence: float
    relevance: float
    category: str  # "follow_up", "proactive", "alternative"
    context: dict[str, Any]


class SuggestionCategory:
    """Suggestion categories."""

    FOLLOW_UP = "follow_up"  # Based on current action
    PROACTIVE = "proactive"  # Based on learned patterns
    ALTERNATIVE = "alternative"  # When primary action fails


class ProactiveSuggestionGenerator:
    """Generates proactive suggestions."""

    # Follow-up suggestions by action type
    FOLLOW_UP_SUGGESTIONS = {
        "set_timer": [
            "Would you like me to set another timer?",
            "Should I remind you when it goes off?",
        ],
        "send_message": [
            "Would you like to send another message?",
            "Should I call them instead?",
        ],
        "query_weather": [
            "Would you like the forecast for tomorrow?",
            "Should I check the weather for another location?",
        ],
        "play_music": [
            "Would you like me to create a playlist?",
            "Should I play something similar?",
        ],
        "create_calendar_event": [
            "Would you like to set a reminder?",
            "Should I invite anyone else?",
        ],
    }

    # Alternative suggestions when action fails
    ALTERNATIVE_SUGGESTIONS = {
        "send_message": [
            "Would you like to call them instead?",
            "Should I send an email?",
        ],
        "query_weather": [
            "Would you like to check a different location?",
            "Should I show you the weekly forecast?",
        ],
        "play_music": [
            "Would you like to try a different song?",
            "Should I play a radio station?",
        ],
    }

    def __init__(self) -> None:
        """Initialize suggestion generator."""
        self.user_patterns: dict[str, list[dict[str, Any]]] = {}

    def generate_follow_up_suggestions(
        self,
        task: Task,
        result: ExecutionResult,
        conversation_state: ConversationState,
    ) -> list[Suggestion]:
        """Generate follow-up suggestions based on completed action.

        Args:
            task: Completed task
            result: Execution result
            conversation_state: Current conversation state

        Returns:
            List of follow-up suggestions

        """
        suggestions: list[Suggestion] = []

        # Only generate for successful actions
        if not result.success:
            return suggestions

        # Get follow-up templates for this action
        templates = self.FOLLOW_UP_SUGGESTIONS.get(task.task_type, [])

        for template in templates:
            # Calculate relevance based on context
            relevance = self._calculate_relevance(
                task,
                conversation_state,
                SuggestionCategory.FOLLOW_UP,
            )

            suggestions.append(
                Suggestion(
                    description=template,
                    action=self._template_to_action(template, task),
                    confidence=0.7,
                    relevance=relevance,
                    category=SuggestionCategory.FOLLOW_UP,
                    context={
                        "original_task": task.task_type,
                        "original_goal": task.goal,
                    },
                ),
            )

        return suggestions

    def generate_proactive_suggestions(
        self,
        user_id: str,
        conversation_state: ConversationState,
        current_time: datetime | None = None,
    ) -> list[Suggestion]:
        """Generate proactive suggestions based on learned patterns.

        Args:
            user_id: User identifier
            conversation_state: Current conversation state
            current_time: Current time (for time-based patterns)

        Returns:
            List of proactive suggestions

        """
        suggestions: list[Suggestion] = []

        # Get user's patterns
        patterns = self.user_patterns.get(user_id, [])

        # Generate suggestions from patterns
        for pattern in patterns:
            # Check if pattern is relevant now
            if self._is_pattern_relevant(pattern, current_time):
                suggestion = self._pattern_to_suggestion(pattern)
                if suggestion:
                    suggestions.append(suggestion)

        # Generate context-based suggestions
        context_suggestions = self._generate_context_suggestions(conversation_state, current_time)
        suggestions.extend(context_suggestions)

        return suggestions

    def generate_alternative_suggestions(
        self,
        task: Task,
        error: Any | None = None,
    ) -> list[Suggestion]:
        """Generate alternative suggestions when primary action fails.

        Args:
            task: Failed task
            error: Optional error information

        Returns:
            List of alternative suggestions

        """
        suggestions: list[Suggestion] = []

        # Get alternative templates for this action
        templates = self.ALTERNATIVE_SUGGESTIONS.get(task.task_type, [])

        for template in templates:
            suggestions.append(
                Suggestion(
                    description=template,
                    action=self._template_to_action(template, task),
                    confidence=0.6,
                    relevance=0.8,  # High relevance when primary fails
                    category=SuggestionCategory.ALTERNATIVE,
                    context={
                        "failed_task": task.task_type,
                        "failed_goal": task.goal,
                        "error": str(error) if error else None,
                    },
                ),
            )

        return suggestions

    def rank_suggestions(
        self,
        suggestions: list[Suggestion],
        max_suggestions: int = 3,
    ) -> list[Suggestion]:
        """Rank suggestions by relevance and confidence.

        Args:
            suggestions: List of suggestions to rank
            max_suggestions: Maximum number to return

        Returns:
            Ranked list of top suggestions

        """
        # Calculate combined score
        for suggestion in suggestions:
            suggestion.context["score"] = suggestion.relevance * 0.6 + suggestion.confidence * 0.4

        # Sort by score
        ranked = sorted(suggestions, key=lambda s: s.context.get("score", 0.0), reverse=True)

        # Return top N
        return ranked[:max_suggestions]

    def learn_pattern(self, user_id: str, action: str, context: dict[str, Any]) -> None:
        """Learn a user pattern for proactive suggestions.

        Args:
            user_id: User identifier
            action: Action performed
            context: Context information (time, location, etc.)

        """
        if user_id not in self.user_patterns:
            self.user_patterns[user_id] = []

        # Create pattern entry
        pattern = {
            "action": action,
            "context": context,
            "frequency": 1,
            "last_seen": datetime.now(tz=UTC),
        }

        # Check if pattern already exists
        existing = self._find_similar_pattern(user_id, pattern)
        if existing:
            # Update frequency
            existing["frequency"] += 1
            existing["last_seen"] = datetime.now(tz=UTC)
        else:
            # Add new pattern
            self.user_patterns[user_id].append(pattern)

    def _calculate_relevance(
        self,
        task: Task,
        conversation_state: ConversationState,
        category: str,
    ) -> float:
        """Calculate relevance score for suggestion.

        Args:
            task: The task
            conversation_state: Conversation state
            category: Suggestion category

        Returns:
            Relevance score (0.0 to 1.0)

        """
        relevance = 0.5  # Base relevance

        # Increase for follow-ups
        if category == SuggestionCategory.FOLLOW_UP:
            relevance += 0.2

        # Increase if related to recent conversation
        if conversation_state.last_intent:
            last_intent_str = (
                conversation_state.last_intent.intent_type.value
                if hasattr(conversation_state.last_intent.intent_type, "value")
                else str(conversation_state.last_intent.intent_type)
            )
            task_type_str = (
                task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type)
            )
            if last_intent_str == task_type_str:
                relevance += 0.2

        # Decrease for long conversations (user might be tired)
        if len(conversation_state.turns) > 10:
            relevance -= 0.1

        return max(0.0, min(1.0, relevance))

    def _template_to_action(self, template: str, task: Task) -> str:
        """Convert template to action string.

        Args:
            template: Template string
            task: Original task

        Returns:
            Action string

        """
        # Simple extraction from template
        if "set another timer" in template:
            return "set_timer"
        if "send another message" in template:
            return "send_message"
        if "check the weather" in template:
            return "query_weather"
        if "play" in template:
            return "play_music"
        if "call" in template:
            return "make_call"

        # Default to original task type
        return task.task_type if isinstance(task.task_type, str) else task.task_type.value

    def _is_pattern_relevant(self, pattern: dict[str, Any], current_time: datetime | None) -> bool:
        """Check if pattern is relevant at current time.

        Args:
            pattern: User pattern
            current_time: Current time

        Returns:
            True if pattern is relevant

        """
        if not current_time:
            return False

        # Check time-based patterns
        if "time_of_day" in pattern["context"]:
            pattern_hour = pattern["context"]["time_of_day"]
            current_hour = current_time.hour

            # Within 1 hour window
            if abs(current_hour - pattern_hour) <= 1:
                return True

        # Check day-of-week patterns
        if "day_of_week" in pattern["context"]:
            pattern_day = pattern["context"]["day_of_week"]
            current_day = current_time.weekday()

            if pattern_day == current_day:
                return True

        # Check frequency (suggest if done frequently)
        return pattern.get("frequency", 0) >= 5

    def _pattern_to_suggestion(self, pattern: dict[str, Any]) -> Suggestion | None:
        """Convert pattern to suggestion.

        Args:
            pattern: User pattern

        Returns:
            Suggestion or None

        """
        action = pattern.get("action")
        if not action:
            return None

        # Generate description
        description = f"Would you like to {action.replace('_', ' ')}?"

        # Calculate confidence based on frequency
        frequency = pattern.get("frequency", 1)
        confidence = min(0.9, 0.5 + (frequency * 0.05))

        return Suggestion(
            description=description,
            action=action,
            confidence=confidence,
            relevance=0.7,
            category=SuggestionCategory.PROACTIVE,
            context={
                "pattern_frequency": frequency,
                "pattern_context": pattern.get("context", {}),
            },
        )

    def _generate_context_suggestions(
        self,
        conversation_state: ConversationState,
        current_time: datetime | None,
    ) -> list[Suggestion]:
        """Generate suggestions based on current context.

        Args:
            conversation_state: Conversation state
            current_time: Current time

        Returns:
            List of context-based suggestions

        """
        suggestions: list[Suggestion] = []

        # Time-based suggestions
        if current_time:
            hour = current_time.hour

            # Morning suggestions
            if 6 <= hour < 9:
                suggestions.append(
                    Suggestion(
                        description="Would you like to hear today's weather?",
                        action="query_weather",
                        confidence=0.6,
                        relevance=0.7,
                        category=SuggestionCategory.PROACTIVE,
                        context={"time_context": "morning"},
                    ),
                )

            # Evening suggestions
            elif 18 <= hour < 21:
                suggestions.append(
                    Suggestion(
                        description="Would you like to set a reminder for tomorrow?",
                        action="set_reminder",
                        confidence=0.5,
                        relevance=0.6,
                        category=SuggestionCategory.PROACTIVE,
                        context={"time_context": "evening"},
                    ),
                )

        return suggestions

    def _find_similar_pattern(self, user_id: str, pattern: dict[str, Any]) -> dict[str, Any] | None:
        """Find similar existing pattern.

        Args:
            user_id: User identifier
            pattern: Pattern to match

        Returns:
            Existing pattern or None

        """
        patterns = self.user_patterns.get(user_id, [])

        for existing in patterns:
            # Match by action and similar context
            if existing["action"] == pattern["action"]:
                # Check context similarity
                if self._contexts_similar(existing["context"], pattern["context"]):
                    return existing

        return None

    def _contexts_similar(self, context1: dict[str, Any], context2: dict[str, Any]) -> bool:
        """Check if two contexts are similar.

        Args:
            context1: First context
            context2: Second context

        Returns:
            True if similar

        """
        # Check time similarity
        if "time_of_day" in context1 and "time_of_day" in context2:
            if abs(context1["time_of_day"] - context2["time_of_day"]) <= 1:
                return True

        # Check day similarity
        if "day_of_week" in context1 and "day_of_week" in context2:
            if context1["day_of_week"] == context2["day_of_week"]:
                return True

        return False
