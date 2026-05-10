"""Edge Case Handler for Self-Improvement Engine.

Prevents overgeneralization from rare events and edge cases by implementing
statistical confidence measures, sample size requirements, and event frequency
weighting. Ensures that rare events don't disproportionately influence learning.

**Validates: Requirements 9.6 (Edge Case Handling Without Overgeneralization)**

Performance Requirements:
- Time Complexity: O(1) for confidence calculation
- Space Complexity: O(1) for statistical measures
- Confidence Calculation Latency: <1ms (99th percentile)

Design Principles:
- Use Wilson score interval for confidence bounds
- Apply Bayesian priors to prevent overfitting to small samples
- Weight events by frequency to prevent rare event dominance
- Require minimum sample sizes before trusting patterns

Author: Agent Guru Team
Date: 2026-02-28
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.connection_pool import ConnectionPool


@dataclass
class ConfidenceMetrics:
    """Confidence metrics for a pattern or strategy."""

    pattern_id: str
    sample_size: int
    success_rate: float
    confidence_score: float  # 0.0 (no confidence) to 1.0 (high confidence)
    lower_bound: float  # Lower bound of confidence interval
    upper_bound: float  # Upper bound of confidence interval
    is_edge_case: bool  # True if this is a rare event
    event_frequency: float  # Frequency of this event type (0.0-1.0)
    weighted_score: float  # Score weighted by frequency
    meets_threshold: bool  # True if meets minimum sample size
    timestamp: datetime


class EdgeCaseHandler:
    """Handles edge cases and prevents overgeneralization from rare events.

    Uses statistical confidence measures to weight rare vs common events
    appropriately. Implements minimum sample size requirements and
    frequency-based weighting to prevent edge cases from dominating learning.

    Time Complexity: O(1) for confidence calculations
    Space Complexity: O(1) for statistical measures

    Example:
        >>> handler = EdgeCaseHandler(pool, min_sample_size=10)
        >>> metrics = handler.calculate_confidence(
        ...     pattern_id="rare_failure",
        ...     successes=1,
        ...     failures=0,
        ...     total_events=1000
        ... )
        >>> if not metrics.meets_threshold:
        ...     print("Not enough data to trust this pattern")
        >>> if metrics.is_edge_case:
        ...     print(f"Rare event: frequency={metrics.event_frequency:.3f}")

    """

    def __init__(
        self,
        pool: "ConnectionPool",
        min_sample_size: int = 10,
        edge_case_threshold: float = 0.05,
        confidence_level: float = 0.95,
        bayesian_prior_successes: int = 1,
        bayesian_prior_failures: int = 1,
    ) -> None:
        """Initialize edge case handler.

        Args:
            pool: ConnectionPool for database access
            min_sample_size: Minimum samples before trusting pattern (default: 10)
            edge_case_threshold: Frequency threshold for edge cases (default: 0.05 = 5%)
            confidence_level: Confidence level for intervals (default: 0.95 = 95%)
            bayesian_prior_successes: Prior successes for Bayesian smoothing (default: 1)
            bayesian_prior_failures: Prior failures for Bayesian smoothing (default: 1)

        Raises:
            ValueError: If parameters are invalid

        """
        if min_sample_size < 1:
            msg = f"min_sample_size must be >= 1, got {min_sample_size}"
            raise ValueError(msg)
        if not 0.0 < edge_case_threshold < 1.0:
            msg = f"edge_case_threshold must be in (0.0, 1.0), got {edge_case_threshold}"
            raise ValueError(
                msg,
            )
        if not 0.0 < confidence_level < 1.0:
            msg = f"confidence_level must be in (0.0, 1.0), got {confidence_level}"
            raise ValueError(msg)

        self.pool = pool
        self.min_sample_size = min_sample_size
        self.edge_case_threshold = edge_case_threshold
        self.confidence_level = confidence_level
        self.bayesian_prior_successes = bayesian_prior_successes
        self.bayesian_prior_failures = bayesian_prior_failures

        # Z-score for confidence level (1.96 for 95% confidence)
        self.z_score = self._calculate_z_score(confidence_level)

        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema for edge case tracking.

        Note: DatabaseSchema.create_schema() should be called first.
        This method only verifies the table exists.
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Verify edge_case_metrics table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='edge_case_metrics'
            """,
            )

            if not cursor.fetchone():
                msg = (
                    "edge_case_metrics table not found. Call DatabaseSchema.create_schema() first."
                )
                raise RuntimeError(
                    msg,
                )

    def calculate_confidence(
        self,
        pattern_id: str,
        successes: int,
        failures: int,
        total_events: int,
    ) -> ConfidenceMetrics:
        """Calculate confidence metrics for a pattern.

        Uses Wilson score interval for confidence bounds and Bayesian
        smoothing to prevent overfitting to small samples.

        Time Complexity: O(1) - constant time calculations
        Space Complexity: O(1)

        Args:
            pattern_id: Pattern identifier
            successes: Number of successes
            failures: Number of failures
            total_events: Total number of events of all types

        Returns:
            ConfidenceMetrics with calculated values

        Example:
            >>> # Common pattern with good data
            >>> metrics = handler.calculate_confidence("common", 90, 10, 1000)
            >>> assert metrics.meets_threshold
            >>> assert not metrics.is_edge_case
            >>>
            >>> # Rare pattern with limited data
            >>> metrics = handler.calculate_confidence("rare", 2, 0, 1000)
            >>> assert not metrics.meets_threshold
            >>> assert metrics.is_edge_case

        """
        sample_size = successes + failures

        # Calculate raw success rate
        successes / sample_size if sample_size > 0 else 0.0

        # Apply Bayesian smoothing to prevent overfitting to small samples
        smoothed_successes = successes + self.bayesian_prior_successes
        smoothed_failures = failures + self.bayesian_prior_failures
        smoothed_sample_size = smoothed_successes + smoothed_failures
        smoothed_success_rate = smoothed_successes / smoothed_sample_size

        # Calculate Wilson score confidence interval
        lower_bound, upper_bound = self._wilson_score_interval(successes, sample_size, self.z_score)

        # Calculate confidence score based on sample size and interval width
        confidence_score = self._calculate_confidence_score(sample_size, lower_bound, upper_bound)

        # Calculate event frequency (how common is this pattern)
        event_frequency = sample_size / total_events if total_events > 0 else 0.0

        # Determine if this is an edge case (rare event)
        is_edge_case = event_frequency < self.edge_case_threshold

        # Calculate weighted score (downweight rare events)
        weighted_score = self._calculate_weighted_score(
            smoothed_success_rate,
            event_frequency,
            is_edge_case,
        )

        # Check if meets minimum sample size threshold
        meets_threshold = sample_size >= self.min_sample_size

        metrics = ConfidenceMetrics(
            pattern_id=pattern_id,
            sample_size=sample_size,
            success_rate=smoothed_success_rate,
            confidence_score=confidence_score,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            is_edge_case=is_edge_case,
            event_frequency=event_frequency,
            weighted_score=weighted_score,
            meets_threshold=meets_threshold,
            timestamp=datetime.now(tz=UTC),
        )

        # Persist metrics
        self._persist_metrics(metrics)

        return metrics

    def _wilson_score_interval(
        self,
        successes: int,
        sample_size: int,
        z: float,
    ) -> tuple[float, float]:
        """Calculate Wilson score confidence interval.

        The Wilson score interval is more accurate than normal approximation
        for small sample sizes and extreme probabilities.

        Args:
            successes: Number of successes
            sample_size: Total sample size
            z: Z-score for confidence level

        Returns:
            Tuple of (lower_bound, upper_bound)

        """
        if sample_size == 0:
            return 0.0, 0.0

        p = successes / sample_size
        denominator = 1 + z**2 / sample_size

        center = (p + z**2 / (2 * sample_size)) / denominator

        margin = (z / denominator) * math.sqrt(
            p * (1 - p) / sample_size + z**2 / (4 * sample_size**2),
        )

        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)

        return lower, upper

    def _calculate_confidence_score(
        self,
        sample_size: int,
        lower_bound: float,
        upper_bound: float,
    ) -> float:
        """Calculate confidence score from sample size and interval width.

        Higher sample size and narrower interval = higher confidence.

        Args:
            sample_size: Number of samples
            lower_bound: Lower confidence bound
            upper_bound: Upper confidence bound

        Returns:
            Confidence score 0.0-1.0

        """
        # Sample size component (sigmoid function)
        # Reaches 0.5 at min_sample_size, approaches 1.0 for large samples
        size_score = 1.0 / (1.0 + math.exp(-0.5 * (sample_size - self.min_sample_size)))

        # Interval width component (narrower = better)
        # Perfect confidence (width=0) = 1.0, wide interval = 0.0
        interval_width = upper_bound - lower_bound
        width_score = max(0.0, 1.0 - interval_width)

        # Combine scores (weighted average)
        return 0.6 * size_score + 0.4 * width_score

    def _calculate_weighted_score(
        self,
        success_rate: float,
        event_frequency: float,
        is_edge_case: bool,
    ) -> float:
        """Calculate weighted score that downweights rare events.

        Rare events (edge cases) are weighted less to prevent them from
        dominating learning. Common events are weighted more heavily.

        Args:
            success_rate: Raw success rate
            event_frequency: Frequency of this event type
            is_edge_case: Whether this is a rare event

        Returns:
            Weighted score 0.0-1.0

        """
        if is_edge_case:
            # Downweight rare events using square root of frequency
            # This prevents rare events from having too much influence
            # while still allowing them to contribute
            weight = math.sqrt(event_frequency / self.edge_case_threshold)
        else:
            # Common events get full weight
            weight = 1.0

        return success_rate * weight

    def _calculate_z_score(self, confidence_level: float) -> float:
        """Calculate z-score for confidence level.

        Args:
            confidence_level: Confidence level (e.g., 0.95 for 95%)

        Returns:
            Z-score (e.g., 1.96 for 95% confidence)

        """
        # Common confidence levels
        z_scores = {
            0.90: 1.645,
            0.95: 1.960,
            0.99: 2.576,
        }

        return z_scores.get(confidence_level, 1.960)

    def should_trust_pattern(
        self,
        pattern_id: str,
        successes: int,
        failures: int,
        total_events: int,
    ) -> tuple[bool, str]:
        """Determine if a pattern should be trusted for learning.

        Checks sample size, confidence, and edge case status.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pattern_id: Pattern identifier
            successes: Number of successes
            failures: Number of failures
            total_events: Total number of events

        Returns:
            Tuple of (should_trust: bool, reason: str)

        Example:
            >>> trust, reason = handler.should_trust_pattern("rare", 1, 0, 1000)
            >>> if not trust:
            ...     print(f"Don't trust: {reason}")

        """
        metrics = self.calculate_confidence(pattern_id, successes, failures, total_events)

        # Check minimum sample size
        if not metrics.meets_threshold:
            return (
                False,
                f"Insufficient data: {metrics.sample_size} samples "
                f"(minimum: {self.min_sample_size})",
            )

        # Check confidence score
        if metrics.confidence_score < 0.5:
            return (
                False,
                f"Low confidence: {metrics.confidence_score:.3f} "
                f"(interval: [{metrics.lower_bound:.3f}, {metrics.upper_bound:.3f}])",
            )

        # Warn about edge cases but don't block
        if metrics.is_edge_case:
            return (
                True,
                f"Edge case detected: frequency={metrics.event_frequency:.3f} "
                f"(weighted score: {metrics.weighted_score:.3f})",
            )

        return True, "Pattern trusted"

    def get_weighted_success_rate(
        self,
        pattern_id: str,
        successes: int,
        failures: int,
        total_events: int,
    ) -> float:
        """Get weighted success rate that accounts for sample size and frequency.

        Use this instead of raw success rate to prevent overgeneralization
        from rare events.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pattern_id: Pattern identifier
            successes: Number of successes
            failures: Number of failures
            total_events: Total number of events

        Returns:
            Weighted success rate 0.0-1.0

        Example:
            >>> # Rare event with 100% success (1/1) gets downweighted
            >>> rate = handler.get_weighted_success_rate("rare", 1, 0, 1000)
            >>> assert rate < 1.0  # Downweighted due to small sample
            >>>
            >>> # Common event with 90% success (90/100) gets full weight
            >>> rate = handler.get_weighted_success_rate("common", 90, 10, 1000)
            >>> assert rate > 0.85  # Close to raw success rate

        """
        metrics = self.calculate_confidence(pattern_id, successes, failures, total_events)
        return metrics.weighted_score

    def get_confidence_report(
        self,
        pattern_id: str,
        successes: int,
        failures: int,
        total_events: int,
    ) -> dict[str, Any]:
        """Get comprehensive confidence report for a pattern.

        Args:
            pattern_id: Pattern identifier
            successes: Number of successes
            failures: Number of failures
            total_events: Total number of events

        Returns:
            Dictionary with confidence metrics and recommendations

        Example:
            >>> report = handler.get_confidence_report("pattern_1", 5, 2, 100)
            >>> print(f"Confidence: {report['confidence_score']:.2f}")
            >>> print(f"Recommendations: {report['recommendations']}")

        """
        metrics = self.calculate_confidence(pattern_id, successes, failures, total_events)
        should_trust, reason = self.should_trust_pattern(
            pattern_id,
            successes,
            failures,
            total_events,
        )

        recommendations = []

        if not metrics.meets_threshold:
            recommendations.append(
                f"Collect at least {self.min_sample_size - metrics.sample_size} "
                f"more samples before trusting this pattern",
            )

        if metrics.is_edge_case:
            recommendations.append(
                "This is a rare event - use weighted score to prevent overgeneralization",
            )

        if metrics.confidence_score < 0.5:
            recommendations.append(
                "Low confidence - collect more data or use conservative estimates",
            )

        if metrics.confidence_score >= 0.8 and metrics.meets_threshold:
            recommendations.append("High confidence - safe to use for learning")

        return {
            "pattern_id": pattern_id,
            "sample_size": metrics.sample_size,
            "success_rate": metrics.success_rate,
            "weighted_score": metrics.weighted_score,
            "confidence_score": metrics.confidence_score,
            "confidence_interval": [metrics.lower_bound, metrics.upper_bound],
            "is_edge_case": metrics.is_edge_case,
            "event_frequency": metrics.event_frequency,
            "meets_threshold": metrics.meets_threshold,
            "should_trust": should_trust,
            "reason": reason,
            "recommendations": recommendations,
            "timestamp": metrics.timestamp.isoformat(),
        }

    def _persist_metrics(self, metrics: ConfidenceMetrics) -> None:
        """Persist confidence metrics to database.

        Args:
            metrics: ConfidenceMetrics to persist

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO edge_case_metrics (
                    metric_id, pattern_id, sample_size, success_rate,
                    confidence_score, lower_bound, upper_bound,
                    is_edge_case, event_frequency, weighted_score,
                    meets_threshold, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"{metrics.pattern_id}_{metrics.timestamp.timestamp()}",
                    metrics.pattern_id,
                    metrics.sample_size,
                    metrics.success_rate,
                    metrics.confidence_score,
                    metrics.lower_bound,
                    metrics.upper_bound,
                    1 if metrics.is_edge_case else 0,
                    metrics.event_frequency,
                    metrics.weighted_score,
                    1 if metrics.meets_threshold else 0,
                    metrics.timestamp.isoformat(),
                ),
            )

            conn.commit()

    def get_recent_edge_cases(self, limit: int = 10, days: int = 7) -> list[ConfidenceMetrics]:
        """Get recent edge cases detected.

        Args:
            limit: Maximum number of edge cases to return
            days: Number of days to look back

        Returns:
            List of ConfidenceMetrics for recent edge cases

        Example:
            >>> edge_cases = handler.get_recent_edge_cases(limit=5, days=7)
            >>> for case in edge_cases:
            ...     print(f"Edge case: {case.pattern_id}, frequency={case.event_frequency:.3f}")

        """
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)

        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT metric_id, pattern_id, sample_size, success_rate,
                       confidence_score, lower_bound, upper_bound,
                       is_edge_case, event_frequency, weighted_score,
                       meets_threshold, timestamp
                FROM edge_case_metrics
                WHERE is_edge_case = 1 AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (cutoff.isoformat(), limit),
            )

            edge_cases = []
            for row in cursor.fetchall():
                edge_cases.append(
                    ConfidenceMetrics(
                        pattern_id=row[1],
                        sample_size=row[2],
                        success_rate=row[3],
                        confidence_score=row[4],
                        lower_bound=row[5],
                        upper_bound=row[6],
                        is_edge_case=bool(row[7]),
                        event_frequency=row[8],
                        weighted_score=row[9],
                        meets_threshold=bool(row[10]),
                        timestamp=datetime.fromisoformat(row[11]),
                    ),
                )

            return edge_cases
