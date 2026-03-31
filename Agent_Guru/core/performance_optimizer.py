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
import time
from collections import deque
from collections.abc import Callable
from typing import Any, Optional, TypeVar

logger = logging.getLogger(__name__)

_PLATFORM = platform.system().lower()
F = TypeVar("F", bound=Callable[..., Any])


class LatencyAccumulator:
    """Rolling latency accumulator for a named pipeline stage.

    Collects live samples and computes mean/p95 on demand.
    Use LatencyStats (from core.performance) for computed result snapshots.
    """

    def __init__(self, name: str, target_ms: float) -> None:
        self.name = name
        self.target_ms = target_ms
        self._samples: deque[float] = deque(maxlen=1000)

    def record(self, latency_ms: float) -> None:
        self._samples.append(latency_ms)

    @property
    def mean_ms(self) -> float:
        return sum(self._samples) / len(self._samples) if self._samples else 0.0

    @property
    def p95_ms(self) -> float:
        if not self._samples:
            return 0.0
        sorted_s = sorted(self._samples)
        idx = int(len(sorted_s) * 0.95)
        return sorted_s[min(idx, len(sorted_s) - 1)]

    @property
    def meets_target(self) -> bool:
        return self.p95_ms <= self.target_ms

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_ms": self.target_ms,
            "mean_ms": round(self.mean_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "meets_target": self.meets_target,
            "samples": len(self._samples),
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

    # ------------------------------------------------------------------
    # Measurement context manager
    # ------------------------------------------------------------------

    class _Timer:
        def __init__(self, stats: LatencyStats) -> None:
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
        """Return cached LLM response for a prompt key, or None."""
        result = self._response_cache.get(prompt_key)
        if result is not None:
            self._cache_hits += 1
        else:
            self._cache_misses += 1
        return result

    def cache_response(self, prompt_key: str, response: str) -> None:
        """Cache an LLM response. Evicts oldest when cache exceeds 512 entries."""
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
            if stats._samples and not stats.meets_target
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
            stats._samples.clear()
        self._response_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
