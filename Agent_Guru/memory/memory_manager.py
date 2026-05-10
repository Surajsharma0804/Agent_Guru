"""Multi-platform memory manager for Agent Guru.

Provides async conversation storage and semantic search across ALL platforms:
Desktop (SQLite), Android (SharedPreferences + SQLite via adb),
iOS (UserDefaults + Core Data via xcrun).

Platform support:
    - Desktop (windows/macos/linux/unknown): aiosqlite-backed SQLite database
    - Android: SharedPreferences + SQLite simulated via adb (log + return True/value)
    - iOS:     UserDefaults + Core Data simulated via xcrun (log + return True/value)

Design Decisions:
    - All public methods are async
    - Returns True/False or list — never raises for normal failures
    - Per-personality conversation storage (GURU and MAYA)
    - Semantic search with embeddings (simulated/stub — log + return ranked list)
    - platform_override parameter for testing
    - Desktop uses in-memory dict + optional aiosqlite persistence
    - Mobile platforms simulate storage (log + return True/value)

Performance Characteristics:
    - Time Complexity: O(1) store, O(n) recall/search over stored interactions
    - Space Complexity: O(n) where n = number of stored interactions
    - Latency: <100ms per operation (simulated)

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

# BUG-029: aiosqlite is a soft dependency — fall back gracefully if not installed
try:
    import aiosqlite as _aiosqlite

    _AIOSQLITE_AVAILABLE = True
except ImportError:
    _aiosqlite = None  # type: ignore[assignment]
    _AIOSQLITE_AVAILABLE = False

if TYPE_CHECKING:
    from Agent_Guru.memory.config import MemoryConfig


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported personalities
# ---------------------------------------------------------------------------

PERSONALITIES = ("GURU", "MAYA")

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Thin wrapper — delegates to canonical PlatformDetector.

    Lazy-imports PlatformDetector to keep the memory layer free of a
    module-level dependency on the platform layer (avoids layer violation
    and circular import risks).
    """
    # Lazy import: platform layer is only needed at runtime, not import time.
    # This keeps memory/ independent of platform/ at the module boundary.
    from Agent_Guru.platform.platform_detector import PlatformDetector  # layer-exempt: lazy import avoids module-level memory→platform dependency

    return PlatformDetector.detect().os_name.lower()


def _is_desktop(plat: str) -> bool:
    """Return True if *plat* is a desktop platform."""
    return plat in ("windows", "macos", "linux", "unknown")


def _is_mobile(plat: str) -> bool:
    """Return True if *plat* is a mobile platform."""
    return plat in ("android", "ios")


# ---------------------------------------------------------------------------
# Interaction record
# ---------------------------------------------------------------------------


