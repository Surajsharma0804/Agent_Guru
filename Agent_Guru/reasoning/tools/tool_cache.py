"""
Tool Selection Caching System

Implements caching for tool selection to reduce latency.
Caches intent→tool mappings and tool availability checks.

Performance Target: <10ms cache lookup overhead
Cache Hit Rate Target: >60%
TTL: 1 minute (60 seconds) for availability, 5 minutes for mappings

Author: Kiro AI
Date: 2026-02-22
Version: 1.0.0
"""

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from Agent_Guru.reasoning.models.intent import Intent


@dataclass
class CachedToolMapping:
    """Cached tool selection result.

    Attributes:
        tool_id: Selected tool ID
        parameters: Extracted parameters
        confidence: Selection confidence
        cache_key: Cache key (hash of intent)
        created_at: When entry was created
        last_accessed: When entry was last accessed
        access_count: Number of times accessed
    """

    tool_id: str
    parameters: dict[str, Any]
    confidence: float
    cache_key: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0

    def update_access(self) -> None:
        """Update access statistics."""
        self.last_accessed = datetime.now(tz=timezone.utc)
        self.access_count += 1


@dataclass
class CachedAvailability:
    """Cached tool availability check.

    Attributes:
        tool_id: Tool ID
        is_available: Whether tool is available
        cache_key: Cache key
        created_at: When entry was created
        last_accessed: When entry was last accessed
    """

    tool_id: str
    is_available: bool
    cache_key: str
    created_at: datetime
    last_accessed: datetime

    def update_access(self) -> None:
        """Update access statistics."""
        self.last_accessed = datetime.now(tz=timezone.utc)


@dataclass
class ToolCacheStats:
    """Tool cache statistics.

    Attributes:
        mapping_requests: Total mapping cache requests
        mapping_hits: Mapping cache hits
        mapping_misses: Mapping cache misses
        availability_requests: Total availability cache requests
        availability_hits: Availability cache hits
        availability_misses: Availability cache misses
        mapping_evictions: Mapping cache evictions
        availability_evictions: Availability cache evictions
        last_reset: When stats were last reset
    """

    mapping_requests: int = 0
    mapping_hits: int = 0
    mapping_misses: int = 0
    availability_requests: int = 0
    availability_hits: int = 0
    availability_misses: int = 0
    mapping_evictions: int = 0
    availability_evictions: int = 0
    last_reset: datetime = field(default_factory=datetime.now)

    def record_mapping_hit(self) -> None:
        """Record mapping cache hit."""
        self.mapping_requests += 1
        self.mapping_hits += 1

    def record_mapping_miss(self) -> None:
        """Record mapping cache miss."""
        self.mapping_requests += 1
        self.mapping_misses += 1

    def record_availability_hit(self) -> None:
        """Record availability cache hit."""
        self.availability_requests += 1
        self.availability_hits += 1

    def record_availability_miss(self) -> None:
        """Record availability cache miss."""
        self.availability_requests += 1
        self.availability_misses += 1

    def get_mapping_hit_rate(self) -> float:
        """Calculate mapping cache hit rate."""
        if self.mapping_requests == 0:
            return 0.0
        return (self.mapping_hits / self.mapping_requests) * 100

    def get_availability_hit_rate(self) -> float:
        """Calculate availability cache hit rate."""
        if self.availability_requests == 0:
            return 0.0
        return (self.availability_hits / self.availability_requests) * 100

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "mapping": {
                "total_requests": self.mapping_requests,
                "cache_hits": self.mapping_hits,
                "cache_misses": self.mapping_misses,
                "hit_rate_percent": self.get_mapping_hit_rate(),
                "evictions": self.mapping_evictions,
            },
            "availability": {
                "total_requests": self.availability_requests,
                "cache_hits": self.availability_hits,
                "cache_misses": self.availability_misses,
                "hit_rate_percent": self.get_availability_hit_rate(),
                "evictions": self.availability_evictions,
            },
            "last_reset": self.last_reset.isoformat(),
        }


