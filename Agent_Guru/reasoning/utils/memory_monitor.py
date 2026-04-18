"""
Memory monitoring and management for Agent_Guru reasoning engine.

This module provides memory usage tracking, limit enforcement, and leak detection
to ensure the reasoning engine operates within resource constraints.

Performance Requirements:
- Memory tracking: O(1) per check
- Limit enforcement: <10ms overhead
- Leak detection: Background task, no impact on main thread

Design:
- Track memory per component using psutil
- Enforce 4GB limit per instance
- Automatic GC tuning based on memory pressure
- Memory leak detection using growth rate analysis
"""

import gc
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot at a point in time."""

    timestamp: datetime
    total_mb: float
    rss_mb: float  # Resident Set Size
    vms_mb: float  # Virtual Memory Size
    percent: float
    component: str = "system"


@dataclass
class ComponentMemoryStats:
    """Memory statistics for a component."""

    component_name: str
    current_mb: float = 0.0
    peak_mb: float = 0.0
    avg_mb: float = 0.0
    samples: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=100))

    def update(self, memory_mb: float) -> None:
        """Update statistics with new memory reading."""
        self.current_mb = memory_mb
        self.peak_mb = max(self.peak_mb, memory_mb)
        self.samples += 1

        # Update running average
        self.avg_mb = ((self.avg_mb * (self.samples - 1)) + memory_mb) / self.samples

        # Add to history
        self.history.append((datetime.now(tz=timezone.utc), memory_mb))


class MemoryMonitor:
    """
    Monitor and manage memory usage for the reasoning engine.

    Features:
    - Per-component memory tracking
    - Memory limit enforcement (4GB default)
    - Automatic garbage collection tuning
    - Memory leak detection

    Time Complexity: O(1) for tracking operations
    Space Complexity: O(n) where n is number of components

    Example:
        >>> monitor = MemoryMonitor(max_memory_mb=4096)
        >>> monitor.start()
        >>> monitor.track_component("intent_detection", 150.5)
        >>> stats = monitor.get_stats()
        >>> monitor.stop()
    """

    def __init__(
        self,
        max_memory_mb: float = 4096.0,  # 4GB default
        check_interval: float = 5.0,  # Check every 5 seconds
        gc_threshold_percent: float = 0.8,  # Trigger GC at 80%
        leak_detection_enabled: bool = True
    ):
        """
        Initialize memory monitor.

        Args:
            max_memory_mb: Maximum memory allowed in MB
            check_interval: Interval between memory checks in seconds
            gc_threshold_percent: Memory usage percent to trigger GC
            leak_detection_enabled: Enable memory leak detection
        """
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        self.gc_threshold_percent = gc_threshold_percent
        self.leak_detection_enabled = leak_detection_enabled

        # Process handle
        self.process = psutil.Process()

        # Component tracking
        self.component_stats: dict[str, ComponentMemoryStats] = {}
        self._stats_lock = threading.Lock()

        # System memory history
        self.memory_history: deque = deque(maxlen=1000)

        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # GC tuning
        self._gc_count = 0
        self._last_gc_time = time.time()

        # Leak detection
        self._leak_warnings: list[str] = []

        # Configure GC thresholds for better performance
        self._configure_gc()

        logger.info(
            f"MemoryMonitor initialized: max={max_memory_mb}MB, "
            f"interval={check_interval}s, gc_threshold={gc_threshold_percent}"
        )

    def _configure_gc(self) -> None:
        """Configure garbage collection for optimal performance."""
        # Set GC thresholds (generation 0, 1, 2)
        # More aggressive collection to prevent memory buildup
        gc.set_threshold(700, 10, 10)
        logger.info("GC thresholds configured: %s", gc.get_threshold())

    def start(self) -> None:
        """Start background memory monitoring."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Memory monitor already running")
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="MemoryMonitor"
        )
        self._monitor_thread.start()
        logger.info("Memory monitor started")

    def stop(self) -> None:
        """Stop background memory monitoring."""
        if not self._monitor_thread:
            return

        self._stop_event.set()
        self._monitor_thread.join(timeout=10.0)
        logger.info("Memory monitor stopped")

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_event.is_set():
            try:
                self._check_memory()
                self._detect_leaks()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error("Error in memory monitor loop: %s", e, exc_info=True)

    def _check_memory(self) -> None:
        """Check current memory usage and enforce limits."""
        try:
            # Get memory info
            mem_info = self.process.memory_info()
            mem_percent = self.process.memory_percent()

            rss_mb = mem_info.rss / (1024 * 1024)
            vms_mb = mem_info.vms / (1024 * 1024)

            # Create snapshot
            snapshot = MemorySnapshot(
                timestamp=datetime.now(tz=timezone.utc),
                total_mb=rss_mb,
                rss_mb=rss_mb,
                vms_mb=vms_mb,
                percent=mem_percent
            )

            # Add to history
            self.memory_history.append(snapshot)

            # Check if over limit
            if rss_mb > self.max_memory_mb:
                logger.error(
                    "Memory limit exceeded: %.1fMB > %.1fMB", rss_mb, self.max_memory_mb
                )
                self._trigger_emergency_gc()

            # Check if approaching limit
            elif rss_mb > (self.max_memory_mb * self.gc_threshold_percent):
                logger.warning(
                    "Memory usage high: %.1fMB (%.1f%% of limit)",
                    rss_mb, mem_percent,
                )
                self._trigger_gc()

        except Exception as e:
            logger.error("Error checking memory: %s", e, exc_info=True)

    def _trigger_gc(self) -> None:
        """Trigger garbage collection."""
        # Avoid triggering GC too frequently
        if time.time() - self._last_gc_time < 10.0:
            return

        start_time = time.time()
        collected = gc.collect()
        duration = time.time() - start_time

        self._gc_count += 1
        self._last_gc_time = time.time()

        logger.info(
            "GC triggered: collected %d objects in %.1fms (total GC count: %d)",
            collected, duration * 1000, self._gc_count,
        )

    def _trigger_emergency_gc(self) -> None:
        """Trigger aggressive garbage collection when over limit."""
        logger.warning("Triggering emergency GC (memory limit exceeded)")

        # Collect all generations
        for generation in range(3):
            collected = gc.collect(generation)
            logger.info("Emergency GC generation %d: collected %d", generation, collected)

        self._last_gc_time = time.time()

    def _detect_leaks(self) -> None:
        """Detect potential memory leaks using growth rate analysis."""
        if not self.leak_detection_enabled:
            return

        if len(self.memory_history) < 10:
            return  # Need more data

        try:
            # Get recent memory samples
            recent = list(self.memory_history)[-10:]

            # Calculate growth rate
            first_mb = recent[0].rss_mb
            last_mb = recent[-1].rss_mb
            growth_mb = last_mb - first_mb
            growth_rate = growth_mb / first_mb if first_mb > 0 else 0

            # Check for sustained growth (potential leak)
            if growth_rate > 0.1 and growth_mb > 100:  # 10% growth and >100MB
                warning = (
                    f"Potential memory leak detected: "
                    f"growth={growth_mb:.1f}MB ({growth_rate*100:.1f}%) "
                    f"over last {len(recent)} checks"
                )

                if warning not in self._leak_warnings:
                    logger.warning(warning)
                    self._leak_warnings.append(warning)

                    # Trigger GC to try to reclaim memory
                    self._trigger_gc()

        except Exception as e:
            logger.error("Error detecting leaks: %s", e, exc_info=True)

    def track_component(self, component_name: str, memory_mb: float) -> None:
        """
        Track memory usage for a specific component.

        Args:
            component_name: Name of the component
            memory_mb: Memory usage in MB
        """
        with self._stats_lock:
            if component_name not in self.component_stats:
                self.component_stats[component_name] = ComponentMemoryStats(
                    component_name=component_name
                )

            self.component_stats[component_name].update(memory_mb)

    def get_stats(self) -> dict[str, ComponentMemoryStats]:
        """
        Get memory statistics for all components.

        Returns:
            Dictionary mapping component names to their stats
        """
        with self._stats_lock:
            return dict(self.component_stats)

    def get_current_usage(self) -> float:
        """
        Get current total memory usage in MB.

        Returns:
            Current memory usage in MB
        """
        mem_info = self.process.memory_info()
        return mem_info.rss / (1024 * 1024)

    def get_usage_percent(self) -> float:
        """
        Get current memory usage as percentage of limit.

        Returns:
            Memory usage percentage (0-100)
        """
        current_mb = self.get_current_usage()
        return (current_mb / self.max_memory_mb) * 100

    def is_over_limit(self) -> bool:
        """
        Check if memory usage exceeds limit.

        Returns:
            True if over limit, False otherwise
        """
        return self.get_current_usage() > self.max_memory_mb

    def get_leak_warnings(self) -> list[str]:
        """
        Get list of memory leak warnings.

        Returns:
            List of leak warning messages
        """
        return list(self._leak_warnings)

    def clear_leak_warnings(self) -> None:
        """Clear memory leak warnings."""
        self._leak_warnings.clear()

    def get_summary(self) -> dict:
        """
        Get summary of memory usage.

        Returns:
            Dictionary with memory usage summary
        """
        current_mb = self.get_current_usage()
        percent = self.get_usage_percent()

        component_summary = {}
        with self._stats_lock:
            for name, stats in self.component_stats.items():
                component_summary[name] = {
                    "current_mb": stats.current_mb,
                    "peak_mb": stats.peak_mb,
                    "avg_mb": stats.avg_mb,
                    "samples": stats.samples
                }

        return {
            "current_mb": current_mb,
            "max_mb": self.max_memory_mb,
            "percent": percent,
            "over_limit": self.is_over_limit(),
            "gc_count": self._gc_count,
            "leak_warnings": len(self._leak_warnings),
            "components": component_summary,
            "history_size": len(self.memory_history)
        }


# Global memory monitor instance
_global_monitor: Optional[MemoryMonitor] = None


def get_memory_monitor() -> MemoryMonitor:
    """
    Get global memory monitor instance.

    Returns:
        Global MemoryMonitor instance
    """
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = MemoryMonitor()
        _global_monitor.start()
    return _global_monitor


def track_memory(component_name: str) -> None:
    """
    Track memory usage for a component (convenience function).

    Args:
        component_name: Name of the component to track
    """
    monitor = get_memory_monitor()
    current_mb = monitor.get_current_usage()
    monitor.track_component(component_name, current_mb)
