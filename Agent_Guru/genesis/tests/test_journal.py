"""The GENESIS journal: append-only, recoverable, and the only source of state."""

from __future__ import annotations

import json

import pytest

from Agent_Guru.genesis import journal as jr


def test_events_get_rising_sequence_numbers_across_reopens(tmp_path):
    path = tmp_path / "j.jsonl"
    j = jr.Journal(path, clock=lambda: 100.0)
    j.append("r1", "core", "Foundation", "planned")
    j.append("r1", "core", "Foundation", "started")
    again = jr.Journal(path, clock=lambda: 200.0)
    third = again.append("r1", "core", "Foundation", "verified", {"probe": "core.import"})
    events, bad = jr.read(path)
    assert [e.seq for e in events] == [1, 2, 3] and bad == 0  # nosec B101
    assert third.ts == 200.0 and third.data == {"probe": "core.import"}  # nosec B101


def test_an_unknown_kind_is_refused_and_not_written(tmp_path):
    j = jr.Journal(tmp_path / "j.jsonl")
    with pytest.raises(ValueError, match="unknown event kind"):
        j.append("r1", "core", "Foundation", "done")
    assert jr.read(tmp_path / "j.jsonl") == ([], 0)  # nosec B101


def test_a_torn_last_line_is_dropped_and_the_recovery_is_logged(tmp_path):
    path = tmp_path / "j.jsonl"
    j = jr.Journal(path)
    j.append("r1", "core", "Foundation", "started")
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"seq": 2, "ts": 1.0, "run_id": "r1", "compo')  # what a crash mid-write leaves
    reopened = jr.Journal(path)
    events, bad = jr.read(path)
    assert bad == 0  # nosec B101
    assert [(e.seq, e.kind) for e in events] == [(1, "started"), (2, "log")]  # nosec B101
    assert "torn last line" in events[-1].data["message"]  # nosec B101
    assert reopened.append("r1", "core", "Foundation", "verified").seq == 3  # nosec B101


def test_an_unterminated_last_line_is_dropped_even_if_it_parses(tmp_path):
    # The next append would be glued onto it and both events would be lost.
    path = tmp_path / "j.jsonl"
    whole = jr.Event(1, 1.0, "r1", "core", "Foundation", "started").to_json()
    path.write_text(whole + "\n" + whole.replace('"seq":1', '"seq":2'), encoding="utf-8")
    jr.Journal(path).append("r1", "core", "Foundation", "verified")
    events, bad = jr.read(path)
    assert bad == 0 and [e.kind for e in events] == ["started", "log", "verified"]  # nosec B101


def test_damage_in_the_middle_is_counted_not_hidden(tmp_path):
    path = tmp_path / "j.jsonl"
    good = jr.Event(1, 1.0, "r1", "core", "Foundation", "started").to_json()
    path.write_text(good + "\nnot json\n" + good.replace('"seq":1', '"seq":3') + "\n", encoding="utf-8")
    events, bad = jr.read(path)
    assert len(events) == 2 and bad == 1  # nosec B101


def test_progress_is_a_real_fraction_or_indeterminate():
    events = [jr.Event(1, 0, "r", "model", "Intelligence", "started"),
              jr.Event(2, 0, "r", "model", "Intelligence", "progress", {"done": 50, "total": 200}),
              jr.Event(3, 0, "r", "voice", "Voice", "started"),
              jr.Event(4, 0, "r", "voice", "Voice", "progress", {"done": 7, "total": 0}),
              jr.Event(5, 0, "r", "voice", "Voice", "progress", {"done": 9})]
    views = jr.project(events)
    assert (views["model"].done, views["model"].total, views["model"].state) == (50, 200, "started")  # nosec B101
    assert (views["voice"].done, views["voice"].total) == (9, None)  # nosec B101
    # A total of zero is not a denominator: the bar stays indeterminate
    # instead of showing 7 of 0, or a full bar.
    zero = jr.project(events[:4])["voice"]
    assert (zero.done, zero.total) == (7, None)  # nosec B101


def test_nothing_is_installed_without_a_verified_or_reused_event():
    events = [jr.Event(1, 0, "r", "core", "Foundation", "planned"),
              jr.Event(2, 0, "r", "core", "Foundation", "started"),
              jr.Event(3, 0, "r", "core", "Foundation", "progress", {"done": 10, "total": 10}),
              jr.Event(4, 0, "r", "memory", "Memory", "reused"),
              jr.Event(5, 0, "r", "voice", "Voice", "verified"),
              jr.Event(6, 0, "r2", "voice", "Voice", "rolled_back")]
    views = jr.project(events)
    assert not views["core"].installed  # nosec B101  finished downloading is not verified
    assert views["memory"].installed  # nosec B101
    assert jr.installed_components(events) == {"memory"}  # nosec B101


def test_a_failure_keeps_its_error_for_the_screen():
    events = [jr.Event(1, 0, "r", "core", "Foundation", "started"),
              jr.Event(2, 0, "r", "core", "Foundation", "failed", {"error": "files.pythonhosted.org: timed out"})]
    view = jr.project(events)["core"]
    assert view.state == "failed" and view.error == "files.pythonhosted.org: timed out"  # nosec B101


def test_each_line_is_one_json_object_with_the_typed_fields(tmp_path):
    path = tmp_path / "j.jsonl"
    jr.Journal(path, clock=lambda: 5.25).append("r1", "core", "Foundation", "planned", {"bytes": 3})
    raw = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert raw == {"seq": 1, "ts": 5.25, "run_id": "r1", "component_id": "core", "stage": "Foundation",  # nosec B101
                   "kind": "planned", "data": {"bytes": 3}}
