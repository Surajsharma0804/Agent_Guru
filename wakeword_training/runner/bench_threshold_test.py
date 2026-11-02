"""The operating threshold is chosen on validation data and never reads a held-out set.

choose_threshold used to pick the threshold with the most detections on "your takes" - the owner's
16 held-out takes - with false wakes from the speech stream and Svarah's held-out speakers, so every
number it then reported was tuned on. Here every held-out entry of the table is poisoned: reading one
fails the test.

    python -m pytest wakeword_training/runner/bench_threshold_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402


class _HeldOut(dict):
    """A held-out table entry: any read of it is the leak this test exists to catch."""

    def _read(self, *args, **kwargs):
        raise AssertionError("threshold selection read a held-out set")

    __getitem__ = __contains__ = __iter__ = get = items = values = keys = _read


def _row(thr, val_hits, val_fw, held_out_hits):
    return {
        "threshold": thr,
        "sets": _HeldOut({"your takes: hey": {"n": 16, "hits": held_out_hits}}),
        "false_wakes": _HeldOut({"16.1 min of speech": {"count": 0, "hours": 0.27}}),
        "validation": {"positives": {"n": 28, "hits": val_hits, "wrong": 0},
                       "false_wakes": {"val_music": {"count": val_fw, "hours": 2.44},
                                       "val_speechy": {"count": 0, "hours": 0.44}}},
    }


def test_the_threshold_comes_from_validation_alone():
    # Held-out detection is best at 0.45; validation says 0.85 is the lowest point under the target.
    table = [_row(0.45, 24, 4, 16), _row(0.65, 23, 3, 15), _row(0.85, 22, 1, 12)]
    point = bench.choose_threshold(table, "hey")
    assert point["threshold"] == 0.85, point
    assert "validation" in point["basis"]


def test_the_view_passed_from_run_holds_no_held_out_set():
    row = _row(0.85, 22, 1, 12)
    assert set(bench.validation_view(row)) == {"threshold", "validation"}


def test_without_validation_audio_no_threshold_is_chosen():
    row = _row(0.85, 22, 1, 12)
    row["validation"]["false_wakes"] = {}
    point = bench.choose_threshold([row], "hey")
    assert point["threshold"] is None and "held-out sets are never used" in point["note"]
