"""
Unit tests for Memory LLM Integration.

Tests cover:
- Memory retrieval for reasoning
- Memory formatting for LLM prompts
- Usage tracking and statistics
- Relevance updates based on usage
- Integration with MemoryRetriever

Coverage Target: 80%+
"""

from datetime import datetime
from uuid import uuid4

import pytest

from Agent_Guru.reasoning.memory.llm_integration import (
    MemoryContext,
    MemoryLLMIntegration,
    MemoryUsageStats,
)
from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.models.memory import (
    EpisodicMemory,
    MemoryType,
    PreferenceMemory,
    SemanticMemory,
    TaskMemory,
)


def create_test_intent(
    intent_type: IntentType = IntentType.SET_TIMER,
    entities: dict = None,
    confidence: float = 0.9,
    original_input: str = "test input",
) -> Intent:
    """Helper to create test Intent with proper Entity objects."""
    if entities is None:
        entities = {}

    # Convert simple dict to Entity objects
    entity_objects = {}
    for key, value in entities.items():
        if isinstance(value, Entity):
            entity_objects[key] = value
        else:
            # Create Entity from simple value
            entity_objects[key] = Entity(
                entity_type=key, value=value, raw_text=str(value), confidence=1.0
            )

    return Intent(
        intent_type=intent_type,
        entities=entity_objects,
        confidence=confidence,
        original_input=original_input,
    )


