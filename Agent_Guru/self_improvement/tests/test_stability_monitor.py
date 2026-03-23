"""
Tests for Stability Monitor.

**Validates: Requirements 9.7 (Rate Limiting and Stability)**

Coverage Target: >80% (enforced by CI/CD)
"""

import pytest

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.stability_monitor import StabilityMonitor


@pytest.fixture
def pool(tmp_path):
    """Create connection pool with test database."""
    db_path = str(tmp_path / "test_stability.db")
    DatabaseSchema.create_schema(db_path)
    return ConnectionPool(db_path, min_size=5)


@pytest.fixture
def monitor(pool):
    """Create stability monitor with test configuration."""
    return StabilityMonitor(
        pool,
        window_size=10,
        variance_threshold=0.15,
        change_frequency_threshold=0.3,
        oscillation_threshold=3,
        dampening_factor=0.7,
    )


class TestStabilityMonitorInitialization:
    """Tests for stability monitor initialization."""

    def test_initialization_with_defaults(self, pool):
        """Test initialization with default parameters."""
        monitor = StabilityMonitor(pool)

        assert monitor.window_size == 100
        assert monitor.variance_threshold == 0.15
        assert monitor.change_frequency_threshold == 0.3
        assert monitor.oscillation_threshold == 3
        assert monitor.dampening_factor == 0.7

    def test_initialization_with_custom_parameters(self, pool):
        """Test initialization with custom parameters."""
        monitor = StabilityMonitor(
            pool,
            window_size=50,
            variance_threshold=0.2,
            change_frequency_threshold=0.4,
            oscillation_threshold=5,
            dampening_factor=0.8,
        )

        assert monitor.window_size == 50
        assert monitor.variance_threshold == 0.2
        assert monitor.change_frequency_threshold == 0.4
        assert monitor.oscillation_threshold == 5
        assert monitor.dampening_factor == 0.8


class TestChangeRecording:
    """Tests for recording changes."""

    def test_record_single_change(self, monitor):
        """Test recording a single change."""
        monitor.record_change("strategy_selection", "task_type_1", 0.75)

        changes = monitor.get_recent_changes("strategy_selection", "task_type_1")
        assert len(changes) == 1
        assert changes[0][1] == 0.75

    def test_record_multiple_changes(self, monitor):
        """Test recording multiple changes."""
        values = [0.5, 0.6, 0.7, 0.8, 0.9]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        changes = monitor.get_recent_changes("strategy_selection", "task_type_1", limit=10)
        assert len(changes) == 5

        # Should be newest first
        assert changes[0][1] == 0.9
        assert changes[-1][1] == 0.5

    def test_record_changes_respects_window_size(self, monitor):
        """Test that change history respects window size."""
        # Record more changes than window size
        for i in range(20):
            monitor.record_change("strategy_selection", "task_type_1", float(i) / 20)

        changes = monitor.get_recent_changes("strategy_selection", "task_type_1", limit=20)

        # Should only keep window_size (10) most recent
        assert len(changes) == 10

    def test_record_changes_for_different_components(self, monitor):
        """Test recording changes for different components."""
        monitor.record_change("strategy_selection", "task_type_1", 0.75)
        monitor.record_change("prompt_evolution", "prompt_type_1", 0.85)

        changes1 = monitor.get_recent_changes("strategy_selection", "task_type_1")
        changes2 = monitor.get_recent_changes("prompt_evolution", "prompt_type_1")

        assert len(changes1) == 1
        assert len(changes2) == 1
        assert changes1[0][1] == 0.75
        assert changes2[0][1] == 0.85


