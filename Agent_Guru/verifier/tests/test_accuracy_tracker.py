"""Regression tests for AccuracyTracker.

Covers two defects fixed together:

1. MEMORY LEAK - ``_alerts`` and ``_snapshots`` were unbounded lists. Because
   ``record()`` appends an alert on *every* call once a rate sits above its
   threshold, a persistently degraded verifier grew them without limit for the
   life of the process. The failure path itself was the leak.

2. O(window) HOT PATH - the rate properties recomputed themselves by scanning
   the entire window, and ``record()`` reads both on every call. The counts are
   now maintained incrementally; these tests pin the incremental result to a
   brute-force recomputation so the optimisation cannot silently drift.
"""

from __future__ import annotations

import random

import pytest

from Agent_Guru.verifier.accuracy_tracker import AccuracySnapshot, AccuracyTracker


def brute_force_rates(labels: list[tuple[bool, bool]]) -> tuple[float, float]:
    """Recompute both rates the original (full-scan) way."""
    fp = sum(1 for pred, actual in labels if pred and not actual)
    tn = sum(1 for pred, actual in labels if not pred and not actual)
    fn = sum(1 for pred, actual in labels if not pred and actual)
    tp = sum(1 for pred, actual in labels if pred and actual)
    fp_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fn_rate = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    return fp_rate, fn_rate


class TestBoundedGrowth:
    """The leak: alerts and snapshots must not grow without limit."""

    def test_alerts_are_bounded_under_sustained_degradation(self) -> None:
        # Thresholds of 0.0 mean every wrong prediction alerts, which is the
        # real-world "verifier has gone bad and nobody noticed" case.
        tracker = AccuracyTracker(
            max_fp_rate=0.0, max_fn_rate=0.0, window_size=10, history_size=50
        )
        for _ in range(5_000):
            tracker.record(predicted_positive=True, actual_positive=False)
            tracker.record(predicted_positive=False, actual_positive=True)

        alerts = tracker.get_alerts()
        assert len(alerts) == 50, (
            f"alert history grew to {len(alerts)} entries; it must stay bounded "
            "at history_size regardless of how long the verifier stays degraded"
        )
        # The retained alerts are the most recent ones, not the first 50.
        assert alerts[-1].startswith(("False positive", "False negative"))

    def test_snapshots_are_bounded(self) -> None:
        tracker = AccuracyTracker(window_size=10, history_size=25)
        for _ in range(500):
            tracker.record(predicted_positive=True, actual_positive=True)
            tracker.take_snapshot()

        assert len(tracker._snapshots) == 25
        assert all(isinstance(s, AccuracySnapshot) for s in tracker._snapshots)

    def test_history_size_defaults_to_class_constant(self) -> None:
        tracker = AccuracyTracker()
        assert tracker._alerts.maxlen == AccuracyTracker.DEFAULT_HISTORY
        assert tracker._snapshots.maxlen == AccuracyTracker.DEFAULT_HISTORY

    def test_memory_does_not_track_call_count(self) -> None:
        """Structural proof independent of timing or of the exact bound.

        With an unbounded list the retained size is a function of how many
        times record() was called. With a bounded deque it is not.
        """
        short = AccuracyTracker(max_fp_rate=0.0, window_size=5, history_size=20)
        long = AccuracyTracker(max_fp_rate=0.0, window_size=5, history_size=20)
        for _ in range(100):
            short.record(predicted_positive=True, actual_positive=False)
        for _ in range(10_000):
            long.record(predicted_positive=True, actual_positive=False)

        assert len(short.get_alerts()) == len(long.get_alerts()) == 20


class TestValidation:
    """Constructor arguments that cannot produce a working tracker."""

    @pytest.mark.parametrize("window_size", [0, -1, -100])
    def test_rejects_non_positive_window(self, window_size: int) -> None:
        with pytest.raises(ValueError, match="window_size must be positive"):
            AccuracyTracker(window_size=window_size)

    @pytest.mark.parametrize("history_size", [0, -1])
    def test_rejects_non_positive_history(self, history_size: int) -> None:
        with pytest.raises(ValueError, match="history_size must be positive"):
            AccuracyTracker(history_size=history_size)


