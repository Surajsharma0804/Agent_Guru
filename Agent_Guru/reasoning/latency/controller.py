"""
Latency Controller for Reasoning Pipeline.

This module implements the main latency controller that orchestrates stage timing,
budget enforcement, timeout handling, and metrics tracking for the reasoning pipeline.

Performance Characteristics:
    - Time Complexity: O(1) for all operations
    - Space Complexity: O(n) where n is history size
    - Overhead: <1ms per stage

Design Principles:
    - High-resolution timing (nanosecond precision)
    - Per-stage budget enforcement
    - Timeout warnings and hard timeouts
    - Comprehensive metrics tracking
    - Zero-overhead when disabled

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generator, Optional

import structlog

from Agent_Guru.reasoning.latency.tracker import (
    DegradedModeManager,
    LATENCY_BUDGETS,
    LatencyEnforcer,
    LatencyTracker,
    PipelineStage,
    StageMetrics,
    get_degraded_mode_manager,
    get_latency_enforcer,
    get_latency_tracker,
)

logger = structlog.get_logger(__name__)


@dataclass
class StageTimer:
    """Timer for a pipeline stage.
    
    Attributes:
        stage: Pipeline stage being timed
        start_time: High-resolution start time
        budget_ms: Latency budget in milliseconds
        max_budget_ms: Maximum latency budget in milliseconds
        metrics: Stage metrics object
        warned: Whether warning has been issued
    """
    
    stage: PipelineStage
    start_time: float
    budget_ms: float
    max_budget_ms: float
    metrics: StageMetrics
    warned: bool = False
    
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds.
        
        Returns:
            Elapsed time in milliseconds
        """
        return (time.perf_counter() - self.start_time) * 1000
    
    def remaining_ms(self) -> float:
        """Get remaining budget in milliseconds.
        
        Returns:
            Remaining budget in milliseconds (negative if exceeded)
        """
        return self.budget_ms - self.elapsed_ms()
    
    def is_over_budget(self) -> bool:
        """Check if stage is over target budget.
        
        Returns:
            True if over budget
        """
        return self.elapsed_ms() > self.budget_ms
    
    def is_over_max_budget(self) -> bool:
        """Check if stage is over maximum budget.
        
        Returns:
            True if over maximum budget
        """
        return self.elapsed_ms() > self.max_budget_ms
    
    def budget_utilization(self) -> float:
        """Get budget utilization percentage.
        
        Returns:
            Budget utilization (0.0-1.0+)
        """
        return self.elapsed_ms() / self.budget_ms if self.budget_ms > 0 else 0.0


