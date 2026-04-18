"""Accuracy tracking and alerting for the Verifier System.

Tracks false positive/negative rates and alerts on degradation.

Requirements: 13.1, 13.2, 13.3, 13.4
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class AccuracySnapshot:
    """Point-in-time accuracy snapshot."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    total_verifications: int = 0


class AccuracyTracker:
    """Tracks verification accuracy and alerts on degradation.

    Requirements: 13.1, 13.2, 13.3, 13.4
    """

    def __init__(
        self,
        max_fp_rate: float = 0.05,
        max_fn_rate: float = 0.02,
        window_size: int = 100,
    ) -> None:
        self._max_fp_rate = max_fp_rate
        self._max_fn_rate = max_fn_rate
        self._window_size = window_size

        # Ground truth labels: result_id -> (predicted_positive, actual_positive)
        self._labels: deque[tuple[bool, bool]] = deque(maxlen=window_size)
        self._snapshots: list[AccuracySnapshot] = []
        self._alerts: list[str] = []

    def record(self, predicted_positive: bool, actual_positive: bool) -> None:
        """Record a verification outcome with ground truth label."""
        self._labels.append((predicted_positive, actual_positive))
        # deque(maxlen=window_size) auto-evicts oldest — no manual pop needed

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
        """FP / (FP + TN)"""
        fp = sum(1 for pred, actual in self._labels if pred and not actual)
        tn = sum(1 for pred, actual in self._labels if not pred and not actual)
        denom = fp + tn
        return fp / denom if denom > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        """FN / (FN + TP)"""
        fn = sum(1 for pred, actual in self._labels if not pred and actual)
        tp = sum(1 for pred, actual in self._labels if pred and actual)
        denom = fn + tp
        return fn / denom if denom > 0 else 0.0

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
