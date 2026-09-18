"""
Tests for PerformanceTracker.

Validates Requirements 4.1-4.7, 7.1-7.7.

Test Coverage:
- Unit tests for all PerformanceTracker methods
- Property-based tests for metrics accuracy
- Edge case tests for insufficient data
- Statistical significance validation
"""

import gc
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.performance_tracker import (
    PerformanceTracker,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        DatabaseSchema.create_schema(db_path)
        yield db_path
        # Cleanup
        gc.collect()


@pytest.fixture
def pool(temp_db):
    """Create connection pool for testing."""
    pool = ConnectionPool(temp_db, min_size=1, max_size=5)
    yield pool
    pool.close_all()
    gc.collect()


@pytest.fixture
def tracker(pool):
    """Create PerformanceTracker for testing."""
    return PerformanceTracker(pool)


class TestPerformanceTrackerInit:
    """Test PerformanceTracker initialization."""

    def test_init_with_valid_pool(self, pool):
        """Test initialization with valid connection pool."""
        tracker = PerformanceTracker(pool)
        assert tracker.pool == pool  # nosec B101

    def test_init_verifies_metrics_table(self, temp_db):
        """Test that initialization verifies metrics table exists."""
        # Create pool without schema
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_db = str(Path(tmpdir) / "empty.db")
            empty_pool = ConnectionPool(empty_db, min_size=1, max_size=5)

            with pytest.raises(RuntimeError, match="Metrics table not found"):
                PerformanceTracker(empty_pool)

            empty_pool.close_all()
            gc.collect()


class TestRecordTaskMetrics:
    """Test record_task_metrics method."""

    def test_record_valid_metrics(self, tracker):
        """Test recording valid task metrics."""
        tracker.record_task_metrics(
            task_id="task_1",
            task_type="analysis",
            strategy_id="strategy_1",
            success=True,
            execution_time_ms=150.0,
            reasoning_quality=0.95,
            tool_selection_correct=True,
            hallucination_detected=False,
            task_sequence_number=1,
        )

        # Verify recorded
        assert tracker.get_task_count() == 1  # nosec B101

    def test_record_invalid_reasoning_quality(self, tracker):
        """Test that invalid reasoning quality raises ValueError."""
        with pytest.raises(ValueError, match="Reasoning quality must be in"):
            tracker.record_task_metrics(
                task_id="task_1",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=150.0,
                reasoning_quality=1.5,  # Invalid
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=1,
            )

    def test_record_multiple_metrics(self, tracker):
        """Test recording multiple task metrics."""
        for i in range(5):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=True,
                execution_time_ms=100.0 + i * 10,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        assert tracker.get_task_count() == 5  # nosec B101


class TestGetCurrentMetrics:
    """Test get_current_metrics method."""

    def test_get_metrics_no_data(self, tracker):
        """Test getting metrics with no data."""
        metrics = tracker.get_current_metrics()

        assert metrics.success_rate == 0.0  # nosec B101
        assert metrics.avg_execution_time_ms == 0.0  # nosec B101
        assert metrics.avg_reasoning_quality == 0.0  # nosec B101
        assert metrics.tool_selection_rate == 0.0  # nosec B101
        assert metrics.hallucination_rate == 0.0  # nosec B101
        assert metrics.total_tasks == 0  # nosec B101

    def test_get_metrics_with_data(self, tracker):
        """Test getting metrics with recorded data."""
        # Record 10 tasks: 8 successes, 2 failures
        for i in range(10):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=i < 8,  # First 8 succeed
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=i < 7,  # First 7 correct
                hallucination_detected=i >= 9,  # Last 1 hallucination
                task_sequence_number=i + 1,
            )

        metrics = tracker.get_current_metrics()

        assert metrics.success_rate == 0.8  # 8/10  # nosec B101
        assert metrics.avg_execution_time_ms == 100.0  # nosec B101
        assert metrics.avg_reasoning_quality == 0.9  # nosec B101
        assert metrics.tool_selection_rate == 0.7  # 7/10  # nosec B101
        assert metrics.hallucination_rate == 0.1  # 1/10  # nosec B101
        assert metrics.total_tasks == 10  # nosec B101


