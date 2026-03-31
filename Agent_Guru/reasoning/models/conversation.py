"""Conversation state management data models."""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .action import Action
from .intent import Intent


class TrackedEntity(BaseModel):
    """Represents an entity tracked across conversation turns."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "entity_type": "location",
            "value": "New York",
            "first_mentioned": 0,
            "last_mentioned": 2,
            "mention_count": 3,
            "confidence": 0.95,
        }
    })

    entity_type: str = Field(..., description="Type of entity")
    value: Any = Field(..., description="Entity value")
    first_mentioned: int = Field(..., description="Turn number when first mentioned")
    last_mentioned: int = Field(..., description="Turn number when last mentioned")
    mention_count: int = Field(default=1, description="Number of times mentioned")
    confidence: float = Field(default=1.0, description="Confidence score")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_mentions(self) -> "TrackedEntity":
        """Validate mention tracking is consistent."""
        if self.last_mentioned < self.first_mentioned:
            raise ValueError("last_mentioned cannot be before first_mentioned")
        return self

    def __eq__(self, other: object) -> bool:
        """Check equality based on type and value."""
        if not isinstance(other, TrackedEntity):
            return False
        return (
            self.entity_type == other.entity_type
            and self.value == other.value
        )

    def __hash__(self) -> int:
        """Generate hash for tracked entity."""
        return hash((self.entity_type, str(self.value)))


class ConversationTurn(BaseModel):
    """Represents a single turn in a conversation."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "turn_id": "turn_123",
            "turn_number": 0,
            "user_input": "set a timer for 5 minutes",
            "response": "Timer set for 5 minutes",
            "execution_time": 0.234,
            "user_feedback": "helpful",
        }
    })

    turn_id: str = Field(..., description="Unique turn identifier")
    turn_number: int = Field(..., description="Turn number in conversation")
    user_input: str = Field(..., description="User input text")
    intent: Optional[Intent] = Field(default=None, description="Detected intent")
    action_taken: Optional[Action] = Field(default=None, description="Action executed")
    response: str = Field(default="", description="System response")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Turn timestamp",
    )
    user_feedback: Optional[str] = Field(
        default=None,
        description="User feedback (helpful, not_helpful, etc.)",
    )
    execution_time: float = Field(
        default=0.0,
        description="Total execution time for turn",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional turn metadata",
    )

    @field_validator("turn_id")
    @classmethod
    def validate_turn_id(cls, v: str) -> str:
        """Validate turn ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Turn ID cannot be empty")
        return v

    @field_validator("turn_number")
    @classmethod
    def validate_turn_number(cls, v: int) -> int:
        """Validate turn number is non-negative."""
        if v < 0:
            raise ValueError("Turn number must be non-negative")
        return v

    @field_validator("user_input")
    @classmethod
    def validate_user_input(cls, v: str) -> str:
        """Validate user input is not empty."""
        if not v or not v.strip():
            raise ValueError("User input cannot be empty")
        return v

    @field_validator("execution_time")
    @classmethod
    def validate_execution_time(cls, v: float) -> float:
        """Validate execution time is non-negative."""
        if v < 0:
            raise ValueError("Execution time must be non-negative")
        return v

    def __eq__(self, other: object) -> bool:
        """Check equality based on turn ID."""
        if not isinstance(other, ConversationTurn):
            return False
        return self.turn_id == other.turn_id

    def __hash__(self) -> int:
        """Generate hash for conversation turn."""
        return hash(self.turn_id)


class ConversationState(BaseModel):
    """Represents the state of an ongoing conversation."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "conversation_id": "conv_123",
            "user_id": "user_456",
            "turns": [],
            "entities": {},
            "user_preferences": {"voice_speed": "normal"},
            "context_summary": None,
            "last_intent": None,
            "active_tasks": [],
        }
    })

    conversation_id: str = Field(..., description="Unique conversation identifier")
    user_id: str = Field(..., description="User identifier")
    turns: list[ConversationTurn] = Field(
        default_factory=list,
        description="Conversation turns",
    )
    entities: dict[str, TrackedEntity] = Field(
        default_factory=dict,
        description="Tracked entities across turns",
    )
    user_preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Learned user preferences",
    )
    context_summary: Optional[str] = Field(
        default=None,
        description="LLM-generated conversation summary",
    )
    last_intent: Optional[Intent] = Field(
        default=None,
        description="Last detected intent",
    )
    active_tasks: list[str] = Field(
        default_factory=list,
        description="IDs of running async tasks",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Conversation creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional conversation metadata",
    )

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: str) -> str:
        """Validate conversation ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Conversation ID cannot be empty")
        return v

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user ID is not empty."""
        if not v or not v.strip():
            raise ValueError("User ID cannot be empty")
        return v

    @field_validator("turns")
    @classmethod
    def validate_turns_order(cls, v: list[ConversationTurn]) -> list[ConversationTurn]:
        """Validate turns are in chronological order."""
        for i in range(len(v) - 1):
            if v[i].turn_number >= v[i + 1].turn_number:
                raise ValueError("Turns must be in chronological order")
        return v

    def add_turn(self, turn: ConversationTurn) -> None:
        """
        Add a turn to the conversation.

        Args:
            turn: Turn to add
        """
        self.turns.append(turn)
        self.updated_at = datetime.now(tz=timezone.utc)

        # Update last intent
        if turn.intent:
            self.last_intent = turn.intent

    def get_recent_turns(self, count: int = 5) -> list[ConversationTurn]:
        """
        Get recent conversation turns.

        Args:
            count: Number of recent turns to retrieve

        Returns:
            List of recent turns
        """
        return self.turns[-count:] if len(self.turns) > count else self.turns

    def get_turn_count(self) -> int:
        """
        Get total number of turns.

        Returns:
            Number of turns
        """
        return len(self.turns)

    def track_entity(
        self,
        entity_type: str,
        value: Any,
        turn_number: int,
        confidence: float = 1.0,
    ) -> None:
        """
        Track an entity across conversation.

        Args:
            entity_type: Type of entity
            value: Entity value
            turn_number: Current turn number
            confidence: Confidence score
        """
        key = f"{entity_type}:{value}"

        if key in self.entities:
            # Update existing entity
            entity = self.entities[key]
            entity.last_mentioned = turn_number
            entity.mention_count += 1
            entity.confidence = max(entity.confidence, confidence)
        else:
            # Create new tracked entity
            self.entities[key] = TrackedEntity(
                entity_type=entity_type,
                value=value,
                first_mentioned=turn_number,
                last_mentioned=turn_number,
                mention_count=1,
                confidence=confidence,
            )

        self.updated_at = datetime.now(tz=timezone.utc)

    def get_entity(self, entity_type: str) -> Optional[TrackedEntity]:
        """
        Get most recently mentioned entity of given type.

        Args:
            entity_type: Type of entity to retrieve

        Returns:
            Most recent entity of that type or None
        """
        matching = [
            e for e in self.entities.values()
            if e.entity_type == entity_type
        ]

        if not matching:
            return None

        # Return most recently mentioned
        return max(matching, key=lambda e: e.last_mentioned)

    def prune_old_turns(self, max_turns: int = 20) -> int:
        """
        Prune old turns to maintain size limit.

        Args:
            max_turns: Maximum number of turns to keep

        Returns:
            Number of turns pruned
        """
        if len(self.turns) <= max_turns:
            return 0

        pruned_count = len(self.turns) - max_turns
        self.turns = self.turns[-max_turns:]
        self.updated_at = datetime.now(tz=timezone.utc)

        return pruned_count

    def __eq__(self, other: object) -> bool:
        """Check equality based on conversation ID."""
        if not isinstance(other, ConversationState):
            return False
        return self.conversation_id == other.conversation_id

    def __hash__(self) -> int:
        """Generate hash for conversation state."""
        return hash(self.conversation_id)
