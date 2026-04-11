"""
Module: agent_guru.platform.network.response_cache
Purpose: HTTP response caching with LRU eviction and Cache-Control support
Author: Agent Guru Team
Date: 2026-02-26

Performance Requirements:
- Time Complexity: O(1) for cache get/set operations
- Space Complexity: O(n) where n is number of cached responses (max 100MB)
- Cache hit latency: <1ms (95th percentile)
- Cache miss overhead: <5ms (95th percentile)

Design Decisions:
- Use OrderedDict for LRU eviction (O(1) operations)
- Parse Cache-Control headers for TTL (RFC 7234 compliance)
- SHA-256 for cache keys (collision-resistant)
- Preallocate cache statistics (avoid runtime allocation)
- Thread-safe with asyncio locks (concurrent access)
"""

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

# Configure structured logging
logger = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    """Cached HTTP response with metadata.

    Attributes:
        body: Response body as bytes
        status_code: HTTP status code
        headers: Response headers
        url: Request URL
        method: HTTP method
        cached_at: Timestamp when response was cached
        expires_at: Timestamp when cache entry expires
        size: Size of cached response in bytes
    """

    body: bytes
    status_code: int
    headers: dict[str, str]
    url: str
    method: str
    cached_at: float
    expires_at: float
    size: int

    def is_expired(self) -> bool:
        """Check if cache entry has expired.

        Time Complexity: O(1)

        Returns:
            True if expired, False otherwise
        """
        return time.time() >= self.expires_at

    def time_to_live(self) -> float:
        """Get remaining time to live in seconds.

        Time Complexity: O(1)

        Returns:
            Seconds until expiration (0 if already expired)
        """
        ttl = self.expires_at - time.time()
        return max(0.0, ttl)


