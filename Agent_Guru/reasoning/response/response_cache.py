"""
Response Caching System

Implements caching for deterministic responses to reduce latency.
Caches responses for queries like weather, time, etc. with data freshness tracking.

Performance Target: <1ms cache lookup overhead
Cache Hit Rate Target: >60% for deterministic queries
TTL: Varies by query type (1 minute for time, 10 minutes for weather, etc.)

Author: Kiro AI
Date: 2026-02-22
Version: 1.0.0
"""

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from Agent_Guru.reasoning.models.result import Response


@dataclass
class CachedResponse:
    """Cached response entry.

    Attributes:
        response: Response object
        cache_key: Cache key (hash of query)
        intent_type: Intent type for TTL determination
        created_at: When entry was created
        last_accessed: When entry was last accessed
        access_count: Number of times accessed
        data_freshness: Data freshness timestamp (for invalidation)
    """

    response: Response
    cache_key: str
    intent_type: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    data_freshness: Optional[datetime] = None

    def update_access(self) -> None:
        """Update access statistics."""
        self.last_accessed = datetime.now(tz=timezone.utc)
        self.access_count += 1


@dataclass
class ResponseCacheStats:
    """Response cache statistics.

    Attributes:
        total_requests: Total cache lookup requests
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        freshness_invalidations: Number of freshness-based invalidations
        ttl_expirations: Number of TTL-based expirations
        evictions: Number of LRU evictions
        last_reset: When stats were last reset
    """

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    freshness_invalidations: int = 0
    ttl_expirations: int = 0
    evictions: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def record_hit(self) -> None:
        """Record cache hit."""
        self.total_requests += 1
        self.cache_hits += 1

    def record_miss(self) -> None:
        """Record cache miss."""
        self.total_requests += 1
        self.cache_misses += 1

    def record_freshness_invalidation(self) -> None:
        """Record freshness-based invalidation."""
        self.freshness_invalidations += 1

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
            "freshness_invalidations": self.freshness_invalidations,
            "ttl_expirations": self.ttl_expirations,
            "evictions": self.evictions,
            "last_reset": self.last_reset.isoformat(),
        }


