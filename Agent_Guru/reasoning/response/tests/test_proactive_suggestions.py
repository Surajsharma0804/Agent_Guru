"""
Tests for Proactive Suggestions Generator

Coverage Target: 80%+
Test Types: Unit tests, property-based tests
"""

import time

import pytest

from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
)
from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.models.result import ExecutionResult
from Agent_Guru.reasoning.response.proactive_suggestions import (
    ProactiveSuggestionGenerator,
    Suggestion,
    SuggestionAcceptance,
    SuggestionType,
)


class TestSuggestion:
    """Test Suggestion data class."""

    def test_suggestion_creation(self):
        """Test creating a suggestion."""
        suggestion = Suggestion(
            text="Set another timer",
            suggestion_type=SuggestionType.FOLLOW_UP,
            intent_type="set_timer",
            confidence=0.9,
            priority=3,
        )

        assert suggestion.text == "Set another timer"  # nosec B101
        assert suggestion.suggestion_type == SuggestionType.FOLLOW_UP  # nosec B101
        assert suggestion.intent_type == "set_timer"  # nosec B101
        assert suggestion.confidence == 0.9  # nosec B101
        assert suggestion.priority == 3  # nosec B101

    def test_suggestion_validation_confidence(self):
        """Test suggestion confidence validation."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            Suggestion(text="Test", suggestion_type=SuggestionType.FOLLOW_UP, confidence=1.5)

    def test_suggestion_validation_empty_text(self):
        """Test suggestion empty text validation."""
        with pytest.raises(ValueError, match="Suggestion text cannot be empty"):
            Suggestion(text="", suggestion_type=SuggestionType.FOLLOW_UP)


class TestSuggestionAcceptance:
    """Test SuggestionAcceptance data class."""

    def test_acceptance_creation(self):
        """Test creating acceptance record."""
        acceptance = SuggestionAcceptance(
            suggestion_text="Set another timer",
            suggestion_type=SuggestionType.FOLLOW_UP,
            intent_type="set_timer",
            was_accepted=True,
            timestamp=time.time(),
        )

        assert acceptance.suggestion_text == "Set another timer"  # nosec B101
        assert acceptance.was_accepted is True  # nosec B101
        assert acceptance.suggestion_type == SuggestionType.FOLLOW_UP  # nosec B101


class TestProactiveSuggestionGenerator:
    """Test ProactiveSuggestionGenerator."""

    @pytest.fixture
    def generator(self):
        """Create generator instance."""
        return ProactiveSuggestionGenerator(max_suggestions=3)

    @pytest.fixture
    def timer_intent(self):
        """Create timer intent."""
        return Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(entity_type="duration", value="5 minutes", raw_text="5 minutes")
            },
            confidence=0.95,
            requires_reasoning=False,
            original_input="Set a timer for 5 minutes",
        )

    @pytest.fixture
    def success_result(self):
        """Create successful execution result."""
        return ExecutionResult(
            success=True,
            result_data={"timer": "5 minutes"},
            error=None,
            execution_time=0.5,
            action_id="action_123",
            tool_id="set_timer",
        )

    @pytest.fixture
    def error_result(self):
        """Create error execution result."""
        return ExecutionResult(
            success=False,
            result_data=None,
            error="Timer service unavailable",
            execution_time=0.2,
            action_id="action_456",
            tool_id="set_timer",
        )

    def test_generator_initialization(self, generator):
        """Test generator initialization."""
        assert generator.max_suggestions == 3  # nosec B101
        assert len(generator._suggestion_registry) > 0  # nosec B101
        assert len(generator._related_capabilities) > 0  # nosec B101

    def test_generate_suggestions_success(self, generator, timer_intent, success_result):
        """Test generating suggestions for successful execution."""
        suggestions = generator.generate_suggestions(timer_intent, success_result)

        assert isinstance(suggestions, list)  # nosec B101
        assert len(suggestions) <= 3  # nosec B101
        assert all(isinstance(s, str) for s in suggestions)  # nosec B101

        # Should include timer-related suggestions
        assert any("timer" in s.lower() for s in suggestions)  # nosec B101

    def test_generate_suggestions_error(self, generator, timer_intent, error_result):
        """Test generating suggestions for error execution."""
        suggestions = generator.generate_suggestions(timer_intent, error_result)

        assert isinstance(suggestions, list)  # nosec B101
        assert len(suggestions) <= 3  # nosec B101

        # Should include error recovery suggestions
        assert any("try again" in s.lower() or "retry" in s.lower() for s in suggestions)  # nosec B101

    def test_generate_suggestions_with_conversation_state(
        self, generator, timer_intent, success_result
    ):
        """Test generating suggestions with conversation context."""
        # Create conversation state
        state = ConversationState(
            conversation_id="conv_123", user_id="user_456", turns=[], entities={}
        )

        suggestions = generator.generate_suggestions(
            timer_intent, success_result, conversation_state=state
        )

        assert isinstance(suggestions, list)  # nosec B101
        assert len(suggestions) <= 3  # nosec B101

    def test_generate_suggestions_with_user_preferences(
        self, generator, timer_intent, success_result
    ):
        """Test generating suggestions with user preferences."""
        user_prefs = {"show_advanced_suggestions": True, "verbosity": "detailed"}

        suggestions = generator.generate_suggestions(
            timer_intent, success_result, user_preferences=user_prefs
        )

        assert isinstance(suggestions, list)  # nosec B101
        assert len(suggestions) <= 3  # nosec B101

    def test_track_acceptance(self, generator):
        """Test tracking suggestion acceptance."""
        suggestion_text = "Set another timer"

        # Track acceptance
        generator.track_acceptance(
            suggestion_text=suggestion_text,
            was_accepted=True,
            suggestion_type=SuggestionType.FOLLOW_UP,
            intent_type="set_timer",
        )

        # Check acceptance was recorded
        assert suggestion_text in generator._acceptance_history  # nosec B101
        assert len(generator._acceptance_history[suggestion_text]) == 1  # nosec B101
        assert generator._acceptance_history[suggestion_text][0].was_accepted is True  # nosec B101

    def test_track_rejection(self, generator):
        """Test tracking suggestion rejection."""
        suggestion_text = "Cancel timer"

        # Track rejection
        generator.track_acceptance(
            suggestion_text=suggestion_text,
            was_accepted=False,
            suggestion_type=SuggestionType.FOLLOW_UP,
            intent_type="cancel_timer",
        )

        # Check rejection was recorded
        assert suggestion_text in generator._acceptance_history  # nosec B101
        assert generator._acceptance_history[suggestion_text][0].was_accepted is False  # nosec B101

    def test_get_acceptance_rate(self, generator):
        """Test getting acceptance rate."""
        suggestion_text = "Set another timer"

        # Track multiple acceptances
        for i in range(7):
            generator.track_acceptance(
                suggestion_text=suggestion_text,
                was_accepted=True,
                suggestion_type=SuggestionType.FOLLOW_UP,
            )

        # Track some rejections
        for i in range(3):
            generator.track_acceptance(
                suggestion_text=suggestion_text,
                was_accepted=False,
                suggestion_type=SuggestionType.FOLLOW_UP,
            )

        # Check acceptance rate
        rate = generator.get_acceptance_rate(suggestion_text)
        assert rate == 0.7  # 7 out of 10  # nosec B101

    def test_get_acceptance_rate_unknown_suggestion(self, generator):
        """Test getting acceptance rate for unknown suggestion."""
        rate = generator.get_acceptance_rate("Unknown suggestion")
        assert rate == 0.5  # Default  # nosec B101

    def test_get_acceptance_stats(self, generator):
        """Test getting overall acceptance statistics."""
        # Track some acceptances
        generator.track_acceptance("Suggestion 1", True, SuggestionType.FOLLOW_UP)
        generator.track_acceptance("Suggestion 2", False, SuggestionType.RELATED)
        generator.track_acceptance("Suggestion 3", True, SuggestionType.FOLLOW_UP)

        stats = generator.get_acceptance_stats()

        assert "overall" in stats  # nosec B101
        assert "by_type" in stats  # nosec B101
        assert "top_suggestions" in stats  # nosec B101

        assert stats["overall"]["total_shown"] == 3  # nosec B101
        assert stats["overall"]["total_accepted"] == 2  # nosec B101
        assert stats["overall"]["acceptance_rate"] == pytest.approx(0.666, rel=0.01)  # nosec B101

    def test_follow_up_suggestions(self, generator, timer_intent, success_result):
        """Test follow-up suggestion generation."""
        suggestions = generator._generate_follow_up_suggestions(timer_intent, success_result)

        assert isinstance(suggestions, list)  # nosec B101
        assert all(isinstance(s, Suggestion) for s in suggestions)  # nosec B101
        assert all(s.suggestion_type == SuggestionType.FOLLOW_UP for s in suggestions)  # nosec B101

    def test_related_suggestions(self, generator, timer_intent):
        """Test related capability suggestion generation."""
        suggestions = generator._generate_related_suggestions(timer_intent)

        assert isinstance(suggestions, list)  # nosec B101
        # Timer is related to alarm and reminder
        if suggestions:
            assert all(isinstance(s, Suggestion) for s in suggestions)  # nosec B101
            assert all(s.suggestion_type == SuggestionType.RELATED for s in suggestions)  # nosec B101

    def test_contextual_suggestions(self, generator, timer_intent):
        """Test contextual suggestion generation."""
        # Create conversation state with repeated actions
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[
                ConversationTurn(
                    turn_id="turn_1",
                    turn_number=1,
                    user_input="Set timer for 5 minutes",
                    intent=timer_intent,
                    response="Timer set",
                    timestamp=time.time(),
                ),
                ConversationTurn(
                    turn_id="turn_2",
                    turn_number=2,
                    user_input="Set timer for 10 minutes",
                    intent=timer_intent,
                    response="Timer set",
                    timestamp=time.time(),
                ),
            ],
            entities={},
        )

        suggestions = generator._generate_contextual_suggestions(timer_intent, state)

        assert isinstance(suggestions, list)  # nosec B101
        if suggestions:
            assert all(isinstance(s, Suggestion) for s in suggestions)  # nosec B101
            assert all(s.suggestion_type == SuggestionType.CONTEXTUAL for s in suggestions)  # nosec B101

    def test_behavioral_suggestions(self, generator, timer_intent):
        """Test behavioral suggestion generation."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
            user_preferences={"verbosity": "detailed"},
        )

        suggestions = generator._generate_behavioral_suggestions(timer_intent, state)

        assert isinstance(suggestions, list)  # nosec B101
        if suggestions:
            assert all(isinstance(s, Suggestion) for s in suggestions)  # nosec B101
            assert all(s.suggestion_type == SuggestionType.BEHAVIORAL for s in suggestions)  # nosec B101

    def test_error_recovery_suggestions(self, generator, timer_intent, error_result):
        """Test error recovery suggestion generation."""
        suggestions = generator._generate_error_recovery_suggestions(timer_intent, error_result)

        assert isinstance(suggestions, list)  # nosec B101
        assert len(suggestions) > 0  # nosec B101
        assert all(isinstance(s, Suggestion) for s in suggestions)  # nosec B101

        # Should include retry suggestion
        assert any("try again" in s.text.lower() for s in suggestions)  # nosec B101

    def test_suggestion_ranking(self, generator, timer_intent):
        """Test suggestion ranking."""
        candidates = [
            Suggestion("Low priority", SuggestionType.FOLLOW_UP, priority=1, confidence=0.5),
            Suggestion("High priority", SuggestionType.FOLLOW_UP, priority=3, confidence=0.9),
            Suggestion("Medium priority", SuggestionType.FOLLOW_UP, priority=2, confidence=0.7),
        ]

        ranked = generator._rank_suggestions(candidates, timer_intent, {})

        assert len(ranked) == 3  # nosec B101
        # High priority should be first
        assert ranked[0].text == "High priority"  # nosec B101
        assert ranked[2].text == "Low priority"  # nosec B101

    def test_suggestion_score_calculation(self, generator, timer_intent):
        """Test suggestion score calculation."""
        suggestion = Suggestion(
            text="Test suggestion",
            suggestion_type=SuggestionType.FOLLOW_UP,
            confidence=0.8,
            priority=2,
        )

        score = generator._calculate_suggestion_score(suggestion, timer_intent, {})

        assert isinstance(score, float)  # nosec B101
        assert score > 0  # nosec B101

    def test_max_suggestions_limit(self, generator, timer_intent, success_result):
        """Test that max suggestions limit is respected."""
        suggestions = generator.generate_suggestions(timer_intent, success_result)

        assert len(suggestions) <= generator.max_suggestions  # nosec B101

    def test_empty_suggestions_on_error(self, generator):
        """Test that empty list is returned on error."""
        # Create valid intent with unknown type
        invalid_intent = Intent(
            intent_type=IntentType.UNKNOWN,
            entities={},
            confidence=0.5,
            requires_reasoning=False,
            original_input="Unknown command",
        )

        result = ExecutionResult(
            success=True,
            result_data={},
            error=None,
            execution_time=0.1,
            action_id="action_789",
            tool_id="unknown_tool",
        )

        suggestions = generator.generate_suggestions(invalid_intent, result)

        # Should return empty list or handle gracefully
        assert isinstance(suggestions, list)  # nosec B101

    def test_suggestion_types_coverage(self, generator):
        """Test that all suggestion types are covered."""
        # Check that default suggestions include various types
        all_suggestions = []
        for suggestions in generator._suggestion_registry.values():
            all_suggestions.extend(suggestions)

        types_present = {s.suggestion_type for s in all_suggestions}

        # Should have at least FOLLOW_UP and ALTERNATIVE
        assert SuggestionType.FOLLOW_UP in types_present  # nosec B101
        assert SuggestionType.ALTERNATIVE in types_present  # nosec B101

    def test_related_capabilities_mapping(self, generator):
        """Test related capabilities are properly mapped."""
        # Timer should be related to alarm and reminder
        timer_related = generator._related_capabilities.get("set_timer", set())
        assert "set_alarm" in timer_related or "create_reminder" in timer_related  # nosec B101

    def test_acceptance_tracking_with_context(self, generator):
        """Test acceptance tracking with context."""
        context = {"user_id": "user_123", "conversation_id": "conv_456"}

        generator.track_acceptance(
            "Test suggestion", True, SuggestionType.FOLLOW_UP, context=context
        )

        acceptance = generator._acceptance_history["Test suggestion"][0]
        assert acceptance.context == context  # nosec B101

    def test_preference_score_update(self, generator):
        """Test preference score updates correctly."""
        suggestion_text = "Test suggestion"

        # Track 8 acceptances and 2 rejections
        for _ in range(8):
            generator.track_acceptance(suggestion_text, True, SuggestionType.FOLLOW_UP)
        for _ in range(2):
            generator.track_acceptance(suggestion_text, False, SuggestionType.FOLLOW_UP)

        # Check preference score
        score = generator._preference_scores[suggestion_text]
        assert score == 0.8  # 8/10  # nosec B101

    def test_top_suggestions(self, generator):
        """Test getting top suggestions."""
        # Track various suggestions
        generator.track_acceptance("Suggestion A", True, SuggestionType.FOLLOW_UP)
        generator.track_acceptance("Suggestion A", True, SuggestionType.FOLLOW_UP)
        generator.track_acceptance("Suggestion B", True, SuggestionType.FOLLOW_UP)
        generator.track_acceptance("Suggestion B", False, SuggestionType.FOLLOW_UP)
        generator.track_acceptance("Suggestion C", False, SuggestionType.FOLLOW_UP)

        top = generator._get_top_suggestions(2)

        assert len(top) <= 2  # nosec B101
        assert all("text" in s and "acceptance_rate" in s for s in top)  # nosec B101
        # Suggestion A should be first (100% acceptance)
        if top:
            assert top[0]["text"] == "Suggestion A"  # nosec B101


