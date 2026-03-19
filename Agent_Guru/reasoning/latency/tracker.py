"""
Latency tracking and budget enforcement for pipeline stages.

Provides high-resolution timing, budget enforcement, and monitoring
for all stages of the reasoning pipeline.
"""

import asyncio
import time
import structlog
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional
import statistics

logger = structlog.get_logger(__name__)


class PipelineStage(str, Enum):
    """Pipeline stage identifiers."""

    INPUT_NORMALIZATION = "input_normalization"
    INTENT_DETECTION = "intent_detection"
    MEMORY_RETRIEVAL = "memory_retrieval"
    REASONING = "reasoning"
    TOOL_SELECTION = "tool_selection"
    SAFETY_VALIDATION = "safety_validation"
    EXECUTION = "execution"
    RESPONSE_GENERATION = "response_generation"


# Latency budget per stage (in milliseconds)
LATENCY_BUDGETS = {
    PipelineStage.INPUT_NORMALIZATION: {
        "target": 50,
        "maximum": 100,
    },
    PipelineStage.INTENT_DETECTION: {
        "target": 200,
        "maximum": 500,
    },
    PipelineStage.MEMORY_RETRIEVAL: {
        "target": 100,
        "maximum": 200,
    },
    PipelineStage.REASONING: {
        "target": 400,
        "maximum": 1000,
    },
    PipelineStage.TOOL_SELECTION: {
        "target": 50,
        "maximum": 100,
    },
    PipelineStage.SAFETY_VALIDATION: {
        "target": 50,
        "maximum": 100,
    },
    PipelineStage.EXECUTION: {
        "target": 500,
        "maximum": 3000,
    },
    PipelineStage.RESPONSE_GENERATION: {
        "target": 100,
        "maximum": 300,
    },
}


@dataclass
class StageMetrics:
    """Metrics for a pipeline stage."""

    stage: PipelineStage
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    timeout: bool = False
    degraded: bool = False
    error: Optional[str] = None


@dataclass
class LatencyStatistics:
    """Latency statistics for a stage."""

    stage: PipelineStage
    count: int
    p50: float
    p95: float
    p99: float
    mean: float
    min: float
    max: float
    timeout_count: int
    timeout_rate: float
    degraded_count: int
    degraded_rate: float


class LatencyTracker:
    """Tracker for pipeline stage latencies."""

    def __init__(self, max_history: int = 10000):
        """Initialize latency tracker.

        Args:
            max_history: Maximum number of measurements to keep per stage
        """
        self.max_history = max_history
        self._measurements: Dict[PipelineStage, Deque[float]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        self._timeout_counts: Dict[PipelineStage, int] = defaultdict(int)
        self._degraded_counts: Dict[PipelineStage, int] = defaultdict(int)
        self._total_counts: Dict[PipelineStage, int] = defaultdict(int)

    def start_stage(self, stage: PipelineStage) -> StageMetrics:
        """Start tracking a pipeline stage.

        Args:
            stage: Pipeline stage

        Returns:
            Stage metrics object
        """
        return StageMetrics(
            stage=stage,
            start_time=time.perf_counter(),
        )

    def end_stage(
        self,
        metrics: StageMetrics,
        timeout: bool = False,
        degraded: bool = False,
        error: Optional[str] = None,
    ) -> StageMetrics:
        """End tracking a pipeline stage.

        Args:
            metrics: Stage metrics object
            timeout: Whether stage timed out
            degraded: Whether stage ran in degraded mode
            error: Error message if any

        Returns:
            Updated stage metrics
        """
        metrics.end_time = time.perf_counter()
        metrics.duration_ms = (metrics.end_time - metrics.start_time) * 1000
        metrics.timeout = timeout
        metrics.degraded = degraded
        metrics.error = error

        # Record measurement
        self._measurements[metrics.stage].append(metrics.duration_ms)
        self._total_counts[metrics.stage] += 1

        if timeout:
            self._timeout_counts[metrics.stage] += 1

        if degraded:
            self._degraded_counts[metrics.stage] += 1

        # Log metrics for analysis
        logger.info(
            "stage_completed",
            stage=metrics.stage.value,
            duration_ms=metrics.duration_ms,
            timeout=timeout,
            degraded=degraded,
            error=error,
            timestamp=datetime.now().isoformat(),
        )

        return metrics

    def get_statistics(self, stage: PipelineStage) -> Optional[LatencyStatistics]:
        """Get latency statistics for a stage.

        Args:
            stage: Pipeline stage

        Returns:
            Latency statistics or None if no data
        """
        measurements = list(self._measurements[stage])
        if not measurements:
            return None

        total_count = self._total_counts[stage]
        timeout_count = self._timeout_counts[stage]
        degraded_count = self._degraded_counts[stage]

        # Calculate percentiles
        sorted_measurements = sorted(measurements)
        count = len(sorted_measurements)

        p50_idx = int(count * 0.50)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)

        return LatencyStatistics(
            stage=stage,
            count=count,
            p50=sorted_measurements[p50_idx] if count > 0 else 0.0,
            p95=sorted_measurements[p95_idx] if count > 0 else 0.0,
            p99=sorted_measurements[p99_idx] if count > 0 else 0.0,
            mean=statistics.mean(measurements),
            min=min(measurements),
            max=max(measurements),
            timeout_count=timeout_count,
            timeout_rate=timeout_count / total_count if total_count > 0 else 0.0,
            degraded_count=degraded_count,
            degraded_rate=degraded_count / total_count if total_count > 0 else 0.0,
        )

    def get_all_statistics(self) -> Dict[PipelineStage, LatencyStatistics]:
        """Get statistics for all stages.

        Returns:
            Dictionary of stage statistics
        """
        stats = {}
        for stage in PipelineStage:
            stage_stats = self.get_statistics(stage)
            if stage_stats:
                stats[stage] = stage_stats
        return stats

    def check_budget(self, metrics: StageMetrics) -> Dict[str, Any]:
        """Check if stage met its latency budget.

        Args:
            metrics: Stage metrics

        Returns:
            Budget check result
        """
        if metrics.duration_ms is None:
            return {
                "met_target": False,
                "met_maximum": False,
                "exceeded_by_ms": 0,
                "exceeded_by_percent": 0,
            }

        budget = LATENCY_BUDGETS.get(metrics.stage, {})
        target = budget.get("target", 0)
        maximum = budget.get("maximum", 0)

        met_target = metrics.duration_ms <= target
        met_maximum = metrics.duration_ms <= maximum

        exceeded_by_ms = max(0, metrics.duration_ms - target)
        exceeded_by_percent = (
            (exceeded_by_ms / target * 100) if target > 0 else 0
        )

        return {
            "met_target": met_target,
            "met_maximum": met_maximum,
            "exceeded_by_ms": exceeded_by_ms,
            "exceeded_by_percent": exceeded_by_percent,
            "target_ms": target,
            "maximum_ms": maximum,
            "actual_ms": metrics.duration_ms,
        }


