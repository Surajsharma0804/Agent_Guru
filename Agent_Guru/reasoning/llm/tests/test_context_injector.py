"""
Unit tests for ContextInjector.

Tests context extraction, compression, and integration with ConversationStateManager.

Coverage Target: 80%+
"""

from datetime import datetime

import pytest

from Agent_Guru.reasoning.llm.context_injector import ContextExtractionConfig, ContextInjector
from Agent_Guru.reasoning.llm.prompt_templates import PromptContext
from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
    TrackedEntity,
)
from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.state.conversation_manager import ConversationStateManager


@pytest.fixture
def conversation_manager():
    """Create conversation manager for testing."""
    return ConversationStateManager(max_conversations=100, inactivity_timeout=3600.0)


@pytest.fixture
def context_injector(conversation_manager):
    """Create context injector for testing."""
    return ContextInjector(conversation_manager)


@pytest.fixture
async def sample_conversation_state():
    """Create sample conversation state."""
    state = ConversationState(
        conversation_id="test_conv_123",
        user_id="test_user",
        turns=[
            ConversationTurn(
                turn_id="turn_1",
                user_input="What's the weather?",
                intent=Intent(
                    intent_type=IntentType.QUERY_WEATHER,
                    entities={
                        "location": Entity(
                            entity_type="location", value="current", raw_text="current"
                        )
                    },
                    confidence=0.95,
                    requires_reasoning=False,
                    original_input="What's the weather?",
                ),
                action_taken={"tool_id": "weather_tool", "parameters": {"location": "current"}},
                response="It's sunny, 72°F",
                timestamp=datetime.now(),
            ),
            ConversationTurn(
                turn_id="turn_2",
                user_input="What about tomorrow?",
                intent=Intent(
                    intent_type=IntentType.QUERY_WEATHER,
                    entities={
                        "location": Entity(
                            entity_type="location", value="current", raw_text="current"
                        ),
                        "time": Entity(entity_type="time", value="tomorrow", raw_text="tomorrow"),
                    },
                    confidence=0.92,
                    requires_reasoning=False,
                    original_input="What about tomorrow?",
                ),
                action_taken={
                    "tool_id": "weather_tool",
                    "parameters": {"location": "current", "time": "tomorrow"},
                },
                response="Tomorrow will be cloudy, 68°F",
                timestamp=datetime.now(),
            ),
            ConversationTurn(
                turn_id="turn_3",
                user_input="Set a timer for 5 minutes",
                intent=Intent(
                    intent_type=IntentType.SET_TIMER,
                    entities={
                        "duration": Entity(
                            entity_type="duration", value="5 minutes", raw_text="5 minutes"
                        ),
                        "duration_seconds": Entity(
                            entity_type="duration", value=300, raw_text="5 minutes"
                        ),
                    },
                    confidence=0.98,
                    requires_reasoning=False,
                    original_input="Set a timer for 5 minutes",
                ),
                action_taken={"tool_id": "timer_tool", "parameters": {"duration_seconds": 300}},
                response="Timer set for 5 minutes",
                timestamp=datetime.now(),
            ),
        ],
        entities={
            "location:current": TrackedEntity(
                entity_type="location",
                value="current",
                first_mentioned=1,
                last_mentioned=2,
                mention_count=2,
            ),
            "duration:5 minutes": TrackedEntity(
                entity_type="duration",
                value="5 minutes",
                first_mentioned=3,
                last_mentioned=3,
                mention_count=1,
            ),
        },
        user_preferences={"temperature_unit": "fahrenheit", "default_timer_sound": "bell"},
    )
    return state


