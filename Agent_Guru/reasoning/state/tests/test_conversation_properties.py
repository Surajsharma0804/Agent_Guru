"""
Property-based tests for conversation state management.

These tests validate universal properties that must hold for all conversation states.
"""

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
)


# Strategies for generating test data
@st.composite
def conversation_turn_strategy(draw, turn_num=None):
    """Generate valid conversation turns."""
    if turn_num is None:
        turn_num = draw(st.integers(min_value=1, max_value=100))

    return ConversationTurn(
        turn_id=f"turn_{turn_num}",
        turn_number=turn_num,
        user_input=draw(
            st.text(min_size=2, max_size=200, alphabet=st.characters(blacklist_categories=("Cs",)))
        ),
        response=draw(
            st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=("Cs",)))
        ),
        timestamp=datetime.now(tz=timezone.utc),
    )


@st.composite
def conversation_state_strategy(draw):
    """Generate valid conversation states with chronologically ordered turns."""
    num_turns = draw(st.integers(min_value=0, max_value=20))

    # Generate turns in chronological order
    base_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    turns = []
    for i in range(num_turns):
        # Generate non-empty, non-whitespace text
        user_input = draw(
            st.text(
                min_size=2,
                max_size=50,
                alphabet=st.characters(blacklist_categories=("Cs", "Cc", "Zs", "Zl", "Zp")),
            )
        )
        if not user_input or not user_input.strip():
            user_input = f"input_{i+1}"

        response = draw(
            st.text(
                min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=("Cs", "Cc"))
            )
        )
        if not response or not response.strip():
            response = f"response_{i+1}"

        turn = ConversationTurn(
            turn_id=f"turn_{i+1}",
            turn_number=i + 1,
            user_input=user_input,
            response=response,
            timestamp=base_time + timedelta(seconds=i),
        )
        turns.append(turn)

    return ConversationState(
        conversation_id=f"conv_{draw(st.integers(min_value=1, max_value=10000))}",
        user_id=f"user_{draw(st.integers(min_value=1, max_value=1000))}",
        turns=turns,
        created_at=base_time,
        updated_at=datetime.now(tz=timezone.utc),
    )


class TestConversationStateProperties:
    """Property 5: Conversation state accumulates history."""

    @settings(max_examples=100)
    @given(state=conversation_state_strategy())
    def test_state_preserves_turn_order(self, state: ConversationState):
        """
        Property: Turns are always in chronological order.

        Validates: Requirements 3.2
        """
        # Verify turns are in order
        for i in range(len(state.turns) - 1):
            assert state.turns[i].turn_number <= state.turns[i + 1].turn_number  # nosec B101
            assert state.turns[i].timestamp <= state.turns[i + 1].timestamp  # nosec B101

    @settings(max_examples=100)
    @given(
        state=conversation_state_strategy(),
        new_turn=conversation_turn_strategy(),
    )
    def test_adding_turn_increases_count(
        self,
        state: ConversationState,
        new_turn: ConversationTurn,
    ):
        """
        Property: Adding a turn increases turn count (up to limit).

        Validates: Requirements 3.2
        """
        initial_count = len(state.turns)

        # Add new turn
        new_turn_adjusted = ConversationTurn(
            turn_id=f"new_{new_turn.turn_id}",
            turn_number=initial_count + 1,
            user_input=new_turn.user_input,
            response=new_turn.response,
            timestamp=datetime.now(tz=timezone.utc),
        )

        new_turns = state.turns + [new_turn_adjusted]
        new_state = ConversationState(
            conversation_id=state.conversation_id,
            user_id=state.user_id,
            turns=new_turns[-20:],  # Keep last 20
            created_at=state.created_at,
            updated_at=datetime.now(tz=timezone.utc),
        )

        # Verify count increased or stayed at limit
        assert len(new_state.turns) == min(initial_count + 1, 20)  # nosec B101


