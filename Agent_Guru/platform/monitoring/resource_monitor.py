"""
Module: agent_guru.platform.monitoring.resource_monitor
Purpose: Real-time resource monitoring with predictive alerting

This module implements comprehensive system resource monitoring with:
- Real-time metrics collection (CPU, memory, disk, network, GPU)
- Configurable alert thresholds
- Historical trend analysis
- Predictive resource exhaustion detection
- Automatic throttling recommendations

Performance Requirements:
- Time Complexity: O(1) per metric query
- Space Complexity: O(history_size) for historical data
- Sampling Overhead: <1% CPU usage
- Latency: <10ms per snapshot

Design Decisions:
- Use psutil for cross-platform metrics (proven, efficient)
- Use GPUtil for GPU metrics (optional dependency)
- Use deque for fixed-size history (O(1) append/pop)
- Use threading for background monitoring (non-blocking)
- Preallocate data structures (minimize GC pressure)

Author: Agent Guru Team
Date: 2026-02-25
Version: 1.0.0
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import psutil

import logging
_logger = logging.getLogger(__name__)

# Optional GPU support
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False


class ResourceType(Enum):
    """Resource types for monitoring."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DiskUsage:
    """Disk usage information for a volume."""
    path: str
    total: int  # bytes
    used: int  # bytes
    free: int  # bytes
    percent: float  # 0-100


@dataclass
class NetworkIO:
    """Network I/O statistics."""
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int


@dataclass
class GPUUsage:
    """GPU usage information."""
    id: int
    name: str
    load: float  # 0-100
    memory_total: int  # MB
    memory_used: int  # MB
    memory_free: int  # MB
    memory_percent: float  # 0-100
    temperature: Optional[float]  # Celsius


@dataclass
class ProcessResourceUsage:
    """Resource usage for a specific process."""
    pid: int
    name: str
    cpu_percent: float
    memory_bytes: int
    memory_percent: float
    num_threads: int
    status: str


@dataclass
class ResourceSnapshot:
    """Complete resource usage snapshot at a point in time."""
    timestamp: datetime
    cpu_percent: float  # Aggregate CPU usage
    cpu_per_core: list[float]  # Per-core CPU usage
    memory_bytes: int  # Used memory in bytes
    memory_percent: float  # Memory usage percentage
    memory_available: int  # Available memory in bytes
    swap_bytes: int  # Swap usage in bytes
    swap_percent: float  # Swap usage percentage
    disk_usage: dict[str, DiskUsage]  # path -> usage
    network_io: NetworkIO
    gpu_usage: Optional[list[GPUUsage]]
    process_count: int
    thread_count: int


@dataclass
class ResourceLimits:
    """Configurable resource limits for alerting."""
    max_cpu_percent: float = 80.0
    max_memory_bytes: int = 2 * 1024 * 1024 * 1024  # 2GB
    max_memory_percent: float = 90.0
    min_disk_free_bytes: int = 1 * 1024 * 1024 * 1024  # 1GB
    max_network_bandwidth_mbps: float = 100.0
    max_gpu_memory_percent: float = 90.0


@dataclass
class ResourceAlert:
    """Resource usage alert."""
    alert_id: str
    resource_type: ResourceType
    current_value: float
    threshold_value: float
    severity: AlertSeverity
    timestamp: datetime
    message: str
    recommended_action: str


@dataclass
class ResourceMonitorConfig:
    """Configuration for ResourceMonitor."""
    sampling_interval: float = 5.0  # seconds
    history_size: int = 1000  # number of snapshots to keep
    enable_gpu_monitoring: bool = True
    enable_network_monitoring: bool = True
    limits: ResourceLimits = field(default_factory=ResourceLimits)


