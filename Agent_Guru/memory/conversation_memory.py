"""Module: Agent_Guru.memory.conversation_memory
Purpose: Encrypted conversation memory with LRU eviction and persistence.

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
from datetime import UTC, datetime
from pathlib import Path

from Agent_Guru.utils.secure_file import (
    restrict_dir_permissions,
    restrict_file_permissions,
    secure_write_bytes,
)

logger = logging.getLogger(__name__)

# Default limits
_DEFAULT_MAX_TURNS = 50


# BUG-002: use OS-appropriate app-data directory so data survives working-directory
# changes and is never accidentally committed to git.
def _default_persist_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "agent_guru" / "memory" / "conversations.enc"


_DEFAULT_PERSIST_PATH = _default_persist_path()
_KEY_ID = os.environ.get("CONVERSATION_KEY_ID", "conversation_key")


class EncryptionUnavailableError(RuntimeError):
    """Raised when AES-256-GCM encryption/decryption cannot be performed.

    BUG FIX (Round 18): `_encrypt`/`_decrypt` used to silently fall back to
    writing/reading the conversation history as PLAIN, UNENCRYPTED JSON
    whenever the `cryptography` package failed to import -- while this
    class's own docstring promises "AES-256-GCM encryption for stored
    conversations". That means a user's full conversation history with
    their AI companion (this module's stated purpose) could be written to
    disk in the clear with no indication to the user or any caller that
    the promised protection wasn't actually applied. `cryptography` is a
    hard pinned dependency (requirements.txt: cryptography>=41.0.0), so
    this exists purely so a broken install fails loudly instead of
    quietly persisting sensitive data unprotected. See allow_insecure_
    fallback on ConversationMemory.__init__.
    """





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
    timestamp: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
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
    """Encrypted conversation memory with LRU eviction and disk persistence.

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
        *,
        allow_insecure_fallback: bool = False,
    ) -> None:
        """Initialize conversation memory.

        Args:
            max_turns: Maximum number of turns to keep (LRU eviction)
            persist_path: Path for encrypted persistence file
            auto_persist: Whether to auto-save after each turn
            allow_insecure_fallback: if True, persist()/load() are
                permitted to silently write/read PLAINTEXT conversation
                history when the `cryptography` package is unavailable.
                BUG FIX (Round 18): defaults to False -- see
                EncryptionUnavailableError. `cryptography` is a hard
                pinned dependency, so this only matters on a broken
                install; leave it False unless a test intentionally
                accepts unencrypted persistence.

        """
        if max_turns < 1:
            msg = f"max_turns must be >= 1, got {max_turns}"
            raise ValueError(msg)

        self._max_turns = max_turns
        self._persist_path = persist_path or _DEFAULT_PERSIST_PATH
        self._auto_persist = auto_persist
        self._allow_insecure_fallback = allow_insecure_fallback
        self._lock = threading.Lock()
        # Separate from _lock: _get_key() is reached from _encrypt()/_decrypt(),
        # which persist()/load() call *outside* _lock. Reusing _lock here would
        # be a latent self-deadlock the first time anyone moved a call site.
        self._key_lock = threading.Lock()
        self._turn_counter = 0

        # OrderedDict for O(1) LRU: key = turn_id, value = ConversationTurn
        self._turns: OrderedDict[int, ConversationTurn] = OrderedDict()

        # Encryption key (generated on first use)
        self._key: bytes | None = None

        logger.info(
            "ConversationMemory initialized: max_turns=%d, persist_path=%s",
            max_turns,
            self._persist_path,
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
            msg = f"role must be 'user' or 'assistant', got '{role}'"
            raise ValueError(msg)
        if not isinstance(content, str):
            msg = f"content must be str, got {type(content)}"
            raise TypeError(msg)

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
        elif last_n is not None and last_n <= 0:
            # BUG-004: last_n=0 should return empty list, not all turns
            return []

        return turns

    def get_context_dicts(self, last_n: int | None = None) -> list[dict]:
        """Return context as list of dicts (for LLM API calls).

        Args:
            last_n: Number of most recent turns

        Returns:
            List of {"role": ..., "content": ...} dicts

        """
        return [{"role": t.role, "content": t.content} for t in self.get_context(last_n=last_n)]

    def clear(self) -> None:
        """Clear all conversation history."""
        with self._lock:
            self._turns.clear()
            self._turn_counter = 0
        logger.info("ConversationMemory: history cleared")

    def delete_user_data(self) -> None:
        """GDPR-compliant deletion of all conversation data.

        Deletes the encryption key as well as the ciphertext. Leaving the key
        behind meant any copy of the encrypted history that outlived this call
        -- a backup, a synced folder, a forensic image -- stayed decryptable,
        which is precisely what a deletion request is asking to prevent.
        """
        self.clear()
        with self._key_lock:
            self._key = None
        for path in (self._persist_path, self._key_path()):
            try:
                if path.exists():
                    path.unlink()
                    logger.info("ConversationMemory: deleted %s", path)
            except OSError:
                logger.exception("ConversationMemory: could not delete %s", path)

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

        # DATA-LOSS FIX: write_bytes() truncates the destination first, so a
        # crash or power loss part-way through left a truncated file -- and a
        # truncated AES-GCM blob is not partially readable, it fails its
        # authentication tag and the ENTIRE conversation history is gone.
        # secure_write_bytes() writes a sibling temp file 0600 and renames it
        # over the destination, so a reader always sees one whole version.
        restrict_dir_permissions(self._persist_path.parent)
        secure_write_bytes(self._persist_path, encrypted)
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

                # BOUND FIX: add_turn() enforces max_turns, but load() did not,
                # so a file written when the limit was higher (or by hand)
                # restored an unbounded number of turns into a structure the
                # class documents as "Space Complexity: O(max_turns) bounded",
                # and get_context(None) then handed all of them to the LLM.
                dropped = 0
                while len(self._turns) > self._max_turns:
                    self._turns.popitem(last=False)
                    dropped += 1
                kept = len(self._turns)

            if dropped:
                logger.warning(
                    "ConversationMemory: loaded file held %s turns, above the "
                    "max_turns=%s limit; kept the %s most recent",
                    len(turns_data), self._max_turns, kept,
                )
            logger.info("ConversationMemory: loaded %s turns", kept)
            return True

        except Exception:
            logger.exception("ConversationMemory: failed to load")
            return False

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _key_path(self) -> Path:
        """Path of the AES key file that sits beside the encrypted history."""
        return self._persist_path.with_suffix(".key")

    def _get_key(self) -> bytes:
        """Get or generate the AES-256 key.

        Three defects fixed here, all of which cost the user their history or
        its confidentiality:

        1. SECURITY -- the key was written with ``write_bytes()``, i.e. under
           the process umask, commonly 0644. A world-readable key sitting next
           to the ciphertext it decrypts makes the AES-256-GCM this class
           advertises decorative on any shared machine. It is now created
           0600 by the open() itself, and its directory 0700.
        2. DATA LOSS (race) -- this method had no synchronization at all.
           Two threads persisting for the first time both saw ``_key is None``,
           both generated a *different* random key, and both wrote the file.
           Whichever lost the race had already encrypted a payload with a key
           that no longer existed on disk: that history was permanently
           undecryptable. The double-checked lock below makes exactly one key
           win, and O_EXCL extends the same guarantee across processes.
        3. CORRUPTION -- a truncated or foreign key file was passed straight
           to AESGCM, which fails with an opaque error. The length is now
           checked where the cause is still visible.
        """
        key = self._key
        if key is not None:
            return key

        with self._key_lock:
            if self._key is not None:
                return self._key

            key_path = self._key_path()
            key_path.parent.mkdir(parents=True, exist_ok=True)
            restrict_dir_permissions(key_path.parent)

            if key_path.exists():
                self._key = self._read_key(key_path)
                return self._key

            new_key = os.urandom(32)
            try:
                # O_EXCL: if another process created the key between the
                # exists() check above and this call, we must use THEIRS --
                # the ciphertext on disk was written with it.
                fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                self._key = self._read_key(key_path)
                return self._key

            with os.fdopen(fd, "wb") as fh:
                fh.write(new_key)
                fh.flush()
                os.fsync(fh.fileno())
            restrict_file_permissions(key_path)
            self._key = new_key
            return self._key

    @staticmethod
    def _read_key(key_path: Path) -> bytes:
        """Read and validate an existing key file."""
        key = key_path.read_bytes()
        if len(key) != 32:
            msg = (
                f"Conversation key file {key_path} is {len(key)} bytes, expected 32. "
                "It is truncated or not an Agent Guru key; refusing to use it."
            )
            raise EncryptionUnavailableError(msg)
        restrict_file_permissions(key_path)
        return key

    def _encrypt(self, plaintext: str) -> bytes:
        """Encrypt with AES-256-GCM. Returns nonce + ciphertext.

        Raises:
            EncryptionUnavailableError: if the `cryptography` package is
                unavailable and allow_insecure_fallback was not set True.

        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            key = self._get_key()
            nonce = os.urandom(12)
            aesgcm = AESGCM(key)
            ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            return nonce + ct
        except ImportError:
            # BUG FIX (Round 18): this used to silently persist the entire
            # conversation history as PLAINTEXT JSON when cryptography
            # couldn't be imported -- see EncryptionUnavailableError's
            # docstring. Fail loudly by default instead.
            if not self._allow_insecure_fallback:
                logger.critical(
                    "cryptography package unavailable -- refusing to "
                    "persist conversation history unencrypted. Install "
                    "cryptography>=41.0.0 (see requirements.txt), or "
                    "construct ConversationMemory(allow_insecure_fallback="
                    "True) if this is a test that intentionally accepts "
                    "plaintext persistence.",
                )
                msg = "cryptography package is unavailable; refusing insecure fallback"
                raise EncryptionUnavailableError(msg) from None
            return plaintext.encode("utf-8")

    def _decrypt(self, data: bytes) -> str:
        """Decrypt AES-256-GCM data.

        Raises:
            EncryptionUnavailableError: if the `cryptography` package is
                unavailable and allow_insecure_fallback was not set True.

        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            key = self._get_key()
            nonce, ct = data[:12], data[12:]
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
        except ImportError:
            if not self._allow_insecure_fallback:
                logger.critical(
                    "cryptography package unavailable -- refusing to read "
                    "persisted conversation history as plaintext. Install "
                    "cryptography>=41.0.0 (see requirements.txt), or "
                    "construct ConversationMemory(allow_insecure_fallback="
                    "True) if this is a test that intentionally accepts "
                    "plaintext persistence.",
                )
                msg = "cryptography package is unavailable; refusing insecure fallback"
                raise EncryptionUnavailableError(msg) from None
            return data.decode("utf-8")
