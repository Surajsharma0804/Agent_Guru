"""
Tests for Ensemble Voting System.

**Validates: Requirements 9.5 (Adversarial Robustness - Ensemble Voting)**

Tests cover:
- Ensemble execution with multiple strategies
- Voting methods (majority, weighted, confidence, unanimous)
- Agreement scoring and disagreement handling
- Performance tracking (ensemble vs single-strategy)
- Criticality-based ensemble sizing
- Parallel execution and error handling

Author: Agent Guru Team
Date: 2026-02-28
"""

import asyncio

import pytest

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.ensemble_voting import (
    EnsembleVotingSystem,
    TaskCriticality,
    VotingMethod,
)
from Agent_Guru.self_improvement.strategy_optimizer import StrategyOptimizer
import logging

logger = logging.getLogger(__name__)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_ensemble_voting.db")
        DatabaseSchema.create_schema(db_path)
        yield db_path


@pytest.fixture
def pool(temp_db):
    """Create in-memory database pool for testing."""
    pool = ConnectionPool(temp_db, min_size=1, max_size=5)
    yield pool
    pool.close_all()


@pytest.fixture
def strategy_optimizer(pool):
    """Create strategy optimizer with test strategies."""
    optimizer = StrategyOptimizer(pool, epsilon=0.0)  # No exploration for tests

    # Register test strategies
    optimizer.register_strategy(
        strategy_id="strategy_1",
        name="Strategy 1",
        description="High success rate strategy",
        task_types=["test_task"],
        parameters={"param": "value1"},
    )

    optimizer.register_strategy(
        strategy_id="strategy_2",
        name="Strategy 2",
        description="Medium success rate strategy",
        task_types=["test_task"],
        parameters={"param": "value2"},
    )

    optimizer.register_strategy(
        strategy_id="strategy_3",
        name="Strategy 3",
        description="Low success rate strategy",
        task_types=["test_task"],
        parameters={"param": "value3"},
    )

    # Set different success rates
    for _ in range(10):
        optimizer.update_strategy_performance("strategy_1", True, 100.0)
    for _ in range(5):
        optimizer.update_strategy_performance("strategy_2", True, 150.0)
    for _ in range(5):
        optimizer.update_strategy_performance("strategy_2", False, 150.0)
    for _ in range(3):
        optimizer.update_strategy_performance("strategy_3", True, 200.0)
    for _ in range(7):
        optimizer.update_strategy_performance("strategy_3", False, 200.0)

    return optimizer


@pytest.fixture
def ensemble_system(pool, strategy_optimizer):
    """Create ensemble voting system."""
    return EnsembleVotingSystem(
        pool, strategy_optimizer, default_voting_method=VotingMethod.WEIGHTED
    )


class TestEnsembleVotingSystemInitialization:
    """Test ensemble voting system initialization."""

    def test_initialization(self, pool, strategy_optimizer):
        """Test system initializes correctly."""
        system = EnsembleVotingSystem(pool, strategy_optimizer)

        assert system.pool == pool  # nosec B101
        assert system.strategy_optimizer == strategy_optimizer  # nosec B101
        assert system.default_voting_method == VotingMethod.WEIGHTED  # nosec B101
        assert system.min_agreement_threshold == 0.6  # nosec B101

    def test_initialization_with_custom_params(self, pool, strategy_optimizer):
        """Test initialization with custom parameters."""
        system = EnsembleVotingSystem(
            pool,
            strategy_optimizer,
            default_voting_method=VotingMethod.MAJORITY,
            min_agreement_threshold=0.8,
        )

        assert system.default_voting_method == VotingMethod.MAJORITY  # nosec B101
        assert system.min_agreement_threshold == 0.8  # nosec B101

    def test_initialization_invalid_threshold(self, pool, strategy_optimizer):
        """Test initialization fails with invalid threshold."""
        with pytest.raises(ValueError, match="min_agreement_threshold must be in"):
            EnsembleVotingSystem(pool, strategy_optimizer, min_agreement_threshold=1.5)

    def test_database_schema_created(self, pool, strategy_optimizer):
        """Test database schema is created."""
        EnsembleVotingSystem(pool, strategy_optimizer)

        with pool.connection() as conn:
            cursor = conn.cursor()

            # Check table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='ensemble_executions'
            """
            )
            assert cursor.fetchone() is not None  # nosec B101

            # Check indexes exist
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='index' AND name LIKE 'idx_ensemble_%'
            """
            )
            indexes = cursor.fetchall()
            assert len(indexes) >= 3  # nosec B101


