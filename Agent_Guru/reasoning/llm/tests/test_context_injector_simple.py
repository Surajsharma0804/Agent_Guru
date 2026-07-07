"""
Simplified unit tests for ContextInjector.

Tests core functionality without complex fixtures.

Coverage Target: 80%+
"""

import pytest

from Agent_Guru.reasoning.llm.context_injector import ContextExtractionConfig, ContextInjector
from Agent_Guru.reasoning.llm.prompt_templates import PromptContext
from Agent_Guru.reasoning.state.conversation_manager import ConversationStateManager


@pytest.fixture
def conversation_manager():
    """Create conversation manager for testing."""
    return ConversationStateManager(max_conversations=100, inactivity_timeout=3600.0)


@pytest.fixture
def context_injector(conversation_manager):
    """Create context injector for testing."""
    return ContextInjector(conversation_manager)


class TestContextExtractionConfig:
    """Test ContextExtractionConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ContextExtractionConfig()

        assert config.max_turns == 5  # nosec B101
        assert config.max_entities == 10  # nosec B101
        assert config.max_preferences == 5  # nosec B101
        assert config.max_actions == 3  # nosec B101
        assert config.max_memories == 5  # nosec B101
        assert config.max_tokens == 1000  # nosec B101
        assert config.include_world_state is True  # nosec B101

    def test_custom_config(self):
        """Test custom configuration."""
        config = ContextExtractionConfig(
            max_turns=3,
            max_entities=5,
            max_preferences=2,
            max_actions=1,
            max_memories=3,
            max_tokens=500,
            include_world_state=False,
        )

        assert config.max_turns == 3  # nosec B101
        assert config.max_entities == 5  # nosec B101
        assert config.max_preferences == 2  # nosec B101
        assert config.max_actions == 1  # nosec B101
        assert config.max_memories == 3  # nosec B101
        assert config.max_tokens == 500  # nosec B101
        assert config.include_world_state is False  # nosec B101

    def test_invalid_max_turns(self):
        """Test validation of max_turns."""
        with pytest.raises(ValueError, match="max_turns must be >= 1"):
            ContextExtractionConfig(max_turns=0)

    def test_invalid_max_entities(self):
        """Test validation of max_entities."""
        with pytest.raises(ValueError, match="max_entities must be >= 0"):
            ContextExtractionConfig(max_entities=-1)

    def test_invalid_max_tokens(self):
        """Test validation of max_tokens."""
        with pytest.raises(ValueError, match="max_tokens must be >= 100"):
            ContextExtractionConfig(max_tokens=50)


class TestContextInjector:
    """Test ContextInjector."""

    @pytest.mark.asyncio
    async def test_initialization(self, conversation_manager):
        """Test context injector initialization."""
        injector = ContextInjector(conversation_manager)

        assert injector.conversation_manager is conversation_manager  # nosec B101
        assert injector.config is not None  # nosec B101
        assert injector.config.max_turns == 5  # nosec B101

    @pytest.mark.asyncio
    async def test_initialization_with_custom_config(self, conversation_manager):
        """Test initialization with custom config."""
        config = ContextExtractionConfig(max_turns=3)
        injector = ContextInjector(conversation_manager, config)

        assert injector.config.max_turns == 3  # nosec B101

    @pytest.mark.asyncio
    async def test_extract_context_empty_conversation(self, context_injector):
        """Test extracting context from non-existent conversation."""
        context = await context_injector.extract_context("nonexistent_conv")

        assert isinstance(context, PromptContext)  # nosec B101
        assert len(context.recent_turns) == 0  # nosec B101
        assert len(context.tracked_entities) == 0  # nosec B101
        assert len(context.user_preferences) == 0  # nosec B101
        assert len(context.past_actions) == 0  # nosec B101

    @pytest.mark.asyncio
    async def test_inject_context_alias(self, context_injector):
        """Test that inject_context is an alias for extract_context."""
        context1 = await context_injector.extract_context("test_conv")
        context2 = await context_injector.inject_context("test_conv")

        # Should produce same results for empty conversation
        assert len(context1.recent_turns) == len(context2.recent_turns)  # nosec B101
        assert len(context1.tracked_entities) == len(context2.tracked_entities)  # nosec B101

    def test_format_action_with_dict(self, context_injector):
        """Test formatting action from dictionary."""
        action = {"tool_id": "weather_tool", "parameters": {"location": "Seattle", "time": "now"}}

        formatted = context_injector._format_action(action)

        assert "weather_tool" in formatted  # nosec B101
        assert "location=Seattle" in formatted  # nosec B101
        assert "time=now" in formatted  # nosec B101

    def test_format_action_with_object(self, context_injector):
        """Test formatting action from object."""

        class MockAction:
            def __init__(self):
                self.tool_id = "timer_tool"
                self.parameters = {"duration_seconds": 300}

        action = MockAction()
        formatted = context_injector._format_action(action)

        assert "timer_tool" in formatted  # nosec B101
        assert "duration_seconds=300" in formatted  # nosec B101

    def test_format_action_fallback(self, context_injector):
        """Test formatting action fallback."""
        action = "some_action"
        formatted = context_injector._format_action(action)

        assert formatted == "some_action"  # nosec B101

    def test_needs_compression_small_context(self, context_injector):
        """Test that small context doesn't need compression."""
        context = PromptContext(
            recent_turns=["User: Hello", "Agent: Hi"],
            tracked_entities={"location": "Seattle"},
            user_preferences={"unit": "metric"},
        )

        needs_compression = context_injector._needs_compression(context)

        assert needs_compression is False  # nosec B101

    def test_needs_compression_large_context(self, context_injector):
        """Test that large context needs compression."""
        # Create large context
        large_turns = [
            f"User: This is a very long conversation turn number {i}" * 10 for i in range(20)
        ]

        context = PromptContext(
            recent_turns=large_turns,
            tracked_entities={f"entity_{i}": f"value_{i}" for i in range(50)},
            user_preferences={f"pref_{i}": f"value_{i}" for i in range(20)},
        )

        needs_compression = context_injector._needs_compression(context)

        assert needs_compression is True  # nosec B101

    def test_compress_context(self, context_injector):
        """Test context compression."""
        # Create large context
        context = PromptContext(
            recent_turns=[f"Turn {i}" for i in range(10)],
            tracked_entities={f"entity_{i}": f"value_{i}" for i in range(20)},
            user_preferences={f"pref_{i}": f"value_{i}" for i in range(10)},
            past_actions=[f"action_{i}" for i in range(5)],
            retrieved_memories=[{"content": f"memory_{i}"} for i in range(10)],
        )

        compressed = context_injector._compress_context(context)

        # Should be compressed
        assert len(compressed.recent_turns) <= 2  # nosec B101
        assert len(compressed.tracked_entities) <= 5  # nosec B101
        assert len(compressed.user_preferences) <= 3  # nosec B101
        assert len(compressed.past_actions) == 0  # Removed first  # nosec B101
        assert len(compressed.retrieved_memories) <= 3  # nosec B101

    @pytest.mark.asyncio
    async def test_update_context_with_feedback_nonexistent_conversation(self, context_injector):
        """Test updating feedback for nonexistent conversation."""
        # Should not raise error
        await context_injector.update_context_with_feedback(
            "nonexistent_conv", "feedback", "correction"
        )

    def test_estimate_token_count(self, context_injector):
        """Test token count estimation."""
        context = PromptContext(
            recent_turns=["User: Hello", "Agent: Hi there!"],
            tracked_entities={"location": "Seattle"},
            user_preferences={"unit": "metric"},
        )

        token_count = context_injector.estimate_token_count(context)

        # Should be reasonable estimate
        assert token_count > 0  # nosec B101
        assert token_count < 1000  # Small context  # nosec B101

    def test_get_compression_stats(self, context_injector):
        """Test getting compression statistics."""
        original = PromptContext(
            recent_turns=[f"Turn {i}" for i in range(10)],
            tracked_entities={f"entity_{i}": f"value_{i}" for i in range(20)},
            user_preferences={f"pref_{i}": f"value_{i}" for i in range(10)},
            past_actions=[f"action_{i}" for i in range(5)],
            retrieved_memories=[{"content": f"memory_{i}"} for i in range(10)],
        )

        compressed = context_injector._compress_context(original)

        stats = context_injector.get_compression_stats(original, compressed)

        # Verify stats
        assert "original_tokens" in stats  # nosec B101
        assert "compressed_tokens" in stats  # nosec B101
        assert "reduction_tokens" in stats  # nosec B101
        assert "reduction_percent" in stats  # nosec B101
        assert "turns_removed" in stats  # nosec B101
        assert "entities_removed" in stats  # nosec B101
        assert "preferences_removed" in stats  # nosec B101
        assert "actions_removed" in stats  # nosec B101
        assert "memories_removed" in stats  # nosec B101

        # Should show reduction
        assert stats["reduction_tokens"] > 0  # nosec B101
        assert stats["reduction_percent"] > 0  # nosec B101
        assert stats["turns_removed"] > 0  # nosec B101


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
