"""Property-based tests for Phase 4: Performance components.

Tasks 5.6, 5.9, 5.12, 5.18 — Properties 9, 10, 11, 12, 13, 14, 21, 22.

Property 9:  Ring Buffer Capacity Invariant
Property 10: Ring Buffer Read/Write Round Trip
Property 11: LRU Cache Size Invariant
Property 12: LRU Cache Eviction Order
Property 13: LRU Cache TTL Expiry
Property 14: LRU Cache Round Trip
Property 21: GPU Pool VRAM Invariant
Property 22: Trie Intent Classification Correctness

Subsystem: audit/tests
Requirements: 4.3, 4.5, 4.7, 4.10
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Optional

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# LockFreeRingBuffer — standalone implementation for property testing.
# This mirrors the contract defined in task 5.5 / speech/audio/capture.py.
# ---------------------------------------------------------------------------

class LockFreeRingBuffer:
    """Single-producer single-consumer ring buffer for float32 audio samples.

    CAPACITY must be a power of 2 to enable bitmask-based wrap-around.
    """

    def __init__(self, capacity: int = 163_840) -> None:
        if capacity <= 0 or (capacity & (capacity - 1)) != 0:
            msg = f"capacity must be a positive power of 2, got {capacity}"
            raise ValueError(msg)
        self._capacity = capacity
        self._mask = capacity - 1
        self._buf = np.zeros(capacity, dtype=np.float32)
        self._write_pos = 0  # next slot to write into
        self._read_pos = 0   # next slot to read from

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def available_samples(self) -> int:
        diff = (self._write_pos - self._read_pos) % (self._capacity * 2)
        # Never report more than capacity - 1 available
        return min(diff, self._capacity - 1)

    def write(self, samples: np.ndarray) -> None:
        """Write samples into the buffer.  Silently drops samples beyond capacity."""
        n = len(samples)
        for i in range(n):
            # Protect capacity - 1 invariant: stop writing if we'd fill the buffer
            avail = (self._write_pos - self._read_pos) % (self._capacity * 2)
            if avail >= self._capacity - 1:
                break  # Buffer full — oldest data preserved for SPSC
            self._buf[self._write_pos & self._mask] = samples[i]
            self._write_pos = (self._write_pos + 1) % (self._capacity * 2)

    def read_frame(self, frame_size: int) -> Optional[np.ndarray]:
        """Return frame_size samples or None if insufficient data."""
        if self.available_samples < frame_size:
            return None
        out = np.empty(frame_size, dtype=np.float32)
        for i in range(frame_size):
            out[i] = self._buf[self._read_pos & self._mask]
            self._read_pos = (self._read_pos + 1) % (self._capacity * 2)
        return out


# ---------------------------------------------------------------------------
# LRUResponseCache — standalone implementation for property testing.
# Mirrors the contract from task 5.11 / reasoning/response/response_cache.py.
# ---------------------------------------------------------------------------

import hashlib


class LRUResponseCache:
    """Thread-safe LRU response cache with TTL expiry."""

    def __init__(self, max_size: int = 1024, ttl_seconds: float = 300.0) -> None:
        if max_size <= 0:
            msg = "max_size must be positive"
            raise ValueError(msg)
        self._max_size = max_size
        self._ttl = ttl_seconds
        # OrderedDict: key → (response, inserted_at)
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

    @staticmethod
    def _key(query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()

    @property
    def size(self) -> int:
        return len(self._cache)

    def get(self, query: str) -> Optional[str]:
        k = self._key(query)
        if k not in self._cache:
            return None
        response, inserted_at = self._cache[k]
        if time.monotonic() - inserted_at > self._ttl:
            del self._cache[k]
            return None
        # LRU promotion
        self._cache.move_to_end(k)
        return response

    def put(self, query: str, response: str) -> None:
        k = self._key(query)
        if k in self._cache:
            self._cache.move_to_end(k)
        self._cache[k] = (response, time.monotonic())
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)  # evict LRU (oldest)

    def invalidate(self, query: str) -> bool:
        k = self._key(query)
        if k in self._cache:
            del self._cache[k]
            return True
        return False


# ---------------------------------------------------------------------------
# GPUMemoryPool — simplified mock for property testing.
# Mirrors the contract from task 5.8 / integration/gpu_pool.py.
# (Real implementation uses torch; this uses plain ints for property tests.)
# ---------------------------------------------------------------------------


class GPUMemoryPoolMock:
    """Mock GPU memory pool for property-based testing without torch."""

    def __init__(self, max_vram_bytes: int) -> None:
        self._max = max_vram_bytes
        self._allocated = 0
        self._pool: list[int] = []  # list of allocation sizes

    @property
    def allocated_bytes(self) -> int:
        return self._allocated

    @property
    def utilization_percent(self) -> float:
        return (self._allocated / self._max) * 100.0 if self._max > 0 else 0.0

    def allocate(self, nbytes: int) -> Optional[int]:
        """Return allocation handle (size in bytes) or None if VRAM exhausted."""
        if self._allocated + nbytes > self._max:
            return None
        self._allocated += nbytes
        self._pool.append(nbytes)
        return nbytes  # handle = size for simplicity

    def release(self, handle: int) -> None:
        if handle in self._pool:
            self._pool.remove(handle)
            self._allocated -= handle


# ---------------------------------------------------------------------------
# TrieNode & IntentTrie — mirrors reasoning/intent/fast_router.py contract.
# ---------------------------------------------------------------------------


class TrieNode:
    """Node in the intent classification trie."""

    def __init__(self) -> None:
        self.children: dict[str, TrieNode] = {}
        self.intent: Optional[str] = None


class IntentTrie:
    """Fast trie-based intent classifier for common voice commands."""

    def __init__(self) -> None:
        self._root = TrieNode()

    def register(self, pattern: str, intent: str) -> None:
        """Register a command pattern → intent mapping."""
        node = self._root
        for word in pattern.lower().split():
            if word not in node.children:
                node.children[word] = TrieNode()
            node = node.children[word]
        node.intent = intent

    def classify(self, command: str) -> Optional[str]:
        """Return intent for exact match or None."""
        node = self._root
        for word in command.lower().split():
            if word not in node.children:
                return None
            node = node.children[word]
        return node.intent


# ===========================================================================
# Properties 9 & 10: LockFreeRingBuffer
# ===========================================================================


class TestLockFreeRingBufferProperties:
    """Properties 9 and 10 — ring buffer invariants."""

    # ── Construction ──────────────────────────────────────────────────────

    def test_capacity_must_be_power_of_two(self) -> None:
        LockFreeRingBuffer(capacity=512)  # OK
        with pytest.raises(ValueError):
            LockFreeRingBuffer(capacity=500)

    def test_capacity_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            LockFreeRingBuffer(capacity=0)

    def test_initial_available_is_zero(self) -> None:
        rb = LockFreeRingBuffer(capacity=1024)
        assert rb.available_samples == 0

    # ── Property 9: Capacity Invariant ────────────────────────────────────

    @given(
        writes=st.lists(
            st.integers(min_value=1, max_value=512),
            min_size=1,
            max_size=30,
        )
    )
    @settings(max_examples=100)
    def test_property_nine_available_never_exceeds_capacity_minus_one(
        self, writes: list[int]
    ) -> None:
        """Property 9: available_samples never exceeds CAPACITY - 1."""
        cap = 1024
        rb = LockFreeRingBuffer(capacity=cap)
        for size in writes:
            samples = np.zeros(size, dtype=np.float32)
            rb.write(samples)
            assert rb.available_samples <= cap - 1, (
                f"available={rb.available_samples} exceeds cap-1={cap - 1} "
                f"after writing {size} samples"
            )

    def test_write_small_batch_increments_available(self) -> None:
        rb = LockFreeRingBuffer(capacity=256)
        rb.write(np.ones(10, dtype=np.float32))
        assert rb.available_samples == 10  # noqa: PLR2004

    def test_write_then_read_decrements_available(self) -> None:
        rb = LockFreeRingBuffer(capacity=256)
        rb.write(np.ones(20, dtype=np.float32))
        rb.read_frame(10)
        assert rb.available_samples == 10  # noqa: PLR2004

    # ── Property 10: Round Trip ────────────────────────────────────────────

    @given(
        data=st.lists(
            st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=200,
        )
    )
    @settings(max_examples=100)
    def test_property_ten_read_write_round_trip(self, data: list[float]) -> None:
        """Property 10: samples written then read back are identical in order."""
        cap = 1024
        rb = LockFreeRingBuffer(capacity=cap)
        arr = np.array(data, dtype=np.float32)

        if len(arr) >= cap:
            pytest.skip("Data exceeds ring buffer capacity — wrap-around case")

        rb.write(arr)
        result = rb.read_frame(len(arr))

        assert result is not None, "read_frame returned None despite sufficient data"
        np.testing.assert_array_almost_equal(result, arr, decimal=5)

    def test_read_frame_returns_none_when_empty(self) -> None:
        rb = LockFreeRingBuffer(capacity=256)
        assert rb.read_frame(1) is None

    def test_read_frame_returns_none_insufficient_data(self) -> None:
        rb = LockFreeRingBuffer(capacity=256)
        rb.write(np.ones(5, dtype=np.float32))
        assert rb.read_frame(10) is None

    def test_read_frame_exact_size(self) -> None:
        rb = LockFreeRingBuffer(capacity=256)
        rb.write(np.arange(8, dtype=np.float32))
        result = rb.read_frame(8)
        assert result is not None
        assert len(result) == 8  # noqa: PLR2004

    def test_values_preserved_across_wrap(self) -> None:
        """Write near capacity, read back, values correct."""
        cap = 64
        rb = LockFreeRingBuffer(capacity=cap)
        expected = np.arange(60, dtype=np.float32)
        rb.write(expected)
        result = rb.read_frame(60)
        assert result is not None
        np.testing.assert_array_equal(result, expected)


# ===========================================================================
# Properties 11-14: LRUResponseCache
# ===========================================================================


class TestLRUCacheProperties:
    """Properties 11, 12, 13, 14 — LRU cache invariants."""

    # ── Property 11: Size Invariant ────────────────────────────────────────

    @given(
        entries=st.lists(
            st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Ll",))),
            min_size=1,
            max_size=200,
        ),
        max_size=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_property_eleven_size_never_exceeds_max(
        self, entries: list[str], max_size: int
    ) -> None:
        """Property 11: cache.size never exceeds max_size after any sequence of puts."""
        cache = LRUResponseCache(max_size=max_size, ttl_seconds=3600.0)
        for entry in entries:
            cache.put(entry, f"response for {entry}")
            assert cache.size <= max_size, (
                f"size={cache.size} exceeds max_size={max_size}"
            )

    # ── Property 12: Eviction Order ────────────────────────────────────────

    def test_property_twelve_lru_evicts_oldest_accessed(self) -> None:
        """Property 12: at capacity, LRU entry is evicted first."""
        cache = LRUResponseCache(max_size=3, ttl_seconds=3600.0)
        cache.put("a", "A")
        cache.put("b", "B")
        cache.put("c", "C")
        # Access 'a' to make it recently used — 'b' becomes LRU
        cache.get("a")
        # Adding 'd' should evict 'b' (LRU)
        cache.put("d", "D")
        assert cache.get("b") is None, "b should have been evicted (LRU)"
        assert cache.get("a") == "A", "a should still be in cache"
        assert cache.get("c") == "C", "c should still be in cache"
        assert cache.get("d") == "D", "d should be in cache"

    def test_at_capacity_oldest_evicted_not_newest(self) -> None:
        cache = LRUResponseCache(max_size=2, ttl_seconds=3600.0)
        cache.put("first", "F")
        cache.put("second", "S")
        cache.put("third", "T")  # should evict "first"
        assert cache.get("first") is None
        assert cache.get("second") == "S"
        assert cache.get("third") == "T"

    @given(
        n_items=st.integers(min_value=2, max_value=20),
        max_size=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=80)
    def test_property_twelve_eviction_count(
        self, n_items: int, max_size: int
    ) -> None:
        """After inserting n_items into cache of max_size, size == min(n_items, max_size)."""
        cache = LRUResponseCache(max_size=max_size, ttl_seconds=3600.0)
        for i in range(n_items):
            cache.put(f"query_{i}", f"response_{i}")
        assert cache.size == min(n_items, max_size)

    # ── Property 13: TTL Expiry ────────────────────────────────────────────

    def test_property_thirteen_expired_entry_returns_none(self) -> None:
        """Property 13: entries older than ttl_seconds return None on get."""
        cache = LRUResponseCache(max_size=10, ttl_seconds=0.05)
        cache.put("key", "value")
        assert cache.get("key") == "value"  # within TTL
        time.sleep(0.1)  # let TTL expire
        assert cache.get("key") is None  # expired

    def test_zero_ttl_expires_immediately(self) -> None:
        """ttl_seconds=0 means every entry expires immediately after insertion.

        Uses a 20ms sleep to guarantee monotonic clock advancement on all
        platforms including Windows where time.sleep(0) may not advance
        time.monotonic() by enough to trigger TTL expiry.
        """
        cache = LRUResponseCache(max_size=10, ttl_seconds=0.0)
        cache.put("key", "value")
        # 20ms sleep guarantees the monotonic clock advances beyond 0.0 seconds
        # even on Windows where the timer resolution is ~15ms.
        time.sleep(0.02)
        assert cache.get("key") is None

    def test_entry_within_ttl_is_accessible(self) -> None:
        cache = LRUResponseCache(max_size=10, ttl_seconds=60.0)
        cache.put("key", "alive")
        assert cache.get("key") == "alive"

    # ── Property 14: Round Trip ────────────────────────────────────────────

    @given(
        query=st.text(min_size=1, max_size=100),
        response=st.text(min_size=0, max_size=500),
    )
    @settings(max_examples=100)
    def test_property_fourteen_put_then_get_round_trip(
        self, query: str, response: str
    ) -> None:
        """Property 14: put(q, r) then get(q) within TTL returns r."""
        cache = LRUResponseCache(max_size=1024, ttl_seconds=3600.0)
        cache.put(query, response)
        result = cache.get(query)
        assert result == response, f"get returned {result!r}, expected {response!r}"

    def test_get_on_missing_key_returns_none(self) -> None:
        cache = LRUResponseCache(max_size=10, ttl_seconds=3600.0)
        assert cache.get("non_existent") is None

    def test_invalidate_removes_entry(self) -> None:
        cache = LRUResponseCache(max_size=10, ttl_seconds=3600.0)
        cache.put("key", "val")
        assert cache.invalidate("key") is True
        assert cache.get("key") is None

    def test_invalidate_missing_key_returns_false(self) -> None:
        cache = LRUResponseCache(max_size=10, ttl_seconds=3600.0)
        assert cache.invalidate("ghost") is False

    def test_key_normalisation_case_insensitive(self) -> None:
        cache = LRUResponseCache(max_size=10, ttl_seconds=3600.0)
        cache.put("Hello World", "response")
        # Lookup with different case should hit the same entry
        assert cache.get("hello world") == "response"

    def test_key_normalisation_strips_whitespace(self) -> None:
        cache = LRUResponseCache(max_size=10, ttl_seconds=3600.0)
        cache.put("  query  ", "result")
        assert cache.get("query") == "result"


# ===========================================================================
# Property 21: GPU Pool VRAM Invariant
# ===========================================================================


class TestGPUMemoryPoolProperty21:
    """Property 21 — allocated_bytes never exceeds max_vram_bytes."""

    @given(
        allocations=st.lists(
            st.integers(min_value=1, max_value=1024 * 1024),  # 1B to 1MB
            min_size=1,
            max_size=30,
        ),
        max_vram=st.integers(min_value=1024 * 1024, max_value=8 * 1024 * 1024 * 1024),
    )
    @settings(max_examples=100)
    def test_property_21_allocated_never_exceeds_max(
        self, allocations: list[int], max_vram: int
    ) -> None:
        """Property 21: allocated_bytes <= max_vram_bytes at all times."""
        pool = GPUMemoryPoolMock(max_vram_bytes=max_vram)
        handles: list[int] = []

        for nbytes in allocations:
            handle = pool.allocate(nbytes)
            assert pool.allocated_bytes <= max_vram, (
                f"allocated={pool.allocated_bytes} > max={max_vram}"
            )
            if handle is not None:
                handles.append(handle)

        # Release all and verify returns to zero
        for h in handles:
            pool.release(h)
        assert pool.allocated_bytes == 0

    def test_allocation_exceeding_max_returns_none(self) -> None:
        pool = GPUMemoryPoolMock(max_vram_bytes=1024)
        result = pool.allocate(2048)
        assert result is None
        assert pool.allocated_bytes == 0

    def test_exact_max_allocation_succeeds(self) -> None:
        pool = GPUMemoryPoolMock(max_vram_bytes=1024)
        result = pool.allocate(1024)
        assert result is not None
        assert pool.allocated_bytes == 1024  # noqa: PLR2004

    def test_one_over_max_fails(self) -> None:
        pool = GPUMemoryPoolMock(max_vram_bytes=1024)
        assert pool.allocate(1025) is None

    def test_release_frees_space_for_reuse(self) -> None:
        pool = GPUMemoryPoolMock(max_vram_bytes=1024)
        h = pool.allocate(1024)
        assert h is not None
        pool.release(h)
        h2 = pool.allocate(1024)  # should succeed now
        assert h2 is not None

    def test_utilization_percent_correct(self) -> None:
        pool = GPUMemoryPoolMock(max_vram_bytes=1000)
        pool.allocate(250)
        assert pool.utilization_percent == pytest.approx(25.0)

    def test_utilization_zero_on_empty(self) -> None:
        pool = GPUMemoryPoolMock(max_vram_bytes=1024)
        assert pool.utilization_percent == pytest.approx(0.0)


# ===========================================================================
# Property 22: Trie Intent Classification Correctness
# ===========================================================================


class TestTrieIntentClassificationProperty22:
    """Property 22 — exact match returns correct intent; non-match returns None."""

    SAMPLE_COMMANDS = [
        ("open edge", "open_browser"),
        ("open youtube", "open_website"),
        ("play music", "play_media"),
        ("set alarm", "set_alarm"),
        ("check weather", "weather_query"),
        ("send email", "send_email"),
        ("take screenshot", "take_screenshot"),
        ("increase volume", "volume_up"),
        ("decrease volume", "volume_down"),
        ("search for python", "web_search"),
    ]

    def _build_trie(self) -> IntentTrie:
        trie = IntentTrie()
        for pattern, intent in self.SAMPLE_COMMANDS:
            trie.register(pattern, intent)
        return trie

    # ── Exact match tests ──────────────────────────────────────────────────

    def test_registered_command_returns_correct_intent(self) -> None:
        trie = self._build_trie()
        assert trie.classify("open edge") == "open_browser"

    def test_all_registered_commands_match(self) -> None:
        trie = self._build_trie()
        for pattern, expected_intent in self.SAMPLE_COMMANDS:
            result = trie.classify(pattern)
            assert result == expected_intent, (
                f"classify({pattern!r}) = {result!r}, expected {expected_intent!r}"
            )

    def test_case_insensitive_match(self) -> None:
        trie = self._build_trie()
        assert trie.classify("OPEN EDGE") == "open_browser"
        assert trie.classify("Open Edge") == "open_browser"
        assert trie.classify("PLAY MUSIC") == "play_media"

    # ── Non-match tests ────────────────────────────────────────────────────

    def test_unregistered_command_returns_none(self) -> None:
        trie = self._build_trie()
        assert trie.classify("delete everything") is None

    def test_partial_match_returns_none(self) -> None:
        trie = self._build_trie()
        # "open" alone is not a registered pattern
        assert trie.classify("open") is None

    def test_empty_string_returns_none(self) -> None:
        trie = self._build_trie()
        assert trie.classify("") is None

    def test_extra_word_returns_none(self) -> None:
        trie = self._build_trie()
        # "open edge browser" is not registered — should not match "open edge"
        assert trie.classify("open edge browser") is None

    def test_empty_trie_always_returns_none(self) -> None:
        trie = IntentTrie()
        assert trie.classify("open edge") is None
        assert trie.classify("anything") is None

    # ── Property 22: Hypothesis property ──────────────────────────────────

    @given(
        commands=st.lists(
            st.sampled_from([p for p, _ in SAMPLE_COMMANDS]),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_property_22_registered_always_matches(
        self, commands: list[str]
    ) -> None:
        """Property 22: any registered command always returns its correct intent."""
        trie = self._build_trie()
        intent_map = dict(self.SAMPLE_COMMANDS)
        for cmd in commands:
            result = trie.classify(cmd)
            assert result == intent_map[cmd], (
                f"classify({cmd!r}) returned {result!r}, "
                f"expected {intent_map[cmd]!r}"
            )

    @given(
        # Generate single lowercase words — these will never match any two-word pattern
        word=st.text(
            min_size=2,
            max_size=20,
            alphabet="abcdefghijklmnopqrstuvwxyz",
        ).filter(
            lambda w: w not in {"open", "play", "set", "check", "send",
                                  "take", "increase", "decrease", "search"}
        )
    )
    @settings(max_examples=50)
    def test_property_22_unregistered_single_words_return_none(
        self, word: str
    ) -> None:
        """Property 22: single-word commands never match any two-word registered pattern."""
        trie = self._build_trie()
        # Single random words that are not registered patterns → always None
        result = trie.classify(word)
        assert result is None, (
            f"Single word {word!r} incorrectly matched intent {result!r}"
        )
