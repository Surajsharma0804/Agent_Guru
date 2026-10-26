"""`learn rate`: go through the turns nobody rated and mark them, through TurnTraceStore.rate.

A turn could be rated only by voice, straight after its answer; the owner's 25 recorded turns had
no ratings, and the fine-tuning export keeps rated-right turns only. Every test here uses its own
temporary turns.db; nothing reads or rates the owner's.
"""

from __future__ import annotations

import pytest

from Agent_Guru.integration.turn_trace import TurnRecord, TurnTraceStore
from Agent_Guru.self_improvement import prompt_tuning
from Agent_Guru.self_improvement.turn_dataset import rate_turns


@pytest.fixture
def turns(tmp_path):
    store = TurnTraceStore(tmp_path / "turns.db")
    made = []
    for n, (heard, said) in enumerate([
        ("what is 17 times 23", "391."),
        ("capital of France", "Paris."),
        ("who won the match", "I'm not sure."),
    ]):
        record = TurnRecord(started_at=1_000.0 + n, seconds=1.0, personality="GURU", heard=heard, said=said)
        store.record(record)
        made.append(record)
    rated = TurnRecord(started_at=2_000.0, seconds=1.0, personality="GURU", heard="hello", said="Hi.")
    store.record(rated)
    store.rate(rated.turn_id, 1.0)
    return tmp_path / "turns.db", store, made


def _answers(*replies):
    queue = list(replies)

    def ask(prompt):
        if not queue:
            raise EOFError
        return queue.pop(0)

    return ask


def _ratings(store, made):
    return [store.get(t.turn_id).rating for t in made]


def test_right_and_wrong_are_recorded(turns):
    path, store, made = turns
    # Newest first: "who won the match", then "capital of France", then "17 times 23".
    counts = rate_turns(source=path, ask=_answers("w", "r", "right"), say=lambda text: None)
    assert _ratings(store, made) == [1.0, 1.0, 0.0]  # nosec B101
    assert counts == {"right": 2, "wrong": 1, "skipped": 0, "remaining": 0}  # nosec B101


def test_skip_leaves_the_turn_unrated(turns):
    path, store, made = turns
    counts = rate_turns(source=path, ask=_answers("s", "r", "s"), say=lambda text: None)
    assert _ratings(store, made) == [None, 1.0, None]  # nosec B101
    assert counts["skipped"] == 2 and counts["remaining"] == 2  # nosec B101


def test_quit_stops_and_keeps_what_was_marked(turns):
    path, store, made = turns
    said = []
    counts = rate_turns(source=path, ask=_answers("w", "q"), say=said.append)
    assert _ratings(store, made) == [None, None, 0.0]  # nosec B101
    assert counts["remaining"] == 2 and "2 turns are still not rated" in said[-1]  # nosec B101


def test_an_unknown_answer_is_asked_again(turns):
    path, store, made = turns
    rate_turns(source=path, ask=_answers("yes", "r", "q"), say=lambda text: None)
    assert _ratings(store, made)[2] == 1.0  # nosec B101


def test_the_already_rated_turn_is_not_shown(turns):
    path, _, _ = turns
    said = []
    rate_turns(source=path, ask=_answers(), say=said.append)
    assert said[0].startswith("3 turns are not rated") and not any("You: hello" in s for s in said)  # nosec B101


def test_nothing_to_rate(tmp_path):
    said = []
    assert rate_turns(source=tmp_path / "none.db", ask=_answers(), say=said.append)["remaining"] == 0  # nosec B101
    assert said == ["No turns have been recorded yet."]  # nosec B101
    store = TurnTraceStore(tmp_path / "turns.db")
    record = TurnRecord(started_at=1.0, seconds=1.0, personality="GURU", heard="hi", said="Hello.")
    store.record(record)
    store.rate(record.turn_id, 0.0)
    said.clear()
    rate_turns(source=tmp_path / "turns.db", ask=_answers(), say=said.append)
    assert said == ["Every recorded turn is rated already."]  # nosec B101


def test_limit_shows_only_that_many(turns, monkeypatch, capsys):
    path, store, made = turns
    monkeypatch.setattr("Agent_Guru.utils.path_utils.app_data_dir", lambda *parts, **kw: path)
    replies = iter(["r", "r", "r"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(replies))
    assert prompt_tuning.run(["rate", "--limit", "1"]) == 0  # nosec B101
    out = capsys.readouterr().out
    assert "Going through 1" in out and "[1 of 1]" in out and "[2 of" not in out  # nosec B101
    assert _ratings(store, made) == [None, None, 1.0]  # nosec B101


def test_limit_must_be_positive(capsys):
    with pytest.raises(SystemExit):
        prompt_tuning.run(["rate", "--limit", "0"])
    assert "must be 1 or more" in capsys.readouterr().err  # nosec B101
