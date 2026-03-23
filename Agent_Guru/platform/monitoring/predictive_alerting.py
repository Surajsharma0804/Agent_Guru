"""
Module: agent_guru.platform.monitoring.predictive_alerting
Purpose: Predictive resource exhaustion detection and alerting

This module implements predictive alerting using:
- Historical metrics storage with efficient time-series data structures
- Trend analysis using linear regression and moving averages
- Resource exhaustion prediction with configurable horizons
- Predictive alert generation with severity levels

Performance Requirements:
- Time Complexity: O(n) for trend analysis where n is window size
- Space Complexity: O(history_size) for historical data
- Prediction Latency: <50ms per resource type
- Memory Usage: <100MB for 24 hours of history

Design Decisions:
- Use deque for fixed-size history (O(1) append/pop)
- Use numpy for efficient numerical operations (10x faster)
- Use simple linear regression (fast, interpretable)
- Use moving averages for noise reduction
- Preallocate arrays for zero-copy operations

Author: Agent Guru Team
Date: 2026-02-25
Version: 1.0.0
"""

import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from .resource_monitor import AlertSeverity, ResourceSnapshot, ResourceType


class TrendDirection(Enum):
    """Trend direction for resource usage."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


class PredictionConfidence(Enum):
    """Confidence level for predictions."""
    LOW = "low"  # <60% confidence
    MEDIUM = "medium"  # 60-80% confidence
    HIGH = "high"  # >80% confidence


@dataclass
class TrendAnalysis:
    """Result of trend analysis for a resource."""
    resource_type: ResourceType
    direction: TrendDirection
    slope: float  # Rate of change per second
    r_squared: float  # Goodness of fit (0-1)
    current_value: float
    predicted_value_1h: float
    predicted_value_24h: float
    confidence: PredictionConfidence
    timestamp: datetime


@dataclass
class ExhaustionPrediction:
    """Prediction of when a resource will be exhausted."""
    resource_type: ResourceType
    current_value: float
    exhaustion_threshold: float
    predicted_exhaustion_time: datetime
    time_until_exhaustion: timedelta
    confidence: PredictionConfidence
    trend_slope: float
    r_squared: float
    timestamp: datetime


@dataclass
class PredictiveAlert:
    """Predictive alert for potential resource exhaustion."""
    alert_id: str
    resource_type: ResourceType
    severity: AlertSeverity
    prediction: ExhaustionPrediction
    message: str
    recommended_action: str
    timestamp: datetime


@dataclass
class PredictiveAlertingConfig:
    """Configuration for predictive alerting."""
    # Trend analysis
    trend_window_size: int = 120  # Number of samples (10 minutes at 5s interval)
    min_samples_for_prediction: int = 10  # Minimum samples needed

    # Prediction horizons
    short_term_horizon: timedelta = timedelta(hours=1)
    medium_term_horizon: timedelta = timedelta(hours=6)
    long_term_horizon: timedelta = timedelta(hours=24)

    # Exhaustion thresholds
    cpu_exhaustion_threshold: float = 95.0  # %
    memory_exhaustion_threshold: float = 95.0  # %
    disk_exhaustion_threshold: float = 95.0  # %
    gpu_exhaustion_threshold: float = 95.0  # %

    # Alert thresholds (time until exhaustion)
    critical_threshold: timedelta = timedelta(minutes=15)
    high_threshold: timedelta = timedelta(hours=1)
    medium_threshold: timedelta = timedelta(hours=6)

    # Confidence thresholds
    min_confidence_for_alert: float = 0.6  # R² threshold

    # Noise filtering
    use_moving_average: bool = True
    moving_average_window: int = 5  # Smooth over 5 samples


class PredictiveAlerting:
    """
    Predictive resource exhaustion detection and alerting.

    Analyzes historical resource metrics to predict future exhaustion
    and generate proactive alerts.

    Time Complexity: O(n) for trend analysis where n is window size
    Space Complexity: O(history_size) for historical data

    Example:
        >>> config = PredictiveAlertingConfig()
        >>> predictor = PredictiveAlerting(config)
        >>>
        >>> # Add historical snapshots
        >>> for snapshot in snapshots:
        ...     predictor.add_snapshot(snapshot)
        >>>
        >>> # Analyze trends
        >>> trend = predictor.analyze_trend(ResourceType.CPU)
        >>> print(f"CPU trend: {trend.direction}, slope: {trend.slope}")
        >>>
        >>> # Predict exhaustion
        >>> prediction = predictor.predict_exhaustion(ResourceType.MEMORY)
        >>> if prediction:
        ...     print(f"Memory exhaustion in {prediction.time_until_exhaustion}")
    """

    def __init__(self, config: Optional[PredictiveAlertingConfig] = None):
        """
        Initialize predictive alerting.

        Args:
            config: Predictive alerting configuration
        """
        self.config = config or PredictiveAlertingConfig()

        # Historical metrics storage (fixed size for memory efficiency)
        self.metrics_history: deque[ResourceSnapshot] = deque(
            maxlen=10000  # ~14 hours at 5s interval
        )

        # Trend analysis cache (avoid recomputation)
        self._trend_cache: dict[ResourceType, tuple[TrendAnalysis, float]] = {}
        self._cache_ttl: float = 60.0  # Cache valid for 60 seconds

        # Active predictive alerts
        self._active_predictions: dict[str, PredictiveAlert] = {}

        # Prediction history
        self._prediction_history: deque[ExhaustionPrediction] = deque(maxlen=1000)

    def add_snapshot(self, snapshot: ResourceSnapshot) -> None:
        """
        Add resource snapshot to historical data.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            snapshot: Resource usage snapshot
        """
        self.metrics_history.append(snapshot)

        # Invalidate trend cache
        self._trend_cache.clear()

    def analyze_trend(
        self,
        resource_type: ResourceType,
        window_size: Optional[int] = None
    ) -> Optional[TrendAnalysis]:
        """
        Analyze resource usage trend using linear regression.

        Time Complexity: O(n) where n is window size
        Space Complexity: O(n) for temporary arrays

        Args:
            resource_type: Type of resource to analyze
            window_size: Number of recent samples to analyze (uses config if None)

        Returns:
            Trend analysis result, or None if insufficient data
        """
        # Check cache
        cache_key = resource_type
        if cache_key in self._trend_cache:
            cached_trend, cache_time = self._trend_cache[cache_key]
            if time.time() - cache_time < self._cache_ttl:
                return cached_trend

        if window_size is None:
            window_size = self.config.trend_window_size

        if len(self.metrics_history) < self.config.min_samples_for_prediction:
            return None

        # Get recent snapshots
        recent = list(self.metrics_history)[-window_size:]

        if len(recent) < self.config.min_samples_for_prediction:
            return None

        # Extract values based on resource type
        values = self._extract_values(recent, resource_type)

        if not values or len(values) < self.config.min_samples_for_prediction:
            return None

        # Apply moving average for noise reduction
        if self.config.use_moving_average:
            values = self._moving_average(
                values,
                self.config.moving_average_window
            )

        # Perform linear regression
        slope, intercept, r_squared = self._linear_regression(values)

        # Determine trend direction
        if abs(slope) < 0.01:  # Threshold for "stable"
            direction = TrendDirection.STABLE
        elif slope > 0:
            direction = TrendDirection.INCREASING
        else:
            direction = TrendDirection.DECREASING

        # Calculate confidence
        if r_squared >= 0.8:
            confidence = PredictionConfidence.HIGH
        elif r_squared >= 0.6:
            confidence = PredictionConfidence.MEDIUM
        else:
            confidence = PredictionConfidence.LOW

        # Get time interval between samples
        if len(recent) >= 2:
            time_delta = (recent[-1].timestamp - recent[0].timestamp).total_seconds()
            samples_per_second = len(recent) / time_delta if time_delta > 0 else 1.0
        else:
            samples_per_second = 1.0

        # Convert slope to per-second rate
        slope_per_second = slope * samples_per_second

        # Predict future values
        current_value = values[-1]
        predicted_1h = current_value + (slope_per_second * 3600)  # 1 hour
        predicted_24h = current_value + (slope_per_second * 86400)  # 24 hours

        # Clamp predictions to valid range [0, 100]
        predicted_1h = max(0.0, min(100.0, predicted_1h))
        predicted_24h = max(0.0, min(100.0, predicted_24h))

        trend = TrendAnalysis(
            resource_type=resource_type,
            direction=direction,
            slope=slope_per_second,
            r_squared=r_squared,
            current_value=current_value,
            predicted_value_1h=predicted_1h,
            predicted_value_24h=predicted_24h,
            confidence=confidence,
            timestamp=datetime.now()
        )

        # Cache result
        self._trend_cache[cache_key] = (trend, time.time())

        return trend

    def predict_exhaustion(
        self,
        resource_type: ResourceType,
        horizon: Optional[timedelta] = None
    ) -> Optional[ExhaustionPrediction]:
        """
        Predict when resource will be exhausted based on current trend.

        Time Complexity: O(n) where n is window size
        Space Complexity: O(n) for temporary arrays

        Args:
            resource_type: Type of resource to predict
            horizon: Maximum prediction horizon (uses config if None)

        Returns:
            Exhaustion prediction, or None if no exhaustion predicted
        """
        if horizon is None:
            horizon = self.config.long_term_horizon

        # Analyze trend
        trend = self.analyze_trend(resource_type)

        if trend is None:
            return None

        # Check if trend is increasing
        if trend.direction != TrendDirection.INCREASING:
            return None

        # Check confidence
        if trend.r_squared < self.config.min_confidence_for_alert:
            return None

        # Get exhaustion threshold
        threshold = self._get_exhaustion_threshold(resource_type)

        # Calculate time to exhaustion
        current_value = trend.current_value
        remaining = threshold - current_value

        if remaining <= 0:
            # Already exhausted
            prediction = ExhaustionPrediction(
                resource_type=resource_type,
                current_value=current_value,
                exhaustion_threshold=threshold,
                predicted_exhaustion_time=datetime.now(),
                time_until_exhaustion=timedelta(0),
                confidence=trend.confidence,
                trend_slope=trend.slope,
                r_squared=trend.r_squared,
                timestamp=datetime.now()
            )
            self._prediction_history.append(prediction)
            return prediction

        if trend.slope <= 0:
            # Not increasing, no exhaustion predicted
            return None

        # Time to exhaustion in seconds
        seconds_to_exhaustion = remaining / trend.slope
        time_to_exhaustion = timedelta(seconds=seconds_to_exhaustion)

        # Check if within horizon
        if time_to_exhaustion > horizon:
            return None

        prediction = ExhaustionPrediction(
            resource_type=resource_type,
            current_value=current_value,
            exhaustion_threshold=threshold,
            predicted_exhaustion_time=datetime.now() + time_to_exhaustion,
            time_until_exhaustion=time_to_exhaustion,
            confidence=trend.confidence,
            trend_slope=trend.slope,
            r_squared=trend.r_squared,
            timestamp=datetime.now()
        )

        # Store in history
        self._prediction_history.append(prediction)

        return prediction

    def generate_predictive_alerts(self) -> list[PredictiveAlert]:
        """
        Generate predictive alerts for all resource types.

        Time Complexity: O(k * n) where k is number of resource types, n is window size
        Space Complexity: O(k) for alerts

        Returns:
            List of predictive alerts
        """
        alerts = []

        # Check each resource type
        for resource_type in [ResourceType.CPU, ResourceType.MEMORY, ResourceType.DISK]:
            prediction = self.predict_exhaustion(resource_type)

            if prediction is None:
                continue

            # Determine severity based on time until exhaustion
            severity = self._calculate_prediction_severity(
                prediction.time_until_exhaustion
            )

            # Create alert
            alert_id = f"predictive_{resource_type.value}"

            alert = PredictiveAlert(
                alert_id=alert_id,
                resource_type=resource_type,
                severity=severity,
                prediction=prediction,
                message=self._generate_alert_message(prediction),
                recommended_action=self._generate_recommended_action(prediction),
                timestamp=datetime.now()
            )

            alerts.append(alert)
            self._active_predictions[alert_id] = alert

        return alerts

    def get_prediction_history(
        self,
        resource_type: Optional[ResourceType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> list[ExhaustionPrediction]:
        """
        Get prediction history with optional filters.

        Time Complexity: O(n) where n is history size
        Space Complexity: O(m) where m is matching predictions

        Args:
            resource_type: Filter by resource type
            start_time: Filter predictions after this time
            end_time: Filter predictions before this time

        Returns:
            List of predictions matching filters
        """
        predictions = list(self._prediction_history)

        if resource_type is not None:
            predictions = [p for p in predictions if p.resource_type == resource_type]

        if start_time is not None:
            predictions = [p for p in predictions if p.timestamp >= start_time]

        if end_time is not None:
            predictions = [p for p in predictions if p.timestamp <= end_time]

        return predictions

    def get_active_predictions(self) -> list[PredictiveAlert]:
        """
        Get currently active predictive alerts.

        Returns:
            List of active predictive alerts
        """
        return list(self._active_predictions.values())

    def clear_prediction(self, alert_id: str) -> bool:
        """
        Clear an active predictive alert.

        Args:
            alert_id: ID of alert to clear

        Returns:
            True if alert was found and cleared
        """
        if alert_id in self._active_predictions:
            del self._active_predictions[alert_id]
            return True
        return False

    def _extract_values(
        self,
        snapshots: list[ResourceSnapshot],
        resource_type: ResourceType
    ) -> list[float]:
        """
        Extract values for specific resource type from snapshots.

        Args:
            snapshots: List of resource snapshots
            resource_type: Type of resource to extract

        Returns:
            List of values
        """
        values = []

        for snapshot in snapshots:
            if resource_type == ResourceType.CPU:
                values.append(snapshot.cpu_percent)
            elif resource_type == ResourceType.MEMORY:
                values.append(snapshot.memory_percent)
            elif resource_type == ResourceType.DISK:
                # Use root partition
                if "/" in snapshot.disk_usage:
                    values.append(snapshot.disk_usage["/"].percent)
                elif "C:\\" in snapshot.disk_usage:
                    values.append(snapshot.disk_usage["C:\\"].percent)
            elif resource_type == ResourceType.GPU:
                if snapshot.gpu_usage and len(snapshot.gpu_usage) > 0:
                    values.append(snapshot.gpu_usage[0].memory_percent)

        return values

    def _moving_average(self, values: list[float], window: int) -> list[float]:
        """
        Apply moving average smoothing.

        Time Complexity: O(n)
        Space Complexity: O(n)

        Args:
            values: Input values
            window: Window size for moving average

        Returns:
            Smoothed values
        """
        if len(values) < window:
            return values

        if NUMPY_AVAILABLE:
            # Use numpy for efficient computation
            arr = np.array(values)
            weights = np.ones(window) / window
            smoothed = np.convolve(arr, weights, mode='valid')
            # Pad beginning to maintain length
            padding = [values[0]] * (window - 1)
            return padding + smoothed.tolist()
        else:
            # Pure Python implementation
            smoothed = []
            for i in range(len(values)):
                if i < window - 1:
                    smoothed.append(values[i])
                else:
                    avg = sum(values[i - window + 1:i + 1]) / window
                    smoothed.append(avg)
            return smoothed

    def _linear_regression(
        self,
        values: list[float]
    ) -> tuple[float, float, float]:
        """
        Perform simple linear regression.

        Time Complexity: O(n)
        Space Complexity: O(1)

        Args:
            values: Y values (X is assumed to be 0, 1, 2, ...)

        Returns:
            Tuple of (slope, intercept, r_squared)
        """
        n = len(values)

        if n < 2:
            return (0.0, values[0] if values else 0.0, 0.0)

        if NUMPY_AVAILABLE:
            # Use numpy for efficient computation
            x = np.arange(n)
            y = np.array(values)

            # Calculate slope and intercept
            x_mean = np.mean(x)
            y_mean = np.mean(y)

            numerator = np.sum((x - x_mean) * (y - y_mean))
            denominator = np.sum((x - x_mean) ** 2)

            if denominator == 0:
                return (0.0, y_mean, 0.0)

            slope = numerator / denominator
            intercept = y_mean - slope * x_mean

            # Calculate R²
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y_mean) ** 2)

            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

            return (float(slope), float(intercept), float(r_squared))
        else:
            # Pure Python implementation
            x = list(range(n))
            y = values

            x_mean = sum(x) / n
            y_mean = sum(y) / n

            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                return (0.0, y_mean, 0.0)

            slope = numerator / denominator
            intercept = y_mean - slope * x_mean

            # Calculate R²
            y_pred = [slope * x[i] + intercept for i in range(n)]
            ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
            ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))

            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

            return (slope, intercept, r_squared)

    def _get_exhaustion_threshold(self, resource_type: ResourceType) -> float:
        """Get exhaustion threshold for resource type."""
        if resource_type == ResourceType.CPU:
            return self.config.cpu_exhaustion_threshold
        elif resource_type == ResourceType.MEMORY:
            return self.config.memory_exhaustion_threshold
        elif resource_type == ResourceType.DISK:
            return self.config.disk_exhaustion_threshold
        elif resource_type == ResourceType.GPU:
            return self.config.gpu_exhaustion_threshold
        else:
            return 95.0

    def _calculate_prediction_severity(
        self,
        time_until_exhaustion: timedelta
    ) -> AlertSeverity:
        """Calculate alert severity based on time until exhaustion."""
        if time_until_exhaustion <= self.config.critical_threshold:
            return AlertSeverity.CRITICAL
        elif time_until_exhaustion <= self.config.high_threshold:
            return AlertSeverity.HIGH
        elif time_until_exhaustion <= self.config.medium_threshold:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW

    def _generate_alert_message(self, prediction: ExhaustionPrediction) -> str:
        """Generate human-readable alert message."""
        resource_name = prediction.resource_type.value.upper()

        hours = int(prediction.time_until_exhaustion.total_seconds() / 3600)
        minutes = int((prediction.time_until_exhaustion.total_seconds() % 3600) / 60)

        if hours > 0:
            time_str = f"{hours}h {minutes}m"
        else:
            time_str = f"{minutes}m"

        return (
            f"{resource_name} predicted to reach "
            f"{prediction.exhaustion_threshold:.0f}% in {time_str} "
            f"(current: {prediction.current_value:.1f}%, "
            f"trend: +{prediction.trend_slope:.2f}%/s)"
        )

    def _generate_recommended_action(
        self,
        prediction: ExhaustionPrediction
    ) -> str:
        """Generate recommended action for prediction."""
        resource_type = prediction.resource_type

        if resource_type == ResourceType.CPU:
            return (
                "Consider throttling operations, closing applications, "
                "or scaling up compute resources"
            )
        elif resource_type == ResourceType.MEMORY:
            return (
                "Consider freeing memory, closing applications, "
                "or increasing available RAM"
            )
        elif resource_type == ResourceType.DISK:
            return (
                "Consider cleaning temporary files, archiving old data, "
                "or expanding storage capacity"
            )
        elif resource_type == ResourceType.GPU:
            return (
                "Consider reducing batch size, model size, "
                "or adding GPU resources"
            )
        else:
            return "Monitor resource usage and take corrective action"
