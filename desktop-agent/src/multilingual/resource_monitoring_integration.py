"""
Resource Monitoring and Throttling Integration

IMPLEMENTS REQUIREMENT 14.6:
- Create resource usage monitoring for multilingual processing
- Implement appropriate throttling to prevent resource exhaustion
- Create performance metrics collection and reporting

This module provides integration examples and utilities for resource monitoring
and throttling in production multilingual systems.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

from .performance_optimization import ResourceMonitor, ResourceUsageMetrics


class ThrottleStrategy(Enum):
    """Throttling strategies for resource management."""

    NONE = "none"  # No throttling
    DELAY = "delay"  # Add delays between operations
    QUEUE = "queue"  # Queue operations for later processing
    REJECT = "reject"  # Reject new operations
    ADAPTIVE = "adaptive"  # Dynamically adjust based on load


@dataclass
class ResourceThresholds:
    """Resource usage thresholds for monitoring."""

    # CPU thresholds
    cpu_warning: float = 70.0
    cpu_critical: float = 85.0
    cpu_emergency: float = 95.0

    # Memory thresholds
    memory_warning: float = 75.0
    memory_critical: float = 85.0
    memory_emergency: float = 95.0

    # Process-specific thresholds
    process_memory_warning_mb: float = 1024.0
    process_memory_critical_mb: float = 2048.0

    # GPU thresholds (if applicable)
    gpu_memory_warning: float = 80.0
    gpu_memory_critical: float = 90.0


class ResourceAwareProcessor:
    """
    Processor with integrated resource monitoring and throttling.

    This class demonstrates production-grade resource management for
    multilingual processing systems.
    """

    def __init__(
        self,
        thresholds: Optional[ResourceThresholds] = None,
        throttle_strategy: ThrottleStrategy = ThrottleStrategy.ADAPTIVE,
    ):
        self.logger = logging.getLogger(__name__)

        self.thresholds = thresholds or ResourceThresholds()
        self.throttle_strategy = throttle_strategy

        # Initialize resource monitor
        self.resource_monitor = ResourceMonitor(
            cpu_threshold=self.thresholds.cpu_critical,
            memory_threshold=self.thresholds.memory_critical,
            monitoring_interval_seconds=1.0,
        )

        # Start monitoring
        self.resource_monitor.start_monitoring()

        # Operation tracking
        self._operations_processed = 0
        self._operations_throttled = 0
        self._operations_rejected = 0

        self.logger.info(f"Resource-aware processor initialized with {throttle_strategy.value} throttling")

    def process_with_resource_awareness(
        self, operation_func: Callable[[], Any], operation_name: str = "operation"
    ) -> Dict[str, Any]:
        """
        Process operation with resource awareness and throttling.

        Args:
            operation_func: Function to execute
            operation_name: Name of operation for logging

        Returns:
            Result dictionary with operation result and metrics
        """
        start_time = time.time()

        # Check current resource usage
        current_metrics = self.resource_monitor.get_current_metrics()

        if not current_metrics:
            # No metrics available yet, proceed with operation
            _result = operation_func()
            processing_time_ms = int((time.time() - start_time) * 1000)

            self._operations_processed += 1

            return {
                "success": True,
                "result": result,
                "processing_time_ms": processing_time_ms,
                "throttled": False,
                "resource_status": "unknown",
            }

        # Determine resource status
        resource_status = self._assess_resource_status(current_metrics)

        # Apply throttling strategy
        throttle_action = self._determine_throttle_action(resource_status)

        if throttle_action == "reject":
            self._operations_rejected += 1
            self.logger.warning(
                f"Operation '{operation_name}' rejected due to resource constraints: "
                f"CPU={current_metrics.cpu_percent:.1f}%, Memory={current_metrics.memory_percent:.1f}%"
            )

            return {
                "success": False,
                "error": "Operation rejected due to resource constraints",
                "resource_status": resource_status,
                "throttled": True,
                "metrics": {
                    "cpu_percent": current_metrics.cpu_percent,
                    "memory_percent": current_metrics.memory_percent,
                },
            }

        elif throttle_action == "delay":
            # Apply throttling delay
            delay_ms = self.resource_monitor.get_throttle_delay_ms()
            if delay_ms > 0:
                self._operations_throttled += 1
                self.logger.debug(f"Throttling operation '{operation_name}' by {delay_ms}ms")
                time.sleep(delay_ms / 1000.0)

        # Execute operation
        try:
            _result = operation_func()
            processing_time_ms = int((time.time() - start_time) * 1000)

            self._operations_processed += 1

            return {
                "success": True,
                "result": result,
                "processing_time_ms": processing_time_ms,
                "throttled": throttle_action == "delay",
                "resource_status": resource_status,
                "metrics": {
                    "cpu_percent": current_metrics.cpu_percent,
                    "memory_percent": current_metrics.memory_percent,
                    "process_memory_mb": current_metrics.process_memory_mb,
                },
            }

        except Exception as e:
            self.logger.error(f"Operation '{operation_name}' failed: {e}")

            return {
                "success": False,
                "error": str(e),
                "resource_status": resource_status,
                "throttled": throttle_action == "delay",
            }

    def _assess_resource_status(self, metrics: ResourceUsageMetrics) -> str:
        """Assess current resource status."""
        # Check CPU
        if metrics.cpu_percent >= self.thresholds.cpu_emergency:
            return "emergency"
        elif metrics.cpu_percent >= self.thresholds.cpu_critical:
            return "critical"
        elif metrics.cpu_percent >= self.thresholds.cpu_warning:
            return "warning"

        # Check memory
        if metrics.memory_percent >= self.thresholds.memory_emergency:
            return "emergency"
        elif metrics.memory_percent >= self.thresholds.memory_critical:
            return "critical"
        elif metrics.memory_percent >= self.thresholds.memory_warning:
            return "warning"

        # Check process memory
        if metrics.process_memory_mb >= self.thresholds.process_memory_critical_mb:
            return "critical"
        elif metrics.process_memory_mb >= self.thresholds.process_memory_warning_mb:
            return "warning"

        return "normal"

    def _determine_throttle_action(self, resource_status: str) -> str:
        """Determine throttling action based on resource status."""
        if self.throttle_strategy == ThrottleStrategy.NONE:
            return "none"

        elif self.throttle_strategy == ThrottleStrategy.REJECT:
            if resource_status in ["critical", "emergency"]:
                return "reject"
            return "none"

        elif self.throttle_strategy == ThrottleStrategy.DELAY:
            if resource_status in ["warning", "critical", "emergency"]:
                return "delay"
            return "none"

        elif self.throttle_strategy == ThrottleStrategy.ADAPTIVE:
            if resource_status == "emergency":
                return "reject"
            elif resource_status in ["critical", "warning"]:
                return "delay"
            return "none"

        return "none"

    def get_resource_health_report(self) -> Dict[str, Any]:
        """Get comprehensive resource health report."""
        current_metrics = self.resource_monitor.get_current_metrics()
        resource_stats = self.resource_monitor.get_resource_statistics()

        if not current_metrics:
            return {"status": "unknown", "monitoring_active": False}

        resource_status = self._assess_resource_status(current_metrics)

        return {
            "status": resource_status,
            "monitoring_active": True,
            "current_metrics": {
                "cpu_percent": current_metrics.cpu_percent,
                "memory_percent": current_metrics.memory_percent,
                "process_memory_mb": current_metrics.process_memory_mb,
                "timestamp": current_metrics.timestamp.isoformat(),
            },
            "statistics": resource_stats,
            "operations": {
                "processed": self._operations_processed,
                "throttled": self._operations_throttled,
                "rejected": self._operations_rejected,
                "throttle_rate": (
                    (self._operations_throttled / self._operations_processed * 100)
                    if self._operations_processed > 0
                    else 0.0
                ),
                "rejection_rate": (
                    (self._operations_rejected / (self._operations_processed + self._operations_rejected) * 100)
                    if (self._operations_processed + self._operations_rejected) > 0
                    else 0.0
                ),
            },
            "thresholds": {
                "cpu_warning": self.thresholds.cpu_warning,
                "cpu_critical": self.thresholds.cpu_critical,
                "memory_warning": self.thresholds.memory_warning,
                "memory_critical": self.thresholds.memory_critical,
            },
        }

    def get_resource_trend(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """Get resource usage trend over specified duration."""
        metrics_history = self.resource_monitor.get_metrics_history(duration_seconds)

        if not metrics_history:
            return {"available": False}

        # Calculate trends
        cpu_values = [m.cpu_percent for m in metrics_history]
        memory_values = [m.memory_percent for m in metrics_history]

        return {
            "available": True,
            "duration_seconds": duration_seconds,
            "samples": len(metrics_history),
            "cpu": {
                "min": min(cpu_values),
                "max": max(cpu_values),
                "avg": sum(cpu_values) / len(cpu_values),
                "current": cpu_values[-1] if cpu_values else 0,
            },
            "memory": {
                "min": min(memory_values),
                "max": max(memory_values),
                "avg": sum(memory_values) / len(memory_values),
                "current": memory_values[-1] if memory_values else 0,
            },
        }

    def adjust_throttle_strategy(self, new_strategy: ThrottleStrategy):
        """Dynamically adjust throttling strategy."""
        old_strategy = self.throttle_strategy
        self.throttle_strategy = new_strategy

        self.logger.info(f"Throttle strategy changed: {old_strategy.value} -> {new_strategy.value}")

    def shutdown(self):
        """Shutdown resource monitoring."""
        self.resource_monitor.stop_monitoring()
        self.logger.info("Resource-aware processor shutdown")


# Example usage and integration patterns
def example_resource_monitoring_workflow():
    """
    Example workflow demonstrating resource monitoring and throttling.
    """
    # Create resource-aware processor
    processor = ResourceAwareProcessor(throttle_strategy=ThrottleStrategy.ADAPTIVE)

    # Simulate processing operations

    for i in range(10):
        # Simulate an operation
        def mock_operation():
            time.sleep(0.1)  # Simulate work
            return f"result_{i}"

        _result = processor.process_with_resource_awareness(
            operation_func=mock_operation, operation_name=f"operation_{i}"
        )

        logger.info(
            f"Operation {i}: Success={result['success']}, "
            f"Throttled={result.get('throttled', False)}, "
            f"Status={result.get('resource_status', 'unknown')}"
        )

    # Get resource health report
    processor.get_resource_health_report()

    # Get resource trend
    trend = processor.get_resource_trend(duration_seconds=30)
    if trend["available"]:
        logger.info(
            f"CPU: min={trend['cpu']['min']:.1f}%, "
            f"max={trend['cpu']['max']:.1f}%, "
            f"avg={trend['cpu']['avg']:.1f}%"
        )
        logger.info(
            f"Memory: min={trend['memory']['min']:.1f}%, "
            f"max={trend['memory']['max']:.1f}%, "
            f"avg={trend['memory']['avg']:.1f}%"
        )

    # Cleanup
    processor.shutdown()


if __name__ == "__main__":
    # Run example workflow
    example_resource_monitoring_workflow()