class TestGetBaselineMetrics:
    """Test get_baseline_metrics method."""

    def test_baseline_insufficient_data(self, tracker):
        """Test baseline with insufficient data."""
        # Record only 5 tasks
        for i in range(5):
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

        baseline = tracker.get_baseline_metrics(baseline_size=10)
        assert baseline is None  # nosec B101

    def test_baseline_with_sufficient_data(self, tracker):
        """Test baseline with sufficient data."""
        # Record 20 tasks
        for i in range(20):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=i < 5,  # First 5 succeed (baseline)
                execution_time_ms=100.0 + i * 10,
                reasoning_quality=0.5 + i * 0.02,
                tool_selection_correct=i < 5,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        baseline = tracker.get_baseline_metrics(baseline_size=10)

        assert baseline is not None  # nosec B101
        assert baseline.success_rate == 0.5  # 5/10  # nosec B101
        assert baseline.total_tasks == 10  # nosec B101


class TestGetRecentMetrics:
    """Test get_recent_metrics method."""

    def test_recent_insufficient_data(self, tracker):
        """Test recent metrics with insufficient data."""
        # Record only 5 tasks
        for i in range(5):
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

        recent = tracker.get_recent_metrics(window_size=10)
        assert recent is None  # nosec B101

    def test_recent_with_sufficient_data(self, tracker):
        """Test recent metrics with sufficient data."""
        # Record 20 tasks
        for i in range(20):
            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=i >= 10,  # Last 10 succeed
                execution_time_ms=100.0 + i * 10,
                reasoning_quality=0.5 + i * 0.02,
                tool_selection_correct=i >= 10,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        recent = tracker.get_recent_metrics(window_size=10)

        assert recent is not None  # nosec B101
        assert recent.success_rate == 1.0  # 10/10  # nosec B101
        assert recent.total_tasks == 10  # nosec B101


class TestCalculateImprovement:
    """Test calculate_improvement method."""

    def test_improvement_insufficient_data(self, tracker):
        """Test improvement calculation with insufficient data."""
        # Record only 5 tasks
        for i in range(5):
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

        improvement = tracker.calculate_improvement(baseline_size=10, recent_size=10)
        assert improvement is None  # nosec B101

    def test_improvement_with_improvement(self, tracker):
        """Test improvement calculation showing improvement."""
        # Record 30 tasks: baseline poor, recent good
        for i in range(30):
            if i < 10:
                # Baseline: 50% success rate
                success = i < 5
                reasoning_quality = 0.5
                tool_correct = i < 5
            else:
                # Recent: 90% success rate
                success = i < 28
                reasoning_quality = 0.9
                tool_correct = i < 28

            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=success,
                execution_time_ms=100.0,
                reasoning_quality=reasoning_quality,
                tool_selection_correct=tool_correct,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        improvement = tracker.calculate_improvement(baseline_size=10, recent_size=10)

        assert improvement is not None  # nosec B101
        assert improvement["success_rate_improvement"] > 0  # nosec B101
        assert improvement["reasoning_quality_improvement"] > 0  # nosec B101
        assert improvement["relative_improvement"] > 0  # nosec B101


class TestCalculateStatisticalSignificance:
    """Test calculate_statistical_significance method."""

    def test_significance_insufficient_data(self, tracker):
        """Test significance calculation with insufficient data."""
        # Record only 5 tasks
        for i in range(5):
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

        significance = tracker.calculate_statistical_significance(baseline_size=10, recent_size=10)
        assert significance is None  # nosec B101

    def test_significance_with_significant_improvement(self, tracker):
        """Test significance calculation with significant improvement."""
        # Record 30 tasks: baseline all fail, recent all succeed
        for i in range(30):
            if i < 10:
                # Baseline: 0% success
                success = False
            else:
                # Recent: 100% success
                success = True

            tracker.record_task_metrics(
                task_id=f"task_{i}",
                task_type="analysis",
                strategy_id="strategy_1",
                success=success,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=i + 1,
            )

        significance = tracker.calculate_statistical_significance(baseline_size=10, recent_size=10)

        assert significance is not None  # nosec B101
        assert significance["is_significant"] == True  # nosec B101
        assert significance["p_value"] < 0.05  # nosec B101
        assert significance["improvement"] > 0  # nosec B101


class TestGetTaskCount:
    """Test get_task_count method."""

    def test_count_no_tasks(self, tracker):
        """Test count with no tasks."""
        assert tracker.get_task_count() == 0  # nosec B101

    def test_count_with_tasks(self, tracker):
        """Test count with recorded tasks."""
        for i in range(15):
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

        assert tracker.get_task_count() == 15  # nosec B101


