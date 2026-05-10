"""Performance Monitor for the LLM Runtime.

Tracks latency, token usage, cost, and reliability per model/provider.
Emits warnings for slow responses and reliability issues.

Performance:
    Time Complexity: O(log n) for percentile calculation
    Space Complexity: O(p * 1000) where p = number of model/provider pairs

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
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
        self._latency_history: dict[str, list[float]] = defaultdict(list)
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

            # Latency history (capped at _MAX_LATENCY_SAMPLES)
            history = self._latency_history[key]
            history.append(latency_ms)
            if len(history) > _MAX_LATENCY_SAMPLES:
                self._latency_history[key] = history[-_MAX_LATENCY_SAMPLES:]

            # Recalculate latency stats
            sorted_latencies = sorted(self._latency_history[key])
            n = len(sorted_latencies)
            m.average_latency_ms = sum(sorted_latencies) / n
            # Clamp indices to valid range
            p95_idx = min(int(n * 0.95), n - 1)
            p99_idx = min(int(n * 0.99), n - 1)
            m.p95_latency_ms = sorted_latencies[p95_idx]
            m.p99_latency_ms = sorted_latencies[p99_idx]

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

        Args:
            model: Optional model name filter.
            provider: Optional provider filter.

        Returns:
            Dict mapping "provider:model" keys to PerformanceMetrics.

        """
        async with self._lock:
            if model and provider:
                key = f"{provider.value}:{model}"
                return {key: self._metrics[key]} if key in self._metrics else {}
            if model:
                return {k: v for k, v in self._metrics.items() if v.model == model}
            if provider:
                return {k: v for k, v in self._metrics.items() if v.provider == provider}
            return dict(self._metrics)

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
