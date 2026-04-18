"""
Module: Agent_Guru.platform.integration.self_improvement_client
Purpose: Self-Improvement Engine integration client for performance metrics reporting.

Performance Requirements:
- Time Complexity: O(1) per report
- Latency: <100ms per report (95th percentile)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a platform operation."""

    operation_type: str
    execution_time_ms: float
    success: bool
    resource_usage: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_type": self.operation_type,
            "execution_time_ms": self.execution_time_ms,
            "success": self.success,
            "resource_usage": self.resource_usage,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ErrorStatistics:
    """Error statistics for reporting to Self-Improvement Engine."""

    error_type: str
    error_count: int
    operation_type: str
    time_window_minutes: int = 60
    sample_messages: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "error_count": self.error_count,
            "operation_type": self.operation_type,
            "time_window_minutes": self.time_window_minutes,
            "sample_messages": self.sample_messages,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ImprovementSuggestion:
    """Improvement suggestion from Self-Improvement Engine."""

    suggestion_id: str
    category: str
    description: str
    priority: str  # "high", "medium", "low"
    estimated_impact: float  # 0.0 - 1.0
    implementation_hints: list[str] = field(default_factory=list)


class SelfImprovementClient:
    """
    Async client for Self-Improvement Engine integration.

    Reports performance metrics, error statistics, and retrieves
    improvement suggestions.

    Example:
        >>> client = SelfImprovementClient(base_url="http://localhost:8083")
        >>> await client.connect()
        >>> metrics = PerformanceMetrics("file_op", 45.2, True)
        >>> await client.report_performance_metrics(metrics)
        >>> suggestions = await client.get_improvement_suggestions()
        >>> await client.disconnect()
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8083",
        timeout: float = 30.0,
        max_retries: int = 3,
        batch_size: int = 50,
    ) -> None:
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout}")
        if max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {max_retries}")
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.batch_size = batch_size
        self._session: Optional[aiohttp.ClientSession] = None
        self._metrics_reported = 0
        self._errors_reported = 0
        self._pending_metrics: list[PerformanceMetrics] = []

    async def connect(self) -> None:
        """Establish connection to Self-Improvement Engine."""
        if self._session is not None:
            raise RuntimeError("Client already connected")
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        logger.info("Connected to Self-Improvement Engine at %s", self.base_url)

    async def disconnect(self) -> None:
        """Disconnect, flushing any pending metrics first."""
        if self._pending_metrics:
            await self._flush_metrics()
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("Disconnected from Self-Improvement Engine")

    async def report_performance_metrics(
        self, metrics: PerformanceMetrics
    ) -> bool:
        """
        Report performance metrics to Self-Improvement Engine.

        Batches metrics for efficiency; flushes when batch is full.

        Args:
            metrics: Performance metrics to report

        Returns:
            True if queued/sent successfully
        """
        if self._session is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        self._pending_metrics.append(metrics)

        if len(self._pending_metrics) >= self.batch_size:
            return await self._flush_metrics()

        return True

    async def _flush_metrics(self) -> bool:
        """Flush pending metrics to Self-Improvement Engine."""
        if not self._pending_metrics or self._session is None:
            return True

        batch = self._pending_metrics[:]
        self._pending_metrics.clear()

        payload = {"metrics": [m.to_dict() for m in batch]}

        for attempt in range(self.max_retries):
            try:
                url = f"{self.base_url}/api/v1/improvement/metrics"
                async with self._session.post(url, json=payload) as resp:
                    if resp.status in (200, 201):
                        self._metrics_reported += len(batch)
                        logger.debug("Flushed %s metrics", len(batch))
                        return True
                    logger.warning("Metrics flush returned %s", resp.status)
            except Exception as e:
                logger.warning("Metrics flush attempt %s failed: %s", attempt + 1, e)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))

        logger.error("Failed to flush %s metrics", len(batch))
        return False

    async def report_error_statistics(
        self, error_stats: ErrorStatistics
    ) -> bool:
        """
        Report error statistics to Self-Improvement Engine.

        Args:
            error_stats: Error statistics to report

        Returns:
            True if reported successfully
        """
        if self._session is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        for attempt in range(self.max_retries):
            try:
                url = f"{self.base_url}/api/v1/improvement/errors"
                async with self._session.post(
                    url, json=error_stats.to_dict()
                ) as resp:
                    if resp.status in (200, 201):
                        self._errors_reported += 1
                        logger.debug(
                            f"Reported error stats: {error_stats.error_type}"
                        )
                        return True
                    logger.warning("Error stats returned %s", resp.status)
            except Exception as e:
                logger.warning("Error stats attempt %s failed: %s", attempt + 1, e)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))

        logger.error("Failed to report error stats: %s", error_stats.error_type)
        return False

    async def get_improvement_suggestions(
        self, category: Optional[str] = None, limit: int = 10
    ) -> list[ImprovementSuggestion]:
        """
        Retrieve improvement suggestions from Self-Improvement Engine.

        Args:
            category: Filter by category (optional)
            limit: Maximum suggestions to return

        Returns:
            List of improvement suggestions
        """
        if self._session is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        params: dict[str, Any] = {"limit": limit}
        if category:
            params["category"] = category

        try:
            url = f"{self.base_url}/api/v1/improvement/suggestions"
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    body = await resp.json()
                    return [
                        ImprovementSuggestion(
                            suggestion_id=s.get("suggestion_id", ""),
                            category=s.get("category", ""),
                            description=s.get("description", ""),
                            priority=s.get("priority", "low"),
                            estimated_impact=s.get("estimated_impact", 0.0),
                            implementation_hints=s.get("implementation_hints", []),
                        )
                        for s in body.get("suggestions", [])
                    ]
                logger.warning("Suggestions returned %s", resp.status)
                return []
        except Exception as e:
            logger.error("Failed to get suggestions: %s", e)
            return []

    def get_statistics(self) -> dict[str, Any]:
        """Get client statistics."""
        return {
            "metrics_reported": self._metrics_reported,
            "errors_reported": self._errors_reported,
            "pending_metrics": len(self._pending_metrics),
        }

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
