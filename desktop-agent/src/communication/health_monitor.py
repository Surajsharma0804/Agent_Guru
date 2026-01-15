"""
Communication Health Monitoring

Production-grade health monitoring for GURU communication system components.
Monitors message bus performance, channel health, and component communication.

Key Features:
- Real-time communication performance monitoring
- Channel health and security monitoring
- Message delivery tracking and analysis
- Component communication pattern analysis
- Automatic failure detection and alerting
- Comprehensive metrics collection
"""

import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ChannelHealthStatus(Enum):
    """Health status for communication channels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILED = "failed"
    UNKNOWN = "unknown"


class CommunicationMetricType(Enum):
    """Types of communication metrics."""
    MESSAGE_LATENCY = "message_latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    QUEUE_DEPTH = "queue_depth"
    CHANNEL_UTILIZATION = "channel_utilization"
    SECURITY_VIOLATIONS = "security_violations"


@dataclass
class CommunicationMetrics:
    """Communication performance metrics."""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Message metrics
    messages_sent: int = 0
    messages_received: int = 0
    messages_failed: int = 0
    messages_retried: int = 0
    
    # Performance metrics
    average_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    throughput_msgs_per_sec: float = 0.0
    
    # Queue metrics
    queue_depth: int = 0
    max_queue_depth: int = 0
    queue_utilization_percent: float = 0.0
    
    # Error metrics
    error_rate_percent: float = 0.0
    timeout_count: int = 0
    security_violations: int = 0
    
    # Channel metrics
    active_channels: int = 0
    failed_channels: int = 0
    channel_utilization_percent: float = 0.0
    
    def calculate_health_score(self) -> float:
        """Calculate overall health score (0-100)."""
        score = 100.0
        
        # Penalize high error rates
        score -= min(self.error_rate_percent * 2, 50)
        
        # Penalize high latency
        if self.average_latency_ms > 1000:  # > 1 second
            score -= min((self.average_latency_ms - 1000) / 100, 30)
        
        # Penalize security violations
        score -= min(self.security_violations * 10, 40)
        
        # Penalize high queue utilization
        if self.queue_utilization_percent > 80:
            score -= min((self.queue_utilization_percent - 80) / 2, 20)
        
        return max(0.0, score)


@dataclass
class ChannelHealth:
    """Health information for a communication channel."""
    channel_id: str
    status: ChannelHealthStatus = ChannelHealthStatus.UNKNOWN
    health_score: float = 100.0
    last_check: datetime = field(default_factory=datetime.now)
    
    # Performance metrics
    message_count: int = 0
    error_count: int = 0
    average_latency_ms: float = 0.0
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Security metrics
    security_violations: int = 0
    encryption_failures: int = 0
    authentication_failures: int = 0
    
    # Issues and diagnostics
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def is_healthy(self) -> bool:
        """Check if channel is healthy."""
        return self.status in [ChannelHealthStatus.HEALTHY, ChannelHealthStatus.DEGRADED]
    
    def time_since_activity(self) -> timedelta:
        """Get time since last activity."""
        return datetime.now() - self.last_activity
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()


class CommunicationHealthMonitor:
    """
    Production-grade health monitoring for communication system.
    
    Monitors all aspects of the GURU communication system including:
    - Message bus performance and reliability
    - Secure channel health and security
    - Component communication patterns
    - Error rates and failure detection
    - Performance metrics and trends
    - Security violation monitoring
    """
    
    def __init__(self,
                 monitoring_interval_seconds: float = 5.0,
                 metrics_history_size: int = 1000,
                 enable_trend_analysis: bool = True):
        """
        Initialize communication health monitor.
        
        Args:
            monitoring_interval_seconds: Interval between health checks
            metrics_history_size: Number of historical metrics to keep
            enable_trend_analysis: Enable trend analysis and prediction
        """
        self.logger = logging.getLogger(__name__)
        self.monitoring_interval = monitoring_interval_seconds
        self.metrics_history_size = metrics_history_size
        self.enable_trend_analysis = enable_trend_analysis
        
        # Health tracking
        self._channel_health: Dict[str, ChannelHealth] = {}
        self._component_health: Dict[str, Dict[str, Any]] = {}
        self._system_health: CommunicationMetrics = CommunicationMetrics()
        
        # Metrics history
        self._metrics_history: deque = deque(maxlen=metrics_history_size)
        self._latency_samples: deque = deque(maxlen=1000)
        self._throughput_samples: deque = deque(maxlen=100)
        
        # Monitoring state
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._health_lock = threading.RLock()
        
        # Callbacks and alerts
        self._health_callbacks: List[Callable[[str, ChannelHealth], None]] = []
        self._alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._metric_callbacks: List[Callable[[CommunicationMetrics], None]] = []
        
        # Thresholds and limits
        self._health_thresholds = {
            "max_latency_ms": 5000.0,
            "max_error_rate_percent": 5.0,
            "max_queue_utilization_percent": 90.0,
            "max_security_violations": 10,
            "min_throughput_msgs_per_sec": 1.0
        }
        
        # Performance tracking
        self._performance_baselines: Dict[str, float] = {}
        self._anomaly_detection_enabled = True
        
        self.logger.info("CommunicationHealthMonitor initialized")
    
    def start_monitoring(self) -> None:
        """Start health monitoring."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="CommunicationHealthMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        self.logger.info("Communication health monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._monitoring_active = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
        
        self.logger.info("Communication health monitoring stopped")
    
    def register_channel(self, channel_id: str, initial_health: Optional[ChannelHealth] = None) -> None:
        """Register channel for health monitoring."""
        with self._health_lock:
            if channel_id in self._channel_health:
                self.logger.warning(f"Channel '{channel_id}' already registered for monitoring")
                return
            
            health = initial_health or ChannelHealth(
                channel_id=channel_id,
                status=ChannelHealthStatus.HEALTHY
            )
            
            self._channel_health[channel_id] = health
        
        self.logger.info(f"Registered channel '{channel_id}' for health monitoring")
    
    def unregister_channel(self, channel_id: str) -> None:
        """Unregister channel from health monitoring."""
        with self._health_lock:
            self._channel_health.pop(channel_id, None)
        
        self.logger.info(f"Unregistered channel '{channel_id}' from health monitoring")
    
    def record_message_sent(self, channel_id: str, latency_ms: float = 0.0) -> None:
        """Record successful message send."""
        with self._health_lock:
            # Update channel health
            if channel_id in self._channel_health:
                channel_health = self._channel_health[channel_id]
                channel_health.message_count += 1
                channel_health.update_activity()
                
                # Update latency if provided
                if latency_ms > 0:
                    if channel_health.average_latency_ms == 0:
                        channel_health.average_latency_ms = latency_ms
                    else:
                        # Exponential moving average
                        channel_health.average_latency_ms = (
                            0.9 * channel_health.average_latency_ms + 0.1 * latency_ms
                        )
            
            # Update system metrics
            self._system_health.messages_sent += 1
            
            # Record latency sample
            if latency_ms > 0:
                self._latency_samples.append(latency_ms)
    
    def record_message_received(self, channel_id: str) -> None:
        """Record successful message receive."""
        with self._health_lock:
            # Update channel health
            if channel_id in self._channel_health:
                channel_health = self._channel_health[channel_id]
                channel_health.update_activity()
            
            # Update system metrics
            self._system_health.messages_received += 1
    
    def record_message_error(self, channel_id: str, error_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record message error."""
        with self._health_lock:
            # Update channel health
            if channel_id in self._channel_health:
                channel_health = self._channel_health[channel_id]
                channel_health.error_count += 1
                channel_health.update_activity()
                
                # Add error to issues
                error_msg = f"{error_type}: {details.get('reason', 'Unknown') if details else 'Unknown'}"
                if error_msg not in channel_health.issues:
                    channel_health.issues.append(error_msg)
                
                # Limit issues list size
                if len(channel_health.issues) > 10:
                    channel_health.issues = channel_health.issues[-10:]
            
            # Update system metrics
            self._system_health.messages_failed += 1
            
            # Check for security violations
            if error_type in ["authentication_failure", "encryption_failure", "replay_attack"]:
                self.record_security_violation(channel_id, error_type, details)
    
    def record_security_violation(self, channel_id: str, violation_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record security violation."""
        with self._health_lock:
            # Update channel health
            if channel_id in self._channel_health:
                channel_health = self._channel_health[channel_id]
                channel_health.security_violations += 1
                
                if violation_type == "encryption_failure":
                    channel_health.encryption_failures += 1
                elif violation_type == "authentication_failure":
                    channel_health.authentication_failures += 1
                
                # Add security warning
                warning_msg = f"Security violation: {violation_type}"
                if warning_msg not in channel_health.warnings:
                    channel_health.warnings.append(warning_msg)
            
            # Update system metrics
            self._system_health.security_violations += 1
            
            # Trigger security alert
            self._trigger_security_alert(channel_id, violation_type, details or {})
    
    def update_queue_metrics(self, component_name: str, queue_depth: int, max_queue_size: int) -> None:
        """Update queue metrics for a component."""
        with self._health_lock:
            utilization = (queue_depth / max_queue_size * 100) if max_queue_size > 0 else 0
            
            # Update system metrics
            self._system_health.queue_depth = max(self._system_health.queue_depth, queue_depth)
            self._system_health.max_queue_depth = max(self._system_health.max_queue_depth, max_queue_size)
            self._system_health.queue_utilization_percent = max(
                self._system_health.queue_utilization_percent, utilization
            )
            
            # Store component-specific metrics
            if component_name not in self._component_health:
                self._component_health[component_name] = {}
            
            self._component_health[component_name].update({
                "queue_depth": queue_depth,
                "queue_utilization": utilization,
                "last_update": datetime.now()
            })
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                start_time = time.time()
                
                # Update system metrics
                self._update_system_metrics()
                
                # Check channel health
                self._check_channel_health()
                
                # Perform trend analysis
                if self.enable_trend_analysis:
                    self._analyze_trends()
                
                # Trigger callbacks
                self._notify_metric_callbacks()
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, self.monitoring_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in communication health monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
    
    def _update_system_metrics(self) -> None:
        """Update system-wide communication metrics."""
        with self._health_lock:
            current_time = datetime.now()
            
            # Calculate throughput (messages per second)
            if self._metrics_history:
                time_window = 60.0  # 1 minute window
                recent_metrics = [
                    m for m in self._metrics_history
                    if (current_time - m.timestamp).total_seconds() <= time_window
                ]
                
                if recent_metrics:
                    total_messages = sum(m.messages_sent + m.messages_received for m in recent_metrics)
                    self._system_health.throughput_msgs_per_sec = total_messages / time_window
            
            # Calculate latency statistics
            if self._latency_samples:
                latencies = list(self._latency_samples)
                self._system_health.average_latency_ms = statistics.mean(latencies)
                self._system_health.max_latency_ms = max(latencies)
                self._system_health.min_latency_ms = min(latencies)
            
            # Calculate error rate
            total_messages = self._system_health.messages_sent + self._system_health.messages_received
            if total_messages > 0:
                self._system_health.error_rate_percent = (
                    self._system_health.messages_failed / total_messages * 100
                )
            
            # Update channel counts
            self._system_health.active_channels = len([
                ch for ch in self._channel_health.values()
                if ch.status in [ChannelHealthStatus.HEALTHY, ChannelHealthStatus.DEGRADED]
            ])
            self._system_health.failed_channels = len([
                ch for ch in self._channel_health.values()
                if ch.status == ChannelHealthStatus.FAILED
            ])
            
            # Add to metrics history
            self._metrics_history.append(CommunicationMetrics(
                timestamp=current_time,
                messages_sent=self._system_health.messages_sent,
                messages_received=self._system_health.messages_received,
                messages_failed=self._system_health.messages_failed,
                average_latency_ms=self._system_health.average_latency_ms,
                throughput_msgs_per_sec=self._system_health.throughput_msgs_per_sec,
                error_rate_percent=self._system_health.error_rate_percent,
                security_violations=self._system_health.security_violations,
                active_channels=self._system_health.active_channels,
                failed_channels=self._system_health.failed_channels
            ))
    
    def _check_channel_health(self) -> None:
        """Check health of all registered channels."""
        with self._health_lock:
            for channel_id, channel_health in self._channel_health.items():
                old_status = channel_health.status
                
                # Calculate health score
                channel_health.health_score = self._calculate_channel_health_score(channel_health)
                
                # Determine health status
                new_status = self._determine_channel_status(channel_health)
                
                # Update status if changed
                if new_status != old_status:
                    channel_health.status = new_status
                    channel_health.last_check = datetime.now()
                    
                    # Notify callbacks
                    self._notify_health_callbacks(channel_id, channel_health)
                    
                    # Log status change
                    self.logger.info(f"Channel '{channel_id}' health: {old_status.value} -> {new_status.value}")
    
    def _calculate_channel_health_score(self, channel_health: ChannelHealth) -> float:
        """Calculate health score for a channel."""
        score = 100.0
        
        # Penalize errors
        if channel_health.message_count > 0:
            error_rate = channel_health.error_count / channel_health.message_count * 100
            score -= min(error_rate * 2, 50)
        
        # Penalize high latency
        if channel_health.average_latency_ms > 1000:
            score -= min((channel_health.average_latency_ms - 1000) / 100, 30)
        
        # Penalize security violations
        score -= min(channel_health.security_violations * 5, 40)
        
        # Penalize inactivity
        inactivity_minutes = channel_health.time_since_activity().total_seconds() / 60
        if inactivity_minutes > 10:  # 10 minutes
            score -= min(inactivity_minutes - 10, 20)
        
        return max(0.0, score)
    
    def _determine_channel_status(self, channel_health: ChannelHealth) -> ChannelHealthStatus:
        """Determine channel status based on health metrics."""
        score = channel_health.health_score
        
        if score >= 90:
            return ChannelHealthStatus.HEALTHY
        elif score >= 70:
            return ChannelHealthStatus.DEGRADED
        elif score >= 50:
            return ChannelHealthStatus.WARNING
        elif score >= 20:
            return ChannelHealthStatus.CRITICAL
        else:
            return ChannelHealthStatus.FAILED
    
    def _analyze_trends(self) -> None:
        """Analyze communication trends for predictive monitoring."""
        if len(self._metrics_history) < 10:
            return
        
        try:
            # Analyze latency trends
            recent_latencies = [m.average_latency_ms for m in list(self._metrics_history)[-10:]]
            if len(recent_latencies) >= 5:
                trend = self._calculate_trend(recent_latencies)
                if trend > 0.1:  # Increasing latency trend
                    self._trigger_trend_alert("latency_increasing", {
                        "trend": trend,
                        "current_latency": recent_latencies[-1],
                        "average_latency": statistics.mean(recent_latencies)
                    })
            
            # Analyze error rate trends
            recent_error_rates = [m.error_rate_percent for m in list(self._metrics_history)[-10:]]
            if len(recent_error_rates) >= 5:
                trend = self._calculate_trend(recent_error_rates)
                if trend > 0.05:  # Increasing error rate trend
                    self._trigger_trend_alert("error_rate_increasing", {
                        "trend": trend,
                        "current_error_rate": recent_error_rates[-1],
                        "average_error_rate": statistics.mean(recent_error_rates)
                    })
        
        except Exception as e:
            self.logger.error(f"Error in trend analysis: {e}")
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend slope for a series of values."""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x_values = list(range(n))
        
        # Simple linear regression slope
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(values)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        return numerator / denominator if denominator != 0 else 0.0
    
    def _trigger_security_alert(self, channel_id: str, violation_type: str, details: Dict[str, Any]) -> None:
        """Trigger security alert."""
        alert_data = {
            "alert_type": "security_violation",
            "channel_id": channel_id,
            "violation_type": violation_type,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        
        self.logger.warning(f"SECURITY_ALERT: {violation_type} on channel {channel_id}")
        
        for callback in self._alert_callbacks:
            try:
                callback("security_violation", alert_data)
            except Exception as e:
                self.logger.error(f"Error in security alert callback: {e}")
    
    def _trigger_trend_alert(self, trend_type: str, details: Dict[str, Any]) -> None:
        """Trigger trend-based alert."""
        alert_data = {
            "alert_type": "trend_alert",
            "trend_type": trend_type,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        
        self.logger.warning(f"TREND_ALERT: {trend_type}")
        
        for callback in self._alert_callbacks:
            try:
                callback("trend_alert", alert_data)
            except Exception as e:
                self.logger.error(f"Error in trend alert callback: {e}")
    
    def _notify_health_callbacks(self, channel_id: str, channel_health: ChannelHealth) -> None:
        """Notify health change callbacks."""
        for callback in self._health_callbacks:
            try:
                callback(channel_id, channel_health)
            except Exception as e:
                self.logger.error(f"Error in health callback: {e}")
    
    def _notify_metric_callbacks(self) -> None:
        """Notify metric callbacks."""
        for callback in self._metric_callbacks:
            try:
                callback(self._system_health)
            except Exception as e:
                self.logger.error(f"Error in metric callback: {e}")
    
    # Public API methods
    
    def get_channel_health(self, channel_id: str) -> Optional[ChannelHealth]:
        """Get health information for a channel."""
        with self._health_lock:
            return self._channel_health.get(channel_id)
    
    def get_all_channel_health(self) -> Dict[str, ChannelHealth]:
        """Get health information for all channels."""
        with self._health_lock:
            return self._channel_health.copy()
    
    def get_system_metrics(self) -> CommunicationMetrics:
        """Get current system-wide metrics."""
        with self._health_lock:
            return self._system_health
    
    def get_metrics_history(self, limit: int = 100) -> List[CommunicationMetrics]:
        """Get historical metrics."""
        with self._health_lock:
            return list(self._metrics_history)[-limit:]
    
    def get_unhealthy_channels(self) -> List[str]:
        """Get list of unhealthy channels."""
        with self._health_lock:
            return [
                channel_id for channel_id, health in self._channel_health.items()
                if health.status in [ChannelHealthStatus.CRITICAL, ChannelHealthStatus.FAILED]
            ]
    
    def add_health_callback(self, callback: Callable[[str, ChannelHealth], None]) -> None:
        """Add channel health change callback."""
        self._health_callbacks.append(callback)
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add alert callback."""
        self._alert_callbacks.append(callback)
    
    def add_metric_callback(self, callback: Callable[[CommunicationMetrics], None]) -> None:
        """Add metric update callback."""
        self._metric_callbacks.append(callback)
    
    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """Get monitoring system statistics."""
        with self._health_lock:
            return {
                "monitoring_active": self._monitoring_active,
                "monitored_channels": len(self._channel_health),
                "monitored_components": len(self._component_health),
                "metrics_history_size": len(self._metrics_history),
                "latency_samples": len(self._latency_samples),
                "health_callbacks": len(self._health_callbacks),
                "alert_callbacks": len(self._alert_callbacks),
                "metric_callbacks": len(self._metric_callbacks),
                "system_health_score": self._system_health.calculate_health_score()
            }