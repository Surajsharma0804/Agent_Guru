"""Performance Monitor for the LLM Runtime.

Tracks latency, token usage, cost, and reliability per model/provider.
Emits warnings for slow responses and reliability issues.

Performance:
    Time Complexity: O(1) amortized for record_request() (BUG FIX, Round 26:
        this used to run a full O(n log n) sort on every single call -- see
        the comment on _compute_latency_stats() and record_request() below).
        O(n log n) for get_metrics()/report_to_self_improvement(), where
        n <= _MAX_LATENCY_SAMPLES -- paid only when a report is actually
        requested, not on every write.
    Space Complexity: O(p * 1000) where p = number of model/provider pairs

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Agent_Guru.llm.models import ModelProvider

logger = logging.getLogger(__name__)

_MAX_LATENCY_SAMPLES = 1000
_FAILURE_WINDOW_S = 60.0


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics for a model/provider pair."""

    model: str
    provider: ModelProvider
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    success_rate: float = 1.0
    # BUG-003: use UTC-aware datetime factory
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class PerformanceMonitor:
    """Monitors and tracks LLM request performance metrics.

    Features:
    - Per-model/provider latency tracking (p95, p99)
    - Token usage and cost aggregation
    - Success/failure rate monitoring
    - Slow response and reliability warnings
    - Metrics reporting for Self-Improvement Engine integration

    Example:
        >>> monitor = PerformanceMonitor()
        >>> await monitor.record_request(
        ...     model="gpt-3.5-turbo",
        ...     provider=ModelProvider.OPENAI,
        ...     latency_ms=250.0,
        ...     tokens=150,
        ...     cost=0.0003,
        ...     success=True,
        ... )
        >>> metrics = await monitor.get_metrics()

    """

    def __init__(
        self,
        slow_threshold_ms: float = 5000.0,
        failure_threshold: int = 5,
    ) -> None:
        self.slow_threshold_ms = slow_threshold_ms
        self.failure_threshold = failure_threshold

        self._metrics: dict[str, PerformanceMetrics] = {}
        # BUG FIX (Round 26): was `defaultdict(list)` with the cap enforced by
        # manually re-slicing `history[-_MAX_LATENCY_SAMPLES:]` every time the
        # list grew past the cap -- which, once the cap is reached, is EVERY
        # subsequent call (one append immediately re-exceeds the cap right
        # after each trim), so that was an O(_MAX_LATENCY_SAMPLES) list copy
        # on effectively every record_request() once a model/provider pair
        # was warmed up. deque(maxlen=...) evicts the oldest sample in O(1)
        # as part of the append itself.
        self._latency_history: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=_MAX_LATENCY_SAMPLES),
        )
        self._recent_failures: dict[str, list[datetime]] = defaultdict(list)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def record_request(
        self,
        model: str,
        provider: ModelProvider,
        latency_ms: float,
        tokens: int,
        cost: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record metrics for a completed (or failed) request.

        Args:
            model: Model name.
            provider: Provider enum value.
            latency_ms: End-to-end latency in milliseconds.
            tokens: Total tokens used.
            cost: Estimated cost in USD.
            success: Whether the request succeeded.
            error: Optional error message for failed requests.

        """
        async with self._lock:
            key = f"{provider.value}:{model}"

            if key not in self._metrics:
                self._metrics[key] = PerformanceMetrics(model=model, provider=provider)

            m = self._metrics[key]
            m.total_requests += 1

            if success:
                m.successful_requests += 1
            else:
                m.failed_requests += 1
                # BUG-017: single `now` avoids two datetime.now() calls with a
                # clock-drift window between append and filter.
                now = datetime.now(tz=UTC)
                self._recent_failures[key].append(now)
                cutoff = now - timedelta(seconds=_FAILURE_WINDOW_S)
                self._recent_failures[key] = [t for t in self._recent_failures[key] if t >= cutoff]

            # Latency history — O(1) amortized append; deque(maxlen=...)
            # evicts the oldest sample automatically once at capacity.
            self._latency_history[key].append(latency_ms)

            # BUG FIX (Round 26): the O(n log n) sort + percentile calc that
            # used to run right here, on every single record_request() call
            # (i.e. on the hot path for every LLM completion, while holding
            # the lock that serializes ALL record_request()/get_metrics()
            # calls across every model/provider pair), has been moved to
            # get_metrics()/_compute_latency_stats() — computed lazily, only
            # when a report is actually requested. Reports are requested far
            # less often than completions happen, and this mirrors the
            # pattern this codebase already uses elsewhere for the identical
            # problem (core/performance_optimizer.py's LatencyAccumulator,
            # avatar/performance.py) rather than eagerly recomputing
            # statistics nobody may read before the next write overwrites
            # them anyway.

            # Accumulate tokens and cost
            m.total_tokens += tokens
            m.total_cost += cost

            # Success rate
            m.success_rate = m.successful_requests / m.total_requests
            # BUG-003: use UTC-aware timestamp
            m.last_updated = datetime.now(tz=UTC)

            # BUG-023: capture recent_count INSIDE the lock so it is consistent
            # with the just-updated list (previously read outside, causing a race).
            recent_count = len(self._recent_failures.get(key, []))

        # Emit warnings outside the lock to avoid blocking
        if latency_ms > self.slow_threshold_ms:
            await self._emit_slow_warning(model, provider, latency_ms)

        if recent_count >= self.failure_threshold:
            await self._emit_reliability_warning(model, provider, recent_count)

    async def get_metrics(
        self,
        model: str | None = None,
        provider: ModelProvider | None = None,
    ) -> dict[str, PerformanceMetrics]:
        """Return performance metrics, optionally filtered.

        Latency statistics (average_latency_ms/p95_latency_ms/p99_latency_ms)
        are computed here, lazily, from the raw sample history rather than
        being read off a pre-computed field — see the Round 26 fix note on
        record_request() and _compute_latency_stats().

        Args:
            model: Optional model name filter.
            provider: Optional provider filter.

        Returns:
            Dict mapping "provider:model" keys to PerformanceMetrics.

        """
        async with self._lock:
            if model and provider:
                key = f"{provider.value}:{model}"
                return {key: self._snapshot(key)} if key in self._metrics else {}
            if model:
                keys = [k for k, v in self._metrics.items() if v.model == model]
            elif provider:
                keys = [k for k, v in self._metrics.items() if v.provider == provider]
            else:
                keys = list(self._metrics.keys())
            return {k: self._snapshot(k) for k in keys}

    def _snapshot(self, key: str) -> PerformanceMetrics:
        """Return a PerformanceMetrics copy for `key` with fresh latency stats.

        Must be called while holding self._lock (both callers already do).
        Returns a copy (dataclasses.replace) rather than the stored instance
        so the object handed to a caller is a self-consistent point-in-time
        snapshot, and so the stored self._metrics[key] instance's latency
        fields are never mutated outside of this read path.
        """
        m = self._metrics[key]
        mean, p95, p99 = self._compute_latency_stats(self._latency_history.get(key, ()))
        return dataclasses.replace(
            m,
            average_latency_ms=mean,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
        )

    @staticmethod
    def _compute_latency_stats(history: deque[float] | tuple[float, ...]) -> tuple[float, float, float]:
        """Compute (mean_ms, p95_ms, p99_ms) from a latency sample collection.

        Time Complexity: O(n log n) for the sort, n = len(history) <= _MAX_LATENCY_SAMPLES.
        Called only from the (comparatively rare) read path — see the Round 26
        fix note on record_request().
        """
        if not history:
            return 0.0, 0.0, 0.0
        sorted_latencies = sorted(history)
        n = len(sorted_latencies)
        mean = sum(sorted_latencies) / n
        p95_idx = min(int(n * 0.95), n - 1)
        p99_idx = min(int(n * 0.99), n - 1)
        return mean, sorted_latencies[p95_idx], sorted_latencies[p99_idx]

    async def report_to_self_improvement(self) -> dict[str, Any]:
        """Format metrics for the Self-Improvement Engine.

        Returns:
            Dict with timestamp and per-model metrics summary.

        """
        metrics = await self.get_metrics()
        return {
            # BUG-003: use UTC-aware timestamp
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "metrics": {
                key: {
                    "model": m.model,
                    "provider": m.provider.value,
                    "success_rate": m.success_rate,
                    "average_latency_ms": m.average_latency_ms,
                    "p95_latency_ms": m.p95_latency_ms,
                    "total_cost": m.total_cost,
                    "total_tokens": m.total_tokens,
                    "total_requests": m.total_requests,
                }
                for key, m in metrics.items()
            },
        }

    # ------------------------------------------------------------------
    # Warnings
    # ------------------------------------------------------------------

    async def _emit_slow_warning(
        self,
        model: str,
        provider: ModelProvider,
        latency_ms: float,
    ) -> None:
        logger.warning(
            "SLOW RESPONSE: %s/%s took %.1fms (threshold: %.1fms)",
            provider.value,
            model,
            latency_ms,
            self.slow_threshold_ms,
        )

    async def _emit_reliability_warning(
        self,
        model: str,
        provider: ModelProvider,
        failure_count: int,
    ) -> None:
        logger.warning(
            "RELIABILITY WARNING: %s/%s had %d failures in the last %ds",
            provider.value,
            model,
            failure_count,
            int(_FAILURE_WINDOW_S),
        )
