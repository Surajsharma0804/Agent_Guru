"""
Stability Monitor for Self-Improvement Engine.

Detects and prevents oscillations in strategy selection, prompt evolution,
and other learning components. Implements dampening mechanisms to smooth
out rapid changes and maintain system stability.

**Validates: Requirements 9.7 (Rate Limiting and Stability)**

Performance Requirements:
- Time Complexity: O(1) for stability checks
- Space Complexity: O(w) where w is window size
- Stability Check Latency: <1ms (99th percentile)

Author: Agent Guru Team
Date: 2026-02-28
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.connection_pool import ConnectionPool


@dataclass
class StabilityMetrics:
    """Metrics for tracking system stability."""

    component: str
    metric_name: str
    current_value: float
    variance: float
    change_frequency: float
    oscillation_detected: bool
    stability_score: float  # 0.0 (unstable) to 1.0 (stable)
    timestamp: datetime


class StabilityMonitor:
    """
    Monitors system stability and prevents oscillations.

    Tracks changes in strategy selection, prompt evolution, and other
    learning components to detect and prevent unstable behavior patterns.

    Time Complexity: O(1) for stability checks
    Space Complexity: O(w) where w is window size

    Example:
        >>> monitor = StabilityMonitor(pool, window_size=100)
        >>> monitor.record_change("strategy_selection", "task_type_1", 0.75)
        >>> is_stable, metrics = monitor.check_stability("strategy_selection")
        >>> if not is_stable:
        ...     print(f"Oscillation detected: {metrics}")
    """

    def __init__(
        self,
        pool: "ConnectionPool",
        window_size: int = 100,
        variance_threshold: float = 0.15,
        change_frequency_threshold: float = 0.3,
        oscillation_threshold: int = 3,
        dampening_factor: float = 0.7,
    ) -> None:
        """
        Initialize stability monitor.

        Args:
            pool: ConnectionPool for database access
            window_size: Number of recent changes to track (default: 100)
            variance_threshold: Maximum acceptable variance (default: 0.15)
            change_frequency_threshold: Maximum change frequency (default: 0.3)
            oscillation_threshold: Number of back-and-forth changes to detect (default: 3)
            dampening_factor: Dampening factor for rapid changes (default: 0.7)

        Raises:
            RuntimeError: If stability_metrics table doesn't exist
        """
        self.pool = pool
        self.window_size = window_size
        self.variance_threshold = variance_threshold
        self.change_frequency_threshold = change_frequency_threshold
        self.oscillation_threshold = oscillation_threshold
        self.dampening_factor = dampening_factor

        # In-memory tracking for fast access
        self._change_history: dict[str, deque[tuple[datetime, float]]] = {}
        self._last_values: dict[str, float] = {}

        self._init_database()

    def _init_database(self) -> None:
        """
        Initialize database schema for stability metrics.

        Note: DatabaseSchema.create_schema() should be called first.
        This method only verifies the table exists.
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Verify stability_metrics table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='stability_metrics'
            """
            )

            if not cursor.fetchone():
                raise RuntimeError(
                    "Stability_metrics table not found. "
                    "Call DatabaseSchema.create_schema() first."
                )

    def record_change(
        self,
        component: str,
        metric_name: str,
        value: float,
    ) -> None:
        """
        Record a change in a tracked metric.

        Time Complexity: O(1) - append to deque
        Space Complexity: O(1) - bounded by window_size

        Args:
            component: Component name (e.g., "strategy_selection", "prompt_evolution")
            metric_name: Metric name (e.g., "task_type_1", "prompt_type_1")
            value: Current value of the metric

        Example:
            >>> monitor.record_change("strategy_selection", "task_type_1", 0.75)
            >>> monitor.record_change("prompt_evolution", "task_analysis", 0.82)
        """
        key = f"{component}:{metric_name}"
        now = datetime.now()

        # Initialize history if needed
        if key not in self._change_history:
            self._change_history[key] = deque(maxlen=self.window_size)

        # Add to history
        self._change_history[key].append((now, value))
        self._last_values[key] = value

        # Persist to database
        self._persist_change(component, metric_name, value, now)

    def check_stability(
        self,
        component: str,
        metric_name: str | None = None,
    ) -> tuple[bool, StabilityMetrics | None]:
        """
        Check if a component or specific metric is stable.

        Time Complexity: O(w) where w is window_size
        Space Complexity: O(1)

        Args:
            component: Component name to check
            metric_name: Optional specific metric name (None = check all metrics)

        Returns:
            Tuple of (is_stable: bool, metrics: StabilityMetrics | None)
            - is_stable: True if stable, False if oscillating
            - metrics: Stability metrics or None if no data

        Example:
            >>> is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")
            >>> if not is_stable:
            ...     print(f"Oscillation detected: variance={metrics.variance}")
        """
        if metric_name:
            key = f"{component}:{metric_name}"
            if key not in self._change_history or len(self._change_history[key]) < 2:
                return True, None

            metrics = self._calculate_stability_metrics(component, metric_name, key)
            is_stable = not metrics.oscillation_detected

            return is_stable, metrics
        else:
            # Check all metrics for this component
            all_stable = True
            worst_metrics = None
            worst_score = 1.0

            for key in self._change_history:
                if key.startswith(f"{component}:"):
                    _, metric = key.split(":", 1)
                    is_stable, metrics = self.check_stability(component, metric)

                    if not is_stable:
                        all_stable = False

                    if metrics and metrics.stability_score < worst_score:
                        worst_score = metrics.stability_score
                        worst_metrics = metrics

            return all_stable, worst_metrics

    def _calculate_stability_metrics(
        self,
        component: str,
        metric_name: str,
        key: str,
    ) -> StabilityMetrics:
        """
        Calculate stability metrics for a tracked metric.

        Args:
            component: Component name
            metric_name: Metric name
            key: Combined key (component:metric_name)

        Returns:
            StabilityMetrics with calculated values
        """
        history = self._change_history[key]
        values = [v for _, v in history]
        timestamps = [t for t, _ in history]

        # Calculate variance
        if len(values) < 2:
            variance = 0.0
        else:
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)

        # Calculate change frequency (proportion of changes)
        changes = sum(1 for i in range(1, len(values)) if values[i] != values[i - 1])
        change_frequency = changes / (len(values) - 1) if len(values) > 1 else 0.0

        # Detect oscillation (back-and-forth pattern)
        oscillation_detected = self._detect_oscillation(values)

        # Calculate stability score (0.0 = unstable, 1.0 = stable)
        variance_score = max(0.0, 1.0 - (variance / self.variance_threshold))
        frequency_score = max(0.0, 1.0 - (change_frequency / self.change_frequency_threshold))
        oscillation_score = 0.0 if oscillation_detected else 1.0

        stability_score = (variance_score + frequency_score + oscillation_score) / 3.0

        return StabilityMetrics(
            component=component,
            metric_name=metric_name,
            current_value=values[-1],
            variance=variance,
            change_frequency=change_frequency,
            oscillation_detected=oscillation_detected,
            stability_score=stability_score,
            timestamp=timestamps[-1],
        )

    def _detect_oscillation(self, values: list[float]) -> bool:
        """
        Detect oscillation pattern in values.

        Oscillation is detected when values alternate between
        the SAME two or three distinct states repeatedly (e.g., A -> B -> A -> B).
        This is different from a trend (A -> B -> C -> D) or gradual changes.

        Args:
            values: List of values to check

        Returns:
            True if oscillation detected, False otherwise
        """
        if len(values) < self.oscillation_threshold * 2:
            return False

        # Look for alternating pattern in recent values
        recent = values[-(self.oscillation_threshold * 2) :]

        # Get unique values in recent history
        unique_values = list(set(recent))
        
        # If there are more than 3 unique values, it's likely a trend, not oscillation
        if len(unique_values) > 3:
            return False
        
        # If only 1 unique value, no oscillation
        if len(unique_values) <= 1:
            return False

        # Count transitions between distinct values
        transitions = 0
        for i in range(1, len(recent)):
            if recent[i] != recent[i - 1]:
                transitions += 1

        # For true oscillation, we need:
        # 1. At least oscillation_threshold transitions
        # 2. Values must return to previous states (not just changing)
        if transitions < self.oscillation_threshold:
            return False
        
        # Check if values actually return to previous states (true oscillation)
        # Count how many times each unique value appears
        value_counts = {v: recent.count(v) for v in unique_values}
        
        # For oscillation, values should appear multiple times (alternating)
        # If each value appears only once, it's a trend, not oscillation
        min_appearances = min(value_counts.values())
        if min_appearances < 2:
            return False
        
        return True

    def apply_dampening(
        self,
        component: str,
        metric_name: str,
        proposed_value: float,
    ) -> float:
        """
        Apply dampening to smooth rapid changes.

        Uses exponential moving average to dampen rapid changes
        and prevent oscillations.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            component: Component name
            metric_name: Metric name
            proposed_value: Proposed new value

        Returns:
            Dampened value (weighted average of current and proposed)

        Example:
            >>> # Rapid change from 0.5 to 0.9
            >>> dampened = monitor.apply_dampening("strategy_selection", "task_type_1", 0.9)
            >>> # dampened will be closer to 0.5 (e.g., 0.72 with factor 0.7)
        """
        key = f"{component}:{metric_name}"

        if key not in self._last_values:
            # No history, return proposed value
            return proposed_value

        current_value = self._last_values[key]

        # Apply exponential moving average
        # dampened = current * factor + proposed * (1 - factor)
        dampened_value = (
            current_value * self.dampening_factor
            + proposed_value * (1 - self.dampening_factor)
        )

        return dampened_value

    def should_allow_change(
        self,
        component: str,
        metric_name: str,
        proposed_value: float,
    ) -> tuple[bool, str]:
        """
        Determine if a proposed change should be allowed.

        Checks stability and applies dampening if needed.

        Time Complexity: O(w) where w is window_size
        Space Complexity: O(1)

        Args:
            component: Component name
            metric_name: Metric name
            proposed_value: Proposed new value

        Returns:
            Tuple of (allow: bool, reason: str)
            - allow: True if change should be allowed
            - reason: Explanation if change is blocked

        Example:
            >>> allow, reason = monitor.should_allow_change(
            ...     "strategy_selection", "task_type_1", 0.9
            ... )
            >>> if not allow:
            ...     print(f"Change blocked: {reason}")
        """
        is_stable, metrics = self.check_stability(component, metric_name)

        if not is_stable and metrics:
            # System is unstable, block change
            return (
                False,
                f"Stability check failed: oscillation detected "
                f"(variance={metrics.variance:.3f}, "
                f"change_frequency={metrics.change_frequency:.3f}, "
                f"stability_score={metrics.stability_score:.3f})",
            )

        # Check if proposed change is too large
        key = f"{component}:{metric_name}"
        if key in self._last_values:
            current_value = self._last_values[key]
            change_magnitude = abs(proposed_value - current_value)

            # Block very large changes (>50% of current value)
            if change_magnitude > 0.5:
                return (
                    False,
                    f"Change too large: {change_magnitude:.3f} "
                    f"(current={current_value:.3f}, proposed={proposed_value:.3f})",
                )

        return True, "Change allowed"

    def get_stability_report(
        self,
        component: str | None = None,
    ) -> dict[str, Any]:
        """
        Get comprehensive stability report.

        Args:
            component: Optional component name (None = all components)

        Returns:
            Dictionary with stability report:
            - components: List of component names
            - metrics: List of StabilityMetrics for each tracked metric
            - overall_stability_score: Average stability score
            - unstable_metrics: List of unstable metrics
            - recommendations: List of recommended actions

        Example:
            >>> report = monitor.get_stability_report("strategy_selection")
            >>> print(f"Overall stability: {report['overall_stability_score']:.2f}")
            >>> for metric in report['unstable_metrics']:
            ...     print(f"Unstable: {metric.component}:{metric.metric_name}")
        """
        metrics_list = []
        unstable_metrics = []

        for key in self._change_history:
            comp, metric = key.split(":", 1)

            if component and comp != component:
                continue

            # Only check if we have enough data
            if len(self._change_history[key]) < 2:
                continue

            is_stable, metrics = self.check_stability(comp, metric)

            if metrics:
                metrics_list.append(metrics)

                if not is_stable:
                    unstable_metrics.append(metrics)

        # Calculate overall stability score
        if metrics_list:
            overall_stability_score = sum(m.stability_score for m in metrics_list) / len(
                metrics_list
            )
        else:
            overall_stability_score = 1.0

        # Generate recommendations
        recommendations = []
        if unstable_metrics:
            recommendations.append(
                "Reduce update frequency for unstable components"
            )
            recommendations.append(
                "Apply dampening to smooth rapid changes"
            )
            recommendations.append(
                "Investigate root cause of oscillations"
            )

        # Get unique components
        components = list(set(m.component for m in metrics_list))

        return {
            "components": components,
            "metrics": metrics_list,
            "overall_stability_score": overall_stability_score,
            "unstable_metrics": unstable_metrics,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
        }

    def reset_history(
        self,
        component: str | None = None,
        metric_name: str | None = None,
    ) -> None:
        """
        Reset change history for a component or metric.

        Args:
            component: Optional component name (None = all components)
            metric_name: Optional metric name (None = all metrics in component)

        Example:
            >>> # Reset specific metric
            >>> monitor.reset_history("strategy_selection", "task_type_1")
            >>>
            >>> # Reset all metrics for component
            >>> monitor.reset_history("strategy_selection")
            >>>
            >>> # Reset everything
            >>> monitor.reset_history()
        """
        if component is None:
            # Reset everything
            self._change_history.clear()
            self._last_values.clear()
        elif metric_name is None:
            # Reset all metrics for component
            keys_to_remove = [k for k in self._change_history if k.startswith(f"{component}:")]
            for key in keys_to_remove:
                del self._change_history[key]
                if key in self._last_values:
                    del self._last_values[key]
        else:
            # Reset specific metric
            key = f"{component}:{metric_name}"
            if key in self._change_history:
                del self._change_history[key]
            if key in self._last_values:
                del self._last_values[key]

    def _persist_change(
        self,
        component: str,
        metric_name: str,
        value: float,
        timestamp: datetime,
    ) -> None:
        """
        Persist change to database.

        Args:
            component: Component name
            metric_name: Metric name
            value: Value
            timestamp: Timestamp of change
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Use timestamp with microseconds and a random suffix for uniqueness
            import random
            metric_id = f"{component}_{metric_name}_{timestamp.timestamp()}_{random.randint(0, 999999)}"

            cursor.execute(
                """
                INSERT INTO stability_metrics (
                    metric_id, component, metric_name, value,
                    variance, change_frequency, oscillation_detected,
                    stability_score, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metric_id,
                    component,
                    metric_name,
                    value,
                    0.0,  # Will be calculated on next check
                    0.0,  # Will be calculated on next check
                    0,  # Will be calculated on next check
                    1.0,  # Will be calculated on next check
                    timestamp.isoformat(),
                ),
            )

            conn.commit()

    def get_recent_changes(
        self,
        component: str,
        metric_name: str,
        limit: int = 10,
    ) -> list[tuple[datetime, float]]:
        """
        Get recent changes for a metric.

        Args:
            component: Component name
            metric_name: Metric name
            limit: Maximum number of changes to return

        Returns:
            List of (timestamp, value) tuples, newest first

        Example:
            >>> changes = monitor.get_recent_changes("strategy_selection", "task_type_1", limit=5)
            >>> for timestamp, value in changes:
            ...     print(f"{timestamp}: {value}")
        """
        key = f"{component}:{metric_name}"

        if key not in self._change_history:
            return []

        history = list(self._change_history[key])
        return history[-limit:][::-1]  # Newest first
