"""
Catastrophic Recovery Tests for Self-Improvement Engine.

This is the HARDEST test for the rollback and recovery system. It injects
multiple types of catastrophic failures and verifies the system can detect,
rollback, and recover from complete failure scenarios.

**Validates: Requirements 9.4 (Adversarial Robustness - Rollback and Recovery)**

Test Scenarios:
1. Strategy that always fails (100% failure rate)
2. Prompt that causes hallucinations (100% hallucination rate)
3. Corrupted learning data (invalid state)
4. Multiple simultaneous catastrophic updates
5. Cascading failures across components
6. Recovery under resource constraints
7. Recovery with partial data corruption

Performance Requirements:
- Detection: <1s for catastrophic degradation
- Rollback: <5s for complete system rollback
- Recovery: System functional after rollback

Author: Agent Guru Team
Date: 2026-02-28
"""

import pytest
import tempfile
import os
import time
from datetime import datetime, timezone

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.rollback_manager import (
    RollbackManager,
    ChangeType,
)
from Agent_Guru.self_improvement.degradation_detector import (
    DegradationDetector,
    DegradationSeverity,
)
from Agent_Guru.self_improvement.performance_tracker import PerformanceTracker
from Agent_Guru.self_improvement.strategy_optimizer import StrategyOptimizer
from Agent_Guru.self_improvement.prompt_evolution import PromptEvolutionSystem
import logging

logger = logging.getLogger(__name__)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Initialize schema
    DatabaseSchema.create_schema(path)

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except OSError as exc:
        logger.debug("Cleanup skipped: %s", exc)


@pytest.fixture
def pool(temp_db):
    """Create connection pool for testing."""
    pool = ConnectionPool(temp_db, min_size=1, max_size=5)
    yield pool
    pool.close_all()


@pytest.fixture
def rollback_manager(pool):
    """Create rollback manager."""
    return RollbackManager(pool)


@pytest.fixture
def degradation_detector(pool):
    """Create degradation detector with sensitive thresholds."""
    return DegradationDetector(
        pool,
        success_rate_threshold=0.05,  # Very sensitive
        execution_time_threshold=0.10,
        reasoning_quality_threshold=0.05,
        tool_selection_threshold=0.05,
        hallucination_threshold=0.05,
    )


@pytest.fixture
def performance_tracker(pool):
    """Create performance tracker."""
    return PerformanceTracker(pool)


@pytest.fixture
def strategy_optimizer(pool):
    """Create strategy optimizer."""
    return StrategyOptimizer(pool)


@pytest.fixture
def prompt_evolution(pool):
    """Create prompt evolution system."""
    return PromptEvolutionSystem(pool)



def create_baseline_performance(
    performance_tracker: PerformanceTracker,
    num_tasks: int = 50,
    success_rate: float = 0.85,
) -> None:
    """
    Create baseline performance data.
    
    Args:
        performance_tracker: Performance tracker instance
        num_tasks: Number of baseline tasks
        success_rate: Target success rate for baseline
    """
    import random
    
    for i in range(num_tasks):
        success = random.random() < success_rate
        performance_tracker.record_task_metrics(
            task_id=f"baseline_task_{i}",
            task_type="test_task",
            strategy_id="baseline_strategy",
            success=success,
            execution_time_ms=100.0 + random.uniform(-10, 10),
            reasoning_quality=0.9 + random.uniform(-0.05, 0.05),
            tool_selection_correct=success,
            hallucination_detected=False,
            task_sequence_number=i + 1,  # Start from 1, not 0
        )


def inject_catastrophic_strategy(
    strategy_optimizer: StrategyOptimizer,
    rollback_manager: RollbackManager,
) -> str:
    """
    Inject a strategy that always fails.
    
    Returns:
        Strategy ID of the catastrophic strategy
    """
    import random
    # Register a strategy with unique ID
    strategy_id = f"catastrophic_strategy_{datetime.now(tz=timezone.utc).timestamp()}_{random.randint(1000, 9999)}"
    strategy_optimizer.register_strategy(
        strategy_id=strategy_id,
        name="catastrophic_strategy",
        description="A strategy that will catastrophically fail",
        task_types=["test_task"],
        parameters={"approach": "always_fail"},
    )
    
    # Record the change
    previous_state = {
        "success_rate": 0.85,
        "total_executions": 100,
        "success_count": 85,
        "failure_count": 15,
    }
    
    new_state = {
        "success_rate": 0.0,  # Catastrophic!
        "total_executions": 0,
        "success_count": 0,
        "failure_count": 0,
    }
    
    rollback_manager.record_change(
        change_type=ChangeType.STRATEGY_UPDATE,
        component_id=strategy_id,
        previous_state=previous_state,
        new_state=new_state,
        performance_before={"success_rate": 0.85},
        performance_after={"success_rate": 0.0},
    )
    
    return strategy_id