class TestProactiveSuggestionsIntegration:
    """Integration tests for proactive suggestions."""

    @pytest.fixture
    def generator(self):
        """Create generator instance."""
        return ProactiveSuggestionGenerator(max_suggestions=3)

    def test_full_workflow(self, generator):
        """Test complete workflow from generation to tracking."""
        # Create intent and result
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(entity_type="duration", value="5 minutes", raw_text="5 minutes")
            },
            confidence=0.95,
            requires_reasoning=False,
            original_input="Set a timer for 5 minutes",
        )

        result = ExecutionResult(
            success=True,
            result_data={"timer": "5 minutes"},
            error=None,
            execution_time=0.5,
            action_id="action_123",
            tool_id="set_timer",
        )

        # Generate suggestions
        suggestions = generator.generate_suggestions(intent, result)

        assert len(suggestions) > 0  # nosec B101

        # Track acceptance for first suggestion
        generator.track_acceptance(
            suggestions[0], True, SuggestionType.FOLLOW_UP, intent_type="set_timer"
        )

        # Get stats
        stats = generator.get_acceptance_stats()

        assert stats["overall"]["total_shown"] == 1  # nosec B101
        assert stats["overall"]["total_accepted"] == 1  # nosec B101

    def test_learning_from_feedback(self, generator):
        """Test that generator learns from user feedback."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(entity_type="duration", value="5 minutes", raw_text="5 minutes")
            },
            confidence=0.95,
            requires_reasoning=False,
            original_input="Set a timer for 5 minutes",
        )

        result = ExecutionResult(
            success=True,
            result_data={"timer": "5 minutes"},
            error=None,
            execution_time=0.5,
            action_id="action_123",
            tool_id="set_timer",
        )

        # Generate suggestions multiple times and track acceptance
        for _ in range(5):
            suggestions = generator.generate_suggestions(intent, result)
            if suggestions:
                # Accept first suggestion
                generator.track_acceptance(suggestions[0], True, SuggestionType.FOLLOW_UP)

        # Check that acceptance rate is tracked
        if suggestions:
            rate = generator.get_acceptance_rate(suggestions[0])
            assert rate > 0.5  # Should have high acceptance rate  # nosec B101