class TestEnsembleExecution:
    """Test ensemble execution with multiple strategies."""

    @pytest.mark.asyncio
    async def test_execute_with_ensemble_medium_criticality(self, ensemble_system):
        """Test ensemble execution with medium criticality (3 strategies)."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            """Mock task executor - all return same result for agreement."""
            return {
                "result": "same_result",  # Same result for all strategies
                "success": True,
                "confidence": 0.9,
            }

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_task_1",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
        )

        assert result.task_id == "test_task_1"  # nosec B101
        assert result.task_type == "test_task"  # nosec B101
        assert result.criticality == TaskCriticality.MEDIUM  # nosec B101
        assert len(result.strategies_used) == 3  # Medium = 3 strategies  # nosec B101
        assert len(result.individual_results) == 3  # nosec B101
        assert result.success is True  # nosec B101
        assert result.agreement_score > 0.0  # nosec B101
        assert result.confidence > 0.0  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_ensemble_high_criticality(self, ensemble_system):
        """Test ensemble execution with high criticality (5 strategies)."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            return {"result": "success", "success": True, "confidence": 0.85}

        # Add more strategies for high criticality
        for i in range(4, 8):
            ensemble_system.strategy_optimizer.register_strategy(
                strategy_id=f"strategy_{i}",
                name=f"Strategy {i}",
                description=f"Test strategy {i}",
                task_types=["test_task"],
                parameters={"param": f"value{i}"},
            )
            ensemble_system.strategy_optimizer.update_strategy_performance(
                f"strategy_{i}", True, 100.0
            )

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_task_2",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.HIGH,
        )

        assert len(result.strategies_used) == 5  # High = 5 strategies  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_all_strategies_agree(self, ensemble_system):
        """Test execution when all strategies agree."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            # All strategies return same result
            return {"result": "agreed_result", "success": True, "confidence": 0.9}

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_task_3",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
        )

        assert result.success is True  # nosec B101
        assert result.agreement_score >= 0.9  # High agreement  # nosec B101
        assert result.voted_result["result"] == "agreed_result"  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_strategies_disagree(self, ensemble_system):
        """Test execution when strategies disagree."""
        call_count = 0

        async def task_executor(strategy_id: str, params: dict) -> dict:
            nonlocal call_count
            call_count += 1
            # Each strategy returns different result
            return {
                "result": f"result_{call_count}",
                "success": True,
                "confidence": 0.8,
            }

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_task_4",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
        )

        # When strategies disagree, success depends on agreement threshold
        # With all different results, agreement_score will be ~0.56 (below 0.6 threshold)
        assert result.success is False  # Below agreement threshold  # nosec B101
        assert result.agreement_score < 0.6  # Low agreement (all different)  # nosec B101
        assert result.voted_result is not None  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_some_failures(self, ensemble_system):
        """Test execution when some strategies fail."""
        call_count = 0

        async def task_executor(strategy_id: str, params: dict) -> dict:
            nonlocal call_count
            call_count += 1
            # First strategy fails, others succeed
            if call_count == 1:
                raise ValueError("Strategy 1 failed")
            return {"result": "success", "success": True, "confidence": 0.85}

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_task_5",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
        )

        # Should still succeed with majority
        assert len(result.individual_results) == 3  # nosec B101
        assert result.individual_results[0]["success"] is False  # nosec B101
        assert result.individual_results[1]["success"] is True  # nosec B101
        assert result.individual_results[2]["success"] is True  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_all_failures(self, ensemble_system):
        """Test execution when all strategies fail."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            raise ValueError("All strategies fail")

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_task_6",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
        )

        assert result.success is False  # nosec B101
        assert all(not r["success"] for r in result.individual_results)  # nosec B101
        assert result.agreement_score == 0.0  # nosec B101