class TestContextExtractionConfig:
    """Test ContextExtractionConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ContextExtractionConfig()

        assert config.max_turns == 5
        assert config.max_entities == 10
        assert config.max_preferences == 5
        assert config.max_actions == 3
        assert config.max_memories == 5
        assert config.max_tokens == 1000
        assert config.include_world_state is True

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

        assert config.max_turns == 3
        assert config.max_entities == 5
        assert config.max_preferences == 2
        assert config.max_actions == 1
        assert config.max_memories == 3
        assert config.max_tokens == 500
        assert config.include_world_state is False

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

        assert injector.conversation_manager is conversation_manager
        assert injector.config is not None
        assert injector.config.max_turns == 5

    @pytest.mark.asyncio
    async def test_initialization_with_custom_config(self, conversation_manager):
        """Test initialization with custom config."""
        config = ContextExtractionConfig(max_turns=3)
        injector = ContextInjector(conversation_manager, config)

        assert injector.config.max_turns == 3

    @pytest.mark.asyncio
    async def test_extract_context_empty_conversation(self, context_injector):
        """Test extracting context from non-existent conversation."""
        context = await context_injector.extract_context("nonexistent_conv")

        assert isinstance(context, PromptContext)
        assert len(context.recent_turns) == 0
        assert len(context.tracked_entities) == 0
        assert len(context.user_preferences) == 0
        assert len(context.past_actions) == 0

    @pytest.mark.asyncio
    async def test_extract_context_with_conversation(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test extracting context from existing conversation."""
        # Set up conversation state
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        # Extract context
        context = await context_injector.extract_context("test_conv_123")

        # Verify context
        assert isinstance(context, PromptContext)
        assert len(context.recent_turns) > 0
        assert len(context.tracked_entities) > 0
        assert len(context.user_preferences) > 0

    @pytest.mark.asyncio
    async def test_extract_recent_turns(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test extracting recent conversation turns."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context = await context_injector.extract_context("test_conv_123")

        # Should have user and agent turns
        assert len(context.recent_turns) > 0
        assert any("User:" in turn for turn in context.recent_turns)
        assert any("Agent:" in turn for turn in context.recent_turns)

    @pytest.mark.asyncio
    async def test_extract_recent_turns_respects_max_turns(
        self, conversation_manager, sample_conversation_state
    ):
        """Test that max_turns limit is respected."""
        config = ContextExtractionConfig(max_turns=2)
        injector = ContextInjector(conversation_manager, config)

        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context = await injector.extract_context("test_conv_123")

        # Should have at most 2 turns * 2 (user + agent) = 4 entries
        assert len(context.recent_turns) <= 4

    @pytest.mark.asyncio
    async def test_extract_tracked_entities(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test extracting tracked entities."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context = await context_injector.extract_context("test_conv_123")

        # Should have entities
        assert len(context.tracked_entities) > 0
        assert "location" in context.tracked_entities or "duration" in context.tracked_entities

    @pytest.mark.asyncio
    async def test_extract_tracked_entities_respects_max_entities(
        self, conversation_manager, sample_conversation_state
    ):
        """Test that max_entities limit is respected."""
        # Add many entities
        for i in range(20):
            sample_conversation_state.entities[f"entity_{i}:value_{i}"] = TrackedEntity(
                entity_type=f"entity_{i}",
                value=f"value_{i}",
                first_mentioned=i,
                last_mentioned=i,
                mention_count=1,
            )

        config = ContextExtractionConfig(max_entities=5)
        injector = ContextInjector(conversation_manager, config)

        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context = await injector.extract_context("test_conv_123")

        # Should have at most 5 entities
        assert len(context.tracked_entities) <= 5

    @pytest.mark.asyncio
    async def test_extract_user_preferences(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test extracting user preferences."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context = await context_injector.extract_context("test_conv_123")

        # Should have preferences
        assert len(context.user_preferences) > 0
        assert "temperature_unit" in context.user_preferences

    @pytest.mark.asyncio
    async def test_extract_user_preferences_respects_max_preferences(
        self, conversation_manager, sample_conversation_state
    ):
        """Test that max_preferences limit is respected."""
        # Add many preferences
        for i in range(10):
            sample_conversation_state.user_preferences[f"pref_{i}"] = f"value_{i}"

        config = ContextExtractionConfig(max_preferences=3)
        injector = ContextInjector(conversation_manager, config)

        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context = await injector.extract_context("test_conv_123")

        # Should have at most 3 preferences
        assert len(context.user_preferences) <= 3

    @pytest.mark.asyncio
    async def test_extract_past_actions(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test extracting past actions."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context = await context_injector.extract_context("test_conv_123")

        # Should have past actions
        assert len(context.past_actions) > 0
        assert any(
            "weather_tool" in action or "timer_tool" in action for action in context.past_actions
        )

    @pytest.mark.asyncio
    async def test_extract_past_actions_respects_max_actions(
        self, conversation_manager, sample_conversation_state
    ):
        """Test that max_actions limit is respected."""
        config = ContextExtractionConfig(max_actions=2)
        injector = ContextInjector(conversation_manager, config)

        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context = await injector.extract_context("test_conv_123")

        # Should have at most 2 actions
        assert len(context.past_actions) <= 2

    @pytest.mark.asyncio
    async def test_extract_context_with_memories(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test extracting context with retrieved memories."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        memories = [
            {"memory_type": "episodic", "content": "User asked about weather yesterday"},
            {"memory_type": "preference", "content": "User prefers Fahrenheit"},
        ]

        context = await context_injector.extract_context(
            "test_conv_123", retrieved_memories=memories
        )

        # Should have memories
        assert len(context.retrieved_memories) == 2
        assert context.retrieved_memories == memories

    @pytest.mark.asyncio
    async def test_extract_context_with_world_state(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test extracting context with world state summary."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        world_state = "Battery: 80%, Network: WiFi, Location: Home"

        context = await context_injector.extract_context(
            "test_conv_123", world_state_summary=world_state
        )

        # Should have world state
        assert context.world_state_summary == world_state

    @pytest.mark.asyncio
    async def test_inject_context_alias(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test that inject_context is an alias for extract_context."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        context1 = await context_injector.extract_context("test_conv_123")
        context2 = await context_injector.inject_context("test_conv_123")

        # Should produce same results
        assert len(context1.recent_turns) == len(context2.recent_turns)
        assert len(context1.tracked_entities) == len(context2.tracked_entities)

    def test_format_action_with_dict(self, context_injector):
        """Test formatting action from dictionary."""
        action = {"tool_id": "weather_tool", "parameters": {"location": "Seattle", "time": "now"}}

        formatted = context_injector._format_action(action)

        assert "weather_tool" in formatted
        assert "location=Seattle" in formatted
        assert "time=now" in formatted

    def test_format_action_with_object(self, context_injector):
        """Test formatting action from object."""

        class MockAction:
            def __init__(self):
                self.tool_id = "timer_tool"
                self.parameters = {"duration_seconds": 300}

        action = MockAction()
        formatted = context_injector._format_action(action)

        assert "timer_tool" in formatted
        assert "duration_seconds=300" in formatted

    def test_format_action_fallback(self, context_injector):
        """Test formatting action fallback."""
        action = "some_action"
        formatted = context_injector._format_action(action)

        assert formatted == "some_action"

    def test_needs_compression_small_context(self, context_injector):
        """Test that small context doesn't need compression."""
        context = PromptContext(
            recent_turns=["User: Hello", "Agent: Hi"],
            tracked_entities={"location": "Seattle"},
            user_preferences={"unit": "metric"},
        )

        needs_compression = context_injector._needs_compression(context)

        assert needs_compression is False

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

        assert needs_compression is True

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
        assert len(compressed.recent_turns) <= 2
        assert len(compressed.tracked_entities) <= 5
        assert len(compressed.user_preferences) <= 3
        assert len(compressed.past_actions) == 0  # Removed first
        assert len(compressed.retrieved_memories) <= 3

    @pytest.mark.asyncio
    async def test_extract_context_for_multi_step(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test extracting context for multi-step reasoning."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        previous_results = [
            {"description": "Check weather", "result": "Sunny, 72°F"},
            {"description": "Set reminder", "result": "Reminder set"},
        ]

        context = await context_injector.extract_context_for_multi_step(
            "test_conv_123", step_number=3, previous_step_results=previous_results
        )

        # Should have previous step results in past actions
        assert len(context.past_actions) > 0
        assert any("Step 1" in action for action in context.past_actions)
        assert any("Step 2" in action for action in context.past_actions)

    @pytest.mark.asyncio
    async def test_update_context_with_feedback(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test updating context with user feedback."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        await context_injector.update_context_with_feedback(
            "test_conv_123", "That was helpful", "confirmation"
        )

        # Verify feedback was added
        state = await conversation_manager.get_state("test_conv_123")
        assert state is not None
        assert state.turns[-1].user_feedback == "That was helpful"

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
        assert token_count > 0
        assert token_count < 1000  # Small context

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
        assert "original_tokens" in stats
        assert "compressed_tokens" in stats
        assert "reduction_tokens" in stats
        assert "reduction_percent" in stats
        assert "turns_removed" in stats
        assert "entities_removed" in stats
        assert "preferences_removed" in stats
        assert "actions_removed" in stats
        assert "memories_removed" in stats

        # Should show reduction
        assert stats["reduction_tokens"] > 0
        assert stats["reduction_percent"] > 0
        assert stats["turns_removed"] > 0


class TestContextInjectorIntegration:
    """Integration tests for ContextInjector."""

    @pytest.mark.asyncio
    async def test_full_context_extraction_workflow(self, context_injector, conversation_manager):
        """Test full context extraction workflow."""
        # Create conversation
        conversation_id = "integration_test_conv"

        # Add turns
        for i in range(10):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                user_input=f"User input {i}",
                intent=Intent(
                    intent_type=IntentType.QUERY_WEATHER,
                    entities={
                        "test": Entity(
                            entity_type="test", value=f"value_{i}", raw_text=f"value_{i}"
                        )
                    },
                    confidence=0.9,
                    requires_reasoning=False,
                    original_input=f"User input {i}",
                ),
                action_taken={"tool_id": "test_tool", "parameters": {"param": f"value_{i}"}},
                response=f"Response {i}",
                timestamp=datetime.now(),
            )

            await conversation_manager.add_turn(conversation_id, turn)

        # Extract context
        context = await context_injector.extract_context(conversation_id)

        # Verify context
        assert len(context.recent_turns) > 0
        assert len(context.recent_turns) <= 10  # Max 5 turns * 2 (user + agent)

    @pytest.mark.asyncio
    async def test_context_compression_workflow(self, conversation_manager):
        """Test context compression workflow."""
        # Create injector with small token limit
        config = ContextExtractionConfig(max_tokens=200)
        injector = ContextInjector(conversation_manager, config)

        # Create large conversation
        conversation_id = "compression_test_conv"
        state = ConversationState(
            conversation_id=conversation_id,
            user_id="test_user",
            turns=[
                ConversationTurn(
                    turn_id=f"turn_{i}",
                    user_input=f"This is a very long user input with lots of text to make it exceed token limits {i}"
                    * 5,
                    intent=Intent(
                        intent_type=IntentType.QUERY_WEATHER,
                        entities={},
                        confidence=0.9,
                        requires_reasoning=False,
                        original_input=f"This is a very long user input with lots of text to make it exceed token limits {i}"
                        * 5,
                    ),
                    response=f"This is a very long response with lots of text {i}" * 5,
                    timestamp=datetime.now(),
                )
                for i in range(10)
            ],
            entities={
                f"entity_{i}:value_{i}": TrackedEntity(
                    entity_type=f"entity_{i}",
                    value=f"value_{i}",
                    first_mentioned=i,
                    last_mentioned=i,
                    mention_count=1,
                )
                for i in range(20)
            },
            user_preferences={f"pref_{i}": f"value_{i}" for i in range(10)},
        )

        await conversation_manager.set_state(conversation_id, state)

        # Extract context (should trigger compression)
        context = await injector.extract_context(conversation_id)

        # Verify compression occurred
        assert len(context.recent_turns) <= 4  # Compressed
        assert len(context.tracked_entities) <= 5  # Compressed
        assert len(context.user_preferences) <= 3  # Compressed

    @pytest.mark.asyncio
    async def test_context_with_all_components(
        self, context_injector, conversation_manager, sample_conversation_state
    ):
        """Test context extraction with all components."""
        await conversation_manager.set_state("test_conv_123", sample_conversation_state)

        memories = [
            {"memory_type": "episodic", "content": "Previous interaction"},
            {"memory_type": "semantic", "content": "Learned fact"},
        ]

        world_state = "Battery: 50%, Network: 4G, Location: Office"

        context = await context_injector.extract_context(
            "test_conv_123", retrieved_memories=memories, world_state_summary=world_state
        )

        # Verify all components present
        assert len(context.recent_turns) > 0
        assert len(context.tracked_entities) > 0
        assert len(context.user_preferences) > 0
        assert len(context.past_actions) > 0
        assert len(context.retrieved_memories) == 2
        assert context.world_state_summary == world_state

        # Format and verify
        formatted = context.format_for_prompt()
        assert "Recent conversation:" in formatted
        assert "Tracked entities:" in formatted
        assert "User preferences:" in formatted
        assert "Recent actions:" in formatted
        assert "Relevant memories:" in formatted
        assert "World state:" in formatted