# Property-Based Tests


@given(
    num_tasks=st.integers(min_value=1, max_value=50),
    success_rate=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=20, deadline=None)
@pytest.mark.property
def test_property_success_rate_accuracy(num_tasks, success_rate):
    """
    Property: Recorded success rate must match actual success rate.

    Validates Requirement 4.1: Accurate metric recording.
    """
    import time
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_db = str(Path(tmpdir) / "test.db")
        DatabaseSchema.create_schema(temp_db)
        pool = ConnectionPool(temp_db, min_size=1, max_size=5)
        tracker = PerformanceTracker(pool)

        try:
            # Record tasks with known success rate
            num_successes = int(num_tasks * success_rate)
            for i in range(num_tasks):
                tracker.record_task_metrics(
                    task_id=f"task_{i}",
                    task_type="analysis",
                    strategy_id="strategy_1",
                    success=i < num_successes,
                    execution_time_ms=100.0,
                    reasoning_quality=0.9,
                    tool_selection_correct=True,
                    hallucination_detected=False,
                    task_sequence_number=i + 1,
                )

            metrics = tracker.get_current_metrics()
            expected_rate = num_successes / num_tasks

            # Allow small floating point error
            assert abs(metrics.success_rate - expected_rate) < 0.01  # nosec B101
        finally:
            # Ensure proper cleanup for Windows file locking
            pool.close_all()
            gc.collect()
            time.sleep(0.1)  # Allow Windows to release file locks


@given(
    baseline_success=st.floats(min_value=0.0, max_value=0.5),
    recent_success=st.floats(min_value=0.5, max_value=1.0),
)
@settings(max_examples=20, deadline=None)
@pytest.mark.property
def test_property_improvement_detection(baseline_success, recent_success):
    """
    Property: Improvement must be detected when recent > baseline.

    Validates Requirement 7.3: Measurable improvement detection.
    """
    import time
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_db = str(Path(tmpdir) / "test.db")
        DatabaseSchema.create_schema(temp_db)
        pool = ConnectionPool(temp_db, min_size=1, max_size=5)
        tracker = PerformanceTracker(pool)

        try:
            # Record baseline tasks
            baseline_successes = int(10 * baseline_success)
            for i in range(10):
                tracker.record_task_metrics(
                    task_id=f"baseline_{i}",
                    task_type="analysis",
                    strategy_id="strategy_1",
                    success=i < baseline_successes,
                    execution_time_ms=100.0,
                    reasoning_quality=0.5,
                    tool_selection_correct=True,
                    hallucination_detected=False,
                    task_sequence_number=i + 1,
                )

            # Record recent tasks
            recent_successes = int(10 * recent_success)
            for i in range(10):
                tracker.record_task_metrics(
                    task_id=f"recent_{i}",
                    task_type="analysis",
                    strategy_id="strategy_1",
                    success=i < recent_successes,
                    execution_time_ms=100.0,
                    reasoning_quality=0.9,
                    tool_selection_correct=True,
                    hallucination_detected=False,
                    task_sequence_number=i + 11,
                )

            improvement = tracker.calculate_improvement(baseline_size=10, recent_size=10)

            assert improvement is not None  # nosec B101
            if recent_success > baseline_success:
                assert improvement["success_rate_improvement"] > 0  # nosec B101
            elif recent_success < baseline_success:
                assert improvement["success_rate_improvement"] < 0  # nosec B101
            else:
                assert abs(improvement["success_rate_improvement"]) < 0.1  # nosec B101
        finally:
            # Ensure proper cleanup for Windows file locking
            pool.close_all()
            gc.collect()
            time.sleep(0.1)  # Allow Windows to release file locks


