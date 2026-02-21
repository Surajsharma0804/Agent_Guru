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
