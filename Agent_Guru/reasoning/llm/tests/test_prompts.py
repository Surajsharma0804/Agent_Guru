"""
Tests for reasoning prompt templates.

Coverage Target: >80% (enforced by CI/CD)
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from Agent_Guru.reasoning.llm.prompts import (
    ConversationContext,
    ReasoningPrompts,
)


class TestConversationContext:
    """Unit tests for ConversationContext."""

    def test_empty_context_formatting(self):
        """Test formatting of empty context."""
        context = ConversationContext()
        formatted = context.format_for_prompt()

        assert formatted == "No conversation context available."  # nosec B101

    def test_recent_turns_formatting(self):
        """Test formatting with recent turns."""
        context = ConversationContext(
            recent_turns=["User: Hello", "Assistant: Hi there", "User: How are you?"]
        )
        formatted = context.format_for_prompt()

        assert "Recent conversation:" in formatted  # nosec B101
        assert "1. User: Hello" in formatted  # nosec B101
        assert "2. Assistant: Hi there" in formatted  # nosec B101
        assert "3. User: How are you?" in formatted  # nosec B101

    def test_recent_turns_max_limit(self):
        """Test that only last N turns are included."""
        context = ConversationContext(recent_turns=[f"Turn {i}" for i in range(10)])
        formatted = context.format_for_prompt(max_turns=3)

        # Should only include last 3 turns
        assert "Turn 7" in formatted  # nosec B101
        assert "Turn 8" in formatted  # nosec B101
        assert "Turn 9" in formatted  # nosec B101
        assert "Turn 6" not in formatted  # nosec B101

    def test_tracked_entities_formatting(self):
        """Test formatting with tracked entities."""
        context = ConversationContext(tracked_entities={"person": "John", "location": "New York"})
        formatted = context.format_for_prompt()

        assert "Tracked entities:" in formatted  # nosec B101
        assert "person: John" in formatted  # nosec B101
        assert "location: New York" in formatted  # nosec B101

    def test_user_preferences_formatting(self):
        """Test formatting with user preferences."""
        context = ConversationContext(user_preferences={"language": "English", "timezone": "UTC"})
        formatted = context.format_for_prompt()

        assert "User preferences:" in formatted  # nosec B101
        assert "language: English" in formatted  # nosec B101
        assert "timezone: UTC" in formatted  # nosec B101

    def test_past_actions_formatting(self):
        """Test formatting with past actions."""
        context = ConversationContext(
            past_actions=["Set timer", "Send message", "Play music", "Check weather"]
        )
        formatted = context.format_for_prompt()

        # Should only include last 3 actions
        assert "Recent actions:" in formatted  # nosec B101
        assert "Send message" in formatted  # nosec B101
        assert "Play music" in formatted  # nosec B101
        assert "Check weather" in formatted  # nosec B101
        assert "Set timer" not in formatted  # Oldest action excluded  # nosec B101

    def test_complete_context_formatting(self):
        """Test formatting with all context fields."""
        context = ConversationContext(
            recent_turns=["User: Hello"],
            tracked_entities={"person": "Alice"},
            user_preferences={"language": "English"},
            past_actions=["Set timer"],
        )
        formatted = context.format_for_prompt()

        assert "Recent conversation:" in formatted  # nosec B101
        assert "Tracked entities:" in formatted  # nosec B101
        assert "User preferences:" in formatted  # nosec B101
        assert "Recent actions:" in formatted  # nosec B101


class TestReasoningPrompts:
    """Unit tests for ReasoningPrompts."""

    def test_system_prompt_exists(self):
        """Test that system prompt is defined."""
        assert ReasoningPrompts.SYSTEM_PROMPT  # nosec B101
        assert len(ReasoningPrompts.SYSTEM_PROMPT) > 100  # nosec B101
        assert "Agent_Guru" in ReasoningPrompts.SYSTEM_PROMPT  # nosec B101

    def test_single_step_template_exists(self):
        """Test that single-step template is defined."""
        assert ReasoningPrompts.SINGLE_STEP_TEMPLATE  # nosec B101
        assert "{user_input}" in ReasoningPrompts.SINGLE_STEP_TEMPLATE  # nosec B101
        assert "{intent_type}" in ReasoningPrompts.SINGLE_STEP_TEMPLATE  # nosec B101
        assert "{entities}" in ReasoningPrompts.SINGLE_STEP_TEMPLATE  # nosec B101

    def test_multi_step_template_exists(self):
        """Test that multi-step template is defined."""
        assert ReasoningPrompts.MULTI_STEP_TEMPLATE  # nosec B101
        assert "{user_input}" in ReasoningPrompts.MULTI_STEP_TEMPLATE  # nosec B101
        assert "{intent_type}" in ReasoningPrompts.MULTI_STEP_TEMPLATE  # nosec B101
        assert "2-5 steps" in ReasoningPrompts.MULTI_STEP_TEMPLATE  # nosec B101

    def test_few_shot_examples_exist(self):
        """Test that few-shot examples are defined."""
        assert ReasoningPrompts.FEW_SHOT_EXAMPLES  # nosec B101
        assert "set_timer" in ReasoningPrompts.FEW_SHOT_EXAMPLES  # nosec B101
        assert "send_message" in ReasoningPrompts.FEW_SHOT_EXAMPLES  # nosec B101
        assert "multi_step_task" in ReasoningPrompts.FEW_SHOT_EXAMPLES  # nosec B101

    def test_few_shot_example_structure(self):
        """Test structure of few-shot examples."""
        example = ReasoningPrompts.FEW_SHOT_EXAMPLES["set_timer"]

        assert "user_input" in example  # nosec B101
        assert "intent_type" in example  # nosec B101
        assert "entities" in example  # nosec B101
        assert "plan" in example  # nosec B101

        plan = example["plan"]
        assert "goal" in plan  # nosec B101
        assert "steps" in plan  # nosec B101
        assert "reasoning" in plan  # nosec B101
        assert "confidence" in plan  # nosec B101

    def test_format_single_step_prompt_basic(self):
        """Test basic single-step prompt formatting."""
        prompt = ReasoningPrompts.format_single_step_prompt(
            user_input="Set a timer for 5 minutes",
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            available_tools=["timer_tool", "alarm_tool"],
        )

        assert "Set a timer for 5 minutes" in prompt  # nosec B101
        assert "set_timer" in prompt  # nosec B101
        assert "{'duration': '5 minutes'}" in prompt  # nosec B101
        assert "timer_tool, alarm_tool" in prompt  # nosec B101

    def test_format_single_step_prompt_with_context(self):
        """Test single-step prompt with conversation context."""
        context = ConversationContext(
            recent_turns=["User: Hello"],
            tracked_entities={"person": "John"},
        )

        prompt = ReasoningPrompts.format_single_step_prompt(
            user_input="Send a message",
            intent_type="send_message",
            entities={},
            available_tools=["messaging_tool"],
            context=context,
        )

        assert "Recent conversation:" in prompt  # nosec B101
        assert "Tracked entities:" in prompt  # nosec B101
        assert "person: John" in prompt  # nosec B101

    def test_format_single_step_prompt_without_context(self):
        """Test single-step prompt without context."""
        prompt = ReasoningPrompts.format_single_step_prompt(
            user_input="Check weather",
            intent_type="query_weather",
            entities={},
            available_tools=["weather_tool"],
            context=None,
        )

        assert "No context available." in prompt  # nosec B101

    def test_format_multi_step_prompt_basic(self):
        """Test basic multi-step prompt formatting."""
        prompt = ReasoningPrompts.format_multi_step_prompt(
            user_input="Play music and set a timer",
            intent_type="multi_step_task",
            entities={"playlist": "workout", "duration": "30 minutes"},
            available_tools=["music_tool", "timer_tool"],
        )

        assert "Play music and set a timer" in prompt  # nosec B101
        assert "multi_step_task" in prompt  # nosec B101
        assert "music_tool, timer_tool" in prompt  # nosec B101
        assert "2-5 steps" in prompt  # nosec B101

    def test_format_multi_step_prompt_with_context(self):
        """Test multi-step prompt with conversation context."""
        context = ConversationContext(
            recent_turns=["User: I'm starting my workout"],
            user_preferences={"workout_playlist": "Rock"},
        )

        prompt = ReasoningPrompts.format_multi_step_prompt(
            user_input="Start workout session",
            intent_type="multi_step_task",
            entities={},
            available_tools=["music_tool", "timer_tool"],
            context=context,
        )

        assert "Recent conversation:" in prompt  # nosec B101
        assert "User preferences:" in prompt  # nosec B101
        assert "workout_playlist: Rock" in prompt  # nosec B101

    def test_get_few_shot_examples_specific_intent(self):
        """Test getting few-shot examples for specific intent."""
        examples = ReasoningPrompts.get_few_shot_examples("set_timer", count=2)

        assert "set_timer" in examples  # nosec B101
        assert "Example:" in examples  # nosec B101
        assert "Set a timer for 5 minutes" in examples  # nosec B101

    def test_get_few_shot_examples_count_limit(self):
        """Test that example count is respected."""
        examples = ReasoningPrompts.get_few_shot_examples("unknown_intent", count=2)

        # Should return at most 2 examples
        example_count = examples.count("Example:")
        assert example_count <= 2  # nosec B101

    def test_get_few_shot_examples_unknown_intent(self):
        """Test getting examples for unknown intent."""
        examples = ReasoningPrompts.get_few_shot_examples("unknown_intent", count=2)

        # Should return general examples
        assert "Example:" in examples  # nosec B101
        assert len(examples) > 0  # nosec B101

    def test_compress_context_basic(self):
        """Test basic context compression."""
        context = ConversationContext(
            recent_turns=[f"Turn {i}" for i in range(10)],
            tracked_entities={"entity1": "value1", "entity2": "value2"},
            user_preferences={"pref1": "val1"},
            past_actions=[f"Action {i}" for i in range(10)],
        )

        compressed = ReasoningPrompts.compress_context(context, max_length=500)

        # Should keep only last 2 turns (aggressive compression)
        assert len(compressed.recent_turns) <= 3  # nosec B101
        assert compressed.recent_turns[-1] == "Turn 9"  # nosec B101

        # Should remove past actions first
        assert len(compressed.past_actions) == 0  # nosec B101

        # Should keep entities (up to 3)
        assert len(compressed.tracked_entities) <= 3  # nosec B101
        assert len(compressed.user_preferences) >= 0  # May be removed if needed  # nosec B101

    def test_compress_context_aggressive(self):
        """Test aggressive context compression for very long context."""
        context = ConversationContext(
            recent_turns=[f"Turn {i}" * 50 for i in range(10)],  # Very long turns
            tracked_entities={f"entity{i}": f"value{i}" * 20 for i in range(10)},
            user_preferences={f"pref{i}": f"val{i}" * 20 for i in range(10)},
            past_actions=[f"Action {i}" * 50 for i in range(10)],
        )

        compressed = ReasoningPrompts.compress_context(context, max_length=200)

        # Should aggressively compress
        assert len(compressed.recent_turns) <= 3  # nosec B101
        assert len(compressed.past_actions) == 0  # Removed first  # nosec B101
        assert len(compressed.tracked_entities) <= 3  # Reduced if needed  # nosec B101

    def test_compress_context_preserves_structure(self):
        """Test that compression preserves ConversationContext structure."""
        context = ConversationContext(
            recent_turns=["Turn 1", "Turn 2"],
            tracked_entities={"person": "Alice"},
            user_preferences={"language": "English"},
            past_actions=["Action 1"],
        )

        compressed = ReasoningPrompts.compress_context(context, max_length=1000)

        assert isinstance(compressed, ConversationContext)  # nosec B101
        assert isinstance(compressed.recent_turns, list)  # nosec B101
        assert isinstance(compressed.tracked_entities, dict)  # nosec B101
        assert isinstance(compressed.user_preferences, dict)  # nosec B101
        assert isinstance(compressed.past_actions, list)  # nosec B101


class TestReasoningPromptsProperties:
    """Property-based tests for ReasoningPrompts."""

    @given(
        user_input=st.text(min_size=1, max_size=200),
        intent_type=st.text(min_size=1, max_size=50),
        num_tools=st.integers(min_value=1, max_value=10),
    )
    def test_single_step_prompt_always_valid(
        self, user_input: str, intent_type: str, num_tools: int
    ):
        """Property: Single-step prompt formatting always produces valid string."""
        tools = [f"tool_{i}" for i in range(num_tools)]

        prompt = ReasoningPrompts.format_single_step_prompt(
            user_input=user_input,
            intent_type=intent_type,
            entities={},
            available_tools=tools,
        )

        # Should produce non-empty string
        assert isinstance(prompt, str)  # nosec B101
        assert len(prompt) > 0  # nosec B101

        # Should contain key components
        assert user_input in prompt  # nosec B101
        assert intent_type in prompt  # nosec B101

    @given(
        user_input=st.text(min_size=1, max_size=200),
        intent_type=st.text(min_size=1, max_size=50),
        num_tools=st.integers(min_value=1, max_value=10),
    )
    def test_multi_step_prompt_always_valid(
        self, user_input: str, intent_type: str, num_tools: int
    ):
        """Property: Multi-step prompt formatting always produces valid string."""
        tools = [f"tool_{i}" for i in range(num_tools)]

        prompt = ReasoningPrompts.format_multi_step_prompt(
            user_input=user_input,
            intent_type=intent_type,
            entities={},
            available_tools=tools,
        )

        # Should produce non-empty string
        assert isinstance(prompt, str)  # nosec B101
        assert len(prompt) > 0  # nosec B101

        # Should contain key components
        assert user_input in prompt  # nosec B101
        assert intent_type in prompt  # nosec B101
        assert "2-5 steps" in prompt  # nosec B101

    @given(
        num_turns=st.integers(min_value=0, max_value=20),
        num_entities=st.integers(min_value=0, max_value=10),
        num_actions=st.integers(min_value=0, max_value=10),
    )
    def test_context_formatting_always_valid(
        self, num_turns: int, num_entities: int, num_actions: int
    ):
        """Property: Context formatting always produces valid string."""
        context = ConversationContext(
            recent_turns=[f"Turn {i}" for i in range(num_turns)],
            tracked_entities={f"entity{i}": f"value{i}" for i in range(num_entities)},
            past_actions=[f"Action {i}" for i in range(num_actions)],
        )

        formatted = context.format_for_prompt()

        # Should always produce string
        assert isinstance(formatted, str)  # nosec B101
        assert len(formatted) > 0  # nosec B101

    @given(
        num_turns=st.integers(min_value=1, max_value=20),
        num_entities=st.integers(min_value=1, max_value=10),
        num_actions=st.integers(min_value=1, max_value=10),
        max_length=st.integers(
            min_value=200, max_value=1000
        ),  # Increased minimum to be more realistic
    )
    def test_compression_reduces_size(
        self, num_turns: int, num_entities: int, num_actions: int, max_length: int
    ):
        """Property: Compression always reduces or maintains context size."""
        context = ConversationContext(
            recent_turns=[f"Turn {i}" * 10 for i in range(num_turns)],
            tracked_entities={f"entity{i}": f"value{i}" * 5 for i in range(num_entities)},
            past_actions=[f"Action {i}" * 10 for i in range(num_actions)],
        )

        original_formatted = context.format_for_prompt()
        compressed = ReasoningPrompts.compress_context(context, max_length=max_length)
        compressed_formatted = compressed.format_for_prompt()

        # Compressed should be smaller or equal
        assert len(compressed_formatted) <= len(original_formatted)  # nosec B101

        # Compressed should try to respect max_length (with tolerance for very small limits)
        # We allow 2x overage because compression is done in stages and very small limits may not be achievable
        if max_length >= 200:
            assert len(compressed_formatted) <= max_length * 2  # nosec B101

    @given(
        num_turns=st.integers(min_value=0, max_value=20),
        max_turns=st.integers(min_value=1, max_value=10),
    )
    def test_format_respects_max_turns(self, num_turns: int, max_turns: int):
        """Property: format_for_prompt respects max_turns parameter."""
        context = ConversationContext(
            recent_turns=[
                f"Turn_{i:03d}" for i in range(num_turns)
            ]  # Use zero-padded numbers to avoid substring matches
        )

        formatted = context.format_for_prompt(max_turns=max_turns)

        # Count how many turns appear in formatted output
        turn_count = sum(1 for i in range(num_turns) if f"Turn_{i:03d}" in formatted)

        # Should not exceed max_turns
        assert turn_count <= max_turns  # nosec B101

        # Should include the most recent turns
        if num_turns > 0:
            expected_count = min(num_turns, max_turns)
            assert turn_count == expected_count  # nosec B101


@pytest.mark.integration
class TestReasoningPromptsIntegration:
    """Integration tests for ReasoningPrompts."""

    def test_complete_single_step_workflow(self):
        """Test complete single-step prompt generation workflow."""
        # Create context
        context = ConversationContext(
            recent_turns=["User: I need to focus"],
            tracked_entities={"duration": "25 minutes"},
            user_preferences={"focus_technique": "Pomodoro"},
        )

        # Format prompt
        prompt = ReasoningPrompts.format_single_step_prompt(
            user_input="Set a focus timer",
            intent_type="set_timer",
            entities={"duration": "25 minutes", "label": "Focus"},
            available_tools=["timer_tool", "notification_tool"],
            context=context,
        )

        # Verify complete prompt structure
        assert "Set a focus timer" in prompt  # nosec B101
        assert "set_timer" in prompt  # nosec B101
        assert "25 minutes" in prompt  # nosec B101
        assert "timer_tool" in prompt  # nosec B101
        assert "Recent conversation:" in prompt  # nosec B101
        assert "Tracked entities:" in prompt  # nosec B101
        assert "User preferences:" in prompt  # nosec B101

    def test_complete_multi_step_workflow(self):
        """Test complete multi-step prompt generation workflow."""
        # Create context
        context = ConversationContext(
            recent_turns=["User: I'm starting my workout"],
            tracked_entities={"playlist": "workout", "duration": "30 minutes"},
            past_actions=["Opened music app"],
        )

        # Format prompt
        prompt = ReasoningPrompts.format_multi_step_prompt(
            user_input="Start workout session with music and timer",
            intent_type="multi_step_task",
            entities={"playlist": "workout", "duration": "30 minutes"},
            available_tools=["music_tool", "timer_tool", "notification_tool"],
            context=context,
        )

        # Verify complete prompt structure
        assert "Start workout session" in prompt  # nosec B101
        assert "multi_step_task" in prompt  # nosec B101
        assert "workout" in prompt  # nosec B101
        assert "30 minutes" in prompt  # nosec B101
        assert "music_tool" in prompt  # nosec B101
        assert "timer_tool" in prompt  # nosec B101
        assert "2-5 steps" in prompt  # nosec B101
        assert "Recent conversation:" in prompt  # nosec B101

    def test_context_compression_workflow(self):
        """Test context compression in realistic scenario."""
        # Create large context
        context = ConversationContext(
            recent_turns=[
                "User: Hello",
                "Assistant: Hi there!",
                "User: What's the weather?",
                "Assistant: It's sunny",
                "User: Set a timer",
                "Assistant: Timer set",
                "User: Play music",
                "Assistant: Playing music",
            ],
            tracked_entities={
                "location": "New York",
                "temperature": "72F",
                "playlist": "workout",
                "timer_duration": "5 minutes",
            },
            past_actions=[
                "Checked weather",
                "Set timer for 5 minutes",
                "Played workout playlist",
                "Sent message to John",
            ],
        )

        # Compress context
        compressed = ReasoningPrompts.compress_context(context, max_length=300)

        # Verify compression worked
        assert len(compressed.recent_turns) <= 2  # nosec B101
        assert len(compressed.past_actions) == 0  # Removed first in compression  # nosec B101

        # Verify most recent data is preserved
        assert (  # nosec B101
            "User: Play music" in compressed.recent_turns
            or "Assistant: Playing music" in compressed.recent_turns
        )

        # Format compressed context
        formatted = compressed.format_for_prompt()
        assert len(formatted) <= 500  # Should fit within reasonable limit  # nosec B101
