"""
Conversation State Manager.

This module implements thread-safe conversation state management with LRU caching
and automatic eviction.
"""

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
    TrackedEntity,
)


@dataclass
class ConversationCacheEntry:
    """Cache entry for conversation state."""

    state: ConversationState
    last_access: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ConversationStateManager:
    """
    Thread-safe conversation state manager with LRU caching.

    Features:
    - LRU cache for active conversations (max 10,000)
    - Automatic eviction after 1 hour of inactivity
    - Thread-safe operations with asyncio locks
    - Efficient state access and updates

    Time Complexity: O(1) for get/set operations
    Space Complexity: O(n) where n is number of active conversations
    """

    def __init__(
        self,
        max_conversations: int = 10000,
        inactivity_timeout: float = 3600.0,  # 1 hour
    ):
        """
        Initialize conversation state manager.

        Args:
            max_conversations: Maximum number of conversations to cache
            inactivity_timeout: Timeout in seconds for inactive conversations
        """
        if max_conversations <= 0:
            raise ValueError("max_conversations must be positive")
        if inactivity_timeout <= 0:
            raise ValueError("inactivity_timeout must be positive")

        self.max_conversations = max_conversations
        self.inactivity_timeout = inactivity_timeout

        # LRU cache: OrderedDict maintains insertion order
        self._cache: OrderedDict[str, ConversationCacheEntry] = OrderedDict()
        self._global_lock = asyncio.Lock()

    async def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        """
        Get conversation state by ID.

        Time Complexity: O(1) average
        Space Complexity: O(1)

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            ConversationState if found, None otherwise
        """
        async with self._global_lock:
            entry = self._cache.get(conversation_id)

            if entry is None:
                return None

            # Check if expired
            if time.time() - entry.last_access > self.inactivity_timeout:
                del self._cache[conversation_id]
                return None

            # Update access time and move to end (LRU)
            entry.last_access = time.time()
            self._cache.move_to_end(conversation_id)

            return entry.state

    async def set_state(self, conversation_id: str, state: ConversationState) -> None:
        """
        Set conversation state.

        Time Complexity: O(1) average
        Space Complexity: O(1)

        Args:
            conversation_id: Unique conversation identifier
            state: Conversation state to store
        """
        async with self._global_lock:
            # Evict oldest if at capacity
            if conversation_id not in self._cache and len(self._cache) >= self.max_conversations:
                # Remove oldest (first item)
                self._cache.popitem(last=False)

            # Create or update entry
            if conversation_id in self._cache:
                entry = self._cache[conversation_id]
                entry.state = state
                entry.last_access = time.time()
                self._cache.move_to_end(conversation_id)
            else:
                entry = ConversationCacheEntry(state=state)
                self._cache[conversation_id] = entry

    async def delete_state(self, conversation_id: str) -> bool:
        """
        Delete conversation state.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if deleted, False if not found
        """
        async with self._global_lock:
            if conversation_id in self._cache:
                del self._cache[conversation_id]
                return True
            return False

    async def add_turn(self, conversation_id: str, turn: ConversationTurn) -> None:
        """
        Add a turn to conversation history.

        Args:
            conversation_id: Unique conversation identifier
            turn: Conversation turn to add
        """
        state = await self.get_state(conversation_id)

        if state is None:
            # Create new conversation state
            state = ConversationState(
                conversation_id=conversation_id,
                user_id="unknown",  # Will be set from turn if available
                turns=[turn],
                entities={},
            )
        else:
            # Add turn to existing state
            state.turns.append(turn)

        await self.set_state(conversation_id, state)

    async def get_recent_turns(
        self, conversation_id: str, max_turns: int = 20
    ) -> list[ConversationTurn]:
        """
        Get recent conversation turns.

        Args:
            conversation_id: Unique conversation identifier
            max_turns: Maximum number of turns to return

        Returns:
            List of recent turns (most recent last)
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return []

        return state.turns[-max_turns:]

    async def track_entity(self, conversation_id: str, entity: TrackedEntity) -> None:
        """
        Track an entity in conversation.

        Args:
            conversation_id: Unique conversation identifier
            entity: Entity to track
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return

        key = f"{entity.entity_type}:{entity.value}"
        state.entities[key] = entity
        await self.set_state(conversation_id, state)

    async def get_tracked_entities(self, conversation_id: str) -> dict[str, TrackedEntity]:
        """
        Get all tracked entities.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Dictionary of tracked entities
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return {}

        return state.entities

    async def evict_expired(self) -> int:
        """
        Evict expired conversations.

        Returns:
            Number of conversations evicted
        """
        async with self._global_lock:
            current_time = time.time()
            expired = [
                conv_id
                for conv_id, entry in self._cache.items()
                if current_time - entry.last_access > self.inactivity_timeout
            ]

            for conv_id in expired:
                del self._cache[conv_id]

            return len(expired)

    async def get_active_count(self) -> int:
        """
        Get number of active conversations.

        Returns:
            Number of active conversations
        """
        async with self._global_lock:
            return len(self._cache)

    async def clear(self) -> None:
        """Clear all conversation states."""
        async with self._global_lock:
            self._cache.clear()
