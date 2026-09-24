"""Regression tests for MemoryRetriever's storage growth behaviour.

MemoryRetriever.store() used to append to its embedding matrix with
``np.vstack([self.embeddings, row])``, which reallocates and copies the whole
matrix on every insert. Storing n memories was O(n^2) - measured, with
embeddings supplied so only the array work was timed:

    stores     1- 1000:  0.190s  (0.190 ms/store)
    stores  1001- 2000:  1.501s  (1.501 ms/store)
    stores  2001- 4000:  6.151s  (3.076 ms/store)
    stores  4001- 8000: 22.384s  (5.596 ms/store)

- per-store cost rising linearly with n. After switching to a
capacity-doubling buffer the same 8,000 stores take 0.26s with a flat
~0.03 ms/store.

For a companion that accumulates memories over months this is the difference
between memory storage being free and it dominating the write path, so the
behaviour is pinned here rather than left to be re-broken silently.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.memory import EpisodicMemory

# Building a MemoryRetriever/EmbeddingGenerator loads a 420 MB
# sentence-transformer. Warm it once per session, in fixture setup, so no
# individual test is charged the load inside its own timeout budget.
pytestmark = pytest.mark.usefixtures("warm_embedding_model")

EMBEDDING_DIM = 768


def _memory(index: int, *, user_id: str = "user_scaling", with_embedding: bool = True):
    """Build a memory, optionally with a pre-computed embedding.

    Supplying the embedding keeps these tests measuring the STORAGE path and
    not sentence-transformer inference.
    """
    embedding = None
    if with_embedding:
        rng = np.random.default_rng(index)
        embedding = rng.random(EMBEDDING_DIM, dtype=np.float32).tolist()
    return EpisodicMemory(
        content=f"Memory {index} about cooking pasta",
        action_taken="test_action",
        result="Success",
        success=True,
        user_id=user_id,
        embedding=embedding,
    )


@pytest.fixture
def retriever() -> MemoryRetriever:
    return MemoryRetriever()


class TestStoreScaling:
    """store() must be amortised O(1), not O(n), per insert."""

    def test_embeddings_is_a_view_of_a_capacity_buffer(self, retriever: MemoryRetriever):
        """The structural invariant behind amortised growth.

        This is the timing-free half of the guard: with a capacity-doubling
        arena, `self.embeddings` is a VIEW of the first n rows of a buffer that
        is at least as tall as n and grows geometrically. A reintroduced
        `np.vstack` append would produce a freshly allocated array each time,
        whose capacity always equals its length and whose `.base` is None.
        """
        for i in range(37):  # not a power of two: capacity must exceed length
            retriever.store(_memory(i))

        assert retriever.embeddings is not None  # nosec B101
        assert retriever.embeddings.shape[0] == 37  # nosec B101
        assert retriever.embeddings.base is not None, (  # nosec B101
            "embeddings should be a view into the growth buffer, not a fresh "
            "array reallocated on every append"
        )
        buffer = retriever._embedding_buffer
        assert buffer is not None  # nosec B101
        assert buffer.shape[0] > 37, (  # nosec B101
            f"buffer capacity {buffer.shape[0]} == length: no spare room means "
            f"every append reallocates"
        )

    def test_per_store_cost_does_not_grow_with_size(self, retriever: MemoryRetriever):
        """The second half of a run must not be much slower than the first.

        For a strictly quadratic append the work in the second half of n
        inserts is exactly 3x the first half; for an amortised O(1) append it
        is 1x. Measured here: ~3.6x before the fix, ~1.1x after. The 2.0
        threshold sits between those two regimes with margin on both sides,
        and the structural test above catches the same regression without
        depending on wall-clock at all.
        """
        total = 4000
        half = total // 2
        memories = [_memory(i) for i in range(total)]

        start = time.perf_counter()
        for memory in memories[:half]:
            retriever.store(memory)
        first_half = time.perf_counter() - start

        start = time.perf_counter()
        for memory in memories[half:]:
            retriever.store(memory)
        second_half = time.perf_counter() - start

        # Guard against a clock so coarse that both halves measure ~0.
        assert first_half > 0.0  # nosec B101
        ratio = second_half / first_half
        assert ratio < 2.0, (  # nosec B101
            f"per-store cost grew {ratio:.1f}x between the first and second "
            f"half ({first_half:.3f}s then {second_half:.3f}s) - the embedding "
            f"matrix is being copied on every append again"
        )

    def test_embeddings_matrix_stays_correct_while_growing(self, retriever: MemoryRetriever):
        """Every row must still be the right embedding, in insertion order."""
        memories = [_memory(i) for i in range(200)]
        for memory in memories:
            retriever.store(memory)

        assert retriever.embeddings is not None  # nosec B101
        assert retriever.embeddings.shape == (200, EMBEDDING_DIM)  # nosec B101
        assert retriever.embeddings.dtype == np.float32  # nosec B101
        for index in (0, 1, 99, 199):
            expected = np.array(memories[index].embedding, dtype=np.float32)
            assert np.allclose(retriever.embeddings[index], expected), index  # nosec B101

    def test_embeddings_length_tracks_memory_ids(self, retriever: MemoryRetriever):
        """A capacity buffer must never expose its unused rows."""
        for i in range(37):  # not a power of two: capacity != length
            retriever.store(_memory(i))

        assert len(retriever.memory_ids) == 37  # nosec B101
        assert retriever.embeddings.shape[0] == 37  # nosec B101

    def test_clear_resets_the_matrix(self, retriever: MemoryRetriever):
        for i in range(50):
            retriever.store(_memory(i))
        retriever.clear()

        assert retriever.embeddings is None  # nosec B101
        assert retriever.get_memory_count() == 0  # nosec B101

        # And storing again after a clear must still work.
        retriever.store(_memory(0))
        assert retriever.embeddings.shape == (1, EMBEDDING_DIM)  # nosec B101

    def test_delete_keeps_rows_aligned_with_ids(self, retriever: MemoryRetriever):
        """After a deletion, row i must still belong to memory_ids[i]."""
        memories = [_memory(i) for i in range(10)]
        for memory in memories:
            retriever.store(memory)

        retriever.delete_memory(memories[3].memory_id, "user_scaling")

        assert retriever.embeddings.shape[0] == len(retriever.memory_ids) == 9  # nosec B101
        for position, memory_id in enumerate(retriever.memory_ids):
            expected = np.array(retriever.memories[memory_id].embedding, dtype=np.float32)
            assert np.allclose(retriever.embeddings[position], expected), position  # nosec B101


class TestStoreMany:
    """store_many() batches embedding inference and keeps store()'s contract."""

    def test_stores_all_memories(self, retriever: MemoryRetriever):
        memories = [_memory(i, with_embedding=False) for i in range(25)]
        retriever.store_many(memories)

        assert retriever.get_memory_count() == 25  # nosec B101
        assert retriever.embeddings.shape == (25, EMBEDDING_DIM)  # nosec B101
        for memory in memories:
            assert memory.memory_id in retriever.memories  # nosec B101

    def test_empty_batch_is_a_no_op(self, retriever: MemoryRetriever):
        retriever.store_many([])
        assert retriever.get_memory_count() == 0  # nosec B101
        assert retriever.embeddings is None  # nosec B101

    def test_generates_embeddings_for_memories_without_one(self, retriever: MemoryRetriever):
        memories = [_memory(i, with_embedding=False) for i in range(4)]
        assert all(m.embedding is None for m in memories)  # nosec B101

        retriever.store_many(memories)

        stored = [retriever.memories[m.memory_id] for m in memories]
        assert all(s.embedding is not None for s in stored)  # nosec B101
        assert all(len(s.embedding) == EMBEDDING_DIM for s in stored)  # nosec B101

    def test_preserves_supplied_embeddings(self, retriever: MemoryRetriever):
        memories = [_memory(i) for i in range(5)]
        retriever.store_many(memories)

        for index, memory in enumerate(memories):
            expected = np.array(memory.embedding, dtype=np.float32)
            assert np.allclose(retriever.embeddings[index], expected), index  # nosec B101

    def test_rejects_a_duplicate_already_in_the_store(self, retriever: MemoryRetriever):
        memory = _memory(0)
        retriever.store(memory)

        with pytest.raises(ValueError, match="already exists"):
            retriever.store_many([_memory(1), memory])

        # The batch must be rejected atomically - no partial write.
        assert retriever.get_memory_count() == 1  # nosec B101
        assert retriever.embeddings.shape[0] == 1  # nosec B101

    def test_rejects_a_duplicate_within_the_batch(self, retriever: MemoryRetriever):
        memory = _memory(0)

        with pytest.raises(ValueError, match="already exists"):
            retriever.store_many([memory, memory])

        assert retriever.get_memory_count() == 0  # nosec B101

    def test_mixed_batch_of_embedded_and_unembedded(self, retriever: MemoryRetriever):
        memories = [
            _memory(0),
            _memory(1, with_embedding=False),
            _memory(2),
            _memory(3, with_embedding=False),
        ]
        retriever.store_many(memories)

        assert retriever.get_memory_count() == 4  # nosec B101
        assert retriever.embeddings.shape == (4, EMBEDDING_DIM)  # nosec B101
        # The pre-supplied rows must be untouched and in position.
        for index in (0, 2):
            expected = np.array(memories[index].embedding, dtype=np.float32)
            assert np.allclose(retriever.embeddings[index], expected), index  # nosec B101

    def test_batch_and_single_store_agree(self, retriever: MemoryRetriever):
        """Embedding a text in a batch must give the same vector as alone."""
        single = MemoryRetriever()
        batched = MemoryRetriever()

        texts = [_memory(i, with_embedding=False) for i in range(6)]
        for memory in texts:
            single.store(memory.model_copy(deep=True))
        batched.store_many([memory.model_copy(deep=True) for memory in texts])

        assert np.allclose(  # nosec B101
            single.embeddings, batched.embeddings, atol=1e-5,
        ), "batched inference must produce the same embeddings as one-at-a-time"
