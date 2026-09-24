"""Memory System Client for Speech Engine.

Stores emotion states, conversation turns, and user preferences
in the Memory System for long-term learning.

Performance Requirements:
- Store operations: async, non-blocking (<50ms overhead)
- Graceful degradation when memory system unavailable

Author: Speech Engine Team
Date: 2026-03-14
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .models import EmotionType

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    user_id: str
    speaker: str  # "user" | "assistant"
    text: str
    emotion: EmotionType
    personality: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class MemoryClient:
    """Client for storing speech-related data in the Memory System.

    Provides:
    - Emotion state storage for long-term mood tracking
    - Conversation turn storage for context learning
    - User preference extraction and storage

    Gracefully degrades when the Memory System is unavailable -
    all operations are fire-and-forget with error logging.

    Time Complexity: O(1) per store call
    Space Complexity: O(n) for local buffer (bounded at max_buffer_size)

    Example:
        >>> client = MemoryClient(memory_system)
        >>> await client.store_emotion_state("user_1", EmotionType.HAPPY, datetime.now())

    """

    def __init__(
        self,
        memory_system: Any | None = None,
        max_buffer_size: int = 1000,
    ) -> None:
        """Initialize the client.

        Args:
            memory_system: Memory system instance (None = disabled)
            max_buffer_size: Maximum local buffer size before oldest entries drop

        """
        self._system = memory_system
        self._max_buffer = max_buffer_size
        # Local ring-buffer for offline/degraded operation - deque for O(1) eviction
        self._emotion_buffer: deque[dict[str, Any]] = deque(maxlen=max_buffer_size)
        self._conversation_buffer: deque[ConversationTurn] = deque(maxlen=max_buffer_size)
        logger.info(
            "MemoryClient initialized (system=%s)",
            "connected" if memory_system else "disabled",
        )

    async def store_emotion_state(
        self,
        user_id: str,
        emotion: EmotionType,
        timestamp: datetime,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Store an emotion state observation for a user.

        Args:
            user_id: User identifier
            emotion: Detected emotion type
            timestamp: When the emotion was detected
            confidence: Detection confidence (0.0-1.0)
            metadata: Optional additional context

        Returns:
            True if stored successfully, False on error

        """
        record: dict[str, Any] = {
            "user_id": user_id,
            "emotion": emotion.value if hasattr(emotion, "value") else str(emotion),
            "timestamp": timestamp.isoformat(),
            "confidence": confidence,
            "metadata": metadata or {},
        }

        # Buffer locally (bounded ring-buffer - deque auto-evicts oldest)
        self._emotion_buffer.append(record)

        if self._system is None:
            return True

        try:
            await self._system.store_emotion_state(user_id, record)
            return True
        except Exception:
            logger.exception("Failed to store emotion state")
            return False

    async def store_conversation_turn(
        self,
        user_id: str,
        speaker: str,
        text: str,
        emotion: EmotionType,
        personality: str,
        timestamp: datetime | None = None,
    ) -> bool:
        """Store a conversation turn for context learning.

        Args:
            user_id: User identifier
            speaker: "user" or "assistant"
            text: Spoken/synthesized text
            emotion: Emotion during this turn
            personality: Active personality (GURU/MAYA)
            timestamp: Turn timestamp (defaults to now)

        Returns:
            True if stored successfully, False on error

        """
        turn = ConversationTurn(
            user_id=user_id,
            speaker=speaker,
            text=text,
            emotion=emotion,
            personality=personality,
            timestamp=timestamp or datetime.now(tz=UTC),
        )

        # Buffer locally - deque auto-evicts oldest
        self._conversation_buffer.append(turn)

        if self._system is None:
            return True

        try:
            record = {
                "user_id": turn.user_id,
                "speaker": turn.speaker,
                "text": turn.text,
                "emotion": turn.emotion.value
                if hasattr(turn.emotion, "value")
                else str(turn.emotion),
                "personality": turn.personality,
                "timestamp": turn.timestamp.isoformat(),
            }
            await self._system.store_conversation_turn(user_id, record)
            return True
        except Exception:
            logger.exception("Failed to store conversation turn")
            return False

    async def store_user_preference(
        self,
        user_id: str,
        preference_key: str,
        preference_value: Any,
    ) -> bool:
        """Store a user preference extracted from conversation.

        Args:
            user_id: User identifier
            preference_key: Preference name (e.g., "preferred_personality")
            preference_value: Preference value

        Returns:
            True if stored successfully, False on error

        """
        if self._system is None:
            return True

        try:
            await self._system.store_preference(user_id, preference_key, preference_value)
            return True
        except Exception:
            logger.exception("Failed to store preference")
            return False

    def get_recent_emotions(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent emotion records from local buffer for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of records to return

        Returns:
            List of emotion records (most recent last)

        """
        user_records = [r for r in self._emotion_buffer if r["user_id"] == user_id]
        return user_records[-limit:]

    def get_recent_turns(self, user_id: str, limit: int = 10) -> list[ConversationTurn]:
        """Get recent conversation turns from local buffer for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of turns to return

        Returns:
            List of conversation turns (most recent last)

        """
        user_turns = [t for t in self._conversation_buffer if t.user_id == user_id]
        return user_turns[-limit:]
