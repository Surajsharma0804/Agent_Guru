"""TurnTraceStore keeps each turn's record and gives it back as it was stored."""

from __future__ import annotations

import sqlite3
import threading

import pytest

from Agent_Guru.integration.turn_trace import StageTiming, TurnRecord, TurnTraceStore


@pytest.fixture
def store(tmp_path):
    return TurnTraceStore(tmp_path / "turns.db")


def _turn(heard="what time is it", said="It's three.", personality="guru", outcome=None, started_at=100.0,
          stages=()):
    return TurnRecord(
        started_at=started_at, seconds=1.5, personality=personality, heard=heard, said=said,
        intent="system_control:time", outcome=outcome, details={"error": None},
        stages=[StageTiming(name=n, started_at=started_at, seconds=s, detail={"n": 1}) for n, s in stages],
    )


def test_a_recorded_turn_comes_back_with_its_stages_in_order(store):
    turn = _turn(stages=[("stt", 0.8), ("intent", 0.01), ("answer_spoken", 4.2)])
    store.record(turn)
    got = store.get(turn.turn_id)
    assert got == turn  # nosec B101


def test_an_unknown_turn_is_none(store):
    assert store.get("nope") is None  # nosec B101


def test_one_turn_cannot_be_recorded_twice(store):
    turn = _turn()
    store.record(turn)
    with pytest.raises(sqlite3.IntegrityError):
        store.record(turn)
    assert store.count() == 1  # nosec B101


def test_recent_turns_come_newest_first_and_can_be_narrowed(store):
    store.record(_turn(personality="guru", outcome="success", started_at=1.0))
    store.record(_turn(personality="maya", outcome="failure", started_at=2.0))
    store.record(_turn(personality="guru", outcome="failure", started_at=3.0))
    assert [t.started_at for t in store.recent()] == [3.0, 2.0, 1.0]  # nosec B101
    assert [t.started_at for t in store.recent(personality="guru")] == [3.0, 1.0]  # nosec B101
    assert [t.started_at for t in store.recent(outcome="failure", since=2.5)] == [3.0]  # nosec B101
    assert len(store.recent(limit=2)) == 2  # nosec B101


def test_find_searches_what_was_heard_and_said_and_takes_punctuation_as_text(store):
    store.record(_turn(heard="open notepad", said="Opening notepad for you!"))
    store.record(_turn(heard="what's the weather", said="Sunny."))
    assert [t.heard for t in store.find("notepad")] == ["open notepad"]  # nosec B101
    # FTS5 syntax typed by the user is searched for, not run: quotes, OR, brackets.
    assert [t.heard for t in store.find('sunny" OR (x')] == ["what's the weather"]  # nosec B101
    assert store.find("!!!") == []  # nosec B101


def test_a_turn_can_be_rated_between_0_and_1(store):
    turn = _turn()
    store.record(turn)
    assert store.rate(turn.turn_id, 0.25) is True and store.get(turn.turn_id).rating == 0.25  # nosec B101
    assert store.rate("nope", 1.0) is False  # nosec B101
    with pytest.raises(ValueError, match="between 0 and 1"):
        store.rate(turn.turn_id, 5)


def test_turns_recorded_from_many_threads_all_land(store):
    # Turns are recorded through asyncio.to_thread, from worker threads.
    errors = []

    def record_some():
        try:
            for _ in range(25):
                store.record(_turn(stages=[("stt", 0.1)]))
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=record_some) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == [] and store.count() == 100  # nosec B101


def test_turns_survive_reopening_and_the_file_is_not_held_open(tmp_path):
    path = tmp_path / "turns.db"
    turn = _turn()
    TurnTraceStore(path).record(turn)
    assert TurnTraceStore(path).get(turn.turn_id).heard == "what time is it"  # nosec B101
    # A connection kept open would lock the file on Windows for the life of the app.
    path.unlink()


def test_the_file_is_restricted_to_its_owner(tmp_path, monkeypatch):
    restricted = []
    monkeypatch.setattr("Agent_Guru.integration.turn_trace.restrict_file_permissions", restricted.append)
    TurnTraceStore(tmp_path / "turns.db")
    assert restricted == [tmp_path / "turns.db"]  # nosec B101
