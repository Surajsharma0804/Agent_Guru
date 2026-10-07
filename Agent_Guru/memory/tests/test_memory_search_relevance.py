"""MemoryManager.search returns only memories relevant to the query and new to the conversation.

It used to return the nearest 5 stored interactions whatever their score.
Every voice turn was handed 5 memories: unrelated ones (a question about the
Prime Minister came with "my doctor says my blood pressure is too high"),
and the session's own earlier turns, which the chat history already held
word for word. The block also differed on every turn, which stopped Ollama
reusing the previous turn's prompt processing.

Embeddings are replaced with fixed vectors so each case sets its own
similarities; the thresholds themselves were calibrated on the real
all-MiniLM-L6-v2 embedder (see RELEVANT_SIMILARITY in memory_manager.py).
"""

from __future__ import annotations

import math

import pytest

from Agent_Guru.memory import memory_manager
from Agent_Guru.memory.memory_manager import (
    REDUNDANT_SIMILARITY,
    RELEVANT_SIMILARITY,
    MemoryManager,
)

DIM = 8


def _at(similarity: float, axis: int = 1) -> list[float]:
    """A unit vector with the given cosine similarity to the query axis (axis 0)."""
    v = [0.0] * DIM
    v[0] = similarity
    v[axis] = math.sqrt(max(0.0, 1.0 - similarity * similarity))
    return v


QUERY = _at(1.0)


@pytest.fixture
def manager(monkeypatch):
    vectors: dict[str, list[float]] = {"what should I gift my sister": QUERY}

    async def embed(text: str) -> list[float]:
        return vectors[text]

    monkeypatch.setattr(memory_manager, "_embed_text_async", embed)
    mgr = MemoryManager(platform_override="test-platform")

    async def remember(user: str, ai: str, vector: list[float]) -> None:
        vectors[f"{user} {ai}"] = vector
        assert await mgr.store_interaction("GURU", user, ai)  # nosec B101

    mgr.remember = remember
    return mgr


async def _users(mgr, **kw) -> list[str]:
    return [r["user_message"] for r in await mgr.search("what should I gift my sister", **kw)]


async def test_a_relevant_memory_is_returned(manager):
    await manager.remember("my sister Priya is getting married in December", "congrats!", _at(0.35))
    assert await _users(manager) == ["my sister Priya is getting married in December"]  # nosec B101


async def test_an_unrelated_memory_is_not_returned_just_because_it_is_nearest(manager):
    # Before: the nearest 5 came back whatever their score, so a store with
    # nothing relevant still put its 5 closest, here a health detail, in the prompt.
    await manager.remember("my doctor says my blood pressure is too high", "let's watch it", _at(0.09, 2))
    await manager.remember("I started learning the guitar", "nice", _at(0.20, 3))
    assert await _users(manager) == []  # nosec B101


async def test_the_cutoff_is_the_calibrated_one(manager):
    await manager.remember("just above", "a", _at(RELEVANT_SIMILARITY + 0.01, 2))
    await manager.remember("just below", "b", _at(RELEVANT_SIMILARITY - 0.01, 3))
    assert await _users(manager) == ["just above"]  # nosec B101


async def test_a_turn_already_in_the_conversation_is_not_returned(manager):
    # The session's own turns are stored too, and came back as "memories"
    # of themselves beside the same turns in the chat history.
    await manager.remember("what should I gift my sister", "maybe a photo album", _at(0.9))
    await manager.remember("my sister Priya is getting married in December", "congrats!", _at(0.35, 2))
    known = [("what should I gift my sister", "maybe a photo album")]
    assert await _users(manager, known=known) == ["my sister Priya is getting married in December"]  # nosec B101


async def test_a_memory_that_repeats_a_known_turn_is_not_returned(manager):
    # An older session's answer to the same question, worded differently.
    said_now = _at(0.6, 2)
    repeat = [0.6, 0.0, 0.8 * REDUNDANT_SIMILARITY, 0.0, 0.0, 0.0, 0.0, 0.0]
    repeat[3] = math.sqrt(1.0 - sum(x * x for x in repeat))
    await manager.remember("my sister's wedding is next month", "so exciting!", said_now)
    await manager.remember("my sister Priya is getting married", "a December wedding!", repeat)
    await manager.remember("I want to buy something handmade", "a quilt is lovely", _at(0.5, 4))
    known = [("my sister's wedding is next month", "so exciting!")]
    assert memory_manager._cosine_similarity(repeat, said_now) >= REDUNDANT_SIMILARITY  # nosec B101
    assert await _users(manager, known=known) == ["I want to buy something handmade"]  # nosec B101


async def test_many_copies_of_a_known_turn_do_not_crowd_out_a_new_memory(manager):
    # The same question asked often leaves many near-identical stored turns.
    # Taking the top 5 first and then dropping repeats would return nothing.
    known_vec = _at(0.8, 2)
    await manager.remember("what should I gift my sister", "a photo album", known_vec)
    for n in range(8):
        await manager.remember("what should I gift my sister", f"a photo album, take {n}", known_vec)
    await manager.remember("my sister loves pottery", "a pottery class then!", _at(0.4, 3))
    known = [("what should I gift my sister", "a photo album")]
    assert await _users(manager, known=known) == ["my sister loves pottery"]  # nosec B101


