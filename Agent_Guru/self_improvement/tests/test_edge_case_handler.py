"""
Unit tests for EdgeCaseHandler.

Tests confidence calculation, edge case detection, and overgeneralization prevention.
"""

import pytest
import tempfile
from pathlib import Path

from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.edge_case_handler import (
    EdgeCaseHandler,
    ConfidenceMetrics,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        DatabaseSchema.create_schema(db_path)
        yield db_path


@pytest.fixture
def pool(temp_db):
    """Create connection pool for testing."""
    pool = ConnectionPool(temp_db, min_size=1, max_size=5)
    yield pool
    # Cleanup: close all connections before temp directory is removed
    pool.close_all()


@pytest.fixture
def handler(pool):
    """Create edge case handler for testing."""
    return EdgeCaseHandler(
        pool,
        min_sample_size=10,
        edge_case_threshold=0.05,
        confidence_level=0.95,
    )


class TestEdgeCaseHandlerInitialization:
    """Test edge case handler initialization."""

    def test_initialization_success(self, pool):
        """Test successful initialization."""
        handler = EdgeCaseHandler(pool, min_sample_size=10)
        assert handler.min_sample_size == 10
        assert handler.edge_case_threshold == 0.05
        assert handler.confidence_level == 0.95

    def test_initialization_custom_params(self, pool):
        """Test initialization with custom parameters."""
        handler = EdgeCaseHandler(
            pool,
            min_sample_size=20,
            edge_case_threshold=0.1,
            confidence_level=0.99,
        )
        assert handler.min_sample_size == 20
        assert handler.edge_case_threshold == 0.1
        assert handler.confidence_level == 0.99

    def test_initialization_invalid_min_sample_size(self, pool):
        """Test initialization with invalid min_sample_size."""
        with pytest.raises(ValueError, match="min_sample_size must be >= 1"):
            EdgeCaseHandler(pool, min_sample_size=0)

    def test_initialization_invalid_edge_case_threshold(self, pool):
        """Test initialization with invalid edge_case_threshold."""
        with pytest.raises(ValueError, match="edge_case_threshold must be in"):
            EdgeCaseHandler(pool, edge_case_threshold=1.5)

    def test_initialization_invalid_confidence_level(self, pool):
        """Test initialization with invalid confidence_level."""
        with pytest.raises(ValueError, match="confidence_level must be in"):
            EdgeCaseHandler(pool, confidence_level=1.5)


class TestConfidenceCalculation:
    """Test confidence calculation."""

    def test_calculate_confidence_common_pattern(self, handler):
        """Test confidence calculation for common pattern with good data."""
        # Common pattern: 100 samples out of 1000 total events
        # 90% success rate
        metrics = handler.calculate_confidence(
            pattern_id="common_pattern",
            successes=90,
            failures=10,
            total_events=1000,
        )

        assert metrics.pattern_id == "common_pattern"
        assert metrics.sample_size == 100
        assert metrics.success_rate > 0.85  # Bayesian smoothing
        assert metrics.confidence_score > 0.8  # High confidence
        assert metrics.meets_threshold is True  # >= 10 samples
        assert metrics.is_edge_case is False  # 10% frequency > 5% threshold
        assert 0.0 <= metrics.lower_bound <= metrics.upper_bound <= 1.0

    def test_calculate_confidence_rare_pattern(self, handler):
        """Test confidence calculation for rare pattern (edge case)."""
        # Rare pattern: 2 samples out of 1000 total events
        # 100% success rate (but small sample)
        metrics = handler.calculate_confidence(
            pattern_id="rare_pattern",
            successes=2,
            failures=0,
            total_events=1000,
        )

        assert metrics.pattern_id == "rare_pattern"
        assert metrics.sample_size == 2
        assert metrics.meets_threshold is False  # < 10 samples
        assert metrics.is_edge_case is True  # 0.2% frequency < 5% threshold
        assert metrics.event_frequency < 0.05
        assert metrics.weighted_score < metrics.success_rate  # Downweighted

    def test_calculate_confidence_perfect_success_small_sample(self, handler):
        """Test that perfect success with small sample gets low confidence."""
        # 5/5 successes but small sample
        metrics = handler.calculate_confidence(
            pattern_id="perfect_small",
            successes=5,
            failures=0,
            total_events=100,
        )

        # Bayesian smoothing should prevent 100% success rate
        assert metrics.success_rate < 1.0
        # Low confidence due to small sample
        assert metrics.confidence_score < 0.7
        # Doesn't meet threshold
        assert metrics.meets_threshold is False

    def test_calculate_confidence_zero_samples(self, handler):
        """Test confidence calculation with zero samples."""
        metrics = handler.calculate_confidence(
            pattern_id="zero_samples",
            successes=0,
            failures=0,
            total_events=100,
        )

        assert metrics.sample_size == 0
        assert metrics.success_rate >= 0.0  # Bayesian prior
        # Confidence score will be non-zero due to sigmoid function
        # but should be low
        assert metrics.confidence_score < 0.5  # Low confidence
        assert metrics.meets_threshold is False
        assert metrics.lower_bound == 0.0
        assert metrics.upper_bound == 0.0

    def test_calculate_confidence_large_sample(self, handler):
        """Test confidence calculation with large sample."""
        # Large sample: 500 samples, 80% success
        metrics = handler.calculate_confidence(
            pattern_id="large_sample",
            successes=400,
            failures=100,
            total_events=1000,
        )

        assert metrics.sample_size == 500
        assert metrics.meets_threshold is True
        assert metrics.confidence_score > 0.9  # Very high confidence
        # Narrow confidence interval
        assert (metrics.upper_bound - metrics.lower_bound) < 0.1


class TestEdgeCaseDetection:
    """Test edge case detection."""

    def test_edge_case_detection_rare_event(self, handler):
        """Test that rare events are detected as edge cases."""
        # 1% frequency (< 5% threshold)
        metrics = handler.calculate_confidence(
            pattern_id="rare",
            successes=5,
            failures=5,
            total_events=1000,
        )

        assert metrics.is_edge_case is True
        assert metrics.event_frequency == 0.01

    def test_edge_case_detection_common_event(self, handler):
        """Test that common events are not edge cases."""
        # 10% frequency (> 5% threshold)
        metrics = handler.calculate_confidence(
            pattern_id="common",
            successes=50,
            failures=50,
            total_events=1000,
        )

        assert metrics.is_edge_case is False
        assert metrics.event_frequency == 0.1

    def test_edge_case_detection_boundary(self, handler):
        """Test edge case detection at boundary."""
        # Exactly 5% frequency (at threshold)
        metrics = handler.calculate_confidence(
            pattern_id="boundary",
            successes=25,
            failures=25,
            total_events=1000,
        )

        # Should not be edge case (>= threshold)
        assert metrics.is_edge_case is False
        assert metrics.event_frequency == 0.05


class TestWeightedScoring:
    """Test weighted scoring to prevent overgeneralization."""

    def test_weighted_score_rare_event_downweighted(self, handler):
        """Test that rare events are downweighted."""
        # Rare event with high success rate
        metrics = handler.calculate_confidence(
            pattern_id="rare_success",
            successes=9,
            failures=1,
            total_events=1000,
        )

        # Weighted score should be less than raw success rate
        assert metrics.weighted_score < metrics.success_rate
        assert metrics.is_edge_case is True

    def test_weighted_score_common_event_full_weight(self, handler):
        """Test that common events get full weight."""
        # Common event with high success rate
        metrics = handler.calculate_confidence(
            pattern_id="common_success",
            successes=90,
            failures=10,
            total_events=1000,
        )

        # Weighted score should be close to raw success rate
        assert abs(metrics.weighted_score - metrics.success_rate) < 0.1
        assert metrics.is_edge_case is False

    def test_get_weighted_success_rate(self, handler):
        """Test get_weighted_success_rate method."""
        # Rare event
        rare_rate = handler.get_weighted_success_rate(
            pattern_id="rare",
            successes=5,
            failures=0,
            total_events=1000,
        )

        # Common event
        common_rate = handler.get_weighted_success_rate(
            pattern_id="common",
            successes=50,
            failures=0,
            total_events=1000,
        )

        # Common event should have higher weighted rate
        assert common_rate > rare_rate


class TestPatternTrust:
    """Test pattern trust decisions."""

    def test_should_trust_pattern_sufficient_data(self, handler):
        """Test trusting pattern with sufficient data."""
        should_trust, reason = handler.should_trust_pattern(
            pattern_id="trusted",
            successes=50,
            failures=10,
            total_events=1000,
        )

        assert should_trust is True
        assert "trusted" in reason.lower() or "edge case" in reason.lower()

    def test_should_trust_pattern_insufficient_data(self, handler):
        """Test not trusting pattern with insufficient data."""
        should_trust, reason = handler.should_trust_pattern(
            pattern_id="untrusted",
            successes=3,
            failures=2,
            total_events=1000,
        )

        assert should_trust is False
        assert "insufficient data" in reason.lower()

    def test_should_trust_pattern_low_confidence(self, handler):
        """Test not trusting pattern with low confidence."""
        # Very small sample with extreme result
        should_trust, reason = handler.should_trust_pattern(
            pattern_id="low_conf",
            successes=1,
            failures=0,
            total_events=1000,
        )

        assert should_trust is False
        # Either insufficient data or low confidence
        assert "insufficient" in reason.lower() or "confidence" in reason.lower()

    def test_should_trust_pattern_edge_case_warning(self, handler):
        """Test that edge cases are trusted but with warning."""
        # Edge case with sufficient data
        should_trust, reason = handler.should_trust_pattern(
            pattern_id="edge",
            successes=15,
            failures=5,
            total_events=1000,
        )

        # Should trust (meets threshold) but with edge case warning
        assert should_trust is True
        assert "edge case" in reason.lower()


class TestConfidenceReport:
    """Test confidence report generation."""

    def test_get_confidence_report_complete(self, handler):
        """Test complete confidence report."""
        report = handler.get_confidence_report(
            pattern_id="test_pattern",
            successes=50,
            failures=10,
            total_events=1000,
        )

        # Check all required fields
        assert "pattern_id" in report
        assert "sample_size" in report
        assert "success_rate" in report
        assert "weighted_score" in report
        assert "confidence_score" in report
        assert "confidence_interval" in report
        assert "is_edge_case" in report
        assert "event_frequency" in report
        assert "meets_threshold" in report
        assert "should_trust" in report
        assert "reason" in report
        assert "recommendations" in report
        assert "timestamp" in report

    def test_get_confidence_report_recommendations_insufficient_data(self, handler):
        """Test recommendations for insufficient data."""
        report = handler.get_confidence_report(
            pattern_id="insufficient",
            successes=3,
            failures=2,
            total_events=100,
        )

        recommendations = report["recommendations"]
        assert len(recommendations) > 0
        assert any("collect" in r.lower() for r in recommendations)

    def test_get_confidence_report_recommendations_edge_case(self, handler):
        """Test recommendations for edge case."""
        report = handler.get_confidence_report(
            pattern_id="edge",
            successes=2,
            failures=1,
            total_events=1000,
        )

        recommendations = report["recommendations"]
        assert any("rare event" in r.lower() for r in recommendations)

    def test_get_confidence_report_recommendations_high_confidence(self, handler):
        """Test recommendations for high confidence pattern."""
        report = handler.get_confidence_report(
            pattern_id="high_conf",
            successes=90,
            failures=10,
            total_events=1000,
        )

        recommendations = report["recommendations"]
        assert any("high confidence" in r.lower() for r in recommendations)


class TestWilsonScoreInterval:
    """Test Wilson score confidence interval calculation."""

    def test_wilson_score_interval_50_percent(self, handler):
        """Test Wilson score for 50% success rate."""
        lower, upper = handler._wilson_score_interval(
            successes=50,
            sample_size=100,
            z=1.96,  # 95% confidence
        )

        # Should be centered around 0.5
        assert 0.4 < lower < 0.5
        assert 0.5 < upper < 0.6
        assert lower < 0.5 < upper

    def test_wilson_score_interval_high_success(self, handler):
        """Test Wilson score for high success rate."""
        lower, upper = handler._wilson_score_interval(
            successes=90,
            sample_size=100,
            z=1.96,
        )

        # Should be centered around 0.9
        assert 0.8 < lower < 0.9
        assert 0.9 < upper < 1.0
        assert lower < 0.9 < upper

    def test_wilson_score_interval_zero_samples(self, handler):
        """Test Wilson score with zero samples."""
        lower, upper = handler._wilson_score_interval(
            successes=0,
            sample_size=0,
            z=1.96,
        )

        assert lower == 0.0
        assert upper == 0.0

    def test_wilson_score_interval_bounds(self, handler):
        """Test that Wilson score stays within [0, 1]."""
        # Extreme case: 1 success out of 1
        lower, upper = handler._wilson_score_interval(
            successes=1,
            sample_size=1,
            z=1.96,
        )

        assert 0.0 <= lower <= 1.0
        assert 0.0 <= upper <= 1.0
        assert lower <= upper


class TestRecentEdgeCases:
    """Test recent edge cases retrieval."""

    def test_get_recent_edge_cases_empty(self, handler):
        """Test getting recent edge cases when none exist."""
        edge_cases = handler.get_recent_edge_cases(limit=10, days=7)
        assert len(edge_cases) == 0

    def test_get_recent_edge_cases_with_data(self, handler):
        """Test getting recent edge cases with data."""
        # Create some edge cases
        for i in range(5):
            handler.calculate_confidence(
                pattern_id=f"edge_{i}",
                successes=2,
                failures=1,
                total_events=1000,  # 0.3% frequency < 5% threshold
            )

        edge_cases = handler.get_recent_edge_cases(limit=10, days=7)
        assert len(edge_cases) == 5
        assert all(case.is_edge_case for case in edge_cases)

    def test_get_recent_edge_cases_limit(self, handler):
        """Test that limit is respected."""
        # Create 10 edge cases
        for i in range(10):
            handler.calculate_confidence(
                pattern_id=f"edge_{i}",
                successes=1,
                failures=1,
                total_events=1000,
            )

        edge_cases = handler.get_recent_edge_cases(limit=5, days=7)
        assert len(edge_cases) == 5

    def test_get_recent_edge_cases_excludes_common(self, handler):
        """Test that common patterns are excluded."""
        # Create edge case
        handler.calculate_confidence(
            pattern_id="edge",
            successes=2,
            failures=1,
            total_events=1000,
        )

        # Create common pattern
        handler.calculate_confidence(
            pattern_id="common",
            successes=50,
            failures=50,
            total_events=1000,
        )

        edge_cases = handler.get_recent_edge_cases(limit=10, days=7)
        assert len(edge_cases) == 1
        assert edge_cases[0].pattern_id == "edge"


class TestBayesianSmoothing:
    """Test Bayesian smoothing to prevent overfitting."""

    def test_bayesian_smoothing_prevents_100_percent(self, handler):
        """Test that Bayesian smoothing prevents 100% success rate."""
        # Perfect success with small sample
        metrics = handler.calculate_confidence(
            pattern_id="perfect",
            successes=5,
            failures=0,
            total_events=100,
        )

        # Should not be exactly 1.0 due to Bayesian prior
        assert metrics.success_rate < 1.0
        assert metrics.success_rate > 0.8  # But still high

    def test_bayesian_smoothing_prevents_0_percent(self, handler):
        """Test that Bayesian smoothing prevents 0% success rate."""
        # Perfect failure with small sample
        metrics = handler.calculate_confidence(
            pattern_id="failure",
            successes=0,
            failures=5,
            total_events=100,
        )

        # Should not be exactly 0.0 due to Bayesian prior
        assert metrics.success_rate > 0.0
        assert metrics.success_rate < 0.2  # But still low

    def test_bayesian_smoothing_minimal_impact_large_sample(self, handler):
        """Test that Bayesian smoothing has minimal impact on large samples."""
        # Large sample with 90% success
        metrics = handler.calculate_confidence(
            pattern_id="large",
            successes=900,
            failures=100,
            total_events=10000,
        )

        # Should be very close to 0.9
        assert 0.89 < metrics.success_rate < 0.91
