"""Proactive Suggestions Generator.

Generates intelligent follow-up suggestions based on:
- Conversation context and history
- User behavior patterns
- Related capabilities
- Current task completion

Performance Requirements:
- Time Complexity: O(1) for suggestion lookup + O(n) for ranking
- Space Complexity: O(1) - fixed suggestion registry
- Latency: <50ms (95th percentile)

Design:
- Context-aware suggestion generation
- Behavioral pattern learning
- Related capability discovery
- Suggestion acceptance tracking
- Personalized ranking based on user preferences
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from Agent_Guru.reasoning.config.logging import get_logger
from Agent_Guru.reasoning.config.metrics import get_metrics_collector
from Agent_Guru.reasoning.models.conversation import ConversationState
from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.result import ExecutionResult

logger = get_logger(__name__)
metrics = get_metrics_collector()


class SuggestionType(str, Enum):
    """Types of proactive suggestions."""

    FOLLOW_UP = "follow_up"  # Natural next action after current task
    RELATED = "related"  # Related capability user might want
    ALTERNATIVE = "alternative"  # Alternative way to accomplish goal
    CONTEXTUAL = "contextual"  # Based on conversation context
    BEHAVIORAL = "behavioral"  # Based on learned user patterns
    ERROR_RECOVERY = "error_recovery"  # Recovery from error


@dataclass
class Suggestion:
    """A proactive suggestion for the user.

    Attributes:
        text: Suggestion text to display
        suggestion_type: Type of suggestion
        intent_type: Intent type this suggestion would trigger
        confidence: Confidence score (0.0-1.0)
        context: Additional context for the suggestion
        priority: Priority for ranking (higher = more important)

    """

    text: str
    suggestion_type: SuggestionType
    intent_type: str | None = None
    confidence: float = 1.0
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def __post_init__(self) -> None:
        """Validate suggestion fields."""
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            raise ValueError(msg)
        if not self.text:
            msg = "Suggestion text cannot be empty"
            raise ValueError(msg)


@dataclass
class SuggestionAcceptance:
    """Tracks suggestion acceptance for learning.

    Attributes:
        suggestion_text: The suggestion that was shown
        suggestion_type: Type of suggestion
        intent_type: Intent type suggested
        was_accepted: Whether user accepted the suggestion
        timestamp: When suggestion was shown
        context: Context when suggestion was shown

    """

    suggestion_text: str
    suggestion_type: SuggestionType
    intent_type: str | None
    was_accepted: bool
    timestamp: float
    context: dict[str, Any] = field(default_factory=dict)


class ProactiveSuggestionGenerator:
    """Generate intelligent proactive suggestions.

    Time Complexity: O(1) for lookup + O(n log n) for ranking where n = suggestion count
    Space Complexity: O(1) - fixed suggestion registry
    Latency Target: <50ms (95th percentile)

    Example:
        >>> generator = ProactiveSuggestionGenerator()
        >>> intent = Intent(intent_type="set_timer", entities={"duration": "5 minutes"})
        >>> result = ExecutionResult(success=True, result_data={"timer": "5 minutes"})
        >>> suggestions = generator.generate_suggestions(intent, result)
        >>> for suggestion in suggestions:
        ...     print(suggestion.text)
        "Set another timer"
        "Cancel timer"
        "Check remaining time"

    """

    def __init__(self, max_suggestions: int = 3) -> None:
        """Initialize proactive suggestion generator.

        Args:
            max_suggestions: Maximum number of suggestions to return

        """
        self.max_suggestions = max_suggestions

        # Suggestion registry: intent_type -> list of suggestions
        self._suggestion_registry: dict[str, list[Suggestion]] = {}

        # Related capabilities: intent_type -> set of related intent types
        self._related_capabilities: dict[str, set[str]] = {}

        # Acceptance tracking: suggestion_text -> list of acceptances
        self._acceptance_history: dict[str, list[SuggestionAcceptance]] = defaultdict(list)

        # User preference scores: suggestion_text -> acceptance_rate
        self._preference_scores: dict[str, float] = {}

        # Load default suggestions
        self._load_default_suggestions()
        self._load_related_capabilities()

        logger.info(
            "ProactiveSuggestionGenerator initialized",
            extra={
                "max_suggestions": max_suggestions,
                "suggestion_count": sum(len(s) for s in self._suggestion_registry.values()),
                "related_capability_count": len(self._related_capabilities),
            },
        )

    def generate_suggestions(
        self,
        intent: Intent,
        result: ExecutionResult,
        conversation_state: ConversationState | None = None,
        user_preferences: dict[str, Any] | None = None,
    ) -> list[str]:
        """Generate proactive suggestions based on context.

        Time Complexity: O(n log n) where n = number of candidate suggestions
        Space Complexity: O(n) for candidate list

        Args:
            intent: Current user intent
            result: Execution result
            conversation_state: Optional conversation state for context
            user_preferences: Optional user preferences

        Returns:
            List of suggestion strings (max self.max_suggestions)

        """
        start_time = time.perf_counter()

        try:
            # Generate candidate suggestions
            candidates: list[Suggestion] = []

            # 1. Follow-up suggestions based on intent
            candidates.extend(self._generate_follow_up_suggestions(intent, result))

            # 2. Related capability suggestions
            candidates.extend(self._generate_related_suggestions(intent))

            # 3. Contextual suggestions from conversation
            if conversation_state:
                candidates.extend(self._generate_contextual_suggestions(intent, conversation_state))

            # 4. Behavioral suggestions from patterns
            if conversation_state:
                candidates.extend(self._generate_behavioral_suggestions(intent, conversation_state))

            # 5. Error recovery suggestions if failed
            if not result.success:
                candidates.extend(self._generate_error_recovery_suggestions(intent, result))

            # Rank and filter suggestions
            ranked_suggestions = self._rank_suggestions(candidates, intent, user_preferences or {})

            # Convert to strings
            suggestion_texts = [s.text for s in ranked_suggestions[: self.max_suggestions]]

            # Track metrics
            latency_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_stage_latency("suggestion_generation", latency_ms / 1000)

            logger.info(
                "Proactive suggestions generated",
                extra={
                    "intent_type": intent.intent_type,
                    "candidate_count": len(candidates),
                    "final_count": len(suggestion_texts),
                    "latency_ms": latency_ms,
                },
            )

            return suggestion_texts

        except Exception as e:
            logger.exception(
                "Suggestion generation failed",
                extra={"error": str(e), "intent_type": intent.intent_type},
            )
            metrics.increment_errors("suggestion_generation")
            # Return empty list on error
            return []

    def track_acceptance(
        self,
        suggestion_text: str,
        was_accepted: bool,
        suggestion_type: SuggestionType,
        intent_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Track whether user accepted a suggestion.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            suggestion_text: The suggestion that was shown
            was_accepted: Whether user accepted it
            suggestion_type: Type of suggestion
            intent_type: Intent type suggested
            context: Optional context

        """
        acceptance = SuggestionAcceptance(
            suggestion_text=suggestion_text,
            suggestion_type=suggestion_type,
            intent_type=intent_type,
            was_accepted=was_accepted,
            timestamp=time.time(),
            context=context or {},
        )

        self._acceptance_history[suggestion_text].append(acceptance)

        # Update preference score
        self._update_preference_score(suggestion_text)

        # Track metrics
        metrics.increment_requests(f"suggestion_{'accepted' if was_accepted else 'rejected'}")

        logger.info(
            "Suggestion acceptance tracked",
            extra={
                "suggestion": suggestion_text,
                "accepted": was_accepted,
                "type": suggestion_type.value,
                "acceptance_rate": self._preference_scores.get(suggestion_text, 0.0),
            },
        )

    def get_acceptance_rate(self, suggestion_text: str) -> float:
        """Get acceptance rate for a suggestion.

        Args:
            suggestion_text: Suggestion to check

        Returns:
            Acceptance rate (0.0-1.0)

        """
        return self._preference_scores.get(suggestion_text, 0.5)  # Default 0.5

    def get_acceptance_stats(self) -> dict[str, Any]:
        """Get overall acceptance statistics.

        Returns:
            Dictionary with acceptance statistics

        """
        total_shown = sum(len(history) for history in self._acceptance_history.values())
        total_accepted = sum(
            sum(1 for a in history if a.was_accepted)
            for history in self._acceptance_history.values()
        )

        overall_rate = total_accepted / total_shown if total_shown > 0 else 0.0

        # Get stats by type
        type_stats = {}
        for suggestion_type in SuggestionType:
            type_acceptances = [
                a
                for history in self._acceptance_history.values()
                for a in history
                if a.suggestion_type == suggestion_type
            ]
            type_total = len(type_acceptances)
            type_accepted = sum(1 for a in type_acceptances if a.was_accepted)
            type_rate = type_accepted / type_total if type_total > 0 else 0.0

            type_stats[suggestion_type.value] = {
                "total": type_total,
                "accepted": type_accepted,
                "rate": type_rate,
            }

        return {
            "overall": {
                "total_shown": total_shown,
                "total_accepted": total_accepted,
                "acceptance_rate": overall_rate,
            },
            "by_type": type_stats,
            "top_suggestions": self._get_top_suggestions(5),
        }

    def _generate_follow_up_suggestions(
        self,
        intent: Intent,
        result: ExecutionResult,
    ) -> list[Suggestion]:
        """Generate follow-up suggestions based on intent."""
        # Convert intent_type to string if it's an enum
        intent_type_str = (
            intent.intent_type.value
            if hasattr(intent.intent_type, "value")
            else str(intent.intent_type)
        )
        suggestions = self._suggestion_registry.get(intent_type_str, [])

        # Filter by result success
        if result.success:
            # Return success-specific suggestions
            return [s for s in suggestions if s.suggestion_type == SuggestionType.FOLLOW_UP]
        # Return error recovery suggestions
        return [s for s in suggestions if s.suggestion_type == SuggestionType.ERROR_RECOVERY]

    def _generate_related_suggestions(self, intent: Intent) -> list[Suggestion]:
        """Generate suggestions for related capabilities."""
        # Convert intent_type to string if it's an enum
        intent_type_str = (
            intent.intent_type.value
            if hasattr(intent.intent_type, "value")
            else str(intent.intent_type)
        )
        related_intents = self._related_capabilities.get(intent_type_str, set())

        suggestions = []
        for related_intent in related_intents:
            # Get first suggestion from related intent
            related_suggestions = self._suggestion_registry.get(related_intent, [])
            if related_suggestions:
                # Create related suggestion
                base_suggestion = related_suggestions[0]
                suggestions.append(
                    Suggestion(
                        text=base_suggestion.text,
                        suggestion_type=SuggestionType.RELATED,
                        intent_type=related_intent,
                        confidence=0.8,  # Slightly lower confidence for related
                        priority=base_suggestion.priority - 1,
                    ),
                )

        return suggestions

    def _generate_contextual_suggestions(
        self,
        intent: Intent,
        conversation_state: ConversationState,
    ) -> list[Suggestion]:
        """Generate suggestions based on conversation context."""
        suggestions = []

        # Check recent turns for patterns
        if len(conversation_state.turns) >= 2:
            # Get last two intents
            recent_intents = [
                turn.intent.intent_type
                for turn in list(conversation_state.turns)[-2:]
                if turn.intent
            ]

            # If user is repeating similar actions, suggest batch operation
            if len({str(i) for i in recent_intents}) == 1:
                suggestions.append(
                    Suggestion(
                        text="Do multiple at once?",
                        suggestion_type=SuggestionType.CONTEXTUAL,
                        confidence=0.7,
                        priority=2,
                    ),
                )

        # Check tracked entities for context
        if conversation_state.entities:
            # If location entity exists, suggest location-based actions
            if any(
                "location" in str(e.entity_type).lower()
                for e in conversation_state.entities.values()
            ):
                suggestions.append(
                    Suggestion(
                        text="Get directions",
                        suggestion_type=SuggestionType.CONTEXTUAL,
                        intent_type="get_directions",
                        confidence=0.6,
                        priority=1,
                    ),
                )

        return suggestions

    def _generate_behavioral_suggestions(
        self,
        intent: Intent,
        conversation_state: ConversationState,
    ) -> list[Suggestion]:
        """Generate suggestions based on learned behavior patterns."""
        suggestions = []

        # Analyze user preferences from conversation state
        if hasattr(conversation_state, "user_preferences"):
            user_prefs = conversation_state.user_preferences

            # If user prefers detailed responses, suggest more info
            if user_prefs.get("verbosity") == "detailed":
                suggestions.append(
                    Suggestion(
                        text="Get more details",
                        suggestion_type=SuggestionType.BEHAVIORAL,
                        confidence=0.7,
                        priority=1,
                    ),
                )

        # Check time-based patterns
        # (In production, this would analyze historical usage patterns)

        return suggestions

    def _generate_error_recovery_suggestions(
        self,
        intent: Intent,
        result: ExecutionResult,
    ) -> list[Suggestion]:
        """Generate suggestions for error recovery."""
        suggestions = []

        # Convert intent_type to string if it's an enum
        intent_type_str = (
            intent.intent_type.value
            if hasattr(intent.intent_type, "value")
            else str(intent.intent_type)
        )

        # Always suggest retry
        suggestions.append(
            Suggestion(
                text="Try again",
                suggestion_type=SuggestionType.ERROR_RECOVERY,
                intent_type=intent_type_str,
                confidence=0.9,
                priority=3,
            ),
        )

        # Suggest simplification
        suggestions.append(
            Suggestion(
                text="Try a simpler version",
                suggestion_type=SuggestionType.ERROR_RECOVERY,
                confidence=0.7,
                priority=2,
            ),
        )

        # Suggest alternative
        suggestions.append(
            Suggestion(
                text="Try a different approach",
                suggestion_type=SuggestionType.ALTERNATIVE,
                confidence=0.6,
                priority=1,
            ),
        )

        return suggestions

    def _rank_suggestions(
        self,
        candidates: list[Suggestion],
        intent: Intent,
        user_preferences: dict[str, Any],
    ) -> list[Suggestion]:
        """Rank suggestions by relevance and user preferences.

        Time Complexity: O(n log n) for sorting

        Args:
            candidates: Candidate suggestions
            intent: Current intent
            user_preferences: User preferences

        Returns:
            Ranked list of suggestions

        """
        # Calculate score for each suggestion
        scored_suggestions = []
        for suggestion in candidates:
            score = self._calculate_suggestion_score(suggestion, intent, user_preferences)
            scored_suggestions.append((score, suggestion))

        # Sort by score (descending)
        scored_suggestions.sort(key=lambda x: x[0], reverse=True)

        # Return suggestions only
        return [s for _, s in scored_suggestions]

    def _calculate_suggestion_score(
        self,
        suggestion: Suggestion,
        intent: Intent,
        user_preferences: dict[str, Any],
    ) -> float:
        """Calculate relevance score for suggestion.

        Args:
            suggestion: Suggestion to score
            intent: Current intent
            user_preferences: User preferences

        Returns:
            Score (higher = more relevant)

        """
        score = 0.0

        # Base score from confidence
        score += suggestion.confidence * 10

        # Priority boost
        score += suggestion.priority * 5

        # Acceptance rate boost
        acceptance_rate = self._preference_scores.get(suggestion.text, 0.5)
        score += acceptance_rate * 8

        # Type-specific boosts
        if suggestion.suggestion_type == SuggestionType.FOLLOW_UP:
            score += 3  # Follow-ups are usually most relevant
        elif suggestion.suggestion_type == SuggestionType.ERROR_RECOVERY:
            score += 2  # Error recovery is important

        # User preference adjustments
        if user_preferences.get("show_advanced_suggestions", False):
            if suggestion.suggestion_type == SuggestionType.RELATED:
                score += 2

        return score

    def _update_preference_score(self, suggestion_text: str) -> None:
        """Update preference score based on acceptance history."""
        history = self._acceptance_history[suggestion_text]
        if not history:
            return

        # Calculate acceptance rate
        accepted_count = sum(1 for a in history if a.was_accepted)
        total_count = len(history)
        acceptance_rate = accepted_count / total_count

        self._preference_scores[suggestion_text] = acceptance_rate

    def _get_top_suggestions(self, limit: int) -> list[dict[str, Any]]:
        """Get top suggestions by acceptance rate."""
        sorted_suggestions = sorted(
            self._preference_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [
            {
                "text": text,
                "acceptance_rate": rate,
                "shown_count": len(self._acceptance_history[text]),
            }
            for text, rate in sorted_suggestions[:limit]
        ]

    def _load_default_suggestions(self) -> None:
        """Load default suggestion registry."""
        # Timer suggestions
        self._suggestion_registry["set_timer"] = [
            Suggestion("Set another timer", SuggestionType.FOLLOW_UP, "set_timer", priority=3),
            Suggestion("Cancel timer", SuggestionType.FOLLOW_UP, "cancel_timer", priority=2),
            Suggestion("Check remaining time", SuggestionType.FOLLOW_UP, "query_timer", priority=1),
        ]

        # Weather suggestions
        self._suggestion_registry["query_weather"] = [
            Suggestion(
                "Check tomorrow's weather",
                SuggestionType.FOLLOW_UP,
                "query_weather",
                priority=3,
            ),
            Suggestion(
                "Get hourly forecast",
                SuggestionType.FOLLOW_UP,
                "query_weather",
                priority=2,
            ),
            Suggestion(
                "Check weather alerts",
                SuggestionType.FOLLOW_UP,
                "query_weather",
                priority=1,
            ),
        ]

        # Message suggestions
        self._suggestion_registry["send_message"] = [
            Suggestion(
                "Send another message",
                SuggestionType.FOLLOW_UP,
                "send_message",
                priority=3,
            ),
            Suggestion(
                "View sent messages",
                SuggestionType.FOLLOW_UP,
                "query_messages",
                priority=2,
            ),
            Suggestion("Call instead", SuggestionType.ALTERNATIVE, "make_call", priority=1),
        ]

        # Music suggestions
        self._suggestion_registry["play_music"] = [
            Suggestion("Play next song", SuggestionType.FOLLOW_UP, "play_music", priority=3),
            Suggestion("Pause music", SuggestionType.FOLLOW_UP, "pause_music", priority=2),
            Suggestion("Add to playlist", SuggestionType.FOLLOW_UP, "add_to_playlist", priority=1),
        ]

        # Reminder suggestions
        self._suggestion_registry["create_reminder"] = [
            Suggestion(
                "View all reminders",
                SuggestionType.FOLLOW_UP,
                "query_reminders",
                priority=3,
            ),
            Suggestion(
                "Set another reminder",
                SuggestionType.FOLLOW_UP,
                "create_reminder",
                priority=2,
            ),
            Suggestion("Edit reminder", SuggestionType.FOLLOW_UP, "edit_reminder", priority=1),
        ]

        # Time suggestions
        self._suggestion_registry["query_time"] = [
            Suggestion("Set alarm", SuggestionType.FOLLOW_UP, "set_alarm", priority=3),
            Suggestion("Check timezone", SuggestionType.FOLLOW_UP, "query_timezone", priority=2),
            Suggestion("World clock", SuggestionType.FOLLOW_UP, "query_world_clock", priority=1),
        ]

        # Calendar suggestions
        self._suggestion_registry["query_calendar"] = [
            Suggestion("Create event", SuggestionType.FOLLOW_UP, "create_event", priority=3),
            Suggestion("View tomorrow", SuggestionType.FOLLOW_UP, "query_calendar", priority=2),
            Suggestion("Check conflicts", SuggestionType.FOLLOW_UP, "check_conflicts", priority=1),
        ]

        # Smart home suggestions
        self._suggestion_registry["control_smart_home"] = [
            Suggestion(
                "Check device status",
                SuggestionType.FOLLOW_UP,
                "query_device_status",
                priority=3,
            ),
            Suggestion(
                "Create automation",
                SuggestionType.FOLLOW_UP,
                "create_automation",
                priority=2,
            ),
            Suggestion("View all devices", SuggestionType.FOLLOW_UP, "list_devices", priority=1),
        ]

    def _load_related_capabilities(self) -> None:
        """Load related capability mappings."""
        # Timer related to alarm and reminder
        self._related_capabilities["set_timer"] = {"set_alarm", "create_reminder"}

        # Weather related to calendar and location
        self._related_capabilities["query_weather"] = {"query_calendar", "get_directions"}

        # Message related to call and email
        self._related_capabilities["send_message"] = {"make_call", "send_email"}

        # Music related to podcast and radio
        self._related_capabilities["play_music"] = {"play_podcast", "play_radio"}

        # Reminder related to timer and calendar
        self._related_capabilities["create_reminder"] = {"set_timer", "create_event"}

        # Calendar related to reminder and weather
        self._related_capabilities["query_calendar"] = {"create_reminder", "query_weather"}

        # Smart home related to automation
        self._related_capabilities["control_smart_home"] = {
            "create_automation",
            "query_device_status",
        }
