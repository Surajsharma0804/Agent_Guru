"""Multi-platform performance optimizer for Agent Guru.

Profiles and optimizes:
- Wake word detection latency
- STT/TTS pipeline throughput
- LLM inference caching
- Memory usage
- Battery efficiency (mobile)

Performance targets:
  - Wake word: <200ms
  - STT: <1s
  - LLM: <2s
  - End-to-end: <4s
  - Mobile battery (sleep): <5%/hour
  - Mobile battery (active): <10%/hour
"""

from __future__ import annotations

import logging
import platform
import threading
import time
from typing import Any, Optional, TypeVar
from collections.abc import Callable

# BUG-024: import the canonical LatencyTracker instead of reimplementing the
# same rolling-window + percentile logic a third time.
from Agent_Guru.core.performance import LatencyTracker, PipelineStage

logger = logging.getLogger(__name__)

_PLATFORM = platform.system().lower()
F = TypeVar("F", bound=Callable[..., Any])


class LatencyAccumulator:
    """Thin wrapper around :class:`LatencyTracker` for a single named stage.

    BUG-024 fix: the original LatencyAccumulator reimplemented rolling-window
    storage and P95 computation that already exist in
    ``core.performance.LatencyTracker``.  This rewrite delegates all math to
    LatencyTracker, keeping the public API identical so callers need no changes.

    Use LatencyStats (from core.performance) for computed result snapshots.
    """

    def __init__(self, name: str, target_ms: float) -> None:
        self.name = name
        self.target_ms = target_ms
        # Reuse the canonical tracker; register a dynamic stage key by name
        # by using a private single-stage tracker instance.
        self._tracker = LatencyTracker(window_size=1000)
        # Map our free-form name to the WAKE_WORD slot as generic storage;
        # we always query via get_stats(PipelineStage.WAKE_WORD) below.
        # All math (mean, p95, min, max) is done by LatencyTracker.
        self._stage = PipelineStage.WAKE_WORD  # used as a single-slot store

    def record(self, latency_ms: float) -> None:
        """Record a latency sample."""
        self._tracker.record(self._stage, latency_ms)

    @property
    def mean_ms(self) -> float:
        stats = self._tracker.get_stats(self._stage)
        return stats.mean_ms if stats else 0.0

    @property
    def p95_ms(self) -> float:
        stats = self._tracker.get_stats(self._stage)
        return stats.p95_ms if stats else 0.0

    @property
    def meets_target(self) -> bool:
        return self.p95_ms <= self.target_ms

    @property
    def sample_count(self) -> int:
        stats = self._tracker.get_stats(self._stage)
        return stats.count if stats else 0

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_ms": self.target_ms,
            "mean_ms": round(self.mean_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "meets_target": self.meets_target,
            "samples": self.sample_count,
        }


class PerformanceOptimizer:
    """Profiles and optimizes Agent Guru performance across all platforms.

    Tracks latency for each pipeline stage and provides optimization
    recommendations based on measured bottlenecks.

    Example:
        >>> opt = PerformanceOptimizer()
        >>> with opt.measure("wake_word"):
        ...     detect_wake_word()
        >>> report = opt.get_report()
        >>> print(report["wake_word"]["meets_target"])

    Performance:
        - Measurement overhead: <0.1ms per sample
        - Memory: O(1000) samples per stage (rolling window)
    """

    # Latency targets per stage (ms) — matches _TARGETS_MS in core.performance
    _TARGETS: dict[str, float] = {
        "wake_word":   50.0,    # ≤50ms  (core.performance.PipelineStage.WAKE_WORD)
        "stt":        120.0,    # ≤120ms/s of audio
        "intent":      50.0,    # ≤50ms
        "llm":        300.0,    # ≤300ms first token
        "tts":        200.0,    # ≤200ms
        "end_to_end": 2500.0,   # ≤2500ms
    }

    def __init__(self) -> None:
        self._stats: dict[str, LatencyAccumulator] = {
            name: LatencyAccumulator(name=name, target_ms=target)
            for name, target in self._TARGETS.items()
        }
        self._response_cache: dict[str, str] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        # Lock guards the cache dict and hit/miss counters against concurrent
        # async tasks interleaved at await points (read-modify-write is not atomic).
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Measurement context manager
    # ------------------------------------------------------------------

    class _Timer:
        # BUG-005: annotation was `LatencyStats` (from core/performance.py) but
        # the actual argument is `LatencyAccumulator` defined in this file.
        def __init__(self, stats: "LatencyAccumulator") -> None:
            self._stats = stats
            self._start = 0.0

        def __enter__(self) -> "PerformanceOptimizer._Timer":
            self._start = time.perf_counter()
            return self

        def __exit__(self, *_: Any) -> None:
            elapsed_ms = (time.perf_counter() - self._start) * 1000
            self._stats.record(elapsed_ms)

    def measure(self, stage: str) -> "PerformanceOptimizer._Timer":
        """Context manager to measure latency for a pipeline stage.

        Args:
            stage: One of wake_word, stt, intent, llm, tts, end_to_end.

        Returns:
            Context manager that records elapsed time on exit.
        """
        if stage not in self._stats:
            self._stats[stage] = LatencyAccumulator(name=stage, target_ms=float("inf"))
        return self._Timer(self._stats[stage])

    # ------------------------------------------------------------------
    # LLM response caching (reduces redundant API calls)
    # ------------------------------------------------------------------

    def get_cached_response(self, prompt_key: str) -> Optional[str]:
        """Return a cached LLM response or None on cache miss."""
        with self._cache_lock:
            result = self._response_cache.get(prompt_key)
            if result is not None:
                self._cache_hits += 1
            else:
                self._cache_misses += 1
            return result

    def cache_response(self, prompt_key: str, response: str) -> None:
        """Cache an LLM response. Evicts oldest when cache exceeds 512 entries."""
        with self._cache_lock:
            if len(self._response_cache) >= 512:
                # Evict oldest key (O(1) amortized with dict ordering in Python 3.7+)
                oldest = next(iter(self._response_cache))
                del self._response_cache[oldest]
            self._response_cache[prompt_key] = response

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate as a fraction [0.0, 1.0]."""
        total = self._cache_hits + self._cache_misses
        return self._cache_hits / total if total > 0 else 0.0

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_report(self) -> dict[str, Any]:
        """Return a full performance report for all tracked stages."""
        return {name: stats.summary() for name, stats in self._stats.items()}

    def get_bottlenecks(self) -> list[str]:
        """Return list of stages that are not meeting their latency targets."""
        return [
            name for name, stats in self._stats.items()
            if stats.sample_count > 0 and not stats.meets_target
        ]

    def log_report(self) -> None:
        """Log the performance report at INFO level."""
        report = self.get_report()
        bottlenecks = self.get_bottlenecks()
        logger.info("Performance report (platform=%s):", _PLATFORM)
        for name, summary in report.items():
            status = "✅" if summary["meets_target"] else "❌"
            logger.info(
                "  %s %s: mean=%.1fms p95=%.1fms target=%.0fms",
                status, name, summary["mean_ms"], summary["p95_ms"], summary["target_ms"],
            )
        if bottlenecks:
            logger.warning("Bottlenecks: %s", bottlenecks)
        logger.info(
            "LLM cache: hits=%d misses=%d rate=%.1f%%",
            self._cache_hits, self._cache_misses, self.cache_hit_rate * 100,
        )

    def reset(self) -> None:
        """Reset all statistics."""
        for stats in self._stats.values():
            # BUG-024: delegate to LatencyTracker.clear() — no more direct _samples access
            stats._tracker.clear(stats._stage)
        self._response_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
