"""The fine-tuning export keeps answers known to be right, never refusals or bare acknowledgements.

A turn's outcome says the pipeline finished, not that the reply was right:
on the owner's records 3 of the 5 pairs the export kept were wrong (two
refusals and a bare "Done."). The turn records here are made for the test
in its own folder; the owner's turns.db is not read.
"""

from __future__ import annotations

import json
import time

import pytest

from Agent_Guru.integration.turn_trace import TurnRecord, TurnTraceStore
from Agent_Guru.self_improvement.turn_dataset import export

TURNS = [
    # heard, said, outcome, rating
    ("What's my locker code?", "Your gym locker code is 7314.", "success", 1.0),
    ("Capital of France?", "Paris.", "success", None),
    ("Keep an eye on the weather in Delhi every hour", "Dude, I can't actually set up hourly checks.", "success", None),
    ("Open notepad", "Done.", "success", None),
    ("Who won?", "Sorry, I couldn't find that.", "success", None),
    ("What's 2 plus 2?", "5.", "success", 0.0),
    ("Read my mail", "Here is your mail from rahul@example.org, call +91 99999 99999.", "success", 1.0),
    ("Turn it up", "I couldn't confirm that it worked.", None, None),
]


@pytest.fixture
def records(tmp_path):
    store = TurnTraceStore(tmp_path / "turns.db")
    for i, (heard, said, outcome, rating) in enumerate(TURNS):
        turn = TurnRecord(started_at=time.time() - 100 + i, seconds=1.0, personality="guru", heard=heard, said=said,
                          outcome=outcome)
        store.record(turn)
        if rating is not None:
            store.rate(turn.turn_id, rating)
    return tmp_path


def _pairs(path):
    return [(m["messages"][0]["content"], m["messages"][1]["content"])
            for m in map(json.loads, path.read_text(encoding="utf-8").splitlines())]


def test_by_default_only_answers_rated_right_are_kept(records):
    report = export(records / "out.jsonl", source=records / "turns.db")
    pairs = _pairs(records / "out.jsonl")
    assert sorted(q for q, _ in pairs) == ["Read my mail", "What's my locker code?"]  # nosec B101
    assert report["pairs"] == 2 and report["left_out"] == {"not rated right": 5, "rated wrong": 1}  # nosec B101


def test_unrated_successes_can_be_added_without_refusals_or_acknowledgements(records):
    report = export(records / "out.jsonl", source=records / "turns.db", include_unrated=True)
    kept = {q for q, _ in _pairs(records / "out.jsonl")}
    # The unrated "success" turns used to be kept whatever they said.
    assert kept == {"What's my locker code?", "Read my mail", "Capital of France?"}  # nosec B101
    assert report["left_out"]["not rated, and the reply refuses or only acknowledges"] == 3  # nosec B101
    assert report["left_out"]["rated wrong"] == 1 and report["left_out"]["not rated and not a success"] == 1  # nosec B101


def test_personal_details_are_masked(records):
    export(records / "out.jsonl", source=records / "turns.db")
    answer = dict(_pairs(records / "out.jsonl"))["Read my mail"]
    assert answer == "Here is your mail from <email>, call <phone>."  # nosec B101
