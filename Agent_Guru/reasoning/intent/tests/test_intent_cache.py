"""
Tests for Intent Detection Caching System

Tests cache functionality, TTL expiration, context invalidation, and performance.
"""

import time
from datetime import datetime, timezone

import pytest

from Agent_Guru.reasoning.intent.intent_cache import (
    CachedIntent,
    IntentCacheStats,
    IntentDetectionCache,
)
from Agent_Guru.reasoning.models.intent import Entity, EntityType, Intent


@pytest.fixture
def sample_intent():
    """Create sample intent for testing."""
    return Intent(
        intent_type="set_timer",
        entities={
            "duration": Entity(
                entity_type=EntityType.DURATION,
                value={"value": 5, "unit": "minutes"},
                raw_text="5 minutes",
                confidence=0.95,
            )
        },
        confidence=0.98,
        requires_reasoning=False,
        original_input="set timer for 5 minutes",
        resolved_input="set timer for 5 minutes",
        detection_method="rule",  # Use "rule" instead of "fast_path"
    )


@pytest.fixture
def cache():
    """Create intent cache for testing."""
    return IntentDetectionCache(max_size=100, ttl_seconds=300)


class TestIntentDetectionCache:
    """Tests for IntentDetectionCache."""

    def test_initialization(self):
        """Test cache initialization."""
        cache = IntentDetectionCache(max_size=1000, ttl_seconds=300)

        assert cache.max_size == 1000  # nosec B101
        assert cache.ttl_seconds == 300  # nosec B101
        assert cache.get_size() == 0  # nosec B101
        assert cache.stats.total_requests == 0  # nosec B101

    def test_initialization_invalid_params(self):
        """Test initialization with invalid parameters."""
        with pytest.raises(ValueError):
            IntentDetectionCache(max_size=0)

        with pytest.raises(ValueError):
            IntentDetectionCache(max_size=-1)

        with pytest.raises(ValueError):
            IntentDetectionCache(ttl_seconds=0)

        with pytest.raises(ValueError):
            IntentDetectionCache(ttl_seconds=-1)

    def test_set_and_get(self, cache, sample_intent):
        """Test basic set and get operations."""
        text = "set timer for 5 minutes"
        context = {"user_id": "user123"}

        # Set intent
        cache.set(text, context, sample_intent)

        # Get intent
        cached_intent = cache.get(text, context)

        assert cached_intent is not None  # nosec B101
        assert cached_intent.intent_type == "set_timer"  # nosec B101
        assert cached_intent.confidence == 0.98  # nosec B101
        assert cache.get_size() == 1  # nosec B101

    def test_cache_hit(self, cache, sample_intent):
        """Test cache hit tracking."""
        text = "set timer for 5 minutes"

        cache.set(text, None, sample_intent)
        cached_intent = cache.get(text, None)

        assert cached_intent is not None  # nosec B101
        assert cache.stats.cache_hits == 1  # nosec B101
        assert cache.stats.cache_misses == 0  # nosec B101
        assert cache.stats.get_hit_rate() == 100.0  # nosec B101

    def test_cache_miss(self, cache):
        """Test cache miss tracking."""
        text = "set timer for 5 minutes"

        cached_intent = cache.get(text, None)

        assert cached_intent is None  # nosec B101
        assert cache.stats.cache_hits == 0  # nosec B101
        assert cache.stats.cache_misses == 1  # nosec B101
        assert cache.stats.get_hit_rate() == 0.0  # nosec B101

    def test_cache_with_context(self, cache, sample_intent):
        """Test caching with different contexts."""
        text = "set timer for 5 minutes"
        context1 = {"user_id": "user1"}
        context2 = {"user_id": "user2"}

        # Set with context1
        cache.set(text, context1, sample_intent)

        # Get with context1 - should hit
        cached1 = cache.get(text, context1)
        assert cached1 is not None  # nosec B101

        # Get with context2 - should miss (different context)
        cached2 = cache.get(text, context2)
        assert cached2 is None  # nosec B101

        # Get with no context - should miss
        cached3 = cache.get(text, None)
        assert cached3 is None  # nosec B101

    def test_ttl_expiration(self, cache, sample_intent):
        """Test TTL-based expiration."""
        # Create cache with 1-second TTL
        short_ttl_cache = IntentDetectionCache(max_size=100, ttl_seconds=1)

        text = "set timer for 5 minutes"
        short_ttl_cache.set(text, None, sample_intent)

        # Should hit immediately
        cached = short_ttl_cache.get(text, None)
        assert cached is not None  # nosec B101

        # Wait for TTL to expire
        time.sleep(1.1)

        # Should miss after expiration
        cached = short_ttl_cache.get(text, None)
        assert cached is None  # nosec B101
        assert short_ttl_cache.stats.ttl_expirations == 1  # nosec B101

    def test_lru_eviction(self, sample_intent):
        """Test LRU eviction when cache is full."""
        # Create small cache
        small_cache = IntentDetectionCache(max_size=3, ttl_seconds=300)

        # Fill cache
        for i in range(3):
            small_cache.set(f"text{i}", None, sample_intent)

        assert small_cache.get_size() == 3  # nosec B101

        # Add one more - should evict oldest
        small_cache.set("text3", None, sample_intent)

        assert small_cache.get_size() == 3  # nosec B101
        assert small_cache.stats.evictions == 1  # nosec B101

        # Oldest entry (text0) should be evicted
        assert small_cache.get("text0", None) is None  # nosec B101
        assert small_cache.get("text1", None) is not None  # nosec B101
        assert small_cache.get("text2", None) is not None  # nosec B101
        assert small_cache.get("text3", None) is not None  # nosec B101

    def test_context_invalidation(self, cache, sample_intent):
        """Test context-based invalidation."""
        context1 = {"user_id": "user1"}
        context2 = {"user_id": "user2"}

        # Add entries with different contexts
        cache.set("text1", context1, sample_intent)
        cache.set("text2", context1, sample_intent)
        cache.set("text3", context2, sample_intent)

        assert cache.get_size() == 3  # nosec B101

        # Invalidate context1
        invalidated = cache.invalidate_by_context(context1)

        assert invalidated == 2  # nosec B101
        assert cache.get_size() == 1  # nosec B101
        assert cache.stats.context_invalidations == 2  # nosec B101

        # context1 entries should be gone
        assert cache.get("text1", context1) is None  # nosec B101
        assert cache.get("text2", context1) is None  # nosec B101

        # context2 entry should remain
        assert cache.get("text3", context2) is not None  # nosec B101

    def test_invalidate_all(self, cache, sample_intent):
        """Test invalidating all entries."""
        # Add multiple entries
        for i in range(5):
            cache.set(f"text{i}", None, sample_intent)

        assert cache.get_size() == 5  # nosec B101

        # Invalidate all
        cache.invalidate_all()

        assert cache.get_size() == 0  # nosec B101
        assert cache.stats.context_invalidations == 5  # nosec B101

    def test_clear(self, cache, sample_intent):
        """Test clearing cache."""
        # Add entries
        for i in range(5):
            cache.set(f"text{i}", None, sample_intent)

        assert cache.get_size() == 5  # nosec B101

        # Clear
        cache.clear()

        assert cache.get_size() == 0  # nosec B101

    def test_access_count_tracking(self, cache, sample_intent):
        """Test access count tracking."""
        text = "set timer for 5 minutes"

        cache.set(text, None, sample_intent)

        # Access multiple times
        for _ in range(5):
            cache.get(text, None)

        # Check most accessed
        most_accessed = cache.get_most_accessed(limit=1)

        assert len(most_accessed) == 1  # nosec B101
        assert most_accessed[0]["access_count"] == 5  # nosec B101
        assert most_accessed[0]["intent_type"] == "set_timer"  # nosec B101

    def test_cache_stats(self, cache, sample_intent):
        """Test cache statistics."""
        # Generate some activity
        cache.set("text1", None, sample_intent)
        cache.get("text1", None)  # Hit
        cache.get("text2", None)  # Miss

        stats = cache.get_stats()

        assert stats["total_requests"] == 2  # nosec B101
        assert stats["cache_hits"] == 1  # nosec B101
        assert stats["cache_misses"] == 1  # nosec B101
        assert stats["hit_rate_percent"] == 50.0  # nosec B101
        assert stats["current_size"] == 1  # nosec B101
        assert stats["max_size"] == 100  # nosec B101
        assert stats["utilization_percent"] == 1.0  # nosec B101

    def test_reset_stats(self, cache, sample_intent):
        """Test resetting statistics."""
        # Generate activity
        cache.set("text1", None, sample_intent)
        cache.get("text1", None)

        assert cache.stats.total_requests > 0  # nosec B101

        # Reset
        cache.reset_stats()

        assert cache.stats.total_requests == 0  # nosec B101
        assert cache.stats.cache_hits == 0  # nosec B101
        assert cache.stats.cache_misses == 0  # nosec B101

    def test_cache_key_consistency(self, cache, sample_intent):
        """Test cache key generation is consistent."""
        text = "set timer for 5 minutes"
        context = {"user_id": "user123", "conversation_id": "conv456"}

        # Set with context
        cache.set(text, context, sample_intent)

        # Get with same context (different dict instance)
        context_copy = {"user_id": "user123", "conversation_id": "conv456"}
        cached = cache.get(text, context_copy)

        assert cached is not None  # nosec B101

    def test_cache_key_order_independence(self, cache, sample_intent):
        """Test cache key is independent of context key order."""
        text = "set timer for 5 minutes"
        context1 = {"user_id": "user123", "conversation_id": "conv456"}
        context2 = {"conversation_id": "conv456", "user_id": "user123"}  # Different order

        # Set with context1
        cache.set(text, context1, sample_intent)

        # Get with context2 (different order) - should hit
        cached = cache.get(text, context2)

        assert cached is not None  # nosec B101

    def test_performance_target(self, cache, sample_intent):
        """Test cache lookup performance (<1ms target)."""
        text = "set timer for 5 minutes"

        # Set intent
        cache.set(text, None, sample_intent)

        # Measure get performance
        start = time.perf_counter()
        for _ in range(1000):
            cache.get(text, None)
        end = time.perf_counter()

        avg_latency_ms = ((end - start) / 1000) * 1000

        # Should be <1ms per lookup
        assert avg_latency_ms < 1.0, f"Cache lookup too slow: {avg_latency_ms:.3f}ms"  # nosec B101

    def test_hit_rate_target(self, cache, sample_intent):
        """Test cache hit rate meets >60% target."""
        # Simulate realistic usage pattern
        common_queries = [
            "set timer for 5 minutes",
            "what's the weather",
            "play music",
            "set alarm for 7am",
            "send message to john",
        ]

        # Add common queries to cache
        for query in common_queries:
            cache.set(query, None, sample_intent)

        # Simulate requests (70% common, 30% unique)
        for i in range(100):
            if i % 10 < 7:  # 70% common queries
                query = common_queries[i % len(common_queries)]
            else:  # 30% unique queries
                query = f"unique query {i}"

            cache.get(query, None)

        hit_rate = cache.stats.get_hit_rate()

        # Should meet >60% target
        assert hit_rate > 60.0, f"Hit rate below target: {hit_rate:.1f}%"  # nosec B101


