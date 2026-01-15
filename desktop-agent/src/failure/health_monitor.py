"""
Component Health Monitoring System

Implements comprehensive health monitoring for all GURU core components with:
- Real-time health status tracking
- Performance metrics collection
- Failure prediction and early warning
- Component lifecycle management
- Thread-safe monitoring operations
"""

import logging
import queue
import threading
import time
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from .exceptions import ComponentFailureError, HealthCheckTimeoutError


class HealthStatus(Enum):
    """Component health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class HealthMetrics:
    """Health metrics for a component."""

    timestamp: datetime
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    response_time_ms: float = 0.0
    error_rate_percent: float = 0.0
    throughput_ops_per_sec: float = 0.0
    active_connections: int = 0
    queue_depth: int = 0
    custom_metrics: Dict[str, float] = field(default_factory=dict)

    def is_within_limits(self, limits: "HealthLimits") -> bool:
        """Check if metrics are within acceptable limits."""
        return (
            self.cpu_usage_percent <= limits.max_cpu_percent
            and self.memory_usage_mb <= limits.max_memory_mb
            and self.response_time_ms <= limits.max_response_time_ms
            and self.error_rate_percent <= limits.max_error_rate_percent
        )


@dataclass
class HealthLimits:
    """Health limits for component monitoring."""

    max_cpu_percent: float = 80.0
    max_memory_mb: float = 512.0
    max_response_time_ms: float = 1000.0
    max_error_rate_percent: float = 5.0
    max_queue_depth: int = 100
    max_silence_seconds: float = 30.0


@dataclass
class ComponentHealth:
    """Complete health information for a component."""

    component_name: str
    status: HealthStatus
    last_check_time: datetime
    last_response_time: datetime
    metrics: HealthMetrics
    error_count: int = 0
    warning_count: int = 0
    consecutive_failures: int = 0
    uptime_seconds: float = 0.0
    health_score: float = 100.0  # 0-100 scale
    issues: List[str] = field(default_factory=list)
    recovery_attempts: int = 0


class HealthCheckable(Protocol):
    """Protocol for components that can be health checked."""

    def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status information."""
        ...

    def get_metrics(self) -> Dict[str, float]:
        """Get current performance metrics."""
        ...