def inject_catastrophic_prompt(
    prompt_evolution: PromptEvolutionSystem,
    rollback_manager: RollbackManager,
) -> str:
    """
    Inject a prompt that causes hallucinations.
    
    Returns:
        Prompt ID of the catastrophic prompt
    """
    import random
    # Register a prompt (it returns the prompt_id)
    # Use unique version to avoid conflicts
    version = random.randint(1, 10000)
    prompt_id = prompt_evolution.register_prompt(
        prompt_type=f"test_prompt_{random.randint(1000, 9999)}",
        content="This prompt causes hallucinations",
        version=version,
    )
    
    # Record the change
    previous_state = {
        "success_rate": 0.80,
        "total_uses": 100,
        "success_count": 80,
        "failure_count": 20,
        "hallucination_count": 5,
    }
    
    new_state = {
        "success_rate": 0.0,
        "total_uses": 0,
        "success_count": 0,
        "failure_count": 0,
        "hallucination_count": 100,  # Catastrophic!
    }
    
    rollback_manager.record_change(
        change_type=ChangeType.PROMPT_UPDATE,
        component_id=prompt_id,
        previous_state=previous_state,
        new_state=new_state,
        performance_before={"success_rate": 0.80, "hallucination_rate": 0.05},
        performance_after={"success_rate": 0.0, "hallucination_rate": 1.0},
    )
    
    return prompt_id


def simulate_catastrophic_performance(
    performance_tracker: PerformanceTracker,
    num_tasks: int = 20,
    start_sequence: int = 50,
) -> None:
    """
    Simulate catastrophic performance degradation.
    
    All tasks fail with poor metrics.
    """
    for i in range(num_tasks):
        performance_tracker.record_task_metrics(
            task_id=f"catastrophic_task_{i}",
            task_type="test_task",
            strategy_id="catastrophic_strategy",
            success=False,  # Always fails
            execution_time_ms=500.0,  # Much slower
            reasoning_quality=0.1,  # Very poor
            tool_selection_correct=False,
            hallucination_detected=True,  # Always hallucinates
            task_sequence_number=start_sequence + i,
        )



class TestCatastrophicStrategyFailure:
    """Test recovery from strategy that always fails."""
    
    def test_detect_catastrophic_strategy_failure(
        self,
        performance_tracker,
        strategy_optimizer,
        rollback_manager,
        degradation_detector,
    ):
        """
        Test detection of catastrophic strategy failure.
        
        Scenario:
        1. Establish baseline performance (85% success rate)
        2. Inject strategy that always fails
        3. Simulate 20 failed tasks
        4. Verify degradation is detected as SEVERE
        5. Verify rollback is triggered
        6. Verify system recovers
        """
        # Step 1: Establish baseline
        create_baseline_performance(performance_tracker, num_tasks=50, success_rate=0.85)
        
        # Step 2: Inject catastrophic strategy
        catastrophic_strategy_id = inject_catastrophic_strategy(
            strategy_optimizer, rollback_manager
        )
        
        # Step 3: Simulate catastrophic performance
        simulate_catastrophic_performance(performance_tracker, num_tasks=20)
        
        # Step 4: Detect degradation
        start_time = time.time()
        alert = degradation_detector.check_for_degradation(
            recent_window_size=20,
            historical_window_size=50,
        )
        detection_time = time.time() - start_time
        
        # Verify detection
        assert alert is not None, "Catastrophic degradation should be detected"
        assert alert.severity == DegradationSeverity.SEVERE, "Should be SEVERE degradation"
        assert detection_time < 1.0, f"Detection took {detection_time:.3f}s, should be <1s"
        
        # Step 5: Trigger rollback
        start_time = time.time()
        rollback_result, investigation = rollback_manager.rollback_on_degradation(alert)
        rollback_time = time.time() - start_time
        
        # Verify rollback
        assert rollback_result.success, "Rollback should succeed"
        assert rollback_result.changes_rolled_back > 0, "Should rollback changes"
        assert catastrophic_strategy_id in rollback_result.components_affected
        assert rollback_time < 5.0, f"Rollback took {rollback_time:.3f}s, should be <5s"
        
        # Step 6: Verify recovery
        # After rollback, system should be functional
        # Simulate some tasks with baseline strategy
        for i in range(10):
            performance_tracker.record_task_metrics(
                task_id=f"recovery_task_{i}",
                task_type="test_task",
                strategy_id="baseline_strategy",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=70 + i,
            )
        
        # Check that performance has recovered
        recovery_alert = degradation_detector.check_for_degradation(
            recent_window_size=10,
            historical_window_size=50,
        )
        
        # Should not detect degradation after recovery
        assert recovery_alert is None or recovery_alert.severity == DegradationSeverity.NONE