class _Interaction:
    """A single stored conversation turn."""

    __slots__ = ("ai_message", "embedding", "personality", "timestamp", "user_message")

    def __init__(
        self,
        personality: str,
        user_message: str,
        ai_message: str,
        timestamp: float | None = None,
    ) -> None:
        self.personality = personality.upper()
        self.user_message = user_message
        self.ai_message = ai_message
        self.timestamp: float = timestamp if timestamp is not None else time.time()
        # Simulated embedding: bag-of-words character frequencies (stub)
        self.embedding: list[float] = _stub_embed(user_message + " " + ai_message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "personality": self.personality,
            "user_message": self.user_message,
            "ai_message": self.ai_message,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Simulated embedding helpers
# ---------------------------------------------------------------------------


def _stub_embed(text: str) -> list[float]:
    """Return a stub embedding vector (character frequency, 26-dim).

    This is a placeholder for a real embedding model.  It produces a
    deterministic, normalised 26-element float vector based on letter
    frequencies so that cosine similarity gives a rough semantic signal
    for testing purposes.

    Time Complexity: O(n) where n = len(text)
    Space Complexity: O(1) — fixed 26-element output
    """
    counts = [0.0] * 26
    for ch in text.lower():
        if "a" <= ch <= "z":
            counts[ord(ch) - ord("a")] += 1.0
    total = sum(counts) or 1.0
    return [c / total for c in counts]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity between two equal-length vectors.

    Returns 0.0 if either vector is all-zeros.

    Time Complexity: O(d) where d = len(a)
    Space Complexity: O(1)
    """
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a < 1e-10 or mag_b < 1e-10:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------


class MemoryManager:
    """Async multi-platform memory manager for Agent Guru.

    Supports Desktop (SQLite via aiosqlite), Android (SharedPreferences +
    SQLite simulated via adb), and iOS (UserDefaults + Core Data simulated
    via xcrun).

    All operations are simulated on mobile (log + return True/value) to allow
    cross-platform testing without requiring real devices.

    Example::

        mgr = MemoryManager()
        await mgr.initialize()

        ok = await mgr.store_interaction(
            personality="GURU",
            user_message="What is the weather?",
            ai_message="It is sunny today.",
        )

        results = await mgr.recall(personality="GURU", limit=5)
        hits = await mgr.search(query="weather", limit=3)

        await mgr.shutdown()

    All action methods return ``True`` on success and ``False`` on failure.
    ``recall`` and ``search`` return a list (empty on failure).
    They never raise exceptions for normal operational failures.
    """

    def __init__(
        self,
        config: MemoryConfig | None = None,
        platform_override: str | None = None,
    ) -> None:
        """Create the memory manager.

        Args:
            config: Optional MemoryConfig instance (accepted but not required
                for the in-memory/simulated backend used on all platforms).
                Stored for future use by persistence backends.
            platform_override: Force a specific platform string (for testing).
                When ``None`` the platform is auto-detected.

        """
        self._config: MemoryConfig | None = config
        self._platform: str = platform_override or _detect_platform()
        self._initialized: bool = False

        # In-memory write-through cache: personality → list of _Interaction
        # On desktop this is populated from SQLite at init and kept in sync.
        self._store: dict[str, list[_Interaction]] = {p: [] for p in PERSONALITIES}

        # SQLite connection (desktop only, None on mobile / when aiosqlite missing)
        self._db: Any = None

        # Resolved database path (set during _initialize_desktop)
        self._db_path: Path | None = None

        logger.info("MemoryManager created — platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """Initialize the memory manager and underlying storage.

        Idempotent — safe to call multiple times.

        Returns:
            ``True`` on success, ``False`` on failure.

        """
        if self._initialized:
            logger.debug("MemoryManager already initialized")
            return True

        try:
            if _is_desktop(self._platform):
                await self._initialize_desktop()
            elif self._platform == "android":
                await self._initialize_android()
            elif self._platform == "ios":
                await self._initialize_ios()
            else:
                logger.warning(
                    "MemoryManager.initialize: unknown platform %r — simulating success",
                    self._platform,
                )

            self._initialized = True
            logger.info("MemoryManager initialized — platform=%s", self._platform)
            return True
        except Exception:
            logger.exception("MemoryManager.initialize failed")
            return False

    async def shutdown(self) -> bool:
        """Shut down the memory manager and release resources.

        Returns:
            ``True`` on success, ``False`` on failure.

        """
        try:
            if _is_desktop(self._platform):
                await self._shutdown_desktop()
            elif self._platform == "android":
                await self._shutdown_android()
            elif self._platform == "ios":
                await self._shutdown_ios()
            else:
                logger.warning(
                    "MemoryManager.shutdown: unknown platform %r — simulating success",
                    self._platform,
                )

            self._initialized = False
            logger.info("MemoryManager shut down")
            return True
        except Exception:
            logger.exception("MemoryManager.shutdown failed")
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def store_interaction(
        self,
        personality: str,
        user_message: str,
        ai_message: str,
    ) -> bool:
        """Store a conversation turn for the given personality.

        Args:
            personality: ``"GURU"`` or ``"MAYA"`` (case-insensitive).
            user_message: The user's utterance.
            ai_message: The AI's response.

        Returns:
            ``True`` on success, ``False`` on invalid personality or failure.

        """
        personality = personality.upper()
        if personality not in PERSONALITIES:
            logger.warning(
                "store_interaction: unknown personality %r (must be GURU or MAYA)",
                personality,
            )
            return False

        # BUG-010: strip whitespace before checking — reject whitespace-only messages
        if not user_message.strip() or not ai_message.strip():
            logger.warning(
                "store_interaction: requires non-empty user_message AND ai_message — skipping "
                "(user_empty=%s, ai_empty=%s)",
                not user_message.strip(),
                not ai_message.strip(),
            )
            return False

        logger.info(
            "store_interaction: personality=%s user_len=%d ai_len=%d platform=%s",
            personality,
            len(user_message),
            len(ai_message),
            self._platform,
        )

        try:
            interaction = _Interaction(
                personality=personality,
                user_message=user_message,
                ai_message=ai_message,
            )

            if _is_desktop(self._platform):
                return await self._store_desktop(interaction)
            if self._platform == "android":
                return await self._store_android(interaction)
            if self._platform == "ios":
                return await self._store_ios(interaction)
            logger.warning(
                "store_interaction: unknown platform %r — simulating success",
                self._platform,
            )
            self._store[personality].append(interaction)
            return True
        except Exception:
            logger.exception("store_interaction failed")
            return False

    async def recall(
        self,
        personality: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve the most recent interactions for the given personality.

        Args:
            personality: ``"GURU"`` or ``"MAYA"`` (case-insensitive).
            limit: Maximum number of interactions to return (default 10).

        Returns:
            List of interaction dicts (newest first), empty list on failure.

        """
        personality = personality.upper()
        if personality not in PERSONALITIES:
            logger.warning("recall: unknown personality %r (must be GURU or MAYA)", personality)
            return []

        if limit <= 0:
            logger.warning("recall: limit must be > 0, got %d", limit)
            return []

        logger.info(
            "recall: personality=%s limit=%d platform=%s",
            personality,
            limit,
            self._platform,
        )

        try:
            if _is_desktop(self._platform):
                return await self._recall_desktop(personality, limit)
            if self._platform == "android":
                return await self._recall_android(personality, limit)
            if self._platform == "ios":
                return await self._recall_ios(personality, limit)
            logger.warning(
                "recall: unknown platform %r — simulating success",
                self._platform,
            )
            items = self._store.get(personality, [])
            return [i.to_dict() for i in reversed(items[-limit:])]
        except Exception:
            logger.exception("recall failed")
            return []

    async def search(
        self,
        query: str,
        limit: int = 5,
        personality: str | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search over stored interactions using stub embeddings.

        Searches all personalities unless *personality* is specified.

        Args:
            query: Natural-language search query.
            limit: Maximum number of results to return (default 5).
            personality: Optional filter — ``"GURU"`` or ``"MAYA"``.

        Returns:
            List of interaction dicts ranked by similarity (best first),
            empty list on failure or no results.

        """
        if not query or not query.strip():
            logger.warning("search: empty query — returning empty list")
            return []

        if limit <= 0:
            logger.warning("search: limit must be > 0, got %d", limit)
            return []

        if personality is not None:
            personality = personality.upper()
            if personality not in PERSONALITIES:
                logger.warning("search: unknown personality %r (must be GURU or MAYA)", personality)
                return []

        logger.info(
            "search: query_len=%d limit=%d personality=%s platform=%s",
            len(query),
            limit,
            personality,
            self._platform,
        )

        try:
            if _is_desktop(self._platform):
                return await self._search_desktop(query, limit, personality)
            if self._platform == "android":
                return await self._search_android(query, limit, personality)
            if self._platform == "ios":
                return await self._search_ios(query, limit, personality)
            logger.warning(
                "search: unknown platform %r — simulating success",
                self._platform,
            )
            return self._semantic_search_in_memory(query, limit, personality)
        except Exception:
            logger.exception("search failed")
            return []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform(self) -> str:
        """Current platform identifier."""
        return self._platform

    @property
    def is_initialized(self) -> bool:
        """Whether the manager has been initialized."""
        return self._initialized

    def interaction_count(self, personality: str | None = None) -> int:
        """Return the number of stored interactions (from in-memory cache)."""
        if personality is not None:
            p = personality.upper()
            return len(self._store.get(p, []))
        return sum(len(v) for v in self._store.values())

    # ------------------------------------------------------------------
    # Desktop implementations (SQLite via aiosqlite — real persistence)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_db_path() -> Path:
        """Return the OS-appropriate path for the SQLite database."""
        if os.name == "nt":  # Windows
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        else:  # Linux / macOS
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        db_dir = base / "agent_guru"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "memory.db"

    async def _initialize_desktop(self) -> None:
        """Initialize desktop storage via aiosqlite (real SQLite persistence)."""
        if not _AIOSQLITE_AVAILABLE:
            logger.warning(
                "BUG-029: aiosqlite not installed — memory will be in-RAM only "
                "(install with: pip install aiosqlite). "
                "Conversation history will be lost on restart.",
            )
            return

        self._db_path = self._resolve_db_path()
        logger.info("Desktop: opening SQLite database at %s", self._db_path)

        self._db = await _aiosqlite.connect(str(self._db_path))
        # Enable WAL mode for concurrent readers
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                personality TEXT NOT NULL,
                user_message TEXT NOT NULL,
                ai_message   TEXT NOT NULL,
                timestamp    REAL NOT NULL
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_personality_ts "
            "ON interactions (personality, timestamp DESC)",
        )
        await self._db.commit()

        # Warm in-memory cache from the last 500 rows per personality
        for personality in PERSONALITIES:
            async with self._db.execute(
                "SELECT personality, user_message, ai_message, timestamp "
                "FROM interactions WHERE personality=? "
                "ORDER BY timestamp ASC "
                "LIMIT 500",
                (personality,),
            ) as cursor:
                rows = await cursor.fetchall()

            for row in rows:
                interaction = _Interaction(
                    personality=row[0],
                    user_message=row[1],
                    ai_message=row[2],
                    timestamp=row[3],
                )
                self._store[personality].append(interaction)

        total = sum(len(v) for v in self._store.values())
        logger.info("Desktop: loaded %d interactions from SQLite cache", total)

    async def _shutdown_desktop(self) -> None:
        """Shut down desktop storage and close the SQLite connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None
            logger.info("Desktop: SQLite connection closed (%s)", self._db_path)
        else:
            logger.info("Desktop: MemoryManager shut down (in-memory mode)")

    async def _store_desktop(self, interaction: _Interaction) -> bool:
        """Persist interaction to SQLite and update in-memory cache."""
        # Always update in-memory cache first (fast path)
        self._store[interaction.personality].append(interaction)

        if self._db is None:
            # aiosqlite unavailable — in-memory only
            return True

        await self._db.execute(
            "INSERT INTO interactions (personality, user_message, ai_message, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (
                interaction.personality,
                interaction.user_message,
                interaction.ai_message,
                interaction.timestamp,
            ),
        )
        await self._db.commit()
        return True

    async def _recall_desktop(self, personality: str, limit: int) -> list[dict[str, Any]]:
        """Recall the *limit* most-recent interactions from SQLite (or cache)."""
        if self._db is not None:
            async with self._db.execute(
                "SELECT personality, user_message, ai_message, timestamp "
                "FROM interactions WHERE personality=? "
                "ORDER BY timestamp DESC LIMIT ?",
                (personality, limit),
            ) as cursor:
                rows = await cursor.fetchall()
            return [
                {"personality": r[0], "user_message": r[1], "ai_message": r[2], "timestamp": r[3]}
                for r in rows
            ]

        # Fallback: serve from in-memory cache
        items = self._store.get(personality, [])
        return [i.to_dict() for i in reversed(items[-limit:])]

    async def _search_desktop(
        self,
        query: str,
        limit: int,
        personality: str | None,
    ) -> list[dict[str, Any]]:
        """Semantic search using stub embeddings against the in-memory cache."""
        # NOTE: real FTS would use SQLite FTS5 or a vector extension.
        # The stub embedding search runs in-memory (cache already warmed at init).
        return self._semantic_search_in_memory(query, limit, personality)

    # ------------------------------------------------------------------
    # Android implementations (SharedPreferences + SQLite via adb — simulated)
    # ------------------------------------------------------------------

    async def _initialize_android(self) -> None:
        """Initialize Android storage (SharedPreferences + SQLite via adb — simulated)."""
        logger.info(
            "Android: MemoryManager initializing SharedPreferences + SQLite via adb (simulated)",
        )
        # Simulated: adb shell am broadcast -a guru.memory.init
        await asyncio.sleep(0)

    async def _shutdown_android(self) -> None:
        """Shut down Android storage."""
        logger.info(
            "Android: MemoryManager shutting down SharedPreferences + SQLite via adb (simulated)",
        )
        await asyncio.sleep(0)

    async def _store_android(self, interaction: _Interaction) -> bool:
        """Store interaction on Android via adb (simulated)."""
        logger.info(
            "Android: storing interaction personality=%s via adb (simulated)",
            interaction.personality,
        )
        # Simulated: adb shell content insert --uri content://guru.memory/interactions ...
        self._store[interaction.personality].append(interaction)
        return True

    async def _recall_android(self, personality: str, limit: int) -> list[dict[str, Any]]:
        """Recall interactions on Android via adb (simulated)."""
        logger.info(
            "Android: recalling personality=%s limit=%d via adb (simulated)",
            personality,
            limit,
        )
        # Simulated: adb shell content query --uri content://guru.memory/interactions ...
        items = self._store.get(personality, [])
        return [i.to_dict() for i in reversed(items[-limit:])]

    async def _search_android(
        self,
        query: str,
        limit: int,
        personality: str | None,
    ) -> list[dict[str, Any]]:
        """Semantic search on Android (simulated)."""
        logger.info(
            "Android: semantic search query_len=%d limit=%d via adb (simulated)",
            len(query),
            limit,
        )
        return self._semantic_search_in_memory(query, limit, personality)

    # ------------------------------------------------------------------
    # iOS implementations (UserDefaults + Core Data via xcrun — simulated)
    # ------------------------------------------------------------------

    async def _initialize_ios(self) -> None:
        """Initialize iOS storage (UserDefaults + Core Data via xcrun — simulated)."""
        logger.info(
            "iOS: MemoryManager initializing UserDefaults + Core Data via xcrun simctl (simulated)",
        )
        # Simulated: xcrun simctl spawn booted defaults write guru.memory initialized 1
        await asyncio.sleep(0)

    async def _shutdown_ios(self) -> None:
        """Shut down iOS storage."""
        logger.info(
            "iOS: MemoryManager shutting down UserDefaults + Core Data via xcrun simctl (simulated)",
        )
        await asyncio.sleep(0)

    async def _store_ios(self, interaction: _Interaction) -> bool:
        """Store interaction on iOS via xcrun (simulated)."""
        logger.info(
            "iOS: storing interaction personality=%s via xcrun simctl (simulated)",
            interaction.personality,
        )
        # Simulated: xcrun simctl spawn booted defaults write guru.memory ...
        self._store[interaction.personality].append(interaction)
        return True

    async def _recall_ios(self, personality: str, limit: int) -> list[dict[str, Any]]:
        """Recall interactions on iOS via xcrun (simulated)."""
        logger.info(
            "iOS: recalling personality=%s limit=%d via xcrun simctl (simulated)",
            personality,
            limit,
        )
        # Simulated: xcrun simctl spawn booted defaults read guru.memory ...
        items = self._store.get(personality, [])
        return [i.to_dict() for i in reversed(items[-limit:])]

    async def _search_ios(
        self,
        query: str,
        limit: int,
        personality: str | None,
    ) -> list[dict[str, Any]]:
        """Semantic search on iOS (simulated)."""
        logger.info(
            "iOS: semantic search query_len=%d limit=%d via xcrun simctl (simulated)",
            len(query),
            limit,
        )
        return self._semantic_search_in_memory(query, limit, personality)

    # ------------------------------------------------------------------
    # Shared semantic search (in-memory, stub embeddings)
    # ------------------------------------------------------------------

    def _semantic_search_in_memory(
        self,
        query: str,
        limit: int,
        personality: str | None,
    ) -> list[dict[str, Any]]:
        """Rank stored interactions by cosine similarity to *query*.

        Uses stub character-frequency embeddings.  In production this would
        use a real sentence-transformer model.

        Time Complexity: O(n * d) where n = interactions, d = embedding dim (26)
        Space Complexity: O(n) for scored list

        Args:
            query: Search query string.
            limit: Maximum results to return.
            personality: Optional personality filter.

        Returns:
            List of interaction dicts ranked by similarity (best first).

        """
        query_emb = _stub_embed(query)

        candidates: list[_Interaction] = []
        if personality is not None:
            candidates = list(self._store.get(personality, []))
        else:
            for items in self._store.values():
                candidates.extend(items)

        if not candidates:
            return []

        scored = [
            (interaction, _cosine_similarity(query_emb, interaction.embedding))
            for interaction in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [item.to_dict() for item, _ in scored[:limit]]
