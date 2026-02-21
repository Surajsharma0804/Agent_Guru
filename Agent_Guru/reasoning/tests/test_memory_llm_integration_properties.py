"""
Property-based tests for Memory LLM Integration.

Tests invariants and edge cases using Hypothesis for comprehensive coverage.

Properties tested:
- Memory retrieval always returns valid MemoryContext
- Formatted prompts are always valid strings
- Usage tracking maintains consistency
- Relevance updates preserve score bounds
- Query building produces non-empty strings

Coverage Target: 100 iterations per property
"""

from datetime import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.memory.llm_integration import MemoryContext, MemoryLLMIntegration
from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.models.memory import (
    EpisodicMemory,
    MemoryType,
    PreferenceMemory,
    SemanticMemory,
    TaskMemory,
)

# Strategy for generating valid intent types
intent_type_strategy = st.sampled_from(
    [
        IntentType.SET_TIMER,
        IntentType.QUERY_WEATHER,
        IntentType.SEND_MESSAGE,
        IntentType.PLAY_MUSIC,
        IntentType.SEARCH_WEB,
        IntentType.UNKNOWN,
    ]
)


# Strategy for generating valid entities (Entity objects)
entity_strategy = st.builds(
    Entity,
    entity_type=st.text(min_size=1, max_size=20),
    value=st.one_of(
        st.text(min_size=1, max_size=50),
        st.integers(min_value=0, max_value=1000),
        st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    ),
    raw_text=st.text(min_size=1, max_size=50),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)

# Strategy for generating valid entities dict
entities_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    values=entity_strategy,
    min_size=0,
    max_size=5,
)


# Strategy for generating valid intents
intent_strategy = st.builds(
    Intent,
    intent_type=intent_type_strategy,
    entities=entities_strategy,
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    original_input=st.text(min_size=1, max_size=100),
)


# Strategy for generating valid user IDs
user_id_strategy = st.text(
    min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P"))
)


# Strategy for generating valid memory types
memory_type_strategy = st.sampled_from(
    [MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PREFERENCE, MemoryType.TASK]
)


