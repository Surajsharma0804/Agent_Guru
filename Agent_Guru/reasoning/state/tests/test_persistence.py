"""Tests for conversation persistence."""

from datetime import datetime, timezone

import pytest

from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
)
from Agent_Guru.reasoning.state.persistence import ConversationPersistence


@pytest.fixture
async def persistence(tmp_path):
    """Create persistence instance with test database.

    The database lives under pytest's per-test tmp_path, not in the current
    working directory. The previous fixed relative path
    ("test_conversations.db") meant three things:

      * every run wrote a stray SQLite file into whatever directory pytest
        happened to be started from -- in practice the repository root;
      * two runs in parallel (pytest-xdist, or simply two terminals) shared
        one database file and corrupted each other's expectations;
      * a crash between create and teardown left the file behind, so the NEXT
        run started against a populated database.

    tmp_path is unique per test and cleaned up by pytest, which removes all
    three.
    """
    db_path = str(tmp_path / "conversations.db")

    persist = ConversationPersistence(db_path=db_path)
    await persist.initialize()

    yield persist

    await persist.close()


@pytest.fixture
def sample_state():
    """Create sample conversation state."""
    return ConversationState(
        conversation_id="conv_123",
        user_id="user_456",
        turns=[
            ConversationTurn(
                turn_id="turn_1",
                turn_number=0,
                user_input="Hello",
                timestamp=datetime.now(tz=timezone.utc),
            )
        ],
        entities={},
    )


class TestPersistence:
    """Test conversation persistence."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, persistence, sample_state):
        """Test saving and loading state."""
        await persistence.save(sample_state)

        loaded = await persistence.load("conv_123")
        assert loaded is not None  # nosec B101
        assert loaded.conversation_id == "conv_123"  # nosec B101
        assert loaded.user_id == "user_456"  # nosec B101
        assert len(loaded.turns) == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, persistence):
        """Test loading nonexistent conversation."""
        loaded = await persistence.load("nonexistent")
        assert loaded is None  # nosec B101

    @pytest.mark.asyncio
    async def test_delete(self, persistence, sample_state):
        """Test deleting conversation."""
        await persistence.save(sample_state)

        deleted = await persistence.delete("conv_123")
        assert deleted is True  # nosec B101

        loaded = await persistence.load("conv_123")
        assert loaded is None  # nosec B101

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, persistence):
        """Test deleting nonexistent conversation."""
        deleted = await persistence.delete("nonexistent")
        assert deleted is False  # nosec B101

    @pytest.mark.asyncio
    async def test_list_by_user(self, persistence):
        """Test listing conversations by user."""
        # Create multiple conversations
        for i in range(3):
            state = ConversationState(
                conversation_id=f"conv_{i}",
                user_id="user_456",
                turns=[],
                entities={},
            )
            await persistence.save(state)

        conv_ids = await persistence.list_by_user("user_456")
        assert len(conv_ids) == 3  # nosec B101
        assert "conv_0" in conv_ids  # nosec B101

    @pytest.mark.asyncio
    async def test_update_existing(self, persistence, sample_state):
        """Test updating existing conversation."""
        await persistence.save(sample_state)

        # Update state
        sample_state.turns.append(
            ConversationTurn(
                turn_id="turn_2",
                turn_number=1,
                user_input="World",
                timestamp=datetime.now(tz=timezone.utc),
            )
        )
        await persistence.save(sample_state)

        loaded = await persistence.load("conv_123")
        assert len(loaded.turns) == 2  # nosec B101
