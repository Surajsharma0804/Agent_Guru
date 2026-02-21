"""
Tests for Conversation State Manager.

Coverage target: >80%
"""

import asyncio
from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
    TrackedEntity,
)
from Agent_Guru.reasoning.state.conversation_manager import (
    ConversationStateManager,
)


class TestInitialization:
    """Test conversation state manager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        manager = ConversationStateManager()

        assert manager.max_conversations == 10000
        assert manager.inactivity_timeout == 3600.0
        assert len(manager._cache) == 0

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        manager = ConversationStateManager(max_conversations=100, inactivity_timeout=600.0)

        assert manager.max_conversations == 100
        assert manager.inactivity_timeout == 600.0

    def test_init_with_invalid_max_conversations(self):
        """Test initialization with invalid max_conversations."""
        with pytest.raises(ValueError, match="max_conversations must be positive"):
            ConversationStateManager(max_conversations=0)

        with pytest.raises(ValueError, match="max_conversations must be positive"):
            ConversationStateManager(max_conversations=-1)

    def test_init_with_invalid_timeout(self):
        """Test initialization with invalid timeout."""
        with pytest.raises(ValueError, match="inactivity_timeout must be positive"):
            ConversationStateManager(inactivity_timeout=0)

        with pytest.raises(ValueError, match="inactivity_timeout must be positive"):
            ConversationStateManager(inactivity_timeout=-1)


class TestStateOperations:
    """Test basic state operations."""

    @pytest.fixture
    def manager(self):
        """Create conversation state manager."""
        return ConversationStateManager(max_conversations=10, inactivity_timeout=1.0)

    @pytest.fixture
    def sample_state(self):
        """Create sample conversation state."""
        return ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

    @pytest.mark.asyncio
    async def test_get_nonexistent_state(self, manager):
        """Test getting nonexistent state returns None."""
        state = await manager.get_state("nonexistent")
        assert state is None

    @pytest.mark.asyncio
    async def test_set_and_get_state(self, manager, sample_state):
        """Test setting and getting state."""
        await manager.set_state("conv_123", sample_state)

        retrieved = await manager.get_state("conv_123")
        assert retrieved is not None
        assert retrieved.conversation_id == "conv_123"
        assert retrieved.user_id == "user_456"

    @pytest.mark.asyncio
    async def test_update_existing_state(self, manager, sample_state):
        """Test updating existing state."""
        await manager.set_state("conv_123", sample_state)

        # Update state
        turn = ConversationTurn(
            turn_id="turn_1",
            turn_number=0,
            user_input="Hello",
            timestamp=datetime.now(),
        )
        sample_state.turns.append(turn)
        await manager.set_state("conv_123", sample_state)

        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 1

    @pytest.mark.asyncio
    async def test_delete_state(self, manager, sample_state):
        """Test deleting state."""
        await manager.set_state("conv_123", sample_state)

        deleted = await manager.delete_state("conv_123")
        assert deleted is True

        state = await manager.get_state("conv_123")
        assert state is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_state(self, manager):
        """Test deleting nonexistent state."""
        deleted = await manager.delete_state("nonexistent")
        assert deleted is False


class TestLRUEviction:
    """Test LRU eviction behavior."""

    @pytest.fixture
    def manager(self):
        """Create manager with small cache."""
        return ConversationStateManager(max_conversations=3, inactivity_timeout=10.0)

    @pytest.mark.asyncio
    async def test_evict_oldest_when_full(self, manager):
        """Test that oldest conversation is evicted when cache is full."""
        # Add 3 conversations
        for i in range(3):
            state = ConversationState(
                conversation_id=f"conv_{i}",
                user_id=f"user_{i}",
                turns=[],
                entities={},
            )
            await manager.set_state(f"conv_{i}", state)

        # Add 4th conversation - should evict conv_0
        state = ConversationState(
            conversation_id="conv_3",
            user_id="user_3",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_3", state)

        # conv_0 should be evicted
        assert await manager.get_state("conv_0") is None
        assert await manager.get_state("conv_1") is not None
        assert await manager.get_state("conv_2") is not None
        assert await manager.get_state("conv_3") is not None

    @pytest.mark.asyncio
    async def test_access_updates_lru_order(self, manager):
        """Test that accessing a conversation updates LRU order."""
        # Add 3 conversations
        for i in range(3):
            state = ConversationState(
                conversation_id=f"conv_{i}",
                user_id=f"user_{i}",
                turns=[],
                entities={},
            )
            await manager.set_state(f"conv_{i}", state)

        # Access conv_0 to move it to end
        await manager.get_state("conv_0")

        # Add 4th conversation - should evict conv_1 (now oldest)
        state = ConversationState(
            conversation_id="conv_3",
            user_id="user_3",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_3", state)

        # conv_1 should be evicted, conv_0 should still exist
        assert await manager.get_state("conv_0") is not None
        assert await manager.get_state("conv_1") is None
        assert await manager.get_state("conv_2") is not None
        assert await manager.get_state("conv_3") is not None


class TestTimeoutEviction:
    """Test timeout-based eviction."""

    @pytest.fixture
    def manager(self):
        """Create manager with short timeout."""
        return ConversationStateManager(max_conversations=10, inactivity_timeout=0.1)

    @pytest.mark.asyncio
    async def test_expired_state_returns_none(self, manager):
        """Test that expired state returns None."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Wait for expiration
        await asyncio.sleep(0.15)

        retrieved = await manager.get_state("conv_123")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_non_expired_state_returns_value(self, manager):
        """Test that non-expired state returns value."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Access before expiration
        await asyncio.sleep(0.05)

        retrieved = await manager.get_state("conv_123")
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_evict_expired_removes_old_conversations(self, manager):
        """Test that evict_expired removes old conversations."""
        # Add 3 conversations
        for i in range(3):
            state = ConversationState(
                conversation_id=f"conv_{i}",
                user_id=f"user_{i}",
                turns=[],
                entities={},
            )
            await manager.set_state(f"conv_{i}", state)

        # Wait for expiration
        await asyncio.sleep(0.15)

        # Evict expired
        evicted = await manager.evict_expired()
        assert evicted == 3

        # All should be gone
        for i in range(3):
            assert await manager.get_state(f"conv_{i}") is None


class TestTurnManagement:
    """Test conversation turn management."""

    @pytest.fixture
    def manager(self):
        """Create conversation state manager."""
        return ConversationStateManager()

    @pytest.fixture
    def sample_turn(self):
        """Create sample conversation turn."""
        return ConversationTurn(
            turn_id="turn_1",
            turn_number=0,
            user_input="Hello",
            timestamp=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_add_turn_creates_new_state(self, manager, sample_turn):
        """Test that adding turn creates new state if not exists."""
        await manager.add_turn("conv_123", sample_turn)

        state = await manager.get_state("conv_123")
        assert state is not None
        assert len(state.turns) == 1
        assert state.turns[0].user_input == "Hello"

    @pytest.mark.asyncio
    async def test_add_turn_to_existing_state(self, manager, sample_turn):
        """Test adding turn to existing state."""
        # Create initial state
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Add turn
        await manager.add_turn("conv_123", sample_turn)

        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 1

    @pytest.mark.asyncio
    async def test_get_recent_turns(self, manager):
        """Test getting recent turns."""
        # Add multiple turns
        for i in range(5):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            await manager.add_turn("conv_123", turn)

        # Get recent turns
        turns = await manager.get_recent_turns("conv_123", max_turns=3)
        assert len(turns) == 3
        assert turns[0].user_input == "Message 2"
        assert turns[2].user_input == "Message 4"

    @pytest.mark.asyncio
    async def test_get_recent_turns_nonexistent(self, manager):
        """Test getting turns from nonexistent conversation."""
        turns = await manager.get_recent_turns("nonexistent")
        assert turns == []


class TestEntityTracking:
    """Test entity tracking."""

    @pytest.fixture
    def manager(self):
        """Create conversation state manager."""
        return ConversationStateManager()

    @pytest.fixture
    def sample_entity(self):
        """Create sample tracked entity."""
        return TrackedEntity(
            entity_type="person",
            value="John",
            first_mentioned=1,
            last_mentioned=1,
            mention_count=1,
        )

    @pytest.mark.asyncio
    async def test_track_entity(self, manager, sample_entity):
        """Test tracking an entity."""
        # Create state first
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track entity
        await manager.track_entity("conv_123", sample_entity)

        entities = await manager.get_tracked_entities("conv_123")
        assert "person:John" in entities
        assert entities["person:John"].value == "John"

    @pytest.mark.asyncio
    async def test_track_entity_nonexistent_conversation(self, manager, sample_entity):
        """Test tracking entity in nonexistent conversation."""
        # Should not raise error
        await manager.track_entity("nonexistent", sample_entity)

        entities = await manager.get_tracked_entities("nonexistent")
        assert entities == {}

    @pytest.mark.asyncio
    async def test_get_tracked_entities_empty(self, manager):
        """Test getting entities from conversation with no entities."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        entities = await manager.get_tracked_entities("conv_123")
        assert entities == {}