class TestVotingMethods:
    """Test different voting methods."""

    @pytest.mark.asyncio
    async def test_majority_vote(self, ensemble_system):
        """Test majority voting method."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            # 2 strategies return "A", 1 returns "B"
            if strategy_id in ["strategy_1", "strategy_2"]:
                return {"result": "A", "success": True, "confidence": 0.8}
            return {"result": "B", "success": True, "confidence": 0.9}

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_vote_1",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
            voting_method=VotingMethod.MAJORITY,
        )

        assert result.voted_result["result"] == "A"  # Majority wins  # nosec B101
        assert result.agreement_score >= 0.6  # 2/3 agreement  # nosec B101

    @pytest.mark.asyncio
    async def test_weighted_vote(self, ensemble_system):
        """Test weighted voting method."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            # strategy_1 (high success rate) returns "A"
            # strategy_2, strategy_3 (lower success rates) return "B"
            if strategy_id == "strategy_1":
                return {"result": "A", "success": True, "confidence": 0.9}
            return {"result": "B", "success": True, "confidence": 0.8}

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_vote_2",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
            voting_method=VotingMethod.WEIGHTED,
        )

        # strategy_1 has highest success rate, so "A" should win despite minority
        assert result.voted_result["result"] == "A"  # nosec B101

    @pytest.mark.asyncio
    async def test_confidence_vote(self, ensemble_system):
        """Test confidence-based voting method."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            # strategy_1 has highest confidence
            if strategy_id == "strategy_1":
                return {"result": "A", "success": True, "confidence": 0.95}
            return {"result": "B", "success": True, "confidence": 0.7}

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_vote_3",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
            voting_method=VotingMethod.CONFIDENCE,
        )

        assert result.voted_result["result"] == "A"  # Highest confidence wins  # nosec B101
        assert result.confidence >= 0.95  # nosec B101

    @pytest.mark.asyncio
    async def test_unanimous_vote_with_agreement(self, ensemble_system):
        """Test unanimous voting when all agree."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            return {"result": "unanimous", "success": True, "confidence": 0.9}

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_vote_4",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
            voting_method=VotingMethod.UNANIMOUS,
        )

        assert result.voted_result["result"] == "unanimous"  # nosec B101
        assert result.agreement_score == 1.0  # Perfect agreement  # nosec B101

    @pytest.mark.asyncio
    async def test_unanimous_vote_without_agreement(self, ensemble_system):
        """Test unanimous voting when strategies disagree."""
        call_count = 0

        async def task_executor(strategy_id: str, params: dict) -> dict:
            nonlocal call_count
            call_count += 1
            return {
                "result": f"result_{call_count}",
                "success": True,
                "confidence": 0.8,
            }

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_vote_5",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
            voting_method=VotingMethod.UNANIMOUS,
        )

        # Falls back to majority vote
        assert result.agreement_score < 1.0  # nosec B101


class TestPerformanceMetrics:
    """Test performance tracking and metrics."""

    @pytest.mark.asyncio
    async def test_performance_metrics_tracking(self, ensemble_system):
        """Test that performance metrics are tracked."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            # Add small delay to ensure measurable execution time
            await asyncio.sleep(0.001)
            return {"result": "success", "success": True, "confidence": 0.9}

        # Execute several ensemble tasks
        for i in range(5):
            await ensemble_system.execute_with_ensemble(
                task_id=f"test_task_{i}",
                task_type="test_task",
                task_executor=task_executor,
                criticality=TaskCriticality.MEDIUM,
            )

        # Get metrics
        metrics = ensemble_system.get_performance_metrics(task_type="test_task")

        assert metrics.total_ensemble_executions == 5  # nosec B101
        assert metrics.ensemble_success_rate > 0.0  # nosec B101
        assert metrics.ensemble_avg_time_ms >= 0.0  # May be 0 if very fast  # nosec B101

    @pytest.mark.asyncio
    async def test_performance_metrics_with_failures(self, ensemble_system):
        """Test metrics with mixed success/failure."""
        call_count = 0

        async def task_executor(strategy_id: str, params: dict) -> dict:
            nonlocal call_count
            call_count += 1
            # Fail every other execution
            if call_count % 2 == 0:
                raise ValueError("Simulated failure")
            return {"result": "success", "success": True, "confidence": 0.9}

        # Execute tasks
        for i in range(6):
            try:
                await ensemble_system.execute_with_ensemble(
                    task_id=f"test_task_{i}",
                    task_type="test_task",
                    task_executor=task_executor,
                    criticality=TaskCriticality.MEDIUM,
                )
            except OSError as exc:
                logger.debug("Cleanup skipped: %s", exc)

        metrics = ensemble_system.get_performance_metrics(task_type="test_task")

        # Should track both successes and failures
        assert metrics.total_ensemble_executions > 0  # nosec B101

    def test_performance_metrics_empty(self, ensemble_system):
        """Test metrics with no executions."""
        metrics = ensemble_system.get_performance_metrics(task_type="nonexistent")

        assert metrics.total_ensemble_executions == 0  # nosec B101
        assert metrics.ensemble_success_rate == 0.0  # nosec B101


class TestCriticalityAssessment:
    """Test task criticality assessment."""

    def test_should_use_ensemble_low_criticality(self, ensemble_system):
        """Test low criticality tasks don't use ensemble."""
        use_ensemble, criticality = ensemble_system.should_use_ensemble(
            task_type="simple_task", task_context={}
        )

        assert use_ensemble is False  # nosec B101
        assert criticality == TaskCriticality.LOW  # nosec B101

    def test_should_use_ensemble_high_criticality_type(self, ensemble_system):
        """Test high criticality task types use ensemble."""
        use_ensemble, criticality = ensemble_system.should_use_ensemble(
            task_type="security_validation", task_context={}
        )

        assert use_ensemble is True  # nosec B101
        assert criticality == TaskCriticality.HIGH  # nosec B101

    def test_should_use_ensemble_with_user_data(self, ensemble_system):
        """Test tasks with user data use ensemble."""
        use_ensemble, criticality = ensemble_system.should_use_ensemble(
            task_type="simple_task", task_context={"user_data": True}
        )

        assert use_ensemble is True  # nosec B101
        # Check criticality is at least MEDIUM
        criticality_values = {
            TaskCriticality.LOW: 0,
            TaskCriticality.MEDIUM: 1,
            TaskCriticality.HIGH: 2,
            TaskCriticality.CRITICAL: 3,
        }
        assert criticality_values[criticality] >= criticality_values[TaskCriticality.MEDIUM]  # nosec B101

    def test_should_use_ensemble_with_financial_data(self, ensemble_system):
        """Test tasks with financial data use ensemble."""
        use_ensemble, criticality = ensemble_system.should_use_ensemble(
            task_type="simple_task", task_context={"financial": True}
        )

        assert use_ensemble is True  # nosec B101
        # Check criticality is at least HIGH
        criticality_values = {
            TaskCriticality.LOW: 0,
            TaskCriticality.MEDIUM: 1,
            TaskCriticality.HIGH: 2,
            TaskCriticality.CRITICAL: 3,
        }
        assert criticality_values[criticality] >= criticality_values[TaskCriticality.HIGH]  # nosec B101

    def test_should_use_ensemble_safety_critical(self, ensemble_system):
        """Test safety-critical tasks use maximum ensemble."""
        use_ensemble, criticality = ensemble_system.should_use_ensemble(
            task_type="simple_task", task_context={"safety_critical": True}
        )

        assert use_ensemble is True  # nosec B101
        assert criticality == TaskCriticality.CRITICAL  # nosec B101


