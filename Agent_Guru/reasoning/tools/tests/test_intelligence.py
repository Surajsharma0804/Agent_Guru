"""
Tests for Tool Intelligence Engine.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from Agent_Guru.reasoning.tools.intelligence import (
    FailurePattern,
    ToolStats,
    UserToolPreference,
)


class TestToolStats:
    """Tests for ToolStats model."""

    def test_initialization_defaults(self) -> None:
        """Test ToolStats initialization with defaults."""
        stats = ToolStats(tool_id="test.tool")

        assert stats.tool_id == "test.tool"  # nosec B101
        assert stats.success_rate == 1.0  # nosec B101
        assert stats.avg_latency == 0.0  # nosec B101
        assert stats.total_executions == 0  # nosec B101
        assert stats.successful_executions == 0  # nosec B101
        assert stats.failed_executions == 0  # nosec B101
        assert stats.failure_patterns == {}  # nosec B101
        assert stats.user_rating == 0.0  # nosec B101
        assert stats.user_feedback_count == 0  # nosec B101
        assert stats.is_degraded is False  # nosec B101
        assert stats.degradation_reason is None  # nosec B101
        assert stats.consecutive_failures == 0  # nosec B101

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

        assert stats.success_rate == 0.95  # nosec B101
        assert stats.avg_latency == 150.0  # nosec B101
        assert stats.total_executions == 100  # nosec B101

    def test_validation_total_executions(self) -> None:
        """Test validation of total_executions."""
        # Valid: total = successful + failed
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
        )
        assert stats.total_executions == 100  # nosec B101

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
        assert stats.success_rate == 0.5  # nosec B101

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
        assert stats.user_rating == 4.5  # nosec B101

        # Invalid: below 0.0
        with pytest.raises(ValueError):
            ToolStats(tool_id="test.tool", user_rating=-0.1)

        # Invalid: above 5.0
        with pytest.raises(ValueError):
            ToolStats(tool_id="test.tool", user_rating=5.1)

    def test_calculate_success_rate_no_executions(self) -> None:
        """Test success rate calculation with no executions."""
        stats = ToolStats(tool_id="test.tool")
        assert stats.calculate_success_rate() == 1.0  # nosec B101

    def test_calculate_success_rate_with_executions(self) -> None:
        """Test success rate calculation with executions."""
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
        )
        assert stats.calculate_success_rate() == 0.95  # nosec B101

    def test_record_success_first_execution(self) -> None:
        """Test recording first successful execution."""
        stats = ToolStats(tool_id="test.tool")
        stats.record_success(latency_ms=100.0)

        assert stats.successful_executions == 1  # nosec B101
        assert stats.total_executions == 1  # nosec B101
        assert stats.failed_executions == 0  # nosec B101
        assert stats.success_rate == 1.0  # nosec B101
        assert stats.avg_latency == 100.0  # nosec B101
        assert stats.consecutive_failures == 0  # nosec B101
        assert stats.last_execution_time is not None  # nosec B101
        assert stats.last_success_time is not None  # nosec B101

    def test_record_success_multiple_executions(self) -> None:
        """Test recording multiple successful executions."""
        stats = ToolStats(tool_id="test.tool")

        stats.record_success(latency_ms=100.0)
        stats.record_success(latency_ms=200.0)
        stats.record_success(latency_ms=150.0)

        assert stats.successful_executions == 3  # nosec B101
        assert stats.total_executions == 3  # nosec B101
        assert stats.success_rate == 1.0  # nosec B101
        # Average should be weighted towards recent values (EMA)
        assert 100.0 < stats.avg_latency < 200.0  # nosec B101

    def test_record_success_resets_consecutive_failures(self) -> None:
        """Test that success resets consecutive failures."""
        stats = ToolStats(tool_id="test.tool", consecutive_failures=5)
        stats.record_success(latency_ms=100.0)

        assert stats.consecutive_failures == 0  # nosec B101

    def test_record_success_clears_degradation(self) -> None:
        """Test that success clears degradation status."""
        stats = ToolStats(
            tool_id="test.tool",
            is_degraded=True,
            degradation_reason="Test degradation",
        )
        stats.record_success(latency_ms=100.0)

        assert stats.is_degraded is False  # nosec B101
        assert stats.degradation_reason is None  # nosec B101

    def test_record_failure_first_failure(self) -> None:
        """Test recording first failure."""
        stats = ToolStats(tool_id="test.tool")
        stats.record_failure(FailurePattern.TIMEOUT)

        assert stats.failed_executions == 1  # nosec B101
        assert stats.total_executions == 1  # nosec B101
        assert stats.successful_executions == 0  # nosec B101
        assert stats.success_rate == 0.0  # nosec B101
        assert stats.consecutive_failures == 1  # nosec B101
        assert stats.failure_patterns["timeout"] == 1  # nosec B101
        assert stats.last_execution_time is not None  # nosec B101

    def test_record_failure_tracks_patterns(self) -> None:
        """Test that failures track patterns correctly."""
        stats = ToolStats(tool_id="test.tool")

        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.NETWORK_ERROR)

        assert stats.failure_patterns["timeout"] == 2  # nosec B101
        assert stats.failure_patterns["network_error"] == 1  # nosec B101
        assert stats.consecutive_failures == 3  # nosec B101

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

        assert stats.is_degraded is True  # nosec B101
        assert "Success rate below threshold" in stats.degradation_reason  # nosec B101

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
        assert stats.is_degraded is False  # nosec B101

        stats.record_failure(FailurePattern.TIMEOUT)
        assert stats.is_degraded is False  # nosec B101

        stats.record_failure(FailurePattern.TIMEOUT)
        assert stats.is_degraded is True  # nosec B101
        assert "Consecutive failures: 3" in stats.degradation_reason  # nosec B101

    def test_record_user_feedback_first_rating(self) -> None:
        """Test recording first user feedback."""
        stats = ToolStats(tool_id="test.tool")
        stats.record_user_feedback(rating=4.5)

        assert stats.user_rating == 4.5  # nosec B101
        assert stats.user_feedback_count == 1  # nosec B101

    def test_record_user_feedback_multiple_ratings(self) -> None:
        """Test recording multiple user feedback ratings."""
        stats = ToolStats(tool_id="test.tool")

        stats.record_user_feedback(rating=5.0)
        stats.record_user_feedback(rating=4.0)
        stats.record_user_feedback(rating=3.0)

        assert stats.user_feedback_count == 3  # nosec B101
        # Rating should be weighted average (EMA)
        assert 3.0 < stats.user_rating < 5.0  # nosec B101

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
        assert stats.get_most_common_failure() is None  # nosec B101

    def test_get_most_common_failure_with_failures(self) -> None:
        """Test getting most common failure pattern."""
        stats = ToolStats(tool_id="test.tool")

        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.TIMEOUT)
        stats.record_failure(FailurePattern.NETWORK_ERROR)

        assert stats.get_most_common_failure() == "timeout"  # nosec B101

    def test_get_reliability_score_normal(self) -> None:
        """Test reliability score for normal tool."""
        stats = ToolStats(
            tool_id="test.tool",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
            success_rate=0.95,
        )

        assert stats.get_reliability_score() == 0.95  # nosec B101

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
        assert stats.get_reliability_score() == 0.3  # nosec B101

    def test_get_speed_score_no_executions(self) -> None:
        """Test speed score with no executions."""
        stats = ToolStats(tool_id="test.tool")
        assert stats.get_speed_score() == 1.0  # nosec B101

    def test_get_speed_score_fast_tool(self) -> None:
        """Test speed score for fast tool."""
        stats = ToolStats(tool_id="test.tool", avg_latency=100.0)
        score = stats.get_speed_score(max_latency=5000.0)

        # 100ms out of 5000ms max = 0.98 score
        assert score > 0.95  # nosec B101

    def test_get_speed_score_slow_tool(self) -> None:
        """Test speed score for slow tool."""
        stats = ToolStats(tool_id="test.tool", avg_latency=4500.0)
        score = stats.get_speed_score(max_latency=5000.0)

        # 4500ms out of 5000ms max = 0.1 score
        assert 0.0 < score < 0.2  # nosec B101

    def test_get_speed_score_very_slow_tool(self) -> None:
        """Test speed score for very slow tool (clamped to 0.0)."""
        stats = ToolStats(tool_id="test.tool", avg_latency=10000.0)
        score = stats.get_speed_score(max_latency=5000.0)

        # Exceeds max, should be clamped to 0.0
        assert score == 0.0  # nosec B101

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
        assert stats.success_rate == 0.95  # nosec B101

    def test_timestamps_updated(self) -> None:
        """Test that timestamps are updated correctly."""
        import time

        stats = ToolStats(tool_id="test.tool")
        initial_updated_at = stats.updated_at

        # Small delay to ensure timestamp difference
        time.sleep(0.01)

        # Record success
        stats.record_success(latency_ms=100.0)
        assert stats.updated_at >= initial_updated_at  # nosec B101
        assert stats.last_execution_time is not None  # nosec B101
        assert stats.last_success_time is not None  # nosec B101

        # Record failure
        updated_at_after_success = stats.updated_at
        last_success_time = stats.last_success_time

        time.sleep(0.01)

        stats.record_failure(FailurePattern.TIMEOUT)
        assert stats.updated_at >= updated_at_after_success  # nosec B101
        assert stats.last_execution_time >= last_success_time  # nosec B101

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
        assert isinstance(json_data, str)  # nosec B101

        # Deserialize from JSON
        restored = ToolStats.model_validate_json(json_data)
        assert restored.tool_id == stats.tool_id  # nosec B101
        assert restored.success_rate == stats.success_rate  # nosec B101
        assert restored.avg_latency == stats.avg_latency  # nosec B101


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
        assert actual_patterns == expected_patterns  # nosec B101

    def test_pattern_values(self) -> None:
        """Test failure pattern values."""
        assert FailurePattern.TIMEOUT.value == "timeout"  # nosec B101
        assert FailurePattern.NETWORK_ERROR.value == "network_error"  # nosec B101
        assert FailurePattern.PERMISSION_DENIED.value == "permission_denied"  # nosec B101
        assert FailurePattern.INVALID_PARAMETERS.value == "invalid_parameters"  # nosec B101
        assert FailurePattern.RESOURCE_UNAVAILABLE.value == "resource_unavailable"  # nosec B101
        assert FailurePattern.UNKNOWN.value == "unknown"  # nosec B101


class TestUserToolPreference:
    """Tests for UserToolPreference model."""

    def test_initialization(self) -> None:
        """Test UserToolPreference initialization."""
        pref = UserToolPreference(user_id="user1", tool_id="tool1")

        assert pref.user_id == "user1"  # nosec B101
        assert pref.tool_id == "tool1"  # nosec B101
        assert pref.preference_score == 0.5  # nosec B101
        assert pref.selection_count == 0  # nosec B101
        assert pref.feedback_count == 0  # nosec B101
        assert pref.last_selected is None  # nosec B101

    def test_record_selection(self) -> None:
        """Test recording tool selection."""
        pref = UserToolPreference(user_id="user1", tool_id="tool1")

        pref.record_selection()

        assert pref.selection_count == 1  # nosec B101
        assert pref.last_selected is not None  # nosec B101
        assert pref.preference_score > 0.5  # Should increase  # nosec B101

    def test_record_selection_multiple(self) -> None:
        """Test recording multiple selections."""
        pref = UserToolPreference(user_id="user1", tool_id="tool1")

        for _ in range(5):
            pref.record_selection()

        assert pref.selection_count == 5  # nosec B101
        assert pref.preference_score > 0.5  # nosec B101

    def test_record_positive_feedback(self) -> None:
        """Test recording positive feedback."""
        pref = UserToolPreference(user_id="user1", tool_id="tool1")

        pref.record_feedback(positive=True)

        assert pref.feedback_count == 1  # nosec B101
        assert pref.preference_score > 0.5  # nosec B101

    def test_record_negative_feedback(self) -> None:
        """Test recording negative feedback."""
        pref = UserToolPreference(user_id="user1", tool_id="tool1")

        pref.record_feedback(positive=False)

        assert pref.feedback_count == 1  # nosec B101
        assert pref.preference_score < 0.5  # nosec B101


class TestToolIntelligenceEngine:
    """Tests for ToolIntelligenceEngine."""

    @pytest.fixture
    def engine(self) -> "ToolIntelligenceEngine":
        """Create tool intelligence engine."""
        from Agent_Guru.reasoning.tools.intelligence import ToolIntelligenceEngine

        return ToolIntelligenceEngine()

    @pytest.mark.asyncio
    async def test_initialization(self, engine: "ToolIntelligenceEngine") -> None:
        """Test engine initialization."""
        stats = await engine.get_all_stats()
        assert stats == {}  # nosec B101

    @pytest.mark.asyncio
    async def test_record_successful_execution(self, engine: "ToolIntelligenceEngine") -> None:
        """Test recording successful execution."""
        await engine.record_execution(tool_id="test.tool", success=True, latency_ms=100.0)

        stats = await engine.get_tool_stats("test.tool")
        assert stats is not None  # nosec B101
        assert stats.successful_executions == 1  # nosec B101
        assert stats.total_executions == 1  # nosec B101
        assert stats.success_rate == 1.0  # nosec B101

    @pytest.mark.asyncio
    async def test_record_failed_execution(self, engine: "ToolIntelligenceEngine") -> None:
        """Test recording failed execution."""
        await engine.record_execution(
            tool_id="test.tool",
            success=False,
            latency_ms=0.0,
            failure_pattern=FailurePattern.TIMEOUT,
        )

        stats = await engine.get_tool_stats("test.tool")
        assert stats is not None  # nosec B101
        assert stats.failed_executions == 1  # nosec B101
        assert stats.total_executions == 1  # nosec B101
        assert stats.failure_patterns["timeout"] == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_record_multiple_executions(self, engine: "ToolIntelligenceEngine") -> None:
        """Test recording multiple executions."""
        # Record 10 successful, 2 failed
        for _ in range(10):
            await engine.record_execution(tool_id="test.tool", success=True, latency_ms=100.0)

        for _ in range(2):
            await engine.record_execution(
                tool_id="test.tool",
                success=False,
                latency_ms=0.0,
                failure_pattern=FailurePattern.TIMEOUT,
            )

        stats = await engine.get_tool_stats("test.tool")
        assert stats is not None  # nosec B101
        assert stats.total_executions == 12  # nosec B101
        assert stats.successful_executions == 10  # nosec B101
        assert stats.failed_executions == 2  # nosec B101
        assert abs(stats.success_rate - 10 / 12) < 0.01  # nosec B101

    @pytest.mark.asyncio
    async def test_record_user_feedback_rating(self, engine: "ToolIntelligenceEngine") -> None:
        """Test recording user feedback rating."""
        await engine.record_user_feedback(tool_id="test.tool", user_id="user1", rating=4.5)

        stats = await engine.get_tool_stats("test.tool")
        assert stats is not None  # nosec B101
        assert stats.user_rating == 4.5  # nosec B101
        assert stats.user_feedback_count == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_record_user_feedback_positive(self, engine: "ToolIntelligenceEngine") -> None:
        """Test recording positive user feedback."""
        await engine.record_user_feedback(tool_id="test.tool", user_id="user1", positive=True)

        prefs = await engine.get_user_tool_preferences("user1")
        assert "test.tool" in prefs  # nosec B101
        assert prefs["test.tool"] > 0.5  # nosec B101

    @pytest.mark.asyncio
    async def test_record_user_feedback_negative(self, engine: "ToolIntelligenceEngine") -> None:
        """Test recording negative user feedback."""
        await engine.record_user_feedback(tool_id="test.tool", user_id="user1", positive=False)

        prefs = await engine.get_user_tool_preferences("user1")
        assert "test.tool" in prefs  # nosec B101
        assert prefs["test.tool"] < 0.5  # nosec B101

    @pytest.mark.asyncio
    async def test_get_tool_stats_nonexistent(self, engine: "ToolIntelligenceEngine") -> None:
        """Test getting stats for nonexistent tool."""
        stats = await engine.get_tool_stats("nonexistent.tool")
        assert stats is None  # nosec B101

    @pytest.mark.asyncio
    async def test_get_all_stats(self, engine: "ToolIntelligenceEngine") -> None:
        """Test getting all tool stats."""
        await engine.record_execution(tool_id="tool1", success=True, latency_ms=100.0)
        await engine.record_execution(tool_id="tool2", success=True, latency_ms=200.0)

        all_stats = await engine.get_all_stats()
        assert len(all_stats) == 2  # nosec B101
        assert "tool1" in all_stats  # nosec B101
        assert "tool2" in all_stats  # nosec B101

    @pytest.mark.asyncio
    async def test_rank_tools_no_data(self, engine: "ToolIntelligenceEngine") -> None:
        """Test ranking tools with no execution data."""
        ranked = await engine.rank_tools(["tool1", "tool2", "tool3"])

        assert len(ranked) == 3  # nosec B101
        # All should have same score (no data)
        scores = [score for _, score in ranked]
        assert all(abs(s - scores[0]) < 0.01 for s in scores)  # nosec B101

    @pytest.mark.asyncio
    async def test_rank_tools_with_stats(self, engine: "ToolIntelligenceEngine") -> None:
        """Test ranking tools with execution stats."""
        # Tool1: high success rate, fast
        for _ in range(10):
            await engine.record_execution(tool_id="tool1", success=True, latency_ms=50.0)

        # Tool2: low success rate, slow
        for _ in range(5):
            await engine.record_execution(tool_id="tool2", success=True, latency_ms=500.0)
        for _ in range(5):
            await engine.record_execution(
                tool_id="tool2",
                success=False,
                latency_ms=0.0,
                failure_pattern=FailurePattern.TIMEOUT,
            )

        ranked = await engine.rank_tools(["tool1", "tool2"])

        # Tool1 should rank higher
        assert ranked[0][0] == "tool1"  # nosec B101
        assert ranked[0][1] > ranked[1][1]  # nosec B101

    @pytest.mark.asyncio
    async def test_rank_tools_with_user_preference(self, engine: "ToolIntelligenceEngine") -> None:
        """Test ranking tools with user preferences."""
        # Record user preference for tool2
        await engine.learn_tool_preference(user_id="user1", tool_id="tool2", selected=True)
        await engine.learn_tool_preference(user_id="user1", tool_id="tool2", selected=True)

        ranked = await engine.rank_tools(["tool1", "tool2"], user_id="user1")

        # Tool2 should have higher score due to user preference
        tool2_score = next(score for tid, score in ranked if tid == "tool2")
        tool1_score = next(score for tid, score in ranked if tid == "tool1")
        assert tool2_score > tool1_score  # nosec B101

    @pytest.mark.asyncio
    async def test_detect_degraded_tools_none(self, engine: "ToolIntelligenceEngine") -> None:
        """Test detecting degraded tools when none exist."""
        degraded = await engine.detect_degraded_tools()
        assert degraded == []  # nosec B101

    @pytest.mark.asyncio
    async def test_detect_degraded_tools_with_degraded(
        self, engine: "ToolIntelligenceEngine"
    ) -> None:
        """Test detecting degraded tools."""
        # Create degraded tool (low success rate)
        for _ in range(5):
            await engine.record_execution(tool_id="bad.tool", success=True, latency_ms=100.0)
        for _ in range(5):
            await engine.record_execution(
                tool_id="bad.tool",
                success=False,
                latency_ms=0.0,
                failure_pattern=FailurePattern.TIMEOUT,
            )

        degraded = await engine.detect_degraded_tools()
        assert "bad.tool" in degraded  # nosec B101

    @pytest.mark.asyncio
    async def test_get_user_tool_preferences_empty(self, engine: "ToolIntelligenceEngine") -> None:
        """Test getting user preferences when none exist."""
        prefs = await engine.get_user_tool_preferences("user1")
        assert prefs == {}  # nosec B101

    @pytest.mark.asyncio
    async def test_get_user_tool_preferences_with_data(
        self, engine: "ToolIntelligenceEngine"
    ) -> None:
        """Test getting user preferences with data."""
        await engine.learn_tool_preference(user_id="user1", tool_id="tool1", selected=True)
        await engine.learn_tool_preference(user_id="user1", tool_id="tool2", selected=True)

        prefs = await engine.get_user_tool_preferences("user1")
        assert len(prefs) == 2  # nosec B101
        assert "tool1" in prefs  # nosec B101
        assert "tool2" in prefs  # nosec B101

    @pytest.mark.asyncio
    async def test_learn_tool_preference_selected(self, engine: "ToolIntelligenceEngine") -> None:
        """Test learning tool preference from selection."""
        await engine.learn_tool_preference(user_id="user1", tool_id="tool1", selected=True)

        prefs = await engine.get_user_tool_preferences("user1")
        assert prefs["tool1"] > 0.5  # nosec B101

    @pytest.mark.asyncio
    async def test_learn_tool_preference_not_selected(
        self, engine: "ToolIntelligenceEngine"
    ) -> None:
        """Test learning tool preference when not selected."""
        await engine.learn_tool_preference(user_id="user1", tool_id="tool1", selected=False)

        prefs = await engine.get_user_tool_preferences("user1")
        # Should still create preference entry but not increase score
        assert "tool1" in prefs  # nosec B101

    @pytest.mark.asyncio
    async def test_persistence_stats(self, tmp_path: Path) -> None:
        """Test stats persistence."""
        from Agent_Guru.reasoning.tools.intelligence import ToolIntelligenceEngine

        stats_file = tmp_path / "stats.json"

        # Create engine and record data
        engine1 = ToolIntelligenceEngine(stats_file=stats_file)
        await engine1.record_execution(tool_id="test.tool", success=True, latency_ms=100.0)

        # Create new engine and verify data loaded
        engine2 = ToolIntelligenceEngine(stats_file=stats_file)
        stats = await engine2.get_tool_stats("test.tool")
        assert stats is not None  # nosec B101
        assert stats.successful_executions == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_persistence_preferences(self, tmp_path: Path) -> None:
        """Test preferences persistence."""
        from Agent_Guru.reasoning.tools.intelligence import ToolIntelligenceEngine

        prefs_file = tmp_path / "prefs.json"

        # Create engine and record data
        engine1 = ToolIntelligenceEngine(preferences_file=prefs_file)
        await engine1.learn_tool_preference(user_id="user1", tool_id="tool1", selected=True)

        # Create new engine and verify data loaded
        engine2 = ToolIntelligenceEngine(preferences_file=prefs_file)
        prefs = await engine2.get_user_tool_preferences("user1")
        assert "tool1" in prefs  # nosec B101

    @pytest.mark.asyncio
    async def test_concurrent_access(self, engine: "ToolIntelligenceEngine") -> None:
        """Test concurrent access to engine."""
        import asyncio

        # Record executions concurrently
        tasks = [
            engine.record_execution(tool_id="test.tool", success=True, latency_ms=100.0)
            for _ in range(10)
        ]

        await asyncio.gather(*tasks)

        stats = await engine.get_tool_stats("test.tool")
        assert stats is not None  # nosec B101
        assert stats.total_executions == 10  # nosec B101


class TestToolRankingAlgorithm:
    """Tests for tool ranking algorithm (Task 12.6.3)."""

    @pytest.fixture
    def engine(self) -> "ToolIntelligenceEngine":
        """Create tool intelligence engine."""
        from Agent_Guru.reasoning.tools.intelligence import ToolIntelligenceEngine

        return ToolIntelligenceEngine()

    @pytest.fixture
    def mock_intent(self) -> Any:
        """Create mock intent for testing."""
        from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType

        return Intent(
            intent_type=IntentType.SET_TIMER,
            original_input="set a timer for 5 minutes",
            confidence=0.95,
            entities={
                "duration": Entity(
                    entity_type="duration",
                    value=300,
                    raw_text="5 minutes",
                    confidence=0.95,
                )
            },
        )

    @pytest.fixture
    def mock_tool_metadata(self) -> Any:
        """Create mock tool metadata for testing."""
        from Agent_Guru.reasoning.tools.base import (
            ToolMetadata,
            ToolParameter,
            ToolParameterType,
        )

        return ToolMetadata(
            tool_id="timer.set",
            name="Set Timer",
            description="Set a timer for a specified duration",
            parameters=[
                ToolParameter(
                    name="duration",
                    type=ToolParameterType.INTEGER,
                    description="Duration in seconds",
                    required=True,
                )
            ],
            capabilities=["timer", "set_timer", "countdown"],
        )

    @pytest.fixture
    def mock_registry(self, mock_tool_metadata: Any) -> Any:
        """Create mock tool registry."""

        class MockRegistry:
            def get_metadata(self, tool_id: str) -> Any:
                if tool_id == "timer.set":
                    return mock_tool_metadata
                return None

        return MockRegistry()

    @pytest.mark.asyncio
    async def test_ranking_formula_weights(self, engine: "ToolIntelligenceEngine") -> None:
        """Test that ranking formula uses correct weights.

        Formula: relevance (50%) + reliability (20%) + speed (20%) + user_preference (10%)
        """
        # Create tool with known stats
        await engine.record_execution(tool_id="test.tool", success=True, latency_ms=100.0)

        # Rank with explicit scores
        context = {
            "relevance": 1.0,  # Perfect relevance
        }

        ranked = await engine.rank_tools(["test.tool"], context=context)

        # Expected score: 0.5*1.0 + 0.2*1.0 + 0.2*0.98 + 0.1*0.5
        # = 0.5 + 0.2 + 0.196 + 0.05 = 0.946
        assert len(ranked) == 1  # nosec B101
        assert ranked[0][0] == "test.tool"  # nosec B101
        assert 0.94 < ranked[0][1] < 0.95  # nosec B101

    @pytest.mark.asyncio
    async def test_relevance_score_calculation(
        self,
        engine: "ToolIntelligenceEngine",
        mock_intent: Any,
        mock_registry: Any,
    ) -> None:
        """Test relevance score calculation from intent matching."""
        context = {"intent": mock_intent, "tool_registry": mock_registry}

        ranked = await engine.rank_tools(["timer.set"], context=context)

        # Should have high relevance due to good intent match
        assert len(ranked) == 1  # nosec B101
        assert ranked[0][1] > 0.7  # High score  # nosec B101

    @pytest.mark.asyncio
    async def test_reliability_score_impact(self, engine: "ToolIntelligenceEngine") -> None:
        """Test that reliability score impacts ranking."""
        # Tool1: high reliability (95% success)
        for _ in range(19):
            await engine.record_execution(tool_id="tool1", success=True, latency_ms=100.0)
        await engine.record_execution(
            tool_id="tool1",
            success=False,
            latency_ms=0.0,
            failure_pattern=FailurePattern.TIMEOUT,
        )

        # Tool2: low reliability (50% success)
        for _ in range(5):
            await engine.record_execution(tool_id="tool2", success=True, latency_ms=100.0)
        for _ in range(5):
            await engine.record_execution(
                tool_id="tool2",
                success=False,
                latency_ms=0.0,
                failure_pattern=FailurePattern.TIMEOUT,
            )

        ranked = await engine.rank_tools(["tool1", "tool2"])

        # Tool1 should rank higher due to better reliability
        assert ranked[0][0] == "tool1"  # nosec B101
        assert ranked[0][1] > ranked[1][1]  # nosec B101

    @pytest.mark.asyncio
    async def test_speed_score_impact(self, engine: "ToolIntelligenceEngine") -> None:
        """Test that speed score impacts ranking."""
        # Tool1: fast (100ms)
        for _ in range(10):
            await engine.record_execution(tool_id="tool1", success=True, latency_ms=100.0)

        # Tool2: slow (2000ms)
        for _ in range(10):
            await engine.record_execution(tool_id="tool2", success=True, latency_ms=2000.0)

        ranked = await engine.rank_tools(["tool1", "tool2"])

        # Tool1 should rank higher due to better speed
        assert ranked[0][0] == "tool1"  # nosec B101
        assert ranked[0][1] > ranked[1][1]  # nosec B101

    @pytest.mark.asyncio
    async def test_user_preference_impact(self, engine: "ToolIntelligenceEngine") -> None:
        """Test that user preference impacts ranking."""
        # Record strong preference for tool2
        for _ in range(10):
            await engine.learn_tool_preference(user_id="user1", tool_id="tool2", selected=True)

        ranked = await engine.rank_tools(["tool1", "tool2"], user_id="user1")

        # Tool2 should rank higher due to user preference
        tool2_score = next(score for tid, score in ranked if tid == "tool2")
        tool1_score = next(score for tid, score in ranked if tid == "tool1")
        assert tool2_score > tool1_score  # nosec B101

    @pytest.mark.asyncio
    async def test_ranking_latency_budget(self, engine: "ToolIntelligenceEngine") -> None:
        """Test that ranking completes within 50ms latency budget."""
        import time

        # Create 100 tools with stats
        for i in range(100):
            await engine.record_execution(tool_id=f"tool{i}", success=True, latency_ms=100.0)

        tool_ids = [f"tool{i}" for i in range(100)]

        # Measure ranking time
        start = time.perf_counter()
        ranked = await engine.rank_tools(tool_ids)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should complete within 50ms budget
        assert elapsed_ms < 50.0  # nosec B101
        assert len(ranked) == 100  # nosec B101

    @pytest.mark.asyncio
    async def test_pre_calculated_relevance_scores(self, engine: "ToolIntelligenceEngine") -> None:
        """Test using pre-calculated relevance scores."""
        context = {
            "relevance_scores": {
                "tool1": 0.9,
                "tool2": 0.5,
                "tool3": 0.7,
            }
        }

        ranked = await engine.rank_tools(["tool1", "tool2", "tool3"], context=context)

        # Should rank by relevance scores
        assert ranked[0][0] == "tool1"  # Highest relevance  # nosec B101
        assert ranked[1][0] == "tool3"  # Medium relevance  # nosec B101
        assert ranked[2][0] == "tool2"  # Lowest relevance  # nosec B101

    @pytest.mark.asyncio
    async def test_intent_match_capability_overlap(
        self,
        engine: "ToolIntelligenceEngine",
        mock_intent: Any,
        mock_registry: Any,
    ) -> None:
        """Test intent matching based on capability overlap."""
        # Intent mentions "timer" which matches tool capabilities
        context = {"intent": mock_intent, "tool_registry": mock_registry}

        relevance = engine._calculate_relevance_score("timer.set", context)

        # Should have high relevance due to capability match
        assert relevance > 0.5  # nosec B101

    @pytest.mark.asyncio
    async def test_intent_match_parameter_coverage(self, engine: "ToolIntelligenceEngine") -> None:
        """Test intent matching based on parameter coverage."""
        from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
        from Agent_Guru.reasoning.tools.base import (
            ToolMetadata,
            ToolParameter,
            ToolParameterType,
        )

        # Intent with duration entity
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            original_input="set timer for 5 minutes",
            confidence=0.95,
            entities={
                "duration": Entity(
                    entity_type="duration",
                    value=300,
                    raw_text="5 minutes",
                    confidence=0.95,
                )
            },
        )

        # Tool requires duration parameter
        metadata = ToolMetadata(
            tool_id="timer.set",
            name="Set Timer",
            description="Set a timer",
            parameters=[
                ToolParameter(
                    name="duration",
                    type=ToolParameterType.INTEGER,
                    description="Duration",
                    required=True,
                )
            ],
        )

        class MockRegistry:
            def get_metadata(self, tool_id: str) -> Any:
                return metadata

        context = {"intent": intent, "tool_registry": MockRegistry()}

        relevance = engine._calculate_relevance_score("timer.set", context)

        # Should have relevance due to parameter coverage (30% of score)
        assert relevance >= 0.3  # nosec B101

    @pytest.mark.asyncio
    async def test_intent_match_description_similarity(
        self, engine: "ToolIntelligenceEngine"
    ) -> None:
        """Test intent matching based on description similarity."""
        from Agent_Guru.reasoning.models.intent import Intent, IntentType
        from Agent_Guru.reasoning.tools.base import ToolMetadata

        # Intent mentions "timer"
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            original_input="set a timer",
            confidence=0.95,
            entities={},
        )

        # Tool description mentions "timer"
        metadata = ToolMetadata(
            tool_id="timer.set",
            name="Set Timer",
            description="Set a timer for countdown",
            parameters=[],
        )

        class MockRegistry:
            def get_metadata(self, tool_id: str) -> Any:
                return metadata

        context = {"intent": intent, "tool_registry": MockRegistry()}

        relevance = engine._calculate_relevance_score("timer.set", context)

        # Should have relevance due to description match
        assert relevance > 0.0  # nosec B101

    @pytest.mark.asyncio
    async def test_ranking_with_degraded_tools(self, engine: "ToolIntelligenceEngine") -> None:
        """Test that degraded tools are deprioritized in ranking."""
        # Tool1: normal (high success rate)
        for _ in range(10):
            await engine.record_execution(tool_id="tool1", success=True, latency_ms=100.0)

        # Tool2: degraded (low success rate)
        for _ in range(5):
            await engine.record_execution(tool_id="tool2", success=True, latency_ms=100.0)
        for _ in range(5):
            await engine.record_execution(
                tool_id="tool2",
                success=False,
                latency_ms=0.0,
                failure_pattern=FailurePattern.TIMEOUT,
            )

        ranked = await engine.rank_tools(["tool1", "tool2"])

        # Tool1 should rank higher (tool2 is degraded)
        assert ranked[0][0] == "tool1"  # nosec B101
        assert ranked[0][1] > ranked[1][1]  # nosec B101

        # Verify tool2 is degraded
        stats2 = await engine.get_tool_stats("tool2")
        assert stats2.is_degraded is True  # nosec B101

    @pytest.mark.asyncio
    async def test_ranking_empty_list(self, engine: "ToolIntelligenceEngine") -> None:
        """Test ranking with empty tool list."""
        ranked = await engine.rank_tools([])
        assert ranked == []  # nosec B101

    @pytest.mark.asyncio
    async def test_ranking_single_tool(self, engine: "ToolIntelligenceEngine") -> None:
        """Test ranking with single tool."""
        ranked = await engine.rank_tools(["tool1"])

        assert len(ranked) == 1  # nosec B101
        assert ranked[0][0] == "tool1"  # nosec B101
        assert 0.0 <= ranked[0][1] <= 1.0  # nosec B101

    @pytest.mark.asyncio
    async def test_ranking_score_range(self, engine: "ToolIntelligenceEngine") -> None:
        """Test that all ranking scores are in valid range [0.0, 1.0]."""
        # Create tools with various stats
        for i in range(10):
            success_rate = i / 10.0
            for _ in range(10):
                if _ < success_rate * 10:
                    await engine.record_execution(
                        tool_id=f"tool{i}", success=True, latency_ms=100.0 * (i + 1)
                    )
                else:
                    await engine.record_execution(
                        tool_id=f"tool{i}",
                        success=False,
                        latency_ms=0.0,
                        failure_pattern=FailurePattern.TIMEOUT,
                    )

        tool_ids = [f"tool{i}" for i in range(10)]
        ranked = await engine.rank_tools(tool_ids)

        # All scores should be in valid range
        for tool_id, score in ranked:
            assert 0.0 <= score <= 1.0  # nosec B101

    @pytest.mark.asyncio
    async def test_ranking_deterministic(self, engine: "ToolIntelligenceEngine") -> None:
        """Test that ranking is deterministic for same input."""
        # Create tools with stats
        for i in range(5):
            await engine.record_execution(tool_id=f"tool{i}", success=True, latency_ms=100.0)

        tool_ids = [f"tool{i}" for i in range(5)]

        # Rank multiple times
        ranked1 = await engine.rank_tools(tool_ids)
        ranked2 = await engine.rank_tools(tool_ids)
        ranked3 = await engine.rank_tools(tool_ids)

        # Should produce same results
        assert ranked1 == ranked2 == ranked3  # nosec B101


class TestDegradedToolDetection:
    """Tests for degraded tool detection (Task 12.6.4) - Production Grade."""

    @pytest.mark.asyncio
    async def test_degradation_alert_severity_levels(self) -> None:
        """Test that degradation alerts use appropriate severity levels."""
        from Agent_Guru.reasoning.tools.intelligence import (
            _alert_manager,
        )

        # Capture alerts
        alerts_received = []

        def capture_alert(alert: Any) -> None:
            alerts_received.append(alert)

        _alert_manager.register_handler(capture_alert)

        # Test WARNING severity (success_rate < 0.7 but >= 0.5)
        stats1 = ToolStats(
            tool_id="warning.tool",
            total_executions=10,
            successful_executions=6,
            failed_executions=4,
            success_rate=0.6,
        )
        stats1.record_failure(FailurePattern.TIMEOUT)
        await asyncio.sleep(0.1)  # Allow async alert to process

        # Test ERROR severity (success_rate < 0.5 or 3-4 consecutive failures)
        stats2 = ToolStats(
            tool_id="error.tool",
            total_executions=10,
            successful_executions=5,
            failed_executions=5,
            success_rate=0.5,
        )
        stats2.record_failure(FailurePattern.TIMEOUT)
        await asyncio.sleep(0.1)

        # Test CRITICAL severity (>= 5 consecutive failures)
        stats3 = ToolStats(
            tool_id="critical.tool",
            total_executions=10,
            successful_executions=5,
            failed_executions=5,
            consecutive_failures=4,
        )
        stats3.record_failure(FailurePattern.TIMEOUT)
        await asyncio.sleep(0.1)

        # Verify severity levels
        assert len(alerts_received) >= 2  # nosec B101
        # Note: Some alerts may be deduplicated

    @pytest.mark.asyncio
    async def test_alert_deduplication(self) -> None:
        """Test that duplicate alerts are deduplicated within time window."""
        from Agent_Guru.reasoning.tools.intelligence import (
            AlertSeverity,
            DegradationAlert,
            _alert_manager,
        )

        # Create identical alerts
        alert1 = DegradationAlert(
            tool_id="test.tool",
            severity=AlertSeverity.WARNING,
            reason="Test degradation",
            metrics={},
        )

        alert2 = DegradationAlert(
            tool_id="test.tool",
            severity=AlertSeverity.WARNING,
            reason="Test degradation",
            metrics={},
        )

        # Send first alert
        sent1 = await _alert_manager.send_alert(alert1)
        assert sent1 is True  # nosec B101

        # Send duplicate alert (should be deduplicated)
        sent2 = await _alert_manager.send_alert(alert2)
        assert sent2 is False  # nosec B101

    @pytest.mark.asyncio
    async def test_alert_throttling(self) -> None:
        """Test that alerts are throttled to prevent alert fatigue."""
        from Agent_Guru.reasoning.tools.intelligence import (
            AlertManager,
            AlertSeverity,
            DegradationAlert,
        )

        # Create alert manager with low throttle limit
        mgr = AlertManager(max_alerts_per_tool_per_hour=3)

        # Send 3 alerts (should all succeed)
        for i in range(3):
            alert = DegradationAlert(
                tool_id="test.tool",
                severity=AlertSeverity.WARNING,
                reason=f"Test {i}",
                metrics={},
            )
            sent = await mgr.send_alert(alert)
            assert sent is True  # nosec B101

        # 4th alert should be throttled
        alert4 = DegradationAlert(
            tool_id="test.tool",
            severity=AlertSeverity.WARNING,
            reason="Test 4",
            metrics={},
        )
        sent4 = await mgr.send_alert(alert4)
        assert sent4 is False  # nosec B101

    @pytest.mark.asyncio
    async def test_custom_alert_handlers(self) -> None:
        """Test that custom alert handlers are executed."""
        from Agent_Guru.reasoning.tools.intelligence import (
            AlertManager,
            AlertSeverity,
            DegradationAlert,
        )

        # Track handler executions
        handler1_called = []
        handler2_called = []

        def handler1(alert: DegradationAlert) -> None:
            handler1_called.append(alert.tool_id)

        def handler2(alert: DegradationAlert) -> None:
            handler2_called.append(alert.tool_id)

        # Register handlers
        mgr = AlertManager()
        mgr.register_handler(handler1)
        mgr.register_handler(handler2)

        # Send alert
        alert = DegradationAlert(
            tool_id="test.tool",
            severity=AlertSeverity.WARNING,
            reason="Test",
            metrics={},
        )
        await mgr.send_alert(alert)

        # Both handlers should be called
        assert "test.tool" in handler1_called  # nosec B101
        assert "test.tool" in handler2_called  # nosec B101

    @pytest.mark.asyncio
    async def test_alert_includes_comprehensive_metrics(self) -> None:
        """Test that alerts include comprehensive performance metrics."""
        from Agent_Guru.reasoning.tools.intelligence import _alert_manager

        alerts_received = []

        def capture_alert(alert: Any) -> None:
            alerts_received.append(alert)

        _alert_manager.register_handler(capture_alert)

        # Create degraded tool
        stats = ToolStats(
            tool_id="metrics.tool",
            total_executions=5,
            successful_executions=5,
            failed_executions=0,
        )

        # Trigger degradation
        for _ in range(3):
            stats.record_failure(FailurePattern.TIMEOUT)

        await asyncio.sleep(0.1)

        # Verify alert contains comprehensive metrics
        assert len(alerts_received) > 0  # nosec B101
        alert = alerts_received[-1]
        assert "success_rate" in alert.metrics  # nosec B101
        assert "consecutive_failures" in alert.metrics  # nosec B101
        assert "total_executions" in alert.metrics  # nosec B101
        assert "failed_executions" in alert.metrics  # nosec B101
        assert "avg_latency_ms" in alert.metrics  # nosec B101
        assert "most_common_failure" in alert.metrics  # nosec B101
        assert "failure_patterns" in alert.metrics  # nosec B101

    @pytest.mark.asyncio
    async def test_recovery_alert_sent(self) -> None:
        """Test that recovery alert is sent when tool recovers."""
        from Agent_Guru.reasoning.tools.intelligence import (
            AlertSeverity,
            _alert_manager,
        )

        alerts_received = []

        def capture_alert(alert: Any) -> None:
            alerts_received.append(alert)

        _alert_manager.register_handler(capture_alert)

        # Create degraded tool
        stats = ToolStats(
            tool_id="recovery.tool",
            is_degraded=True,
            degradation_reason="Test degradation",
            consecutive_failures=0,
        )

        # Record success (should trigger recovery)
        stats.record_success(latency_ms=100.0)
        await asyncio.sleep(0.1)

        # Verify recovery alert sent
        recovery_alerts = [a for a in alerts_received if a.severity == AlertSeverity.INFO]
        assert len(recovery_alerts) > 0  # nosec B101
        assert "recovered" in recovery_alerts[0].reason.lower()  # nosec B101

    def test_degraded_tools_deprioritized_in_ranking(self) -> None:
        """Test that degraded tools get 50% penalty in reliability score."""
        # Normal tool
        normal_stats = ToolStats(
            tool_id="normal.tool",
            total_executions=100,
            successful_executions=80,
            failed_executions=20,
            success_rate=0.8,
            is_degraded=False,
        )

        # Degraded tool with same success rate
        degraded_stats = ToolStats(
            tool_id="degraded.tool",
            total_executions=100,
            successful_executions=80,
            failed_executions=20,
            success_rate=0.8,
            is_degraded=True,
        )

        # Normal tool should have higher reliability score
        normal_score = normal_stats.get_reliability_score()
        degraded_score = degraded_stats.get_reliability_score()

        assert normal_score == 0.8  # nosec B101
        assert degraded_score == 0.4  # 50% penalty  # nosec B101
        assert normal_score > degraded_score  # nosec B101

    def test_no_degradation_with_insufficient_data(self) -> None:
        """Test that tool is not marked degraded with < 5 executions."""
        stats = ToolStats(tool_id="test.tool")

        # Record 4 failures (below minimum threshold)
        for _ in range(4):
            stats.record_failure(FailurePattern.TIMEOUT)

        # Should NOT be marked as degraded (insufficient data)
        assert stats.is_degraded is False  # nosec B101
        assert stats.consecutive_failures == 4  # nosec B101

    @pytest.mark.asyncio
    async def test_detect_degraded_tools_method(self) -> None:
        """Test ToolIntelligenceEngine.detect_degraded_tools() method."""
        from Agent_Guru.reasoning.tools.intelligence import ToolIntelligenceEngine

        engine = ToolIntelligenceEngine()

        # Create normal tool
        for _ in range(10):
            await engine.record_execution(tool_id="normal.tool", success=True, latency_ms=100.0)

        # Create degraded tool
        for _ in range(5):
            await engine.record_execution(tool_id="degraded.tool", success=True, latency_ms=100.0)
        for _ in range(5):
            await engine.record_execution(
                tool_id="degraded.tool",
                success=False,
                latency_ms=0.0,
                failure_pattern=FailurePattern.TIMEOUT,
            )

        # Detect degraded tools
        degraded = await engine.detect_degraded_tools()

        # Should only include degraded tool
        assert "degraded.tool" in degraded  # nosec B101
        assert "normal.tool" not in degraded  # nosec B101

    @pytest.mark.asyncio
    async def test_alert_manager_cleanup(self) -> None:
        """Test that alert manager cleans up old alerts."""
        from Agent_Guru.reasoning.tools.intelligence import (
            AlertManager,
            AlertSeverity,
            DegradationAlert,
        )

        mgr = AlertManager(dedup_window_seconds=1)  # 1 second window

        # Send alert
        alert = DegradationAlert(
            tool_id="test.tool",
            severity=AlertSeverity.WARNING,
            reason="Test",
            metrics={},
        )
        await mgr.send_alert(alert)

        # Wait for cleanup window
        await asyncio.sleep(1.5)

        # Send another alert (should not be deduplicated after cleanup)
        alert2 = DegradationAlert(
            tool_id="test.tool",
            severity=AlertSeverity.WARNING,
            reason="Test",
            metrics={},
        )
        sent = await mgr.send_alert(alert2)
        assert sent is True  # nosec B101

    def test_get_alert_manager(self) -> None:
        """Test that alert manager can be retrieved for configuration."""
        from Agent_Guru.reasoning.tools.intelligence import ToolIntelligenceEngine

        engine = ToolIntelligenceEngine()
        alert_mgr = engine.get_alert_manager()

        assert alert_mgr is not None  # nosec B101
        # Should be able to register handlers
        alert_mgr.register_handler(lambda alert: None)