async def test_results_are_bounded_and_best_first(manager):
    for n, score in enumerate((0.3, 0.9, 0.5, 0.7, 0.4, 0.6, 0.8)):
        await manager.remember(f"m{score}", "r", _at(score, 1 + n % (DIM - 1)))
    assert await _users(manager, limit=3) == ["m0.9", "m0.8", "m0.7"]  # nosec B101


async def test_a_memory_not_returned_now_is_still_stored_and_found_later(manager):
    await manager.remember("my sister Priya is getting married in December", "congrats!", _at(0.35))
    known = [("my sister Priya is getting married in December", "congrats!")]
    assert await _users(manager, known=known) == []  # nosec B101
    assert manager.interaction_count() == 1  # nosec B101
    assert await _users(manager) == ["my sister Priya is getting married in December"]  # nosec B101


async def test_an_empty_store_returns_nothing(manager):
    assert await _users(manager, known=[("a", "b")]) == []  # nosec B101


# ---- names in the query ----
# Scores below are the real all-MiniLM-L6-v2 ones from
# scripts/memory_recall_eval.py, set here as fixed vectors.

@pytest.fixture
def named(monkeypatch):
    vectors: dict[str, list[float]] = {}

    async def embed(text: str) -> list[float]:
        return vectors.get(text, QUERY)

    monkeypatch.setattr(memory_manager, "_embed_text_async", embed)
    mgr = MemoryManager(platform_override="test-platform")

    async def remember(user: str, vector: list[float]) -> None:
        vectors[f"{user} ok"] = vector
        assert await mgr.store_interaction("GURU", user, "ok")  # nosec B101

    async def ask(query: str) -> list[str]:
        return [r["user_message"] for r in await mgr.search(query)]

    mgr.remember, mgr.ask = remember, ask
    return mgr


async def test_a_memory_holding_the_name_asked_about_is_found_under_the_cutoff(named):
    # Meaning alone scored "how is Bruno" 0.246 against the memory about him.
    await named.remember("I have a golden retriever called Bruno", _at(0.246))
    await named.remember("I started learning the guitar", _at(0.13, 2))
    assert await named.ask("How is Bruno") == ["I have a golden retriever called Bruno"]  # nosec B101
    assert await named.ask("how is bruno") == ["I have a golden retriever called Bruno"]  # nosec B101


async def test_a_neighbour_without_the_name_asked_about_is_dropped(named):
    # The locker code came back beside the train booking the number named.
    await named.remember("my train PNR is 4521876390", _at(0.37))
    await named.remember("the gym locker code is 7314", _at(0.326, 2))
    assert await named.ask("Is 4521876390 confirmed") == ["my train PNR is 4521876390"]  # nosec B101


async def test_names_of_things_never_mentioned_leave_the_cutoff_to_decide(named):
    # No memory mentions the Himalayas; the allergy is still worth knowing.
    await named.remember("I'm allergic to peanuts", _at(0.262))
    await named.remember("I started learning the guitar", _at(0.10, 2))
    assert await named.ask("Any snack ideas for my Himalaya hike") == ["I'm allergic to peanuts"]  # nosec B101


async def test_a_name_matches_only_as_a_whole_word(named):
    await named.remember("my sister Priya is getting married", _at(0.20))
    assert await named.ask("Is Priyanka Chopra in a new film") == []  # nosec B101


async def test_ordinary_words_and_short_numbers_are_not_names(named):
    # "Tell" starts the stored sentence and the query; 800 is arithmetic.
    await named.remember("Tell me a fun fact", _at(0.156))
    await named.remember("the plumber charged 800 rupees", _at(0.10, 2))
    assert await named.ask("Tell me about space") == []  # nosec B101
    assert await named.ask("What is 800 times 3") == []  # nosec B101


async def test_with_letter_frequency_embeddings_the_cutoffs_do_not_apply(monkeypatch):
    # Without sentence-transformers the stub puts any two texts at about
    # 0.75: the cutoffs would pass everything and drop every "repeat".
    monkeypatch.setattr(memory_manager, "_get_real_embedder", lambda: None)

    async def stub(text: str) -> list[float]:
        return memory_manager._stub_embed(text)

    monkeypatch.setattr(memory_manager, "_embed_text_async", stub)
    mgr = MemoryManager(platform_override="test-platform")
    await mgr.store_interaction("GURU", "I started learning the guitar", "nice")
    await mgr.store_interaction("GURU", "what is the capital of Japan", "Tokyo")
    found = await mgr.search("tell me a fun fact about space", known=[("what is the capital of Japan", "Tokyo")])
    assert [r["user_message"] for r in found] == ["I started learning the guitar"]  # nosec B101