class TestMemoryLLMIntegration:
    """Unit tests for MemoryLLMIntegration class."""

    def test_initialization(self):
        """Test MemoryLLMIntegration initialization."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        assert integration.memory_retriever is retriever
        assert integration.max_memories == 5
        assert integration.relevance_boost_factor == 0.1
        assert len(integration.usage_stats) == 0

    def test_initialization_with_custom_params(self):
        """Test initialization with custom parameters."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever, max_memories=10, relevance_boost_factor=0.2)

        assert integration.max_memories == 10
        assert integration.relevance_boost_factor == 0.2

    def test_initialization_invalid_max_memories(self):
        """Test initialization with invalid max_memories."""
        retriever = MemoryRetriever()

        with pytest.raises(ValueError, match="max_memories must be >= 1"):
            MemoryLLMIntegration(retriever, max_memories=0)

    def test_initialization_invalid_boost_factor(self):
        """Test initialization with invalid relevance_boost_factor."""
        retriever = MemoryRetriever()

        with pytest.raises(ValueError, match="relevance_boost_factor must be >= 0"):
            MemoryLLMIntegration(retriever, relevance_boost_factor=-0.1)

    def test_retrieve_for_reasoning_empty(self):
        """Test retrieve_for_reasoning with no memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        intent = create_test_intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": "5 minutes"},
            original_input="set a timer for 5 minutes",
        )

        context = integration.retrieve_for_reasoning(intent=intent, user_id="user_123")

        assert isinstance(context, MemoryContext)
        assert len(context.memories) == 0
        assert context.formatted_prompt == "No relevant memories found."
        assert context.retrieval_time_ms >= 0
        assert len(context.memory_ids) == 0
        assert "timer" in context.query.lower()

    def test_retrieve_for_reasoning_with_memories(self):
        """Test retrieve_for_reasoning with stored memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store some memories
        memory1 = EpisodicMemory(
            content="User set a timer for 5 minutes",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123",
        )
        memory2 = EpisodicMemory(
            content="User set a timer for 10 minutes",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory1)
        retriever.store(memory2)

        # Retrieve for reasoning
        intent = create_test_intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": "5 minutes"},
            original_input="set a timer for 5 minutes",
        )

        context = integration.retrieve_for_reasoning(intent=intent, user_id="user_123")

        assert len(context.memories) > 0
        assert len(context.memories) <= integration.max_memories
        assert context.formatted_prompt != "No relevant memories found."
        assert context.retrieval_time_ms >= 0
        assert len(context.memory_ids) == len(context.memories)
        assert all(isinstance(mid, type(memory1.memory_id)) for mid in context.memory_ids)

    def test_retrieve_for_reasoning_with_memory_types(self):
        """Test retrieve_for_reasoning with memory type filtering."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store different memory types
        episodic = EpisodicMemory(
            content="User set a timer",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123",
        )
        semantic = SemanticMemory(
            content="Timers are useful for cooking",
            fact="Timers help with time management",
            source="user_feedback",
            confidence=0.9,
            user_id="user_123",
        )
        retriever.store(episodic)
        retriever.store(semantic)

        # Retrieve only episodic memories
        intent = create_test_intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": "5 minutes"},
            original_input="set a timer for 5 minutes",
        )

        context = integration.retrieve_for_reasoning(
            intent=intent, user_id="user_123", memory_types=[MemoryType.EPISODIC]
        )

        assert len(context.memories) > 0
        assert all(m.memory_type == MemoryType.EPISODIC for m in context.memories)

    def test_retrieve_for_reasoning_latency(self):
        """Test that retrieve_for_reasoning meets latency budget."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store many memories
        for i in range(100):
            memory = EpisodicMemory(
                content=f"User action {i}",
                action_taken="test_action",
                result="Success",
                success=True,
                user_id="user_123",
            )
            retriever.store(memory)

        # Retrieve for reasoning
        intent = create_test_intent(
            intent_type=IntentType.QUERY_WEATHER, original_input="what's the weather"
        )

        context = integration.retrieve_for_reasoning(intent=intent, user_id="user_123")

        # Should meet <100ms latency budget
        assert context.retrieval_time_ms < 100

    def test_format_memories_for_prompt_empty(self):
        """Test format_memories_for_prompt with empty list."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        formatted = integration.format_memories_for_prompt([])

        assert formatted == "No relevant memories found."

    def test_format_memories_for_prompt_episodic(self):
        """Test format_memories_for_prompt with episodic memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory = EpisodicMemory(
            content="User set a timer for 5 minutes",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123",
        )

        formatted = integration.format_memories_for_prompt([memory])

        assert "## Relevant Memories" in formatted
        assert "Memory 1" in formatted
        assert "episodic" in formatted.lower()
        assert memory.content in formatted
        assert memory.action_taken in formatted
        assert memory.result in formatted
        assert "**Success**: True" in formatted
        assert f"**Relevance**: {memory.relevance_score:.2f}" in formatted

    def test_format_memories_for_prompt_semantic(self):
        """Test format_memories_for_prompt with semantic memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory = SemanticMemory(
            content="Timers are useful for cooking",
            fact="Timers help with time management",
            source="user_feedback",
            confidence=0.9,
            user_id="user_123",
        )

        formatted = integration.format_memories_for_prompt([memory])

        assert "## Relevant Memories" in formatted
        assert "semantic" in formatted.lower()
        assert memory.content in formatted
        assert memory.fact in formatted
        assert f"**Confidence**: {memory.confidence:.2f}" in formatted

    def test_format_memories_for_prompt_preference(self):
        """Test format_memories_for_prompt with preference memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory = PreferenceMemory(
            content="User prefers 5-minute timers",
            preference_key="default_timer_duration",
            preference_value="5 minutes",
            learned_from="explicit",  # Valid value
            user_id="user_123",
        )

        formatted = integration.format_memories_for_prompt([memory])

        assert "## Relevant Memories" in formatted
        assert "preference" in formatted.lower()
        assert memory.content in formatted
        assert memory.preference_key in formatted
        assert memory.preference_value in formatted
        assert memory.learned_from in formatted

    def test_format_memories_for_prompt_task(self):
        """Test format_memories_for_prompt with task memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory = TaskMemory(
            content="Multi-step timer task",
            task_id="task_123",
            task_description="Set multiple timers",
            outcome="Success",
            lessons_learned=["User likes stacked timers"],  # List of strings
            user_id="user_123",
        )

        formatted = integration.format_memories_for_prompt([memory])

        assert "## Relevant Memories" in formatted
        assert "task" in formatted.lower()
        assert memory.content in formatted
        assert memory.task_description in formatted
        assert memory.outcome in formatted
        assert "User likes stacked timers" in formatted

    def test_format_memories_for_prompt_multiple(self):
        """Test format_memories_for_prompt with multiple memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory1 = EpisodicMemory(
            content="Memory 1",
            action_taken="action1",
            result="Success",
            success=True,
            user_id="user_123",
        )
        memory2 = SemanticMemory(
            content="Memory 2", fact="Fact 2", source="source2", confidence=0.8, user_id="user_123"
        )

        formatted = integration.format_memories_for_prompt([memory1, memory2])

        assert "Memory 1" in formatted
        assert "Memory 2" in formatted
        assert memory1.content in formatted
        assert memory2.content in formatted

    def test_track_memory_usage_new(self):
        """Test track_memory_usage with new memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_id = uuid4()
        integration.track_memory_usage([memory_id])

        assert memory_id in integration.usage_stats
        stats = integration.usage_stats[memory_id]
        assert stats.usage_count == 1
        assert stats.relevance_boost == integration.relevance_boost_factor
        assert isinstance(stats.last_used, datetime)

    def test_track_memory_usage_existing(self):
        """Test track_memory_usage with existing memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_id = uuid4()

        # Track first time
        integration.track_memory_usage([memory_id])
        first_boost = integration.usage_stats[memory_id].relevance_boost

        # Track second time
        integration.track_memory_usage([memory_id])
        second_stats = integration.usage_stats[memory_id]

        assert second_stats.usage_count == 2
        # Boost should increase (with diminishing returns)
        assert second_stats.relevance_boost >= first_boost

    def test_track_memory_usage_multiple(self):
        """Test track_memory_usage with multiple memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_ids = [uuid4() for _ in range(5)]
        integration.track_memory_usage(memory_ids)

        assert len(integration.usage_stats) == 5
        for memory_id in memory_ids:
            assert memory_id in integration.usage_stats
            assert integration.usage_stats[memory_id].usage_count == 1

    def test_track_memory_usage_diminishing_returns(self):
        """Test that relevance boost has diminishing returns."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_id = uuid4()

        # Track many times
        boosts = []
        for _ in range(10):
            integration.track_memory_usage([memory_id])
            boosts.append(integration.usage_stats[memory_id].relevance_boost)

        # Check diminishing returns
        assert boosts[0] < boosts[1]  # First boost is significant
        assert boosts[-1] - boosts[-2] < boosts[1] - boosts[0]  # Later boosts are smaller
        assert boosts[-1] <= 0.5  # Max boost is 0.5

    def test_update_relevance_from_usage_empty(self):
        """Test update_relevance_from_usage with no usage stats."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        updated_count = integration.update_relevance_from_usage()

        assert updated_count == 0

    def test_update_relevance_from_usage_with_memories(self):
        """Test update_relevance_from_usage with tracked memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store memories with initial score < 1.0
        memory1 = EpisodicMemory(
            content="Memory 1",
            action_taken="action1",
            result="Success",
            success=True,
            user_id="user_123",
        )
        memory2 = EpisodicMemory(
            content="Memory 2",
            action_taken="action2",
            result="Success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory1)
        retriever.store(memory2)

        # Set lower initial scores
        retriever.update_relevance(memory1.memory_id, 0.5)
        retriever.update_relevance(memory2.memory_id, 0.5)

        # Track usage
        integration.track_memory_usage([memory1.memory_id, memory2.memory_id])

        # Update relevance
        updated_count = integration.update_relevance_from_usage()

        assert updated_count == 2

        # Check scores increased
        new_score1 = retriever.memories[memory1.memory_id].relevance_score
        new_score2 = retriever.memories[memory2.memory_id].relevance_score
        assert new_score1 > 0.5
        assert new_score2 > 0.5

    def test_update_relevance_from_usage_clamped(self):
        """Test that relevance scores are clamped to [0.0, 1.0]."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever, relevance_boost_factor=0.5)

        # Store memory with high initial score
        memory = EpisodicMemory(
            content="Memory",
            action_taken="action",
            result="Success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory)

        # Set high relevance
        retriever.update_relevance(memory.memory_id, 0.9)

        # Track usage multiple times
        for _ in range(5):
            integration.track_memory_usage([memory.memory_id])

        # Update relevance
        integration.update_relevance_from_usage()

        # Check score is clamped to 1.0
        final_score = retriever.memories[memory.memory_id].relevance_score
        assert final_score <= 1.0

    def test_update_relevance_from_usage_missing_memory(self):
        """Test update_relevance_from_usage with missing memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Track usage for non-existent memory
        fake_id = uuid4()
        integration.track_memory_usage([fake_id])

        # Update relevance (should skip missing memory)
        updated_count = integration.update_relevance_from_usage()

        assert updated_count == 0

    def test_get_usage_stats_existing(self):
        """Test get_usage_stats for existing memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_id = uuid4()
        integration.track_memory_usage([memory_id])

        stats = integration.get_usage_stats(memory_id)

        assert stats is not None
        assert stats.memory_id == memory_id
        assert stats.usage_count == 1

    def test_get_usage_stats_missing(self):
        """Test get_usage_stats for missing memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        stats = integration.get_usage_stats(uuid4())

        assert stats is None

    def test_clear_usage_stats(self):
        """Test clear_usage_stats."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Track some usage
        memory_ids = [uuid4() for _ in range(5)]
        integration.track_memory_usage(memory_ids)

        assert len(integration.usage_stats) == 5

        # Clear stats
        integration.clear_usage_stats()

        assert len(integration.usage_stats) == 0

    def test_build_query_from_intent_simple(self):
        """Test _build_query_from_intent with simple intent."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        intent = create_test_intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": "5 minutes"},
            original_input="set a timer for 5 minutes",
        )

        query = integration._build_query_from_intent(intent)

        assert "set timer" in query.lower()
        assert "5 minutes" in query.lower()

    def test_build_query_from_intent_multiple_entities(self):
        """Test _build_query_from_intent with multiple entities."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        intent = create_test_intent(
            intent_type=IntentType.SEND_MESSAGE,
            entities={"recipient": "John", "message": "Hello", "platform": "SMS"},
            original_input="send a message to John saying Hello via SMS",
        )

        query = integration._build_query_from_intent(intent)

        assert "send message" in query.lower()
        assert "john" in query.lower()
        assert "hello" in query.lower()
        assert "sms" in query.lower()

    def test_build_query_from_intent_numeric_entities(self):
        """Test _build_query_from_intent with numeric entities."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        intent = create_test_intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": 5, "count": 3},
            original_input="set 3 timers for 5 minutes",
        )

        query = integration._build_query_from_intent(intent)

        assert "set timer" in query.lower()
        assert "5" in query
        assert "3" in query


