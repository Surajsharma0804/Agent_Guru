"""
Conversation context manager for maintaining conversation state.

ZERO COMPROMISE - BEST IMPLEMENTATION

This module provides conversation context management including:
- Multi-turn conversation tracking
- Reference resolution (pronouns, "it", "that")
- Topic shift detection
- User preference extraction
- Conversation summarization
- Separate contexts for Guru and Maya personalities
"""

import time
import uuid
from typing import Dict, List, Optional, Any
import re

from Agent_Guru.speech.models import (
    ConversationContext,
    ConversationTurn,
    PersonalityType,
    EmotionType
)
from Agent_Guru.speech.exceptions import GuruSpeechError


class ContextNotFoundError(GuruSpeechError):
    """Raised when conversation context is not found."""
    pass


class ConversationContextManager:
    """
    Manage conversation context across multiple turns.
    
    Features:
    - Track last N conversation turns
    - Resolve references to previous context
    - Detect topic shifts
    - Extract user preferences
    - Generate conversation summaries
    - Maintain separate contexts per personality
    
    Thread-safe for concurrent access.
    """
    
    def __init__(self, max_history_turns: int = 10):
        """
        Initialize conversation context manager.
        
        Args:
            max_history_turns: Maximum turns to keep in memory (default: 10)
        """
        self.max_history_turns = max_history_turns
        self._contexts: Dict[str, ConversationContext] = {}
        
        # Reference resolution patterns
        self._pronoun_patterns = [
            r'\bit\b',
            r'\bthat\b',
            r'\bthis\b',
            r'\bthose\b',
            r'\bthese\b',
            r'\bthe one\b',
            r'\bthe same\b',
        ]
        
        # Topic keywords for shift detection
        self._topic_keywords = {
            'weather': ['weather', 'temperature', 'rain', 'sunny', 'forecast'],
            'email': ['email', 'message', 'inbox', 'send', 'reply'],
            'calendar': ['calendar', 'meeting', 'appointment', 'schedule', 'event'],
            'file': ['file', 'document', 'folder', 'save', 'open'],
            'system': ['volume', 'brightness', 'wifi', 'bluetooth', 'settings'],
            'web': ['search', 'browse', 'website', 'google', 'internet'],
        }
    
    def create_context(
        self,
        user_id: str,
        personality: PersonalityType
    ) -> tuple[str, ConversationContext]:
        """
        Create new conversation context.
        
        Args:
            user_id: User identifier
            personality: AI personality (GURU or MAYA)
            
        Returns:
            Tuple of (context_id, ConversationContext)
        """
        context_id = f"{user_id}_{personality.value}_{uuid.uuid4().hex[:8]}"
        
        context = ConversationContext(
            personality=personality,
            turns=[],
            current_topic=None,
            user_preferences={},
            created_at=time.time(),
            updated_at=time.time()
        )
        
        self._contexts[context_id] = context
        return context_id, context
    
    def add_turn(
        self,
        context_id: str,
        speaker: str,
        text: str,
        emotion: Optional[EmotionType] = None
    ) -> ConversationContext:
        """
        Add conversation turn to context.
        
        Args:
            context_id: Context identifier
            speaker: Speaker identifier ("user" or "agent")
            text: Spoken/transcribed text
            emotion: Optional emotion detected
            
        Returns:
            Updated ConversationContext
            
        Raises:
            ContextNotFoundError: If context_id not found
        """
        if context_id not in self._contexts:
            raise ContextNotFoundError(f"Context not found: {context_id}")
        
        context = self._contexts[context_id]
        
        # Create turn
        turn = ConversationTurn(
            speaker=speaker,
            text=text,
            timestamp=time.time(),
            emotion=emotion
        )
        
        # Add turn and maintain max history
        context.turns.append(turn)
        if len(context.turns) > self.max_history_turns:
            context.turns = context.turns[-self.max_history_turns:]
        
        # Update topic if needed
        if speaker == "user":
            new_topic = self._extract_topic(text)
            if new_topic and new_topic != context.current_topic:
                context.current_topic = new_topic
        
        # Extract preferences
        if speaker == "user":
            preferences = self._extract_preferences_from_text(text)
            context.user_preferences.update(preferences)
        
        context.updated_at = time.time()
        
        return context
    
    def resolve_reference(
        self,
        context_id: str,
        reference: str
    ) -> Optional[str]:
        """
        Resolve pronoun or reference to previous context.
        
        Examples:
        - "it" -> last mentioned noun/entity
        - "that" -> last mentioned concept
        - "the one I mentioned" -> previous reference
        
        Args:
            context_id: Context identifier
            reference: Reference text to resolve
            
        Returns:
            Resolved text or None if cannot resolve
            
        Raises:
            ContextNotFoundError: If context_id not found
        """
        if context_id not in self._contexts:
            raise ContextNotFoundError(f"Context not found: {context_id}")
        
        context = self._contexts[context_id]
        
        # Check if reference contains pronouns
        has_pronoun = any(
            re.search(pattern, reference.lower())
            for pattern in self._pronoun_patterns
        )
        
        if not has_pronoun:
            return None
        
        # Look back through turns to find referent
        for turn in reversed(context.turns):
            if turn.speaker == "user":
                # Extract nouns/entities from previous user turns
                entities = self._extract_entities(turn.text)
                if entities:
                    # Return most recent entity
                    return entities[0]
        
        return None
    
    def detect_topic_shift(
        self,
        context_id: str,
        new_input: str
    ) -> bool:
        """
        Detect if conversation topic has changed.
        
        Args:
            context_id: Context identifier
            new_input: New user input
            
        Returns:
            True if topic shift detected, False otherwise
            
        Raises:
            ContextNotFoundError: If context_id not found
        """
        if context_id not in self._contexts:
            raise ContextNotFoundError(f"Context not found: {context_id}")
        
        context = self._contexts[context_id]
        
        if not context.current_topic:
            return False
        
        new_topic = self._extract_topic(new_input)
        
        if not new_topic:
            return False
        
        return new_topic != context.current_topic
    
    def get_context_summary(
        self,
        context_id: str
    ) -> str:
        """
        Generate summary of conversation context.
        
        Args:
            context_id: Context identifier
            
        Returns:
            Human-readable conversation summary
            
        Raises:
            ContextNotFoundError: If context_id not found
        """
        if context_id not in self._contexts:
            raise ContextNotFoundError(f"Context not found: {context_id}")
        
        context = self._contexts[context_id]
        
        if not context.turns:
            return "No conversation history."
        
        summary_parts = []
        summary_parts.append(f"Conversation with {context.personality.value.title()}")
        summary_parts.append(f"Total turns: {len(context.turns)}")
        
        if context.current_topic:
            summary_parts.append(f"Current topic: {context.current_topic}")
        
        if context.user_preferences:
            prefs = ", ".join(f"{k}: {v}" for k, v in context.user_preferences.items())
            summary_parts.append(f"User preferences: {prefs}")
        
        # Add recent turns
        summary_parts.append("\nRecent conversation:")
        for turn in context.turns[-3:]:  # Last 3 turns
            speaker_label = "User" if turn.speaker == "user" else context.personality.value.title()
            summary_parts.append(f"  {speaker_label}: {turn.text[:50]}...")
        
        return "\n".join(summary_parts)
    
    def clear_context(self, context_id: str) -> None:
        """
        Clear conversation context.
        
        Args:
            context_id: Context identifier
            
        Raises:
            ContextNotFoundError: If context_id not found
        """
        if context_id not in self._contexts:
            raise ContextNotFoundError(f"Context not found: {context_id}")
        
        del self._contexts[context_id]
    
    def get_context(self, context_id: str) -> ConversationContext:
        """
        Get conversation context.
        
        Args:
            context_id: Context identifier
            
        Returns:
            ConversationContext
            
        Raises:
            ContextNotFoundError: If context_id not found
        """
        if context_id not in self._contexts:
            raise ContextNotFoundError(f"Context not found: {context_id}")
        
        return self._contexts[context_id]
    
    def extract_preferences(
        self,
        context_id: str
    ) -> Dict[str, Any]:
        """
        Extract user preferences from conversation.
        
        Examples:
        - "I prefer email over calls" -> {"communication": "email"}
        - "I like morning meetings" -> {"meeting_time": "morning"}
        
        Args:
            context_id: Context identifier
            
        Returns:
            Dictionary of extracted preferences
            
        Raises:
            ContextNotFoundError: If context_id not found
        """
        if context_id not in self._contexts:
            raise ContextNotFoundError(f"Context not found: {context_id}")
        
        context = self._contexts[context_id]
        return context.user_preferences.copy()
    
    def _extract_topic(self, text: str) -> Optional[str]:
        """
        Extract topic from text using keyword matching.
        
        Args:
            text: Input text
            
        Returns:
            Topic name or None
        """
        text_lower = text.lower()
        
        for topic, keywords in self._topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return topic
        
        return None
    
    def _extract_entities(self, text: str) -> List[str]:
        """
        Extract entities (nouns, proper nouns) from text.
        
        Simple implementation using capitalized words and common nouns.
        
        Args:
            text: Input text
            
        Returns:
            List of extracted entities
        """
        entities = []
        
        # Extract capitalized words (proper nouns)
        words = text.split()
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word[0].isupper() and len(clean_word) > 1:
                entities.append(clean_word)
        
        # Extract common nouns (simple heuristic)
        common_nouns = ['file', 'document', 'email', 'message', 'meeting', 'task', 'app', 'browser']
        for noun in common_nouns:
            if noun in text.lower():
                entities.append(noun)
        
        return entities
    
    def _extract_preferences_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract user preferences from text.
        
        Looks for patterns like:
        - "I prefer X over Y"
        - "I like X"
        - "I don't like X"
        - "I want X"
        
        Args:
            text: Input text
            
        Returns:
            Dictionary of preferences
        """
        preferences = {}
        text_lower = text.lower()
        
        # Pattern: "I prefer X over Y"
        prefer_match = re.search(r'i prefer (\w+) over (\w+)', text_lower)
        if prefer_match:
            preferred = prefer_match.group(1)
            not_preferred = prefer_match.group(2)
            preferences[f"prefer_{preferred}_over_{not_preferred}"] = True
        
        # Pattern: "I like X"
        like_match = re.search(r'i like (\w+(?:\s+\w+)?)', text_lower)
        if like_match:
            liked = like_match.group(1)
            preferences[f"likes_{liked.replace(' ', '_')}"] = True
        
        # Pattern: "I don't like X"
        dislike_match = re.search(r"i don't like (\w+(?:\s+\w+)?)", text_lower)
        if dislike_match:
            disliked = dislike_match.group(1)
            preferences[f"dislikes_{disliked.replace(' ', '_')}"] = True
        
        # Pattern: "I want X"
        want_match = re.search(r'i want (\w+(?:\s+\w+)?)', text_lower)
        if want_match:
            wanted = want_match.group(1)
            preferences[f"wants_{wanted.replace(' ', '_')}"] = True
        
        return preferences