class TestCachedIntent:
    """Tests for CachedIntent dataclass."""

    def test_creation(self, sample_intent):
        """Test CachedIntent creation."""
        entry = CachedIntent(
            intent=sample_intent,
            cache_key="test_key",
            created_at=datetime.now(tz=timezone.utc),
            last_accessed=datetime.now(tz=timezone.utc),
            context_hash="context_hash",
        )

        assert entry.intent == sample_intent  # nosec B101
        assert entry.cache_key == "test_key"  # nosec B101
        assert entry.access_count == 0  # nosec B101

    def test_update_access(self, sample_intent):
        """Test access tracking."""
        entry = CachedIntent(
            intent=sample_intent,
            cache_key="test_key",
            created_at=datetime.now(tz=timezone.utc),
            last_accessed=datetime.now(tz=timezone.utc),
        )

        initial_time = entry.last_accessed

        # Wait a bit
        time.sleep(0.01)

        # Update access
        entry.update_access()

        assert entry.access_count == 1  # nosec B101
        assert entry.last_accessed > initial_time  # nosec B101


class TestIntentCacheStats:
    """Tests for IntentCacheStats."""

    def test_initialization(self):
        """Test stats initialization."""
        stats = IntentCacheStats()

        assert stats.total_requests == 0  # nosec B101
        assert stats.cache_hits == 0  # nosec B101
        assert stats.cache_misses == 0  # nosec B101
        assert stats.get_hit_rate() == 0.0  # nosec B101

    def test_record_hit(self):
        """Test recording cache hit."""
        stats = IntentCacheStats()

        stats.record_hit()

        assert stats.total_requests == 1  # nosec B101
        assert stats.cache_hits == 1  # nosec B101
        assert stats.get_hit_rate() == 100.0  # nosec B101

    def test_record_miss(self):
        """Test recording cache miss."""
        stats = IntentCacheStats()

        stats.record_miss()

        assert stats.total_requests == 1  # nosec B101
        assert stats.cache_misses == 1  # nosec B101
        assert stats.get_hit_rate() == 0.0  # nosec B101

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = IntentCacheStats()

        # 7 hits, 3 misses = 70% hit rate
        for _ in range(7):
            stats.record_hit()
        for _ in range(3):
            stats.record_miss()

        assert stats.get_hit_rate() == 70.0  # nosec B101

    def test_get_stats(self):
        """Test getting statistics dictionary."""
        stats = IntentCacheStats()

        stats.record_hit()
        stats.record_miss()
        stats.record_context_invalidation()
        stats.record_ttl_expiration()
        stats.record_eviction()

        stats_dict = stats.get_stats()

        assert stats_dict["total_requests"] == 2  # nosec B101
        assert stats_dict["cache_hits"] == 1  # nosec B101
        assert stats_dict["cache_misses"] == 1  # nosec B101
        assert stats_dict["hit_rate_percent"] == 50.0  # nosec B101
        assert stats_dict["context_invalidations"] == 1  # nosec B101
        assert stats_dict["ttl_expirations"] == 1  # nosec B101
        assert stats_dict["evictions"] == 1  # nosec B101
        assert "last_reset" in stats_dict  # nosec B101
