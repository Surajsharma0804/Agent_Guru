"""
Tests for Tool Intelligence Engine.
"""

import pytest
from datetime import datetime, timedelta

from Agent_Guru.reasoning.tools.intelligence import ToolStats, FailurePattern


class TestToolStats:
    """Tests for ToolStats model."""

    def test_initialization_defaults(self) -> None:
        """Test ToolStats initialization with defaults."""
        stats = ToolStats(tool_id="test.tool")

        assert stats.tool_id == "test.tool"
        assert stats.success_rate == 1.0
        assert stats.avg_latency == 0.0
        assert stats.total_executions == 0
        assert stats.successful_executions == 0
        assert stats.failed_executions == 0
        assert stats.failure_patterns == {}
        assert stats.user_rating == 0.0
        assert stats.user_feedback_count == 0
        assert stats.is_degraded is False
        assert stats.degradation_reason is None
        assert stats.consecutive_failures == 0

    def test_initialization_with_values(self) -> None:
        """Test ToolStats initialization with custom values."""
        stats = ToolStats(
            tool_id="test.tool",
            success_rate=0.95,
            avg_latency=150.0,
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
        )

        assert stats.success_rate == 0.95
        assert stats.avg_latency == 150.0
        assert stats.total_executions == 100

    def test_validation_total_executions(self) -> None:
        """Test validation of total_executions."""
        # Valid: total = successful + failed
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
        )
        assert stats.total_executions == 100

        # Invalid: total != successful + failed
        with pytest.raises(ValueError, match="total_executions"):
            ToolStats(
                tool_id="test.tool",
                successful_executions=90,
                failed_executions=5,
                total_executions=100,  # Move to end to ensure validation runs
            )

    def test_validation_success_rate_range(self) -> None:
        """Test validation of success_rate range."""
        # Valid range
        stats = ToolStats(tool_id="test.tool", success_rate=0.5)
        assert stats.success_rate == 0.5

        # Invalid: below 0.0
        with pytest.raises(ValueError):
            ToolStats(tool_id="test.tool", success_rate=-0.1)

        # Invalid: above 1.0
        with pytest.raises(ValueError):
            ToolStats(tool_id="test.tool", success_rate=1.1)

    def test_validation_user_rating_range(self) -> None:
        """Test validation of user_rating range."""
        # Valid range
        stats = ToolStats(tool_id="test.tool", user_rating=4.5)
        assert stats.user_rating == 4.5

        # Invalid: below 0.0
        with pytest.raises(ValueError):
            ToolStats(tool_id="test.tool", user_rating=-0.1)

        # Invalid: above 5.0
        with pytest.raises(ValueError):
            ToolStats(tool_id="test.tool", user_rating=5.1)

    def test_calculate_success_rate_no_executions(self) -> None:
        """Test success rate calculation with no executions."""
        stats = ToolStats(tool_id="test.tool")
        assert stats.calculate_success_rate() == 1.0

    def test_calculate_success_rate_with_executions(self) -> None:
        """Test success rate calculation with executions."""
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
        )
        assert stats.calculate_success_rate() == 0.95

    def test_record_success_first_execution(self) -> None:
        """Test recording first successful execution."""
        stats = ToolStats(tool_id="test.tool")
        stats.record_success(latency_ms=100.0)

        assert stats.successful_executions == 1
        assert stats.total_executions == 1
        assert stats.failed_executions == 0
        assert stats.success_rate == 1.0
        assert stats.avg_latency == 100.0
        assert stats.consecutive_failures == 0
        assert stats.last_execution_time is not None
        assert stats.last_success_time is not None

    def test_record_success_multiple_executions(self) -> None:
        """Test recording multiple successful executions."""
        stats = ToolStats(tool_id="test.tool")

        stats.record_success(latency_ms=100.0)
        stats.record_success(latency_ms=200.0)
        stats.record_success(latency_ms=150.0)

        assert stats.successful_executions == 3
        assert stats.total_executions == 3
        assert stats.success_rate == 1.0
        # Average should be weighted towards recent values (EMA)
        assert 100.0 < stats.avg_latency < 200.0

    def test_record_success_resets_consecutive_failures(self) -> None:
        """Test that success resets consecutive failures."""
        stats = ToolStats(tool_id="test.tool", consecutive_failures=5)
        stats.record_success(latency_ms=100.0)

        assert stats.consecutive_failures == 0

    def test_record_success_clears_degradation(self) -> None:
        """Test that success clears degradation status."""
        stats = ToolStats(
            tool_id="test.tool",
            is_degraded=True,
            degradation_reason="Test degradation",
        )
        stats.record_success(latency_ms=100.0)

        assert stats.is_degraded is False
        assert stats.degradation_reason is None

    def test_record_failure_first_failure(self) -> None:
        """Test recording first failure."""
        stats = ToolStats(tool_id="test.tool")
        stats.record_failure(FailurePattern.TIMEOUT)

        assert stats.failed_executions == 1
        assert stats.total_executions == 1
        assert stats.successful_executions == 0
        assert stats.success_rate == 0.0
        assert stats.consecutive_failures == 1
        assert stats.failure_patterns["timeout"] == 1
        assert stats.last_execution_time is not None

    def test_record_failure_tracks_patterns(self) -> None:
        """Test that failures track patterns correctly."""
        stats = ToolStats(tool_id="test.tool")

        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.NETWORK_ERROR)

        assert stats.failure_patterns["timeout"] == 2
        assert stats.failure_patterns["network_error"] == 1
        assert stats.consecutive_failures == 3

    def test_record_failure_marks_degraded_low_success_rate(self) -> None:
        """Test that low success rate marks tool as degraded."""
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=10,
            successful_executions=7,
            failed_executions=3,
            success_rate=0.7,
        )

        # One more failure should drop below 0.7 threshold
        stats.record_failure(FailurePattern.TIMEOUT)

        assert stats.is_degraded is True
        assert "Success rate below threshold" in stats.degradation_reason

    def test_record_failure_marks_degraded_consecutive_failures(self) -> None:
        """Test that 3 consecutive failures mark tool as degraded."""
        # Start with some successful executions to avoid immediate degradation
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=5,
            successful_executions=5,
            failed_executions=0,
            success_rate=1.0,
        )

        stats.record_failure(FailurePattern.TIMEOUT)
        assert stats.is_degraded is False

        stats.record_failure(FailurePattern.TIMEOUT)
        assert stats.is_degraded is False

        stats.record_failure(FailurePattern.TIMEOUT)
        assert stats.is_degraded is True
        assert "Consecutive failures: 3" in stats.degradation_reason

    def test_record_user_feedback_first_rating(self) -> None:
        """Test recording first user feedback."""
        stats = ToolStats(tool_id="test.tool")
        stats.record_user_feedback(rating=4.5)

        assert stats.user_rating == 4.5
        assert stats.user_feedback_count == 1

    def test_record_user_feedback_multiple_ratings(self) -> None:
        """Test recording multiple user feedback ratings."""
        stats = ToolStats(tool_id="test.tool")

        stats.record_user_feedback(rating=5.0)
        stats.record_user_feedback(rating=4.0)
        stats.record_user_feedback(rating=3.0)

        assert stats.user_feedback_count == 3
        # Rating should be weighted average (EMA)
        assert 3.0 < stats.user_rating < 5.0

    def test_record_user_feedback_invalid_rating(self) -> None:
        """Test that invalid ratings are rejected."""
        stats = ToolStats(tool_id="test.tool")

        with pytest.raises(ValueError, match="Rating must be between"):
            stats.record_user_feedback(rating=-1.0)

        with pytest.raises(ValueError, match="Rating must be between"):
            stats.record_user_feedback(rating=6.0)

    def test_get_most_common_failure_no_failures(self) -> None:
        """Test getting most common failure with no failures."""
        stats = ToolStats(tool_id="test.tool")
        assert stats.get_most_common_failure() is None

    def test_get_most_common_failure_with_failures(self) -> None:
        """Test getting most common failure pattern."""
        stats = ToolStats(tool_id="test.tool")

        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.NETWORK_ERROR)

        assert stats.get_most_common_failure() == "timeout"

    def test_get_reliability_score_normal(self) -> None:
        """Test reliability score for normal tool."""
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
            success_rate=0.95,
        )

        assert stats.get_reliability_score() == 0.95

    def test_get_reliability_score_degraded(self) -> None:
        """Test reliability score for degraded tool."""
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=100,
            successful_executions=60,
            failed_executions=40,
            success_rate=0.6,
            is_degraded=True,
        )

        # Degraded tools get 50% penalty
        assert stats.get_reliability_score() == 0.3

    def test_get_speed_score_no_executions(self) -> None:
        """Test speed score with no executions."""
        stats = ToolStats(tool_id="test.tool")
        assert stats.get_speed_score() == 1.0

    def test_get_speed_score_fast_tool(self) -> None:
        """Test speed score for fast tool."""
        stats = ToolStats(tool_id="test.tool", avg_latency=100.0)
        score = stats.get_speed_score(max_latency=5000.0)

        # 100ms out of 5000ms max = 0.98 score
        assert score > 0.95

    def test_get_speed_score_slow_tool(self) -> None:
        """Test speed score for slow tool."""
        stats = ToolStats(tool_id="test.tool", avg_latency=4500.0)
        score = stats.get_speed_score(max_latency=5000.0)

        # 4500ms out of 5000ms max = 0.1 score
        assert 0.0 < score < 0.2

    def test_get_speed_score_very_slow_tool(self) -> None:
        """Test speed score for very slow tool (clamped to 0.0)."""
        stats = ToolStats(tool_id="test.tool", avg_latency=10000.0)
        score = stats.get_speed_score(max_latency=5000.0)

        # Exceeds max, should be clamped to 0.0
        assert score == 0.0

    def test_update_success_rate(self) -> None:
        """Test updating success rate."""
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
            success_rate=0.0,  # Incorrect initial value
        )

        stats.update_success_rate()
        assert stats.success_rate == 0.95

    def test_timestamps_updated(self) -> None:
        """Test that timestamps are updated correctly."""
        import time

        stats = ToolStats(tool_id="test.tool")
        initial_updated_at = stats.updated_at

        # Small delay to ensure timestamp difference
        time.sleep(0.01)

        # Record success
        stats.record_success(latency_ms=100.0)
        assert stats.updated_at >= initial_updated_at
        assert stats.last_execution_time is not None
        assert stats.last_success_time is not None

        # Record failure
        updated_at_after_success = stats.updated_at
        last_success_time = stats.last_success_time

        time.sleep(0.01)

        stats.record_failure(FailurePattern.TIMEOUT)
        assert stats.updated_at >= updated_at_after_success
        assert stats.last_execution_time >= last_success_time

    def test_json_serialization(self) -> None:
        """Test JSON serialization/deserialization."""
        stats = ToolStats(
            tool_id="test.tool",
            success_rate=0.95,
            avg_latency=150.0,
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
        )

        # Serialize to JSON
        json_data = stats.model_dump_json()
        assert isinstance(json_data, str)

        # Deserialize from JSON
        restored = ToolStats.model_validate_json(json_data)
        assert restored.tool_id == stats.tool_id
        assert restored.success_rate == stats.success_rate
        assert restored.avg_latency == stats.avg_latency


class TestFailurePattern:
    """Tests for FailurePattern enum."""

    def test_all_patterns_defined(self) -> None:
        """Test that all expected failure patterns are defined."""
        expected_patterns = {
            "timeout",
            "network_error",
            "permission_denied",
            "invalid_parameters",
            "resource_unavailable",
            "unknown",
        }

        actual_patterns = {pattern.value for pattern in FailurePattern}
        assert actual_patterns == expected_patterns

    def test_pattern_values(self) -> None:
        """Test failure pattern values."""
        assert FailurePattern.TIMEOUT.value == "timeout"
        assert FailurePattern.NETWORK_ERROR.value == "network_error"
        assert FailurePattern.PERMISSION_DENIED.value == "permission_denied"
        assert FailurePattern.INVALID_PARAMETERS.value == "invalid_parameters"
        assert FailurePattern.RESOURCE_UNAVAILABLE.value == "resource_unavailable"
        assert FailurePattern.UNKNOWN.value == "unknown"
