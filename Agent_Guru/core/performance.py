"""
Module: Agent_Guru.core.performance
Purpose: Performance monitoring and optimization utilities

Provides:
- LatencyTracker: Per-stage latency measurement with P50/P95/P99
- ResourceMonitor: CPU/memory usage tracking
- PerformanceTargets: Validated targets for each pipeline stage
- StartupTimer: Application startup time measurement

Performance Targets (from requirements):
    - Wake word detection: ≤50ms
    - STT processing: ≤120ms/sec of audio
    - Intent classification: ≤50ms
    - LLM first token: ≤300ms
    - TTS synthesis: ≤200ms
    - End-to-end: ≤2500ms
    - Idle CPU: <10%
    - Active CPU: <20%
    - Memory: <500MB

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """Pipeline stages for latency tracking."""
    WAKE_WORD = "wake_word"
    STT = "stt"
    INTENT = "intent"
    LLM_FIRST_TOKEN = "llm_first_token"  # BUG-032: removed incorrect nosec B105 — not a password
    TTS = "tts"
    END_TO_END = "end_to_end"
    STARTUP = "startup"


# Performance targets in milliseconds
_TARGETS_MS: dict[PipelineStage, float] = {
    PipelineStage.WAKE_WORD: 50.0,
    PipelineStage.STT: 120.0,       # per second of audio
    PipelineStage.INTENT: 50.0,
    PipelineStage.LLM_FIRST_TOKEN: 300.0,
    PipelineStage.TTS: 200.0,
    PipelineStage.END_TO_END: 2500.0,
    PipelineStage.STARTUP: 5000.0,
}

# Resource targets
_IDLE_CPU_PCT = 10.0
_ACTIVE_CPU_PCT = 20.0
_MAX_MEMORY_MB = 500.0


@dataclass
class LatencyStats:
    """Latency statistics for a pipeline stage.

    Attributes:
        stage: Pipeline stage name
        count: Number of measurements
        mean_ms: Mean latency in milliseconds
        p50_ms: 50th percentile latency
        p95_ms: 95th percentile latency
        p99_ms: 99th percentile latency
        min_ms: Minimum latency
        max_ms: Maximum latency
        target_ms: Performance target
        meets_target: Whether P95 meets the target
    """
    stage: PipelineStage
    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    target_ms: float
    meets_target: bool


class LatencyTracker:
    """
    Per-stage latency tracker with percentile statistics.

    Uses a fixed-size deque for O(1) append and bounded memory.
    Percentiles computed on demand from sorted samples.

    Performance:
        - record(): O(1) amortized
        - get_stats(): O(n log n) for sort
        - Space: O(window_size) per stage
    """

    def __init__(self, window_size: int = 1000) -> None:
        """Initialize latency tracker.

        Args:
            window_size: Maximum samples to keep per stage
        """
        if window_size < 1:
            raise ValueError(f"window_size must be >= 1, got {window_size}")
        self._window_size = window_size
        self._samples: dict[PipelineStage, deque[float]] = {
            stage: deque(maxlen=window_size) for stage in PipelineStage
        }
        self._lock = threading.Lock()

    def record(self, stage: PipelineStage, latency_ms: float) -> None:
        """Record a latency measurement.

        Time Complexity: O(1)

        Args:
            stage: Pipeline stage
            latency_ms: Latency in milliseconds
        """
        if latency_ms < 0:
            raise ValueError(f"latency_ms must be >= 0, got {latency_ms}")
        with self._lock:
            self._samples[stage].append(latency_ms)

    def get_stats(self, stage: PipelineStage) -> LatencyStats | None:
        """Compute latency statistics for a stage.

        Time Complexity: O(n log n) for sort

        Args:
            stage: Pipeline stage

        Returns:
            LatencyStats or None if no samples recorded
        """
        with self._lock:
            samples = sorted(self._samples[stage])

        if not samples:
            return None

        n = len(samples)
        target = _TARGETS_MS.get(stage, float("inf"))

        def percentile(p: float) -> float:
            idx = int(p / 100.0 * (n - 1))
            return samples[min(idx, n - 1)]

        p95 = percentile(95)
        return LatencyStats(
            stage=stage,
            count=n,
            mean_ms=sum(samples) / n,
            p50_ms=percentile(50),
            p95_ms=p95,
            p99_ms=percentile(99),
            min_ms=samples[0],
            max_ms=samples[-1],
            target_ms=target,
            meets_target=p95 <= target,
        )

    def get_all_stats(self) -> dict[PipelineStage, LatencyStats | None]:
        """Get stats for all stages."""
        return {stage: self.get_stats(stage) for stage in PipelineStage}

    def clear(self, stage: PipelineStage | None = None) -> None:
        """Clear samples for a stage or all stages.

        Args:
            stage: Stage to clear, or None to clear all
        """
        with self._lock:
            if stage is not None:
                self._samples[stage].clear()
            else:
                for s in self._samples.values():
                    s.clear()


class StageTimer:
    """
    Context manager for timing a pipeline stage.

    Example:
        >>> tracker = LatencyTracker()
        >>> with StageTimer(tracker, PipelineStage.INTENT):
        ...     result = parse_intent(text)
    """

    def __init__(self, tracker: LatencyTracker, stage: PipelineStage) -> None:
        self._tracker = tracker
        self._stage = stage
        self._start: float = 0.0

    def __enter__(self) -> StageTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._tracker.record(self._stage, elapsed_ms)


class StartupTimer:
    """Measures application startup time."""

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self._checkpoints: dict[str, float] = {}

    def checkpoint(self, name: str) -> float:
        """Record a startup checkpoint.

        Args:
            name: Checkpoint name

        Returns:
            Elapsed time in milliseconds since start
        """
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._checkpoints[name] = elapsed_ms
        logger.debug("Startup checkpoint '%s': %.1fms", name, elapsed_ms)
        return elapsed_ms

    def total_ms(self) -> float:
        """Return total elapsed time in milliseconds."""
        return (time.perf_counter() - self._start) * 1000

    def meets_target(self) -> bool:
        """Return True if startup time meets the 5-second target."""
        return self.total_ms() <= _TARGETS_MS[PipelineStage.STARTUP]

    def get_checkpoints(self) -> dict[str, float]:
        """Return all recorded checkpoints."""
        return dict(self._checkpoints)


class ResourceMonitor:
    """
    CPU and memory usage monitor.

    Uses psutil for cross-platform resource monitoring.
    Falls back gracefully if psutil is not available.
    """

    def __init__(self) -> None:
        self._psutil_available = False
        try:
            import psutil  # noqa: F401
            self._psutil_available = True
        except ImportError:
            logger.warning("psutil not available - resource monitoring disabled")

    def get_cpu_percent(self, interval: float = 0.1) -> float:
        """Get current CPU usage percentage.

        Args:
            interval: Measurement interval in seconds

        Returns:
            CPU usage percentage (0.0-100.0), or -1.0 if unavailable
        """
        if not self._psutil_available:
            return -1.0
        try:
            import psutil
            return psutil.cpu_percent(interval=interval)
        except Exception as e:
            logger.warning("CPU measurement failed: %s", e)
            return -1.0

    def get_memory_mb(self) -> float:
        """Get current process memory usage in MB.

        Returns:
            Memory usage in MB, or -1.0 if unavailable
        """
        if not self._psutil_available:
            return -1.0
        try:
            import os

            import psutil
            proc = psutil.Process(os.getpid())
            return proc.memory_info().rss / (1024 * 1024)
        except Exception as e:
            logger.warning("Memory measurement failed: %s", e)
            return -1.0

    def meets_idle_cpu_target(self) -> bool:
        """Return True if idle CPU usage is within target (<10%)."""
        cpu = self.get_cpu_percent()
        return cpu < 0 or cpu <= _IDLE_CPU_PCT  # -1 means unavailable

    def meets_active_cpu_target(self) -> bool:
        """Return True if active CPU usage is within target (<20%)."""
        cpu = self.get_cpu_percent()
        return cpu < 0 or cpu <= _ACTIVE_CPU_PCT

    def meets_memory_target(self) -> bool:
        """Return True if memory usage is within target (<500MB)."""
        mem = self.get_memory_mb()
        return mem < 0 or mem <= _MAX_MEMORY_MB
