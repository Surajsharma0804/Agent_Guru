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
    - Returns True/False or list - never raises for normal failures
    - Per-personality conversation storage (GURU and MAYA)
    - Semantic search with real sentence-transformer embeddings when available
      (reuses Agent_Guru.reasoning.memory.embedding.EmbeddingGenerator, the
      all-MiniLM-L6-v2 model, instead of a second, separate embedding
      scheme).
      Falls back to a cheap 26-dim letter-frequency vector ONLY when
      sentence-transformers/torch aren't installed, so this module never
      hard-fails without them. See _embed_text() / _REAL_EMBEDDER_AVAILABLE.
    - platform_override parameter for testing
    - Desktop uses in-memory dict + aiosqlite persistence (embeddings are
      persisted alongside each row so they are computed once, not
      recomputed on every warm-cache load at startup)
    - Mobile platforms simulate storage (log + return True/value) - this is
      a known, explicitly-documented limitation (see store/recall/search
      docstrings below), not a claim that mobile persistence is real.

Performance Characteristics:
    - Time Complexity: O(1) store, O(n) recall/search over stored interactions
    - Space Complexity: O(n) where n = number of stored interactions
    - Latency: <100ms per operation on desktop (real embedding generation adds
      ~20-200ms to store_interaction() depending on CPU/GPU - see
      Agent_Guru/reasoning/memory/embedding.py's documented latency budget)

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

# BUG-029: aiosqlite is a soft dependency - fall back gracefully if not installed
try:
    import aiosqlite as _aiosqlite

    _AIOSQLITE_AVAILABLE = True
except ImportError:
    _aiosqlite = None  # type: ignore[assignment]
    _AIOSQLITE_AVAILABLE = False

if TYPE_CHECKING:
    from collections.abc import Iterable

    from Agent_Guru.memory.config import MemoryConfig


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Real embeddings (soft dependency, same pattern as aiosqlite above)
# ---------------------------------------------------------------------------
# Reuses the existing, already-built EmbeddingGenerator (sentence-transformers
# all-MiniLM-L6-v2, 384-dim, GPU-aware) from reasoning/memory/embedding.py
# instead of writing a second embedding implementation. That module raises
# ImportError at construction time if sentence-transformers/torch aren't
# installed - this file catches that once, at first use, and falls back to
# the 26-dim letter-frequency stub rather than crashing memory storage/search.
_real_embedder: Any = None
_real_embedder_lock = threading.Lock()
_REAL_EMBEDDER_AVAILABLE: bool | None = None  # None = not yet probed
_logged_stub_fallback = False


def _get_real_embedder() -> Any:
    """Return a process-wide EmbeddingGenerator singleton, or None if unavailable.

    Loading a sentence-transformers model is expensive (real disk/GPU I/O), so
    this is done at most once per process and cached - never per-interaction.
    Thread-safe (double-checked locking) since callers reach this via
    loop.run_in_executor from multiple coroutines.
    """
    global _real_embedder, _REAL_EMBEDDER_AVAILABLE  # noqa: PLW0603
    if _REAL_EMBEDDER_AVAILABLE is False:
        return None
    if _real_embedder is not None:
        return _real_embedder
    with _real_embedder_lock:
        if _real_embedder is not None:
            return _real_embedder
        if _REAL_EMBEDDER_AVAILABLE is False:
            return None
        try:
            from Agent_Guru.reasoning.memory.embedding import EmbeddingGenerator

            _real_embedder = EmbeddingGenerator()
            _REAL_EMBEDDER_AVAILABLE = True
            logger.info("MemoryManager: using real sentence-transformer embeddings")
        except Exception as exc:  # ImportError (not installed) or model load failure
            _REAL_EMBEDDER_AVAILABLE = False
            global _logged_stub_fallback  # noqa: PLW0603
            if not _logged_stub_fallback:
                logger.warning(
                    "MemoryManager: real embeddings unavailable (%s) - falling back to "
                    "a 26-dim letter-frequency stub. Semantic recall quality will be "
                    "significantly degraded until sentence-transformers + torch are "
                    "installed. Install with: pip install sentence-transformers torch",
                    exc,
                )
                _logged_stub_fallback = True
        return _real_embedder

# ---------------------------------------------------------------------------
# Supported personalities
# ---------------------------------------------------------------------------

PERSONALITIES = ("GURU", "MAYA")

# ---------------------------------------------------------------------------
# What search() returns
# ---------------------------------------------------------------------------

#: search() returns an interaction only if it is at least this similar to the
#: query. It used to return the nearest `limit` whatever their score, so every
#: voice turn was handed 5 memories: a question about the Prime Minister came
#: with "my doctor says my blood pressure is too high" attached (0.09), which
#: also put a different 600-token block into every prompt. Calibrated with
#: all-MiniLM-L6-v2, query against stored "user message + reply": memories
#: about the asked-about thing scored 0.31 to 0.56 (hike snack -> peanut
#: allergy 0.31, sister's wedding gift -> her wedding 0.35, IPL match ->
#: favourite team 0.36), memories unrelated to it at most 0.20. A memory
#: related only by inference (more salt -> high blood pressure, 0.18) scores
#: like an unrelated one and is not returned; the nearest-5 rule returned it
#: only by accident, along with the unrelated ones.
RELEVANT_SIMILARITY = 0.25

#: A memory at least this similar to a turn the conversation already holds
#: says nothing new and is not returned. Same calibration: the same question
#: answered in different words scored 0.74 to 0.94 and the same fact
#: paraphrased 0.89, while a different fact about the same person scored 0.56
#: and a different question on the same topic 0.63.
REDUNDANT_SIMILARITY = 0.70

#: Length of the _stub_embed() fallback vector. Both thresholds above hold
#: only for the real embedder: letter-frequency vectors put any two English
#: texts at 0.75 to 0.79, so with them the relevance cutoff would pass
#: everything and the repeat check would drop everything. A stub-embedded
#: query is therefore ranked as before, without either cutoff.
_STUB_EMBEDDING_DIM = 26

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Thin wrapper - delegates to canonical PlatformDetector.

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
        embedding: list[float] | None = None,
    ) -> None:
        self.personality = personality.upper()
        self.user_message = user_message
        self.ai_message = ai_message
        self.timestamp: float = timestamp if timestamp is not None else time.time()
        # embedding is passed in when loading a row that already has one
        # persisted (see _initialize_desktop's warm-cache load) so it is
        # computed once at write time, never recomputed on every startup.
        # Only compute fresh here for a brand-new interaction.
        self.embedding: list[float] = (
            embedding if embedding is not None else _embed_text(user_message + " " + ai_message)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "personality": self.personality,
            "user_message": self.user_message,
            "ai_message": self.ai_message,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------


def _stub_embed(text: str) -> list[float]:
    """Return a fallback embedding vector (character frequency, 26-dim).

    Used ONLY when the real embedder (_get_real_embedder(), sentence-
    transformers all-MiniLM-L6-v2) is unavailable, or for legacy rows loaded
    from a database written before this file used real embeddings (see
    _initialize_desktop - recomputing a real embedding for every legacy row
    at every startup would turn a fast warm-cache load into a multi-minute
    stall on CPU-only machines, so legacy rows deliberately keep this cheap
    fallback rather than being silently upgraded on load).

    This vector captures letter-frequency, not meaning - cosine similarity
    against it gives an extremely rough signal, not real semantic recall.

    Time Complexity: O(n) where n = len(text)
    Space Complexity: O(1) - fixed 26-element output
    """
    counts = [0.0] * _STUB_EMBEDDING_DIM
    for ch in text.lower():
        if "a" <= ch <= "z":
            counts[ord(ch) - ord("a")] += 1.0
    total = sum(counts) or 1.0
    return [c / total for c in counts]


def _embed_text(text: str) -> list[float]:
    """Return an embedding for *text*: real sentence-transformer if available.

    Dispatches to the shared EmbeddingGenerator singleton (384-dim,
    meaning-aware) when sentence-transformers/torch are installed, otherwise
    falls back to the 26-dim letter-frequency stub. Never raises - a failure
    in the real embedder degrades to the stub rather than breaking storage.

    This is a BLOCKING, synchronous call - real sentence-transformer
    inference takes ~20-200ms on CPU (see module docstring). Callers from
    async code must go through _embed_text_async() below rather than
    calling this directly, or they will stall the event loop for the
    duration of every embedding computation.

    Time Complexity: O(n) where n = len(text) either way.
    Space Complexity: O(1) - fixed-size output (384-dim real, 26-dim stub).
    """
    embedder = _get_real_embedder()
    if embedder is not None:
        try:
            return embedder.generate(text)
        except Exception:
            logger.debug("Real embedding generation failed, falling back to stub", exc_info=True)
    return _stub_embed(text)


async def _embed_text_async(text: str) -> list[float]:
    """Async wrapper around _embed_text() - runs it in a thread-pool executor.

    BUG FIX (Round 19): _get_real_embedder()'s own docstring already
    documented "callers reach this via loop.run_in_executor from multiple
    coroutines" as the intended design, but nothing in this file actually
    did that - _Interaction.__init__ (via store_interaction) and
    _semantic_search_in_memory (via search) both called _embed_text()
    directly and synchronously from async methods. Real embedding
    generation is documented elsewhere in this file as costing ~20-200ms
    on CPU; run synchronously on the event loop, that stalls EVERY other
    concurrent coroutine (other store/recall/search calls, IPC, voice
    pipeline callbacks) for the duration - exactly the latency regression
    the project's async-scheduling performance standard calls out. This
    wrapper, used by every async call site below, is what actually makes
    the double-checked locking in _get_real_embedder() meaningful (it now
    really can be entered from multiple executor threads concurrently).

    Time Complexity: same as _embed_text() (O(n) in text length), plus a
    thread-pool dispatch.
    Space Complexity: O(1).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _embed_text, text)


def _vector_magnitude(v: list[float]) -> float:
    """Euclidean norm of *v*. Split out so a query vector compared against
    thousands of candidates has its magnitude computed once, not once per
    candidate (see _cosine_similarity's `a_magnitude` argument)."""
    return sum(x * x for x in v) ** 0.5


def _cosine_similarity(
    a: list[float],
    b: list[float],
    a_magnitude: float | None = None,
) -> float:
    """Return cosine similarity between two vectors of the SAME dimension.

    Returns 0.0 if either vector is all-zeros, OR if the two vectors have
    different lengths. The mismatched-length case matters in practice: it
    happens whenever a query is embedded in "real" (384-dim) mode while a
    stored interaction only has a "stub" (26-dim) fallback embedding (e.g. a
    legacy row from before real embeddings were wired in, or the real
    embedder failed to load for just one of the two calls). zip() would
    previously truncate silently to the shorter vector instead of raising -
    producing a meaningless similarity score rather than an error, which is
    worse than just excluding the candidate. Now it's treated as "not a
    match" (0.0) instead of silently comparing incompatible embedding spaces.

    PERFORMANCE: this made THREE separate passes over the vectors (one
    generator-sum each for the dot product and the two magnitudes), and
    recomputed the *query* magnitude once per candidate even though it is
    identical for every comparison in a search. Ranking N stored interactions
    therefore cost 3*N*d multiply-adds where N*d + d is sufficient. The maths
    is unchanged -- the loop below computes exactly the same three sums, in
    one pass -- and `a_magnitude` lets a caller that already knows |a| skip
    recomputing it. Same result, same guard conditions.

    Args:
        a: First vector (the query, in search use).
        b: Second vector (a candidate).
        a_magnitude: Precomputed |a| from _vector_magnitude(), when the caller
            is comparing one vector against many.

    Time Complexity: O(d) where d = len(a), one pass instead of three.
    Space Complexity: O(1)
    """
    if len(a) != len(b):
        return 0.0

    dot = 0.0
    mag_b_sq = 0.0
    if a_magnitude is None:
        mag_a_sq = 0.0
        for x, y in zip(a, b, strict=True):
            dot += x * y
            mag_a_sq += x * x
            mag_b_sq += y * y
        mag_a = mag_a_sq**0.5
    else:
        mag_a = a_magnitude
        for x, y in zip(a, b, strict=True):
            dot += x * y
            mag_b_sq += y * y

    mag_b = mag_b_sq**0.5
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

        logger.info("MemoryManager created - platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """Initialize the memory manager and underlying storage.

        Idempotent - safe to call multiple times.

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
                    "MemoryManager.initialize: unknown platform %r - simulating success",
                    self._platform,
                )

            self._initialized = True
            logger.info("MemoryManager initialized - platform=%s", self._platform)
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
                    "MemoryManager.shutdown: unknown platform %r - simulating success",
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

        # BUG-010: strip whitespace before checking - reject whitespace-only messages
        if not user_message.strip() or not ai_message.strip():
            logger.warning(
                "store_interaction: requires non-empty user_message AND ai_message - skipping "
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
            # BUG FIX (Round 19): compute the embedding via the async,
            # executor-backed wrapper instead of letting _Interaction's
            # constructor call the (blocking) real embedder synchronously
            # on the event loop - see _embed_text_async()'s docstring.
            embedding = await _embed_text_async(user_message + " " + ai_message)
            interaction = _Interaction(
                personality=personality,
                user_message=user_message,
                ai_message=ai_message,
                embedding=embedding,
            )

            if _is_desktop(self._platform):
                return await self._store_desktop(interaction)
            if self._platform == "android":
                return await self._store_android(interaction)
            if self._platform == "ios":
                return await self._store_ios(interaction)
            logger.warning(
                "store_interaction: unknown platform %r - simulating success",
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
                "recall: unknown platform %r - simulating success",
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
        *,
        known: Iterable[tuple[str, str]] = (),
        min_similarity: float = RELEVANT_SIMILARITY,
    ) -> list[dict[str, Any]]:
        """Semantic search over stored interactions.

        Searches all personalities unless *personality* is specified.
        Returns at most *limit* interactions, only those relevant to the
        query and new to the conversation (see RELEVANT_SIMILARITY and
        REDUNDANT_SIMILARITY); fewer, or none, is a normal result.

        Args:
            query: Natural-language search query.
            limit: Maximum number of results to return (default 5).
            personality: Optional filter - ``"GURU"`` or ``"MAYA"``.
            known: ``(user_message, ai_message)`` turns the caller already
                has in front of the model. They are not returned, and
                neither is anything that repeats them.
            min_similarity: Lowest similarity to the query that is returned.

        Returns:
            List of interaction dicts ranked by similarity (best first),
            empty list on failure or no results.

        """
        if not query or not query.strip():
            logger.warning("search: empty query - returning empty list")
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
            known = list(known)
            if _is_desktop(self._platform):
                return await self._search_desktop(query, limit, personality, known, min_similarity)
            if self._platform == "android":
                return await self._search_android(query, limit, personality, known, min_similarity)
            if self._platform == "ios":
                return await self._search_ios(query, limit, personality, known, min_similarity)
            logger.warning(
                "search: unknown platform %r - simulating success",
                self._platform,
            )
            query_emb = await _embed_text_async(query)
            return self._semantic_search_in_memory(query_emb, limit, personality, known, min_similarity)
        except Exception:
            logger.exception("search failed")
            return []

    # ------------------------------------------------------------------
    # P2-72: Conversation summary compression
    # ------------------------------------------------------------------

    @staticmethod
    def compress_history(
        history: list[dict[str, str]],
        max_verbatim: int = 6,
        threshold: int = 20,
    ) -> list[dict[str, str]]:
        """Compress long conversation history to prevent context noise.

        When history exceeds ``threshold`` messages, older messages are
        compressed into a single summary message while preserving the
        most recent ``max_verbatim`` messages verbatim.

        This prevents "memory collapse" - where the LLM becomes confused
        by too many low-relevance historical messages.

        Args:
            history: List of ``{"role": ..., "content": ...}`` dicts.
            max_verbatim: Number of recent messages to keep verbatim.
            threshold: Minimum history length before compression kicks in.

        Returns:
            Compressed history list.

        """
        if len(history) <= threshold:
            return history

        # Split into older (to compress) and recent (to keep).
        # BUG FIX (Round 19): `history[:-max_verbatim]` / `history[-max_verbatim:]`
        # silently misbehaved at both edges of max_verbatim's valid range:
        #   - max_verbatim == 0: Python treats -0 as 0, so `[:-0]` is `[:0]`
        #     (empty) and `[-0:]` is `[0:]` (everything) - the EXACT INVERSE
        #     of "keep 0 messages verbatim, compress everything".
        #   - max_verbatim >= len(history): `older` becomes empty but the
        #     code still unconditionally built and prepended a
        #     "[Compressed conversation history - 0 earlier messages
        #     summarized]" system message, making compression add a
        #     useless message instead of being a safe no-op.
        # Both are handled explicitly below rather than relying on slice
        # arithmetic to do the right thing at the boundaries.
        if max_verbatim > 0:
            older = history[:-max_verbatim]
            recent = history[-max_verbatim:]
        else:
            older = list(history)
            recent = []

        if not older:
            return recent

        # Build summary of older messages
        summary_parts = []
        for msg in older:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]  # Truncate for summary
            summary_parts.append(f"[{role}] {content}")

        summary_text = (
            "[Compressed conversation history - "
            f"{len(older)} earlier messages summarized]\n"
            + "\n".join(summary_parts[-10:])  # Keep last 10 summaries
        )

        compressed = [{"role": "system", "content": summary_text}]
        compressed.extend(recent)
        return compressed

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
    # Desktop implementations (SQLite via aiosqlite - real persistence)
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
                "BUG-029: aiosqlite not installed - memory will be in-RAM only "
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
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                personality TEXT NOT NULL,
                user_message TEXT NOT NULL,
                ai_message   TEXT NOT NULL,
                timestamp    REAL NOT NULL,
                embedding    TEXT
            )
        """)
        await self._migrate_add_embedding_column()
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_personality_ts "
            "ON interactions (personality, timestamp DESC)",
        )
        await self._db.commit()

        # Warm in-memory cache from the last 500 rows per personality.
        # embedding is persisted (see _store_desktop) so it is computed once,
        # at write time - NOT recomputed here on every startup. A row written
        # before this column existed has embedding=NULL; for those legacy
        # rows we explicitly use the cheap stub (never the real embedder) so
        # a database with hundreds of old rows can't turn a warm-cache load
        # into a multi-minute startup stall. See _stub_embed()'s docstring.
        for personality in PERSONALITIES:
            async with self._db.execute(
                "SELECT personality, user_message, ai_message, timestamp, embedding "
                "FROM interactions WHERE personality=? "
                "ORDER BY timestamp ASC "
                "LIMIT 500",
                (personality,),
            ) as cursor:
                rows = await cursor.fetchall()

            for row in rows:
                stored_embedding_json = row[4]
                if stored_embedding_json:
                    try:
                        embedding = json.loads(stored_embedding_json)
                    except (ValueError, TypeError):
                        logger.debug("Corrupt stored embedding, recomputing as stub")
                        embedding = _stub_embed(row[1] + " " + row[2])
                else:
                    embedding = _stub_embed(row[1] + " " + row[2])
                interaction = _Interaction(
                    personality=row[0],
                    user_message=row[1],
                    ai_message=row[2],
                    timestamp=row[3],
                    embedding=embedding,
                )
                self._store[personality].append(interaction)

        total = sum(len(v) for v in self._store.values())
        logger.info("Desktop: loaded %d interactions from SQLite cache", total)

    async def _migrate_add_embedding_column(self) -> None:
        """Add the embedding column to a pre-existing database that lacks it.

        SQLite has no 'ADD COLUMN IF NOT EXISTS', so this checks
        PRAGMA table_info first. Safe to call every startup - a no-op once
        the column exists. New databases already get the column from the
        CREATE TABLE above; this only matters for databases created before
        real-embedding persistence was added.
        """
        async with self._db.execute("PRAGMA table_info(interactions)") as cursor:
            columns = await cursor.fetchall()
        column_names = {col[1] for col in columns}
        if "embedding" not in column_names:
            logger.info("Migrating interactions table: adding embedding column")
            await self._db.execute("ALTER TABLE interactions ADD COLUMN embedding TEXT")
            await self._db.commit()

    async def _shutdown_desktop(self) -> None:
        """Shut down desktop storage and close the SQLite connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None
            logger.info("Desktop: SQLite connection closed (%s)", self._db_path)
        else:
            logger.info("Desktop: MemoryManager shut down (in-memory mode)")

    async def _store_desktop(self, interaction: _Interaction) -> bool:
        """Persist interaction to SQLite and update in-memory cache.

        BUG FIX (Round 19): this used to append to the in-memory cache
        BEFORE attempting the SQLite insert. If the insert then raised
        (disk full, corruption, a lock held past busy_timeout...), the
        interaction stayed in the cache anyway - so search() and
        interaction_count() (which read the cache) would report an
        interaction that recall() (which reads SQLite directly when
        available) would never show, and that would silently vanish on
        the next restart despite search() having found it in the
        meantime. The cache is now only updated after the durable write
        actually succeeds, so all read paths stay consistent with what
        was really persisted.
        """
        if self._db is None:
            # aiosqlite unavailable - in-memory only, nothing to fail against
            self._store[interaction.personality].append(interaction)
            return True

        await self._db.execute(
            "INSERT INTO interactions "
            "(personality, user_message, ai_message, timestamp, embedding) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                interaction.personality,
                interaction.user_message,
                interaction.ai_message,
                interaction.timestamp,
                json.dumps(interaction.embedding),
            ),
        )
        await self._db.commit()
        self._store[interaction.personality].append(interaction)
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
        known: list[tuple[str, str]],
        min_similarity: float,
    ) -> list[dict[str, Any]]:
        """Semantic search against the in-memory cache (real or stub embeddings)."""
        # NOTE: real FTS would use SQLite FTS5 or a vector extension.
        # The embedding search runs in-memory (cache already warmed at init).
        # BUG FIX (Round 19): the query is now embedded with the same
        # dispatcher (_embed_text_async, real embedder when available) used
        # to embed stored interactions - see _semantic_search_in_memory()'s
        # docstring for why embedding the query with the cheap stub while
        # interactions carry real 384-dim embeddings made search a no-op.
        query_emb = await _embed_text_async(query)
        return self._semantic_search_in_memory(query_emb, limit, personality, known, min_similarity)

    # ------------------------------------------------------------------
    # Android implementations (SharedPreferences + SQLite via adb - simulated)
    # ------------------------------------------------------------------

    async def _initialize_android(self) -> None:
        """Initialize Android storage (SharedPreferences + SQLite via adb - simulated)."""
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
        known: list[tuple[str, str]],
        min_similarity: float,
    ) -> list[dict[str, Any]]:
        """Semantic search on Android (simulated)."""
        logger.info(
            "Android: semantic search query_len=%d limit=%d via adb (simulated)",
            len(query),
            limit,
        )
        query_emb = await _embed_text_async(query)
        return self._semantic_search_in_memory(query_emb, limit, personality, known, min_similarity)

    # ------------------------------------------------------------------
    # iOS implementations (UserDefaults + Core Data via xcrun - simulated)
    # ------------------------------------------------------------------

    async def _initialize_ios(self) -> None:
        """Initialize iOS storage (UserDefaults + Core Data via xcrun - simulated)."""
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
        known: list[tuple[str, str]],
        min_similarity: float,
    ) -> list[dict[str, Any]]:
        """Semantic search on iOS (simulated)."""
        logger.info(
            "iOS: semantic search query_len=%d limit=%d via xcrun simctl (simulated)",
            len(query),
            limit,
        )
        query_emb = await _embed_text_async(query)
        return self._semantic_search_in_memory(query_emb, limit, personality, known, min_similarity)

    # ------------------------------------------------------------------
    # Shared semantic search (in-memory, stub embeddings)
    # ------------------------------------------------------------------

    def _semantic_search_in_memory(
        self,
        query_emb: list[float],
        limit: int,
        personality: str | None,
        known: list[tuple[str, str]] = [],  # noqa: B006 - read only, never mutated
        min_similarity: float = RELEVANT_SIMILARITY,
    ) -> list[dict[str, Any]]:
        """Rank stored interactions by cosine similarity to a pre-embedded query.

        Uses the real sentence-transformer embedding when available (same
        model used to embed stored interactions), falling back to the
        26-dim letter-frequency stub only when unavailable for both.

        BUG FIX (Round 19): this used to compute `query_emb = _stub_embed(query)`
        internally, UNCONDITIONALLY - even when stored interactions carry
        real 384-dim embeddings (the normal case whenever sentence-
        transformers/torch are installed, i.e. the intended production
        configuration this module's own docstring advertises). Since
        _cosine_similarity() correctly returns 0.0 for any dimension
        mismatch (26 vs 384) rather than silently truncating, EVERY
        candidate scored exactly 0.0 against a stub-embedded query whenever
        real embeddings were in use - making "semantic search" silently
        degrade to an unranked, effectively-random ordering (Python's
        stable sort just preserves insertion order for a set of all-equal
        scores) instead of doing what its name says. Callers now embed the
        query with the same dispatcher used for storage (_embed_text_async,
        real embedder when available) and pass the result in here, so
        query and candidate embeddings are always in the same space.

        Time Complexity: O(n * d + r log r + k * c * d) where n =
        interactions, d = embedding dim (26 for the stub, 384 for the real
        embedder), r = candidates above min_similarity (a handful), k =
        limit and c = known turns. It once was O(n * d * 3 + n log n): every
        candidate recomputed the query's magnitude, and the whole candidate
        list was sorted to take the top few.
        Space Complexity: O(r + c).

        Args:
            query_emb: Pre-computed embedding of the search query, produced
                by the same embedding function used for stored interactions
                (see _embed_text_async()).
            limit: Maximum results to return.
            personality: Optional personality filter.
            known: Turns already in the conversation (see search()).
            min_similarity: Lowest similarity to the query returned.

        Returns:
            List of interaction dicts ranked by similarity (best first).

        The conversation's own turns are stored here as well, and were
        returned as "memories" of themselves: in a 10-turn session every
        recall carried the session's earlier turns, word for word, beside
        the same turns in the chat history. They are matched by their exact
        text, which costs a set lookup per candidate, and their stored
        embeddings are reused for the repeat check, which therefore embeds
        nothing new and compares only the few results against them.

        """
        candidates: list[_Interaction] = []
        if personality is not None:
            candidates = list(self._store.get(personality, []))
        else:
            for items in self._store.values():
                candidates.extend(items)

        if not candidates:
            return []

        if limit <= 0:
            return []

        known_pairs = set(known)
        known_embeddings: list[list[float]] = []
        if known_pairs:
            fresh: list[_Interaction] = []
            for item in candidates:
                if (item.user_message, item.ai_message) in known_pairs:
                    known_embeddings.append(item.embedding)
                else:
                    fresh.append(item)
            candidates = fresh

        # The query magnitude is identical for every comparison, so compute it
        # once here instead of once per candidate inside _cosine_similarity.
        query_mag = _vector_magnitude(query_emb)
        if len(query_emb) == _STUB_EMBEDDING_DIM:
            min_similarity, redundant_similarity = float("-inf"), float("inf")
        else:
            redundant_similarity = REDUNDANT_SIMILARITY

        # Only the candidates above min_similarity are ranked, normally a
        # handful, so sorting them costs nothing next to scoring all n. They
        # are walked best first until `limit` new ones are found: taking the
        # top `limit` first and then dropping repeats would return fewer than
        # it could, or none when many stored copies of one known turn (the
        # same question asked often) fill the top places.
        relevant = sorted(
            (
                (score, n, item)
                for n, item in enumerate(candidates)
                if (score := _cosine_similarity(query_emb, item.embedding, query_mag)) >= min_similarity
            ),
            key=lambda t: (-t[0], t[1]),
        )
        results: list[dict[str, Any]] = []
        for _, _, item in relevant:
            if len(results) == limit:
                break
            if any(
                _cosine_similarity(item.embedding, seen) >= redundant_similarity
                for seen in known_embeddings
            ):
                continue
            results.append(item.to_dict())
        return results