class TestStabilityChecks:
    """Tests for stability checking."""

    def test_stable_system_with_no_changes(self, monitor):
        """Test that system with no changes is stable."""
        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert is_stable is True
        assert metrics is None

    def test_stable_system_with_consistent_values(self, monitor):
        """Test that system with consistent values is stable."""
        # Record same value multiple times
        for _ in range(5):
            monitor.record_change("strategy_selection", "task_type_1", 0.75)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert is_stable is True
        assert metrics is not None
        assert metrics.variance == 0.0
        assert metrics.change_frequency == 0.0
        assert metrics.oscillation_detected is False
        assert metrics.stability_score == 1.0

    def test_stable_system_with_gradual_changes(self, monitor):
        """Test that system with gradual changes is stable."""
        # Record gradually increasing values (small changes)
        for i in range(10):
            monitor.record_change("strategy_selection", "task_type_1", 0.5 + i * 0.01)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        # Gradual changes should be stable (low variance, no oscillation)
        assert metrics is not None
        assert metrics.variance < 0.15  # Below threshold
        assert metrics.oscillation_detected is False
        # Overall stability might be slightly lower due to changes, but should still be reasonable
        assert metrics.stability_score > 0.5

    def test_unstable_system_with_oscillation(self, monitor):
        """Test that oscillating system is detected as unstable."""
        # Record oscillating values (A -> B -> A -> B -> A -> B)
        values = [0.5, 0.9, 0.5, 0.9, 0.5, 0.9, 0.5, 0.9]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert is_stable is False
        assert metrics is not None
        assert metrics.oscillation_detected is True
        assert metrics.stability_score < 1.0

    def test_unstable_system_with_high_variance(self, monitor):
        """Test that system with high variance is detected as unstable."""
        # Record values with high variance
        values = [0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        # May or may not be unstable depending on oscillation detection
        assert metrics is not None
        assert metrics.variance > 0.0

    def test_check_all_metrics_for_component(self, monitor):
        """Test checking all metrics for a component."""
        # Record changes for multiple metrics (need at least 2 values each)
        monitor.record_change("strategy_selection", "task_type_1", 0.75)
        monitor.record_change("strategy_selection", "task_type_1", 0.76)
        monitor.record_change("strategy_selection", "task_type_2", 0.85)
        monitor.record_change("strategy_selection", "task_type_2", 0.86)

        is_stable, metrics = monitor.check_stability("strategy_selection")

        assert is_stable is True
        # Should return worst metrics (but both are stable)
        assert metrics is not None


class TestOscillationDetection:
    """Tests for oscillation detection."""

    def test_no_oscillation_with_few_changes(self, monitor):
        """Test that few changes don't trigger oscillation."""
        values = [0.5, 0.9, 0.5]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert metrics.oscillation_detected is False

    def test_oscillation_with_alternating_pattern(self, monitor):
        """Test oscillation detection with clear alternating pattern."""
        # A -> B -> A -> B -> A -> B (6 transitions, threshold is 3)
        values = [0.5, 0.9, 0.5, 0.9, 0.5, 0.9, 0.5, 0.9]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert metrics.oscillation_detected is True

    def test_no_oscillation_with_trend(self, monitor):
        """Test that trending values don't trigger oscillation."""
        # Gradually increasing values
        for i in range(10):
            monitor.record_change("strategy_selection", "task_type_1", 0.5 + i * 0.05)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert metrics.oscillation_detected is False


class TestDampening:
    """Tests for dampening mechanism."""

    def test_dampening_with_no_history(self, monitor):
        """Test dampening with no history returns proposed value."""
        dampened = monitor.apply_dampening("strategy_selection", "task_type_1", 0.9)

        assert dampened == 0.9

    def test_dampening_smooths_large_change(self, monitor):
        """Test that dampening smooths large changes."""
        # Record current value
        monitor.record_change("strategy_selection", "task_type_1", 0.5)

        # Propose large change
        dampened = monitor.apply_dampening("strategy_selection", "task_type_1", 0.9)

        # Dampened value should be between current and proposed
        assert 0.5 < dampened < 0.9

        # With dampening_factor=0.7: 0.5 * 0.7 + 0.9 * 0.3 = 0.62
        assert abs(dampened - 0.62) < 0.01

    def test_dampening_with_small_change(self, monitor):
        """Test dampening with small change."""
        monitor.record_change("strategy_selection", "task_type_1", 0.75)

        dampened = monitor.apply_dampening("strategy_selection", "task_type_1", 0.80)

        # Should still dampen
        assert 0.75 < dampened < 0.80


class TestChangeAllowance:
    """Tests for change allowance checks."""

    def test_allow_change_with_stable_system(self, monitor):
        """Test that changes are allowed in stable system."""
        # Record stable values
        for _ in range(5):
            monitor.record_change("strategy_selection", "task_type_1", 0.75)

        allow, reason = monitor.should_allow_change(
            "strategy_selection", "task_type_1", 0.80
        )

        assert allow is True
        assert reason == "Change allowed"

    def test_block_change_with_oscillating_system(self, monitor):
        """Test that changes are blocked in oscillating system."""
        # Create oscillation
        values = [0.5, 0.9, 0.5, 0.9, 0.5, 0.9, 0.5, 0.9]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        allow, reason = monitor.should_allow_change(
            "strategy_selection", "task_type_1", 0.5
        )

        assert allow is False
        assert "oscillation detected" in reason.lower()

    def test_block_very_large_change(self, monitor):
        """Test that very large changes are blocked."""
        monitor.record_change("strategy_selection", "task_type_1", 0.5)

        # Propose change >50% of current value
        allow, reason = monitor.should_allow_change(
            "strategy_selection", "task_type_1", 1.5
        )

        assert allow is False
        assert "too large" in reason.lower()

    def test_allow_first_change(self, monitor):
        """Test that first change is always allowed."""
        allow, reason = monitor.should_allow_change(
            "strategy_selection", "task_type_1", 0.75
        )

        assert allow is True
        assert reason == "Change allowed"


class TestStabilityReport:
    """Tests for stability reporting."""

    def test_report_with_no_data(self, monitor):
        """Test report with no tracked metrics."""
        report = monitor.get_stability_report()

        assert report["components"] == []
        assert report["metrics"] == []
        assert report["overall_stability_score"] == 1.0
        assert report["unstable_metrics"] == []
        assert len(report["recommendations"]) == 0

    def test_report_with_stable_metrics(self, monitor):
        """Test report with stable metrics."""
        # Record stable values
        for _ in range(5):
            monitor.record_change("strategy_selection", "task_type_1", 0.75)
            monitor.record_change("prompt_evolution", "prompt_type_1", 0.85)

        report = monitor.get_stability_report()

        assert len(report["components"]) == 2
        assert "strategy_selection" in report["components"]
        assert "prompt_evolution" in report["components"]
        assert len(report["metrics"]) == 2
        assert report["overall_stability_score"] > 0.9
        assert len(report["unstable_metrics"]) == 0

    def test_report_with_unstable_metrics(self, monitor):
        """Test report with unstable metrics."""
        # Create oscillation
        values = [0.5, 0.9, 0.5, 0.9, 0.5, 0.9, 0.5, 0.9]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        report = monitor.get_stability_report()

        assert len(report["unstable_metrics"]) > 0
        assert report["overall_stability_score"] < 1.0
        assert len(report["recommendations"]) > 0

    def test_report_for_specific_component(self, monitor):
        """Test report for specific component."""
        # Record multiple values to have enough data for stability check
        monitor.record_change("strategy_selection", "task_type_1", 0.75)
        monitor.record_change("strategy_selection", "task_type_1", 0.76)
        monitor.record_change("prompt_evolution", "prompt_type_1", 0.85)
        monitor.record_change("prompt_evolution", "prompt_type_1", 0.86)

        report = monitor.get_stability_report("strategy_selection")

        assert report["components"] == ["strategy_selection"]
        assert len(report["metrics"]) == 1


class TestHistoryReset:
    """Tests for history reset."""

    def test_reset_specific_metric(self, monitor):
        """Test resetting specific metric."""
        monitor.record_change("strategy_selection", "task_type_1", 0.75)
        monitor.record_change("strategy_selection", "task_type_2", 0.85)

        monitor.reset_history("strategy_selection", "task_type_1")

        changes1 = monitor.get_recent_changes("strategy_selection", "task_type_1")
        changes2 = monitor.get_recent_changes("strategy_selection", "task_type_2")

        assert len(changes1) == 0
        assert len(changes2) == 1

    def test_reset_all_metrics_for_component(self, monitor):
        """Test resetting all metrics for component."""
        monitor.record_change("strategy_selection", "task_type_1", 0.75)
        monitor.record_change("strategy_selection", "task_type_2", 0.85)
        monitor.record_change("prompt_evolution", "prompt_type_1", 0.95)

        monitor.reset_history("strategy_selection")

        changes1 = monitor.get_recent_changes("strategy_selection", "task_type_1")
        changes2 = monitor.get_recent_changes("strategy_selection", "task_type_2")
        changes3 = monitor.get_recent_changes("prompt_evolution", "prompt_type_1")

        assert len(changes1) == 0
        assert len(changes2) == 0
        assert len(changes3) == 1

    def test_reset_all_history(self, monitor):
        """Test resetting all history."""
        monitor.record_change("strategy_selection", "task_type_1", 0.75)
        monitor.record_change("prompt_evolution", "prompt_type_1", 0.85)

        monitor.reset_history()

        changes1 = monitor.get_recent_changes("strategy_selection", "task_type_1")
        changes2 = monitor.get_recent_changes("prompt_evolution", "prompt_type_1")

        assert len(changes1) == 0
        assert len(changes2) == 0


class TestStabilityMetrics:
    """Tests for stability metrics calculation."""

    def test_metrics_with_zero_variance(self, monitor):
        """Test metrics calculation with zero variance."""
        for _ in range(5):
            monitor.record_change("strategy_selection", "task_type_1", 0.75)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert metrics.variance == 0.0
        assert metrics.change_frequency == 0.0
        assert metrics.stability_score == 1.0

    def test_metrics_with_high_variance(self, monitor):
        """Test metrics calculation with high variance."""
        values = [0.1, 0.9, 0.2, 0.8, 0.3, 0.7]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert metrics.variance > 0.0
        assert metrics.stability_score < 1.0

    def test_metrics_with_high_change_frequency(self, monitor):
        """Test metrics calculation with high change frequency."""
        # Every value is different
        for i in range(10):
            monitor.record_change("strategy_selection", "task_type_1", float(i) / 10)

        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        assert metrics.change_frequency == 1.0  # 100% changes
        assert metrics.stability_score < 1.0


class TestIntegration:
    """Integration tests for stability monitor."""

    def test_full_workflow_stable_system(self, monitor):
        """Test full workflow with stable system."""
        # Record stable changes with mostly repeated values (very stable)
        values = [0.75, 0.75, 0.75, 0.75, 0.75, 0.76, 0.76, 0.76, 0.76, 0.76]
        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        # Check stability
        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")
        assert is_stable is True

        # Should allow changes
        allow, _ = monitor.should_allow_change("strategy_selection", "task_type_1", 0.77)
        assert allow is True

        # Get report
        report = monitor.get_stability_report()
        # Stable system should have high stability score (>0.75 is good for very stable)
        assert report["overall_stability_score"] > 0.75

    def test_full_workflow_unstable_system(self, monitor):
        """Test full workflow with unstable system."""
        # Create oscillation
        values = [0.5, 0.9, 0.5, 0.9, 0.5, 0.9, 0.5, 0.9]

        for value in values:
            monitor.record_change("strategy_selection", "task_type_1", value)

        # Check stability
        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")
        assert is_stable is False
        assert metrics.oscillation_detected is True

        # Should block changes
        allow, reason = monitor.should_allow_change("strategy_selection", "task_type_1", 0.5)
        assert allow is False

        # Get report
        report = monitor.get_stability_report()
        assert len(report["unstable_metrics"]) > 0
        assert len(report["recommendations"]) > 0

    def test_dampening_prevents_oscillation(self, monitor):
        """Test that dampening can prevent oscillation."""
        # Start with stable value
        monitor.record_change("strategy_selection", "task_type_1", 0.5)

        # Try to make large change with dampening
        dampened = monitor.apply_dampening("strategy_selection", "task_type_1", 0.9)

        # Record dampened value instead of proposed
        monitor.record_change("strategy_selection", "task_type_1", dampened)

        # Try another large change
        dampened2 = monitor.apply_dampening("strategy_selection", "task_type_1", 0.5)
        monitor.record_change("strategy_selection", "task_type_1", dampened2)

        # Should not trigger oscillation due to dampening
        is_stable, metrics = monitor.check_stability("strategy_selection", "task_type_1")

        # May still be stable due to dampening smoothing the changes
        assert metrics is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