@dataclass
class CacheStatistics:
    """Cache performance statistics.

    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        evictions: Number of LRU evictions
        invalidations: Number of manual invalidations
        total_size: Current cache size in bytes
        entry_count: Number of cached entries
        hit_rate: Cache hit rate (0.0-1.0)
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0
    total_size: int = 0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate.

        Time Complexity: O(1)

        Returns:
            Hit rate as percentage (0.0-1.0)
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def reset(self) -> None:
        """Reset all statistics to zero.

        Time Complexity: O(1)
        """
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.invalidations = 0
        # Don't reset total_size and entry_count (current state)


class ResponseCache:
    """HTTP response cache with LRU eviction and Cache-Control support.

    Time Complexity: O(1) for get/set operations
    Space Complexity: O(n) where n is number of cached responses

    Features:
    - LRU eviction policy (least recently used)
    - Respect Cache-Control headers (max-age, no-cache, no-store)
    - Configurable max size (default: 100MB)
    - Cache invalidation by URL pattern
    - Cache statistics tracking
    - Thread-safe with asyncio locks

    Example:
        >>> cache = ResponseCache(max_size=100 * 1024 * 1024)
        >>> await cache.set("https://api.example.com/data", response, ttl=300)
        >>> cached = await cache.get("https://api.example.com/data")
        >>> if cached:
        ...     print(f"Cache hit! TTL: {cached.time_to_live()}s")
        >>> stats = cache.get_statistics()
        >>> print(f"Hit rate: {stats.hit_rate:.2%}")
    """

    def __init__(self, max_size: int = 100 * 1024 * 1024):
        """Initialize response cache.

        Args:
            max_size: Maximum cache size in bytes (default: 100MB)

        Raises:
            ValueError: If max_size is not positive
        """
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")

        self.max_size = max_size
        self._cache: OrderedDict[str, CachedResponse] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = CacheStatistics()

        logger.info(
            "ResponseCache initialized",
            extra={
                "max_size_mb": max_size / (1024 * 1024),
            }
        )

    def _generate_cache_key(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None
    ) -> str:
        """Generate cache key from request parameters.

        Time Complexity: O(n) where n is URL + headers length
        Space Complexity: O(1) - fixed hash size

        Args:
            url: Request URL
            method: HTTP method
            headers: Request headers (only Vary headers considered)

        Returns:
            SHA-256 hash as cache key
        """
        # Normalize URL (remove fragment, sort query params)
        parsed = urlparse(url)
        normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            # Sort query parameters for consistent caching
            query_parts = sorted(parsed.query.split('&'))
            normalized_url += '?' + '&'.join(query_parts)

        # Create cache key from method + URL
        key_data = f"{method.upper()}:{normalized_url}"

        # Include Vary headers if present
        if headers:
            vary_headers = []
            for header, value in sorted(headers.items()):
                if header.lower() in ('accept', 'accept-encoding', 'accept-language'):
                    vary_headers.append(f"{header}:{value}")
            if vary_headers:
                key_data += ':' + ':'.join(vary_headers)

        # Generate SHA-256 hash
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()

    def _parse_cache_control(self, headers: dict[str, str]) -> tuple[bool, Optional[int]]:
        """Parse Cache-Control header for caching directives.

        Time Complexity: O(n) where n is header value length
        Space Complexity: O(1)

        Args:
            headers: Response headers

        Returns:
            Tuple of (is_cacheable, max_age_seconds)
        """
        cache_control = headers.get('Cache-Control', '').lower()

        # Check for no-cache or no-store directives
        if 'no-cache' in cache_control or 'no-store' in cache_control:
            return False, None

        # Extract max-age directive
        max_age = None
        for directive in cache_control.split(','):
            directive = directive.strip()
            if directive.startswith('max-age='):
                try:
                    max_age = int(directive.split('=')[1])
                except (ValueError, IndexError):
                    pass

        # Check Expires header if no max-age
        if max_age is None and 'Expires' in headers:
            try:
                from email.utils import parsedate_to_datetime
                expires = parsedate_to_datetime(headers['Expires'])
                max_age = int((expires - datetime.now(expires.tzinfo)).total_seconds())
            except (ValueError, TypeError):
                pass

        # Default TTL if no caching directives
        if max_age is None:
            max_age = 300  # 5 minutes default

        return True, max_age

    async def get(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None
    ) -> Optional[CachedResponse]:
        """Get cached response if available and not expired.

        Time Complexity: O(1) average case
        Space Complexity: O(1)

        Args:
            url: Request URL
            method: HTTP method
            headers: Request headers

        Returns:
            Cached response or None if not found/expired
        """
        cache_key = self._generate_cache_key(url, method, headers)

        async with self._lock:
            # Check if entry exists
            if cache_key not in self._cache:
                self._stats.misses += 1
                logger.debug(
                    "Cache miss",
                    extra={
                        "url": url,
                        "method": method,
                        "cache_key": cache_key[:16],
                    }
                )
                return None

            # Get entry and move to end (LRU)
            cached = self._cache.pop(cache_key)

            # Check if expired
            if cached.is_expired():
                # Remove expired entry
                self._stats.total_size -= cached.size
                self._stats.entry_count -= 1
                self._stats.misses += 1
                logger.debug(
                    "Cache expired",
                    extra={
                        "url": url,
                        "method": method,
                        "cached_at": datetime.fromtimestamp(cached.cached_at).isoformat(),
                        "expires_at": datetime.fromtimestamp(cached.expires_at).isoformat(),
                    }
                )
                return None

            # Move to end (most recently used)
            self._cache[cache_key] = cached
            self._stats.hits += 1

            logger.debug(
                "Cache hit",
                extra={
                    "url": url,
                    "method": method,
                    "ttl": cached.time_to_live(),
                    "size": cached.size,
                }
            )

            return cached

    async def set(
        self,
        url: str,
        status_code: int,
        headers: dict[str, str],
        body: bytes,
        method: str = "GET",
        ttl: Optional[int] = None
    ) -> bool:
        """Cache response with TTL.

        Time Complexity: O(1) average case, O(n) worst case for eviction
        Space Complexity: O(1)

        Args:
            url: Request URL
            status_code: HTTP status code
            headers: Response headers
            body: Response body
            method: HTTP method
            ttl: Time to live in seconds (overrides Cache-Control)

        Returns:
            True if cached, False if not cacheable
        """
        # Only cache successful responses
        if not (200 <= status_code < 300):
            logger.debug(
                "Response not cacheable (status code)",
                extra={
                    "url": url,
                    "status_code": status_code,
                }
            )
            return False

        # Parse Cache-Control headers
        is_cacheable, max_age = self._parse_cache_control(headers)
        if not is_cacheable:
            logger.debug(
                "Response not cacheable (Cache-Control)",
                extra={
                    "url": url,
                    "cache_control": headers.get('Cache-Control', ''),
                }
            )
            return False

        # Use provided TTL or Cache-Control max-age
        cache_ttl = ttl if ttl is not None else max_age
        if cache_ttl is None or cache_ttl <= 0:
            return False

        # Calculate entry size
        entry_size = len(body) + sum(len(k) + len(v) for k, v in headers.items())

        # Check if entry is too large
        if entry_size > self.max_size:
            logger.warning(
                "Response too large to cache",
                extra={
                    "url": url,
                    "size_mb": entry_size / (1024 * 1024),
                    "max_size_mb": self.max_size / (1024 * 1024),
                }
            )
            return False

        cache_key = self._generate_cache_key(url, method, headers)
        current_time = time.time()

        async with self._lock:
            # Evict LRU entries if needed
            await self._evict_if_needed(entry_size)

            # Create cached response
            cached = CachedResponse(
                body=body,
                status_code=status_code,
                headers=headers.copy(),
                url=url,
                method=method,
                cached_at=current_time,
                expires_at=current_time + cache_ttl,
                size=entry_size,
            )

            # Remove old entry if exists
            if cache_key in self._cache:
                old_cached = self._cache.pop(cache_key)
                self._stats.total_size -= old_cached.size
                self._stats.entry_count -= 1

            # Add to cache
            self._cache[cache_key] = cached
            self._stats.total_size += entry_size
            self._stats.entry_count += 1

            logger.debug(
                "Response cached",
                extra={
                    "url": url,
                    "method": method,
                    "ttl": cache_ttl,
                    "size": entry_size,
                    "total_size_mb": self._stats.total_size / (1024 * 1024),
                    "entry_count": self._stats.entry_count,
                }
            )

            return True

    async def _evict_if_needed(self, required_size: int) -> None:
        """Evict LRU entries to free space.

        Time Complexity: O(n) worst case where n is number of evictions
        Space Complexity: O(1)

        Args:
            required_size: Size needed for new entry
        """
        # Evict until we have enough space
        while self._stats.total_size + required_size > self.max_size and self._cache:
            # Remove least recently used (first item)
            cache_key, cached = self._cache.popitem(last=False)
            self._stats.total_size -= cached.size
            self._stats.entry_count -= 1
            self._stats.evictions += 1

            logger.debug(
                "Cache eviction (LRU)",
                extra={
                    "url": cached.url,
                    "size": cached.size,
                    "age": time.time() - cached.cached_at,
                }
            )

    async def invalidate(self, url_pattern: Optional[str] = None) -> int:
        """Invalidate cache entries matching URL pattern.

        Time Complexity: O(n) where n is number of cache entries
        Space Complexity: O(k) where k is number of matching entries

        Args:
            url_pattern: URL pattern to match (None = invalidate all)

        Returns:
            Number of entries invalidated
        """
        async with self._lock:
            if url_pattern is None:
                # Invalidate all
                count = len(self._cache)
                self._cache.clear()
                self._stats.total_size = 0
                self._stats.entry_count = 0
                self._stats.invalidations += count

                logger.info(
                    "Cache invalidated (all)",
                    extra={"count": count}
                )

                return count

            # Invalidate matching entries
            keys_to_remove = []
            for cache_key, cached in self._cache.items():
                if url_pattern in cached.url:
                    keys_to_remove.append(cache_key)

            # Remove matching entries
            for cache_key in keys_to_remove:
                cached = self._cache.pop(cache_key)
                self._stats.total_size -= cached.size
                self._stats.entry_count -= 1
                self._stats.invalidations += 1

            logger.info(
                "Cache invalidated (pattern)",
                extra={
                    "pattern": url_pattern,
                    "count": len(keys_to_remove),
                }
            )

            return len(keys_to_remove)

    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Time Complexity: O(n) where n is number of cache entries
        Space Complexity: O(k) where k is number of expired entries

        Returns:
            Number of entries removed
        """
        async with self._lock:
            current_time = time.time()
            keys_to_remove = []

            for cache_key, cached in self._cache.items():
                if cached.expires_at <= current_time:
                    keys_to_remove.append(cache_key)

            # Remove expired entries
            for cache_key in keys_to_remove:
                cached = self._cache.pop(cache_key)
                self._stats.total_size -= cached.size
                self._stats.entry_count -= 1

            if keys_to_remove:
                logger.debug(
                    "Expired entries cleaned up",
                    extra={"count": len(keys_to_remove)}
                )

            return len(keys_to_remove)

    def get_statistics(self) -> CacheStatistics:
        """Get cache statistics.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Cache statistics (copy)
        """
        return CacheStatistics(
            hits=self._stats.hits,
            misses=self._stats.misses,
            evictions=self._stats.evictions,
            invalidations=self._stats.invalidations,
            total_size=self._stats.total_size,
            entry_count=self._stats.entry_count,
        )

    def reset_statistics(self) -> None:
        """Reset cache statistics (keep cached entries).

        Time Complexity: O(1)
        """
        self._stats.reset()
        logger.info("Cache statistics reset")

    @property
    def size(self) -> int:
        """Get current cache size in bytes.

        Time Complexity: O(1)

        Returns:
            Current cache size
        """
        return self._stats.total_size

    @property
    def count(self) -> int:
        """Get number of cached entries.

        Time Complexity: O(1)

        Returns:
            Number of entries
        """
        return self._stats.entry_count

    @property
    def hit_rate(self) -> float:
        """Get cache hit rate.

        Time Complexity: O(1)

        Returns:
            Hit rate as percentage (0.0-1.0)
        """
        return self._stats.hit_rate
