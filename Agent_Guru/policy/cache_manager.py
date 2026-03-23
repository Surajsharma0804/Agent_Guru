"""
Cache Manager - LRU cache for policy evaluation results.

Provides O(1) cache lookups with configurable TTL and LRU eviction.
Tracks hit/miss/eviction statistics.

Performance Characteristics:
    - get/put: O(1) amortized
    - invalidate: O(n) worst case

Validates: Requirement 7 (Performance Optimization through Caching)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

from Agent_Guru.policy.models import AccessDecision, CacheStats

logger = logging.getLogger(__name__)


class CacheManager:
    """LRU cache for policy evaluation results.

    Uses an OrderedDict for O(1) LRU operations.
    Each entry stores (decision, expiry_timestamp).

    Validates: Requirements 7.1–7.6
    """

    def __init__(
        self,
        max_size: int = 10_000,
        default_ttl: int = 300,
    ) -> None:
        """Initialise the cache.

        Args:
            max_size: Maximum number of entries before LRU eviction.
            default_ttl: Default time-to-live in seconds.
        """
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        if default_ttl < 1:
            raise ValueError("default_ttl must be >= 1")

        self.max_size = max_size
        self.default_ttl = default_ttl

        # OrderedDict preserves insertion order for LRU
        self._cache: OrderedDict[str, tuple[AccessDecision, float]] = OrderedDict()

        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def get(self, cache_key: str) -> Optional[AccessDecision]:
        """Return cached decision if valid, else None.

        Moves the entry to the end (most recently used) on hit.

        Validates: Requirements 7.1, 7.2
        """
        entry = self._cache.get(cache_key)
        if entry is None:
            self._misses += 1
            return None

        decision, expiry = entry
        if time.monotonic() > expiry:
            # Expired — remove and treat as miss
            del self._cache[cache_key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        self._hits += 1
        return decision

    def put(
        self,
        cache_key: str,
        decision: AccessDecision,
        ttl: Optional[int] = None,
    ) -> None:
        """Cache a decision.

        Evicts the LRU entry if at capacity.

        Validates: Requirements 7.1, 7.5
        """
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expiry = time.monotonic() + effective_ttl

        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
        elif len(self._cache) >= self.max_size:
            # Evict least recently used (first item)
            self._cache.popitem(last=False)
            self._evictions += 1

        self._cache[cache_key] = (decision, expiry)

    def invalidate(self, pattern: Optional[str] = None) -> int:
        """Invalidate cache entries.

        Args:
            pattern: If provided, only invalidate keys containing this substring.
                     If None, flush the entire cache.

        Returns:
            Number of entries invalidated.

        Validates: Requirement 7.4
        """
        if pattern is None:
            count = len(self._cache)
            self._cache.clear()
            return count

        keys_to_remove = [k for k in self._cache if pattern in k]
        for k in keys_to_remove:
            del self._cache[k]
        return len(keys_to_remove)

    def invalidate_for_policy(self, policy_id: str) -> int:
        """Invalidate all entries that reference a specific policy.

        Since cache keys don't embed policy IDs directly, we flush all
        entries as a conservative safe approach.

        Validates: Requirement 7.4
        """
        return self.invalidate()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> CacheStats:
        """Return current cache statistics.

        Validates: Requirement 7.6
        """
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            size=len(self._cache),
        )

    # ------------------------------------------------------------------
    # Cache key computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_cache_key(
        principal_id: str,
        resource_id: str,
        action: str,
        context: dict[str, Any],
        principal_attrs: Optional[dict[str, Any]] = None,
        resource_attrs: Optional[dict[str, Any]] = None,
    ) -> str:
        """Compute a stable cache key from request parameters.

        Includes principal and resource attributes so two principals with
        the same ID but different attributes get distinct cache entries.

        Args:
            principal_id: Principal identifier.
            resource_id: Resource identifier.
            action: Requested action.
            context: Evaluation context dict.
            principal_attrs: Principal attribute dict (optional).
            resource_attrs: Resource attribute dict (optional).

        Returns:
            SHA256 hex string cache key.
        """
        data = {
            "principal_id": principal_id,
            "principal_attrs": principal_attrs or {},
            "resource_id": resource_id,
            "resource_attrs": resource_attrs or {},
            "action": action,
            "context": context,
        }
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