class TestUtilityMethods:
    """Test utility methods."""

    @pytest.fixture
    def manager(self):
        """Create conversation state manager."""
        return ConversationStateManager()

    @pytest.mark.asyncio
    async def test_get_active_count(self, manager):
        """Test getting active conversation count."""
        assert await manager.get_active_count() == 0

        # Add conversations
        for i in range(3):
            state = ConversationState(
                conversation_id=f"conv_{i}",
                user_id=f"user_{i}",
                turns=[],
                entities={},
            )
            await manager.set_state(f"conv_{i}", state)

        assert await manager.get_active_count() == 3

    @pytest.mark.asyncio
    async def test_clear(self, manager):
        """Test clearing all conversations."""
        # Add conversations
        for i in range(3):
            state = ConversationState(
                conversation_id=f"conv_{i}",
                user_id=f"user_{i}",
                turns=[],
                entities={},
            )
            await manager.set_state(f"conv_{i}", state)

        await manager.clear()

        assert await manager.get_active_count() == 0


class TestConcurrency:
    """Test concurrent access."""

    @pytest.fixture
    def manager(self):
        """Create conversation state manager."""
        return ConversationStateManager()

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, manager):
        """Test concurrent reads are safe."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Concurrent reads
        tasks = [manager.get_state("conv_123") for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert all(r is not None for r in results)
        assert all(r.conversation_id == "conv_123" for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, manager):
        """Test concurrent writes are safe."""
        # Concurrent writes
        tasks = []
        for i in range(10):
            state = ConversationState(
                conversation_id=f"conv_{i}",
                user_id=f"user_{i}",
                turns=[],
                entities={},
            )
            tasks.append(manager.set_state(f"conv_{i}", state))

        await asyncio.gather(*tasks)

        assert await manager.get_active_count() == 10


class TestConversationStateManagerProperties:
    """Property-based tests for conversation state manager."""

    @given(
        max_conversations=st.integers(min_value=1, max_value=1000),
        inactivity_timeout=st.floats(min_value=0.1, max_value=3600.0),
    )
    def test_valid_initialization_always_works(
        self, max_conversations: int, inactivity_timeout: float
    ):
        """Property: Valid parameters always create manager."""
        manager = ConversationStateManager(
            max_conversations=max_conversations,
            inactivity_timeout=inactivity_timeout,
        )

        assert manager.max_conversations == max_conversations
        assert manager.inactivity_timeout == inactivity_timeout

    @pytest.mark.asyncio
    @given(
        conversation_id=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        user_id=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
    )
    @settings(deadline=500)
    async def test_set_and_get_always_consistent(self, conversation_id: str, user_id: str):
        """Property: Set and get are always consistent."""
        manager = ConversationStateManager()

        state = ConversationState(
            conversation_id=conversation_id,
            user_id=user_id,
            turns=[],
            entities={},
        )

        await manager.set_state(conversation_id, state)
        retrieved = await manager.get_state(conversation_id)

        assert retrieved is not None
        assert retrieved.conversation_id == conversation_id
        assert retrieved.user_id == user_id

    @pytest.mark.asyncio
    @given(
        num_conversations=st.integers(min_value=1, max_value=20),
    )
    @settings(deadline=1000)
    async def test_active_count_always_accurate(self, num_conversations: int):
        """Property: Active count is always accurate."""
        manager = ConversationStateManager(max_conversations=100)

        # Add conversations
        for i in range(num_conversations):
            state = ConversationState(
                conversation_id=f"conv_{i}",
                user_id=f"user_{i}",
                turns=[],
                entities={},
            )
            await manager.set_state(f"conv_{i}", state)

        count = await manager.get_active_count()
        assert count == num_conversations


class TestHistoryManagement:
    """Test conversation history management (Task 10.2)."""

    @pytest.fixture
    def manager(self):
        """Create conversation state manager."""
        return ConversationStateManager()

    @pytest.fixture
    def state_with_many_turns(self):
        """Create state with many turns."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        # Add 30 turns
        for i in range(30):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            state.turns.append(turn)

        return state

    @pytest.mark.asyncio
    async def test_prune_turns_no_pruning_needed(self, manager):
        """Test pruning when no pruning is needed."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        # Add 10 turns
        for i in range(10):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            state.turns.append(turn)

        await manager.set_state("conv_123", state)

        # Prune with max_turns=20 (no pruning needed)
        pruned = await manager.prune_turns("conv_123", max_turns=20)
        assert pruned == 0

        # Verify turns unchanged
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 10

    @pytest.mark.asyncio
    async def test_prune_turns_removes_old_turns(self, manager, state_with_many_turns):
        """Test pruning removes old turns."""
        await manager.set_state("conv_123", state_with_many_turns)

        # Prune to 20 turns
        pruned = await manager.prune_turns("conv_123", max_turns=20)
        assert pruned == 10

        # Verify only 20 most recent turns remain
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 20
        assert retrieved.turns[0].user_input == "Message 10"
        assert retrieved.turns[-1].user_input == "Message 29"

    @pytest.mark.asyncio
    async def test_prune_turns_nonexistent_conversation(self, manager):
        """Test pruning nonexistent conversation."""
        pruned = await manager.prune_turns("nonexistent", max_turns=20)
        assert pruned == 0

    @pytest.mark.asyncio
    async def test_generate_summary(self, manager, state_with_many_turns):
        """Test generating conversation summary."""
        await manager.set_state("conv_123", state_with_many_turns)

        # Mock LLM function
        async def mock_llm_generate(turns):
            return f"Summary of {len(turns)} turns"

        summary = await manager.generate_summary("conv_123", mock_llm_generate)
        assert summary == "Summary of 30 turns"

        # Verify summary stored in state
        retrieved = await manager.get_state("conv_123")
        assert retrieved.context_summary == "Summary of 30 turns"

    @pytest.mark.asyncio
    async def test_generate_summary_nonexistent_conversation(self, manager):
        """Test generating summary for nonexistent conversation."""

        async def mock_llm_generate(turns):
            return "Summary"

        summary = await manager.generate_summary("nonexistent", mock_llm_generate)
        assert summary is None

    @pytest.mark.asyncio
    async def test_compress_context_no_compression_needed(self, manager):
        """Test compression when not needed."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        # Add 10 turns
        for i in range(10):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            state.turns.append(turn)

        await manager.set_state("conv_123", state)

        # Compress with max_turns=20 (no compression needed)
        compressed = await manager.compress_context("conv_123", max_turns=20)
        assert compressed is False

        # Verify turns unchanged
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 10

    @pytest.mark.asyncio
    async def test_compress_context_with_summary(self, manager, state_with_many_turns):
        """Test compression with summary generation."""
        await manager.set_state("conv_123", state_with_many_turns)

        # Mock LLM function
        async def mock_llm_generate(turns):
            return f"Summary of {len(turns)} old turns"

        # Compress to 20 turns
        compressed = await manager.compress_context(
            "conv_123", max_turns=20, llm_generate_fn=mock_llm_generate
        )
        assert compressed is True

        # Verify compression
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 20
        assert retrieved.context_summary == "Summary of 10 old turns"
        assert retrieved.turns[0].user_input == "Message 10"

    @pytest.mark.asyncio
    async def test_compress_context_without_summary(self, manager, state_with_many_turns):
        """Test compression without summary generation."""
        await manager.set_state("conv_123", state_with_many_turns)

        # Compress without LLM function
        compressed = await manager.compress_context("conv_123", max_turns=20)
        assert compressed is True

        # Verify compression without summary
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 20
        assert retrieved.context_summary is None

    @pytest.mark.asyncio
    async def test_compress_context_nonexistent_conversation(self, manager):
        """Test compressing nonexistent conversation."""
        compressed = await manager.compress_context("nonexistent", max_turns=20)
        assert compressed is False

    @pytest.mark.asyncio
    async def test_fixed_size_deque_behavior(self, manager):
        """Test that turns behave like fixed-size deque."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Add 25 turns
        for i in range(25):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            await manager.add_turn("conv_123", turn)

        # Prune to 20
        await manager.prune_turns("conv_123", max_turns=20)

        # Add 5 more turns
        for i in range(25, 30):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            await manager.add_turn("conv_123", turn)

        # Should have 25 turns now
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 25

        # Prune again
        await manager.prune_turns("conv_123", max_turns=20)
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 20
        assert retrieved.turns[0].user_input == "Message 10"
        assert retrieved.turns[-1].user_input == "Message 29"


class TestHistoryManagementProperties:
    """Property-based tests for history management."""

    @pytest.mark.asyncio
    @given(
        num_turns=st.integers(min_value=1, max_value=50),
        max_turns=st.integers(min_value=1, max_value=20),
    )
    @settings(deadline=1000)
    async def test_prune_respects_max_turns(self, num_turns: int, max_turns: int):
        """Property: After pruning, turns <= max_turns."""
        manager = ConversationStateManager()

        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        # Add turns
        for i in range(num_turns):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            state.turns.append(turn)

        await manager.set_state("conv_123", state)

        # Prune
        await manager.prune_turns("conv_123", max_turns=max_turns)

        # Verify
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) <= max_turns

    @pytest.mark.asyncio
    @given(
        num_turns=st.integers(min_value=21, max_value=50),
    )
    @settings(deadline=1000)
    async def test_compression_always_reduces_size(self, num_turns: int):
        """Property: Compression always reduces turn count when needed."""
        manager = ConversationStateManager()

        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        # Add turns
        for i in range(num_turns):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            state.turns.append(turn)

        await manager.set_state("conv_123", state)

        # Compress to 20 turns
        compressed = await manager.compress_context("conv_123", max_turns=20)
        assert compressed is True

        # Verify size reduced
        retrieved = await manager.get_state("conv_123")
        assert len(retrieved.turns) == 20


class TestEntityTrackingAcrossTurns:
    """Test entity tracking across turns (Task 10.3)."""

    @pytest.fixture
    def manager(self):
        """Create conversation state manager."""
        return ConversationStateManager()

    @pytest.mark.asyncio
    async def test_extract_and_track_entities(self, manager):
        """Test extracting and tracking entities from turns."""
        # Create state
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Extract and track entities from turn 0
        entities = {
            "person": "John",
            "location": "Seattle",
            "time": "3pm",
        }
        await manager.extract_and_track_entities("conv_123", 0, entities)

        # Verify entities tracked
        tracked = await manager.get_tracked_entities("conv_123")
        assert "person:John" in tracked
        assert "location:Seattle" in tracked
        assert "time:3pm" in tracked
        assert tracked["person:John"].first_mentioned == 0
        assert tracked["person:John"].last_mentioned == 0
        assert tracked["person:John"].mention_count == 1

    @pytest.mark.asyncio
    async def test_entity_mention_count_updates(self, manager):
        """Test that entity mention count updates correctly."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Mention John in turn 0
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})

        # Mention John again in turn 2
        await manager.extract_and_track_entities("conv_123", 2, {"person": "John"})

        # Verify mention tracking
        tracked = await manager.get_tracked_entities("conv_123")
        john = tracked["person:John"]
        assert john.first_mentioned == 0
        assert john.last_mentioned == 2
        assert john.mention_count == 2

    @pytest.mark.asyncio
    async def test_resolve_coreference_by_type(self, manager):
        """Test resolving coreference to most recent entity of type."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track multiple people
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})
        await manager.extract_and_track_entities("conv_123", 1, {"person": "Mary"})
        await manager.extract_and_track_entities("conv_123", 2, {"person": "Bob"})

        # Resolve "he" to most recent person
        resolved = await manager.resolve_coreference("conv_123", "he", "person")
        assert resolved is not None
        assert resolved.value == "Bob"
        assert resolved.last_mentioned == 2

    @pytest.mark.asyncio
    async def test_resolve_coreference_any_type(self, manager):
        """Test resolving coreference to most recent entity of any type."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track different entity types
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})
        await manager.extract_and_track_entities("conv_123", 1, {"location": "Seattle"})
        await manager.extract_and_track_entities("conv_123", 2, {"app": "Spotify"})

        # Resolve "it" to most recent entity (any type)
        resolved = await manager.resolve_coreference("conv_123", "it")
        assert resolved is not None
        assert resolved.value == "Spotify"
        assert resolved.last_mentioned == 2

    @pytest.mark.asyncio
    async def test_resolve_coreference_no_entities(self, manager):
        """Test resolving coreference when no entities exist."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Resolve with no entities
        resolved = await manager.resolve_coreference("conv_123", "he", "person")
        assert resolved is None

    @pytest.mark.asyncio
    async def test_expire_old_entities(self, manager):
        """Test expiring entities not mentioned recently."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track entities at different turns
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})
        await manager.extract_and_track_entities("conv_123", 5, {"person": "Mary"})
        await manager.extract_and_track_entities("conv_123", 15, {"person": "Bob"})

        # Expire entities not mentioned in last 10 turns (current turn = 20)
        expired = await manager.expire_old_entities("conv_123", 20, max_turns_without_mention=10)
        assert expired == 2  # John and Mary expired

        # Verify only Bob remains
        tracked = await manager.get_tracked_entities("conv_123")
        assert len(tracked) == 1
        assert "person:Bob" in tracked

    @pytest.mark.asyncio
    async def test_expire_old_entities_none_expired(self, manager):
        """Test expiring when all entities are recent."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track recent entities
        await manager.extract_and_track_entities("conv_123", 15, {"person": "John"})
        await manager.extract_and_track_entities("conv_123", 18, {"person": "Mary"})

        # Expire with current turn = 20 (all within 10 turns)
        expired = await manager.expire_old_entities("conv_123", 20, max_turns_without_mention=10)
        assert expired == 0

        # Verify all entities remain
        tracked = await manager.get_tracked_entities("conv_123")
        assert len(tracked) == 2

    @pytest.mark.asyncio
    async def test_get_entity_by_type(self, manager):
        """Test getting most recent entity by type."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track multiple entities of same type
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})
        await manager.extract_and_track_entities("conv_123", 2, {"person": "Mary"})

        # Get most recent person
        entity = await manager.get_entity_by_type("conv_123", "person")
        assert entity is not None
        assert entity.value == "Mary"
        assert entity.last_mentioned == 2

    @pytest.mark.asyncio
    async def test_get_entity_by_type_not_found(self, manager):
        """Test getting entity by type when type doesn't exist."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Get non-existent type
        entity = await manager.get_entity_by_type("conv_123", "location")
        assert entity is None


class TestEntityTrackingProperties:
    """Property-based tests for entity tracking."""

    @pytest.mark.asyncio
    @given(
        num_entities=st.integers(min_value=1, max_value=20),
        current_turn=st.integers(min_value=20, max_value=50),
        max_turns=st.integers(min_value=5, max_value=15),
    )
    @settings(deadline=1000)
    async def test_expire_removes_old_entities(
        self, num_entities: int, current_turn: int, max_turns: int
    ):
        """Property: Expire removes entities older than threshold."""
        manager = ConversationStateManager()

        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track entities at various turns
        for i in range(num_entities):
            turn = i  # Entities at turns 0, 1, 2, ...
            await manager.extract_and_track_entities("conv_123", turn, {"entity": f"entity_{i}"})

        # Expire old entities
        await manager.expire_old_entities("conv_123", current_turn, max_turns)

        # Verify remaining entities are within threshold
        tracked = await manager.get_tracked_entities("conv_123")
        for entity in tracked.values():
            assert current_turn - entity.last_mentioned <= max_turns


class TestReferenceResolution:
    """Test reference resolution (Task 10.4)."""

    @pytest.fixture
    def manager(self):
        """Create conversation state manager."""
        return ConversationStateManager()

    @pytest.mark.asyncio
    async def test_resolve_pronoun_he(self, manager):
        """Test resolving 'he' pronoun."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track a person
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})

        # Resolve "he"
        resolved = await manager.resolve_pronoun("conv_123", "he")
        assert resolved is not None
        assert resolved.value == "John"

    @pytest.mark.asyncio
    async def test_resolve_pronoun_it(self, manager):
        """Test resolving 'it' pronoun to non-person entity."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track person and app
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})
        await manager.extract_and_track_entities("conv_123", 1, {"app": "Spotify"})

        # Resolve "it" should get Spotify (non-person)
        resolved = await manager.resolve_pronoun("conv_123", "it")
        assert resolved is not None
        assert resolved.value == "Spotify"

    @pytest.mark.asyncio
    async def test_resolve_pronoun_case_insensitive(self, manager):
        """Test pronoun resolution is case insensitive."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        await manager.extract_and_track_entities("conv_123", 0, {"person": "Mary"})

        # Test various cases
        for pronoun in ["She", "SHE", "she", "HER", "her"]:
            resolved = await manager.resolve_pronoun("conv_123", pronoun)
            assert resolved is not None
            assert resolved.value == "Mary"

    @pytest.mark.asyncio
    async def test_resolve_implicit_reference(self, manager):
        """Test resolving implicit reference from context."""
        from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType

        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        # Set last intent
        state.last_intent = Intent(
            intent_type=IntentType.QUERY_WEATHER,
            confidence=0.9,
            original_input="weather in NYC",
            entities={"location": Entity(entity_type="location", value="NYC", raw_text="NYC")},
        )

        await manager.set_state("conv_123", state)

        # Resolve "what about tomorrow?"
        resolved = await manager.resolve_implicit_reference("conv_123", "what about tomorrow?")
        assert resolved is not None
        assert resolved["intent_type"] == IntentType.QUERY_WEATHER
        assert "location" in resolved["entities"]

    @pytest.mark.asyncio
    async def test_resolve_implicit_reference_no_context(self, manager):
        """Test implicit reference with no context."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # No last intent
        resolved = await manager.resolve_implicit_reference("conv_123", "what about tomorrow?")
        assert resolved is None

    @pytest.mark.asyncio
    async def test_complete_incomplete_request_time(self, manager):
        """Test completing incomplete request with time reference."""
        from Agent_Guru.reasoning.models.intent import Intent, IntentType

        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        state.last_intent = Intent(
            intent_type=IntentType.QUERY_WEATHER,
            confidence=0.9,
            original_input="weather today",
            entities={},
        )

        await manager.set_state("conv_123", state)

        # Complete "tomorrow"
        completed = await manager.complete_incomplete_request("conv_123", "tomorrow")
        assert completed is not None
        assert "query_weather" in completed.lower()
        assert "tomorrow" in completed.lower()

    @pytest.mark.asyncio
    async def test_complete_incomplete_request_duration(self, manager):
        """Test completing incomplete request with duration."""
        from Agent_Guru.reasoning.models.intent import Intent, IntentType

        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        state.last_intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.9,
            original_input="set timer",
            entities={},
        )

        await manager.set_state("conv_123", state)

        # Complete "5 minutes"
        completed = await manager.complete_incomplete_request("conv_123", "5 minutes")
        assert completed is not None
        assert "set_timer" in completed.lower()
        assert "5 minutes" in completed.lower()

    @pytest.mark.asyncio
    async def test_complete_incomplete_request_location(self, manager):
        """Test completing incomplete request with location."""
        from Agent_Guru.reasoning.models.intent import Intent, IntentType

        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )

        state.last_intent = Intent(
            intent_type=IntentType.QUERY_WEATHER,
            confidence=0.9,
            original_input="weather",
            entities={},
        )

        await manager.set_state("conv_123", state)

        # Complete "Seattle" (capitalized single word)
        completed = await manager.complete_incomplete_request("conv_123", "Seattle")
        assert completed is not None
        assert "query_weather" in completed.lower()
        assert "Seattle" in completed

    @pytest.mark.asyncio
    async def test_complete_incomplete_request_no_context(self, manager):
        """Test completing request with no context."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # No last intent
        completed = await manager.complete_incomplete_request("conv_123", "tomorrow")
        assert completed is None

    @pytest.mark.asyncio
    async def test_detect_ambiguous_reference_multiple_people(self, manager):
        """Test detecting ambiguous reference with multiple people."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track multiple people recently
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})
        await manager.extract_and_track_entities("conv_123", 1, {"person": "Mary"})

        # "they" is ambiguous
        ambiguous = await manager.detect_ambiguous_reference("conv_123", "they")
        assert ambiguous is not None
        assert len(ambiguous) == 2

    @pytest.mark.asyncio
    async def test_detect_ambiguous_reference_single_person(self, manager):
        """Test no ambiguity with single person."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track single person
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})

        # "they" is not ambiguous with single person
        ambiguous = await manager.detect_ambiguous_reference("conv_123", "they")
        assert ambiguous is None

    @pytest.mark.asyncio
    async def test_detect_ambiguous_reference_old_mentions(self, manager):
        """Test ambiguity detection ignores old mentions."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            turns=[],
            entities={},
        )
        await manager.set_state("conv_123", state)

        # Track people at different times
        await manager.extract_and_track_entities("conv_123", 0, {"person": "John"})  # Old
        await manager.extract_and_track_entities("conv_123", 10, {"person": "Mary"})  # Recent

        # Add many turns to make John old
        for i in range(11, 20):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                turn_number=i,
                user_input=f"Message {i}",
                timestamp=datetime.now(),
            )
            await manager.add_turn("conv_123", turn)

        # "they" should not be ambiguous (John is too old)
        ambiguous = await manager.detect_ambiguous_reference("conv_123", "they")
        assert ambiguous is None or len(ambiguous) <= 1
