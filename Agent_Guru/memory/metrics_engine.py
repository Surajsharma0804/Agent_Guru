"""Metrics and Monitoring Engine.

Tracks all memory system metrics in-memory with:
- record_metric: store a MetricSnapshot (Property 52)
- get_metric_history: retrieve snapshots by type and time range
- calculate_trend: linear trend over recent snapshots
- generate_dashboard: summary of all metric types
- check_alerts: detect degradation below thresholds (Property 54)
- A/B testing: isolated parallel instances (Requirement 11.10)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from Agent_Guru.memory.models import MetricSnapshot, MetricType

logger = logging.getLogger(__name__)

_DEFAULT_ALERT_THRESHOLDS: dict[MetricType, float] = {
    MetricType.QUERY_ACCURACY: 0.80,
    MetricType.PREFERENCE_PREDICTION_ACCURACY: 0.70,
    MetricType.RETRIEVAL_RELEVANCE: 0.70,
    MetricType.PERSONALITY_CONSISTENCY: 0.60,
    MetricType.GITHUB_SYNC_SUCCESS_RATE: 0.80,
    MetricType.OPERATION_THROUGHPUT: 10.0,
}


@dataclass
class AlertEvent:
    metric_type: MetricType
    current_value: float
    threshold: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    message: str = ""


@dataclass
class TrendResult:
    metric_type: MetricType
    slope: float  # positive = improving, negative = degrading
    mean: float
    latest: float
    sample_count: int


@dataclass
class DashboardEntry:
    metric_type: MetricType
    latest_value: float
    mean_value: float
    sample_count: int
    trend_slope: float


class MetricsEngine:
    """In-memory metrics engine with alerting and A/B support.

    Uses InfluxDB-style time-series storage backed by in-memory lists.
    For production, swap _store for an InfluxDB client.
    """

    def __init__(
        self,
        alert_thresholds: dict[MetricType, float] | None = None,
        max_history_per_metric: int = 10_000,
    ) -> None:
        self._store: dict[MetricType, list[MetricSnapshot]] = defaultdict(list)
        self._thresholds = alert_thresholds or dict(_DEFAULT_ALERT_THRESHOLDS)
        self._max_history = max_history_per_metric
        self._alerts: list[AlertEvent] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        metadata: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ) -> MetricSnapshot:
        """Record a single metric snapshot."""
        snap = MetricSnapshot(
            metric_type=metric_type,
            value=value,
            metadata=metadata or {},
            timestamp=timestamp or datetime.now(tz=timezone.utc),
        )
        bucket = self._store[metric_type]
        bucket.append(snap)
        # Trim to max history (keep most recent)
        if len(bucket) > self._max_history:
            self._store[metric_type] = bucket[-self._max_history :]
        logger.debug("Recorded %s = %.4f", metric_type.value, value)
        return snap

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_metric_history(
        self,
        metric_type: MetricType,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> list[MetricSnapshot]:
        """Return snapshots for a metric type, optionally filtered by time."""
        snaps = self._store.get(metric_type, [])
        if since:
            snaps = [s for s in snaps if s.timestamp >= since]
        if until:
            snaps = [s for s in snaps if s.timestamp <= until]
        if limit:
            snaps = snaps[-limit:]
        return list(snaps)

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

    def calculate_trend(
        self, metric_type: MetricType, window: int = 20
    ) -> TrendResult | None:
        """Linear trend over the last `window` snapshots. Returns None if <2 points."""
        snaps = self._store.get(metric_type, [])[-window:]
        n = len(snaps)
        if n < 2:
            return None
        values = [s.value for s in snaps]
        mean = sum(values) / n
        # Simple linear regression slope
        xs = list(range(n))
        x_mean = (n - 1) / 2.0
        numerator = sum((xs[i] - x_mean) * (values[i] - mean) for i in range(n))
        denominator = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator else 0.0
        return TrendResult(
            metric_type=metric_type,
            slope=slope,
            mean=mean,
            latest=values[-1],
            sample_count=n,
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def generate_dashboard(
        self, since: datetime | None = None
    ) -> list[DashboardEntry]:
        """Summary of all tracked metric types."""
        entries = []
        for metric_type, snaps in self._store.items():
            if since:
                snaps = [s for s in snaps if s.timestamp >= since]
            if not snaps:
                continue
            values = [s.value for s in snaps]
            trend = self.calculate_trend(metric_type)
            entries.append(
                DashboardEntry(
                    metric_type=metric_type,
                    latest_value=values[-1],
                    mean_value=sum(values) / len(values),
                    sample_count=len(values),
                    trend_slope=trend.slope if trend else 0.0,
                )
            )
        return entries

    # ------------------------------------------------------------------
    # Alerting (Property 54)
    # ------------------------------------------------------------------

    def check_alerts(self) -> list[AlertEvent]:
        """Check all metrics against thresholds. Returns new alerts."""
        new_alerts: list[AlertEvent] = []
        for metric_type, threshold in self._thresholds.items():
            snaps = self._store.get(metric_type, [])
            if not snaps:
                continue
            latest = snaps[-1].value
            if latest < threshold:
                alert = AlertEvent(
                    metric_type=metric_type,
                    current_value=latest,
                    threshold=threshold,
                    message=f"{metric_type.value} degraded: {latest:.4f} < {threshold:.4f}",
                )
                self._alerts.append(alert)
                new_alerts.append(alert)
                logger.warning(alert.message)
        return new_alerts

    def set_threshold(self, metric_type: MetricType, threshold: float) -> None:
        self._thresholds[metric_type] = threshold

    def get_all_alerts(self) -> list[AlertEvent]:
        return list(self._alerts)

    # ------------------------------------------------------------------
    # A/B testing support (Requirement 11.10)
    # ------------------------------------------------------------------

    @classmethod
    def create_ab_pair(
        cls,
        thresholds: dict[MetricType, float] | None = None,
    ) -> tuple[MetricsEngine, MetricsEngine]:
        """Create two isolated MetricsEngine instances for A/B comparison."""
        return cls(alert_thresholds=thresholds), cls(alert_thresholds=thresholds)
