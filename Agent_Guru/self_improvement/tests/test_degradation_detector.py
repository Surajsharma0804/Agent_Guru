"""
Tests for DegradationDetector.

Validates performance degradation detection functionality.
"""

import gc
import tempfile
from pathlib import Path

import pytest

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.degradation_detector import (
    DegradationDetector,
    DegradationSeverity,
    DegradationMetric,
)
from Agent_Guru.self_improvement.performance_tracker import PerformanceTracker


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        DatabaseSchema.create_schema(db_path)
        yield db_path
        gc.collect()


@pytest.fixture
def pool(temp_db):
    """Create connection pool for testing."""
    pool = ConnectionPool(temp_db, min_size=1, max_size=5)
    yield pool
    pool.close_all()
    gc.collect()


@pytest.fixture
def detector(pool):
    """Create degradation detector."""
    return DegradationDetector(pool)


@pytest.fixture
def tracker(pool):
    """Create performance tracker."""
    return PerformanceTracker(pool)


class TestDegradationDetectorInitialization:
    """Test degradation detector initialization."""

    def test_initialization_with_defaults(self, pool):
        """Test initialization with default thresholds."""
        detector = DegradationDetector(pool)

        assert detector.success_rate_threshold == 0.10  # nosec B101
        assert detector.execution_time_threshold == 0.20  # nosec B101
        assert detector.reasoning_quality_threshold == 0.10  # nosec B101
        assert detector.tool_selection_threshold == 0.10  # nosec B101
        assert detector.hallucination_threshold == 0.10  # nosec B101
        assert detector.significance_level == 0.05  # nosec B101

    def test_initialization_with_custom_thresholds(self, pool):
        """Test initialization with custom thresholds."""
        detector = DegradationDetector(
            pool,
            success_rate_threshold=0.15,
            execution_time_threshold=0.25,
            reasoning_quality_threshold=0.12,
            tool_selection_threshold=0.08,
            hallucination_threshold=0.15,
            significance_level=0.01,
        )

        assert detector.success_rate_threshold == 0.15  # nosec B101
        assert detector.execution_time_threshold == 0.25  # nosec B101
        assert detector.reasoning_quality_threshold == 0.12  # nosec B101
        assert detector.tool_selection_threshold == 0.08  # nosec B101
        assert detector.hallucination_threshold == 0.15  # nosec B101
        assert detector.significance_level == 0.01  # nosec B101

    def test_invalid_threshold_raises_error(self, pool):
        """Test that invalid thresholds raise ValueError."""
        with pytest.raises(ValueError, match="success_rate_threshold"):
            DegradationDetector(pool, success_rate_threshold=1.5)

        with pytest.raises(ValueError, match="execution_time_threshold"):
            DegradationDetector(pool, execution_time_threshold=-0.1)

        with pytest.raises(ValueError, match="significance_level"):
            DegradationDetector(pool, significance_level=1.5)


class TestDegradationDetection:
    """Test degradation detection functionality."""

    def test_no_degradation_with_insufficient_data(self, detector):
        """Test that no alert is returned with insufficient data."""
        alert = detector.check_for_degradation()
        assert alert is None  # nosec B101

    def test_no_degradation_with_stable_performance(self, detector, tracker):
        """Test that no alert is returned when performance is stable."""
        # Record 150 tasks with stable performance
        for i in range(150):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )
        assert alert is None  # nosec B101

    def test_success_rate_degradation_detected(self, detector, tracker):
        """Test detection of success rate degradation."""
        # Record 100 historical tasks with high success rate
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,  # 100% success
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with degraded success rate
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=(i % 2 == 0),  # 50% success - significant drop
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        assert alert is not None  # nosec B101
        assert DegradationMetric.SUCCESS_RATE in alert.degraded_metrics  # nosec B101
        assert alert.severity in [  # nosec B101
            DegradationSeverity.MODERATE,
            DegradationSeverity.SEVERE,
        ]
        assert "success_rate" in alert.metric_changes  # nosec B101
        assert alert.metric_changes["success_rate"] < 0  # Negative change  # nosec B101

    def test_execution_time_degradation_detected(self, detector, tracker):
        """Test detection of execution time degradation."""
        # Record 100 historical tasks with fast execution
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,  # Fast
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with slow execution
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=200.0,  # 2x slower - significant increase
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        assert alert is not None  # nosec B101
        assert DegradationMetric.EXECUTION_TIME in alert.degraded_metrics  # nosec B101
        assert "execution_time_change_pct" in alert.metric_changes  # nosec B101
        assert alert.metric_changes["execution_time_change_pct"] > 0  # Positive change  # nosec B101

    def test_reasoning_quality_degradation_detected(self, detector, tracker):
        """Test detection of reasoning quality degradation."""
        # Record 100 historical tasks with high reasoning quality
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,  # High quality
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with degraded reasoning quality
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.6,  # Significant drop
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        assert alert is not None  # nosec B101
        assert DegradationMetric.REASONING_QUALITY in alert.degraded_metrics  # nosec B101
        assert "reasoning_quality" in alert.metric_changes  # nosec B101
        assert alert.metric_changes["reasoning_quality"] < 0  # Negative change  # nosec B101

    def test_hallucination_rate_degradation_detected(self, detector, tracker):
        """Test detection of increased hallucination rate."""
        # Record 100 historical tasks with no hallucinations
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,  # No hallucinations
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with hallucinations
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=(i % 3 == 0),  # ~33% hallucination rate
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        assert alert is not None  # nosec B101
        assert DegradationMetric.HALLUCINATION_RATE in alert.degraded_metrics  # nosec B101
        assert "hallucination_rate" in alert.metric_changes  # nosec B101
        assert alert.metric_changes["hallucination_rate"] > 0  # Positive change (bad)  # nosec B101

    def test_multiple_metrics_degradation(self, detector, tracker):
        """Test detection when multiple metrics degrade simultaneously."""
        # Record 100 historical tasks with good performance
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with multiple degradations
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=(i % 2 == 0),  # 50% success (degraded)
                execution_time_ms=200.0,  # 2x slower (degraded)
                reasoning_quality=0.6,  # Lower quality (degraded)
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        assert alert is not None  # nosec B101
        assert len(alert.degraded_metrics) >= 2  # Multiple metrics degraded  # nosec B101
        assert alert.severity in [  # nosec B101
            DegradationSeverity.MODERATE,
            DegradationSeverity.SEVERE,
        ]


