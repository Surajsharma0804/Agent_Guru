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
from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

_PLATFORM = platform.system().lower()
F = TypeVar("F", bound=Callable[..., Any])


class LatencyAccumulator:
    """Per-stage latency accumulator with rolling-window statistics.

    HIGH-001 fix: the previous implementation misrouted ALL stage names
    through ``PipelineStage.WAKE_WORD``, so every LatencyAccumulator instance
    shared the same slot and overwrote each other's data. This rewrite gives
    each accumulator its own independent ``deque`` — semantically correct and
    O(1) amortized append with O(n log n) percentile computation on demand.

    MED-002 fix: public ``reset()`` method added so ``PerformanceOptimizer``
    no longer needs to access private ``_tracker``/``_stage`` attributes.

    Public API is identical to the previous version — zero callers need changes.
    """

    def __init__(self, name: str, target_ms: float, window_size: int = 1000) -> None:
        self.name = name
        self.target_ms = target_ms
        # Own deque — no shared slot, no PipelineStage dependency
        self._samples: deque[float] = deque(maxlen=window_size)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, latency_ms: float) -> None:
        """Record a latency sample. Thread-safe. O(1) amortized."""
        with self._lock:
            self._samples.append(latency_ms)

    # ------------------------------------------------------------------
    # Statistics (computed on demand)
    # ------------------------------------------------------------------

    def _sorted_copy(self) -> list[float]:
        """Return a sorted snapshot of samples under the lock."""
        with self._lock:
            return sorted(self._samples)

    def _percentile(self, samples: list[float], p: float) -> float:
        if not samples:
            return 0.0
        idx = int(p / 100.0 * (len(samples) - 1))
        return samples[min(idx, len(samples) - 1)]

    @property
    def mean_ms(self) -> float:
        s = self._sorted_copy()
        return sum(s) / len(s) if s else 0.0

    @property
    def p50_ms(self) -> float:
        return self._percentile(self._sorted_copy(), 50)

    @property
    def p95_ms(self) -> float:
        return self._percentile(self._sorted_copy(), 95)

    @property
    def p99_ms(self) -> float:
        return self._percentile(self._sorted_copy(), 99)

    @property
    def min_ms(self) -> float:
        s = self._sorted_copy()
        return s[0] if s else 0.0

    @property
    def max_ms(self) -> float:
        s = self._sorted_copy()
        return s[-1] if s else 0.0

    @property
    def meets_target(self) -> bool:
        """Return True when P95 latency is within the target."""
        return self.p95_ms <= self.target_ms

    @property
    def sample_count(self) -> int:
        with self._lock:
            return len(self._samples)

    def reset(self) -> None:
        """Clear all recorded samples. Thread-safe."""
        with self._lock:
            self._samples.clear()

    def summary(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary dict."""
        s = self._sorted_copy()
        n = len(s)
        return {
            "name": self.name,
            "target_ms": self.target_ms,
            "count": n,
            "mean_ms": round(sum(s) / n, 2) if n else 0.0,
            "p50_ms": round(self._percentile(s, 50), 2),
            "p95_ms": round(self._percentile(s, 95), 2),
            "p99_ms": round(self._percentile(s, 99), 2),
            "min_ms": round(s[0], 2) if s else 0.0,
            "max_ms": round(s[-1], 2) if s else 0.0,
            "meets_target": self.meets_target,
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
        "wake_word": 50.0,   # ≤50ms  (core.performance.PipelineStage.WAKE_WORD)
        "stt": 120.0,        # ≤120ms/s of audio
        "intent": 50.0,      # ≤50ms
        "llm": 300.0,        # ≤300ms first token
        "tts": 200.0,        # ≤200ms
        "end_to_end": 2500.0,  # ≤2500ms
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
        def __init__(self, stats: LatencyAccumulator) -> None:
            self._stats = stats
            self._start = 0.0

        def __enter__(self) -> PerformanceOptimizer._Timer:
            self._start = time.perf_counter()
            return self

        def __exit__(self, *_: object) -> None:
            elapsed_ms = (time.perf_counter() - self._start) * 1000
            self._stats.record(elapsed_ms)

    def measure(self, stage: str) -> PerformanceOptimizer._Timer:
        """Context manager to measure latency for a pipeline stage.

        Args:
            stage: One of wake_word, stt, intent, llm, tts, end_to_end.
                   Unknown names are tracked with no target (inf).

        Returns:
            Context manager that records elapsed time on exit.

        """
        if stage not in self._stats:
            self._stats[stage] = LatencyAccumulator(name=stage, target_ms=float("inf"))
        return self._Timer(self._stats[stage])

    # ------------------------------------------------------------------
    # LLM response caching (reduces redundant API calls)
    # ------------------------------------------------------------------

    def get_cached_response(self, prompt_key: str) -> str | None:
        """Return a cached LLM response or None on cache miss."""
        with self._cache_lock:
            result = self._response_cache.get(prompt_key)
            if result is not None:
                self._cache_hits += 1
            else:
                self._cache_misses += 1
            return result

    def cache_response(self, prompt_key: str, response: str) -> None:
        """Cache an LLM response. Evicts oldest entry when cache exceeds 512 entries."""
        with self._cache_lock:
            if len(self._response_cache) >= 512:  # noqa: PLR2004
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
            name
            for name, stats in self._stats.items()
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
                "  %s %s: mean=%.1fms p95=%.1fms target=%.0fms (n=%d)",
                status,
                name,
                summary["mean_ms"],
                summary["p95_ms"],
                summary["target_ms"],
                summary["count"],
            )
        if bottlenecks:
            logger.warning("Bottlenecks detected: %s", bottlenecks)
        logger.info(
            "LLM cache: hits=%d misses=%d rate=%.1f%%",
            self._cache_hits,
            self._cache_misses,
            self.cache_hit_rate * 100,
        )

    def reset(self) -> None:
        """Reset all statistics and clear the response cache."""
        for stats in self._stats.values():
            stats.reset()  # MED-002 fix: uses public API, not private attrs
        with self._cache_lock:
            self._response_cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0