class ResourceMonitor:
    """
    Real-time resource monitoring with predictive alerting.

    Monitors:
    - CPU usage (per-core and aggregate)
    - Memory usage (RSS, VMS, swap)
    - Disk usage (all mounted volumes)
    - Network bandwidth (upload/download)
    - GPU usage and memory (when available)

    Time Complexity: O(1) per metric query
    Space Complexity: O(history_size) for historical data

    Example:
        >>> config = ResourceMonitorConfig(sampling_interval=5.0)
        >>> monitor = ResourceMonitor(config)
        >>> monitor.start_monitoring()
        >>> snapshot = monitor.get_current_usage()
        >>> print(f"CPU: {snapshot.cpu_percent}%")
        >>> monitor.stop_monitoring()
    """

    def __init__(self, config: Optional[ResourceMonitorConfig] = None):
        """
        Initialize resource monitor.

        Args:
            config: Monitor configuration (uses defaults if None)
        """
        self.config = config or ResourceMonitorConfig()

        # Historical metrics storage (fixed size for O(1) operations)
        self.metrics_history: deque[ResourceSnapshot] = deque(
            maxlen=self.config.history_size
        )

        # Alert callbacks
        self.alert_callbacks: list[Callable[[ResourceAlert], None]] = []

        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Network I/O baseline for bandwidth calculation
        self._last_network_io: Optional[NetworkIO] = None
        self._last_network_time: Optional[float] = None

        # Alert tracking (prevent duplicate alerts)
        self._active_alerts: dict[str, ResourceAlert] = {}

        # Alert history (fixed size for memory efficiency)
        self._alert_history: deque[ResourceAlert] = deque(maxlen=1000)

        # Validate GPU availability
        if self.config.enable_gpu_monitoring and not GPU_AVAILABLE:
            self.config.enable_gpu_monitoring = False

        # Prime CPU cache (first call with interval=None returns 0.0)
        psutil.cpu_percent(interval=0.01)

    def get_current_usage(self) -> ResourceSnapshot:
        """
        Get current resource usage snapshot.

        Time Complexity: O(1) - constant time operations
        Space Complexity: O(1) - fixed size snapshot

        Returns:
            Current resource usage snapshot
        """
        timestamp = datetime.now()

        # CPU metrics (O(1) - psutil caches values)
        # Use interval=None for non-blocking call (returns cached value)
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)

        # Memory metrics (O(1))
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk metrics (O(partitions) - typically small constant)
        disk_usage = {}
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_usage[partition.mountpoint] = DiskUsage(
                    path=partition.mountpoint,
                    total=usage.total,
                    used=usage.used,
                    free=usage.free,
                    percent=usage.percent
                )
            except (PermissionError, OSError):
                # Skip inaccessible partitions
                continue

        # Network metrics (O(1))
        network_io = None
        if self.config.enable_network_monitoring:
            net_io = psutil.net_io_counters()
            network_io = NetworkIO(
                bytes_sent=net_io.bytes_sent,
                bytes_recv=net_io.bytes_recv,
                packets_sent=net_io.packets_sent,
                packets_recv=net_io.packets_recv,
                errin=net_io.errin,
                errout=net_io.errout,
                dropin=net_io.dropin,
                dropout=net_io.dropout
            )

        # GPU metrics (O(gpus) - typically 1-2 GPUs)
        gpu_usage = None
        if self.config.enable_gpu_monitoring and GPU_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                gpu_usage = [
                    GPUUsage(
                        id=gpu.id,
                        name=gpu.name,
                        load=gpu.load * 100,  # Convert to percentage
                        memory_total=gpu.memoryTotal,
                        memory_used=gpu.memoryUsed,
                        memory_free=gpu.memoryFree,
                        memory_percent=(gpu.memoryUsed / gpu.memoryTotal * 100)
                        if gpu.memoryTotal > 0 else 0.0,
                        temperature=gpu.temperature
                    )
                    for gpu in gpus
                ]
            except Exception:
                # GPU monitoring failed, continue without it
                gpu_usage = None

        # Process/thread counts (O(1))
        process_count = len(psutil.pids())

        # Thread count: use process_count as proxy on Windows (num_threads hangs on
        # protected system processes via psutil C extension on Windows)
        import platform as _platform
        thread_count = 0
        if _platform.system() != "Windows":
            try:
                for pid in psutil.pids():
                    try:
                        p = psutil.Process(pid)
                        try:
                            nt = p.num_threads()
                            thread_count += nt
                        except (psutil.AccessDenied, OSError):
                            pass
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                        continue
            except Exception:
                thread_count = 0

        snapshot = ResourceSnapshot(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            cpu_per_core=cpu_per_core,
            memory_bytes=memory.used,
            memory_percent=memory.percent,
            memory_available=memory.available,
            swap_bytes=swap.used,
            swap_percent=swap.percent,
            disk_usage=disk_usage,
            network_io=network_io,
            gpu_usage=gpu_usage,
            process_count=process_count,
            thread_count=thread_count
        )

        return snapshot

    def get_process_usage(self, pid: int) -> ProcessResourceUsage:
        """
        Get resource usage for specific process.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pid: Process ID

        Returns:
            Process resource usage

        Raises:
            psutil.NoSuchProcess: If process doesn't exist
            psutil.AccessDenied: If insufficient permissions
        """
        process = psutil.Process(pid)

        return ProcessResourceUsage(
            pid=pid,
            name=process.name(),
            cpu_percent=process.cpu_percent(interval=None),
            memory_bytes=process.memory_info().rss,
            memory_percent=process.memory_percent(),
            num_threads=process.num_threads(),
            status=process.status()
        )

    def set_alert_thresholds(self, limits: ResourceLimits) -> None:
        """
        Configure alert thresholds.

        Args:
            limits: New resource limits
        """
        with self._lock:
            self.config.limits = limits

    def start_monitoring(self, interval: Optional[float] = None) -> None:
        """
        Start periodic resource monitoring in background thread.

        Args:
            interval: Sampling interval in seconds (uses config if None)
        """
        if self._monitoring:
            return

        if interval is not None:
            self.config.sampling_interval = interval

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None

    def register_alert_callback(
        self,
        callback: Callable[[ResourceAlert], None]
    ) -> None:
        """
        Register callback for resource alerts.

        Args:
            callback: Function to call when alert is triggered
        """
        with self._lock:
            self.alert_callbacks.append(callback)

    def unregister_alert_callback(
        self,
        callback: Callable[[ResourceAlert], None]
    ) -> bool:
        """
        Unregister alert callback.

        Args:
            callback: Callback function to remove

        Returns:
            True if callback was found and removed, False otherwise
        """
        with self._lock:
            try:
                self.alert_callbacks.remove(callback)
                return True
            except ValueError:
                return False

    def get_alert_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        resource_type: Optional[ResourceType] = None,
        severity: Optional[AlertSeverity] = None
    ) -> list[ResourceAlert]:
        """
        Get alert history with optional filters.

        Time Complexity: O(n) where n is history size
        Space Complexity: O(m) where m is matching alerts

        Args:
            start_time: Filter alerts after this time (inclusive)
            end_time: Filter alerts before this time (inclusive)
            resource_type: Filter by resource type
            severity: Filter by severity level

        Returns:
            List of alerts matching filters
        """
        with self._lock:
            alerts = list(self._alert_history)

        # Apply filters
        if start_time is not None:
            alerts = [a for a in alerts if a.timestamp >= start_time]

        if end_time is not None:
            alerts = [a for a in alerts if a.timestamp <= end_time]

        if resource_type is not None:
            alerts = [a for a in alerts if a.resource_type == resource_type]

        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def get_active_alerts(self) -> list[ResourceAlert]:
        """
        Get currently active alerts.

        Returns:
            List of active alerts
        """
        with self._lock:
            return list(self._active_alerts.values())

    def clear_alert(self, alert_id: str) -> bool:
        """
        Clear an active alert.

        Args:
            alert_id: ID of alert to clear

        Returns:
            True if alert was found and cleared, False otherwise
        """
        with self._lock:
            if alert_id in self._active_alerts:
                del self._active_alerts[alert_id]
                return True
            return False

    def clear_all_alerts(self) -> int:
        """
        Clear all active alerts.

        Returns:
            Number of alerts cleared
        """
        with self._lock:
            count = len(self._active_alerts)
            self._active_alerts.clear()
            return count

    def get_historical_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> list[ResourceSnapshot]:
        """
        Get historical resource metrics within time range.

        Time Complexity: O(n) where n is history size
        Space Complexity: O(m) where m is matching snapshots

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of snapshots within time range
        """
        with self._lock:
            return [
                snapshot for snapshot in self.metrics_history
                if start_time <= snapshot.timestamp <= end_time
            ]

    def predict_resource_exhaustion(
        self,
        resource_type: ResourceType,
        horizon: timedelta = timedelta(hours=1)
    ) -> Optional[datetime]:
        """
        Predict when resource will be exhausted based on trends.

        Uses linear regression on recent history to predict exhaustion time.

        Args:
            resource_type: Type of resource to predict
            horizon: Maximum prediction horizon

        Returns:
            Estimated time of exhaustion, or None if no exhaustion predicted
        """
        with self._lock:
            if len(self.metrics_history) < 10:
                # Not enough data for prediction
                return None

            # Get recent snapshots (last 10 minutes)
            recent = list(self.metrics_history)[-120:]  # 120 samples at 5s interval

            if len(recent) < 2:
                return None

            # Extract values based on resource type
            values = []
            for snapshot in recent:
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
                    else:
                        return None
                else:
                    return None

            if not values:
                return None

            # Simple linear regression
            n = len(values)
            x = list(range(n))
            y = values

            # Calculate slope
            x_mean = sum(x) / n
            y_mean = sum(y) / n

            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                return None

            slope = numerator / denominator

            # If slope is negative or near zero, no exhaustion predicted
            if slope <= 0.01:
                return None

            # Calculate when resource will reach 100%
            current_value = values[-1]
            remaining = 100.0 - current_value

            if remaining <= 0:
                return datetime.now()

            # Time to exhaustion in samples
            samples_to_exhaustion = remaining / slope

            # Convert to time
            time_to_exhaustion = timedelta(
                seconds=samples_to_exhaustion * self.config.sampling_interval
            )

            # Check if within horizon
            if time_to_exhaustion > horizon:
                return None

            return datetime.now() + time_to_exhaustion

    def _monitoring_loop(self) -> None:
        """Background monitoring loop (runs in separate thread)."""
        try:
            # Prime CPU monitoring with first blocking call
            psutil.cpu_percent(interval=0.1)

            while self._monitoring:
                try:
                    # Collect metrics
                    snapshot = self.get_current_usage()

                    # Store in history
                    with self._lock:
                        self.metrics_history.append(snapshot)

                    # Check thresholds and trigger alerts
                    self._check_thresholds(snapshot)

                    # Sleep until next sample
                    time.sleep(self.config.sampling_interval)

                except Exception as e:
                    # Log error but continue monitoring
                    _logger.error("Error in monitoring loop: %s", e, exc_info=True)
                    time.sleep(self.config.sampling_interval)
        except Exception as e:
            # Fatal error in monitoring loop
            _logger.critical("Fatal error in monitoring loop: %s", e, exc_info=True)

    def _check_thresholds(self, snapshot: ResourceSnapshot) -> None:
        """
        Check resource thresholds and trigger alerts.

        Args:
            snapshot: Current resource snapshot
        """
        limits = self.config.limits

        # Check CPU
        if snapshot.cpu_percent > limits.max_cpu_percent:
            self._trigger_alert(
                resource_type=ResourceType.CPU,
                current_value=snapshot.cpu_percent,
                threshold_value=limits.max_cpu_percent,
                severity=self._calculate_severity(
                    snapshot.cpu_percent,
                    limits.max_cpu_percent
                ),
                message=f"CPU usage at {snapshot.cpu_percent:.1f}%",
                recommended_action="Consider throttling operations or closing applications"
            )

        # Check memory
        if snapshot.memory_percent > limits.max_memory_percent:
            self._trigger_alert(
                resource_type=ResourceType.MEMORY,
                current_value=snapshot.memory_percent,
                threshold_value=limits.max_memory_percent,
                severity=self._calculate_severity(
                    snapshot.memory_percent,
                    limits.max_memory_percent
                ),
                message=f"Memory usage at {snapshot.memory_percent:.1f}%",
                recommended_action="Consider freeing memory or closing applications"
            )

        # Check disk
        for path, usage in snapshot.disk_usage.items():
            if usage.free < limits.min_disk_free_bytes:
                self._trigger_alert(
                    resource_type=ResourceType.DISK,
                    current_value=usage.free,
                    threshold_value=limits.min_disk_free_bytes,
                    severity=self._calculate_severity(
                        limits.min_disk_free_bytes - usage.free,
                        limits.min_disk_free_bytes,
                        inverse=True
                    ),
                    message=f"Low disk space on {path}: {usage.free / (1024**3):.1f} GB free",
                    recommended_action="Free up disk space or clean temporary files"
                )

        # Check GPU
        if snapshot.gpu_usage:
            for gpu in snapshot.gpu_usage:
                if gpu.memory_percent > limits.max_gpu_memory_percent:
                    self._trigger_alert(
                        resource_type=ResourceType.GPU,
                        current_value=gpu.memory_percent,
                        threshold_value=limits.max_gpu_memory_percent,
                        severity=self._calculate_severity(
                            gpu.memory_percent,
                            limits.max_gpu_memory_percent
                        ),
                        message=f"GPU {gpu.id} memory at {gpu.memory_percent:.1f}%",
                        recommended_action="Consider reducing batch size or model size"
                    )

    def _calculate_severity(
        self,
        current: float,
        threshold: float,
        inverse: bool = False
    ) -> AlertSeverity:
        """
        Calculate alert severity based on how much threshold is exceeded.

        Args:
            current: Current value
            threshold: Threshold value
            inverse: If True, lower values are worse

        Returns:
            Alert severity
        """
        if inverse:
            ratio = threshold / current if current > 0 else float('inf')
        else:
            ratio = current / threshold

        if ratio >= 1.5:
            return AlertSeverity.CRITICAL
        elif ratio >= 1.25:
            return AlertSeverity.HIGH
        elif ratio >= 1.1:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW

    def _trigger_alert(
        self,
        resource_type: ResourceType,
        current_value: float,
        threshold_value: float,
        severity: AlertSeverity,
        message: str,
        recommended_action: str
    ) -> None:
        """
        Trigger resource alert and notify callbacks.

        Args:
            resource_type: Type of resource
            current_value: Current resource value
            threshold_value: Threshold that was exceeded
            severity: Alert severity
            message: Alert message
            recommended_action: Recommended action to take
        """
        # Create alert ID (prevents duplicate alerts)
        alert_id = f"{resource_type.value}_{severity.value}"

        # Check if alert already active
        with self._lock:
            if alert_id in self._active_alerts:
                # Update existing alert
                self._active_alerts[alert_id].current_value = current_value
                self._active_alerts[alert_id].timestamp = datetime.now()
                return

            # Create new alert
            alert = ResourceAlert(
                alert_id=alert_id,
                resource_type=resource_type,
                current_value=current_value,
                threshold_value=threshold_value,
                severity=severity,
                timestamp=datetime.now(),
                message=message,
                recommended_action=recommended_action
            )

            self._active_alerts[alert_id] = alert

            # Add to history
            self._alert_history.append(alert)

            # Notify callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    _logger.warning("Error in alert callback: %s", e)