class LatencyController:
    """Main latency controller for reasoning pipeline.
    
    This class provides the primary interface for latency management in the
    reasoning pipeline. It orchestrates timing, budget enforcement, warnings,
    and metrics tracking.
    
    Time Complexity:
        - start_stage: O(1)
        - check_timeout: O(1)
        - end_stage: O(1)
    
    Space Complexity:
        - O(n) where n is history size in tracker
    
    Features:
        - High-resolution timing (perf_counter)
        - Per-stage budget enforcement
        - Timeout warnings at 80% budget
        - Hard timeouts at maximum budget
        - Comprehensive metrics tracking
        - Context manager support
        - Degraded mode management
    
    Example:
        >>> controller = LatencyController()
        >>> timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        >>> # ... do work ...
        >>> controller.end_stage(timer)
        
        >>> # Or use context manager
        >>> with controller.stage_context(PipelineStage.INPUT_NORMALIZATION):
        ...     # ... do work ...
    """
    
    # Warning threshold (80% of budget)
    WARNING_THRESHOLD = 0.8
    
    def __init__(
        self,
        tracker: Optional[LatencyTracker] = None,
        enforcer: Optional[LatencyEnforcer] = None,
        degraded_manager: Optional[DegradedModeManager] = None,
        enable_warnings: bool = True,
        enable_hard_timeouts: bool = True,
    ) -> None:
        """Initialize LatencyController.
        
        Args:
            tracker: Optional LatencyTracker instance (uses global if None)
            enforcer: Optional LatencyEnforcer instance (uses global if None)
            degraded_manager: Optional DegradedModeManager instance (uses global if None)
            enable_warnings: Whether to enable timeout warnings
            enable_hard_timeouts: Whether to enable hard timeouts
        """
        self.tracker = tracker or get_latency_tracker()
        self.enforcer = enforcer or get_latency_enforcer()
        self.degraded_manager = degraded_manager or get_degraded_mode_manager()
        self.enable_warnings = enable_warnings
        self.enable_hard_timeouts = enable_hard_timeouts
    
    def start_stage(self, stage: PipelineStage) -> StageTimer:
        """Start timing a pipeline stage.
        
        Time Complexity: O(1)
        
        This method starts high-resolution timing for a pipeline stage and
        initializes budget tracking.
        
        Args:
            stage: Pipeline stage to time
        
        Returns:
            StageTimer for tracking
        
        Example:
            >>> controller = LatencyController()
            >>> timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        """
        # Get budget for stage
        budget = LATENCY_BUDGETS.get(stage, {})
        target_ms = budget.get("target", 1000)
        max_ms = budget.get("maximum", 5000)
        
        # Start tracking
        metrics = self.tracker.start_stage(stage)
        
        # Create timer
        timer = StageTimer(
            stage=stage,
            start_time=time.perf_counter(),
            budget_ms=target_ms,
            max_budget_ms=max_ms,
            metrics=metrics,
        )
        
        logger.debug(
            "stage_started",
            stage=stage.value,
            budget_ms=target_ms,
            max_budget_ms=max_ms,
            timestamp=datetime.now().isoformat(),
        )
        
        return timer
    
    def check_timeout(self, timer: StageTimer) -> bool:
        """Check if stage has exceeded timeout.
        
        Time Complexity: O(1)
        
        This method checks if the stage has exceeded its budget and issues
        warnings or raises timeouts as appropriate.
        
        Args:
            timer: Stage timer
        
        Returns:
            True if stage should be halted (hard timeout)
        
        Example:
            >>> if controller.check_timeout(timer):
            ...     # Handle timeout
            ...     break
        """
        elapsed_ms = timer.elapsed_ms()
        
        # Check for warning threshold (80% of budget)
        if (
            self.enable_warnings
            and not timer.warned
            and elapsed_ms > timer.budget_ms * self.WARNING_THRESHOLD
        ):
            timer.warned = True
            logger.warning(
                "stage_approaching_timeout",
                stage=timer.stage.value,
                elapsed_ms=elapsed_ms,
                budget_ms=timer.budget_ms,
                utilization=timer.budget_utilization(),
                timestamp=datetime.now().isoformat(),
            )
        
        # Check for hard timeout (maximum budget)
        if self.enable_hard_timeouts and timer.is_over_max_budget():
            logger.error(
                "stage_hard_timeout",
                stage=timer.stage.value,
                elapsed_ms=elapsed_ms,
                max_budget_ms=timer.max_budget_ms,
                timestamp=datetime.now().isoformat(),
            )
            return True
        
        return False
    
    def end_stage(
        self,
        timer: StageTimer,
        error: Optional[str] = None,
    ) -> StageMetrics:
        """End timing for a pipeline stage.
        
        Time Complexity: O(1)
        
        This method completes timing for a stage, records metrics, and checks
        for budget violations.
        
        Args:
            timer: Stage timer
            error: Optional error message
        
        Returns:
            Completed stage metrics
        
        Example:
            >>> metrics = controller.end_stage(timer)
            >>> print(f"Duration: {metrics.duration_ms:.1f}ms")
        """
        # Check if timed out
        timed_out = timer.is_over_max_budget()
        
        # Check if degraded
        degraded = self.degraded_manager.is_degraded(timer.stage)
        
        # End tracking
        metrics = self.tracker.end_stage(
            timer.metrics,
            timeout=timed_out,
            degraded=degraded,
            error=error,
        )
        
        # Check budget
        budget_check = self.tracker.check_budget(metrics)
        
        # Log completion
        if budget_check["met_target"]:
            logger.info(
                "stage_completed_on_budget",
                stage=timer.stage.value,
                duration_ms=metrics.duration_ms,
                budget_ms=timer.budget_ms,
                utilization=timer.budget_utilization(),
                timestamp=datetime.now().isoformat(),
            )
        else:
            logger.warning(
                "stage_completed_over_budget",
                stage=timer.stage.value,
                duration_ms=metrics.duration_ms,
                budget_ms=timer.budget_ms,
                exceeded_by_ms=budget_check["exceeded_by_ms"],
                exceeded_by_percent=budget_check["exceeded_by_percent"],
                timestamp=datetime.now().isoformat(),
            )
        
        # Check if should activate degraded mode
        if self.degraded_manager.should_degrade(timer.stage, metrics):
            self.degraded_manager.activate_degraded_mode(timer.stage)
            logger.warning(
                "degraded_mode_activated",
                stage=timer.stage.value,
                duration_ms=metrics.duration_ms,
                max_budget_ms=timer.max_budget_ms,
                timestamp=datetime.now().isoformat(),
            )
        
        return metrics
    
    @contextmanager
    def stage_context(
        self, stage: PipelineStage
    ) -> Generator[StageTimer, None, None]:
        """Context manager for stage timing.
        
        This provides a convenient way to time a stage using a with statement.
        The stage is automatically started and ended.
        
        Args:
            stage: Pipeline stage
        
        Yields:
            StageTimer for the stage
        
        Example:
            >>> with controller.stage_context(PipelineStage.INPUT_NORMALIZATION) as timer:
            ...     # ... do work ...
            ...     if controller.check_timeout(timer):
            ...         break
        """
        timer = self.start_stage(stage)
        error = None
        
        try:
            yield timer
        except Exception as e:
            error = str(e)
            raise
        finally:
            self.end_stage(timer, error=error)
    
    def get_stage_statistics(self, stage: PipelineStage) -> Optional[Any]:
        """Get statistics for a stage.
        
        Args:
            stage: Pipeline stage
        
        Returns:
            Stage statistics or None if no data
        """
        return self.tracker.get_statistics(stage)
    
    def get_all_statistics(self) -> dict[PipelineStage, Any]:
        """Get statistics for all stages.
        
        Returns:
            Dictionary of stage statistics
        """
        return self.tracker.get_all_statistics()
    
    def is_degraded(self, stage: PipelineStage) -> bool:
        """Check if stage is in degraded mode.
        
        Args:
            stage: Pipeline stage
        
        Returns:
            True if degraded
        """
        return self.degraded_manager.is_degraded(stage)
    
    def get_degraded_stages(self) -> list[PipelineStage]:
        """Get list of degraded stages.
        
        Returns:
            List of degraded stages
        """
        return self.degraded_manager.get_degraded_stages()
    
    def reset_degraded_mode(self, stage: Optional[PipelineStage] = None) -> None:
        """Reset degraded mode for a stage or all stages.
        
        Args:
            stage: Optional stage to reset (resets all if None)
        """
        if stage is None:
            # Reset all stages
            for s in self.degraded_manager.get_degraded_stages():
                self.degraded_manager.deactivate_degraded_mode(s)
        else:
            self.degraded_manager.deactivate_degraded_mode(stage)


# Global instance
_global_controller: Optional[LatencyController] = None


def get_latency_controller() -> LatencyController:
    """Get the global latency controller instance.
    
    Returns:
        Global LatencyController instance
    """
    global _global_controller
    if _global_controller is None:
        _global_controller = LatencyController()
    return _global_controller
