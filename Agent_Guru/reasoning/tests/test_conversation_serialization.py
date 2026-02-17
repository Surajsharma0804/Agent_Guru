"""Property-based tests for conversation state serialization.

**Property 7: Conversation state round-trip**
**Validates: Requirements 3.5**
"""

from typing import Any, Dict

import pytest
from hypothesis import given, strategies as st, settings, assume

from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
    TrackedEntity,
)
from Agent_Guru.reasoning.models.intent import Intent, IntentType, Entity
from Agent_Guru.reasoning.models.action import Action


# Hypothesis strategies for generating test data
@st.composite
def entity_strategy(draw):
    """Generate random Entity instances with valid constraints."""
    # Generate positions ensuring start < end if both exist
    has_positions = draw(st.booleans())
    if has_positions:
        start_pos = draw(st.integers(min_value=0, max_value=100))
        end_pos = draw(st.integers(min_value=start_pos + 1, max_value=150))
    else:
        start_pos = None
        end_pos = None
    
    return Entity(
        entity_type=draw(st.sampled_from(["person", "location", "time", "duration", "quantity"])),
        value=draw(st.one_of(
            st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
            st.integers(min_value=-1000000, max_value=1000000),
            st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
        )),
        raw_text=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=('Cs',)))),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        start_pos=start_pos,
        end_pos=end_pos,
    )


@st.composite
def intent_strategy(draw):
    """Generate random Intent instances with valid constraints."""
    intent_type = draw(st.sampled_from(list(IntentType)))
    entities_dict = draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
        values=entity_strategy(),
        max_size=3,
    ))
    
    return Intent(
        intent_type=intent_type,
        entities=entities_dict,
        confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        requires_reasoning=draw(st.booleans()),
        original_input=draw(st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=('Cs',))).filter(lambda x: x.strip())),
        detection_method=draw(st.sampled_from(["rule", "neural", "llm", "hybrid"])),
    )


@st.composite
def action_strategy(draw):
    """Generate random Action instances with valid constraints."""
    return Action(
        action_id=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)).filter(lambda x: x.strip())),
        tool_id=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)).filter(lambda x: x.strip())),
        parameters=draw(st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
            values=st.one_of(
                st.text(max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
                st.integers(min_value=-1000000, max_value=1000000),
                st.floats(min_value=-1000000.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
                st.booleans()
            ),
            max_size=5,
        )),
        is_sensitive=draw(st.booleans()),
        estimated_duration=draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)),
        requires_confirmation=draw(st.booleans()),
    )


@st.composite
def tracked_entity_strategy(draw):
    """Generate random TrackedEntity instances with valid constraints."""
    first_mentioned = draw(st.integers(min_value=0, max_value=50))
    last_mentioned = draw(st.integers(min_value=first_mentioned, max_value=100))
    
    return TrackedEntity(
        entity_type=draw(st.sampled_from(["person", "location", "time", "duration"])),
        value=draw(st.one_of(
            st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
            st.integers(min_value=-1000000, max_value=1000000)
        )),
        first_mentioned=first_mentioned,
        last_mentioned=last_mentioned,
        mention_count=draw(st.integers(min_value=1, max_value=50)),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
    )


@st.composite
def conversation_turn_strategy(draw):
    """Generate random ConversationTurn instances with valid constraints."""
    return ConversationTurn(
        turn_id=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)).filter(lambda x: x.strip())),
        turn_number=draw(st.integers(min_value=0, max_value=100)),
        user_input=draw(st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=('Cs',))).filter(lambda x: x.strip())),
        intent=draw(st.one_of(st.none(), intent_strategy())),
        action_taken=draw(st.one_of(st.none(), action_strategy())),
        response=draw(st.text(max_size=500, alphabet=st.characters(blacklist_categories=('Cs',)))),
        user_feedback=draw(st.one_of(st.none(), st.sampled_from(["helpful", "not_helpful"]))),
        execution_time=draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)),
    )


@st.composite
def conversation_state_strategy(draw):
    """Generate random ConversationState instances with valid constraints."""
    # Generate turns with sequential turn numbers
    num_turns = draw(st.integers(min_value=0, max_value=10))
    turns = []
    for i in range(num_turns):
        turn = draw(conversation_turn_strategy())
        turn.turn_number = i
        turns.append(turn)
    
    entities_dict = draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
        values=tracked_entity_strategy(),
        max_size=5,
    ))
    
    return ConversationState(
        conversation_id=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)).filter(lambda x: x.strip())),
        user_id=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)).filter(lambda x: x.strip())),
        turns=turns,
        entities=entities_dict,
        user_preferences=draw(st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
            values=st.one_of(
                st.text(max_size=50, alphabet=st.characters(blacklist_categories=('Cs',))),
                st.integers(min_value=-1000000, max_value=1000000),
                st.booleans()
            ),
            max_size=3,
        )),
        context_summary=draw(st.one_of(st.none(), st.text(max_size=500, alphabet=st.characters(blacklist_categories=('Cs',))))),
        last_intent=draw(st.one_of(st.none(), intent_strategy())),
        active_tasks=draw(st.lists(st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)), max_size=3)),
    )


