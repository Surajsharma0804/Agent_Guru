"""
Tests for Latency Controller.

Coverage Target: >80% (enforced by CI/CD)
"""

import pytest
import time

from Agent_Guru.reasoning.latency.controller import (
    LatencyController,
    StageTimer,
    get_latency_controller,
)
from Agent_Guru.reasoning.latency.tracker import (
    PipelineStage,
    LatencyTracker,
    DegradedModeManager,
)


class TestLatencyController:
    """Unit tests for LatencyController."""
    
    def test_initialization(self):
        """Test controller initialization."""
        controller = LatencyController()
        
        assert controller.tracker is not None  # nosec B101
        assert controller.enforcer is not None  # nosec B101
        assert controller.degraded_manager is not None  # nosec B101
        assert controller.enable_warnings is True  # nosec B101
        assert controller.enable_hard_timeouts is True  # nosec B101
    
    def test_initialization_with_custom_components(self):
        """Test controller initialization with custom components."""
        tracker = LatencyTracker()
        degraded_manager = DegradedModeManager()
        
        controller = LatencyController(
            tracker=tracker,
            degraded_manager=degraded_manager,
            enable_warnings=False,
            enable_hard_timeouts=False,
        )
        
        assert controller.tracker is tracker  # nosec B101
        assert controller.degraded_manager is degraded_manager  # nosec B101
        assert controller.enable_warnings is False  # nosec B101
        assert controller.enable_hard_timeouts is False  # nosec B101
    
    def test_start_stage(self):
        """Test starting a stage."""
        controller = LatencyController()
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        assert isinstance(timer, StageTimer)  # nosec B101
        assert timer.stage == PipelineStage.INPUT_NORMALIZATION  # nosec B101
        assert timer.start_time > 0  # nosec B101
        assert timer.budget_ms > 0  # nosec B101
        assert timer.max_budget_ms > 0  # nosec B101
        assert timer.warned is False  # nosec B101
    
    def test_end_stage(self):
        """Test ending a stage."""
        controller = LatencyController()
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        # Simulate some work
        time.sleep(0.01)
        
        metrics = controller.end_stage(timer)
        
        assert metrics.duration_ms is not None  # nosec B101
        assert metrics.duration_ms > 0  # nosec B101
        assert metrics.end_time is not None  # nosec B101
    
    def test_end_stage_with_error(self):
        """Test ending a stage with error."""
        controller = LatencyController()
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        metrics = controller.end_stage(timer, error="Test error")
        
        assert metrics.error == "Test error"  # nosec B101
    
    def test_check_timeout_no_timeout(self):
        """Test check_timeout when not timed out."""
        controller = LatencyController()
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        # Should not timeout immediately
        assert controller.check_timeout(timer) is False  # nosec B101
    
    def test_check_timeout_warning(self):
        """Test check_timeout issues warning."""
        controller = LatencyController(enable_warnings=True)
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        # Simulate time passing beyond warning threshold
        timer.start_time = time.perf_counter() - (timer.budget_ms * 0.85 / 1000)
        
        # Should issue warning but not timeout
        assert controller.check_timeout(timer) is False  # nosec B101
        assert timer.warned is True  # nosec B101
    
    def test_check_timeout_hard_timeout(self):
        """Test check_timeout with hard timeout."""
        controller = LatencyController(enable_hard_timeouts=True)
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        # Simulate time passing beyond max budget
        timer.start_time = time.perf_counter() - (timer.max_budget_ms * 1.1 / 1000)
        
        # Should timeout
        assert controller.check_timeout(timer) is True  # nosec B101
    
    def test_check_timeout_disabled(self):
        """Test check_timeout when timeouts disabled."""
        controller = LatencyController(enable_hard_timeouts=False)
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        # Simulate time passing beyond max budget
        timer.start_time = time.perf_counter() - (timer.max_budget_ms * 2 / 1000)
        
        # Should not timeout when disabled
        assert controller.check_timeout(timer) is False  # nosec B101
    
    def test_stage_context_success(self):
        """Test stage context manager with success."""
        controller = LatencyController()
        
        with controller.stage_context(PipelineStage.INPUT_NORMALIZATION) as timer:
            assert isinstance(timer, StageTimer)  # nosec B101
            time.sleep(0.01)
        
        # Should complete without error
        assert timer.metrics.duration_ms is not None  # nosec B101
        assert timer.metrics.error is None  # nosec B101
    
    def test_stage_context_with_error(self):
        """Test stage context manager with error."""
        controller = LatencyController()
        
        with pytest.raises(ValueError):
            with controller.stage_context(PipelineStage.INPUT_NORMALIZATION) as timer:
                raise ValueError("Test error")
        
        # Should record error
        assert timer.metrics.error == "Test error"  # nosec B101
    
    def test_get_stage_statistics(self):
        """Test getting stage statistics."""
        # Use fresh controller to avoid shared state
        tracker = LatencyTracker()
        controller = LatencyController(tracker=tracker)
        
        # Run a few stages
        for _ in range(5):
            timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
            time.sleep(0.01)
            controller.end_stage(timer)
        
        stats = controller.get_stage_statistics(PipelineStage.INPUT_NORMALIZATION)
        
        assert stats is not None  # nosec B101
        assert stats.count == 5  # nosec B101
        assert stats.mean > 0  # nosec B101
    
    def test_get_all_statistics(self):
        """Test getting all statistics."""
        controller = LatencyController()
        
        # Run different stages
        for stage in [PipelineStage.INPUT_NORMALIZATION, PipelineStage.INTENT_DETECTION]:
            timer = controller.start_stage(stage)
            time.sleep(0.01)
            controller.end_stage(timer)
        
        all_stats = controller.get_all_statistics()
        
        assert len(all_stats) >= 2  # nosec B101
        assert PipelineStage.INPUT_NORMALIZATION in all_stats  # nosec B101
        assert PipelineStage.INTENT_DETECTION in all_stats  # nosec B101
    
    def test_is_degraded(self):
        """Test checking degraded mode."""
        controller = LatencyController()
        
        # Initially not degraded
        assert controller.is_degraded(PipelineStage.INPUT_NORMALIZATION) is False  # nosec B101
        
        # Activate degraded mode
        controller.degraded_manager.activate_degraded_mode(PipelineStage.INPUT_NORMALIZATION)
        
        # Should be degraded
        assert controller.is_degraded(PipelineStage.INPUT_NORMALIZATION) is True  # nosec B101
    
    def test_get_degraded_stages(self):
        """Test getting degraded stages."""
        controller = LatencyController()
        
        # Activate degraded mode for multiple stages
        controller.degraded_manager.activate_degraded_mode(PipelineStage.INPUT_NORMALIZATION)
        controller.degraded_manager.activate_degraded_mode(PipelineStage.INTENT_DETECTION)
        
        degraded = controller.get_degraded_stages()
        
        assert len(degraded) == 2  # nosec B101
        assert PipelineStage.INPUT_NORMALIZATION in degraded  # nosec B101
        assert PipelineStage.INTENT_DETECTION in degraded  # nosec B101
    
    def test_reset_degraded_mode_single(self):
        """Test resetting degraded mode for single stage."""
        controller = LatencyController()
        
        # Activate degraded mode
        controller.degraded_manager.activate_degraded_mode(PipelineStage.INPUT_NORMALIZATION)
        assert controller.is_degraded(PipelineStage.INPUT_NORMALIZATION) is True  # nosec B101
        
        # Reset
        controller.reset_degraded_mode(PipelineStage.INPUT_NORMALIZATION)
        assert controller.is_degraded(PipelineStage.INPUT_NORMALIZATION) is False  # nosec B101
    
    def test_reset_degraded_mode_all(self):
        """Test resetting degraded mode for all stages."""
        controller = LatencyController()
        
        # Activate degraded mode for multiple stages
        controller.degraded_manager.activate_degraded_mode(PipelineStage.INPUT_NORMALIZATION)
        controller.degraded_manager.activate_degraded_mode(PipelineStage.INTENT_DETECTION)
        
        # Reset all
        controller.reset_degraded_mode()
        
        assert len(controller.get_degraded_stages()) == 0  # nosec B101