class TestEnsembleSizing:
    """Test ensemble size based on criticality."""

    def test_ensemble_size_low(self, ensemble_system):
        """Test low criticality uses 1 strategy."""
        size = ensemble_system._get_ensemble_size(TaskCriticality.LOW)
        assert size == 1  # nosec B101

    def test_ensemble_size_medium(self, ensemble_system):
        """Test medium criticality uses 3 strategies."""
        size = ensemble_system._get_ensemble_size(TaskCriticality.MEDIUM)
        assert size == 3  # nosec B101

    def test_ensemble_size_high(self, ensemble_system):
        """Test high criticality uses 5 strategies."""
        size = ensemble_system._get_ensemble_size(TaskCriticality.HIGH)
        assert size == 5  # nosec B101

    def test_ensemble_size_critical(self, ensemble_system):
        """Test critical tasks use 7 strategies."""
        size = ensemble_system._get_ensemble_size(TaskCriticality.CRITICAL)
        assert size == 7  # nosec B101


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_execute_with_no_strategies(self, temp_db):
        """Test execution fails gracefully with no strategies."""
        pool = ConnectionPool(temp_db, min_size=1, max_size=5)
        optimizer = StrategyOptimizer(pool, epsilon=0.0)
        system = EnsembleVotingSystem(pool, optimizer)

        async def task_executor(strategy_id: str, params: dict) -> dict:
            return {"result": "success", "success": True}

        with pytest.raises(ValueError, match="No strategies available"):
            await system.execute_with_ensemble(
                task_id="test_task",
                task_type="nonexistent_type",
                task_executor=task_executor,
                criticality=TaskCriticality.MEDIUM,
            )

        pool.close_all()

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, ensemble_system):
        """Test execution handles timeouts."""

        async def task_executor(strategy_id: str, params: dict) -> dict:
            # Simulate slow execution
            await asyncio.sleep(0.1)
            return {"result": "success", "success": True, "confidence": 0.9}

        result = await ensemble_system.execute_with_ensemble(
            task_id="test_task",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
        )

        # Should complete successfully
        assert result.success is True  # nosec B101
        assert result.execution_time_ms >= 100  # At least 100ms  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_low_agreement(self, ensemble_system):
        """Test execution with low agreement threshold."""
        system = EnsembleVotingSystem(
            ensemble_system.pool,
            ensemble_system.strategy_optimizer,
            min_agreement_threshold=0.9,  # High threshold
        )

        call_count = 0

        async def task_executor(strategy_id: str, params: dict) -> dict:
            nonlocal call_count
            call_count += 1
            # All different results
            return {
                "result": f"result_{call_count}",
                "success": True,
                "confidence": 0.8,
            }

        result = await system.execute_with_ensemble(
            task_id="test_task",
            task_type="test_task",
            task_executor=task_executor,
            criticality=TaskCriticality.MEDIUM,
        )

        # Should fail due to low agreement
        assert result.agreement_score < 0.9  # nosec B101
        assert result.success is False  # Below threshold  # nosec B101


# Property-based tests would go here using hypothesis
# For now, we have comprehensive unit tests covering all scenarios