class TestMemoryContext:
    """Unit tests for MemoryContext dataclass."""

    def test_memory_context_creation(self):
        """Test MemoryContext creation."""
        memory = EpisodicMemory(
            content="Test memory",
            action_taken="test_action",
            result="Success",
            success=True,
            user_id="user_123",
        )

        context = MemoryContext(
            memories=[memory],
            formatted_prompt="Test prompt",
            retrieval_time_ms=50.0,
            memory_ids=[memory.memory_id],
            query="test query",
        )

        assert len(context.memories) == 1
        assert context.formatted_prompt == "Test prompt"
        assert context.retrieval_time_ms == 50.0
        assert len(context.memory_ids) == 1
        assert context.query == "test query"


class TestMemoryUsageStats:
    """Unit tests for MemoryUsageStats dataclass."""

    def test_memory_usage_stats_creation(self):
        """Test MemoryUsageStats creation."""
        memory_id = uuid4()
        now = datetime.utcnow()

        stats = MemoryUsageStats(
            memory_id=memory_id, usage_count=5, last_used=now, relevance_boost=0.3
        )

        assert stats.memory_id == memory_id
        assert stats.usage_count == 5
        assert stats.last_used == now
        assert stats.relevance_boost == 0.3

    """Unit tests for MemoryLLMIntegration class."""

    def test_initialization(self):
        """Test MemoryLLMIntegration initialization."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        assert integration.memory_retriever is retriever
        assert integration.max_memories == 5
        assert integration.relevance_boost_factor == 0.1
        assert len(integration.usage_stats) == 0

    def test_initialization_with_custom_params(self):
        """Test initialization with custom parameters."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever, max_memories=10, relevance_boost_factor=0.2)

        assert integration.max_memories == 10
        assert integration.relevance_boost_factor == 0.2

    def test_initialization_invalid_max_memories(self):
        """Test initialization with invalid max_memories."""
        retriever = MemoryRetriever()

        with pytest.raises(ValueError, match="max_memories must be >= 1"):
            MemoryLLMIntegration(retriever, max_memories=0)

    def test_initialization_invalid_boost_factor(self):
        """Test initialization with invalid relevance_boost_factor."""
        retriever = MemoryRetriever()

        with pytest.raises(ValueError, match="relevance_boost_factor must be >= 0"):
            MemoryLLMIntegration(retriever, relevance_boost_factor=-0.1)

    def test_retrieve_for_reasoning_empty(self):
        """Test retrieve_for_reasoning with no memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        intent = Intent(
            intent_type=IntentType.SET_TIMER, entities={"duration": "5 minutes"}, confidence=0.9
        )

        context = integration.retrieve_for_reasoning(intent=intent, user_id="user_123")

        assert isinstance(context, MemoryContext)
        assert len(context.memories) == 0
        assert context.formatted_prompt == "No relevant memories found."
        assert context.retrieval_time_ms >= 0
        assert len(context.memory_ids) == 0
        assert "timer" in context.query.lower()

    def test_retrieve_for_reasoning_with_memories(self):
        """Test retrieve_for_reasoning with stored memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store some memories
        memory1 = EpisodicMemory(
            content="User set a timer for 5 minutes",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123",
        )
        memory2 = EpisodicMemory(
            content="User set a timer for 10 minutes",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory1)
        retriever.store(memory2)

        # Retrieve for reasoning
        intent = Intent(
            intent_type=IntentType.SET_TIMER, entities={"duration": "5 minutes"}, confidence=0.9
        )

        context = integration.retrieve_for_reasoning(intent=intent, user_id="user_123")

        assert len(context.memories) > 0
        assert len(context.memories) <= integration.max_memories
        assert context.formatted_prompt != "No relevant memories found."
        assert context.retrieval_time_ms >= 0
        assert len(context.memory_ids) == len(context.memories)
        assert all(isinstance(mid, type(memory1.memory_id)) for mid in context.memory_ids)

    def test_retrieve_for_reasoning_with_memory_types(self):
        """Test retrieve_for_reasoning with memory type filtering."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store different memory types
        episodic = EpisodicMemory(
            content="User set a timer",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123",
        )
        semantic = SemanticMemory(
            content="Timers are useful for cooking",
            fact="Timers help with time management",
            source="user_feedback",
            confidence=0.9,
            user_id="user_123",
        )
        retriever.store(episodic)
        retriever.store(semantic)

        # Retrieve only episodic memories
        intent = Intent(
            intent_type=IntentType.SET_TIMER, entities={"duration": "5 minutes"}, confidence=0.9
        )

        context = integration.retrieve_for_reasoning(
            intent=intent, user_id="user_123", memory_types=[MemoryType.EPISODIC]
        )

        assert len(context.memories) > 0
        assert all(m.memory_type == MemoryType.EPISODIC for m in context.memories)

    def test_retrieve_for_reasoning_latency(self):
        """Test that retrieve_for_reasoning meets latency budget."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store many memories
        for i in range(100):
            memory = EpisodicMemory(
                content=f"User action {i}",
                action_taken="test_action",
                result="Success",
                success=True,
                user_id="user_123",
            )
            retriever.store(memory)

        # Retrieve for reasoning
        intent = Intent(intent_type=IntentType.QUERY_WEATHER, entities={}, confidence=0.9)

        context = integration.retrieve_for_reasoning(intent=intent, user_id="user_123")

        # Should meet <100ms latency budget
        assert context.retrieval_time_ms < 100

    def test_format_memories_for_prompt_empty(self):
        """Test format_memories_for_prompt with empty list."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        formatted = integration.format_memories_for_prompt([])

        assert formatted == "No relevant memories found."

    def test_format_memories_for_prompt_episodic(self):
        """Test format_memories_for_prompt with episodic memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory = EpisodicMemory(
            content="User set a timer for 5 minutes",
            action_taken="set_timer",
            result="Success",
            success=True,
            user_id="user_123",
        )

        formatted = integration.format_memories_for_prompt([memory])

        assert "## Relevant Memories" in formatted
        assert "Memory 1" in formatted
        assert "episodic" in formatted.lower()
        assert memory.content in formatted
        assert memory.action_taken in formatted
        assert memory.result in formatted
        assert "Success: True" in formatted
        assert f"Relevance: {memory.relevance_score:.2f}" in formatted

    def test_format_memories_for_prompt_semantic(self):
        """Test format_memories_for_prompt with semantic memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory = SemanticMemory(
            content="Timers are useful for cooking",
            fact="Timers help with time management",
            source="user_feedback",
            confidence=0.9,
            user_id="user_123",
        )

        formatted = integration.format_memories_for_prompt([memory])

        assert "## Relevant Memories" in formatted
        assert "semantic" in formatted.lower()
        assert memory.content in formatted
        assert memory.fact in formatted
        assert f"Confidence: {memory.confidence:.2f}" in formatted

    def test_format_memories_for_prompt_preference(self):
        """Test format_memories_for_prompt with preference memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory = PreferenceMemory(
            content="User prefers 5-minute timers",
            preference_key="default_timer_duration",
            preference_value="5 minutes",
            learned_from="repeated_usage",
            user_id="user_123",
        )

        formatted = integration.format_memories_for_prompt([memory])

        assert "## Relevant Memories" in formatted
        assert "preference" in formatted.lower()
        assert memory.content in formatted
        assert memory.preference_key in formatted
        assert memory.preference_value in formatted
        assert memory.learned_from in formatted

    def test_format_memories_for_prompt_task(self):
        """Test format_memories_for_prompt with task memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory = TaskMemory(
            content="Multi-step timer task",
            task_id="task_123",
            task_description="Set multiple timers",
            outcome="Success",
            lessons_learned="User likes stacked timers",
            user_id="user_123",
        )

        formatted = integration.format_memories_for_prompt([memory])

        assert "## Relevant Memories" in formatted
        assert "task" in formatted.lower()
        assert memory.content in formatted
        assert memory.task_description in formatted
        assert memory.outcome in formatted
        assert memory.lessons_learned in formatted

    def test_format_memories_for_prompt_multiple(self):
        """Test format_memories_for_prompt with multiple memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory1 = EpisodicMemory(
            content="Memory 1",
            action_taken="action1",
            result="Success",
            success=True,
            user_id="user_123",
        )
        memory2 = SemanticMemory(
            content="Memory 2", fact="Fact 2", source="source2", confidence=0.8, user_id="user_123"
        )

        formatted = integration.format_memories_for_prompt([memory1, memory2])

        assert "Memory 1" in formatted
        assert "Memory 2" in formatted
        assert memory1.content in formatted
        assert memory2.content in formatted

    def test_track_memory_usage_new(self):
        """Test track_memory_usage with new memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_id = uuid4()
        integration.track_memory_usage([memory_id])

        assert memory_id in integration.usage_stats
        stats = integration.usage_stats[memory_id]
        assert stats.usage_count == 1
        assert stats.relevance_boost == integration.relevance_boost_factor
        assert isinstance(stats.last_used, datetime)

    def test_track_memory_usage_existing(self):
        """Test track_memory_usage with existing memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_id = uuid4()

        # Track first time
        integration.track_memory_usage([memory_id])
        first_stats = integration.usage_stats[memory_id]

        # Track second time
        integration.track_memory_usage([memory_id])
        second_stats = integration.usage_stats[memory_id]

        assert second_stats.usage_count == 2
        assert second_stats.relevance_boost > first_stats.relevance_boost
        assert second_stats.last_used >= first_stats.last_used

    def test_track_memory_usage_multiple(self):
        """Test track_memory_usage with multiple memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_ids = [uuid4() for _ in range(5)]
        integration.track_memory_usage(memory_ids)

        assert len(integration.usage_stats) == 5
        for memory_id in memory_ids:
            assert memory_id in integration.usage_stats
            assert integration.usage_stats[memory_id].usage_count == 1

    def test_track_memory_usage_diminishing_returns(self):
        """Test that relevance boost has diminishing returns."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_id = uuid4()

        # Track many times
        boosts = []
        for _ in range(10):
            integration.track_memory_usage([memory_id])
            boosts.append(integration.usage_stats[memory_id].relevance_boost)

        # Check diminishing returns
        assert boosts[0] < boosts[1]  # First boost is significant
        assert boosts[-1] - boosts[-2] < boosts[1] - boosts[0]  # Later boosts are smaller
        assert boosts[-1] <= 0.5  # Max boost is 0.5

    def test_update_relevance_from_usage_empty(self):
        """Test update_relevance_from_usage with no usage stats."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        updated_count = integration.update_relevance_from_usage()

        assert updated_count == 0

    def test_update_relevance_from_usage_with_memories(self):
        """Test update_relevance_from_usage with tracked memories."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store memories
        memory1 = EpisodicMemory(
            content="Memory 1",
            action_taken="action1",
            result="Success",
            success=True,
            user_id="user_123",
        )
        memory2 = EpisodicMemory(
            content="Memory 2",
            action_taken="action2",
            result="Success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory1)
        retriever.store(memory2)

        # Track usage
        integration.track_memory_usage([memory1.memory_id, memory2.memory_id])

        # Get original scores
        original_score1 = retriever.memories[memory1.memory_id].relevance_score
        original_score2 = retriever.memories[memory2.memory_id].relevance_score

        # Update relevance
        updated_count = integration.update_relevance_from_usage()

        assert updated_count == 2

        # Check scores increased
        new_score1 = retriever.memories[memory1.memory_id].relevance_score
        new_score2 = retriever.memories[memory2.memory_id].relevance_score
        assert new_score1 > original_score1
        assert new_score2 > original_score2

    def test_update_relevance_from_usage_clamped(self):
        """Test that relevance scores are clamped to [0.0, 1.0]."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever, relevance_boost_factor=0.5)

        # Store memory with high initial score
        memory = EpisodicMemory(
            content="Memory",
            action_taken="action",
            result="Success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory)

        # Set high relevance
        retriever.update_relevance(memory.memory_id, 0.9)

        # Track usage multiple times
        for _ in range(5):
            integration.track_memory_usage([memory.memory_id])

        # Update relevance
        integration.update_relevance_from_usage()

        # Check score is clamped to 1.0
        final_score = retriever.memories[memory.memory_id].relevance_score
        assert final_score <= 1.0

    def test_update_relevance_from_usage_missing_memory(self):
        """Test update_relevance_from_usage with missing memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Track usage for non-existent memory
        fake_id = uuid4()
        integration.track_memory_usage([fake_id])

        # Update relevance (should skip missing memory)
        updated_count = integration.update_relevance_from_usage()

        assert updated_count == 0

    def test_get_usage_stats_existing(self):
        """Test get_usage_stats for existing memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        memory_id = uuid4()
        integration.track_memory_usage([memory_id])

        stats = integration.get_usage_stats(memory_id)

        assert stats is not None
        assert stats.memory_id == memory_id
        assert stats.usage_count == 1

    def test_get_usage_stats_missing(self):
        """Test get_usage_stats for missing memory."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        stats = integration.get_usage_stats(uuid4())

        assert stats is None

    def test_clear_usage_stats(self):
        """Test clear_usage_stats."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Track some usage
        memory_ids = [uuid4() for _ in range(5)]
        integration.track_memory_usage(memory_ids)

        assert len(integration.usage_stats) == 5

        # Clear stats
        integration.clear_usage_stats()

        assert len(integration.usage_stats) == 0

    def test_build_query_from_intent_simple(self):
        """Test _build_query_from_intent with simple intent."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        intent = Intent(
            intent_type=IntentType.SET_TIMER, entities={"duration": "5 minutes"}, confidence=0.9
        )

        query = integration._build_query_from_intent(intent)

        assert "set timer" in query.lower()
        assert "5 minutes" in query.lower()

    def test_build_query_from_intent_multiple_entities(self):
        """Test _build_query_from_intent with multiple entities."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        intent = Intent(
            intent_type=IntentType.SEND_MESSAGE,
            entities={"recipient": "John", "message": "Hello", "platform": "SMS"},
            confidence=0.9,
        )

        query = integration._build_query_from_intent(intent)

        assert "send message" in query.lower()
        assert "john" in query.lower()
        assert "hello" in query.lower()
        assert "sms" in query.lower()

    def test_build_query_from_intent_numeric_entities(self):
        """Test _build_query_from_intent with numeric entities."""
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        intent = Intent(
            intent_type=IntentType.SET_TIMER, entities={"duration": 5, "count": 3}, confidence=0.9
        )

        query = integration._build_query_from_intent(intent)

        assert "set timer" in query.lower()
        assert "5" in query
        assert "3" in query


class TestMemoryContext:
    """Unit tests for MemoryContext dataclass."""

    def test_memory_context_creation(self):
        """Test MemoryContext creation."""
        memory = EpisodicMemory(
            content="Test memory",
            action_taken="test_action",
            result="Success",
            success=True,
            user_id="user_123",
        )

        context = MemoryContext(
            memories=[memory],
            formatted_prompt="Test prompt",
            retrieval_time_ms=50.0,
            memory_ids=[memory.memory_id],
            query="test query",
        )

        assert len(context.memories) == 1
        assert context.formatted_prompt == "Test prompt"
        assert context.retrieval_time_ms == 50.0
        assert len(context.memory_ids) == 1
        assert context.query == "test query"


class TestMemoryUsageStats:
    """Unit tests for MemoryUsageStats dataclass."""

    def test_memory_usage_stats_creation(self):
        """Test MemoryUsageStats creation."""
        memory_id = uuid4()
        now = datetime.utcnow()

        stats = MemoryUsageStats(
            memory_id=memory_id, usage_count=5, last_used=now, relevance_boost=0.3
        )

        assert stats.memory_id == memory_id
        assert stats.usage_count == 5
        assert stats.last_used == now
        assert stats.relevance_boost == 0.3
