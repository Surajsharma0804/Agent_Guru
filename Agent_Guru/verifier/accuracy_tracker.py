"""Accuracy tracking and alerting for the Verifier System.

Tracks false positive/negative rates and alerts on degradation.

Requirements: 13.1, 13.2, 13.3, 13.4
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class AccuracySnapshot:
    """Point-in-time accuracy snapshot."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    total_verifications: int = 0


class AccuracyTracker:
    """Tracks verification accuracy and alerts on degradation.

    Requirements: 13.1, 13.2, 13.3, 13.4
    """

    #: How many recent alerts and snapshots to retain.
    #:
    #: MEMORY-LEAK FIX: _alerts and _snapshots were plain lists that only ever
    #: grew. record() appends an alert on EVERY call once a rate is above its
    #: threshold, so a persistently degraded verifier added two strings per
    #: verification, for the life of the process - the failure path itself was
    #: the leak. _labels was already correctly bounded with
    #: deque(maxlen=window_size); these two were simply missed.
    DEFAULT_HISTORY = 1000

    def __init__(
        self,
        max_fp_rate: float = 0.05,
        max_fn_rate: float = 0.02,
        window_size: int = 100,
        history_size: int | None = None,
    ) -> None:
        """Initialize the tracker.

        Args:
            max_fp_rate: False-positive rate above which an alert is raised.
            max_fn_rate: False-negative rate above which an alert is raised.
            window_size: How many recent outcomes the rates are computed over.
            history_size: How many recent alerts and snapshots to retain
                (default DEFAULT_HISTORY). Bounded so a long-running process
                cannot accumulate them without limit.

        """
        if window_size <= 0:
            msg = f"window_size must be positive, got {window_size}"
            raise ValueError(msg)
        retained = self.DEFAULT_HISTORY if history_size is None else history_size
        if retained <= 0:
            msg = f"history_size must be positive, got {retained}"
            raise ValueError(msg)

        self._max_fp_rate = max_fp_rate
        self._max_fn_rate = max_fn_rate
        self._window_size = window_size
        self._history_size = retained

        # Ground truth labels: (predicted_positive, actual_positive)
        self._labels: deque[tuple[bool, bool]] = deque(maxlen=window_size)
        self._snapshots: deque[AccuracySnapshot] = deque(maxlen=retained)
        self._alerts: deque[str] = deque(maxlen=retained)

        # PERFORMANCE: confusion-matrix cells maintained incrementally.
        #
        # The rate properties used to recompute themselves by scanning the whole
        # window - four generator passes over `window_size` tuples - and record()
        # reads both of them on every call. That made recording a single outcome
        # O(window_size) (400 iterations at the default window of 100) on the
        # per-verification hot path, for numbers that change by exactly one
        # observation. The window is a bounded deque, so the only entry that can
        # leave on an append is the leftmost one: decrement its cell before
        # appending and the counts stay exact at O(1) per record.
        self._tp = 0
        self._fp = 0
        self._tn = 0
        self._fn = 0

    def _cell(self, predicted_positive: bool, actual_positive: bool) -> str:
        """Return the confusion-matrix attribute name for one outcome."""
        if predicted_positive:
            return "_tp" if actual_positive else "_fp"
        return "_fn" if actual_positive else "_tn"

    def record(self, predicted_positive: bool, actual_positive: bool) -> None:
        """Record a verification outcome with ground truth label."""
        # deque(maxlen=window_size) auto-evicts the oldest entry on append, so
        # drop its contribution to the counts first - otherwise the confusion
        # matrix would describe more observations than the window holds.
        labels = self._labels
        if labels.maxlen is not None and len(labels) == labels.maxlen:
            evicted = self._cell(*labels[0])
            setattr(self, evicted, getattr(self, evicted) - 1)

        labels.append((predicted_positive, actual_positive))
        added = self._cell(predicted_positive, actual_positive)
        setattr(self, added, getattr(self, added) + 1)

        # Check for degradation
        fp_rate = self.false_positive_rate
        fn_rate = self.false_negative_rate

        if fp_rate > self._max_fp_rate:
            alert = f"False positive rate {fp_rate:.3f} exceeds threshold {self._max_fp_rate}"
            logger.warning(alert)
            self._alerts.append(alert)

        if fn_rate > self._max_fn_rate:
            alert = f"False negative rate {fn_rate:.3f} exceeds threshold {self._max_fn_rate}"
            logger.warning(alert)
            self._alerts.append(alert)

    @property
    def false_positive_rate(self) -> float:
        """FP / (FP + TN) over the current window. O(1)."""
        denom = self._fp + self._tn
        return self._fp / denom if denom > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        """FN / (FN + TP) over the current window. O(1)."""
        denom = self._fn + self._tp
        return self._fn / denom if denom > 0 else 0.0

    @property
    def total(self) -> int:
        return len(self._labels)

    def get_alerts(self) -> list[str]:
        return list(self._alerts)

    def take_snapshot(self) -> AccuracySnapshot:
        snap = AccuracySnapshot(
            false_positive_rate=self.false_positive_rate,
            false_negative_rate=self.false_negative_rate,
            total_verifications=self.total,
        )
        self._snapshots.append(snap)
        return snap