class TestIncrementalCountsMatchFullScan:
    """The optimisation: O(1) counts must equal the O(window) recomputation."""

    def test_matches_brute_force_on_random_stream(self) -> None:
        rng = random.Random(20260924)
        window = 32
        tracker = AccuracyTracker(max_fp_rate=1.1, max_fn_rate=1.1, window_size=window)
        history: list[tuple[bool, bool]] = []

        for _ in range(2_000):
            pred = rng.random() < 0.5
            actual = rng.random() < 0.5
            tracker.record(predicted_positive=pred, actual_positive=actual)
            history.append((pred, actual))

            expected_fp, expected_fn = brute_force_rates(history[-window:])
            assert tracker.false_positive_rate == pytest.approx(expected_fp)
            assert tracker.false_negative_rate == pytest.approx(expected_fn)

    def test_matches_brute_force_before_window_fills(self) -> None:
        tracker = AccuracyTracker(max_fp_rate=1.1, max_fn_rate=1.1, window_size=100)
        history: list[tuple[bool, bool]] = []
        for pred, actual in [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
            (True, False),
        ]:
            tracker.record(predicted_positive=pred, actual_positive=actual)
            history.append((pred, actual))
            expected_fp, expected_fn = brute_force_rates(history)
            assert tracker.false_positive_rate == pytest.approx(expected_fp)
            assert tracker.false_negative_rate == pytest.approx(expected_fn)

    def test_counts_never_exceed_window(self) -> None:
        """Eviction must decrement, or the matrix outgrows the window."""
        tracker = AccuracyTracker(max_fp_rate=1.1, max_fn_rate=1.1, window_size=8)
        rng = random.Random(7)
        for _ in range(1_000):
            tracker.record(
                predicted_positive=rng.random() < 0.5,
                actual_positive=rng.random() < 0.5,
            )
            total_cells = tracker._tp + tracker._fp + tracker._tn + tracker._fn
            assert total_cells == len(tracker._labels) == tracker.total <= 8

    def test_empty_tracker_reports_zero_rates(self) -> None:
        tracker = AccuracyTracker()
        assert tracker.false_positive_rate == 0.0
        assert tracker.false_negative_rate == 0.0
        assert tracker.total == 0

    def test_rates_are_zero_when_denominator_is_empty(self) -> None:
        # Only true positives: no FP+TN and no FN+TP contribution to FP rate.
        tracker = AccuracyTracker(max_fp_rate=1.1, max_fn_rate=1.1)
        for _ in range(10):
            tracker.record(predicted_positive=True, actual_positive=True)
        assert tracker.false_positive_rate == 0.0
        assert tracker.false_negative_rate == 0.0


class TestAlerting:
    """Alerting behaviour must survive both changes."""

    def test_alert_raised_when_fp_rate_exceeds_threshold(self) -> None:
        tracker = AccuracyTracker(max_fp_rate=0.5, max_fn_rate=1.1, window_size=10)
        tracker.record(predicted_positive=False, actual_positive=False)
        assert tracker.get_alerts() == []
        tracker.record(predicted_positive=True, actual_positive=False)
        tracker.record(predicted_positive=True, actual_positive=False)
        alerts = tracker.get_alerts()
        assert alerts, "an FP rate of 2/3 must trip a 0.5 threshold"
        assert "False positive rate" in alerts[-1]

    def test_recovery_stops_new_alerts(self) -> None:
        """Once the window rolls clean, the tracker must stop alerting."""
        tracker = AccuracyTracker(max_fp_rate=0.5, max_fn_rate=1.1, window_size=4)
        for _ in range(4):
            tracker.record(predicted_positive=True, actual_positive=False)
        assert tracker.get_alerts()

        # The window rolls one entry at a time, so clean records displace the
        # bad ones gradually: at 3 FP / 1 TN the rate is still 0.75 and alerts
        # legitimately. Fill the window completely, then assert silence.
        for _ in range(4):
            tracker.record(predicted_positive=False, actual_positive=False)
        assert tracker.false_positive_rate == 0.0

        settled = len(tracker.get_alerts())
        for _ in range(20):
            tracker.record(predicted_positive=False, actual_positive=False)
        assert len(tracker.get_alerts()) == settled, (
            "a recovered verifier must stop appending alerts"
        )

    def test_snapshot_reflects_current_state(self) -> None:
        tracker = AccuracyTracker(max_fp_rate=1.1, max_fn_rate=1.1, window_size=10)
        tracker.record(predicted_positive=True, actual_positive=False)
        tracker.record(predicted_positive=False, actual_positive=False)
        snap = tracker.take_snapshot()
        assert snap.total_verifications == 2
        assert snap.false_positive_rate == pytest.approx(0.5)
        assert snap.timestamp.tzinfo is not None
