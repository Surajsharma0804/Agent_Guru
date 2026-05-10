"""Intent Detection Caching System.

Implements LRU cache with TTL for intent detection results to reduce latency.
Caches identical inputs with context-aware invalidation.

Performance Target: <1ms cache lookup overhead
Cache Hit Rate Target: >60%
TTL: 5 minutes (300 seconds)

Author: Kiro AI
Date: 2026-02-22
Version: 1.0.0
"""

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from Agent_Guru.reasoning.models.intent import Intent


@dataclass
class CachedIntent:
    """Cached intent detection result.

    Attributes:
        intent: Detected intent object
        cache_key: Cache key (hash of input + context)
        created_at: When entry was created
        last_accessed: When entry was last accessed
        access_count: Number of times accessed
        context_hash: Hash of context for invalidation

    """

    intent: Intent
    cache_key: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    context_hash: str = ""

    def update_access(self) -> None:
        """Update access statistics."""
        self.last_accessed = datetime.now(tz=UTC)
        self.access_count += 1


@dataclass
class IntentCacheStats:
    """Intent cache statistics.

    Attributes:
        total_requests: Total cache lookup requests
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        context_invalidations: Number of context-based invalidations
        ttl_expirations: Number of TTL-based expirations
        evictions: Number of LRU evictions
        last_reset: When stats were last reset

    """

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    context_invalidations: int = 0
    ttl_expirations: int = 0
    evictions: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def record_hit(self) -> None:
        """Record cache hit."""
        self.total_requests += 1
        self.cache_hits += 1

    def record_miss(self) -> None:
        """Record cache miss."""
        self.total_requests += 1
        self.cache_misses += 1

    def record_context_invalidation(self) -> None:
        """Record context-based invalidation."""
        self.context_invalidations += 1

    def record_ttl_expiration(self) -> None:
        """Record TTL expiration."""
        self.ttl_expirations += 1

    def record_eviction(self) -> None:
        """Record LRU eviction."""
        self.evictions += 1

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate.

        Returns:
            Hit rate as percentage (0.0-100.0)

        """
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with all statistics

        """
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate_percent": self.get_hit_rate(),
            "context_invalidations": self.context_invalidations,
            "ttl_expirations": self.ttl_expirations,
            "evictions": self.evictions,
            "last_reset": self.last_reset.isoformat(),
        }


