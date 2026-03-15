"""
Module: Agent_Guru.avatar.performance
Purpose: Real-time performance monitoring for the avatar system.

Tracks CPU, memory, FPS, and latency metrics using psutil.
Enforces configurable resource limits with graceful degradation.

Requirements: Req 7 (Performance and Resource Management)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Deque, Dict, Optional

logger = logging.getLogger("guruvision.avatar.performance")


class PerformanceMonitor:
    """Monitor CPU, memory, and rendering performance.

    Args:
        max_cpu_percent: CPU usage limit (0-100).
        max_memory_mb: Memory usage limit in MB.
        sample_interval: Sampling interval in seconds.
        history_size: Number of samples to keep in history.
    """

    def __init__(
        self,
        max_cpu_percent: float = 50.0,
        max_memory_mb: float = 512.0,
        sample_interval: float = 1.0,
        history_size: int = 60,
    ) -> None:
        self._max_cpu = max_cpu_percent
        self._max_memory = max_memory_mb
        self._sample_interval = sample_interval

        self._cpu_history: Deque[float] = deque(maxlen=history_size)
        self._memory_history: Deque[float] = deque(maxlen=history_size)
        self._fps_history: Deque[float] = deque(maxlen=history_size)
        self._latency_history: Deque[float] = deque(maxlen=history_size)

        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._psutil_available = self._check_psutil()
        self._process = None

        if self._psutil_available:
            import psutil  # type: ignore[import]
            self._process = psutil.Process()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start background monitoring thread."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="avatar-perf-monitor",
        )
        self._monitor_thread.start()
        logger.info("Performance monitor started")

    def stop(self) -> None:
        """Stop background monitoring thread."""
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        logger.info("Performance monitor stopped")

    # ------------------------------------------------------------------
    # Metrics recording
    # ------------------------------------------------------------------

    def record_fps(self, fps: float) -> None:
        """Record a FPS measurement."""
        self._fps_history.append(fps)

    def record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement in milliseconds."""
        self._latency_history.append(latency_ms)

    # ------------------------------------------------------------------
    # Metrics retrieval
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, float]:
        """Return current performance metrics.

        Returns:
            Dict with keys: cpu_percent, memory_mb, fps, latency_ms,
            cpu_limit_exceeded, memory_limit_exceeded.
        """
        cpu = self._get_cpu()
        memory = self._get_memory()
        fps = float(self._fps_history[-1]) if self._fps_history else 0.0
        latency = float(self._latency_history[-1]) if self._latency_history else 0.0

        return {
            "cpu_percent": cpu,
            "memory_mb": memory,
            "fps": fps,
            "latency_ms": latency,
            "cpu_limit_exceeded": float(cpu > self._max_cpu),
            "memory_limit_exceeded": float(memory > self._max_memory),
            "avg_fps": self._avg(self._fps_history),
            "avg_latency_ms": self._avg(self._latency_history),
            "p95_latency_ms": self._percentile(self._latency_history, 95),
        }

    def is_resource_constrained(self) -> bool:
        """Return True if CPU or memory limits are exceeded."""
        return (
            self._get_cpu() > self._max_cpu
            or self._get_memory() > self._max_memory
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            cpu = self._get_cpu()
            memory = self._get_memory()
            self._cpu_history.append(cpu)
            self._memory_history.append(memory)

            if cpu > self._max_cpu:
                logger.warning("CPU usage %.1f%% exceeds limit %.1f%%", cpu, self._max_cpu)
            if memory > self._max_memory:
                logger.warning("Memory %.1fMB exceeds limit %.1fMB", memory, self._max_memory)

            time.sleep(self._sample_interval)

    def _get_cpu(self) -> float:
        if self._process is None:
            return 0.0
        try:
            return float(self._process.cpu_percent(interval=None))
        except Exception:
            return 0.0

    def _get_memory(self) -> float:
        if self._process is None:
            return 0.0
        try:
            import psutil  # type: ignore[import]
            info = self._process.memory_info()
            return float(info.rss / (1024 * 1024))  # bytes → MB
        except Exception:
            return 0.0

    @staticmethod
    def _avg(history: Deque[float]) -> float:
        if not history:
            return 0.0
        return float(sum(history) / len(history))

    @staticmethod
    def _percentile(history: Deque[float], p: int) -> float:
        if not history:
            return 0.0
        import numpy as np
        return float(np.percentile(list(history), p))

    @staticmethod
    def _check_psutil() -> bool:
        try:
            import psutil  # noqa: F401
            return True
        except ImportError:
            logger.debug("psutil not available — performance monitoring limited")
            return False