class TestStageTimer:
    """Tests for StageTimer."""
    
    def test_elapsed_ms(self):
        """Test elapsed time calculation."""
        from Agent_Guru.reasoning.latency.tracker import StageMetrics
        
        metrics = StageMetrics(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter(),
        )
        
        timer = StageTimer(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter(),
            budget_ms=100,
            max_budget_ms=200,
            metrics=metrics,
        )
        
        time.sleep(0.01)
        
        elapsed = timer.elapsed_ms()
        assert elapsed > 0  # nosec B101
        assert elapsed >= 10  # At least 10ms  # nosec B101
    
    def test_remaining_ms(self):
        """Test remaining budget calculation."""
        from Agent_Guru.reasoning.latency.tracker import StageMetrics
        
        metrics = StageMetrics(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter(),
        )
        
        timer = StageTimer(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter(),
            budget_ms=100,
            max_budget_ms=200,
            metrics=metrics,
        )
        
        remaining = timer.remaining_ms()
        assert remaining <= 100  # nosec B101
    
    def test_is_over_budget(self):
        """Test budget check."""
        from Agent_Guru.reasoning.latency.tracker import StageMetrics
        
        metrics = StageMetrics(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter(),
        )
        
        timer = StageTimer(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter() - 0.2,  # 200ms ago
            budget_ms=100,
            max_budget_ms=200,
            metrics=metrics,
        )
        
        assert timer.is_over_budget() is True  # nosec B101
    
    def test_is_over_max_budget(self):
        """Test maximum budget check."""
        from Agent_Guru.reasoning.latency.tracker import StageMetrics
        
        metrics = StageMetrics(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter(),
        )
        
        timer = StageTimer(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter() - 0.3,  # 300ms ago
            budget_ms=100,
            max_budget_ms=200,
            metrics=metrics,
        )
        
        assert timer.is_over_max_budget() is True  # nosec B101
    
    def test_budget_utilization(self):
        """Test budget utilization calculation."""
        from Agent_Guru.reasoning.latency.tracker import StageMetrics
        
        metrics = StageMetrics(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter(),
        )
        
        timer = StageTimer(
            stage=PipelineStage.INPUT_NORMALIZATION,
            start_time=time.perf_counter() - 0.05,  # 50ms ago
            budget_ms=100,
            max_budget_ms=200,
            metrics=metrics,
        )
        
        utilization = timer.budget_utilization()
        assert 0.4 <= utilization <= 0.6  # Around 50%  # nosec B101