class IntentDetectionCache:
    """LRU cache for intent detection results with context-aware invalidation.

    Caches intent detection results for identical inputs to reduce latency.
    Implements TTL-based expiration and context-aware invalidation.

    Time Complexity: O(1) for get/set operations
    Space Complexity: O(n) where n = max_size

    Example:
        >>> cache = IntentDetectionCache(max_size=10000, ttl_seconds=300)
        >>> cache.set("set timer for 5 minutes", context, intent)
        >>> cached_intent = cache.get("set timer for 5 minutes", context)
        >>> if cached_intent:
        ...     print(f"Cache hit! Intent: {cached_intent.intent_type}")

    """

    def __init__(
        self,
        max_size: int = 10000,
        ttl_seconds: float = 300.0,  # 5 minutes
    ) -> None:
        """Initialize intent detection cache.

        Args:
            max_size: Maximum number of cached intents (LRU eviction)
            ttl_seconds: Time-to-live for cache entries in seconds

        Raises:
            ValueError: If max_size <= 0 or ttl_seconds <= 0

        """
        if max_size <= 0:
            msg = f"max_size must be positive, got {max_size}"
            raise ValueError(msg)
        if ttl_seconds <= 0:
            msg = f"ttl_seconds must be positive, got {ttl_seconds}"
            raise ValueError(msg)

        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.ttl_delta = timedelta(seconds=ttl_seconds)
        self._cache: OrderedDict[str, CachedIntent] = OrderedDict()
        self.stats = IntentCacheStats()

    def _generate_cache_key(self, text: str, context: dict[str, Any] | None = None) -> str:
        """Generate cache key from input text and context.

        Uses SHA256 hash of text + context for consistent keys.

        Args:
            text: Input text (normalized)
            context: Optional conversation context

        Returns:
            Cache key string (SHA256 hash)

        Time Complexity: O(n) where n = text length + context size

        """
        # Normalize text (lowercase, strip whitespace)
        normalized_text = text.lower().strip()

        # Create key string with context
        if context:
            # Handle both dict and string context (for backward compatibility)
            if isinstance(context, dict):
                # Sort context keys for consistent hashing
                context_str = str(sorted(context.items()))
            else:
                # If context is string (e.g., user_id), use it directly
                context_str = str(context)
            key_string = f"{normalized_text}:{context_str}"
        else:
            key_string = normalized_text

        return hashlib.sha256(key_string.encode()).hexdigest()

    def _generate_context_hash(self, context: dict[str, Any] | None = None) -> str:
        """Generate hash of context for invalidation tracking.

        Args:
            context: Optional conversation context

        Returns:
            Context hash string

        Time Complexity: O(n) where n = context size

        """
        if not context:
            return ""

        # Handle both dict and string context
        if isinstance(context, dict):
            # Sort context keys for consistent hashing
            context_str = str(sorted(context.items()))
        else:
            # If context is string, use it directly
            context_str = str(context)

        return hashlib.sha256(context_str.encode()).hexdigest()

    def _is_expired(self, entry: CachedIntent) -> bool:
        """Check if cache entry is expired based on TTL.

        Args:
            entry: Cached intent entry

        Returns:
            True if expired, False otherwise

        Time Complexity: O(1)

        """
        age = datetime.now(tz=UTC) - entry.created_at
        return age > self.ttl_delta

    def _evict_lru(self) -> None:
        """Evict least recently used entry.

        Time Complexity: O(1)
        """
        if self._cache:
            # OrderedDict maintains insertion order, oldest first
            self._cache.popitem(last=False)
            self.stats.record_eviction()

    def _evict_expired(self) -> None:
        """Evict all expired entries based on TTL.

        Time Complexity: O(n) where n = cache size
        """
        expired_keys = [key for key, entry in self._cache.items() if self._is_expired(entry)]

        for key in expired_keys:
            del self._cache[key]
            self.stats.record_ttl_expiration()

    def get(self, text: str, context: dict[str, Any] | None = None) -> Intent | None:
        """Get cached intent for input text and context.

        Args:
            text: Input text
            context: Optional conversation context

        Returns:
            Cached Intent if found and valid, None otherwise

        Time Complexity: O(1) average case

        """
        time.perf_counter()

        cache_key = self._generate_cache_key(text, context)

        # Check if entry exists
        if cache_key not in self._cache:
            self.stats.record_miss()
            return None

        entry = self._cache[cache_key]

        # Check if expired
        if self._is_expired(entry):
            del self._cache[cache_key]
            self.stats.record_miss()
            self.stats.record_ttl_expiration()
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)

        # Update access stats
        entry.update_access()

        # Record hit
        self.stats.record_hit()

        return entry.intent

    def set(
        self,
        text: str,
        context: dict[str, Any] | None,
        intent: Intent,
    ) -> None:
        """Set cached intent for input text and context.

        Args:
            text: Input text
            context: Optional conversation context
            intent: Intent to cache

        Time Complexity: O(1) amortized

        """
        cache_key = self._generate_cache_key(text, context)
        context_hash = self._generate_context_hash(context)

        # Evict expired entries first
        self._evict_expired()

        # Evict LRU if at capacity
        if len(self._cache) >= self.max_size and cache_key not in self._cache:
            self._evict_lru()

        # Create or update entry
        entry = CachedIntent(
            intent=intent,
            cache_key=cache_key,
            created_at=datetime.now(tz=UTC),
            last_accessed=datetime.now(tz=UTC),
            access_count=0,
            context_hash=context_hash,
        )

        self._cache[cache_key] = entry

    def invalidate_by_context(self, context: dict[str, Any]) -> int:
        """Invalidate all cache entries with matching context.

        This is called when conversation context changes significantly
        (e.g., new conversation, context reset).

        Args:
            context: Context to match for invalidation

        Returns:
            Number of entries invalidated

        Time Complexity: O(n) where n = cache size

        """
        context_hash = self._generate_context_hash(context)

        # Find all entries with matching context
        keys_to_invalidate = [
            key for key, entry in self._cache.items() if entry.context_hash == context_hash
        ]

        # Remove entries
        for key in keys_to_invalidate:
            del self._cache[key]
            self.stats.record_context_invalidation()

        return len(keys_to_invalidate)

    def invalidate_all(self) -> None:
        """Invalidate all cache entries.

        Time Complexity: O(1)
        """
        count = len(self._cache)
        self._cache.clear()
        self.stats.context_invalidations += count

    def clear(self) -> None:
        """Clear all cached intents.

        Time Complexity: O(1)
        """
        self._cache.clear()

    def get_size(self) -> int:
        """Get current cache size.

        Returns:
            Number of cached entries

        Time Complexity: O(1)

        """
        return len(self._cache)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics

        """
        stats = self.stats.get_stats()
        stats["current_size"] = self.get_size()
        stats["max_size"] = self.max_size
        stats["utilization_percent"] = (self.get_size() / self.max_size) * 100
        stats["ttl_seconds"] = self.ttl_seconds
        return stats

    def reset_stats(self) -> None:
        """Reset cache statistics.

        Time Complexity: O(1)
        """
        self.stats = IntentCacheStats()

    def get_most_accessed(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most accessed cache entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of entry statistics

        Time Complexity: O(n log n) where n = cache size

        """
        sorted_entries = sorted(
            self._cache.values(),
            key=lambda e: e.access_count,
            reverse=True,
        )

        return [
            {
                "cache_key": entry.cache_key[:16] + "...",  # Truncate for readability
                "intent_type": entry.intent.intent_type,
                "confidence": entry.intent.confidence,
                "access_count": entry.access_count,
                "created_at": entry.created_at.isoformat(),
                "last_accessed": entry.last_accessed.isoformat(),
            }
            for entry in sorted_entries[:limit]
        ]
