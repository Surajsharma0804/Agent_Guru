"""Module: Agent_Guru.platform.hardware.monitor
Purpose: Cross-platform hardware monitoring with <1s query response time.

Performance Requirements:
- Time Complexity: O(1) per metric query
- Space Complexity: O(1) (no unbounded growth)
- Query Response: <1 second (all metrics)
- Accuracy: Real-time system metrics

Design Decisions:
- Use psutil for cross-platform compatibility
- Use GPUtil for GPU metrics (optional)
- Return None for unavailable metrics (graceful degradation)
- Cache-friendly design for repeated queries

Author: Agent Guru Team
Date: 2026-02-24
Version: 1.0.0
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import psutil

# Optional GPU support
try:
    import GPUtil

    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False


class NetworkInterfaceStatus(Enum):
    """Network interface status."""

    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class CPUInfo:
    """CPU usage information.

    Attributes:
        percent: Overall CPU usage percentage (0-100)
        per_cpu: Per-CPU usage percentages (0-100 each)
        count_physical: Number of physical CPU cores
        count_logical: Number of logical CPU cores
        frequency_current: Current CPU frequency in MHz
        frequency_min: Minimum CPU frequency in MHz
        frequency_max: Maximum CPU frequency in MHz

    """

    percent: float
    per_cpu: list[float]
    count_physical: int
    count_logical: int
    frequency_current: float | None
    frequency_min: float | None
    frequency_max: float | None


@dataclass
class MemoryInfo:
    """Memory usage information.

    Attributes:
        total: Total physical memory in bytes
        available: Available memory in bytes
        used: Used memory in bytes
        percent: Memory usage percentage (0-100)
        swap_total: Total swap memory in bytes
        swap_used: Used swap memory in bytes
        swap_percent: Swap usage percentage (0-100)

    """

    total: int
    available: int
    used: int
    percent: float
    swap_total: int
    swap_used: int
    swap_percent: float


@dataclass
class DiskInfo:
    """Disk usage information.

    Attributes:
        total: Total disk space in bytes
        used: Used disk space in bytes
        free: Free disk space in bytes
        percent: Disk usage percentage (0-100)
        path: Disk mount path

    """

    total: int
    used: int
    free: int
    percent: float
    path: str


@dataclass
class NetworkInterface:
    """Network interface information.

    Attributes:
        name: Interface name (e.g., 'eth0', 'wlan0')
        status: Interface status (up/down/unknown)
        bytes_sent: Total bytes sent
        bytes_recv: Total bytes received
        packets_sent: Total packets sent
        packets_recv: Total packets received
        errors_in: Input errors
        errors_out: Output errors
        drops_in: Input drops
        drops_out: Output drops

    """

    name: str
    status: NetworkInterfaceStatus
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errors_in: int
    errors_out: int
    drops_in: int
    drops_out: int


@dataclass
class GPUInfo:
    """GPU information.

    Attributes:
        id: GPU ID
        name: GPU name
        load: GPU load percentage (0-100)
        memory_total: Total GPU memory in MB
        memory_used: Used GPU memory in MB
        memory_free: Free GPU memory in MB
        temperature: GPU temperature in Celsius

    """

    id: int
    name: str
    load: float
    memory_total: float
    memory_used: float
    memory_free: float
    temperature: float


@dataclass
class BatteryInfo:
    """Battery information.

    Attributes:
        percent: Battery percentage (0-100)
        is_charging: Whether battery is charging
        time_remaining: Estimated time remaining in seconds (None if charging)

    """

    percent: float
    is_charging: bool
    time_remaining: int | None


class HardwareMonitor:
    """Cross-platform hardware monitor using psutil and GPUtil.

    Time Complexity: O(1) per metric query
    Space Complexity: O(1) (no unbounded growth)
    Query Response: <1 second (all metrics)

    Example:
        >>> monitor = HardwareMonitor()
        >>> cpu_info = monitor.get_cpu_usage()
        >>> print(f"CPU usage: {cpu_info.percent}%")
        >>> memory_info = monitor.get_memory_info()
        >>> print(f"Memory usage: {memory_info.percent}%")

    """

    def __init__(self) -> None:
        """Initialize hardware monitor."""

    def get_cpu_usage(self, per_cpu: bool = False, interval: float = 0.1) -> CPUInfo:
        """Get CPU usage information.

        Time Complexity: O(1)
        Space Complexity: O(num_cpus) for per_cpu list

        Args:
            per_cpu: If True, include per-CPU usage
            interval: Measurement interval in seconds (default: 0.1)

        Returns:
            CPUInfo with current CPU metrics

        Raises:
            RuntimeError: If CPU metrics cannot be retrieved

        """
        try:
            # Get CPU usage percentage
            percent = psutil.cpu_percent(interval=interval)

            # Get per-CPU usage if requested
            per_cpu_list = []
            if per_cpu:
                per_cpu_list = psutil.cpu_percent(interval=interval, percpu=True)

            # Get CPU counts
            count_physical = psutil.cpu_count(logical=False) or 0
            count_logical = psutil.cpu_count(logical=True) or 0

            # Get CPU frequency (may not be available on all platforms)
            freq = psutil.cpu_freq()
            frequency_current = freq.current if freq else None
            frequency_min = freq.min if freq else None
            frequency_max = freq.max if freq else None

            return CPUInfo(
                percent=percent,
                per_cpu=per_cpu_list,
                count_physical=count_physical,
                count_logical=count_logical,
                frequency_current=frequency_current,
                frequency_min=frequency_min,
                frequency_max=frequency_max,
            )
        except Exception as e:
            msg = f"Failed to get CPU usage: {e}"
            raise RuntimeError(msg) from e

    def get_memory_info(self) -> MemoryInfo:
        """Get memory usage information.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            MemoryInfo with current memory metrics

        Raises:
            RuntimeError: If memory metrics cannot be retrieved

        """
        try:
            # Get virtual memory
            mem = psutil.virtual_memory()

            # Get swap memory
            swap = psutil.swap_memory()

            return MemoryInfo(
                total=mem.total,
                available=mem.available,
                used=mem.used,
                percent=mem.percent,
                swap_total=swap.total,
                swap_used=swap.used,
                swap_percent=swap.percent,
            )
        except Exception as e:
            msg = f"Failed to get memory info: {e}"
            raise RuntimeError(msg) from e

    def get_disk_usage(self, path: str = "/") -> DiskInfo:
        """Get disk usage for specified path.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            path: Path to check disk usage (default: root)

        Returns:
            DiskInfo with disk usage metrics

        Raises:
            RuntimeError: If disk metrics cannot be retrieved
            ValueError: If path does not exist

        """
        try:
            usage = psutil.disk_usage(path)

            return DiskInfo(
                total=usage.total,
                used=usage.used,
                free=usage.free,
                percent=usage.percent,
                path=path,
            )
        except FileNotFoundError as e:
            msg = f"Path does not exist: {path}"
            raise ValueError(msg) from e
            msg = f"Failed to get disk usage: {e}"
            raise RuntimeError(msg) from e

    def get_network_interfaces(self) -> list[NetworkInterface]:
        """Get network interface information.

        Time Complexity: O(n) where n is number of interfaces
        Space Complexity: O(n)

        Returns:
            List of NetworkInterface with current network metrics

        Raises:
            RuntimeError: If network metrics cannot be retrieved

        """
        try:
            interfaces = []

            # Get network I/O statistics
            net_io = psutil.net_io_counters(pernic=True)

            # Get interface status
            net_if_stats = psutil.net_if_stats()

            for name, stats in net_io.items():
                # Determine interface status
                if name in net_if_stats:
                    is_up = net_if_stats[name].isup
                    status = NetworkInterfaceStatus.UP if is_up else NetworkInterfaceStatus.DOWN
                else:
                    status = NetworkInterfaceStatus.UNKNOWN

                interfaces.append(
                    NetworkInterface(
                        name=name,
                        status=status,
                        bytes_sent=stats.bytes_sent,
                        bytes_recv=stats.bytes_recv,
                        packets_sent=stats.packets_sent,
                        packets_recv=stats.packets_recv,
                        errors_in=stats.errin,
                        errors_out=stats.errout,
                        drops_in=stats.dropin,
                        drops_out=stats.dropout,
                    ),
                )

            return interfaces
        except Exception as e:
            msg = f"Failed to get network interfaces: {e}"
            raise RuntimeError(msg) from e

    def get_gpu_info(self) -> list[GPUInfo] | None:
        """Get GPU information if available.

        Time Complexity: O(n) where n is number of GPUs
        Space Complexity: O(n)

        Returns:
            List of GPUInfo or None if GPU not available

        """
        if not GPU_AVAILABLE:
            return None

        try:
            gpus = GPUtil.getGPUs()

            if not gpus:
                return None

            gpu_info_list = []
            for gpu in gpus:
                gpu_info_list.append(
                    GPUInfo(
                        id=gpu.id,
                        name=gpu.name,
                        load=gpu.load * 100,  # Convert to percentage
                        memory_total=gpu.memoryTotal,
                        memory_used=gpu.memoryUsed,
                        memory_free=gpu.memoryFree,
                        temperature=gpu.temperature,
                    ),
                )

            return gpu_info_list
        except Exception:
            # GPU metrics unavailable
            return None

    def get_battery_info(self) -> BatteryInfo | None:
        """Get battery information if available.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            BatteryInfo or None if no battery

        """
        try:
            battery = psutil.sensors_battery()

            if battery is None:
                return None

            return BatteryInfo(
                percent=battery.percent,
                is_charging=battery.power_plugged,
                time_remaining=battery.secsleft
                if battery.secsleft != psutil.POWER_TIME_UNLIMITED
                else None,
            )
        except Exception:
            # Battery info unavailable
            return None

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all available hardware metrics.

        Time Complexity: O(n) where n is number of interfaces/GPUs
        Space Complexity: O(n)
        Query Response: <1 second (target)

        Returns:
            Dictionary with all available metrics

        """
        metrics = {}

        # CPU metrics
        try:
            metrics["cpu"] = self.get_cpu_usage(per_cpu=True)
        except Exception:
            metrics["cpu"] = None
        # Memory metrics
        try:
            metrics["memory"] = self.get_memory_info()
        except Exception:
            metrics["memory"] = None
        # Disk metrics
        try:
            metrics["disk"] = self.get_disk_usage()
        except Exception:
            metrics["disk"] = None
        # Network metrics
        try:
            metrics["network"] = self.get_network_interfaces()
        except Exception:
            metrics["network"] = None
        # GPU metrics (optional)
        metrics["gpu"] = self.get_gpu_info()

        # Battery metrics (optional)
        metrics["battery"] = self.get_battery_info()

        return metrics
