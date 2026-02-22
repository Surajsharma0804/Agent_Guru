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

    async def prune_turns(self, conversation_id: str, max_turns: int = 20) -> int:
        """
        Prune old turns from conversation history.

        Args:
            conversation_id: Unique conversation identifier
            max_turns: Maximum number of turns to keep

        Returns:
            Number of turns pruned
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return 0

        pruned_count = state.prune_old_turns(max_turns)

        if pruned_count > 0:
            await self.set_state(conversation_id, state)

        return pruned_count

    async def generate_summary(self, conversation_id: str, llm_generate_fn) -> Optional[str]:
        """
        Generate conversation summary using LLM.

        Args:
            conversation_id: Unique conversation identifier
            llm_generate_fn: Async function to generate summary from turns

        Returns:
            Generated summary or None if conversation not found
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return None

        # Generate summary using provided LLM function
        summary = await llm_generate_fn(state.turns)

        # Update state with summary
        state.context_summary = summary
        await self.set_state(conversation_id, state)

        return summary

    async def compress_context(
        self, conversation_id: str, max_turns: int = 20, llm_generate_fn=None
    ) -> bool:
        """
        Compress conversation context to fit within token limits.

        Strategy:
        1. If turns <= max_turns, no compression needed
        2. If turns > max_turns, generate summary of old turns and prune

        Args:
            conversation_id: Unique conversation identifier
            max_turns: Maximum number of turns to keep
            llm_generate_fn: Optional async function to generate summary

        Returns:
            True if compression was performed, False otherwise
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return False

        if len(state.turns) <= max_turns:
            return False

        # Generate summary of old turns if LLM function provided
        if llm_generate_fn is not None:
            old_turns = state.turns[:-max_turns]
            summary = await llm_generate_fn(old_turns)
            state.context_summary = summary

        # Prune old turns
        state.prune_old_turns(max_turns)
        await self.set_state(conversation_id, state)

        return True

    async def extract_and_track_entities(
        self,
        conversation_id: str,
        turn_number: int,
        entities: dict[str, any],
    ) -> None:
        """
        Extract and track entities from a conversation turn.

        Args:
            conversation_id: Unique conversation identifier
            turn_number: Current turn number
            entities: Dictionary of entity_type -> value pairs
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return

        # Track each entity
        for entity_type, value in entities.items():
            state.track_entity(entity_type, value, turn_number)

        await self.set_state(conversation_id, state)

    async def resolve_coreference(
        self,
        conversation_id: str,
        reference: str,
        entity_type: Optional[str] = None,
    ) -> Optional[TrackedEntity]:
        """
        Resolve coreference to most recent entity.

        Args:
            conversation_id: Unique conversation identifier
            reference: Reference text (e.g., "he", "she", "it", "that")
            entity_type: Optional entity type to filter by

        Returns:
            Most recently mentioned entity or None
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return None

        # Get entities of specified type or all entities
        if entity_type:
            matching = [e for e in state.entities.values() if e.entity_type == entity_type]
        else:
            matching = list(state.entities.values())

        if not matching:
            return None

        # Return most recently mentioned entity
        return max(matching, key=lambda e: e.last_mentioned)

    async def expire_old_entities(
        self,
        conversation_id: str,
        current_turn: int,
        max_turns_without_mention: int = 10,
    ) -> int:
        """
        Expire entities not mentioned in last N turns.

        Args:
            conversation_id: Unique conversation identifier
            current_turn: Current turn number
            max_turns_without_mention: Maximum turns without mention before expiration

        Returns:
            Number of entities expired
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return 0

        # Find expired entities
        expired_keys = [
            key
            for key, entity in state.entities.items()
            if current_turn - entity.last_mentioned > max_turns_without_mention
        ]

        # Remove expired entities
        for key in expired_keys:
            del state.entities[key]

        if expired_keys:
            await self.set_state(conversation_id, state)

        return len(expired_keys)

    async def get_entity_by_type(
        self,
        conversation_id: str,
        entity_type: str,
    ) -> Optional[TrackedEntity]:
        """
        Get most recently mentioned entity of given type.

        Args:
            conversation_id: Unique conversation identifier
            entity_type: Type of entity to retrieve

        Returns:
            Most recent entity of that type or None
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return None

        return state.get_entity(entity_type)

    async def resolve_pronoun(
        self,
        conversation_id: str,
        pronoun: str,
    ) -> Optional[TrackedEntity]:
        """
        Resolve pronoun to most recent entity.

        Pronoun mapping:
        - he/him/his -> person (male)
        - she/her/hers -> person (female)
        - it/its -> any non-person entity
        - they/them/their -> person or group

        Args:
            conversation_id: Unique conversation identifier
            pronoun: Pronoun to resolve

        Returns:
            Most recently mentioned entity or None
        """
        pronoun_lower = pronoun.lower()

        # Map pronouns to entity types
        if pronoun_lower in ["he", "him", "his", "she", "her", "hers", "they", "them", "their"]:
            return await self.resolve_coreference(conversation_id, pronoun, "person")
        elif pronoun_lower in ["it", "its"]:
            # Resolve to most recent non-person entity
            state = await self.get_state(conversation_id)
            if state is None:
                return None

            non_person = [e for e in state.entities.values() if e.entity_type != "person"]

            if not non_person:
                return None

            return max(non_person, key=lambda e: e.last_mentioned)

        return None

    async def resolve_implicit_reference(
        self,
        conversation_id: str,
        current_input: str,
    ) -> Optional[dict[str, any]]:
        """
        Resolve implicit reference from context.

        Examples:
        - "what about tomorrow?" after "weather today" -> {"intent": "weather", "time": "tomorrow"}
        - "and Seattle?" after "weather in NYC" -> {"intent": "weather", "location": "Seattle"}

        Args:
            conversation_id: Unique conversation identifier
            current_input: Current user input

        Returns:
            Dictionary with resolved context or None
        """
        state = await self.get_state(conversation_id)

        if state is None or not state.last_intent:
            return None

        # Get last intent for context
        last_intent = state.last_intent

        # Simple implicit reference patterns
        implicit_patterns = {
            "what about": last_intent.intent_type,
            "and": last_intent.intent_type,
            "how about": last_intent.intent_type,
        }

        current_lower = current_input.lower()

        for pattern, intent_type in implicit_patterns.items():
            if current_lower.startswith(pattern):
                # Return context from last intent
                return {
                    "intent_type": intent_type,
                    "entities": last_intent.entities.copy(),
                }

        return None

    async def complete_incomplete_request(
        self,
        conversation_id: str,
        current_input: str,
    ) -> Optional[str]:
        """
        Complete incomplete request using context.

        Examples:
        - "tomorrow" after "weather today" -> "weather tomorrow"
        - "5 minutes" after "set timer" -> "set timer for 5 minutes"

        Args:
            conversation_id: Unique conversation identifier
            current_input: Current user input

        Returns:
            Completed request or None
        """
        state = await self.get_state(conversation_id)

        if state is None or not state.last_intent:
            return None

        # Get last intent for context
        last_intent = state.last_intent

        # Check if current input is just an entity value
        current_lower = current_input.lower().strip()

        # Time references
        time_keywords = [
            "tomorrow",
            "today",
            "yesterday",
            "tonight",
            "morning",
            "afternoon",
            "evening",
        ]
        if any(keyword in current_lower for keyword in time_keywords):
            # Complete with last intent
            return f"{last_intent.intent_type} {current_input}"

        # Duration references
        duration_keywords = ["minutes", "hours", "seconds", "days"]
        if any(keyword in current_lower for keyword in duration_keywords):
            return f"{last_intent.intent_type} for {current_input}"

        # Location references (single word that might be a location)
        if len(current_input.split()) == 1 and current_input[0].isupper():
            return f"{last_intent.intent_type} in {current_input}"

        return None

    async def detect_ambiguous_reference(
        self,
        conversation_id: str,
        reference: str,
    ) -> Optional[list[TrackedEntity]]:
        """
        Detect ambiguous references that need clarification.

        Args:
            conversation_id: Unique conversation identifier
            reference: Reference text

        Returns:
            List of possible entities if ambiguous, None otherwise
        """
        state = await self.get_state(conversation_id)

        if state is None:
            return None

        # Check for ambiguous pronouns (they/them could refer to multiple people)
        if reference.lower() in ["they", "them", "their"]:
            people = [e for e in state.entities.values() if e.entity_type == "person"]

            # Ambiguous if multiple people mentioned recently
            if len(people) > 1:
                # Get people mentioned in last 3 turns
                recent_people = [
                    e for e in people if state.get_turn_count() - e.last_mentioned <= 3
                ]

                if len(recent_people) > 1:
                    return recent_people

        return None

    async def list_conversations(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[ConversationState]:
        """
        List conversations for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of conversations to return

        Returns:
            List of conversation states for the user
        """
        async with self._global_lock:
            # Filter conversations by user_id
            user_conversations = [
                entry.state
                for entry in self._cache.values()
                if entry.state.user_id == user_id
            ]
            
            # Sort by most recently updated
            user_conversations.sort(
                key=lambda s: s.updated_at,
                reverse=True,
            )
            
            # Return limited results
            return user_conversations[:limit]


# Global instance
_manager: Optional[ConversationStateManager] = None


def get_conversation_manager() -> ConversationStateManager:
    """Get global conversation manager instance.
    
    Returns:
        Conversation manager
    """
    global _manager
    if _manager is None:
        _manager = ConversationStateManager()
    return _manager