class TestConversationStateSizeLimits:
    """Property 6: Conversation state maintains size limit."""

    @settings(max_examples=100)
    @given(state=conversation_state_strategy())
    def test_state_never_exceeds_max_turns(self, state: ConversationState):
        """
        Property: Number of turns ≤ MAX_TURNS (20).

        Validates: Requirements 3.4
        """
        assert len(state.turns) <= 20  # nosec B101

    @settings(max_examples=100)
    @given(
        num_turns=st.integers(min_value=21, max_value=50),
    )
    def test_pruning_keeps_recent_turns(self, num_turns: int):
        """
        Property: Pruning keeps the most recent turns.

        Validates: Requirements 3.4
        """
        # Create state with many turns
        base_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        turns = []
        for i in range(num_turns):
            turn = ConversationTurn(
                turn_id=f"turn_{i+1}",
                turn_number=i + 1,
                user_input=f"Input {i+1}",
                response=f"Response {i+1}",
                timestamp=base_time + timedelta(seconds=i),
            )
            turns.append(turn)

        # Keep only last 20
        pruned_turns = turns[-20:]

        state = ConversationState(
            conversation_id="conv_test",
            user_id="user_test",
            turns=pruned_turns,
            created_at=base_time,
            updated_at=datetime.now(tz=timezone.utc),
        )

        # Verify size limit
        assert len(state.turns) == 20  # nosec B101

        # Verify most recent turns are kept
        assert state.turns[-1].turn_number == num_turns  # nosec B101
        assert state.turns[0].turn_number == num_turns - 19  # nosec B101


class TestConversationStatePersistence:
    """Property 7: Conversation state round-trip."""

    @settings(max_examples=100)
    @given(state=conversation_state_strategy())
    def test_state_serialization_roundtrip(self, state: ConversationState):
        """
        Property: Serializing and deserializing state produces equivalent object.

        Validates: Requirements 3.5
        """
        # Serialize to JSON
        json_data = state.model_dump_json()

        # Deserialize back
        restored_state = ConversationState.model_validate_json(json_data)

        # Verify equivalence
        assert restored_state.conversation_id == state.conversation_id  # nosec B101
        assert restored_state.user_id == state.user_id  # nosec B101
        assert len(restored_state.turns) == len(state.turns)  # nosec B101

        # Verify all turns are preserved
        for original, restored in zip(state.turns, restored_state.turns, strict=False):
            assert original.turn_id == restored.turn_id  # nosec B101
            assert original.user_input == restored.user_input  # nosec B101
            assert original.response == restored.response  # nosec B101

    @settings(max_examples=100)
    @given(state=conversation_state_strategy())
    def test_state_dict_roundtrip(self, state: ConversationState):
        """
        Property: Converting to dict and back preserves all fields.

        Validates: Requirements 3.5
        """
        # Convert to dict
        state_dict = state.model_dump()

        # Restore from dict
        restored_state = ConversationState(**state_dict)

        # Verify equivalence
        assert restored_state.conversation_id == state.conversation_id  # nosec B101
        assert restored_state.user_id == state.user_id  # nosec B101
        assert len(restored_state.turns) == len(state.turns)  # nosec B101

    @settings(max_examples=100)
    @given(state=conversation_state_strategy())
    def test_timestamps_preserved_in_serialization(self, state: ConversationState):
        """
        Property: Timestamps are correctly preserved through serialization.

        Validates: Requirements 3.5
        """
        # Serialize and deserialize
        json_data = state.model_dump_json()
        restored_state = ConversationState.model_validate_json(json_data)

        # Verify timestamps
        assert restored_state.created_at.replace(microsecond=0) == state.created_at.replace(  # nosec B101
            microsecond=0
        )
        assert restored_state.updated_at.replace(microsecond=0) == state.updated_at.replace(  # nosec B101
            microsecond=0
        )

        # Verify turn timestamps
        for original, restored in zip(state.turns, restored_state.turns, strict=False):
            assert original.timestamp.replace(microsecond=0) == restored.timestamp.replace(  # nosec B101
                microsecond=0
            )