class ToolSelectionCache:
    """LRU cache for tool selection with separate caches for mappings and availability.

    Caches intent→tool mappings and tool availability checks.

    Time Complexity: O(1) for get/set operations
    Space Complexity: O(n) where n = max_size

    Example:
        >>> cache = ToolSelectionCache()
        >>> cache.set_mapping(intent, "timer_tool", params, 0.95)
        >>> cached = cache.get_mapping(intent)
        >>> if cached:
        ...     print(f"Tool: {cached['tool_id']}")
    """

    def __init__(
        self,
        mapping_max_size: int = 10000,
        mapping_ttl_seconds: float = 300.0,  # 5 minutes
        availability_max_size: int = 1000,
        availability_ttl_seconds: float = 60.0,  # 1 minute
    ):
        """Initialize tool selection cache.

        Args:
            mapping_max_size: Maximum number of cached mappings
            mapping_ttl_seconds: TTL for mapping cache entries
            availability_max_size: Maximum number of cached availability checks
            availability_ttl_seconds: TTL for availability cache entries

        Raises:
            ValueError: If any size or TTL parameter is invalid
        """
        if mapping_max_size <= 0:
            raise ValueError(f"mapping_max_size must be positive, got {mapping_max_size}")
        if availability_max_size <= 0:
            raise ValueError(f"availability_max_size must be positive, got {availability_max_size}")
        if mapping_ttl_seconds <= 0:
            raise ValueError(f"mapping_ttl_seconds must be positive, got {mapping_ttl_seconds}")
        if availability_ttl_seconds <= 0:
            raise ValueError(
                f"availability_ttl_seconds must be positive, got {availability_ttl_seconds}"
            )

        self.mapping_max_size = mapping_max_size
        self.mapping_ttl = timedelta(seconds=mapping_ttl_seconds)
        self.availability_max_size = availability_max_size
        self.availability_ttl = timedelta(seconds=availability_ttl_seconds)

        self._mapping_cache: OrderedDict[str, CachedToolMapping] = OrderedDict()
        self._availability_cache: OrderedDict[str, CachedAvailability] = OrderedDict()
        self.stats = ToolCacheStats()

        # Hot path tracking for frequently used tools
        self._hot_path_tools: set[str] = set()
        self._tool_access_counts: dict[str, int] = {}

    def _generate_mapping_key(self, intent: Intent) -> str:
        """Generate cache key for intent→tool mapping.

        Args:
            intent: Intent object

        Returns:
            Cache key string (SHA256 hash)

        Time Complexity: O(n) where n = intent size
        """
        # Create key from intent type and entities
        key_parts = [intent.intent_type]

        # Add sorted entity keys and values
        for entity_name in sorted(intent.entities.keys()):
            entity = intent.entities[entity_name]
            key_parts.append(f"{entity_name}:{entity.entity_type.value}")

        key_string = ":".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _generate_availability_key(self, tool_id: str) -> str:
        """Generate cache key for tool availability.

        Args:
            tool_id: Tool ID

        Returns:
            Cache key string

        Time Complexity: O(1)
        """
        return f"avail:{tool_id}"

    def _is_mapping_expired(self, entry: CachedToolMapping) -> bool:
        """Check if mapping entry is expired."""
        age = datetime.now(tz=timezone.utc) - entry.created_at
        return age > self.mapping_ttl

    def _is_availability_expired(self, entry: CachedAvailability) -> bool:
        """Check if availability entry is expired."""
        age = datetime.now(tz=timezone.utc) - entry.created_at
        return age > self.availability_ttl

    def get_mapping(self, intent: Intent) -> Optional[dict[str, Any]]:
        """Get cached tool mapping for intent.

        Args:
            intent: Intent object

        Returns:
            Dictionary with tool_id, parameters, confidence if found, None otherwise

        Time Complexity: O(1) average case
        """
        cache_key = self._generate_mapping_key(intent)

        if cache_key not in self._mapping_cache:
            self.stats.record_mapping_miss()
            return None

        entry = self._mapping_cache[cache_key]

        # Check if expired
        if self._is_mapping_expired(entry):
            del self._mapping_cache[cache_key]
            self.stats.record_mapping_miss()
            return None

        # Move to end (most recently used)
        self._mapping_cache.move_to_end(cache_key)

        # Update access stats
        entry.update_access()

        # Record hit
        self.stats.record_mapping_hit()

        return {
            "tool_id": entry.tool_id,
            "parameters": entry.parameters,
            "confidence": entry.confidence,
        }

    def set_mapping(
        self,
        intent: Intent,
        tool_id: str,
        parameters: dict[str, Any],
        confidence: float,
    ) -> None:
        """Set cached tool mapping for intent.

        Args:
            intent: Intent object
            tool_id: Selected tool ID
            parameters: Extracted parameters
            confidence: Selection confidence

        Time Complexity: O(1) amortized
        """
        cache_key = self._generate_mapping_key(intent)

        # Evict LRU if at capacity
        if len(self._mapping_cache) >= self.mapping_max_size and cache_key not in self._mapping_cache:
            self._mapping_cache.popitem(last=False)
            self.stats.mapping_evictions += 1

        # Create or update entry
        entry = CachedToolMapping(
            tool_id=tool_id,
            parameters=parameters,
            confidence=confidence,
            cache_key=cache_key,
            created_at=datetime.now(tz=timezone.utc),
            last_accessed=datetime.now(tz=timezone.utc),
        )

        self._mapping_cache[cache_key] = entry

        # Track tool access for hot path
        self._tool_access_counts[tool_id] = self._tool_access_counts.get(tool_id, 0) + 1

        # Update hot path if tool is frequently used (>100 accesses)
        if self._tool_access_counts[tool_id] > 100:
            self._hot_path_tools.add(tool_id)

    def get_availability(self, tool_id: str) -> Optional[bool]:
        """Get cached tool availability.

        Args:
            tool_id: Tool ID

        Returns:
            True if available, False if not available, None if not cached

        Time Complexity: O(1) average case
        """
        cache_key = self._generate_availability_key(tool_id)

        if cache_key not in self._availability_cache:
            self.stats.record_availability_miss()
            return None

        entry = self._availability_cache[cache_key]

        # Check if expired
        if self._is_availability_expired(entry):
            del self._availability_cache[cache_key]
            self.stats.record_availability_miss()
            return None

        # Move to end (most recently used)
        self._availability_cache.move_to_end(cache_key)

        # Update access stats
        entry.update_access()

        # Record hit
        self.stats.record_availability_hit()

        return entry.is_available

    def set_availability(self, tool_id: str, is_available: bool) -> None:
        """Set cached tool availability.

        Args:
            tool_id: Tool ID
            is_available: Whether tool is available

        Time Complexity: O(1) amortized
        """
        cache_key = self._generate_availability_key(tool_id)

        # Evict LRU if at capacity
        if (
            len(self._availability_cache) >= self.availability_max_size
            and cache_key not in self._availability_cache
        ):
            self._availability_cache.popitem(last=False)
            self.stats.availability_evictions += 1

        # Create or update entry
        entry = CachedAvailability(
            tool_id=tool_id,
            is_available=is_available,
            cache_key=cache_key,
            created_at=datetime.now(tz=timezone.utc),
            last_accessed=datetime.now(tz=timezone.utc),
        )

        self._availability_cache[cache_key] = entry

    def is_hot_path_tool(self, tool_id: str) -> bool:
        """Check if tool is in hot path (frequently used).

        Args:
            tool_id: Tool ID

        Returns:
            True if tool is frequently used, False otherwise

        Time Complexity: O(1)
        """
        return tool_id in self._hot_path_tools

    def get_hot_path_tools(self) -> list[str]:
        """Get list of hot path tools.

        Returns:
            List of frequently used tool IDs

        Time Complexity: O(1)
        """
        return list(self._hot_path_tools)

    def invalidate_tool(self, tool_id: str) -> None:
        """Invalidate all cache entries for a specific tool.

        Args:
            tool_id: Tool ID to invalidate

        Time Complexity: O(n) where n = cache size
        """
        # Invalidate mappings
        keys_to_remove = [
            key for key, entry in self._mapping_cache.items() if entry.tool_id == tool_id
        ]
        for key in keys_to_remove:
            del self._mapping_cache[key]

        # Invalidate availability
        avail_key = self._generate_availability_key(tool_id)
        if avail_key in self._availability_cache:
            del self._availability_cache[avail_key]

    def clear(self) -> None:
        """Clear all cached entries.

        Time Complexity: O(1)
        """
        self._mapping_cache.clear()
        self._availability_cache.clear()
        self._hot_path_tools.clear()
        self._tool_access_counts.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = self.stats.get_stats()
        stats["mapping"]["current_size"] = len(self._mapping_cache)
        stats["mapping"]["max_size"] = self.mapping_max_size
        stats["mapping"]["utilization_percent"] = (
            len(self._mapping_cache) / self.mapping_max_size
        ) * 100
        stats["availability"]["current_size"] = len(self._availability_cache)
        stats["availability"]["max_size"] = self.availability_max_size
        stats["availability"]["utilization_percent"] = (
            len(self._availability_cache) / self.availability_max_size
        ) * 100
        stats["hot_path_tools"] = list(self._hot_path_tools)
        stats["hot_path_count"] = len(self._hot_path_tools)
        return stats

    def reset_stats(self) -> None:
        """Reset cache statistics.

        Time Complexity: O(1)
        """
        self.stats = ToolCacheStats()
