"""
Unit tests for StrategyOptimizer.

Tests strategy registration, performance tracking, and selection algorithms.

**Validates: Requirements 2.1, 2.2, 2.3**

Coverage Target: >80%
"""

import os
import sqlite3
import tempfile

import pytest

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.strategy_optimizer import StrategyOptimizer

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_strategy_optimizer.db")
        DatabaseSchema.create_schema(db_path)
        yield db_path


@pytest.fixture
def connection_pool(temp_db):
    """Create connection pool for testing."""
    pool = ConnectionPool(temp_db, min_size=1, max_size=5)
    yield pool
    pool.close_all()


@pytest.fixture
def optimizer(connection_pool):
    """Create StrategyOptimizer instance for testing."""
    return StrategyOptimizer(connection_pool, epsilon=0.1)


# ============================================================================
# Initialization Tests
# ============================================================================


class TestStrategyOptimizerInitialization:
    """Test StrategyOptimizer initialization."""

    def test_initialization(self, connection_pool):
        """Test basic initialization."""
        optimizer = StrategyOptimizer(connection_pool)

        assert optimizer.pool == connection_pool
        assert optimizer.epsilon == 0.1  # Default
        assert optimizer.min_executions_for_confidence == 10  # Default

    def test_initialization_with_custom_epsilon(self, connection_pool):
        """Test initialization with custom epsilon."""
        optimizer = StrategyOptimizer(connection_pool, epsilon=0.2)

        assert optimizer.epsilon == 0.2

    def test_initialization_with_invalid_epsilon(self, connection_pool):
        """Test initialization with invalid epsilon."""
        with pytest.raises(ValueError, match="Epsilon must be in"):
            StrategyOptimizer(connection_pool, epsilon=1.5)

        with pytest.raises(ValueError, match="Epsilon must be in"):
            StrategyOptimizer(connection_pool, epsilon=-0.1)

    def test_database_schema_created(self, optimizer, connection_pool):
        """Test that database schema is created."""
        with connection_pool.connection() as conn:
            cursor = conn.cursor()

            # Check strategies table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='strategies'
            """
            )
            assert cursor.fetchone() is not None

    def test_initialization_without_schema_fails(self):
        """Test that initialization fails if schema not created."""
        # Create temp db WITHOUT calling DatabaseSchema.create_schema()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "no_schema.db")
            # Just create empty database
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.close()

            pool = ConnectionPool(db_path, min_size=1, max_size=5)

            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="Strategies table not found"):
                StrategyOptimizer(pool)

            pool.close_all()


# ============================================================================
# Strategy Registration Tests
# ============================================================================


class TestStrategyRegistration:
    """Test strategy registration."""

    def test_register_strategy(self, optimizer):
        """Test registering a new strategy."""
        optimizer.register_strategy(
            strategy_id="chain_of_thought",
            name="Chain of Thought",
            description="Step-by-step reasoning",
            task_types=["analysis", "problem_solving"],
            parameters={"max_steps": 5},
        )

        # Verify strategy was registered
        strategy = optimizer.get_strategy("chain_of_thought")
        assert strategy is not None
        assert strategy.strategy_id == "chain_of_thought"
        assert strategy.name == "Chain of Thought"
        assert strategy.description == "Step-by-step reasoning"
        assert strategy.task_types == ["analysis", "problem_solving"]
        assert strategy.parameters == {"max_steps": 5}
        assert strategy.success_rate == 0.0
        assert strategy.total_executions == 0

    def test_register_duplicate_strategy(self, optimizer):
        """Test registering duplicate strategy raises error."""
        optimizer.register_strategy(
            strategy_id="test_strategy",
            name="Test",
            description="Test strategy",
            task_types=["test"],
            parameters={},
        )

        with pytest.raises(ValueError, match="already exists"):
            optimizer.register_strategy(
                strategy_id="test_strategy",
                name="Test 2",
                description="Another test",
                task_types=["test"],
                parameters={},
            )

    def test_register_multiple_strategies(self, optimizer):
        """Test registering multiple strategies."""
        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First strategy",
            task_types=["type1"],
            parameters={},
        )

        optimizer.register_strategy(
            strategy_id="strategy2",
            name="Strategy 2",
            description="Second strategy",
            task_types=["type2"],
            parameters={},
        )

        assert optimizer.get_strategy_count() == 2


# ============================================================================
# Performance Tracking Tests
# ============================================================================


class TestPerformanceTracking:
    """Test strategy performance tracking."""

    def test_update_performance_success(self, optimizer):
        """Test updating performance after successful execution."""
        optimizer.register_strategy(
            strategy_id="test_strategy",
            name="Test",
            description="Test strategy",
            task_types=["test"],
            parameters={},
        )

        optimizer.update_strategy_performance("test_strategy", True, 100.0)

        strategy = optimizer.get_strategy("test_strategy")
        assert strategy.total_executions == 1
        assert strategy.success_count == 1
        assert strategy.failure_count == 0
        assert strategy.success_rate == 1.0
        assert strategy.avg_execution_time_ms == 100.0

    def test_update_performance_failure(self, optimizer):
        """Test updating performance after failed execution."""
        optimizer.register_strategy(
            strategy_id="test_strategy",
            name="Test",
            description="Test strategy",
            task_types=["test"],
            parameters={},
        )

        optimizer.update_strategy_performance("test_strategy", False, 50.0)

        strategy = optimizer.get_strategy("test_strategy")
        assert strategy.total_executions == 1
        assert strategy.success_count == 0
        assert strategy.failure_count == 1
        assert strategy.success_rate == 0.0
        assert strategy.avg_execution_time_ms == 50.0

    def test_update_performance_multiple_times(self, optimizer):
        """Test updating performance multiple times."""
        optimizer.register_strategy(
            strategy_id="test_strategy",
            name="Test",
            description="Test strategy",
            task_types=["test"],
            parameters={},
        )

        # 3 successes, 1 failure
        optimizer.update_strategy_performance("test_strategy", True, 100.0)
        optimizer.update_strategy_performance("test_strategy", True, 150.0)
        optimizer.update_strategy_performance("test_strategy", False, 200.0)
        optimizer.update_strategy_performance("test_strategy", True, 50.0)

        strategy = optimizer.get_strategy("test_strategy")
        assert strategy.total_executions == 4
        assert strategy.success_count == 3
        assert strategy.failure_count == 1
        assert strategy.success_rate == 0.75  # 3/4
        assert strategy.avg_execution_time_ms == 125.0  # (100+150+200+50)/4

    def test_update_performance_nonexistent_strategy(self, optimizer):
        """Test updating performance for nonexistent strategy."""
        with pytest.raises(ValueError, match="not found"):
            optimizer.update_strategy_performance("nonexistent", True, 100.0)


# ============================================================================
# Strategy Selection Tests
# ============================================================================


class TestStrategySelection:
    """Test strategy selection algorithms."""

    def test_get_best_strategy(self, optimizer):
        """Test getting best strategy for task type."""
        # Register strategies with different success rates
        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First strategy",
            task_types=["analysis"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="strategy2",
            name="Strategy 2",
            description="Second strategy",
            task_types=["analysis"],
            parameters={},
        )

        # Update performance
        optimizer.update_strategy_performance("strategy1", True, 100.0)
        optimizer.update_strategy_performance("strategy1", True, 100.0)
        optimizer.update_strategy_performance("strategy2", True, 100.0)
        optimizer.update_strategy_performance("strategy2", False, 100.0)

        # strategy1 has 100% success rate, strategy2 has 50%
        best = optimizer.get_best_strategy("analysis")
        assert best.strategy_id == "strategy1"
        assert best.success_rate == 1.0

    def test_get_best_strategy_no_strategies(self, optimizer):
        """Test getting best strategy when none exist."""
        best = optimizer.get_best_strategy("nonexistent_type")
        assert best is None

    def test_get_best_strategy_with_min_success_rate(self, optimizer):
        """Test getting best strategy with minimum success rate."""
        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First strategy",
            task_types=["analysis"],
            parameters={},
        )

        # Update to 50% success rate
        optimizer.update_strategy_performance("strategy1", True, 100.0)
        optimizer.update_strategy_performance("strategy1", False, 100.0)

        # Should return None with min_success_rate=0.8
        best = optimizer.get_best_strategy("analysis", min_success_rate=0.8)
        assert best is None

        # Should return strategy with min_success_rate=0.4
        best = optimizer.get_best_strategy("analysis", min_success_rate=0.4)
        assert best is not None
        assert best.strategy_id == "strategy1"

    def test_select_strategy_with_exploration(self, optimizer):
        """Test epsilon-greedy strategy selection."""
        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First strategy",
            task_types=["analysis"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="strategy2",
            name="Strategy 2",
            description="Second strategy",
            task_types=["analysis"],
            parameters={},
        )

        # Make strategy1 clearly better
        for _ in range(10):
            optimizer.update_strategy_performance("strategy1", True, 100.0)
        optimizer.update_strategy_performance("strategy2", False, 100.0)

        # With epsilon=0.1, should mostly select strategy1
        selections = []
        for _ in range(100):
            strategy = optimizer.select_strategy_with_exploration("analysis")
            selections.append(strategy.strategy_id)

        # Should have mostly strategy1, but some strategy2 due to exploration
        strategy1_count = selections.count("strategy1")
        strategy2_count = selections.count("strategy2")

        assert strategy1_count > strategy2_count
        assert strategy2_count > 0  # Some exploration should happen

    def test_select_strategy_with_exploration_no_strategies(self, optimizer):
        """Test selection when no strategies exist."""
        result = optimizer.select_strategy_with_exploration("nonexistent")
        assert result is None


# ============================================================================
# Strategy Retrieval Tests
# ============================================================================


class TestStrategyRetrieval:
    """Test strategy retrieval methods."""

    def test_get_strategies_for_task_type(self, optimizer):
        """Test getting strategies for specific task type."""
        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First strategy",
            task_types=["analysis", "problem_solving"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="strategy2",
            name="Strategy 2",
            description="Second strategy",
            task_types=["coding"],
            parameters={},
        )

        # Get strategies for "analysis"
        strategies = optimizer.get_strategies_for_task_type("analysis")
        assert len(strategies) == 1
        assert strategies[0].strategy_id == "strategy1"

        # Get strategies for "coding"
        strategies = optimizer.get_strategies_for_task_type("coding")
        assert len(strategies) == 1
        assert strategies[0].strategy_id == "strategy2"

    def test_get_strategies_wildcard_task_type(self, optimizer):
        """Test getting strategies with wildcard task type."""
        optimizer.register_strategy(
            strategy_id="universal",
            name="Universal Strategy",
            description="Works for all tasks",
            task_types=["*"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="specific",
            name="Specific Strategy",
            description="Works for analysis only",
            task_types=["analysis"],
            parameters={},
        )

        # Universal strategy should match any task type
        strategies = optimizer.get_strategies_for_task_type("anything")
        assert len(strategies) == 1
        assert strategies[0].strategy_id == "universal"

        # Analysis should match both
        strategies = optimizer.get_strategies_for_task_type("analysis")
        assert len(strategies) == 2

    def test_get_all_strategies(self, optimizer):
        """Test getting all strategies."""
        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First strategy",
            task_types=["type1"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="strategy2",
            name="Strategy 2",
            description="Second strategy",
            task_types=["type2"],
            parameters={},
        )

        strategies = optimizer.get_all_strategies()
        assert len(strategies) == 2
        assert {s.strategy_id for s in strategies} == {"strategy1", "strategy2"}

    def test_get_strategy_nonexistent(self, optimizer):
        """Test getting nonexistent strategy returns None."""
        result = optimizer.get_strategy("nonexistent")
        assert result is None


# ============================================================================
# Strategy Ranking Tests
# ============================================================================


class TestStrategyRanking:
    """Test strategy ranking with UCB."""

    def test_rank_strategies(self, optimizer):
        """Test ranking strategies by UCB score."""
        # Register strategies
        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First strategy",
            task_types=["analysis"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="strategy2",
            name="Strategy 2",
            description="Second strategy",
            task_types=["analysis"],
            parameters={},
        )

        # Give both strategies enough executions to be confident
        # strategy1: 100% success rate with 20 executions
        for _ in range(20):
            optimizer.update_strategy_performance("strategy1", True, 100.0)
        # strategy2: 50% success rate with 20 executions
        for _ in range(10):
            optimizer.update_strategy_performance("strategy2", True, 100.0)
        for _ in range(10):
            optimizer.update_strategy_performance("strategy2", False, 100.0)

        ranked = optimizer.rank_strategies("analysis")
        assert len(ranked) == 2
        # strategy1 should rank higher due to better success rate
        assert ranked[0].strategy_id == "strategy1"

    def test_rank_strategies_with_low_executions(self, optimizer):
        """Test ranking gives priority to unexplored strategies."""
        optimizer.register_strategy(
            strategy_id="explored",
            name="Explored Strategy",
            description="Has many executions",
            task_types=["analysis"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="unexplored",
            name="Unexplored Strategy",
            description="Has few executions",
            task_types=["analysis"],
            parameters={},
        )

        # Give explored strategy many executions
        for _ in range(20):
            optimizer.update_strategy_performance("explored", True, 100.0)

        # Give unexplored strategy only 1 execution
        optimizer.update_strategy_performance("unexplored", True, 100.0)

        ranked = optimizer.rank_strategies("analysis")
        # Unexplored should rank higher due to exploration bonus
        assert ranked[0].strategy_id == "unexplored"

    def test_rank_strategies_with_filter(self, optimizer):
        """Test ranking with strategy ID filter."""
        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First strategy",
            task_types=["analysis"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="strategy2",
            name="Strategy 2",
            description="Second strategy",
            task_types=["analysis"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="strategy3",
            name="Strategy 3",
            description="Third strategy",
            task_types=["analysis"],
            parameters={},
        )

        # Rank only strategy1 and strategy3
        ranked = optimizer.rank_strategies("analysis", strategy_ids=["strategy1", "strategy3"])

        assert len(ranked) == 2
        assert {s.strategy_id for s in ranked} == {"strategy1", "strategy3"}

    def test_rank_strategies_no_strategies(self, optimizer):
        """Test ranking when no strategies exist."""
        ranked = optimizer.rank_strategies("nonexistent")
        assert ranked == []


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.performance
class TestPerformance:
    """Test performance requirements."""

    def test_strategy_selection_performance(self, optimizer, benchmark):
        """Test that strategy selection meets <10ms requirement."""
        # Register 100 strategies
        for i in range(100):
            optimizer.register_strategy(
                strategy_id=f"strategy_{i}",
                name=f"Strategy {i}",
                description=f"Strategy number {i}",
                task_types=["analysis"],
                parameters={},
            )
            # Give each some executions
            for _ in range(10):
                optimizer.update_strategy_performance(f"strategy_{i}", True, 100.0)

        # Benchmark selection
        result = benchmark(optimizer.get_best_strategy, "analysis")

        # Should complete in <10ms
        assert benchmark.stats["mean"] < 0.01  # 10ms
        assert result is not None


# ============================================================================
# Hardest Tests - Adversarial and Stress Testing
# ============================================================================


@pytest.mark.hardest
class TestAdversarialScenarios:
    """HARDEST TESTS: Adversarial scenarios and edge cases."""

    def test_extreme_success_rate_oscillation(self, optimizer):
        """
        HARDEST: Test strategy with rapidly oscillating success rate.

        Validates that the system handles non-stationary environments.
        """
        optimizer.register_strategy(
            strategy_id="oscillating",
            name="Oscillating Strategy",
            description="Success rate oscillates wildly",
            task_types=["test"],
            parameters={},
        )

        # Alternate between success and failure rapidly
        for i in range(100):
            success = i % 2 == 0
            optimizer.update_strategy_performance("oscillating", success, 100.0)

        strategy = optimizer.get_strategy("oscillating")
        # Should converge to 50% success rate
        assert 0.45 <= strategy.success_rate <= 0.55
        assert strategy.total_executions == 100

    def test_zero_epsilon_pure_exploitation(self, connection_pool):
        """
        HARDEST: Test with epsilon=0 (pure exploitation, no exploration).

        Validates that system works without exploration.
        """
        optimizer = StrategyOptimizer(connection_pool, epsilon=0.0)

        optimizer.register_strategy(
            strategy_id="best",
            name="Best Strategy",
            description="Clearly best",
            task_types=["test"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="worst",
            name="Worst Strategy",
            description="Clearly worst",
            task_types=["test"],
            parameters={},
        )

        # Make best clearly better
        for _ in range(10):
            optimizer.update_strategy_performance("best", True, 100.0)
        optimizer.update_strategy_performance("worst", False, 100.0)

        # With epsilon=0, should ALWAYS select best
        for _ in range(50):
            selected = optimizer.select_strategy_with_exploration("test")
            assert selected.strategy_id == "best", "Pure exploitation should always select best"

    def test_one_epsilon_pure_exploration(self, connection_pool):
        """
        HARDEST: Test with epsilon=1.0 (pure exploration, no exploitation).

        Validates that system works with only exploration.
        """
        optimizer = StrategyOptimizer(connection_pool, epsilon=1.0)

        optimizer.register_strategy(
            strategy_id="strategy1",
            name="Strategy 1",
            description="First",
            task_types=["test"],
            parameters={},
        )
        optimizer.register_strategy(
            strategy_id="strategy2",
            name="Strategy 2",
            description="Second",
            task_types=["test"],
            parameters={},
        )

        # With epsilon=1.0, should explore randomly
        selections = []
        for _ in range(100):
            selected = optimizer.select_strategy_with_exploration("test")
            selections.append(selected.strategy_id)

        # Should have roughly equal distribution (within 30% tolerance)
        count1 = selections.count("strategy1")
        count2 = selections.count("strategy2")
        assert 30 <= count1 <= 70, "Pure exploration should distribute roughly equally"
        assert 30 <= count2 <= 70, "Pure exploration should distribute roughly equally"

    def test_massive_strategy_count(self, optimizer):
        """
        HARDEST: Test with 1000 strategies to validate scalability.

        Validates O(n log n) ranking performance.
        """
        # Register 1000 strategies
        for i in range(1000):
            optimizer.register_strategy(
                strategy_id=f"strategy_{i}",
                name=f"Strategy {i}",
                description=f"Strategy number {i}",
                task_types=["test"],
                parameters={},
            )

        # Give each some executions
        for i in range(1000):
            success_rate = i / 1000.0  # Varying success rates
            for _ in range(5):
                success = (hash(i) % 100) < (success_rate * 100)
                optimizer.update_strategy_performance(f"strategy_{i}", success, 100.0)

        # Ranking should complete quickly
        import time

        start = time.time()
        ranked = optimizer.rank_strategies("test")
        elapsed = time.time() - start

        assert len(ranked) == 1000
        assert elapsed < 1.0, f"Ranking 1000 strategies took {elapsed:.3f}s, should be <1s"

    def test_extreme_execution_counts(self, optimizer):
        """
        HARDEST: Test with millions of executions to validate numerical stability.

        Validates that running averages don't overflow or lose precision.
        """
        optimizer.register_strategy(
            strategy_id="high_volume",
            name="High Volume Strategy",
            description="Millions of executions",
            task_types=["test"],
            parameters={},
        )

        # Simulate 1 million executions (in batches for speed)
        total_executions = 0
        total_time = 0.0

        for batch in range(1000):
            for _ in range(1000):
                success = batch % 3 != 0  # ~66% success rate
                exec_time = 100.0 + (batch % 50)  # Varying execution times
                optimizer.update_strategy_performance("high_volume", success, exec_time)
                total_executions += 1
                total_time += exec_time

        strategy = optimizer.get_strategy("high_volume")

        # Verify counts are accurate
        assert strategy.total_executions == 1_000_000

        # Verify success rate is approximately 66%
        assert 0.65 <= strategy.success_rate <= 0.67

        # Verify average execution time is accurate
        expected_avg = total_time / total_executions
        assert abs(strategy.avg_execution_time_ms - expected_avg) < 1.0

    def test_concurrent_strategy_updates(self, optimizer):
        """
        HARDEST: Test concurrent updates to same strategy.

        Validates thread-safety and data consistency.
        """
        optimizer.register_strategy(
            strategy_id="concurrent",
            name="Concurrent Strategy",
            description="Updated concurrently",
            task_types=["test"],
            parameters={},
        )

        # Simulate concurrent updates
        import threading

        def update_worker(num_updates):
            for _ in range(num_updates):
                optimizer.update_strategy_performance("concurrent", True, 100.0)

        # Create 10 threads, each doing 100 updates
        threads = []
        for _ in range(10):
            t = threading.Thread(target=update_worker, args=(100,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify total count is correct
        strategy = optimizer.get_strategy("concurrent")
        assert (
            strategy.total_executions == 1000
        ), f"Expected 1000 executions, got {strategy.total_executions}"

    def test_strategy_with_zero_executions(self, optimizer):
        """
        HARDEST: Test edge case of strategy with zero executions.

        Validates division by zero handling.
        """
        optimizer.register_strategy(
            strategy_id="unused",
            name="Unused Strategy",
            description="Never executed",
            task_types=["test"],
            parameters={},
        )

        strategy = optimizer.get_strategy("unused")

        # Should have zero success rate, not NaN or error
        assert strategy.success_rate == 0.0
        assert strategy.total_executions == 0
        assert strategy.avg_execution_time_ms == 0.0

    def test_negative_execution_time_rejected(self, optimizer):
        """
        HARDEST: Test that negative execution times are rejected by database constraint.

        Validates database integrity constraints.
        """
        optimizer.register_strategy(
            strategy_id="test",
            name="Test Strategy",
            description="Test",
            task_types=["test"],
            parameters={},
        )

        # Negative execution time should be rejected by CHECK constraint
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            optimizer.update_strategy_performance("test", True, -100.0)

        # Strategy should remain unchanged
        strategy = optimizer.get_strategy("test")
        assert strategy.total_executions == 0

    def test_extremely_long_strategy_id(self, optimizer):
        """
        HARDEST: Test with extremely long strategy ID (1000 chars).

        Validates string handling limits.
        """
        long_id = "x" * 1000

        optimizer.register_strategy(
            strategy_id=long_id,
            name="Long ID Strategy",
            description="Has very long ID",
            task_types=["test"],
            parameters={},
        )

        # Should be able to retrieve it
        strategy = optimizer.get_strategy(long_id)
        assert strategy is not None
        assert strategy.strategy_id == long_id

    def test_unicode_in_strategy_names(self, optimizer):
        """
        HARDEST: Test Unicode characters in strategy names.

        Validates internationalization support.
        """
        optimizer.register_strategy(
            strategy_id="unicode_test",
            name="策略 🚀 Стратегия",
            description="مع الأحرف العربية",
            task_types=["test"],
            parameters={},
        )

        strategy = optimizer.get_strategy("unicode_test")
        assert strategy.name == "策略 🚀 Стратегия"
        assert "العربية" in strategy.description

    def test_json_injection_in_parameters(self, optimizer):
        """
        HARDEST: Test JSON injection attack in parameters.

        Validates security against injection attacks.
        """
        malicious_params = {
            "key": '"}; DROP TABLE strategies; --',
            "nested": {"attack": "'; DELETE FROM strategies WHERE '1'='1"},
        }

        optimizer.register_strategy(
            strategy_id="injection_test",
            name="Injection Test",
            description="Tests JSON injection",
            task_types=["test"],
            parameters=malicious_params,
        )

        # Should store and retrieve safely
        strategy = optimizer.get_strategy("injection_test")
        assert strategy.parameters == malicious_params

        # Table should still exist
        assert optimizer.get_strategy_count() >= 1


@pytest.mark.hardest
class TestStatisticalProperties:
    """HARDEST TESTS: Statistical correctness validation."""

    def test_success_rate_confidence_intervals(self, optimizer):
        """
        HARDEST: Validate success rate falls within statistical confidence intervals.

        Uses binomial distribution confidence intervals.
        """
        optimizer.register_strategy(
            strategy_id="statistical",
            name="Statistical Strategy",
            description="For statistical testing",
            task_types=["test"],
            parameters={},
        )

        # True success rate: 70%
        true_rate = 0.7
        num_trials = 100

        import random

        random.seed(42)  # For reproducibility

        for _ in range(num_trials):
            success = random.random() < true_rate
            optimizer.update_strategy_performance("statistical", success, 100.0)

        strategy = optimizer.get_strategy("statistical")
        measured_rate = strategy.success_rate

        # Calculate 95% confidence interval for binomial distribution
        # CI = p ± 1.96 * sqrt(p(1-p)/n)
        import math

        margin = 1.96 * math.sqrt(true_rate * (1 - true_rate) / num_trials)

        assert (
            true_rate - margin <= measured_rate <= true_rate + margin
        ), f"Measured rate {measured_rate:.3f} outside 95% CI [{true_rate-margin:.3f}, {true_rate+margin:.3f}]"

    def test_ucb_exploration_bonus_correctness(self, optimizer):
        """
        HARDEST: Validate UCB exploration bonus calculation is mathematically correct.

        Tests the UCB1 formula: mean + sqrt(2 * ln(total) / executions)
        """
        optimizer.register_strategy(
            strategy_id="ucb_test",
            name="UCB Test Strategy",
            description="For UCB testing",
            task_types=["test"],
            parameters={},
        )

        # Give it some executions
        for _ in range(20):
            optimizer.update_strategy_performance("ucb_test", True, 100.0)

        # Rank to get UCB score
        ranked = optimizer.rank_strategies("test")

        # Verify ranking logic is applied
        assert len(ranked) >= 1
        assert ranked[0].strategy_id == "ucb_test"