class TestGlobalController:
    """Tests for global controller instance."""
    
    def test_get_latency_controller(self):
        """Test getting global controller."""
        controller1 = get_latency_controller()
        controller2 = get_latency_controller()
        
        # Should return same instance
        assert controller1 is controller2  # nosec B101


@pytest.mark.integration
class TestLatencyControllerIntegration:
    """Integration tests for LatencyController."""
    
    def test_end_to_end_timing(self):
        """Test complete timing flow."""
        controller = LatencyController()
        
        # Start stage
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        # Simulate work
        time.sleep(0.02)
        
        # Check timeout (should not timeout)
        assert controller.check_timeout(timer) is False  # nosec B101
        
        # End stage
        metrics = controller.end_stage(timer)
        
        # Verify metrics
        assert metrics.duration_ms >= 20  # nosec B101
        assert metrics.timeout is False  # nosec B101
        assert metrics.error is None  # nosec B101
    
    def test_degraded_mode_activation(self):
        """Test degraded mode activation on timeout."""
        tracker = LatencyTracker()
        degraded_manager = DegradedModeManager()
        controller = LatencyController(tracker=tracker, degraded_manager=degraded_manager)
        
        # Create timer
        timer = controller.start_stage(PipelineStage.INPUT_NORMALIZATION)
        
        # Simulate work exceeding max budget by setting start time far in the past
        # This will make elapsed_ms() return a large value
        timer.start_time = time.perf_counter() - 0.2  # 200ms ago
        timer.metrics.start_time = timer.start_time
        
        # End stage (should activate degraded mode)
        metrics = controller.end_stage(timer)
        
        # Verify degraded mode activated (duration should be ~200ms, max budget is 100ms)
        assert metrics.duration_ms > timer.max_budget_ms  # nosec B101
        assert controller.is_degraded(PipelineStage.INPUT_NORMALIZATION) is True  # nosec B101
    
    def test_context_manager_integration(self):
        """Test context manager with real timing."""
        controller = LatencyController()
        
        with controller.stage_context(PipelineStage.INPUT_NORMALIZATION) as timer:
            # Simulate work
            time.sleep(0.01)
            
            # Check timeout during work
            assert controller.check_timeout(timer) is False  # nosec B101
        
        # Verify completion
        assert timer.metrics.duration_ms >= 10  # nosec B101
        assert timer.metrics.error is None  # nosec B101