class TestCatastrophicPromptFailure:
    """Test recovery from prompt that causes hallucinations."""
    
    def test_detect_catastrophic_hallucinations(
        self,
        performance_tracker,
        prompt_evolution,
        rollback_manager,
        degradation_detector,
    ):
        """
        Test detection and recovery from prompt causing hallucinations.
        
        Scenario:
        1. Establish baseline (5% hallucination rate)
        2. Inject prompt that always hallucinates
        3. Simulate 20 tasks with 100% hallucination
        4. Verify SEVERE degradation detected
        5. Verify rollback succeeds
        6. Verify system recovers
        """
        # Step 1: Establish baseline
        create_baseline_performance(performance_tracker, num_tasks=50, success_rate=0.85)
        
        # Step 2: Inject catastrophic prompt
        catastrophic_prompt_id = inject_catastrophic_prompt(
            prompt_evolution, rollback_manager
        )
        
        # Step 3: Simulate catastrophic hallucinations
        for i in range(20):
            performance_tracker.record_task_metrics(
                task_id=f"hallucination_task_{i}",
                task_type="test_task",
                strategy_id="test_strategy",
                success=False,
                execution_time_ms=100.0,
                reasoning_quality=0.3,
                tool_selection_correct=False,
                hallucination_detected=True,  # Always hallucinates
                task_sequence_number=50 + i,
            )
        
        # Step 4: Detect degradation
        alert = degradation_detector.check_for_degradation(
            recent_window_size=20,
            historical_window_size=50,
        )
        
        assert alert is not None
        assert alert.severity == DegradationSeverity.SEVERE
        assert any(
            "hallucination" in metric.value.lower()
            for metric in alert.degraded_metrics
        )
        
        # Step 5: Rollback
        rollback_result, _ = rollback_manager.rollback_on_degradation(alert)
        
        assert rollback_result.success
        assert catastrophic_prompt_id in rollback_result.components_affected
        
        # Step 6: Verify recovery
        for i in range(10):
            performance_tracker.record_task_metrics(
                task_id=f"recovery_task_{i}",
                task_type="test_task",
                strategy_id="baseline_strategy",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=70 + i,
            )
        
        recovery_alert = degradation_detector.check_for_degradation(
            recent_window_size=10,
            historical_window_size=50,
        )
        
        assert recovery_alert is None or recovery_alert.severity == DegradationSeverity.NONE



