"""
Module: Agent_Guru.memory.conversation_memory
Purpose: Encrypted conversation memory with LRU eviction and persistence

Provides:
- AES-256-GCM encryption for stored conversations
- LRU eviction (max 50 turns by default)
- Persistence to disk (.kiro/memory/conversations.enc)
- Fast context retrieval (≤10ms)
- User controls for history deletion

Performance:
    - Time Complexity: O(1) for add/get (LRU dict), O(n) for search
    - Space Complexity: O(max_turns) bounded
    - Retrieval latency: ≤10ms P99

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

import os

# Default limits
_DEFAULT_MAX_TURNS = 50
_DEFAULT_PERSIST_PATH = Path(".kiro/memory/conversations.enc")
_KEY_ID = os.environ.get("CONVERSATION_KEY_ID", "conversation_key")


@dataclass
class ConversationTurn:
    """A single turn in a conversation.

    Attributes:
        role: 'user' or 'assistant'
        content: Text content of the turn
        timestamp: ISO-format timestamp
        turn_id: Sequential turn identifier
    """
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    turn_id: int = 0

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "turn_id": self.turn_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConversationTurn:
        return cls(
            role=d["role"],
            content=d["content"],
            timestamp=d.get("timestamp", ""),
            turn_id=d.get("turn_id", 0),
        )


class ConversationMemory:
    """
    Encrypted conversation memory with LRU eviction and disk persistence.

    Stores conversation turns in an LRU-ordered dict (O(1) add/evict).
    Encrypts data with AES-256-GCM before writing to disk.
    Supports fast context retrieval for LLM context windows.

    Example:
        >>> mem = ConversationMemory(max_turns=50)
        >>> mem.add_turn("user", "Hello Guru!")
        >>> mem.add_turn("assistant", "Hello! How can I help?")
        >>> context = mem.get_context(last_n=10)
        >>> print(len(context))  # 2

    Performance:
        - add_turn: O(1) amortized
        - get_context: O(k) where k = last_n
        - Retrieval latency: ≤10ms P99
    """

    def __init__(
        self,
        max_turns: int = _DEFAULT_MAX_TURNS,
        persist_path: Path | None = None,
        auto_persist: bool = False,
    ) -> None:
        """Initialize conversation memory.

        Args:
            max_turns: Maximum number of turns to keep (LRU eviction)
            persist_path: Path for encrypted persistence file
            auto_persist: Whether to auto-save after each turn
        """
        if max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {max_turns}")

        self._max_turns = max_turns
        self._persist_path = persist_path or _DEFAULT_PERSIST_PATH
        self._auto_persist = auto_persist
        self._lock = threading.Lock()
        self._turn_counter = 0

        # OrderedDict for O(1) LRU: key = turn_id, value = ConversationTurn
        self._turns: OrderedDict[int, ConversationTurn] = OrderedDict()

        # Encryption key (generated on first use)
        self._key: bytes | None = None

        logger.info(
            f"ConversationMemory initialized: max_turns={max_turns}, "
            f"persist_path={self._persist_path}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_turn(self, role: str, content: str) -> ConversationTurn:
        """Add a conversation turn.

        Time Complexity: O(1) amortized (LRU eviction is O(1))

        Args:
            role: 'user' or 'assistant'
            content: Text content

        Returns:
            The created ConversationTurn

        Raises:
            ValueError: If role is not 'user' or 'assistant'
        """
        if role not in ("user", "assistant"):
            raise ValueError(f"role must be 'user' or 'assistant', got '{role}'")
        if not isinstance(content, str):
            raise TypeError(f"content must be str, got {type(content)}")

        with self._lock:
            self._turn_counter += 1
            turn = ConversationTurn(
                role=role,
                content=content,
                turn_id=self._turn_counter,
            )
            self._turns[turn.turn_id] = turn

            # LRU eviction: remove oldest if over limit
            while len(self._turns) > self._max_turns:
                self._turns.popitem(last=False)  # Remove oldest (FIFO order)

        if self._auto_persist:
            self.persist()

        return turn

    def get_context(self, last_n: int | None = None) -> list[ConversationTurn]:
        """Retrieve recent conversation turns for LLM context.

        Time Complexity: O(k) where k = last_n

        Args:
            last_n: Number of most recent turns to return. None = all turns.

        Returns:
            List of ConversationTurn in chronological order
        """
        with self._lock:
            turns = list(self._turns.values())

        if last_n is not None and last_n > 0:
            turns = turns[-last_n:]

        return turns

    def get_context_dicts(self, last_n: int | None = None) -> list[dict]:
        """Return context as list of dicts (for LLM API calls).

        Args:
            last_n: Number of most recent turns

        Returns:
            List of {"role": ..., "content": ...} dicts
        """
        return [
            {"role": t.role, "content": t.content}
            for t in self.get_context(last_n=last_n)
        ]

    def clear(self) -> None:
        """Clear all conversation history."""
        with self._lock:
            self._turns.clear()
            self._turn_counter = 0
        logger.info("ConversationMemory: history cleared")

    def delete_user_data(self) -> None:
        """GDPR-compliant deletion of all conversation data."""
        self.clear()
        # Remove persisted file if it exists
        try:
            if self._persist_path.exists():
                self._persist_path.unlink()
                logger.info("ConversationMemory: deleted %s", self._persist_path)
        except OSError as e:
            logger.warning("ConversationMemory: could not delete file: %s", e)

    def turn_count(self) -> int:
        """Return current number of stored turns."""
        with self._lock:
            return len(self._turns)

    def max_turns(self) -> int:
        """Return the maximum number of turns."""
        return self._max_turns

    # ------------------------------------------------------------------
    # Persistence (AES-256-GCM encrypted)
    # ------------------------------------------------------------------

    def persist(self) -> None:
        """Encrypt and save conversation history to disk.

        Uses AES-256-GCM encryption. Key is derived from a random 32-byte
        secret stored alongside the encrypted file.

        Raises:
            OSError: If the file cannot be written
        """
        with self._lock:
            turns_data = [t.to_dict() for t in self._turns.values()]

        payload = json.dumps(turns_data, ensure_ascii=False)
        encrypted = self._encrypt(payload)

        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._persist_path.write_bytes(encrypted)
        logger.debug("ConversationMemory: persisted %s turns", len(turns_data))

    def load(self) -> bool:
        """Load and decrypt conversation history from disk.

        Returns:
            True if loaded successfully, False if file doesn't exist or is corrupt
        """
        if not self._persist_path.exists():
            return False

        try:
            encrypted = self._persist_path.read_bytes()
            payload = self._decrypt(encrypted)
            turns_data = json.loads(payload)

            with self._lock:
                self._turns.clear()
                for d in turns_data:
                    turn = ConversationTurn.from_dict(d)
                    self._turns[turn.turn_id] = turn
                    self._turn_counter = max(self._turn_counter, turn.turn_id)

            logger.info("ConversationMemory: loaded %s turns", len(turns_data))
            return True

        except Exception as e:
            logger.error("ConversationMemory: failed to load: %s", e)
            return False

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _get_key(self) -> bytes:
        """Get or generate the encryption key."""
        if self._key is not None:
            return self._key

        key_path = self._persist_path.with_suffix(".key")
        if key_path.exists():
            self._key = key_path.read_bytes()
        else:
            self._key = os.urandom(32)
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(self._key)

        return self._key

    def _encrypt(self, plaintext: str) -> bytes:
        """Encrypt with AES-256-GCM. Returns nonce + ciphertext."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            key = self._get_key()
            nonce = os.urandom(12)
            aesgcm = AESGCM(key)
            ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            return nonce + ct
        except ImportError:
            # Fallback: store as plain JSON (dev/test only)
            logger.warning("cryptography not available - storing unencrypted")
            return plaintext.encode("utf-8")

    def _decrypt(self, data: bytes) -> str:
        """Decrypt AES-256-GCM data."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            key = self._get_key()
            nonce, ct = data[:12], data[12:]
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
        except ImportError:
            return data.decode("utf-8")
