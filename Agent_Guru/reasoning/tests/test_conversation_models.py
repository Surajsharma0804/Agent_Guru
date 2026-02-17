"""Comprehensive unit tests for conversation models - 100% coverage."""

import pytest
from datetime import datetime

from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
    TrackedEntity,
)
from Agent_Guru.reasoning.models.intent import Intent, IntentType, Entity
from Agent_Guru.reasoning.models.action import Action


class TestTrackedEntity:
    """Test TrackedEntity model."""
    
    def test_tracked_entity_creation_valid(self):
        """Test creating a valid tracked entity."""
        entity = TrackedEntity(
            entity_type="location",
            value="New York",
            first_mentioned=0,
            last_mentioned=2,
            mention_count=3,
            confidence=0.95,
        )
        
        assert entity.entity_type == "location"
        assert entity.value == "New York"
        assert entity.first_mentioned == 0
        assert entity.last_mentioned == 2
        assert entity.mention_count == 3
        assert entity.confidence == 0.95
    
    def test_tracked_entity_confidence_validation_invalid(self):
        """Test confidence validation fails for invalid values."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TrackedEntity(
                entity_type="location",
                value="New York",
                first_mentioned=0,
                last_mentioned=0,
                confidence=1.5,
            )
    
    def test_tracked_entity_mentions_validation_invalid(self):
        """Test mentions validation fails when last < first."""
        with pytest.raises(ValueError, match="last_mentioned cannot be before first_mentioned"):
            TrackedEntity(
                entity_type="location",
                value="New York",
                first_mentioned=5,
                last_mentioned=2,
            )
    
    def test_tracked_entity_equality(self):
        """Test tracked entity equality comparison."""
        entity1 = TrackedEntity(
            entity_type="location",
            value="New York",
            first_mentioned=0,
            last_mentioned=0,
        )
        entity2 = TrackedEntity(
            entity_type="location",
            value="New York",
            first_mentioned=0,
            last_mentioned=0,
        )
        entity3 = TrackedEntity(
            entity_type="location",
            value="Boston",
            first_mentioned=0,
            last_mentioned=0,
        )
        
        assert entity1 == entity2
        assert entity1 != entity3
        assert entity1 != "not an entity"
    
    def test_tracked_entity_hash(self):
        """Test tracked entity hashing."""
        entity1 = TrackedEntity(
            entity_type="location",
            value="New York",
            first_mentioned=0,
            last_mentioned=0,
        )
        entity2 = TrackedEntity(
            entity_type="location",
            value="New York",
            first_mentioned=0,
            last_mentioned=0,
        )
        
        assert hash(entity1) == hash(entity2)


class TestConversationTurn:
    """Test ConversationTurn model."""
    
    def test_conversation_turn_creation_valid(self):
        """Test creating a valid conversation turn."""
        turn = ConversationTurn(
            turn_id="turn_123",
            turn_number=0,
            user_input="set a timer for 5 minutes",
            response="Timer set for 5 minutes",
            execution_time=0.234,
            user_feedback="helpful",
        )
        
        assert turn.turn_id == "turn_123"
        assert turn.turn_number == 0
        assert turn.user_input == "set a timer for 5 minutes"
        assert turn.response == "Timer set for 5 minutes"
        assert turn.execution_time == 0.234
        assert turn.user_feedback == "helpful"
    
    def test_conversation_turn_id_validation_invalid_empty(self):
        """Test turn ID validation fails for empty ID."""
        with pytest.raises(ValueError, match="Turn ID cannot be empty"):
            ConversationTurn(
                turn_id="",
                turn_number=0,
                user_input="test",
            )
    
    def test_conversation_turn_id_validation_invalid_whitespace(self):
        """Test turn ID validation fails for whitespace-only ID."""
        with pytest.raises(ValueError, match="Turn ID cannot be empty"):
            ConversationTurn(
                turn_id="   ",
                turn_number=0,
                user_input="test",
            )
    
    def test_conversation_turn_number_validation_invalid(self):
        """Test turn number validation fails for negative value."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ConversationTurn(
                turn_id="turn_123",
                turn_number=-1,
                user_input="test",
            )
    
    def test_conversation_turn_user_input_validation_invalid_empty(self):
        """Test user input validation fails for empty input."""
        with pytest.raises(ValueError, match="User input cannot be empty"):
            ConversationTurn(
                turn_id="turn_123",
                turn_number=0,
                user_input="",
            )
    
    def test_conversation_turn_user_input_validation_invalid_whitespace(self):
        """Test user input validation fails for whitespace-only input."""
        with pytest.raises(ValueError, match="User input cannot be empty"):
            ConversationTurn(
                turn_id="turn_123",
                turn_number=0,
                user_input="   ",
            )
    
    def test_conversation_turn_execution_time_validation_invalid(self):
        """Test execution time validation fails for negative value."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ConversationTurn(
                turn_id="turn_123",
                turn_number=0,
                user_input="test",
                execution_time=-1.0,
            )
    
    def test_conversation_turn_equality(self):
        """Test conversation turn equality comparison."""
        turn1 = ConversationTurn(turn_id="turn_123", turn_number=0, user_input="test")
        turn2 = ConversationTurn(turn_id="turn_123", turn_number=0, user_input="test")
        turn3 = ConversationTurn(turn_id="turn_456", turn_number=0, user_input="test")
        
        assert turn1 == turn2
        assert turn1 != turn3
        assert turn1 != "not a turn"
    
    def test_conversation_turn_hash(self):
        """Test conversation turn hashing."""
        turn1 = ConversationTurn(turn_id="turn_123", turn_number=0, user_input="test")
        turn2 = ConversationTurn(turn_id="turn_123", turn_number=0, user_input="test")
        
        assert hash(turn1) == hash(turn2)


class TestConversationState:
    """Test ConversationState model."""
    
    def test_conversation_state_creation_valid(self):
        """Test creating a valid conversation state."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
            user_preferences={"voice_speed": "normal"},
        )
        
        assert state.conversation_id == "conv_123"
        assert state.user_id == "user_456"
        assert state.user_preferences == {"voice_speed": "normal"}
        assert len(state.turns) == 0
        assert len(state.entities) == 0
    
    def test_conversation_id_validation_invalid_empty(self):
        """Test conversation ID validation fails for empty ID."""
        with pytest.raises(ValueError, match="Conversation ID cannot be empty"):
            ConversationState(
                conversation_id="",
                user_id="user_456",
            )
    
    def test_conversation_id_validation_invalid_whitespace(self):
        """Test conversation ID validation fails for whitespace-only ID."""
        with pytest.raises(ValueError, match="Conversation ID cannot be empty"):
            ConversationState(
                conversation_id="   ",
                user_id="user_456",
            )
    
    def test_user_id_validation_invalid_empty(self):
        """Test user ID validation fails for empty ID."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            ConversationState(
                conversation_id="conv_123",
                user_id="",
            )
    
    def test_user_id_validation_invalid_whitespace(self):
        """Test user ID validation fails for whitespace-only ID."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            ConversationState(
                conversation_id="conv_123",
                user_id="   ",
            )
    
    def test_turns_validation_invalid_order(self):
        """Test turns validation fails for non-chronological order."""
        turn1 = ConversationTurn(turn_id="turn_1", turn_number=1, user_input="test")
        turn2 = ConversationTurn(turn_id="turn_2", turn_number=0, user_input="test")
        
        with pytest.raises(ValueError, match="Turns must be in chronological order"):
            ConversationState(
                conversation_id="conv_123",
                user_id="user_456",
                turns=[turn1, turn2],
            )
    
    def test_add_turn(self):
        """Test adding a turn to conversation."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={},
            confidence=0.9,
            original_input="test",
        )
        turn = ConversationTurn(
            turn_id="turn_1",
            turn_number=0,
            user_input="test",
            intent=intent,
        )
        
        state.add_turn(turn)
        
        assert len(state.turns) == 1
        assert state.turns[0] == turn
        assert state.last_intent == intent
    
    def test_get_recent_turns_less_than_count(self):
        """Test getting recent turns when total is less than count."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        turn1 = ConversationTurn(turn_id="turn_1", turn_number=0, user_input="test1")
        turn2 = ConversationTurn(turn_id="turn_2", turn_number=1, user_input="test2")
        state.turns = [turn1, turn2]
        
        recent = state.get_recent_turns(count=5)
        assert len(recent) == 2
    
    def test_get_recent_turns_more_than_count(self):
        """Test getting recent turns when total is more than count."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        turns = [
            ConversationTurn(turn_id=f"turn_{i}", turn_number=i, user_input=f"test{i}")
            for i in range(10)
        ]
        state.turns = turns
        
        recent = state.get_recent_turns(count=3)
        assert len(recent) == 3
        assert recent[0].turn_number == 7
        assert recent[2].turn_number == 9
    
    def test_get_turn_count(self):
        """Test getting turn count."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        turn1 = ConversationTurn(turn_id="turn_1", turn_number=0, user_input="test1")
        turn2 = ConversationTurn(turn_id="turn_2", turn_number=1, user_input="test2")
        state.turns = [turn1, turn2]
        
        assert state.get_turn_count() == 2
    
    def test_track_entity_new(self):
        """Test tracking a new entity."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        state.track_entity("location", "New York", turn_number=0, confidence=0.95)
        
        assert "location:New York" in state.entities
        entity = state.entities["location:New York"]
        assert entity.entity_type == "location"
        assert entity.value == "New York"
        assert entity.first_mentioned == 0
        assert entity.last_mentioned == 0
        assert entity.mention_count == 1
    
    def test_track_entity_existing(self):
        """Test tracking an existing entity updates it."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        state.track_entity("location", "New York", turn_number=0, confidence=0.9)
        state.track_entity("location", "New York", turn_number=2, confidence=0.95)
        
        entity = state.entities["location:New York"]
        assert entity.first_mentioned == 0
        assert entity.last_mentioned == 2
        assert entity.mention_count == 2
        assert entity.confidence == 0.95
    
    def test_get_entity_exists(self):
        """Test getting an existing entity."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        state.track_entity("location", "New York", turn_number=0)
        
        entity = state.get_entity("location")
        assert entity is not None
        assert entity.value == "New York"
    
    def test_get_entity_not_exists(self):
        """Test getting a non-existing entity returns None."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        entity = state.get_entity("location")
        assert entity is None
    
    def test_get_entity_most_recent(self):
        """Test getting entity returns most recently mentioned."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        state.track_entity("location", "New York", turn_number=0)
        state.track_entity("location", "Boston", turn_number=2)
        
        entity = state.get_entity("location")
        assert entity.value == "Boston"
    
    def test_prune_old_turns_no_pruning_needed(self):
        """Test pruning when no pruning is needed."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        turns = [
            ConversationTurn(turn_id=f"turn_{i}", turn_number=i, user_input=f"test{i}")
            for i in range(5)
        ]
        state.turns = turns
        
        pruned = state.prune_old_turns(max_turns=10)
        assert pruned == 0
        assert len(state.turns) == 5
    
    def test_prune_old_turns_pruning_needed(self):
        """Test pruning when pruning is needed."""
        state = ConversationState(
            conversation_id="conv_123",
            user_id="user_456",
        )
        
        turns = [
            ConversationTurn(turn_id=f"turn_{i}", turn_number=i, user_input=f"test{i}")
            for i in range(25)
        ]
        state.turns = turns
        
        pruned = state.prune_old_turns(max_turns=20)
        assert pruned == 5
        assert len(state.turns) == 20
        assert state.turns[0].turn_number == 5
        assert state.turns[-1].turn_number == 24
    
    def test_conversation_state_equality(self):
        """Test conversation state equality comparison."""
        state1 = ConversationState(conversation_id="conv_123", user_id="user_456")
        state2 = ConversationState(conversation_id="conv_123", user_id="user_456")
        state3 = ConversationState(conversation_id="conv_789", user_id="user_456")
        
        assert state1 == state2
        assert state1 != state3
        assert state1 != "not a state"
    
    def test_conversation_state_hash(self):
        """Test conversation state hashing."""
        state1 = ConversationState(conversation_id="conv_123", user_id="user_456")
        state2 = ConversationState(conversation_id="conv_123", user_id="user_456")
        
        assert hash(state1) == hash(state2)


    def test_tracked_entity_validate_confidence_valid(self):
        """Test confidence validation passes for valid value."""
        entity = TrackedEntity(
            entity_type="location",
            value="New York",
            first_mentioned=0,
            last_mentioned=0,
            confidence=0.95,
        )
        assert entity.confidence == 0.95
    
    def test_conversation_turn_validate_turn_number_valid(self):
        """Test turn number validation passes for valid positive value."""
        turn = ConversationTurn(
            turn_id="turn_123",
            turn_number=5,
            user_input="test",
        )
        assert turn.turn_number == 5
    
    def test_conversation_turn_validate_execution_time_valid(self):
        """Test execution time validation passes for valid positive value."""
        turn = ConversationTurn(
            turn_id="turn_123",
            turn_number=0,
            user_input="test",
            execution_time=0.5,
        )
        assert turn.execution_time == 0.5