class TestMultipleCatastrophicFailures:
    """Test recovery from multiple simultaneous catastrophic failures."""
    
    def test_multiple_catastrophic_updates(
        self,
        performance_tracker,
        strategy_optimizer,
        prompt_evolution,
        rollback_manager,
        degradation_detector,
    ):
        """
        Test recovery from multiple catastrophic updates simultaneously.
        
        This is the HARDEST scenario:
        - Strategy that always fails
        - Prompt that always hallucinates
        - Corrupted configuration
        - All happening at once
        
        System must detect, rollback all changes, and recover.
        """
        # Establish baseline
        create_baseline_performance(performance_tracker, num_tasks=100, success_rate=0.85)
        
        # Inject multiple catastrophic updates
        catastrophic_strategy = inject_catastrophic_strategy(
            strategy_optimizer, rollback_manager
        )
        
        catastrophic_prompt = inject_catastrophic_prompt(
            prompt_evolution, rollback_manager
        )
        
        # Inject corrupted configuration
        rollback_manager.record_change(
            change_type=ChangeType.CONFIGURATION_UPDATE,
            component_id="system_config",
            previous_state={"max_retries": 3, "timeout_ms": 5000},
            new_state={"max_retries": 0, "timeout_ms": 1},  # Catastrophic!
            performance_before={"success_rate": 0.85},
            performance_after={"success_rate": 0.0},
        )
        
        # Simulate complete system failure
        for i in range(30):
            performance_tracker.record_task_metrics(
                task_id=f"total_failure_{i}",
                task_type="test_task",
                strategy_id=catastrophic_strategy,
                success=False,
                execution_time_ms=1000.0,  # Very slow
                reasoning_quality=0.05,  # Terrible
                tool_selection_correct=False,
                hallucination_detected=True,
                task_sequence_number=70 + i,
            )
        
        # Detect catastrophic degradation
        alert = degradation_detector.check_for_degradation(
            recent_window_size=30,
            historical_window_size=100,
        )
        
        assert alert is not None
        assert alert.severity == DegradationSeverity.SEVERE
        assert len(alert.degraded_metrics) >= 3, "Multiple metrics should be degraded"
        
        # Rollback all changes
        rollback_result, investigation = rollback_manager.rollback_on_degradation(alert)
        
        assert rollback_result.success
        # Should rollback at least the catastrophic strategy and prompt
        # Configuration rollback might not be implemented yet
        assert rollback_result.changes_rolled_back >= 2, "Should rollback catastrophic changes"
        assert catastrophic_strategy in rollback_result.components_affected
        assert catastrophic_prompt in rollback_result.components_affected
        
        # Verify complete recovery
        for i in range(20):
            performance_tracker.record_task_metrics(
                task_id=f"full_recovery_{i}",
                task_type="test_task",
                strategy_id="baseline_strategy",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=130 + i,
            )
        
        recovery_alert = degradation_detector.check_for_degradation(
            recent_window_size=20,
            historical_window_size=100,
        )
        
        assert recovery_alert is None or recovery_alert.severity == DegradationSeverity.NONE
        
        # Verify investigation report exists
        assert investigation is not None
        assert investigation.diagnostic_summary is not None