class LatencyEnforcer:
    """Enforcer for latency budgets with timeout support."""

    def __init__(self, tracker: LatencyTracker):
        """Initialize latency enforcer.

        Args:
            tracker: Latency tracker instance
        """
        self.tracker = tracker

    async def execute_with_budget(
        self,
        stage: PipelineStage,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, StageMetrics]:
        """Execute a function with latency budget enforcement.

        Args:
            stage: Pipeline stage
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Tuple of (result, metrics)

        Raises:
            asyncio.TimeoutError: If execution exceeds maximum budget
        """
        metrics = self.tracker.start_stage(stage)
        budget = LATENCY_BUDGETS.get(stage, {})
        maximum_ms = budget.get("maximum", 5000)
        timeout_seconds = maximum_ms / 1000

        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds,
                )
            else:
                result = func(*args, **kwargs)

            # End tracking
            self.tracker.end_stage(metrics)

            return result, metrics

        except asyncio.TimeoutError:
            # Mark as timeout and log
            self.tracker.end_stage(metrics, timeout=True)
            logger.warning(
                "stage_timeout",
                stage=stage.value,
                maximum_ms=maximum_ms,
                timestamp=datetime.now().isoformat(),
            )
            raise

        except Exception as e:
            # Mark as error and log
            self.tracker.end_stage(metrics, error=str(e))
            logger.error(
                "stage_error",
                stage=stage.value,
                error=str(e),
                timestamp=datetime.now().isoformat(),
            )
            raise


class DegradedModeManager:
    """Manager for degraded mode activation."""

    def __init__(self):
        """Initialize degraded mode manager."""
        self._degraded_stages: set[PipelineStage] = set()
        self._degraded_count = 0

    def should_degrade(
        self, stage: PipelineStage, metrics: StageMetrics
    ) -> bool:
        """Check if stage should enter degraded mode.

        Args:
            stage: Pipeline stage
            metrics: Stage metrics

        Returns:
            True if should degrade
        """
        if metrics.duration_ms is None:
            return False

        budget = LATENCY_BUDGETS.get(stage, {})
        maximum = budget.get("maximum", float("inf"))

        # Degrade if exceeded maximum budget
        return metrics.duration_ms > maximum

    def activate_degraded_mode(self, stage: PipelineStage) -> None:
        """Activate degraded mode for a stage.

        Args:
            stage: Pipeline stage
        """
        if stage not in self._degraded_stages:
            self._degraded_stages.add(stage)
            self._degraded_count += 1

    def deactivate_degraded_mode(self, stage: PipelineStage) -> None:
        """Deactivate degraded mode for a stage.

        Args:
            stage: Pipeline stage
        """
        if stage in self._degraded_stages:
            self._degraded_stages.discard(stage)

    def is_degraded(self, stage: PipelineStage) -> bool:
        """Check if stage is in degraded mode.

        Args:
            stage: Pipeline stage

        Returns:
            True if degraded
        """
        return stage in self._degraded_stages

    def get_degraded_stages(self) -> List[PipelineStage]:
        """Get list of degraded stages.

        Returns:
            List of degraded stages
        """
        return list(self._degraded_stages)

    def get_degraded_count(self) -> int:
        """Get total degraded mode activations.

        Returns:
            Degraded count
        """
        return self._degraded_count


# Global instances
_global_tracker: Optional[LatencyTracker] = None
_global_enforcer: Optional[LatencyEnforcer] = None
_global_degraded_manager: Optional[DegradedModeManager] = None


def get_latency_tracker() -> LatencyTracker:
    """Get the global latency tracker instance.

    Returns:
        Global LatencyTracker instance
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = LatencyTracker()
    return _global_tracker


def get_latency_enforcer() -> LatencyEnforcer:
    """Get the global latency enforcer instance.

    Returns:
        Global LatencyEnforcer instance
    """
    global _global_enforcer
    if _global_enforcer is None:
        _global_enforcer = LatencyEnforcer(get_latency_tracker())
    return _global_enforcer


def get_degraded_mode_manager() -> DegradedModeManager:
    """Get the global degraded mode manager instance.

    Returns:
        Global DegradedModeManager instance
    """
    global _global_degraded_manager
    if _global_degraded_manager is None:
        _global_degraded_manager = DegradedModeManager()
    return _global_degraded_manager