class ComponentHealthMonitor:
    """
    Comprehensive health monitoring system for GURU components.

    Monitors all core components with configurable health checks,
    performance metrics collection, and failure detection.
    """

    def __init__(self, check_interval_seconds: float = 5.0):
        self.check_interval_seconds = check_interval_seconds
        self.logger = logging.getLogger(__name__)

        # Component registry
        self._components: Dict[str, weakref.ReferenceType] = {}
        self._health_status: Dict[str, ComponentHealth] = {}
        self._health_limits: Dict[str, HealthLimits] = {}
        self._health_callbacks: Dict[str, List[Callable[[ComponentHealth], None]]] = {}

        # Monitoring control
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._health_lock = threading.RLock()

        # Health history for trend analysis
        self._health_history: Dict[str, List[ComponentHealth]] = {}
        self._max_history_size = 100

        # System-wide health tracking
        self._system_start_time = datetime.now()
        self._global_health_callbacks: List[Callable[[Dict[str, ComponentHealth]], None]] = []

        # Performance tracking
        self._check_performance: Dict[str, List[float]] = {}

    def register_component(self, name: str, component: HealthCheckable, limits: Optional[HealthLimits] = None) -> None:
        """Register a component for health monitoring."""
        with self._health_lock:
            self._components[name] = weakref.ref(component)
            self._health_limits[name] = limits or HealthLimits()
            self._health_callbacks[name] = []
            self._health_history[name] = []
            self._check_performance[name] = []

            # Initialize health status
            self._health_status[name] = ComponentHealth(
                component_name=name,
                status=HealthStatus.UNKNOWN,
                last_check_time=datetime.now(),
                last_response_time=datetime.now(),
                metrics=HealthMetrics(timestamp=datetime.now()),
            )

        self.logger.info(f"Registered component '{name}' for health monitoring")

    def unregister_component(self, name: str) -> None:
        """Unregister a component from health monitoring."""
        with self._health_lock:
            self._components.pop(name, None)
            self._health_status.pop(name, None)
            self._health_limits.pop(name, None)
            self._health_callbacks.pop(name, None)
            self._health_history.pop(name, None)
            self._check_performance.pop(name, None)

        self.logger.info(f"Unregistered component '{name}' from health monitoring")

    def add_health_callback(self, component_name: str, callback: Callable[[ComponentHealth], None]) -> None:
        """Add callback for component health changes."""
        with self._health_lock:
            if component_name in self._health_callbacks:
                self._health_callbacks[component_name].append(callback)

    def add_global_health_callback(self, callback: Callable[[Dict[str, ComponentHealth]], None]) -> None:
        """Add callback for system-wide health changes."""
        self._global_health_callbacks.append(callback)

    def start_monitoring(self) -> None:
        """Start health monitoring for all registered components."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True, name="HealthMonitor")
        self._monitor_thread.start()

        self.logger.info("Started component health monitoring")

    def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)

        self.logger.info("Stopped component health monitoring")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                start_time = time.time()

                # Check health of all registered components
                self._perform_health_checks()

                # Analyze trends and predict issues
                self._analyze_health_trends()

                # Notify global health callbacks
                self._notify_global_callbacks()

                # Calculate sleep time to maintain interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.check_interval_seconds - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(self.check_interval_seconds)

    def _perform_health_checks(self) -> None:
        """Perform health checks on all registered components."""
        with self._health_lock:
            components_to_check = list(self._components.items())

        for name, component_ref in components_to_check:
            try:
                component = component_ref()
                if component is None:
                    # Component has been garbage collected
                    self.unregister_component(name)
                    continue

                self._check_component_health(name, component)

            except Exception as e:
                self.logger.error(f"Error checking health of component '{name}': {e}")
                self._record_health_check_failure(name, str(e))

    def _check_component_health(self, name: str, component: HealthCheckable) -> None:
        """Check health of a specific component."""
        check_start = time.time()

        try:
            # Get health check timeout
            limits = self._health_limits[name]
            timeout_seconds = min(limits.max_response_time_ms / 1000.0, 5.0)

            # Perform health check with timeout
            health_data = self._perform_timed_health_check(component, timeout_seconds)
            metrics_data = self._get_component_metrics(component)

            # Calculate response time
            response_time_ms = (time.time() - check_start) * 1000

            # Ensure response_time_ms is not duplicated
            if "response_time_ms" in metrics_data:
                metrics_data.pop("response_time_ms")

            # Create health metrics
            metrics = HealthMetrics(timestamp=datetime.now(), response_time_ms=response_time_ms, **metrics_data)

            # Determine health status
            status = self._determine_health_status(name, health_data, metrics)

            # Update component health
            self._update_component_health(name, status, metrics, health_data)

            # Record performance
            self._record_check_performance(name, response_time_ms)

        except HealthCheckTimeoutError:
            self._record_health_check_failure(name, f"Health check timeout: {e}")
        except Exception as e:
            self._record_health_check_failure(name, f"Health check error: {e}")

    def _perform_timed_health_check(self, component: HealthCheckable, timeout_seconds: float) -> Dict[str, Any]:
        """Perform health check with timeout."""
        result_queue = queue.Queue()

        def health_check_worker():
            try:
                _result = component.health_check()
                result_queue.put(("success", result))
            except Exception as e:
                result_queue.put(("error", str(e)))

        # Start health check in separate thread
        check_thread = threading.Thread(target=health_check_worker, daemon=True)
        check_thread.start()

        try:
            status, _result = result_queue.get(timeout=timeout_seconds)
            if status == "error":
                raise ComponentFailureError("health_check", result)
            return result
        except queue.Empty:
            raise HealthCheckTimeoutError("health_check", timeout_seconds)

    def _get_component_metrics(self, component: HealthCheckable) -> Dict[str, float]:
        """Get performance metrics from component."""
        try:
            return component.get_metrics()
        except Exception as e:
            self.logger.warning(f"Failed to get metrics from component: {e}")
            return {}

    def _determine_health_status(self, name: str, health_data: Dict[str, Any], metrics: HealthMetrics) -> HealthStatus:
        """Determine component health status based on data and metrics."""
        limits = self._health_limits[name]

        # Check explicit health status from component
        if "status" in health_data:
            explicit_status = health_data["status"].lower()
            if explicit_status in ["failed", "critical", "error"]:
                return HealthStatus.FAILED
            elif explicit_status in ["warning", "degraded"]:
                return HealthStatus.WARNING
            elif explicit_status == "healthy":
                # Continue with metrics-based assessment
                pass

        # Check metrics against limits
        if not metrics.is_within_limits(limits):
            if (
                metrics.cpu_usage_percent > limits.max_cpu_percent * 1.5
                or metrics.memory_usage_mb > limits.max_memory_mb * 1.5
                or metrics.response_time_ms > limits.max_response_time_ms * 2
            ):
                return HealthStatus.CRITICAL
            else:
                return HealthStatus.WARNING

        # Check error rates
        if metrics.error_rate_percent > limits.max_error_rate_percent:
            if metrics.error_rate_percent > limits.max_error_rate_percent * 2:
                return HealthStatus.CRITICAL
            else:
                return HealthStatus.WARNING

        # Check for degraded performance
        current_health = self._health_status.get(name)
        if current_health:
            # Compare with recent performance
            if (
                metrics.response_time_ms > current_health.metrics.response_time_ms * 2
                or metrics.cpu_usage_percent > current_health.metrics.cpu_usage_percent * 1.5
            ):
                return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _update_component_health(
        self, name: str, status: HealthStatus, metrics: HealthMetrics, health_data: Dict[str, Any]
    ) -> None:
        """Update component health status."""
        with self._health_lock:
            current_health = self._health_status.get(name)
            if not current_health:
                return

            # Calculate uptime
            uptime_seconds = (datetime.now() - self._system_start_time).total_seconds()

            # Update consecutive failure count
            consecutive_failures = 0
            if status in [HealthStatus.FAILED, HealthStatus.CRITICAL]:
                consecutive_failures = current_health.consecutive_failures + 1

            # Calculate health score (0-100)
            health_score = self._calculate_health_score(status, metrics, consecutive_failures)

            # Extract issues from health data
            issues = health_data.get("issues", [])
            if status != HealthStatus.HEALTHY:
                issues.append(f"Status: {status.value}")

            # Create updated health status
            updated_health = ComponentHealth(
                component_name=name,
                status=status,
                last_check_time=datetime.now(),
                last_response_time=datetime.now(),
                metrics=metrics,
                error_count=current_health.error_count + (1 if status == HealthStatus.FAILED else 0),
                warning_count=current_health.warning_count + (1 if status == HealthStatus.WARNING else 0),
                consecutive_failures=consecutive_failures,
                uptime_seconds=uptime_seconds,
                health_score=health_score,
                issues=issues,
                recovery_attempts=current_health.recovery_attempts,
            )

            # Update status
            self._health_status[name] = updated_health

            # Add to history
            self._add_to_health_history(name, updated_health)

            # Notify callbacks if status changed
            if current_health.status != status:
                self._notify_health_callbacks(name, updated_health)

    def _calculate_health_score(self, status: HealthStatus, metrics: HealthMetrics, consecutive_failures: int) -> float:
        """Calculate health score (0-100) based on status and metrics."""
        base_score = {
            HealthStatus.HEALTHY: 100.0,
            HealthStatus.DEGRADED: 80.0,
            HealthStatus.WARNING: 60.0,
            HealthStatus.CRITICAL: 30.0,
            HealthStatus.FAILED: 0.0,
            HealthStatus.UNKNOWN: 50.0,
        }.get(status, 50.0)

        # Adjust for consecutive failures
        failure_penalty = min(consecutive_failures * 10, 50)

        # Adjust for response time
        response_penalty = min(metrics.response_time_ms / 100, 20)

        # Adjust for error rate
        error_penalty = min(metrics.error_rate_percent * 2, 30)

        final_score = max(0, base_score - failure_penalty - response_penalty - error_penalty)
        return final_score

    def _record_health_check_failure(self, name: str, error_message: str) -> None:
        """Record a health check failure."""
        with self._health_lock:
            current_health = self._health_status.get(name)
            if not current_health:
                return

            # Create failure health status
            failed_health = ComponentHealth(
                component_name=name,
                status=HealthStatus.FAILED,
                last_check_time=datetime.now(),
                last_response_time=current_health.last_response_time,
                metrics=HealthMetrics(timestamp=datetime.now()),
                error_count=current_health.error_count + 1,
                warning_count=current_health.warning_count,
                consecutive_failures=current_health.consecutive_failures + 1,
                uptime_seconds=current_health.uptime_seconds,
                health_score=0.0,
                issues=[error_message],
                recovery_attempts=current_health.recovery_attempts,
            )

            self._health_status[name] = failed_health
            self._add_to_health_history(name, failed_health)
            self._notify_health_callbacks(name, failed_health)

    def _record_check_performance(self, name: str, response_time_ms: float) -> None:
        """Record health check performance."""
        with self._health_lock:
            if name in self._check_performance:
                self._check_performance[name].append(response_time_ms)
                # Keep only recent performance data
                if len(self._check_performance[name]) > 50:
                    self._check_performance[name] = self._check_performance[name][-50:]

    def _add_to_health_history(self, name: str, health: ComponentHealth) -> None:
        """Add health status to history."""
        if name in self._health_history:
            self._health_history[name].append(health)
            # Keep history manageable
            if len(self._health_history[name]) > self._max_history_size:
                self._health_history[name] = self._health_history[name][-self._max_history_size :]

    def _analyze_health_trends(self) -> None:
        """Analyze health trends for predictive monitoring."""
        # This is a simplified trend analysis - in production, you might use
        # more sophisticated algorithms for trend detection and prediction
        with self._health_lock:
            for name, history in self._health_history.items():
                if len(history) < 5:
                    continue

                # Check for degrading trends
                recent_scores = [h.health_score for h in history[-5:]]
                if self._is_degrading_trend(recent_scores):
                    current_health = self._health_status.get(name)
                    if current_health and current_health.status == HealthStatus.HEALTHY:
                        # Preemptively mark as degraded
                        current_health.status = HealthStatus.DEGRADED
                        current_health.issues.append("Degrading performance trend detected")
                        self._notify_health_callbacks(name, current_health)

    def _is_degrading_trend(self, scores: List[float]) -> bool:
        """Check if health scores show a degrading trend."""
        if len(scores) < 3:
            return False

        # Simple trend detection: check if scores are consistently decreasing
        decreasing_count = 0
        for i in range(1, len(scores)):
            if scores[i] < scores[i - 1]:
                decreasing_count += 1

        return decreasing_count >= len(scores) - 1

    def _notify_health_callbacks(self, name: str, health: ComponentHealth) -> None:
        """Notify health change callbacks."""
        callbacks = self._health_callbacks.get(name, [])
        for callback in callbacks:
            try:
                callback(health)
            except Exception as e:
                self.logger.error(f"Error in health callback for '{name}': {e}")

    def _notify_global_callbacks(self) -> None:
        """Notify global health callbacks."""
        if not self._global_health_callbacks:
            return

        with self._health_lock:
            health_snapshot = self._health_status.copy()

        for callback in self._global_health_callbacks:
            try:
                callback(health_snapshot)
            except Exception as e:
                self.logger.error(f"Error in global health callback: {e}")

    # Public API methods

    def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        """Get current health status of a component."""
        with self._health_lock:
            return self._health_status.get(name)

    def get_all_health_status(self) -> Dict[str, ComponentHealth]:
        """Get health status of all components."""
        with self._health_lock:
            return self._health_status.copy()

    def get_failed_components(self) -> List[str]:
        """Get list of failed components."""
        with self._health_lock:
            return [name for name, health in self._health_status.items() if health.status == HealthStatus.FAILED]

    def get_critical_components(self) -> List[str]:
        """Get list of components in critical state."""
        with self._health_lock:
            return [name for name, health in self._health_status.items() if health.status == HealthStatus.CRITICAL]

    def get_system_health_score(self) -> float:
        """Get overall system health score (0-100)."""
        with self._health_lock:
            if not self._health_status:
                return 0.0

            total_score = sum(health.health_score for health in self._health_status.values())
            return total_score / len(self._health_status)

    def get_component_history(self, name: str, limit: Optional[int] = None) -> List[ComponentHealth]:
        """Get health history for a component."""
        with self._health_lock:
            history = self._health_history.get(name, [])
            if limit:
                return history[-limit:]
            return history.copy()

    def force_health_check(self, name: str) -> Optional[ComponentHealth]:
        """Force immediate health check of a component."""
        component_ref = self._components.get(name)
        if not component_ref:
            return None

        component = component_ref()
        if component is None:
            self.unregister_component(name)
            return None

        self._check_component_health(name, component)
        return self.get_component_health(name)

    def is_system_healthy(self) -> bool:
        """Check if the overall system is healthy."""
        with self._health_lock:
            return all(
                health.status not in [HealthStatus.FAILED, HealthStatus.CRITICAL]
                for health in self._health_status.values()
            )

    def get_unhealthy_components(self) -> Dict[str, ComponentHealth]:
        """Get all components that are not healthy."""
        with self._health_lock:
            return {
                name: health for name, health in self._health_status.items() if health.status != HealthStatus.HEALTHY
            }