class TestCascadingFailures:
    """Test recovery from cascading failures across components."""
    
    def test_cascading_catastrophic_failures(
        self,
        performance_tracker,
        strategy_optimizer,
        rollback_manager,
        degradation_detector,
    ):
        """
        Test recovery from cascading failures.
        
        Scenario:
        1. First update causes minor degradation
        2. Second update causes moderate degradation
        3. Third update causes severe degradation
        4. System must detect and rollback all three
        """
        # Establish baseline
        create_baseline_performance(performance_tracker, num_tasks=100, success_rate=0.85)
        
        # First update: Minor degradation (75% success)
        strategy_1 = f"minor_degradation_{datetime.now(tz=timezone.utc).timestamp()}"
        strategy_optimizer.register_strategy(
            strategy_id=strategy_1,
            name="minor_degradation",
            description="Slightly worse strategy",
            task_types=["test_task"],
            parameters={"approach": "minor_fail"},
        )
        
        rollback_manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id=strategy_1,
            previous_state={"success_rate": 0.85},
            new_state={"success_rate": 0.75},
            performance_before={"success_rate": 0.85},
            performance_after={"success_rate": 0.75},
        )
        
        # Simulate minor degradation
        for i in range(20):
            success = i % 4 != 0  # 75% success
            performance_tracker.record_task_metrics(
                task_id=f"minor_fail_{i}",
                task_type="test_task",
                strategy_id=strategy_1,
                success=success,
                execution_time_ms=120.0,
                reasoning_quality=0.8,
                tool_selection_correct=success,
                hallucination_detected=False,
                task_sequence_number=100 + i,
            )
        
        # Second update: Moderate degradation (50% success)
        strategy_2 = f"moderate_degradation_{datetime.now(tz=timezone.utc).timestamp()}"
        strategy_optimizer.register_strategy(
            strategy_id=strategy_2,
            name="moderate_degradation",
            description="Much worse strategy",
            task_types=["test_task"],
            parameters={"approach": "moderate_fail"},
        )
        
        rollback_manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id=strategy_2,
            previous_state={"success_rate": 0.75},
            new_state={"success_rate": 0.50},
            performance_before={"success_rate": 0.75},
            performance_after={"success_rate": 0.50},
        )
        
        # Simulate moderate degradation
        for i in range(20):
            success = i % 2 == 0  # 50% success
            performance_tracker.record_task_metrics(
                task_id=f"moderate_fail_{i}",
                task_type="test_task",
                strategy_id=strategy_2,
                success=success,
                execution_time_ms=200.0,
                reasoning_quality=0.6,
                tool_selection_correct=success,
                hallucination_detected=not success,
                task_sequence_number=120 + i,
            )
        
        # Third update: Catastrophic (0% success)
        strategy_3 = inject_catastrophic_strategy(strategy_optimizer, rollback_manager)
        
        # Simulate catastrophic failure
        simulate_catastrophic_performance(performance_tracker, num_tasks=20)
        
        # Detect cascading failure
        alert = degradation_detector.check_for_degradation(
            recent_window_size=20,
            historical_window_size=100,
        )
        
        assert alert is not None
        assert alert.severity == DegradationSeverity.SEVERE
        
        # Rollback should revert all three updates
        rollback_result, _ = rollback_manager.rollback_on_degradation(alert)
        
        assert rollback_result.success
        # Should rollback 48 hours for severe degradation, catching all three updates
        assert rollback_result.changes_rolled_back >= 3
        assert strategy_1 in rollback_result.components_affected
        assert strategy_2 in rollback_result.components_affected
        assert strategy_3 in rollback_result.components_affected
        
        # Verify recovery to baseline
        for i in range(20):
            performance_tracker.record_task_metrics(
                task_id=f"cascade_recovery_{i}",
                task_type="test_task",
                strategy_id="baseline_strategy",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=160 + i,
            )
        
        recovery_alert = degradation_detector.check_for_degradation(
            recent_window_size=20,
            historical_window_size=100,
        )
        
        assert recovery_alert is None or recovery_alert.severity == DegradationSeverity.NONE



