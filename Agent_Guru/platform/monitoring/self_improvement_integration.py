"""
Module: agent_guru.platform.monitoring.self_improvement_integration
Purpose: Integration with Self-Improvement Engine for resource monitoring

This module provides integration between the Resource Monitor and the
Self-Improvement Engine, enabling the system to learn from resource usage
patterns and optimize performance over time.

Performance Requirements:
- Time Complexity: O(1) per alert notification
- Space Complexity: O(1) per notification
- Latency: <5ms per notification

Design Decisions:
- Async notification to avoid blocking monitoring
- Structured data format for ML analysis
- Automatic metric aggregation
- Failure isolation (errors don't affect monitoring)

Author: Agent Guru Team
Date: 2026-02-25
Version: 1.0.0
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import logging

from .resource_monitor import AlertSeverity, ResourceAlert, ResourceSnapshot, ResourceType

_logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics sent to Self-Improvement Engine."""
    ALERT_TRIGGERED = "alert_triggered"
    RESOURCE_SNAPSHOT = "resource_snapshot"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    RESOURCE_EXHAUSTION_PREDICTED = "resource_exhaustion_predicted"


@dataclass
class SelfImprovementMetric:
    """
    Metric data sent to Self-Improvement Engine.

    This structured format enables the Self-Improvement Engine to:
    - Learn resource usage patterns
    - Predict future resource needs
    - Optimize threshold configurations
    - Recommend performance improvements
    """
    metric_type: MetricType
    timestamp: datetime
    resource_type: Optional[ResourceType]
    severity: Optional[AlertSeverity]
    current_value: Optional[float]
    threshold_value: Optional[float]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert metric to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to strings
        data['metric_type'] = self.metric_type.value
        if self.resource_type:
            data['resource_type'] = self.resource_type.value
        if self.severity:
            data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