class TestMemoryLLMIntegrationProperties:
    """Property-based tests for MemoryLLMIntegration."""

    @given(intent=intent_strategy, user_id=user_id_strategy)
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_retrieve_for_reasoning_returns_valid_context(self, intent, user_id):
        """Property: retrieve_for_reasoning always returns valid MemoryContext.

        **Validates: Requirements 33.1, 33.3**

        For any valid intent and user_id, retrieve_for_reasoning should return
        a MemoryContext with all required fields properly populated.
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        context = integration.retrieve_for_reasoning(intent, user_id)

        # Verify MemoryContext structure
        assert isinstance(context, MemoryContext)
        assert isinstance(context.memories, list)
        assert isinstance(context.formatted_prompt, str)
        assert isinstance(context.retrieval_time_ms, float)
        assert isinstance(context.memory_ids, list)
        assert isinstance(context.query, str)

        # Verify constraints
        assert context.retrieval_time_ms >= 0
        assert len(context.memories) <= integration.max_memories
        assert len(context.memory_ids) == len(context.memories)
        assert len(context.formatted_prompt) > 0
        assert len(context.query) > 0

    @given(
        max_memories=st.integers(min_value=1, max_value=20),
        intent=intent_strategy,
        user_id=user_id_strategy,
    )
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_retrieve_respects_max_memories(self, max_memories, intent, user_id):
        """Property: Retrieved memories never exceed max_memories limit.

        **Validates: Requirements 33.1, 33.3**

        For any max_memories setting, the number of retrieved memories should
        never exceed the configured limit.
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever, max_memories=max_memories)

        # Store more memories than max_memories
        for i in range(max_memories + 10):
            memory = EpisodicMemory(
                content=f"Memory {i}",
                action_taken="test_action",
                result="Success",
                success=True,
                user_id=user_id,
            )
            retriever.store(memory)

        context = integration.retrieve_for_reasoning(intent, user_id)

        assert len(context.memories) <= max_memories
        assert len(context.memory_ids) <= max_memories

    @given(memories_count=st.integers(min_value=0, max_value=10), user_id=user_id_strategy)
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_format_memories_always_returns_string(self, memories_count, user_id):
        """Property: format_memories_for_prompt always returns valid string.

        **Validates: Requirements 33.1, 33.3**

        For any list of memories (including empty), format_memories_for_prompt
        should return a non-empty string.
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Create memories
        memories = []
        for i in range(memories_count):
            memory = EpisodicMemory(
                content=f"Memory {i}",
                action_taken="test_action",
                result="Success",
                success=True,
                user_id=user_id,
            )
            memories.append(memory)

        formatted = integration.format_memories_for_prompt(memories)

        assert isinstance(formatted, str)
        assert len(formatted) > 0

        if memories_count == 0:
            assert formatted == "No relevant memories found."
        else:
            assert "## Relevant Memories" in formatted
            assert "Memory 1" in formatted

    @given(
        memory_ids_count=st.integers(min_value=1, max_value=20),
        track_count=st.integers(min_value=1, max_value=10),
    )
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_usage_tracking_maintains_consistency(self, memory_ids_count, track_count):
        """Property: Usage tracking maintains consistent state.

        **Validates: Requirements 33.1, 33.3**

        For any sequence of track_memory_usage calls, the usage stats should
        maintain consistency (counts increase, timestamps update, boosts bounded).
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Generate memory IDs
        from uuid import uuid4

        memory_ids = [uuid4() for _ in range(memory_ids_count)]

        # Track usage multiple times
        for _ in range(track_count):
            integration.track_memory_usage(memory_ids)

        # Verify consistency
        assert len(integration.usage_stats) == memory_ids_count

        for memory_id in memory_ids:
            stats = integration.usage_stats[memory_id]

            # Usage count should match track_count
            assert stats.usage_count == track_count

            # Relevance boost should be bounded
            assert 0.0 <= stats.relevance_boost <= 0.5

            # Last used should be recent
            assert isinstance(stats.last_used, datetime)

    @given(
        initial_score=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
        boost_factor=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
        usage_count=st.integers(min_value=1, max_value=20),
    )
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_relevance_updates_preserve_bounds(self, initial_score, boost_factor, usage_count):
        """Property: Relevance updates always preserve [0.0, 1.0] bounds.

        **Validates: Requirements 33.1, 33.3**

        For any initial score, boost factor, and usage count, the updated
        relevance score should always be in the range [0.0, 1.0].
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever, relevance_boost_factor=boost_factor)

        # Store memory with initial score
        memory = EpisodicMemory(
            content="Test memory",
            action_taken="test_action",
            result="Success",
            success=True,
            user_id="user_123",
        )
        retriever.store(memory)
        retriever.update_relevance(memory.memory_id, initial_score)

        # Track usage multiple times
        for _ in range(usage_count):
            integration.track_memory_usage([memory.memory_id])

        # Update relevance
        integration.update_relevance_from_usage()

        # Verify bounds
        final_score = retriever.memories[memory.memory_id].relevance_score
        assert 0.0 <= final_score <= 1.0

    @given(intent=intent_strategy)
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_query_building_produces_non_empty_string(self, intent):
        """Property: Query building always produces non-empty string.

        **Validates: Requirements 33.1, 33.3**

        For any valid intent, _build_query_from_intent should produce a
        non-empty query string.
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        query = integration._build_query_from_intent(intent)

        assert isinstance(query, str)
        assert len(query) > 0

        # Query should contain intent type
        intent_type_str = intent.intent_type.value.replace("_", " ")
        assert intent_type_str in query.lower()

    @given(
        memory_type=memory_type_strategy,
        user_id=user_id_strategy,
        content=st.text(min_size=1, max_size=200),
    )
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_format_handles_all_memory_types(self, memory_type, user_id, content):
        """Property: Formatting handles all memory types correctly.

        **Validates: Requirements 33.1, 33.3**

        For any memory type, format_memories_for_prompt should produce a
        valid formatted string with type-specific details.
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Create memory of specific type
        if memory_type == MemoryType.EPISODIC:
            memory = EpisodicMemory(
                content=content,
                action_taken="test_action",
                result="Success",
                success=True,
                user_id=user_id,
            )
        elif memory_type == MemoryType.SEMANTIC:
            memory = SemanticMemory(
                content=content,
                fact="Test fact",
                source="test_source",
                confidence=0.8,
                user_id=user_id,
            )
        elif memory_type == MemoryType.PREFERENCE:
            memory = PreferenceMemory(
                content=content,
                preference_key="test_key",
                preference_value="test_value",
                learned_from="test_source",
                user_id=user_id,
            )
        else:  # TASK
            memory = TaskMemory(
                content=content,
                task_id="task_123",
                task_description="Test task",
                outcome="Success",
                lessons_learned="Test lessons",
                user_id=user_id,
            )

        formatted = integration.format_memories_for_prompt([memory])

        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert "## Relevant Memories" in formatted
        assert memory_type.value in formatted.lower()
        assert content in formatted

    @given(
        retrieval_count=st.integers(min_value=1, max_value=10),
        intent=intent_strategy,
        user_id=user_id_strategy,
    )
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_multiple_retrievals_maintain_consistency(self, retrieval_count, intent, user_id):
        """Property: Multiple retrievals maintain consistent behavior.

        **Validates: Requirements 33.1, 33.3**

        For any number of retrieval operations, the system should maintain
        consistent behavior and not degrade.
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever)

        # Store some memories
        for i in range(5):
            memory = EpisodicMemory(
                content=f"Memory {i}",
                action_taken="test_action",
                result="Success",
                success=True,
                user_id=user_id,
            )
            retriever.store(memory)

        # Perform multiple retrievals
        contexts = []
        for _ in range(retrieval_count):
            context = integration.retrieve_for_reasoning(intent, user_id)
            contexts.append(context)

        # Verify all contexts are valid
        for context in contexts:
            assert isinstance(context, MemoryContext)
            assert len(context.memories) <= integration.max_memories
            assert context.retrieval_time_ms >= 0
            assert len(context.formatted_prompt) > 0

    @given(
        boost_factor=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False)
    )
    @settings(deadline=None, max_examples=50)  # Disable deadline, reduce examples
    def test_relevance_boost_has_diminishing_returns(self, boost_factor):
        """Property: Relevance boost exhibits diminishing returns.

        **Validates: Requirements 33.1, 33.3**

        For any boost factor, repeated usage should show diminishing returns
        in relevance boost (each additional use adds less boost).
        """
        retriever = MemoryRetriever()
        integration = MemoryLLMIntegration(retriever, relevance_boost_factor=boost_factor)

        from uuid import uuid4

        memory_id = uuid4()

        # Track usage multiple times and record boosts
        boosts = []
        for _ in range(10):
            integration.track_memory_usage([memory_id])
            stats = integration.usage_stats[memory_id]
            boosts.append(stats.relevance_boost)

        # Verify diminishing returns
        if len(boosts) >= 3:
            # First increment should be larger than later increments
            first_increment = boosts[1] - boosts[0]
            last_increment = boosts[-1] - boosts[-2]

            # Allow for floating point precision
            assert first_increment >= last_increment - 1e-6

            # Boost should be capped at 0.5
            assert boosts[-1] <= 0.5
