"""
Context Manager for conversation history and context window management.

Manages per-session conversation history with automatic compression
when approaching context window limits.

Performance:
    Time Complexity: O(n) for compression, O(1) for inject/update
    Space Complexity: O(s * m) where s=sessions, m=messages per session

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
import warnings  # kept for any future use; context pressure now uses logger (BUG-030)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from Agent_Guru.llm.models import Message
from Agent_Guru.llm.token_counter import TokenCounter

logger = logging.getLogger(__name__)

# BUG-031: Renamed to public CONTEXT_LIMITS so llm_runtime.py can import it
# instead of duplicating the same dict. This is the single canonical definition.
CONTEXT_LIMITS: dict[str, int] = {
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo-16k": 16384,
    "gpt-3.5-turbo": 4096,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-2": 100000,
    "gemini-pro": 32768,
    "gemini-1.5": 1000000,
}
# Keep private alias for backward-compat within this module
_CONTEXT_LIMITS = CONTEXT_LIMITS


@dataclass
class SessionContext:
    """Context for a single conversation session."""

    session_id: str
    messages: list[Message] = field(default_factory=list)
    token_count: int = 0
    # BUG-007: use UTC-aware datetimes to prevent timezone-comparison TypeError
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """
    Manages conversation history and context windows.

    Features:
    - Per-session history tracking with thread-safe updates
    - Automatic context compression at configurable threshold
    - Token budget management
    - Context injection and manipulation

    Example:
        >>> counter = TokenCounter()
        >>> cm = ContextManager(counter)
        >>> await cm.update_context("session1", user_msg, assistant_msg)
        >>> messages = cm.inject_context("session1", new_messages)
    """

    def __init__(
        self,
        token_counter: TokenCounter,
        compression_threshold: float = 0.8,
        max_history_messages: int = 100,
    ) -> None:
        self.token_counter = token_counter
        self.compression_threshold = compression_threshold
        self.max_history_messages = max_history_messages
        self.sessions: dict[str, SessionContext] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inject_context(
        self, session_id: str, messages: list[Message]
    ) -> list[Message]:
        """
        Inject conversation history into a message list.

        System messages are kept first; history is inserted before
        the new user messages.

        Args:
            session_id: Session identifier.
            messages: Current (new) messages for this turn.

        Returns:
            Combined message list with history injected.
        """
        if session_id not in self.sessions:
            return messages

        context = self.sessions[session_id]
        if not context.messages:
            return messages

        system_messages = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        return system_messages + context.messages + non_system

    async def update_context(
        self,
        session_id: str,
        user_message: Message,
        assistant_message: Message,
    ) -> None:
        """
        Append a user/assistant exchange to the session history.

        Automatically trims history if it exceeds max_history_messages.

        Args:
            session_id: Session identifier.
            user_message: The user's message.
            assistant_message: The assistant's response.
        """
        async with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = SessionContext(session_id=session_id)

            ctx = self.sessions[session_id]
            ctx.messages.extend([user_message, assistant_message])
            # BUG-007: use UTC-aware timestamp
            ctx.last_updated = datetime.now(tz=timezone.utc)

            # Trim to max history
            if len(ctx.messages) > self.max_history_messages:
                ctx.messages = ctx.messages[-self.max_history_messages :]

            # BUG-016: token count must use the session's actual model, not the
            # hardcoded "gpt-3.5-turbo" — caller can pass model via session metadata.
            # Fall back to gpt-3.5-turbo only if no model recorded yet.
            model_for_count = ctx.metadata.get("model", "gpt-3.5-turbo")
            ctx.token_count = self.token_counter.count_messages(
                ctx.messages, model_for_count
            )

    def get_context_usage(self, session_id: str, model: str) -> dict[str, Any]:
        """
        Return context usage statistics for a session.

        Args:
            session_id: Session identifier.
            model: Model name (used to determine context limit).

        Returns:
            Dict with token_count, message_count, context_limit, usage_percentage.
        """
        if session_id not in self.sessions:
            return {
                "token_count": 0,
                "message_count": 0,
                "context_limit": self._get_context_limit(model),
                "usage_percentage": 0.0,
            }

        ctx = self.sessions[session_id]
        limit = self._get_context_limit(model)
        usage_pct = (ctx.token_count / limit * 100) if limit > 0 else 0.0

        if usage_pct >= self.compression_threshold * 100:
            # BUG-030: was warnings.warn() — replaced with logger.warning so it
            # flows through structured logging and is not silently suppressed.
            logger.warning(
                "Session '%s' context usage at %.1f%% of %s context window (%d tokens).",
                session_id, usage_pct, model, limit,
            )

        return {
            "token_count": ctx.token_count,
            "message_count": len(ctx.messages),
            "context_limit": limit,
            "usage_percentage": usage_pct,
        }

    async def compress_context(self, session_id: str, target_tokens: int) -> None:
        """
        Compress session context to fit within target_tokens.

        Strategy: Remove oldest non-system messages while preserving
        the system prompt and most recent messages.

        Args:
            session_id: Session identifier.
            target_tokens: Target token budget.
        """
        if session_id not in self.sessions:
            return

        if target_tokens <= 0:
            return

        async with self._lock:
            ctx = self.sessions[session_id]

            while ctx.token_count > target_tokens and len(ctx.messages) > 1:
                # Preserve system message at index 0
                if ctx.messages[0].role == "system" and len(ctx.messages) > 1:
                    ctx.messages.pop(1)
                else:
                    ctx.messages.pop(0)

                # BUG-016: use session's recorded model (same fix as update_context)
                model_for_count = ctx.metadata.get("model", "gpt-3.5-turbo")
                ctx.token_count = self.token_counter.count_messages(
                    ctx.messages, model_for_count
                )

    def clear_context(self, session_id: str) -> None:
        """Remove all history for a session."""
        self.sessions.pop(session_id, None)

    def insert_message(
        self, session_id: str, message: Message, index: int
    ) -> None:
        """Insert a message at a specific position in the session history."""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionContext(session_id=session_id)
        ctx = self.sessions[session_id]
        ctx.messages.insert(index, message)
        # BUG-016: use session's recorded model
        model_for_count = ctx.metadata.get("model", "gpt-3.5-turbo")
        ctx.token_count = self.token_counter.count_messages(
            ctx.messages, model_for_count
        )

    def delete_message(self, session_id: str, index: int) -> None:
        """Delete a message at a specific position in the session history."""
        if session_id not in self.sessions:
            return
        ctx = self.sessions[session_id]
        if 0 <= index < len(ctx.messages):
            ctx.messages.pop(index)
            # BUG-016: use session's recorded model
            model_for_count = ctx.metadata.get("model", "gpt-3.5-turbo")
            ctx.token_count = self.token_counter.count_messages(
                ctx.messages, model_for_count
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_context_limit(model: str) -> int:
        """Return the context window limit for a given model."""
        for prefix, limit in _CONTEXT_LIMITS.items():
            if model.startswith(prefix):
                return limit
        return 4096  # Conservative default
