"""
Tests for Prompt Caching System.

Tests cache operations, LRU eviction, TTL expiration, and statistics tracking.

Coverage Target: 80%+
"""

import time

import pytest

from Agent_Guru.reasoning.llm.prompt_cache import CacheStats, PromptCache

# ============================================================================
# Initialization Tests
# ============================================================================


class TestInitialization:
    """Tests for cache initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        cache = PromptCache()

        assert cache.max_size == 1000  # nosec B101
        assert cache.ttl_seconds == 300.0  # nosec B101
        assert cache.get_size() == 0  # nosec B101

    def test_init_with_custom_size(self):
        """Test initialization with custom max size."""
        cache = PromptCache(max_size=500)

        assert cache.max_size == 500  # nosec B101

    def test_init_with_no_ttl(self):
        """Test initialization with no TTL."""
        cache = PromptCache(ttl_seconds=None)

        assert cache.ttl_seconds is None  # nosec B101

    def test_init_with_invalid_size(self):
        """Test initialization with invalid size fails."""
        with pytest.raises(ValueError, match="max_size must be positive"):
            PromptCache(max_size=0)

        with pytest.raises(ValueError, match="max_size must be positive"):
            PromptCache(max_size=-1)


# ============================================================================
# Cache Operations Tests
# ============================================================================


class TestCacheOperations:
    """Tests for basic cache operations."""

    def test_set_and_get(self):
        """Test setting and getting cached prompt."""
        cache = PromptCache()
        cache.set("set_timer", "context1", "Timer prompt template")

        prompt = cache.get("set_timer", "context1")
        assert prompt == "Timer prompt template"  # nosec B101

    def test_get_nonexistent(self):
        """Test getting nonexistent prompt returns None."""
        cache = PromptCache()

        prompt = cache.get("nonexistent", "context")
        assert prompt is None  # nosec B101

    def test_set_updates_existing(self):
        """Test setting existing key updates the entry."""
        cache = PromptCache()
        cache.set("set_timer", "context1", "Old prompt")
        cache.set("set_timer", "context1", "New prompt")

        prompt = cache.get("set_timer", "context1")
        assert prompt == "New prompt"  # nosec B101

    def test_different_contexts_different_keys(self):
        """Test different contexts create different cache keys."""
        cache = PromptCache()
        cache.set("set_timer", "context1", "Prompt 1")
        cache.set("set_timer", "context2", "Prompt 2")

        prompt1 = cache.get("set_timer", "context1")
        prompt2 = cache.get("set_timer", "context2")

        assert prompt1 == "Prompt 1"  # nosec B101
        assert prompt2 == "Prompt 2"  # nosec B101

    def test_invalidate_existing(self):
        """Test invalidating existing entry."""
        cache = PromptCache()
        cache.set("set_timer", "context1", "Prompt")

        result = cache.invalidate("set_timer", "context1")
        assert result is True  # nosec B101

        prompt = cache.get("set_timer", "context1")
        assert prompt is None  # nosec B101

    def test_invalidate_nonexistent(self):
        """Test invalidating nonexistent entry."""
        cache = PromptCache()

        result = cache.invalidate("nonexistent", "context")
        assert result is False  # nosec B101

    def test_clear(self):
        """Test clearing all cache entries."""
        cache = PromptCache()
        cache.set("intent1", "context1", "Prompt 1")
        cache.set("intent2", "context2", "Prompt 2")

        cache.clear()

        assert cache.get_size() == 0  # nosec B101
        assert cache.get("intent1", "context1") is None  # nosec B101
        assert cache.get("intent2", "context2") is None  # nosec B101

    def test_get_size(self):
        """Test getting cache size."""
        cache = PromptCache()

        assert cache.get_size() == 0  # nosec B101

        cache.set("intent1", "context1", "Prompt 1")
        assert cache.get_size() == 1  # nosec B101

        cache.set("intent2", "context2", "Prompt 2")
        assert cache.get_size() == 2  # nosec B101


# ============================================================================
# LRU Eviction Tests
# ============================================================================


class TestLRUEviction:
    """Tests for LRU eviction."""

    def test_evict_lru_when_full(self):
        """Test LRU eviction when cache is full."""
        cache = PromptCache(max_size=3)

        # Fill cache
        cache.set("intent1", "context1", "Prompt 1")
        cache.set("intent2", "context2", "Prompt 2")
        cache.set("intent3", "context3", "Prompt 3")

        # Add one more (should evict intent1)
        cache.set("intent4", "context4", "Prompt 4")

        assert cache.get_size() == 3  # nosec B101
        assert cache.get("intent1", "context1") is None  # Evicted  # nosec B101
        assert cache.get("intent2", "context2") == "Prompt 2"  # nosec B101
        assert cache.get("intent3", "context3") == "Prompt 3"  # nosec B101
        assert cache.get("intent4", "context4") == "Prompt 4"  # nosec B101

    def test_access_updates_lru_order(self):
        """Test accessing entry updates LRU order."""
        cache = PromptCache(max_size=3)

        # Fill cache
        cache.set("intent1", "context1", "Prompt 1")
        cache.set("intent2", "context2", "Prompt 2")
        cache.set("intent3", "context3", "Prompt 3")

        # Access intent1 (moves to end)
        cache.get("intent1", "context1")

        # Add one more (should evict intent2, not intent1)
        cache.set("intent4", "context4", "Prompt 4")

        assert cache.get("intent1", "context1") == "Prompt 1"  # Not evicted  # nosec B101
        assert cache.get("intent2", "context2") is None  # Evicted  # nosec B101
        assert cache.get("intent3", "context3") == "Prompt 3"  # nosec B101
        assert cache.get("intent4", "context4") == "Prompt 4"  # nosec B101


# ============================================================================
# TTL Expiration Tests
# ============================================================================


class TestTTLExpiration:
    """Tests for TTL expiration."""

    def test_expired_entry_returns_none(self):
        """Test expired entry returns None."""
        cache = PromptCache(ttl_seconds=0.1)  # 100ms TTL
        cache.set("intent1", "context1", "Prompt 1")

        # Wait for expiration
        time.sleep(0.15)

        prompt = cache.get("intent1", "context1")
        assert prompt is None  # nosec B101

    def test_non_expired_entry_returns_value(self):
        """Test non-expired entry returns value."""
        cache = PromptCache(ttl_seconds=1.0)  # 1s TTL
        cache.set("intent1", "context1", "Prompt 1")

        # Access immediately
        prompt = cache.get("intent1", "context1")
        assert prompt == "Prompt 1"  # nosec B101

    def test_no_ttl_never_expires(self):
        """Test entries never expire when TTL is None."""
        cache = PromptCache(ttl_seconds=None)
        cache.set("intent1", "context1", "Prompt 1")

        # Wait a bit
        time.sleep(0.1)

        prompt = cache.get("intent1", "context1")
        assert prompt == "Prompt 1"  # nosec B101

    def test_expired_entries_evicted_on_set(self):
        """Test expired entries are evicted when setting new entry."""
        cache = PromptCache(max_size=10, ttl_seconds=0.1)

        # Add entries
        cache.set("intent1", "context1", "Prompt 1")
        cache.set("intent2", "context2", "Prompt 2")

        # Wait for expiration
        time.sleep(0.15)

        # Add new entry (should evict expired)
        cache.set("intent3", "context3", "Prompt 3")

        # Expired entries should be gone
        assert cache.get("intent1", "context1") is None  # nosec B101
        assert cache.get("intent2", "context2") is None  # nosec B101
        assert cache.get("intent3", "context3") == "Prompt 3"  # nosec B101


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Tests for cache statistics."""

    def test_stats_initialization(self):
        """Test statistics initialization."""
        stats = CacheStats()

        assert stats.total_requests == 0  # nosec B101
        assert stats.cache_hits == 0  # nosec B101
        assert stats.cache_misses == 0  # nosec B101
        assert stats.total_tokens_saved == 0  # nosec B101

    def test_record_hit(self):
        """Test recording cache hit."""
        stats = CacheStats()
        stats.record_hit(tokens_saved=100)

        assert stats.total_requests == 1  # nosec B101
        assert stats.cache_hits == 1  # nosec B101
        assert stats.total_tokens_saved == 100  # nosec B101

    def test_record_miss(self):
        """Test recording cache miss."""
        stats = CacheStats()
        stats.record_miss()

        assert stats.total_requests == 1  # nosec B101
        assert stats.cache_misses == 1  # nosec B101

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats()
        stats.record_hit(100)
        stats.record_hit(100)
        stats.record_miss()

        hit_rate = stats.get_hit_rate()
        assert hit_rate == pytest.approx(2 / 3)  # nosec B101

    def test_hit_rate_zero_requests(self):
        """Test hit rate with zero requests."""
        stats = CacheStats()

        hit_rate = stats.get_hit_rate()
        assert hit_rate == 0.0  # nosec B101

    def test_cache_tracks_hits_and_misses(self):
        """Test cache tracks hits and misses."""
        cache = PromptCache()
        cache.set("intent1", "context1", "Prompt 1", token_count=100)

        # Hit
        cache.get("intent1", "context1")

        # Miss
        cache.get("intent2", "context2")

        stats = cache.get_stats()
        assert stats["total_requests"] == 2  # nosec B101
        assert stats["cache_hits"] == 1  # nosec B101
        assert stats["cache_misses"] == 1  # nosec B101
        assert stats["hit_rate"] == 0.5  # nosec B101

    def test_token_savings_tracking(self):
        """Test token savings tracking."""
        cache = PromptCache()
        cache.set("intent1", "context1", "Prompt 1", token_count=100)

        # Multiple hits
        cache.get("intent1", "context1")
        cache.get("intent1", "context1")
        cache.get("intent1", "context1")

        stats = cache.get_stats()
        assert stats["total_tokens_saved"] == 300  # 3 hits * 100 tokens  # nosec B101

    def test_eviction_tracking(self):
        """Test eviction tracking."""
        cache = PromptCache(max_size=2)

        cache.set("intent1", "context1", "Prompt 1")
        cache.set("intent2", "context2", "Prompt 2")
        cache.set("intent3", "context3", "Prompt 3")  # Evicts intent1

        stats = cache.get_stats()
        assert stats["evictions"] == 1  # nosec B101

    def test_reset_stats(self):
        """Test resetting statistics."""
        cache = PromptCache()
        cache.set("intent1", "context1", "Prompt 1")
        cache.get("intent1", "context1")

        cache.reset_stats()

        stats = cache.get_stats()
        assert stats["total_requests"] == 0  # nosec B101
        assert stats["cache_hits"] == 0  # nosec B101


