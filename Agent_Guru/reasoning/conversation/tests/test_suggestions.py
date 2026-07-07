"""
Tests for proactive suggestion generation.
"""

from datetime import datetime, timezone

import pytest

from Agent_Guru.reasoning.conversation.suggestions import (
    ProactiveSuggestionGenerator,
    Suggestion,
    SuggestionCategory,
)
from Agent_Guru.reasoning.models.conversation import ConversationState
from Agent_Guru.reasoning.models.result import ExecutionResult
from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskStep, TaskType


class TestProactiveSuggestionGenerator:
    """Test proactive suggestion generator."""

    def test_generate_follow_up_suggestions(self):
        """Test generating follow-up suggestions."""
        generator = ProactiveSuggestionGenerator()

        task = Task(
            goal="Set a timer for 5 minutes",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": 300},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer for 5 minutes",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=1.0,
                    status=TaskStatus.COMPLETED,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.COMPLETED,
            retry_count=0,
        )

        result = ExecutionResult(
            success=True,
            result_data={"timer_id": "123"},
            error=None,
            execution_time=0.5,
            action_id="action_123",
            tool_id="set_timer",
        )

        conversation_state = ConversationState(
            conversation_id="conv_123", user_id="user123", turns=[], last_intent=None
        )

        suggestions = generator.generate_follow_up_suggestions(task, result, conversation_state)

        # May or may not have suggestions depending on task type
        assert isinstance(suggestions, list)  # nosec B101
        if suggestions:
            assert all(s.category == SuggestionCategory.FOLLOW_UP for s in suggestions)  # nosec B101

    def test_generate_proactive_suggestions(self):
        """Test generating proactive suggestions based on patterns."""
        generator = ProactiveSuggestionGenerator()

        conversation_state = ConversationState(
            conversation_id="conv_123", user_id="user123", turns=[], last_intent=None
        )

        current_time = datetime(2024, 1, 1, 10, 0)  # 10 AM

        suggestions = generator.generate_proactive_suggestions(
            "user123", conversation_state, current_time
        )

        # Should return list (may be empty)
        assert isinstance(suggestions, list)  # nosec B101

    def test_generate_alternative_suggestions(self):
        """Test generating alternative suggestions when task fails."""
        generator = ProactiveSuggestionGenerator()

        failed_task = Task(
            goal="Send a message",
            task_type=TaskType.SINGLE_STEP,
            entities={"recipient": "John", "message": "Hello"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Send message",
                    tool_id="send_message",
                    parameters={"recipient": "John", "message": "Hello"},
                    estimated_duration=1.0,
                    status=TaskStatus.FAILED,
                    error="Messaging service unavailable",
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.FAILED,
            retry_count=0,
            error="Messaging service unavailable",
        )

        suggestions = generator.generate_alternative_suggestions(failed_task)

        # May or may not have suggestions depending on task type
        assert isinstance(suggestions, list)  # nosec B101
        if suggestions:
            assert all(s.category == SuggestionCategory.ALTERNATIVE for s in suggestions)  # nosec B101

    def test_rank_suggestions(self):
        """Test ranking suggestions by relevance."""
        generator = ProactiveSuggestionGenerator()

        suggestions = [
            Suggestion(
                description="Set another timer",
                action="set_timer",
                confidence=0.9,
                relevance=0.8,
                category=SuggestionCategory.FOLLOW_UP,
                context={},
            ),
            Suggestion(
                description="Cancel the timer",
                action="cancel_timer",
                confidence=0.7,
                relevance=0.9,
                category=SuggestionCategory.FOLLOW_UP,
                context={},
            ),
            Suggestion(
                description="Check the time",
                action="query_time",
                confidence=0.8,
                relevance=0.6,
                category=SuggestionCategory.FOLLOW_UP,
                context={},
            ),
        ]

        ranked = generator.rank_suggestions(suggestions, max_suggestions=3)

        assert len(ranked) <= 3  # nosec B101
        # Should be sorted by combined score
        if len(ranked) > 1:
            score1 = ranked[0].relevance * 0.6 + ranked[0].confidence * 0.4
            score2 = ranked[1].relevance * 0.6 + ranked[1].confidence * 0.4
            assert score1 >= score2  # nosec B101

    def test_learn_pattern(self):
        """Test learning user patterns."""
        generator = ProactiveSuggestionGenerator()

        # Learn a pattern
        generator.learn_pattern("user123", "set_timer", {"time_of_day": 10, "day_of_week": 0})

        # Check pattern was stored
        assert "user123" in generator.user_patterns  # nosec B101
        assert len(generator.user_patterns["user123"]) == 1  # nosec B101
        assert generator.user_patterns["user123"][0]["action"] == "set_timer"  # nosec B101

    def test_learn_pattern_updates_frequency(self):
        """Test that learning same pattern updates frequency."""
        generator = ProactiveSuggestionGenerator()

        # Learn same pattern twice
        context = {"time_of_day": 10, "day_of_week": 0}
        generator.learn_pattern("user123", "set_timer", context)
        generator.learn_pattern("user123", "set_timer", context)

        # Should have one pattern with frequency 2
        assert len(generator.user_patterns["user123"]) == 1  # nosec B101
        assert generator.user_patterns["user123"][0]["frequency"] == 2  # nosec B101


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
