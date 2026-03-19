"""
Module: Agent_Guru.llm.voice_context
Purpose: Voice-optimized conversation context management

Wraps ContextManager with voice-specific features:
- System prompt injection for voice personality
- Context window management across provider switches
- Conversation history persistence across sessions

Performance:
    - Time Complexity: O(1) for inject/update, O(n) for compression
    - Space Complexity: O(s * m) where s=sessions, m=messages
    - Retrieval latency: <10ms

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from Agent_Guru.llm.context_manager import ContextManager
from Agent_Guru.llm.models import Message
from Agent_Guru.llm.token_counter import TokenCounter

logger = logging.getLogger(__name__)

# Default voice system prompt
_VOICE_SYSTEM_PROMPT = (
    "You are Guru, a helpful AI voice assistant. "
    "Keep responses concise and natural for voice output. "
    "Avoid markdown, bullet points, or formatting. "
    "Speak in a friendly, conversational tone. "
    "If you don't know something, say so clearly."
)

# Default Maya personality prompt
_MAYA_SYSTEM_PROMPT = (
    "You are Maya, a warm and creative AI voice assistant. "
    "Keep responses concise and natural for voice output. "
    "Avoid markdown, bullet points, or formatting. "
    "Speak in a warm, empathetic, and creative tone. "
    "If you don't know something, say so clearly."
)


@dataclass
class VoiceContextConfig:
    """Configuration for voice context management.

    Attributes:
        max_turns: Maximum conversation turns to keep (LRU eviction)
        system_prompt: System prompt for voice personality
        personality: 'guru' or 'maya'
        context_window_tokens: Maximum tokens in context window
        compression_threshold: Fraction of context window before compression
    """
    max_turns: int = 50
    system_prompt: Optional[str] = None
    personality: str = "guru"
    context_window_tokens: int = 4096
    compression_threshold: float = 0.8


class VoiceContextManager:
    """
    Voice-optimized conversation context manager.

    Extends ContextManager with:
    - Automatic voice system prompt injection
    - Context preservation across provider switches
    - LRU eviction at max_turns limit
    - Fast retrieval (<10ms target)

    Example:
        >>> vcm = VoiceContextManager()
        >>> vcm.add_turn("session1", "open youtube", "Opening YouTube for you.")
        >>> messages = vcm.get_context_messages("session1")
        >>> print(len(messages))  # system + history
    """

    def __init__(self, config: Optional[VoiceContextConfig] = None) -> None:
        """Initialize voice context manager."""
        self._config = config or VoiceContextConfig()
        self._token_counter = TokenCounter()
        self._context_manager = ContextManager(
            token_counter=self._token_counter,
            compression_threshold=self._config.compression_threshold,
            max_history_messages=self._config.max_turns * 2,  # 2 msgs per turn
        )
        self._system_prompt = self._resolve_system_prompt()
        self._lock = asyncio.Lock()

    def _resolve_system_prompt(self) -> str:
        """Resolve system prompt from config or personality."""
        if self._config.system_prompt:
            return self._config.system_prompt
        if self._config.personality.lower() == "maya":
            return _MAYA_SYSTEM_PROMPT
        return _VOICE_SYSTEM_PROMPT

    def add_turn(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """
        Add a conversation turn to the session history.

        Time Complexity: O(1) amortized
        Space Complexity: O(1)

        Args:
            session_id: Session identifier
            user_text: User's utterance
            assistant_text: Assistant's response
        """
        user_msg = Message(role="user", content=user_text)
        assistant_msg = Message(role="assistant", content=assistant_text)

        # Use asyncio.run_coroutine_threadsafe or create event loop if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule as a task
                asyncio.ensure_future(
                    self._context_manager.update_context(
                        session_id, user_msg, assistant_msg
                    )
                )
            else:
                loop.run_until_complete(
                    self._context_manager.update_context(
                        session_id, user_msg, assistant_msg
                    )
                )
        except RuntimeError:
            # No event loop — create one
            asyncio.run(
                self._context_manager.update_context(
                    session_id, user_msg, assistant_msg
                )
            )

    def add_turn_sync(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """
        Synchronous version of add_turn for non-async contexts.

        Args:
            session_id: Session identifier
            user_text: User's utterance
            assistant_text: Assistant's response
        """
        user_msg = Message(role="user", content=user_text)
        assistant_msg = Message(role="assistant", content=assistant_text)

        if session_id not in self._context_manager.sessions:
            from Agent_Guru.llm.context_manager import SessionContext
            self._context_manager.sessions[session_id] = SessionContext(
                session_id=session_id
            )

        ctx = self._context_manager.sessions[session_id]
        ctx.messages.extend([user_msg, assistant_msg])

        # Enforce max_turns (LRU eviction — remove oldest pairs)
        max_msgs = self._config.max_turns * 2
        if len(ctx.messages) > max_msgs:
            ctx.messages = ctx.messages[-max_msgs:]

        # Update token count
        ctx.token_count = self._token_counter.count_messages(
            ctx.messages, "gpt-3.5-turbo"
        )

    def get_context_messages(
        self,
        session_id: str,
        new_messages: Optional[List[Message]] = None,
    ) -> List[Message]:
        """
        Get full context for a session including system prompt.

        Time Complexity: O(n) where n = history length
        Space Complexity: O(n)

        Args:
            session_id: Session identifier
            new_messages: New messages to append after history

        Returns:
            [system_prompt] + [history] + [new_messages]
        """
        system_msg = Message(role="system", content=self._system_prompt)
        new_messages = new_messages or []

        history = self._context_manager.inject_context(session_id, new_messages)

        # Ensure system message is first
        if history and history[0].role == "system":
            return history
        return [system_msg] + history

    def get_turn_count(self, session_id: str) -> int:
        """Return number of conversation turns for a session."""
        if session_id not in self._context_manager.sessions:
            return 0
        msg_count = len(self._context_manager.sessions[session_id].messages)
        return msg_count // 2  # Each turn = user + assistant

    def clear_session(self, session_id: str) -> None:
        """Clear all history for a session."""
        self._context_manager.clear_context(session_id)

    def get_token_usage(self, session_id: str) -> Dict[str, Any]:
        """Return token usage statistics for a session."""
        return self._context_manager.get_context_usage(session_id, "gpt-3.5-turbo")

    def switch_personality(self, personality: str) -> None:
        """
        Switch voice personality (guru/maya).

        Args:
            personality: 'guru' or 'maya'
        """
        self._config.personality = personality.lower()
        self._system_prompt = self._resolve_system_prompt()
        logger.info(f"Switched personality to: {personality}")

    def get_system_prompt(self) -> str:
        """Return the current system prompt."""
        return self._system_prompt

    def list_sessions(self) -> List[str]:
        """Return all active session IDs."""
        return list(self._context_manager.sessions.keys())
