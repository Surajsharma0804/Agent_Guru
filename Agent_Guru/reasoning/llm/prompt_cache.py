"""
Prompt Caching System

Implements LRU cache for prompt templates to reduce token usage by 80%.
Caches common prompt patterns and reuses them across requests.

Performance Target: <10ms cache lookup overhead
Token Reduction Target: 80% for cached prompts
"""

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class CachedPrompt:
    """Cached prompt entry."""

    prompt: str
    cache_key: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_access(self) -> None:
        """Update access statistics."""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_tokens_saved: int = 0
    evictions: int = 0
    last_reset: datetime = field(default_factory=datetime.now)

    def record_hit(self, tokens_saved: int) -> None:
        """Record cache hit."""
        self.total_requests += 1
        self.cache_hits += 1
        self.total_tokens_saved += tokens_saved

    def record_miss(self) -> None:
        """Record cache miss."""
        self.total_requests += 1
        self.cache_misses += 1

    def record_eviction(self) -> None:
        """Record cache eviction."""
        self.evictions += 1

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    def get_token_reduction(self) -> float:
        """Calculate token reduction percentage."""
        if self.total_requests == 0:
            return 0.0
        # Estimate: assume average prompt is 500 tokens
        estimated_total_tokens = self.total_requests * 500
        if estimated_total_tokens == 0:
            return 0.0
        return (self.total_tokens_saved / estimated_total_tokens) * 100

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.get_hit_rate(),
            "total_tokens_saved": self.total_tokens_saved,
            "token_reduction_percent": self.get_token_reduction(),
            "evictions": self.evictions,
            "last_reset": self.last_reset.isoformat(),
        }


class PromptCache:
    """
    LRU cache for prompt templates.

    Caches prompt templates with automatic eviction of least recently used entries.
    Tracks cache hits/misses and token savings.

    Example:
        >>> cache = PromptCache(max_size=1000)
        >>> cache.set("intent_type", "context", "prompt template")
        >>> prompt = cache.get("intent_type", "context")
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: Optional[float] = 300.0,  # 5 minutes default
    ):
        """Initialize prompt cache.

        Args:
            max_size: Maximum number of cached prompts
            ttl_seconds: Time-to-live for cache entries (None = no expiration)

        Raises:
            ValueError: If max_size <= 0
        """
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")

        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CachedPrompt] = OrderedDict()
        self.stats = CacheStats()

    def _generate_cache_key(self, intent_type: str, context: str) -> str:
        """
        Generate cache key from intent type and context.

        Uses SHA256 hash of intent_type + context for consistent keys.

        Args:
            intent_type: Intent type (e.g., "set_timer", "query_weather")
            context: Context string (conversation history, entities, etc.)

        Returns:
            Cache key string
        """
        key_string = f"{intent_type}:{context}"
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _is_expired(self, entry: CachedPrompt) -> bool:
        """Check if cache entry is expired."""
        if self.ttl_seconds is None:
            return False

        age = (datetime.now() - entry.created_at).total_seconds()
        return age > self.ttl_seconds

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._cache:
            # OrderedDict maintains insertion order, oldest first
            self._cache.popitem(last=False)
            self.stats.record_eviction()

    def _evict_expired(self) -> None:
        """Evict all expired entries."""
        if self.ttl_seconds is None:
            return

        expired_keys = [key for key, entry in self._cache.items() if self._is_expired(entry)]

        for key in expired_keys:
            del self._cache[key]
            self.stats.record_eviction()

    def get(self, intent_type: str, context: str = "") -> Optional[str]:
        """
        Get cached prompt.

        Args:
            intent_type: Intent type
            context: Context string

        Returns:
            Cached prompt or None if not found
        """
        cache_key = self._generate_cache_key(intent_type, context)

        # Check if entry exists
        if cache_key not in self._cache:
            self.stats.record_miss()
            return None

        entry = self._cache[cache_key]

        # Check if expired
        if self._is_expired(entry):
            del self._cache[cache_key]
            self.stats.record_miss()
            self.stats.record_eviction()
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)

        # Update access stats
        entry.update_access()

        # Record hit with token savings
        self.stats.record_hit(entry.token_count)

        return entry.prompt

    def set(
        self,
        intent_type: str,
        context: str,
        prompt: str,
        token_count: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Set cached prompt.

        Args:
            intent_type: Intent type
            context: Context string
            prompt: Prompt template to cache
            token_count: Optional token count for statistics
            metadata: Optional metadata
        """
        cache_key = self._generate_cache_key(intent_type, context)

        # Evict expired entries first
        self._evict_expired()

        # Evict LRU if at capacity
        if len(self._cache) >= self.max_size and cache_key not in self._cache:
            self._evict_lru()

        # Estimate token count if not provided
        if token_count is None:
            # Rough estimate: 1 token ≈ 4 characters
            token_count = len(prompt) // 4

        # Create or update entry
        entry = CachedPrompt(
            prompt=prompt,
            cache_key=cache_key,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=0,
            token_count=token_count,
            metadata=metadata or {},
        )

        self._cache[cache_key] = entry

    def invalidate(self, intent_type: str, context: str = "") -> bool:
        """
        Invalidate cached prompt.

        Args:
            intent_type: Intent type
            context: Context string

        Returns:
            True if entry was removed, False if not found
        """
        cache_key = self._generate_cache_key(intent_type, context)

        if cache_key in self._cache:
            del self._cache[cache_key]
            return True

        return False

    def clear(self) -> None:
        """Clear all cached prompts."""
        self._cache.clear()

    def get_size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        stats = self.stats.get_stats()
        stats["current_size"] = self.get_size()
        stats["max_size"] = self.max_size
        stats["utilization_percent"] = (self.get_size() / self.max_size) * 100
        return stats

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = CacheStats()

    def get_most_accessed(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get most accessed cache entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of entry statistics
        """
        sorted_entries = sorted(
            self._cache.values(),
            key=lambda e: e.access_count,
            reverse=True,
        )

        return [
            {
                "cache_key": entry.cache_key[:16] + "...",  # Truncate for readability
                "access_count": entry.access_count,
                "token_count": entry.token_count,
                "created_at": entry.created_at.isoformat(),
                "last_accessed": entry.last_accessed.isoformat(),
                "metadata": entry.metadata,
            }
            for entry in sorted_entries[:limit]
        ]