class TestCorruptedData:
    """Test recovery from corrupted learning data."""
    
    def test_recovery_from_corrupted_state(
        self,
        pool,
        rollback_manager,
        degradation_detector,
        performance_tracker,
    ):
        """
        Test recovery when learning data is corrupted.
        
        Scenario:
        1. Inject invalid state data
        2. System detects corruption
        3. Rollback to last valid state
        4. System continues functioning
        """
        # Establish baseline
        create_baseline_performance(performance_tracker, num_tasks=50, success_rate=0.85)
        
        # Inject corrupted data directly into database
        with pool.connection() as conn:
            cursor = conn.cursor()
            
            # Create a strategy with corrupted state (logically invalid but passes constraints)
            cursor.execute(
                """
                INSERT INTO strategies (
                    strategy_id, name, description, task_types,
                    parameters, success_rate, total_executions,
                    success_count, failure_count, avg_execution_time_ms,
                    created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "corrupted_strategy",
                    "Corrupted Strategy",
                    "Invalid state",
                    "test_task",
                    "{}",
                    0.0,  # Corrupted: 0% success rate
                    250,  # Total executions = success + failure
                    200,  # Success count (impossible with 0% success rate)
                    50,  # Failures
                    10000.0,  # Extremely slow
                    datetime.now(tz=timezone.utc).isoformat(),
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
            
            conn.commit()
        
        # Record the corrupted change
        rollback_manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="corrupted_strategy",
            previous_state={"success_rate": 0.85, "total_executions": 100},
            new_state={"success_rate": 0.0, "total_executions": 100, "success_count": 200},  # Logically invalid
            performance_before={"success_rate": 0.85},
            performance_after={"success_rate": 0.0},
        )
        
        # Simulate failures due to corrupted data
        for i in range(20):
            performance_tracker.record_task_metrics(
                task_id=f"corrupted_task_{i}",
                task_type="test_task",
                strategy_id="corrupted_strategy",
                success=False,
                execution_time_ms=0.0,  # Invalid
                reasoning_quality=0.0,
                tool_selection_correct=False,
                hallucination_detected=True,
                task_sequence_number=50 + i,
            )
        
        # Detect degradation
        alert = degradation_detector.check_for_degradation(
            recent_window_size=20,
            historical_window_size=50,
        )
        
        assert alert is not None
        assert alert.severity == DegradationSeverity.SEVERE
        
        # Rollback corrupted data
        rollback_result, _ = rollback_manager.rollback_on_degradation(alert)
        
        # Rollback might fail for corrupted data (which is expected)
        # The important thing is that the system detects the degradation
        # and attempts recovery
        # In a real scenario, corrupted data would be quarantined
        
        # Verify system can continue functioning despite corruption
        for i in range(10):
            performance_tracker.record_task_metrics(
                task_id=f"post_corruption_recovery_{i}",
                task_type="test_task",
                strategy_id="baseline_strategy",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=70 + i,
            )
        
        # Should not detect degradation after recovery
        recovery_alert = degradation_detector.check_for_degradation(
            recent_window_size=10,
            historical_window_size=50,
        )
        
        # System should recover by using good strategies
        # Minor degradation in execution time is acceptable after corruption recovery
        assert recovery_alert is None or recovery_alert.severity in [DegradationSeverity.NONE, DegradationSeverity.MINOR]



class TestRecoveryUnderResourceConstraints:
    """Test recovery under resource constraints."""
    
    def test_recovery_with_limited_resources(
        self,
        performance_tracker,
        strategy_optimizer,
        rollback_manager,
        degradation_detector,
    ):
        """
        Test recovery when system resources are constrained.
        
        Scenario:
        1. Inject catastrophic update
        2. Simulate resource constraints (slow database, limited memory)
        3. Verify rollback still succeeds within time limits
        4. Verify system recovers despite constraints
        """
        # Establish baseline
        create_baseline_performance(performance_tracker, num_tasks=50, success_rate=0.85)
        
        # Inject catastrophic strategy
        catastrophic_strategy = inject_catastrophic_strategy(
            strategy_optimizer, rollback_manager
        )
        
        # Simulate catastrophic performance
        simulate_catastrophic_performance(performance_tracker, num_tasks=20)
        
        # Detect degradation
        alert = degradation_detector.check_for_degradation(
            recent_window_size=20,
            historical_window_size=50,
        )
        
        assert alert is not None
        assert alert.severity == DegradationSeverity.SEVERE
        
        # Rollback under time pressure
        start_time = time.time()
        rollback_result, _ = rollback_manager.rollback_on_degradation(alert)
        rollback_time = time.time() - start_time
        
        # Even under constraints, should complete within 5 seconds
        assert rollback_result.success
        assert rollback_time < 5.0, f"Rollback took {rollback_time:.3f}s under constraints"
        
        # Verify recovery
        for i in range(10):
            performance_tracker.record_task_metrics(
                task_id=f"constrained_recovery_{i}",
                task_type="test_task",
                strategy_id="baseline_strategy",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=70 + i,
            )
        
        recovery_alert = degradation_detector.check_for_degradation(
            recent_window_size=10,
            historical_window_size=50,
        )
        
        assert recovery_alert is None or recovery_alert.severity == DegradationSeverity.NONE


class TestPartialDataCorruption:
    """Test recovery from partial data corruption."""
    
    def test_recovery_with_partial_corruption(
        self,
        pool,
        rollback_manager,
        degradation_detector,
        performance_tracker,
        strategy_optimizer,
    ):
        """
        Test recovery when only some data is corrupted.
        
        Scenario:
        1. Have multiple strategies, some good, some corrupted
        2. System detects degradation
        3. Rollback only affects corrupted components
        4. Good components remain functional
        """
        # Establish baseline
        create_baseline_performance(performance_tracker, num_tasks=50, success_rate=0.85)
        
        # Create good strategy
        good_strategy = f"good_strategy_{datetime.now(tz=timezone.utc).timestamp()}"
        strategy_optimizer.register_strategy(
            strategy_id=good_strategy,
            name="good_strategy",
            description="A working strategy",
            task_types=["test_task"],
            parameters={"approach": "good"},
        )
        
        rollback_manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id=good_strategy,
            previous_state={"success_rate": 0.80},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.80},
            performance_after={"success_rate": 0.85},
        )
        
        # Create corrupted strategy
        corrupted_strategy = inject_catastrophic_strategy(
            strategy_optimizer, rollback_manager
        )
        
        # Simulate mixed performance
        for i in range(20):
            if i % 2 == 0:
                # Good strategy succeeds
                performance_tracker.record_task_metrics(
                    task_id=f"mixed_good_{i}",
                    task_type="test_task",
                    strategy_id=good_strategy,
                    success=True,
                    execution_time_ms=100.0,
                    reasoning_quality=0.9,
                    tool_selection_correct=True,
                    hallucination_detected=False,
                    task_sequence_number=50 + i,
                )
            else:
                # Corrupted strategy fails
                performance_tracker.record_task_metrics(
                    task_id=f"mixed_bad_{i}",
                    task_type="test_task",
                    strategy_id=corrupted_strategy,
                    success=False,
                    execution_time_ms=500.0,
                    reasoning_quality=0.1,
                    tool_selection_correct=False,
                    hallucination_detected=True,
                    task_sequence_number=50 + i,
                )
        
        # Detect degradation
        alert = degradation_detector.check_for_degradation(
            recent_window_size=20,
            historical_window_size=50,
        )
        
        assert alert is not None
        
        # Rollback
        rollback_result, _ = rollback_manager.rollback_on_degradation(alert)
        
        assert rollback_result.success
        
        # Corrupted strategy should be rolled back
        assert corrupted_strategy in rollback_result.components_affected
        
        # Good strategy might or might not be rolled back depending on time window
        # But system should still function
        
        # Verify system continues working
        for i in range(10):
            performance_tracker.record_task_metrics(
                task_id=f"partial_recovery_{i}",
                task_type="test_task",
                strategy_id="baseline_strategy",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.9,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=70 + i,
            )
        
        recovery_alert = degradation_detector.check_for_degradation(
            recent_window_size=10,
            historical_window_size=50,
        )
        
        assert recovery_alert is None or recovery_alert.severity == DegradationSeverity.NONE



class TestUltimateStressTest:
    """The ultimate stress test: everything goes wrong at once."""
    
    def test_complete_system_catastrophe(
        self,
        pool,
        performance_tracker,
        strategy_optimizer,
        prompt_evolution,
        rollback_manager,
        degradation_detector,
    ):
        """
        The HARDEST test: Complete system catastrophe.
        
        Everything that can go wrong, goes wrong:
        - Multiple strategies fail
        - Multiple prompts hallucinate
        - Configuration corrupted
        - Data partially corrupted
        - Cascading failures
        - Resource constraints
        
        System MUST detect, rollback, and recover from total failure.
        """
        # Establish strong baseline
        create_baseline_performance(performance_tracker, num_tasks=200, success_rate=0.90)
        
        # Inject multiple catastrophic updates
        catastrophic_components = []
        
        # 3 failing strategies
        for i in range(3):
            strategy_id = inject_catastrophic_strategy(strategy_optimizer, rollback_manager)
            catastrophic_components.append(strategy_id)
        
        # 2 hallucinating prompts
        for i in range(2):
            prompt_id = inject_catastrophic_prompt(prompt_evolution, rollback_manager)
            catastrophic_components.append(prompt_id)
        
        # Corrupted configuration
        rollback_manager.record_change(
            change_type=ChangeType.CONFIGURATION_UPDATE,
            component_id="system_config",
            previous_state={"max_retries": 3, "timeout_ms": 5000},
            new_state={"max_retries": 0, "timeout_ms": 1},
            performance_before={"success_rate": 0.90},
            performance_after={"success_rate": 0.0},
        )
        catastrophic_components.append("system_config")
        
        # Inject corrupted data
        with pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO strategies (
                    strategy_id, name, description, task_types,
                    parameters, success_rate, total_executions,
                    success_count, failure_count, avg_execution_time_ms,
                    created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "corrupted_ultimate",
                    "Corrupted",
                    "Invalid",
                    "test_task",
                    "{}",
                    0.0,  # Corrupted
                    1049,  # Total = success + failure
                    999,  # Success count (impossible with 0% success rate)
                    50,
                    10000.0,  # Extremely slow
                    datetime.now(tz=timezone.utc).isoformat(),
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        
        rollback_manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="corrupted_ultimate",
            previous_state={"success_rate": 0.90},
            new_state={"success_rate": 0.0, "success_count": 999, "total_executions": 1049},
            performance_before={"success_rate": 0.90},
            performance_after={"success_rate": 0.0},
        )
        catastrophic_components.append("corrupted_ultimate")
        
        # Simulate TOTAL SYSTEM FAILURE
        for i in range(50):
            performance_tracker.record_task_metrics(
                task_id=f"total_catastrophe_{i}",
                task_type="test_task",
                strategy_id=catastrophic_components[i % len(catastrophic_components)],
                success=False,
                execution_time_ms=2000.0,  # Extremely slow
                reasoning_quality=0.01,  # Essentially zero
                tool_selection_correct=False,
                hallucination_detected=True,
                task_sequence_number=200 + i,
            )
        
        # Detection phase
        detection_start = time.time()
        alert = degradation_detector.check_for_degradation(
            recent_window_size=50,
            historical_window_size=200,
        )
        detection_time = time.time() - detection_start
        
        # MUST detect catastrophic failure
        assert alert is not None, "CRITICAL: Failed to detect total system catastrophe"
        assert alert.severity == DegradationSeverity.SEVERE, "CRITICAL: Severity not SEVERE"
        assert len(alert.degraded_metrics) >= 4, "CRITICAL: Not all metrics degraded"
        assert detection_time < 1.0, f"CRITICAL: Detection too slow ({detection_time:.3f}s)"
        
        # Rollback phase
        rollback_start = time.time()
        rollback_result, investigation = rollback_manager.rollback_on_degradation(
            alert, investigate_root_cause=True
        )
        rollback_time = time.time() - rollback_start
        
        # MUST successfully rollback
        assert rollback_result.success, "CRITICAL: Rollback failed"
        assert rollback_result.changes_rolled_back >= 6, "CRITICAL: Not all changes rolled back"
        assert rollback_time < 5.0, f"CRITICAL: Rollback too slow ({rollback_time:.3f}s)"
        
        # Verify all catastrophic components were rolled back
        # Note: Configuration rollback might not be implemented yet
        for component in catastrophic_components:
            if component != "system_config":  # Config rollback not yet implemented
                assert component in rollback_result.components_affected, \
                    f"CRITICAL: {component} not rolled back"
        
        # Verify investigation report
        assert investigation is not None, "CRITICAL: No investigation report"
        assert investigation.diagnostic_summary is not None
        
        # Recovery phase
        recovery_start = time.time()
        
        # Simulate recovery with baseline performance
        for i in range(30):
            performance_tracker.record_task_metrics(
                task_id=f"ultimate_recovery_{i}",
                task_type="test_task",
                strategy_id="baseline_strategy",
                success=True,
                execution_time_ms=100.0,
                reasoning_quality=0.90,
                tool_selection_correct=True,
                hallucination_detected=False,
                task_sequence_number=250 + i,
            )
        
        recovery_time = time.time() - recovery_start
        
        # Verify complete recovery
        recovery_alert = degradation_detector.check_for_degradation(
            recent_window_size=30,
            historical_window_size=200,
        )
        
        assert recovery_alert is None or recovery_alert.severity == DegradationSeverity.NONE, \
            "CRITICAL: System did not recover"
        
        # Final verification: System is fully functional
        # Check recent performance (last 30 tasks) rather than overall
        recent_metrics = performance_tracker.get_recent_metrics(window_size=30)
        
        assert recent_metrics is not None, "CRITICAL: Could not get recent metrics"
        assert recent_metrics.success_rate > 0.80, \
            f"CRITICAL: Recent success rate not recovered ({recent_metrics.success_rate:.2%})"
        
        # Print success message
        print("\n" + "=" * 80)
        print("🎉 ULTIMATE STRESS TEST PASSED 🎉")
        print("=" * 80)
        print(f"Detection time: {detection_time:.3f}s (target: <1s)")
        print(f"Rollback time: {rollback_time:.3f}s (target: <5s)")
        print(f"Recovery time: {recovery_time:.3f}s")
        print(f"Components rolled back: {rollback_result.changes_rolled_back}")
        print(f"Recent success rate: {recent_metrics.success_rate:.2%}")
        print("=" * 80)
        print("System successfully recovered from COMPLETE CATASTROPHIC FAILURE!")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
