"""The retrieval threshold must let real memories through.

REGRESSION TEST for a defect that made long-term memory functionally dead.

security/embedding_auth.RETRIEVAL_THRESHOLD was 0.85 — a biometric-grade
number (BIOMETRIC_THRESHOLD is 0.97) applied to semantic search. Raw cosine
similarity between a short query and a stored sentence does not reach it:
measured against this project's own embedding model, "timer" scores 0.641
against "User set a timer for 5 minutes" and was discarded, while the
unrelated "User played music" scores 0.177. Recall at 0.85 was **0%** — the
assistant could recall a fact only if the user repeated it close to verbatim.

These tests are deliberately about END-TO-END RECALL rather than the constant
itself: they fail the same way if the threshold is raised again, if the
embedding model is swapped for one on a different scale, or if the filter
moves somewhere else in the pipeline.
"""

from __future__ import annotations

import pytest

from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.memory import Memory, MemoryType
from Agent_Guru.security.embedding_auth import (
    BIOMETRIC_THRESHOLD,
    RETRIEVAL_THRESHOLD,
)

# Building a MemoryRetriever/EmbeddingGenerator loads a 420 MB
# sentence-transformer. Warm it once per session, in fixture setup, so no
# individual test is charged the load inside its own timeout budget.
pytestmark = pytest.mark.usefixtures("warm_embedding_model")

USER = "user_calibration"

MEMORIES = [
    "User set a timer for 5 minutes",
    "User played music by Coldplay",
    "User asked to be reminded about the 3pm meeting",
    "User's sister is called Priya",
    "User's flight to Delhi is on Tuesday",
]

# (query, index of the memory it should retrieve)
QUERIES = [
    ("timer", 0),
    ("what music did I play", 1),
    ("my meeting", 2),
    ("who is priya", 3),
    ("when is my flight", 4),
]


@pytest.fixture(scope="module")
def retriever() -> MemoryRetriever:
    r = MemoryRetriever()
    for content in MEMORIES:
        r.store(Memory(memory_type=MemoryType.EPISODIC, content=content, user_id=USER))
    return r


def test_retrieval_threshold_is_not_a_biometric_threshold() -> None:
    """Semantic recall and identity verification are different problems."""
    assert RETRIEVAL_THRESHOLD < BIOMETRIC_THRESHOLD  # nosec B101
    assert RETRIEVAL_THRESHOLD <= 0.5, (  # nosec B101
        f"RETRIEVAL_THRESHOLD is {RETRIEVAL_THRESHOLD}. Raw cosine similarity "
        "between a short query and a stored sentence sits around 0.3-0.7 for "
        "this model, so anything above ~0.5 starts silently discarding real "
        "memories. It was 0.85, at which recall was zero."
    )


@pytest.mark.parametrize(("query", "expected_index"), QUERIES)
def test_real_queries_retrieve_something(
    retriever: MemoryRetriever, query: str, expected_index: int
) -> None:
    """Every one of these returned an EMPTY list before the fix."""
    results = retriever.semantic_search(query, user_id=USER, top_k=3)

    assert results, (  # nosec B101
        f"semantic_search({query!r}) returned nothing. The memory is stored "
        f"and the model scores it well above the noise floor; the threshold "
        f"is discarding it."
    )
    assert results[0].content == MEMORIES[expected_index], (  # nosec B101
        f"{query!r} ranked {results[0].content!r} first, expected "
        f"{MEMORIES[expected_index]!r}"
    )


def test_unrelated_query_does_not_match_everything(
    retriever: MemoryRetriever,
) -> None:
    """Lowering the threshold must not turn retrieval into "return all"."""
    results = retriever.semantic_search(
        "quantum chromodynamics lattice gauge theory",
        user_id=USER,
        top_k=len(MEMORIES),
    )

    assert len(results) < len(MEMORIES), (  # nosec B101
        "A query unrelated to every stored memory matched all of them. The "
        "threshold is now too low to reject noise."
    )


def test_ranking_uses_semantics_not_just_recency(
    retriever: MemoryRetriever,
) -> None:
    """rank_memories() scored 0.0 for any memory whose embedding was absent.

    store() embeds its own copy, not the caller's object, so the obvious usage
    — store it, then rank it — left every semantic score at zero and the order
    was decided by microseconds of timestamp difference.
    """
    stored = list(retriever.memories.values())
    originals = [
        Memory(memory_type=m.memory_type, content=m.content, user_id=m.user_id)
        for m in stored
    ]
    for original in originals:
        retriever.store(original)

    ranked = retriever.rank_memories(originals, "timer")

    assert "timer" in ranked[0].content.lower(), (  # nosec B101
        f"Ranking for 'timer' put {ranked[0].content!r} first. Semantic "
        "similarity is not reaching the score."
    )