class SelfImprovementIntegration:
    """
    Integration layer between Resource Monitor and Self-Improvement Engine.

    Responsibilities:
    - Convert alerts to structured metrics
    - Aggregate resource snapshots
    - Send notifications to Self-Improvement Engine
    - Handle communication failures gracefully

    Time Complexity: O(1) per notification
    Space Complexity: O(1)

    Example:
        >>> integration = SelfImprovementIntegration()
        >>> monitor.register_alert_callback(integration.on_alert)
        >>> # Alerts automatically sent to Self-Improvement Engine
    """

    def __init__(self, enable_logging: bool = True):
        """
        Initialize Self-Improvement Engine integration.

        Args:
            enable_logging: Whether to log notifications (for debugging)
        """
        self.enable_logging = enable_logging
        self._notification_count = 0
        self._error_count = 0

    def on_alert(self, alert: ResourceAlert) -> None:
        """
        Handle resource alert from Resource Monitor.

        This callback is registered with ResourceMonitor and called
        whenever an alert is triggered.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            alert: Resource alert to process
        """
        try:
            # Convert alert to metric
            metric = SelfImprovementMetric(
                metric_type=MetricType.ALERT_TRIGGERED,
                timestamp=alert.timestamp,
                resource_type=alert.resource_type,
                severity=alert.severity,
                current_value=alert.current_value,
                threshold_value=alert.threshold_value,
                metadata={
                    'alert_id': alert.alert_id,
                    'message': alert.message,
                    'recommended_action': alert.recommended_action
                }
            )

            # Send to Self-Improvement Engine
            self._send_metric(metric)

        except Exception as e:
            # Isolate errors - don't let them affect monitoring
            self._error_count += 1
            if self.enable_logging:
                _logger.error("Error in Self-Improvement integration: %s", e)

    def on_resource_snapshot(self, snapshot: ResourceSnapshot) -> None:
        """
        Handle periodic resource snapshot.

        Sends aggregated metrics to Self-Improvement Engine for
        pattern analysis and optimization.

        Args:
            snapshot: Resource usage snapshot
        """
        try:
            # Create metric with aggregated data
            metric = SelfImprovementMetric(
                metric_type=MetricType.RESOURCE_SNAPSHOT,
                timestamp=snapshot.timestamp,
                resource_type=None,  # Multiple resources
                severity=None,
                current_value=None,
                threshold_value=None,
                metadata={
                    'cpu_percent': snapshot.cpu_percent,
                    'memory_percent': snapshot.memory_percent,
                    'swap_percent': snapshot.swap_percent,
                    'process_count': snapshot.process_count,
                    'thread_count': snapshot.thread_count,
                    'disk_usage': {
                        path: usage.percent
                        for path, usage in snapshot.disk_usage.items()
                    },
                    'gpu_usage': [
                        {
                            'id': gpu.id,
                            'load': gpu.load,
                            'memory_percent': gpu.memory_percent
                        }
                        for gpu in (snapshot.gpu_usage or [])
                    ]
                }
            )

            self._send_metric(metric)

        except Exception as e:
            self._error_count += 1
            if self.enable_logging:
                _logger.error("Error sending snapshot to Self-Improvement Engine: %s", e)

    def on_threshold_exceeded(
        self,
        resource_type: ResourceType,
        current_value: float,
        threshold_value: float
    ) -> None:
        """
        Notify when threshold is exceeded (before alert is triggered).

        This enables the Self-Improvement Engine to learn about
        near-threshold conditions and optimize thresholds.

        Args:
            resource_type: Type of resource
            current_value: Current resource value
            threshold_value: Threshold that was exceeded
        """
        try:
            metric = SelfImprovementMetric(
                metric_type=MetricType.THRESHOLD_EXCEEDED,
                timestamp=datetime.now(tz=timezone.utc),
                resource_type=resource_type,
                severity=None,
                current_value=current_value,
                threshold_value=threshold_value,
                metadata={}
            )

            self._send_metric(metric)

        except Exception as e:
            self._error_count += 1
            if self.enable_logging:
                _logger.error("Error notifying threshold exceeded: %s", e)

    def on_resource_exhaustion_predicted(
        self,
        resource_type: ResourceType,
        predicted_time: datetime,
        current_value: float
    ) -> None:
        """
        Notify when resource exhaustion is predicted.

        Enables proactive optimization before resources are exhausted.

        Args:
            resource_type: Type of resource
            predicted_time: Predicted exhaustion time
            current_value: Current resource value
        """
        try:
            metric = SelfImprovementMetric(
                metric_type=MetricType.RESOURCE_EXHAUSTION_PREDICTED,
                timestamp=datetime.now(tz=timezone.utc),
                resource_type=resource_type,
                severity=AlertSeverity.HIGH,
                current_value=current_value,
                threshold_value=100.0,  # Exhaustion threshold
                metadata={
                    'predicted_time': predicted_time.isoformat(),
                    'time_until_exhaustion': (
                        predicted_time - datetime.now(tz=timezone.utc)
                    ).total_seconds()
                }
            )

            self._send_metric(metric)

        except Exception as e:
            self._error_count += 1
            if self.enable_logging:
                _logger.error("Error notifying resource exhaustion prediction: %s", e)

    def _send_metric(self, metric: SelfImprovementMetric) -> None:
        """
        Send metric to Self-Improvement Engine.

        Currently logs metrics. In production, this would send to
        the actual Self-Improvement Engine via API or message queue.

        Args:
            metric: Metric to send
        """
        self._notification_count += 1

        if self.enable_logging:
            _logger.debug(
                "Self-Improvement metric: %s resource=%s ts=%s",
                metric.metric_type.value,
                metric.resource_type.value if metric.resource_type else "N/A",
                metric.timestamp.isoformat(),
            )

        # TODO: Implement actual Self-Improvement Engine API call
        # Example:
        # async with aiohttp.ClientSession() as session:
        #     await session.post(
        #         'http://self-improvement-engine/api/metrics',
        #         json=metric.to_dict()
        #     )

    def get_stats(self) -> dict[str, int]:
        """
        Get integration statistics.

        Returns:
            Dictionary with notification and error counts
        """
        return {
            'notifications_sent': self._notification_count,
            'errors': self._error_count
        }
