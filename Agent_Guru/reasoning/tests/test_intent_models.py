"""Comprehensive unit tests for intent models - 100% coverage."""

import pytest
from datetime import datetime

from Agent_Guru.reasoning.models.intent import Intent, IntentType, Entity


class TestEntity:
    """Test Entity model."""
    
    def test_entity_creation_valid(self):
        """Test creating a valid entity."""
        entity = Entity(
            entity_type="duration",
            value=300,
            raw_text="5 minutes",
            confidence=0.95,
            start_pos=10,
            end_pos=19,
            normalized_value=300,
        )
        assert entity.entity_type == "duration"
        assert entity.value == 300
        assert entity.raw_text == "5 minutes"
        assert entity.confidence == 0.95
        assert entity.start_pos == 10
        assert entity.end_pos == 19
        assert entity.normalized_value == 300
    
    def test_entity_confidence_validation_invalid(self):
        """Test entity confidence validation fails for invalid values."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Entity(
                entity_type="duration",
                value=300,
                raw_text="5 minutes",
                confidence=1.5,
            )
    
    def test_entity_position_validation_invalid(self):
        """Test entity position validation fails when start >= end."""
        with pytest.raises(ValueError, match="start_pos must be less than end_pos"):
            Entity(
                entity_type="duration",
                value=300,
                raw_text="5 minutes",
                start_pos=20,
                end_pos=10,
            )
    
    def test_entity_equality(self):
        """Test entity equality comparison."""
        entity1 = Entity(entity_type="person", value="John", raw_text="John")
        entity2 = Entity(entity_type="person", value="John", raw_text="John")
        entity3 = Entity(entity_type="person", value="Jane", raw_text="Jane")
        
        assert entity1 == entity2
        assert entity1 != entity3
        assert entity1 != "not an entity"
    
    def test_entity_hash(self):
        """Test entity hashing."""
        entity1 = Entity(entity_type="person", value="John", raw_text="John")
        entity2 = Entity(entity_type="person", value="John", raw_text="John")
        
        assert hash(entity1) == hash(entity2)
        assert len({entity1, entity2}) == 1


class TestIntent:
    """Test Intent model."""
    
    def test_intent_creation_valid(self):
        """Test creating a valid intent."""
        entity = Entity(entity_type="duration", value=300, raw_text="5 minutes")
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": entity},
            confidence=0.98,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes",
            detection_method="neural",
        )
        
        assert intent.intent_type == IntentType.SET_TIMER
        assert "duration" in intent.entities
        assert intent.confidence == 0.98
        assert not intent.requires_reasoning
        assert intent.original_input == "set a timer for 5 minutes"
        assert intent.detection_method == "neural"
    
    def test_intent_confidence_validation_invalid(self):
        """Test intent confidence validation fails for invalid values."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Intent(
                intent_type=IntentType.SET_TIMER,
                entities={},
                confidence=2.0,
                original_input="test",
            )
    
    def test_intent_alternative_intents_validation_invalid(self):
        """Test alternative intents validation fails for invalid confidence."""
        with pytest.raises(ValueError, match="Alternative intent confidence must be between"):
            Intent(
                intent_type=IntentType.SET_TIMER,
                entities={},
                confidence=0.9,
                original_input="test",
                alternative_intents=[(IntentType.SET_ALARM, 1.5)],
            )
    
    def test_intent_detection_method_validation_invalid(self):
        """Test detection method validation fails for invalid method."""
        with pytest.raises(ValueError, match="Detection method must be one of"):
            Intent(
                intent_type=IntentType.SET_TIMER,
                entities={},
                confidence=0.9,
                original_input="test",
                detection_method="invalid_method",
            )
    
    def test_intent_get_entity_exists(self):
        """Test getting an existing entity."""
        entity = Entity(entity_type="duration", value=300, raw_text="5 minutes")
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": entity},
            confidence=0.98,
            original_input="test",
        )
        
        assert intent.get_entity("duration") == 300
    
    def test_intent_get_entity_not_exists(self):
        """Test getting a non-existing entity returns default."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={},
            confidence=0.98,
            original_input="test",
        )
        
        assert intent.get_entity("duration") is None
        assert intent.get_entity("duration", default=0) == 0
    
    def test_intent_has_entity(self):
        """Test checking if entity exists."""
        entity = Entity(entity_type="duration", value=300, raw_text="5 minutes")
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": entity},
            confidence=0.98,
            original_input="test",
        )
        
        assert intent.has_entity("duration")
        assert not intent.has_entity("location")
    
    def test_intent_is_ambiguous_low_confidence(self):
        """Test intent is ambiguous with low confidence."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={},
            confidence=0.7,
            original_input="test",
        )
        
        assert intent.is_ambiguous(threshold=0.8)
    
    def test_intent_is_ambiguous_close_alternatives(self):
        """Test intent is ambiguous with close alternative confidence."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={},
            confidence=0.85,
            original_input="test",
            alternative_intents=[(IntentType.SET_ALARM, 0.82)],
        )
        
        assert intent.is_ambiguous(threshold=0.8)
    
    def test_intent_is_not_ambiguous(self):
        """Test intent is not ambiguous."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={},
            confidence=0.95,
            original_input="test",
            alternative_intents=[(IntentType.SET_ALARM, 0.15)],
        )
        
        assert not intent.is_ambiguous(threshold=0.8)
    
    def test_intent_equality(self):
        """Test intent equality comparison."""
        entity = Entity(entity_type="duration", value=300, raw_text="5 minutes")
        intent1 = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": entity},
            confidence=0.98,
            original_input="set timer",
        )
        intent2 = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": entity},
            confidence=0.98,
            original_input="set timer",
        )
        intent3 = Intent(
            intent_type=IntentType.SET_ALARM,
            entities={},
            confidence=0.98,
            original_input="set alarm",
        )
        
        assert intent1 == intent2
        assert intent1 != intent3
        assert intent1 != "not an intent"
    
    def test_intent_hash(self):
        """Test intent hashing."""
        entity = Entity(entity_type="duration", value=300, raw_text="5 minutes")
        intent1 = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": entity},
            confidence=0.98,
            original_input="set timer",
        )
        intent2 = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={"duration": entity},
            confidence=0.98,
            original_input="set timer",
        )
        
        assert hash(intent1) == hash(intent2)
    
    def test_intent_all_intent_types(self):
        """Test all intent types are accessible."""
        assert IntentType.SET_TIMER == "set_timer"
        assert IntentType.QUERY_WEATHER == "query_weather"
        assert IntentType.SEND_MESSAGE == "send_message"
        assert IntentType.UNKNOWN == "unknown"


    def test_entity_validate_confidence_valid(self):
        """Test confidence validation passes for valid value."""
        entity = Entity(
            entity_type="duration",
            value=300,
            raw_text="5 minutes",
            confidence=0.95,
        )
        assert entity.confidence == 0.95
    
    def test_intent_validate_confidence_valid(self):
        """Test confidence validation passes for valid value."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={},
            confidence=0.95,
            original_input="test",
        )
        assert intent.confidence == 0.95
