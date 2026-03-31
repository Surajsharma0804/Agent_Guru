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
import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from Agent_Guru.memory.config import MemoryConfig

from Agent_Guru.platform.platform_detector import PlatformDetector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported personalities
# ---------------------------------------------------------------------------

PERSONALITIES = ("GURU", "MAYA")

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Thin wrapper — delegates to canonical PlatformDetector."""
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

    __slots__ = ("personality", "user_message", "ai_message", "timestamp", "embedding")

    def __init__(
        self,
        personality: str,
        user_message: str,
        ai_message: str,
        timestamp: Optional[float] = None,
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
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0.0 or mag_b == 0.0:
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
        config: Optional["MemoryConfig"] = None,
        platform_override: Optional[str] = None,
    ) -> None:
        """Create the memory manager.

        Args:
            config: Optional MemoryConfig instance (accepted but not required
                for the in-memory/simulated backend used on all platforms).
                Stored for future use by persistence backends.
            platform_override: Force a specific platform string (for testing).
                When ``None`` the platform is auto-detected.
        """
        self._config: Optional["MemoryConfig"] = config  # stored for future persistence backend use
        self._platform: str = platform_override or _detect_platform()
        self._initialized: bool = False

        # In-memory store: personality → list of _Interaction
        self._store: dict[str, list[_Interaction]] = {p: [] for p in PERSONALITIES}

        logger.info(
            "MemoryManager created — platform=%s", self._platform
        )

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
            logger.info(
                "MemoryManager initialized — platform=%s", self._platform
            )
            return True
        except Exception as exc:
            logger.error("MemoryManager.initialize failed: %s", exc)
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
        except Exception as exc:
            logger.error("MemoryManager.shutdown failed: %s", exc)
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

        if not user_message and not ai_message:
            logger.warning("store_interaction: both messages are empty — skipping")
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
            elif self._platform == "android":
                return await self._store_android(interaction)
            elif self._platform == "ios":
                return await self._store_ios(interaction)
            else:
                logger.warning(
                    "store_interaction: unknown platform %r — simulating success",
                    self._platform,
                )
                self._store[personality].append(interaction)
                return True
        except Exception as exc:
            logger.error("store_interaction failed: %s", exc)
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
            logger.warning(
                "recall: unknown personality %r (must be GURU or MAYA)", personality
            )
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
            elif self._platform == "android":
                return await self._recall_android(personality, limit)
            elif self._platform == "ios":
                return await self._recall_ios(personality, limit)
            else:
                logger.warning(
                    "recall: unknown platform %r — simulating success",
                    self._platform,
                )
                items = self._store.get(personality, [])
                return [i.to_dict() for i in reversed(items[-limit:])]
        except Exception as exc:
            logger.error("recall failed: %s", exc)
            return []

    async def search(
        self,
        query: str,
        limit: int = 5,
        personality: Optional[str] = None,
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
                logger.warning(
                    "search: unknown personality %r (must be GURU or MAYA)", personality
                )
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
            elif self._platform == "android":
                return await self._search_android(query, limit, personality)
            elif self._platform == "ios":
                return await self._search_ios(query, limit, personality)
            else:
                logger.warning(
                    "search: unknown platform %r — simulating success",
                    self._platform,
                )
                return self._semantic_search_in_memory(query, limit, personality)
        except Exception as exc:
            logger.error("search failed: %s", exc)
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

    def interaction_count(self, personality: Optional[str] = None) -> int:
        """Return the number of stored interactions.

        Args:
            personality: Optional filter.  When ``None`` returns total count.

        Returns:
            Number of stored interactions.
        """
        if personality is not None:
            p = personality.upper()
            return len(self._store.get(p, []))
        return sum(len(v) for v in self._store.values())

    # ------------------------------------------------------------------
    # Desktop implementations (SQLite via aiosqlite — simulated in-memory)
    # ------------------------------------------------------------------

    async def _initialize_desktop(self) -> None:
        """Initialize desktop storage (SQLite — simulated in-memory)."""
        logger.info(
            "Desktop: MemoryManager initializing SQLite storage (simulated) "
            "platform=%s",
            self._platform,
        )
        # Simulated: would open aiosqlite connection and create tables
        # aiosqlite.connect("guru_memory.db") + CREATE TABLE IF NOT EXISTS ...
        await asyncio.sleep(0)  # yield to event loop

    async def _shutdown_desktop(self) -> None:
        """Shut down desktop storage."""
        logger.info(
            "Desktop: MemoryManager shutting down SQLite storage (simulated)"
        )
        await asyncio.sleep(0)

    async def _store_desktop(self, interaction: _Interaction) -> bool:
        """Store interaction on desktop via SQLite (simulated)."""
        logger.info(
            "Desktop: storing interaction personality=%s via SQLite (simulated)",
            interaction.personality,
        )
        # Simulated: INSERT INTO interactions (personality, user_msg, ai_msg, ts)
        self._store[interaction.personality].append(interaction)
        return True

    async def _recall_desktop(
        self, personality: str, limit: int
    ) -> list[dict[str, Any]]:
        """Recall interactions on desktop via SQLite (simulated)."""
        logger.info(
            "Desktop: recalling personality=%s limit=%d via SQLite (simulated)",
            personality,
            limit,
        )
        # Simulated: SELECT * FROM interactions WHERE personality=? ORDER BY ts DESC LIMIT ?
        items = self._store.get(personality, [])
        return [i.to_dict() for i in reversed(items[-limit:])]

    async def _search_desktop(
        self, query: str, limit: int, personality: Optional[str]
    ) -> list[dict[str, Any]]:
        """Semantic search on desktop (simulated stub embeddings)."""
        logger.info(
            "Desktop: semantic search query_len=%d limit=%d via SQLite (simulated)",
            len(query),
            limit,
        )
        return self._semantic_search_in_memory(query, limit, personality)

    # ------------------------------------------------------------------
    # Android implementations (SharedPreferences + SQLite via adb — simulated)
    # ------------------------------------------------------------------

    async def _initialize_android(self) -> None:
        """Initialize Android storage (SharedPreferences + SQLite via adb — simulated)."""
        logger.info(
            "Android: MemoryManager initializing SharedPreferences + SQLite "
            "via adb (simulated)"
        )
        # Simulated: adb shell am broadcast -a guru.memory.init
        await asyncio.sleep(0)

    async def _shutdown_android(self) -> None:
        """Shut down Android storage."""
        logger.info(
            "Android: MemoryManager shutting down SharedPreferences + SQLite "
            "via adb (simulated)"
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

    async def _recall_android(
        self, personality: str, limit: int
    ) -> list[dict[str, Any]]:
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
        self, query: str, limit: int, personality: Optional[str]
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
            "iOS: MemoryManager initializing UserDefaults + Core Data "
            "via xcrun simctl (simulated)"
        )
        # Simulated: xcrun simctl spawn booted defaults write guru.memory initialized 1
        await asyncio.sleep(0)

    async def _shutdown_ios(self) -> None:
        """Shut down iOS storage."""
        logger.info(
            "iOS: MemoryManager shutting down UserDefaults + Core Data "
            "via xcrun simctl (simulated)"
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

    async def _recall_ios(
        self, personality: str, limit: int
    ) -> list[dict[str, Any]]:
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
        self, query: str, limit: int, personality: Optional[str]
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
        personality: Optional[str],
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
