"""Intent detection data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator


class IntentType(str, Enum):
    """Enumeration of common intent types."""
    
    # Time & Scheduling
    SET_TIMER = "set_timer"
    SET_ALARM = "set_alarm"
    SET_REMINDER = "set_reminder"
    CANCEL_TIMER = "cancel_timer"
    
    # Information Queries
    QUERY_WEATHER = "query_weather"
    QUERY_TIME = "query_time"
    QUERY_DATE = "query_date"
    QUERY_FACT = "query_fact"
    SEARCH_WEB = "search_web"
    
    # Communication
    SEND_MESSAGE = "send_message"
    SEND_EMAIL = "send_email"
    MAKE_CALL = "make_call"
    
    # Media & Entertainment
    PLAY_MUSIC = "play_music"
    PLAY_VIDEO = "play_video"
    PAUSE_MEDIA = "pause_media"
    STOP_MEDIA = "stop_media"
    NEXT_TRACK = "next_track"
    PREVIOUS_TRACK = "previous_track"
    
    # Smart Home
    CONTROL_LIGHTS = "control_lights"
    CONTROL_THERMOSTAT = "control_thermostat"
    CONTROL_DEVICE = "control_device"
    
    # Calendar & Events
    CREATE_EVENT = "create_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"
    QUERY_EVENTS = "query_events"
    
    # System & Control
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    SYSTEM_COMMAND = "system_command"
    
    # Conversation Management
    CLARIFICATION_REQUEST = "clarification_request"
    CONFIRMATION = "confirmation"
    CANCELLATION = "cancellation"
    HELP_REQUEST = "help_request"
    
    # Special
    UNKNOWN = "unknown"
    MULTI_INTENT = "multi_intent"


class Entity(BaseModel):
    """Represents an extracted entity from user input."""
    
    entity_type: str = Field(..., description="Type of entity (person, location, time, etc.)")
    value: Any = Field(..., description="Extracted entity value")
    raw_text: str = Field(..., description="Original text span")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    start_pos: Optional[int] = Field(default=None, description="Start position in input text")
    end_pos: Optional[int] = Field(default=None, description="End position in input text")
    normalized_value: Optional[Any] = Field(default=None, description="Normalized entity value")
    
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v
    
    @model_validator(mode="after")
    def validate_positions(self) -> "Entity":
        """Validate start and end positions."""
        if self.start_pos is not None and self.end_pos is not None:
            if self.start_pos >= self.end_pos:
                raise ValueError("start_pos must be less than end_pos")
        return self
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on type, value, and text."""
        if not isinstance(other, Entity):
            return False
        return (
            self.entity_type == other.entity_type
            and self.value == other.value
            and self.raw_text == other.raw_text
        )
    
    def __hash__(self) -> int:
        """Generate hash for entity."""
        return hash((self.entity_type, str(self.value), self.raw_text))
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "entity_type": "duration",
                "value": 300,
                "raw_text": "5 minutes",
                "confidence": 0.95,
                "start_pos": 10,
                "end_pos": 19,
                "normalized_value": 300,
            }
        }


class Intent(BaseModel):
    """Represents a detected user intent."""
    
    intent_type: IntentType = Field(..., description="Type of detected intent")
    entities: Dict[str, Entity] = Field(
        default_factory=dict,
        description="Extracted entities keyed by parameter name",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Intent detection confidence")
    requires_reasoning: bool = Field(
        default=False,
        description="Whether this intent requires LLM reasoning",
    )
    original_input: str = Field(..., description="Original user input text")
    alternative_intents: List[Tuple[IntentType, float]] = Field(
        default_factory=list,
        description="Alternative intents with confidence scores",
    )
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when intent was detected",
    )
    detection_method: str = Field(
        default="neural",
        description="Method used for detection (rule, neural, llm)",
    )
    
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v
    
    @field_validator("alternative_intents")
    @classmethod
    def validate_alternatives(cls, v: List[Tuple[IntentType, float]]) -> List[Tuple[IntentType, float]]:
        """Validate alternative intents have valid confidence scores."""
        for intent_type, confidence in v:
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(f"Alternative intent confidence must be between 0.0 and 1.0, got {confidence}")
        return v
    
    @field_validator("detection_method")
    @classmethod
    def validate_detection_method(cls, v: str) -> str:
        """Validate detection method is valid."""
        valid_methods = {"rule", "neural", "llm", "hybrid"}
        if v not in valid_methods:
            raise ValueError(f"Detection method must be one of {valid_methods}, got {v}")
        return v
    
    def get_entity(self, key: str, default: Any = None) -> Any:
        """
        Get entity value by key.
        
        Args:
            key: Entity parameter name
            default: Default value if entity not found
            
        Returns:
            Entity value or default
        """
        entity = self.entities.get(key)
        return entity.value if entity else default
    
    def has_entity(self, key: str) -> bool:
        """
        Check if entity exists.
        
        Args:
            key: Entity parameter name
            
        Returns:
            True if entity exists
        """
        return key in self.entities
    
    def is_ambiguous(self, threshold: float = 0.8) -> bool:
        """
        Check if intent is ambiguous based on confidence and alternatives.
        
        Args:
            threshold: Confidence threshold for ambiguity
            
        Returns:
            True if intent is ambiguous
        """
        if self.confidence < threshold:
            return True
        
        # Check if any alternative is close in confidence
        for _, alt_confidence in self.alternative_intents:
            if abs(self.confidence - alt_confidence) < 0.2:
                return True
        
        return False
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on intent type and entities."""
        if not isinstance(other, Intent):
            return False
        return (
            self.intent_type == other.intent_type
            and self.entities == other.entities
            and self.original_input == other.original_input
        )
    
    def __hash__(self) -> int:
        """Generate hash for intent."""
        entity_hash = hash(tuple(sorted(self.entities.items())))
        return hash((self.intent_type, entity_hash, self.original_input))
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "intent_type": "set_timer",
                "entities": {
                    "duration": {
                        "entity_type": "duration",
                        "value": 300,
                        "raw_text": "5 minutes",
                        "confidence": 0.95,
                    }
                },
                "confidence": 0.98,
                "requires_reasoning": False,
                "original_input": "set a timer for 5 minutes",
                "alternative_intents": [("set_alarm", 0.15)],
                "detection_method": "neural",
            }
        }