@pytest.mark.property
@given(state=conversation_state_strategy())
@settings(max_examples=100, deadline=None)
def test_conversation_state_json_round_trip(state: ConversationState):
    """
    Test that ConversationState can be serialized to JSON and deserialized back.
    
    **Property 7: Conversation state round-trip**
    **Validates: Requirements 3.5**
    
    For any valid ConversationState, serializing to JSON and deserializing
    should produce an equivalent object with all fields preserved.
    """
    # Serialize to JSON
    json_str = state.model_dump_json()
    
    # Deserialize from JSON
    deserialized = ConversationState.model_validate_json(json_str)
    
    # Verify all required fields are preserved
    assert deserialized.conversation_id == state.conversation_id
    assert deserialized.user_id == state.user_id
    assert len(deserialized.turns) == len(state.turns)
    assert len(deserialized.entities) == len(state.entities)
    assert deserialized.user_preferences == state.user_preferences
    assert deserialized.context_summary == state.context_summary
    assert len(deserialized.active_tasks) == len(state.active_tasks)
    
    # Verify turns are preserved
    for orig_turn, deser_turn in zip(state.turns, deserialized.turns):
        assert deser_turn.turn_id == orig_turn.turn_id
        assert deser_turn.turn_number == orig_turn.turn_number
        assert deser_turn.user_input == orig_turn.user_input
        assert deser_turn.response == orig_turn.response
    
    # Verify entities are preserved
    for key in state.entities:
        assert key in deserialized.entities
        assert deserialized.entities[key].entity_type == state.entities[key].entity_type
        assert deserialized.entities[key].value == state.entities[key].value


@pytest.mark.property
@given(state=conversation_state_strategy())
@settings(max_examples=100, deadline=None)
def test_conversation_state_dict_round_trip(state: ConversationState):
    """
    Test that ConversationState can be converted to dict and back.
    
    **Property 7: Conversation state round-trip**
    **Validates: Requirements 3.5**
    
    For any valid ConversationState, converting to dict and back
    should produce an equivalent object.
    """
    # Convert to dict
    state_dict = state.model_dump()
    
    # Convert back from dict
    deserialized = ConversationState.model_validate(state_dict)
    
    # Verify core fields
    assert deserialized.conversation_id == state.conversation_id
    assert deserialized.user_id == state.user_id
    assert len(deserialized.turns) == len(state.turns)
    assert len(deserialized.entities) == len(state.entities)


@pytest.mark.property
@given(state=conversation_state_strategy())
@settings(max_examples=100, deadline=None)
def test_conversation_state_timestamps_preserved(state: ConversationState):
    """
    Test that timestamps are correctly serialized and deserialized.
    
    **Property 7: Conversation state round-trip**
    **Validates: Requirements 3.5**
    
    Timestamps should be preserved through serialization round-trip.
    """
    # Serialize and deserialize
    json_str = state.model_dump_json()
    deserialized = ConversationState.model_validate_json(json_str)
    
    # Verify timestamps are preserved (within reasonable tolerance)
    created_diff = abs((deserialized.created_at - state.created_at).total_seconds())
    updated_diff = abs((deserialized.updated_at - state.updated_at).total_seconds())
    
    assert created_diff < 1.0, "created_at timestamp not preserved"
    assert updated_diff < 1.0, "updated_at timestamp not preserved"
    
    # Verify turn timestamps
    for orig_turn, deser_turn in zip(state.turns, deserialized.turns):
        turn_diff = abs((deser_turn.timestamp - orig_turn.timestamp).total_seconds())
        assert turn_diff < 1.0, f"Turn {orig_turn.turn_id} timestamp not preserved"


@pytest.mark.property
@given(state=conversation_state_strategy())
@settings(max_examples=100, deadline=None)
def test_conversation_state_nested_objects_preserved(state: ConversationState):
    """
    Test that nested objects (intents, actions, entities) are preserved.
    
    **Property 7: Conversation state round-trip**
    **Validates: Requirements 3.5**
    
    All nested objects should be preserved including their fields.
    """
    # Serialize and deserialize
    json_str = state.model_dump_json()
    deserialized = ConversationState.model_validate_json(json_str)
    
    # Check nested intents in turns
    for orig_turn, deser_turn in zip(state.turns, deserialized.turns):
        if orig_turn.intent is not None:
            assert deser_turn.intent is not None
            assert deser_turn.intent.intent_type == orig_turn.intent.intent_type
            assert deser_turn.intent.confidence == orig_turn.intent.confidence
            assert deser_turn.intent.original_input == orig_turn.intent.original_input
        
        if orig_turn.action_taken is not None:
            assert deser_turn.action_taken is not None
            assert deser_turn.action_taken.action_id == orig_turn.action_taken.action_id
            assert deser_turn.action_taken.tool_id == orig_turn.action_taken.tool_id
    
    # Check last_intent
    if state.last_intent is not None:
        assert deserialized.last_intent is not None
        assert deserialized.last_intent.intent_type == state.last_intent.intent_type


@pytest.mark.property
@given(
    state=conversation_state_strategy(),
    extra_data=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.text(), st.integers(), st.booleans()),
        max_size=5,
    ),
)
@settings(max_examples=100, deadline=None)
def test_conversation_state_metadata_preserved(state: ConversationState, extra_data: Dict[str, Any]):
    """
    Test that metadata fields are preserved through serialization.
    
    **Property 7: Conversation state round-trip**
    **Validates: Requirements 3.5**
    
    Metadata dictionaries should be preserved exactly.
    """
    # Add metadata
    state.metadata = extra_data
    
    # Serialize and deserialize
    json_str = state.model_dump_json()
    deserialized = ConversationState.model_validate_json(json_str)
    
    # Verify metadata is preserved
    assert deserialized.metadata == state.metadata
