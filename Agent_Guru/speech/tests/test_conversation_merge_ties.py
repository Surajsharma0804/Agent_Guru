"""Turns that share a timestamp still merge in the order they happened.

Each turn was stamped with time.time() and merge_contexts ordered by that alone. Windows reads the
clock in steps of about 15.6 ms, so turns added within one step shared a timestamp and heapq.merge
took all of one speaker's tied turns first: the merged conversation came out of order, and
test_merged_turns_are_in_timestamp_order failed on the Windows and macOS CI legs. Here the clock is
frozen, so every turn ties on any machine.
"""

from __future__ import annotations

import types

import Agent_Guru.speech.conversation as conversation
from Agent_Guru.speech.conversation import SpeakerDiarization


def test_turns_with_the_same_timestamp_merge_in_the_order_they_were_added(monkeypatch):
    monkeypatch.setattr(conversation, "time", types.SimpleNamespace(time=lambda: 1_700_000_000.0))
    diarization = SpeakerDiarization()
    alice = diarization.get_or_create_context("alice")
    bob = diarization.get_or_create_context("bob")
    for i in range(10):
        (alice if i % 2 == 0 else bob).add_turn(f"turn {i}")
    merged = diarization.merge_contexts(["alice", "bob"])
    assert [t["text"] for t in merged.turns] == [f"turn {i}" for i in range(10)]