class ResponseCache:
    """LRU cache for deterministic responses with intent-specific TTLs.

    Caches responses for deterministic queries with data freshness tracking.
    Different intent types have different TTLs based on data volatility.

    Time Complexity: O(1) for get/set operations
    Space Complexity: O(n) where n = max_size

    Example:
        >>> cache = ResponseCache(max_size=10000)
        >>> cache.set("what time is it", "query_time", response)
        >>> cached_response = cache.get("what time is it", "query_time")
        >>> if cached_response:
        ...     print(f"Response: {cached_response.text}")
    """

    # Intent-specific TTLs (in seconds)
    INTENT_TTL_MAP = {
        "query_time": 60,  # 1 minute (time changes frequently)
        "query_date": 3600,  # 1 hour (date changes less frequently)
        "query_weather": 600,  # 10 minutes (weather updates periodically)
        "query_stock_price": 300,  # 5 minutes (stock prices update frequently)
        "query_news": 600,  # 10 minutes (news updates periodically)
        "query_traffic": 300,  # 5 minutes (traffic changes frequently)
        "query_calendar": 300,  # 5 minutes (calendar may change)
        "query_reminder": 300,  # 5 minutes (reminders may change)
        "query_fact": 86400,  # 24 hours (facts are static)
        "query_definition": 86400,  # 24 hours (definitions are static)
        "query_calculation": 3600,  # 1 hour (calculations are deterministic)
    }

    DEFAULT_TTL = 300  # 5 minutes default

    def __init__(
        self,
        max_size: int = 10000,
    ):
        """Initialize response cache.

        Args:
            max_size: Maximum number of cached responses (LRU eviction)

        Raises:
            ValueError: If max_size <= 0
        """
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")

        self.max_size = max_size
        self._cache: OrderedDict[str, CachedResponse] = OrderedDict()
        self.stats = ResponseCacheStats()

        # Track cache hit rate per intent type
        self._intent_hit_rates: dict[str, tuple[int, int]] = {}  # (hits, total)

    def _generate_cache_key(self, query: str, intent_type: str) -> str:
        """Generate cache key from query and intent type.

        Args:
            query: Query text (normalized)
            intent_type: Intent type

        Returns:
            Cache key string (SHA256 hash)

        Time Complexity: O(n) where n = query length
        """
        # Normalize query (lowercase, strip whitespace)
        normalized_query = query.lower().strip()

        # Create key string with intent type
        key_string = f"{intent_type}:{normalized_query}"

        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_ttl(self, intent_type: str) -> timedelta:
        """Get TTL for intent type.

        Args:
            intent_type: Intent type

        Returns:
            TTL as timedelta

        Time Complexity: O(1)
        """
        ttl_seconds = self.INTENT_TTL_MAP.get(intent_type, self.DEFAULT_TTL)
        return timedelta(seconds=ttl_seconds)

    def _is_expired(self, entry: CachedResponse) -> bool:
        """Check if cache entry is expired based on TTL.

        Args:
            entry: Cached response entry

        Returns:
            True if expired, False otherwise

        Time Complexity: O(1)
        """
        ttl = self._get_ttl(entry.intent_type)
        age = datetime.now(tz=timezone.utc) - entry.created_at
        return age > ttl

    def _is_data_stale(self, entry: CachedResponse, freshness_threshold: Optional[datetime] = None) -> bool:
        """Check if cached data is stale based on freshness threshold.

        Args:
            entry: Cached response entry
            freshness_threshold: Optional freshness threshold

        Returns:
            True if data is stale, False otherwise

        Time Complexity: O(1)
        """
        if freshness_threshold is None or entry.data_freshness is None:
            return False

        return entry.data_freshness < freshness_threshold

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

    def get(
        self,
        query: str,
        intent_type: str,
        freshness_threshold: Optional[datetime] = None,
    ) -> Optional[Response]:
        """Get cached response for query.

        Args:
            query: Query text
            intent_type: Intent type
            freshness_threshold: Optional freshness threshold for invalidation

        Returns:
            Cached Response if found and valid, None otherwise

        Time Complexity: O(1) average case
        """
        start_time = time.perf_counter()

        cache_key = self._generate_cache_key(query, intent_type)

        # Check if entry exists
        if cache_key not in self._cache:
            self.stats.record_miss()
            self._update_intent_hit_rate(intent_type, hit=False)
            return None

        entry = self._cache[cache_key]

        # Check if expired
        if self._is_expired(entry):
            del self._cache[cache_key]
            self.stats.record_miss()
            self.stats.record_ttl_expiration()
            self._update_intent_hit_rate(intent_type, hit=False)
            return None

        # Check if data is stale
        if self._is_data_stale(entry, freshness_threshold):
            del self._cache[cache_key]
            self.stats.record_miss()
            self.stats.record_freshness_invalidation()
            self._update_intent_hit_rate(intent_type, hit=False)
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)

        # Update access stats
        entry.update_access()

        # Record hit
        self.stats.record_hit()
        self._update_intent_hit_rate(intent_type, hit=True)

        return entry.response

    def set(
        self,
        query: str,
        intent_type: str,
        response: Response,
        data_freshness: Optional[datetime] = None,
    ) -> None:
        """Set cached response for query.

        Args:
            query: Query text
            intent_type: Intent type
            response: Response to cache
            data_freshness: Optional data freshness timestamp

        Time Complexity: O(1) amortized
        """
        cache_key = self._generate_cache_key(query, intent_type)

        # Evict expired entries first
        self._evict_expired()

        # Evict LRU if at capacity
        if len(self._cache) >= self.max_size and cache_key not in self._cache:
            self._evict_lru()

        # Create or update entry
        entry = CachedResponse(
            response=response,
            cache_key=cache_key,
            intent_type=intent_type,
            created_at=datetime.now(tz=timezone.utc),
            last_accessed=datetime.now(tz=timezone.utc),
            data_freshness=data_freshness or datetime.now(tz=timezone.utc),
        )

        self._cache[cache_key] = entry

    def invalidate_by_intent_type(self, intent_type: str) -> int:
        """Invalidate all cache entries for a specific intent type.

        Args:
            intent_type: Intent type to invalidate

        Returns:
            Number of entries invalidated

        Time Complexity: O(n) where n = cache size
        """
        keys_to_invalidate = [
            key for key, entry in self._cache.items() if entry.intent_type == intent_type
        ]

        for key in keys_to_invalidate:
            del self._cache[key]
            self.stats.record_freshness_invalidation()

        return len(keys_to_invalidate)

    def invalidate_all(self) -> None:
        """Invalidate all cache entries.

        Time Complexity: O(1)
        """
        count = len(self._cache)
        self._cache.clear()
        self.stats.freshness_invalidations += count

    def clear(self) -> None:
        """Clear all cached responses.

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

    def _update_intent_hit_rate(self, intent_type: str, hit: bool) -> None:
        """Update hit rate tracking for intent type.

        Args:
            intent_type: Intent type
            hit: Whether this was a cache hit

        Time Complexity: O(1)
        """
        if intent_type not in self._intent_hit_rates:
            self._intent_hit_rates[intent_type] = (0, 0)

        hits, total = self._intent_hit_rates[intent_type]
        if hit:
            hits += 1
        total += 1
        self._intent_hit_rates[intent_type] = (hits, total)

    def get_intent_hit_rates(self) -> dict[str, float]:
        """Get cache hit rates per intent type.

        Returns:
            Dictionary mapping intent type to hit rate percentage

        Time Complexity: O(n) where n = number of intent types
        """
        return {
            intent_type: (hits / total * 100) if total > 0 else 0.0
            for intent_type, (hits, total) in self._intent_hit_rates.items()
        }

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = self.stats.get_stats()
        stats["current_size"] = self.get_size()
        stats["max_size"] = self.max_size
        stats["utilization_percent"] = (self.get_size() / self.max_size) * 100
        stats["intent_hit_rates"] = self.get_intent_hit_rates()
        return stats

    def reset_stats(self) -> None:
        """Reset cache statistics.

        Time Complexity: O(1)
        """
        self.stats = ResponseCacheStats()
        self._intent_hit_rates.clear()

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
                "intent_type": entry.intent_type,
                "access_count": entry.access_count,
                "created_at": entry.created_at.isoformat(),
                "last_accessed": entry.last_accessed.isoformat(),
            }
            for entry in sorted_entries[:limit]
        ]