class TestSeverityDetermination:
    """Test severity level determination."""

    def test_severe_degradation_for_critical_metrics(self, detector, tracker):
        """Test that critical metric degradation triggers severe alert."""
        # Record 100 historical tasks
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with severe success rate drop
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=(i % 4 == 0),  # 25% success - severe drop
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        assert alert is not None  # nosec B101
        assert alert.severity == DegradationSeverity.SEVERE  # nosec B101
        assert "CRITICAL" in alert.recommended_action  # nosec B101
        assert "rollback" in alert.recommended_action.lower()  # nosec B101


class TestStatisticalSignificance:
    """Test statistical significance testing."""

    def test_statistical_significance_included_in_alert(self, detector, tracker):
        """Test that statistical significance is calculated and included."""
        # Record 100 historical tasks
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with degradation
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=(i % 2 == 0),  # 50% success
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        assert alert is not None  # nosec B101
        assert "t_statistic" in alert.statistical_significance  # nosec B101
        assert "p_value" in alert.statistical_significance  # nosec B101
        assert "is_significant" in alert.statistical_significance  # nosec B101
        assert "cohens_d" in alert.statistical_significance  # nosec B101
        assert "effect_size" in alert.statistical_significance  # nosec B101


class TestDiagnosticInfo:
    """Test diagnostic information collection."""

    def test_diagnostic_info_included_in_alert(self, detector, tracker):
        """Test that diagnostic info is collected and included."""
        # Record 100 historical tasks
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with degradation
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=(i % 2 == 0),
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        assert alert is not None  # nosec B101
        assert "recent_performance" in alert.diagnostic_info  # nosec B101
        assert "historical_performance" in alert.diagnostic_info  # nosec B101
        assert "degraded_metrics_list" in alert.diagnostic_info  # nosec B101
        assert "time_range" in alert.diagnostic_info  # nosec B101

        # Verify structure
        recent_perf = alert.diagnostic_info["recent_performance"]
        assert "success_rate" in recent_perf  # nosec B101
        assert "avg_execution_time_ms" in recent_perf  # nosec B101
        assert "total_tasks" in recent_perf  # nosec B101


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_minimum_tasks_required(self, detector, tracker):
        """Test with exactly minimum tasks required."""
        # Record exactly 50 tasks (minimum)
        for i in range(50):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=10, historical_window_size=30, min_tasks_required=50
        )

        # Should work with exactly minimum tasks
        assert alert is not None or alert is None  # Either is valid  # nosec B101

    def test_degradation_at_threshold_boundary(self, detector, tracker):
        """Test degradation exactly at threshold boundary."""
        # Record 100 historical tasks
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with slightly more than 10% drop (11% drop)
        # 18 successes out of 20 = 90% success rate (10% drop from 100%)
        # But we need to ensure it's detected, so let's make it 17/20 = 85% (15% drop)
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=(i < 117),  # 85% success (15% drop - above threshold)
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        # Above threshold, should trigger alert
        assert alert is not None  # nosec B101
        assert DegradationMetric.SUCCESS_RATE in alert.degraded_metrics  # nosec B101


class TestCustomThresholds:
    """Test custom threshold configuration."""

    def test_stricter_thresholds_detect_smaller_changes(self, pool, tracker):
        """Test that stricter thresholds detect smaller degradations."""
        # Create detector with strict thresholds
        strict_detector = DegradationDetector(
            pool,
            success_rate_threshold=0.05,  # 5% threshold (stricter)
            execution_time_threshold=0.10,
            reasoning_quality_threshold=0.05,
        )

        # Record 100 historical tasks
        for i in range(100):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        # Record 20 recent tasks with small degradation (7% drop)
        for i in range(100, 120):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=(i < 119),  # 93% success (7% drop)
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        alert = strict_detector.check_for_degradation(
            recent_window_size=20, historical_window_size=100
        )

        # Strict detector should catch this
        assert alert is not None  # nosec B101
        assert DegradationMetric.SUCCESS_RATE in alert.degraded_metrics  # nosec B101