@given(
    reasoning_quality=st.floats(min_value=0.0, max_value=1.0),
    num_tasks=st.integers(min_value=1, max_value=30),
)
@settings(max_examples=20, deadline=None)
@pytest.mark.property
def test_property_reasoning_quality_tracking(reasoning_quality, num_tasks):
    """
    Property: Average reasoning quality must match recorded values.

    Validates Requirement 4.5: Reasoning quality tracking.
    """
    import time
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_db = str(Path(tmpdir) / "test.db")
        DatabaseSchema.create_schema(temp_db)
        pool = ConnectionPool(temp_db, min_size=1, max_size=5)
        tracker = PerformanceTracker(pool)

        try:
            # Record tasks with known reasoning quality
            for i in range(num_tasks):
                tracker.record_task_metrics(
                    task_id=f"task_{i}",
                    task_type="analysis",
                    strategy_id="strategy_1",
                    success=True,
                    execution_time_ms=100.0,
                    reasoning_quality=reasoning_quality,
                    tool_selection_correct=True,
                    hallucination_detected=False,
                    task_sequence_number=i + 1,
                )

            metrics = tracker.get_current_metrics()

            # Allow small floating point error
            assert abs(metrics.avg_reasoning_quality - reasoning_quality) < 0.01  # nosec B101
        finally:
            # Ensure proper cleanup for Windows file locking
            pool.close_all()
            gc.collect()
            time.sleep(0.1)  # Allow Windows to release file locks


# Edge Case Tests


def test_edge_case_zero_baseline_success_rate(tracker):
    """Test improvement calculation when baseline has 0% success."""
    # Record baseline: all failures
    for i in range(10):
        tracker.record_task_metrics(
            task_id=f"baseline_{i}",
            task_type="analysis",
            strategy_id="strategy_1",
            success=False,
            execution_time_ms=100.0,
            reasoning_quality=0.5,
            tool_selection_correct=False,
            hallucination_detected=False,
            task_sequence_number=i + 1,
        )

    # Record recent: all successes
    for i in range(10):
        tracker.record_task_metrics(
            task_id=f"recent_{i}",
            task_type="analysis",
            strategy_id="strategy_1",
            success=True,
            execution_time_ms=100.0,
            reasoning_quality=0.9,
            tool_selection_correct=True,
            hallucination_detected=False,
            task_sequence_number=i + 11,
        )

    improvement = tracker.calculate_improvement(baseline_size=10, recent_size=10)

    assert improvement is not None  # nosec B101
    assert improvement["success_rate_improvement"] == 1.0  # nosec B101
    # Baseline 0% -> recent 100% is the largest possible gain, so relative
    # improvement is capped at 100.0 rather than reported as 0.0. Asserting
    # 0.0 here encoded a harmful expectation: ImprovementReporter divides
    # this by 100 and compares it against its improvement threshold, so 0.0
    # would make a total turnaround (0% -> 100% success) register as
    # 'failed to improve' and raise a false alert.
    assert improvement["relative_improvement"] == 100.0  # nosec B101


def test_edge_case_perfect_baseline(tracker):
    """Test improvement calculation when baseline is already perfect."""
    # Record baseline: all successes
    for i in range(10):
        tracker.record_task_metrics(
            task_id=f"baseline_{i}",
            task_type="analysis",
            strategy_id="strategy_1",
            success=True,
            execution_time_ms=100.0,
            reasoning_quality=1.0,
            tool_selection_correct=True,
            hallucination_detected=False,
            task_sequence_number=i + 1,
        )

    # Record recent: also all successes
    for i in range(10):
        tracker.record_task_metrics(
            task_id=f"recent_{i}",
            task_type="analysis",
            strategy_id="strategy_1",
            success=True,
            execution_time_ms=100.0,
            reasoning_quality=1.0,
            tool_selection_correct=True,
            hallucination_detected=False,
            task_sequence_number=i + 11,
        )

    improvement = tracker.calculate_improvement(baseline_size=10, recent_size=10)

    assert improvement is not None  # nosec B101
    assert improvement["success_rate_improvement"] == 0.0  # nosec B101
    assert improvement["relative_improvement"] == 0.0  # nosec B101


def test_edge_case_single_task_window(tracker):
    """Test metrics with window size of 1."""
    tracker.record_task_metrics(
        task_id="task_1",
        task_type="analysis",
        strategy_id="strategy_1",
        success=True,
        execution_time_ms=100.0,
        reasoning_quality=0.9,
        tool_selection_correct=True,
        hallucination_detected=False,
        task_sequence_number=1,
    )

    recent = tracker.get_recent_metrics(window_size=1)

    assert recent is not None  # nosec B101
    assert recent.success_rate == 1.0  # nosec B101
    assert recent.total_tasks == 1  # nosec B101