# ============================================================================
# Access Tracking Tests
# ============================================================================


class TestAccessTracking:
    """Tests for access tracking."""

    def test_access_count_increments(self):
        """Test access count increments on each get."""
        cache = PromptCache()
        cache.set("intent1", "context1", "Prompt 1")

        # Access multiple times
        cache.get("intent1", "context1")
        cache.get("intent1", "context1")
        cache.get("intent1", "context1")

        most_accessed = cache.get_most_accessed()
        assert len(most_accessed) == 1  # nosec B101
        assert most_accessed[0]["access_count"] == 3  # nosec B101

    def test_get_most_accessed(self):
        """Test getting most accessed entries."""
        cache = PromptCache()

        cache.set("intent1", "context1", "Prompt 1")
        cache.set("intent2", "context2", "Prompt 2")
        cache.set("intent3", "context3", "Prompt 3")

        # Access with different frequencies
        cache.get("intent1", "context1")  # 1 access
        cache.get("intent2", "context2")  # 2 accesses
        cache.get("intent2", "context2")
        cache.get("intent3", "context3")  # 3 accesses
        cache.get("intent3", "context3")
        cache.get("intent3", "context3")

        most_accessed = cache.get_most_accessed(limit=2)
        assert len(most_accessed) == 2  # nosec B101
        assert most_accessed[0]["access_count"] == 3  # intent3  # nosec B101
        assert most_accessed[1]["access_count"] == 2  # intent2  # nosec B101

    def test_metadata_storage(self):
        """Test metadata storage and retrieval."""
        cache = PromptCache()
        metadata = {"intent_type": "set_timer", "complexity": "simple"}

        cache.set("intent1", "context1", "Prompt 1", metadata=metadata)

        most_accessed = cache.get_most_accessed()
        assert most_accessed[0]["metadata"] == metadata  # nosec B101


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for cache."""

    def test_realistic_usage_pattern(self):
        """Test realistic usage pattern."""
        cache = PromptCache(max_size=100, ttl_seconds=60.0)

        # Simulate 1000 requests with 80% cache hit rate
        for i in range(1000):
            if i % 5 == 0:
                # 20% new intents (cache miss)
                cache.set(f"intent{i}", f"context{i}", f"Prompt {i}", token_count=500)
            else:
                # 80% repeated intents (cache hit)
                intent_id = (i // 5) * 5
                cache.get(f"intent{intent_id}", f"context{intent_id}")

        stats = cache.get_stats()

        # Should have ~80% hit rate
        assert stats["hit_rate"] >= 0.75  # nosec B101

        # Should have significant token savings
        assert stats["total_tokens_saved"] > 0  # nosec B101

    def test_cache_key_consistency(self):
        """Test cache key generation is consistent."""
        cache = PromptCache()

        # Set with same intent and context
        cache.set("intent1", "context1", "Prompt 1")

        # Get with same intent and context
        prompt1 = cache.get("intent1", "context1")
        prompt2 = cache.get("intent1", "context1")

        assert prompt1 == prompt2 == "Prompt 1"  # nosec B101
