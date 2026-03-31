"""
Proactive suggestion generation system.

This module generates proactive suggestions based on learned patterns,
context, and user preferences.

Performance Requirements:
- Time Complexity: O(n) where n is number of patterns
- Space Complexity: O(s) where s is number of suggestions
- Latency: <100ms for suggestion generation

Author: Kiro AI
Date: 2024
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from Agent_Guru.reasoning.learning.app_tracker import AppTracker
from Agent_Guru.reasoning.learning.command_tracker import CommandTracker
from Agent_Guru.reasoning.learning.pattern_detector import PatternDetector
from Agent_Guru.reasoning.learning.preference_learner import PreferenceLearner
from Agent_Guru.reasoning.models.behavioral import ProactiveSuggestion


class SuggestionGenerator:
    """
    Generates proactive suggestions based on learned behavior.

    Generates suggestions from:
    - Time-based patterns (morning routine, evening routine)
    - Context-based patterns (location, activity)
    - Predictive patterns (based on history)

    Time Complexity: O(n) where n is patterns
    Space Complexity: O(s) where s is suggestions

    Example:
        >>> generator = SuggestionGenerator("behavioral.db")
        >>> await generator.initialize()
        >>> suggestions = await generator.generate_suggestions(
        ...     "user123", context={"hour": 8, "day": 0}
        ... )
    """

    def __init__(
        self,
        db_path: str = "behavioral.db",
        max_suggestions: int = 5,
        min_confidence: float = 0.6,
    ):
        """
        Initialize suggestion generator.

        Args:
            db_path: Path to SQLite database
            max_suggestions: Maximum suggestions to generate
            min_confidence: Minimum confidence threshold
        """
        self.db_path = db_path
        self.max_suggestions = max_suggestions
        self.min_confidence = min_confidence

        # Initialize components
        self.pattern_detector = PatternDetector(db_path)
        self.command_tracker = CommandTracker(db_path)
        self.app_tracker = AppTracker(db_path)
        self.preference_learner = PreferenceLearner(db_path)

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all components."""
        if self._initialized:
            return

        await self.pattern_detector.initialize()
        await self.command_tracker.initialize()
        await self.app_tracker.initialize()
        await self.preference_learner.initialize()

        self._initialized = True

    async def generate_suggestions(
        self, user_id: str, context: Optional[dict] = None
    ) -> list[ProactiveSuggestion]:
        """
        Generate proactive suggestions for user.

        Time Complexity: O(n) where n is patterns

        Args:
            user_id: User identifier
            context: Current context (hour, day, location, etc.)

        Returns:
            List of ranked suggestions
        """
        if not self._initialized:
            await self.initialize()

        if context is None:
            now = datetime.now(tz=timezone.utc)
            context = {"hour": now.hour, "day": now.weekday()}

        suggestions = []

        # Generate time-based suggestions
        time_suggestions = await self._generate_time_based_suggestions(user_id, context)
        suggestions.extend(time_suggestions)

        # Generate context-based suggestions
        context_suggestions = await self._generate_context_based_suggestions(user_id, context)
        suggestions.extend(context_suggestions)

        # Generate predictive suggestions
        predictive_suggestions = await self._generate_predictive_suggestions(user_id, context)
        suggestions.extend(predictive_suggestions)

        # Rank and filter suggestions
        ranked = self._rank_suggestions(suggestions)
        filtered = [s for s in ranked if s.confidence >= self.min_confidence]

        return filtered[: self.max_suggestions]

    async def _generate_time_based_suggestions(
        self, user_id: str, context: dict
    ) -> list[ProactiveSuggestion]:
        """
        Generate suggestions based on time patterns.

        Args:
            user_id: User identifier
            context: Current context

        Returns:
            List of time-based suggestions
        """
        hour = context.get("hour", datetime.now(tz=timezone.utc).hour)
        day = context.get("day", datetime.now(tz=timezone.utc).weekday())

        # Get patterns for current time
        patterns = await self.pattern_detector.get_patterns_for_time(
            user_id, hour, day, min_confidence=self.min_confidence
        )

        suggestions = []
        for pattern in patterns:
            # Create suggestion
            suggestion = ProactiveSuggestion(
                suggestion_id=str(uuid.uuid4()),
                user_id=user_id,
                suggestion_text=self._format_suggestion_text(pattern.command, "time"),
                command=pattern.command,
                confidence=pattern.confidence,
                relevance=self._calculate_time_relevance(pattern, hour, day),
                based_on=f"time_pattern_{pattern.pattern_type.value}",
                context=context,
                created_at=datetime.now(tz=timezone.utc),
                expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=1),
                metadata={
                    "pattern_id": pattern.pattern_id,
                    "pattern_type": pattern.pattern_type.value,
                    "frequency": pattern.frequency,
                },
            )
            suggestions.append(suggestion)

        return suggestions

    async def _generate_context_based_suggestions(
        self, user_id: str, context: dict
    ) -> list[ProactiveSuggestion]:
        """
        Generate suggestions based on current context.

        Args:
            user_id: User identifier
            context: Current context

        Returns:
            List of context-based suggestions
        """
        suggestions = []

        # Check for location-based suggestions
        if "location" in context:
            # Get frequently used apps at this location
            recent_apps = await self.app_tracker.get_recently_used_apps(user_id, limit=5)

            for app in recent_apps[:2]:  # Top 2 apps
                suggestion = ProactiveSuggestion(
                    suggestion_id=str(uuid.uuid4()),
                    user_id=user_id,
                    suggestion_text=f"Open {app.app_name}?",
                    command=f"open_app:{app.app_id}",
                    confidence=min(0.8, app.open_count / 100.0),
                    relevance=0.7,
                    based_on="location_context",
                    context=context,
                    created_at=datetime.now(tz=timezone.utc),
                    expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
                    metadata={"app_id": app.app_id, "open_count": app.open_count},
                )
                suggestions.append(suggestion)

        # Check for activity-based suggestions
        if "activity" in context:
            context["activity"]
            # Get commands associated with this activity
            # (This would require activity tracking, simplified for now)

        return suggestions

    async def _generate_predictive_suggestions(
        self, user_id: str, context: dict
    ) -> list[ProactiveSuggestion]:
        """
        Generate predictive suggestions based on history.

        Args:
            user_id: User identifier
            context: Current context

        Returns:
            List of predictive suggestions
        """
        suggestions = []

        # Get most frequent commands
        frequent_commands = await self.command_tracker.get_most_frequent_commands(
            user_id, limit=10, min_frequency=5
        )

        # Get recent commands to avoid duplicates
        recent_commands = await self.command_tracker.get_recent_commands(
            user_id, since=datetime.now(tz=timezone.utc) - timedelta(hours=1), limit=10
        )
        recent_command_set = {c.command for c in recent_commands}

        # Suggest frequent commands not recently used
        for cmd_freq in frequent_commands[:3]:
            if cmd_freq.command not in recent_command_set:
                # Calculate confidence based on frequency and success rate
                confidence = min(0.9, cmd_freq.success_rate * (cmd_freq.frequency / 100.0))

                if confidence >= self.min_confidence:
                    suggestion = ProactiveSuggestion(
                        suggestion_id=str(uuid.uuid4()),
                        user_id=user_id,
                        suggestion_text=self._format_suggestion_text(cmd_freq.command, "frequent"),
                        command=cmd_freq.command,
                        confidence=confidence,
                        relevance=0.6,
                        based_on="frequency_pattern",
                        context=context,
                        created_at=datetime.now(tz=timezone.utc),
                        expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=2),
                        metadata={
                            "frequency": cmd_freq.frequency,
                            "success_rate": cmd_freq.success_rate,
                        },
                    )
                    suggestions.append(suggestion)

        return suggestions

    def _rank_suggestions(
        self, suggestions: list[ProactiveSuggestion]
    ) -> list[ProactiveSuggestion]:
        """
        Rank suggestions by combined score.

        Args:
            suggestions: List of suggestions

        Returns:
            Sorted list of suggestions
        """
        # Calculate scores
        for suggestion in suggestions:
            suggestion.metadata["score"] = suggestion.calculate_score()

        # Sort by score (descending)
        return sorted(suggestions, key=lambda s: s.metadata["score"], reverse=True)

    def _calculate_time_relevance(self, pattern, current_hour: int, current_day: int) -> float:
        """
        Calculate time relevance for a pattern.

        Args:
            pattern: Time pattern
            current_hour: Current hour (0-23)
            current_day: Current day (0-6)

        Returns:
            Relevance score (0.0-1.0)
        """
        relevance = 1.0

        # Check time-of-day match
        if pattern.time_of_day is not None:
            hour_diff = abs(current_hour - pattern.time_of_day)
            # Reduce relevance based on time difference
            relevance *= max(0.5, 1.0 - (hour_diff / 24.0))

        # Check day-of-week match
        if pattern.day_of_week is not None:
            if current_day == pattern.day_of_week:
                relevance *= 1.0
            else:
                relevance *= 0.5

        return relevance

    def _format_suggestion_text(self, command: str, suggestion_type: str) -> str:
        """
        Format suggestion text for display.

        Args:
            command: Command to suggest
            suggestion_type: Type of suggestion

        Returns:
            Formatted suggestion text
        """
        # Simple formatting (can be enhanced with templates)
        if suggestion_type == "time":
            return f"It's time for: {command}"
        elif suggestion_type == "frequent":
            return f"You often use: {command}"
        elif suggestion_type == "context":
            return f"Based on your location: {command}"
        else:
            return f"Suggestion: {command}"

    async def record_suggestion_feedback(self, suggestion_id: str, accepted: bool) -> None:
        """
        Record user feedback on suggestion.

        Args:
            suggestion_id: Suggestion identifier
            accepted: Whether user accepted suggestion
        """
        # This would update suggestion acceptance rates
        # and adjust future suggestion generation
        # (Implementation would require suggestion storage)

    async def get_suggestion_stats(self, user_id: str) -> dict:
        """
        Get suggestion statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Statistics dictionary
        """
        # This would return acceptance rates, most accepted types, etc.
        # (Implementation would require suggestion history storage)
        return {
            "user_id": user_id,
            "total_suggestions": 0,
            "accepted_suggestions": 0,
            "acceptance_rate": 0.0,
            "most_accepted_type": None,
        }
