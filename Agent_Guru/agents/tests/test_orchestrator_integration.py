"""
Integration tests for Agent Orchestrator with Self-Improvement Engine.

Tests the complete integration between orchestration and learning systems.

**Validates: Requirements 15.1-15.6, Orchestration integration**

Author: Agent Guru Team
Date: 2026-02-28
"""

import pytest
import tempfile
import os
import time
from typing import Dict, Any

from Agent_Guru.agents.orchestrator import (
    AgentOrchestrator,
    TaskResult,
    TaskStatus,
    create_orchestrator_with_learning
)
from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine


class TestOrchestratorIntegration:
    """Integration tests for orchestrator with self-improvement."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            try:
                os.unlink(path)
            except PermissionError:
                time.sleep(0.1)
                try:
                    os.unlink(path)
                except:
                    pass
    
    @pytest.fixture
    def engine(self, temp_db):
        """Create self-improvement engine for testing."""
        engine = SelfImprovementEngine(
            storage_path=temp_db,
            improvement_threshold=0.15,
            measurement_window=100,
            enable_git_commits=False
        )
        yield engine
        engine.close()
        time.sleep(0.1)
    
    @pytest.fixture
    def orchestrator(self, engine):
        """Create orchestrator with learning enabled."""
        return AgentOrchestrator(
            self_improvement_engine=engine,
            enable_learning=True
        )
    
    def test_orchestrator_initialization(self, orchestrator, engine):
        """Test that orchestrator initializes with engine."""
        assert orchestrator.self_improvement_engine is engine
        assert orchestrator.enable_learning is True
        assert len(orchestrator.active_tasks) == 0
    
    def test_execute_task_without_learning(self):
        """Test task execution without learning enabled."""
        orchestrator = AgentOrchestrator(
            self_improvement_engine=None,
            enable_learning=False
        )
        
        # Simple task executor
        def add_numbers(params: Dict[str, Any]) -> int:
            return params["a"] + params["b"]
        
        # Execute task
        result = orchestrator.execute_task(
            task_id="task_1",
            task_type="arithmetic",
            description="Add two numbers",
            parameters={"a": 5, "b": 3},
            executor=add_numbers
        )
        
        # Verify result
        assert result.success is True
        assert result.result == 8
        assert result.error is None
        assert result.execution_time_ms > 0
        assert result.strategy_used == "default_strategy"
    
    def test_execute_task_with_learning(self, orchestrator, engine):
        """Test task execution with learning integration."""
        # Register a strategy
        engine.strategy_optimizer.register_strategy(
            strategy_id="test_strategy",
            name="Test Strategy",
            description="Test strategy",
            task_types=["arithmetic"],
            parameters={}
        )
        
        # Simple task executor
        def multiply_numbers(params: Dict[str, Any]) -> int:
            return params["x"] * params["y"]
        
        # Execute task
        result = orchestrator.execute_task(
            task_id="task_1",
            task_type="arithmetic",
            description="Multiply two numbers",
            parameters={"x": 4, "y": 7},
            executor=multiply_numbers
        )
        
        # Verify result
        assert result.success is True
        assert result.result == 28
        assert result.error is None
        assert result.execution_time_ms > 0
        
        # Verify learning recorded
        metrics = engine.get_improvement_metrics()
        assert metrics["total_tasks"] == 1
        assert metrics["success_rate"] == 1.0
    
    def test_execute_failing_task(self, orchestrator, engine):
        """Test task execution that fails."""
        # Register strategy
        engine.strategy_optimizer.register_strategy(
            strategy_id="failing_strategy",
            name="Failing Strategy",
            description="Test failing",
            task_types=["division"],
            parameters={}
        )
        
        # Task that will fail
        def divide_numbers(params: Dict[str, Any]) -> float:
            return params["a"] / params["b"]  # Will raise ZeroDivisionError
        
        # Execute task with zero divisor
        result = orchestrator.execute_task(
            task_id="task_fail",
            task_type="division",
            description="Divide by zero",
            parameters={"a": 10, "b": 0},
            executor=divide_numbers
        )
        
        # Verify failure
        assert result.success is False
        assert result.result is None
        assert result.error is not None
        assert "division by zero" in result.error.lower()
        assert result.execution_time_ms > 0
        
        # Verify failure recorded
        metrics = engine.get_improvement_metrics()
        assert metrics["total_tasks"] == 1
        assert metrics["success_rate"] == 0.0
        
        # Verify failure analyzed
        failures = engine.failure_analyzer.get_recent_failures(limit=1)
        assert len(failures) == 1
        assert failures[0]["task_id"] == "task_fail"
    
    def test_strategy_selection_integration(self, orchestrator, engine):
        """Test that orchestrator uses optimal strategy from engine."""
        # Register two strategies with different performance
        engine.strategy_optimizer.register_strategy(
            strategy_id="good_strategy",
            name="Good Strategy",
            description="High success rate",
            task_types=["test_task"],
            parameters={}
        )
        
        engine.strategy_optimizer.register_strategy(
            strategy_id="bad_strategy",
            name="Bad Strategy",
            description="Low success rate",
            task_types=["test_task"],
            parameters={}
        )
        
        # Record performance for strategies
        for i in range(10):
            engine.record_task_execution(
                task_id=f"good_{i}",
                task_type="test_task",
                strategy_used="good_strategy",
                success=True,
                execution_time_ms=100.0
            )
        
        for i in range(10):
            engine.record_task_execution(
                task_id=f"bad_{i}",
                task_type="test_task",
                strategy_used="bad_strategy",
                success=i < 3,  # 30% success
                execution_time_ms=100.0
            )
        
        # Execute task - should prefer good_strategy
        def simple_task(params: Dict[str, Any]) -> str:
            return "done"
        
        # Test multiple times (due to epsilon-greedy)
        good_count = 0
        for i in range(20):
            result = orchestrator.execute_task(
                task_id=f"select_{i}",
                task_type="test_task",
                description="Test strategy selection",
                parameters={},
                executor=simple_task
            )
            
            if result.strategy_used == "good_strategy":
                good_count += 1
        
        # Should select good strategy most of the time
        assert good_count > 10, f"Good strategy selected only {good_count}/20 times"
    
    def test_outcome_recording_integration(self, orchestrator, engine):
        """Test that outcomes are properly recorded in engine."""
        # Register strategy
        engine.strategy_optimizer.register_strategy(
            strategy_id="record_strategy",
            name="Record Strategy",
            description="Test recording",
            task_types=["recording_test"],
            parameters={}
        )
        
        # Execute multiple tasks
        def task_executor(params: Dict[str, Any]) -> int:
            return params["value"] * 2
        
        for i in range(5):
            result = orchestrator.execute_task(
                task_id=f"record_{i}",
                task_type="recording_test",
                description="Test recording",
                parameters={"value": i},
                executor=task_executor
            )
            
            assert result.success is True
        
        # Verify all recorded
        metrics = engine.get_improvement_metrics()
        assert metrics["total_tasks"] == 5
        assert metrics["success_rate"] == 1.0
        
        # Verify strategy performance updated
        strategy = engine.strategy_optimizer.get_strategy("record_strategy")
        assert strategy is not None
        assert strategy.total_executions == 5
        assert strategy.success_rate == 1.0
    
    def test_active_tasks_tracking(self, orchestrator):
        """Test that active tasks are tracked correctly."""
        # Task that takes some time
        def slow_task(params: Dict[str, Any]) -> str:
            time.sleep(0.01)
            return "done"
        
        # Execute task
        result = orchestrator.execute_task(
            task_id="slow_task",
            task_type="slow",
            description="Slow task",
            parameters={},
            executor=slow_task
        )
        
        # After completion, should not be in active tasks
        assert "slow_task" not in orchestrator.active_tasks
        assert result.success is True
    
    def test_create_orchestrator_with_learning(self, temp_db):
        """Test convenience function for creating orchestrator."""
        orchestrator = create_orchestrator_with_learning(
            storage_path=temp_db,
            improvement_threshold=0.15,
            measurement_window=100
        )
        
        assert orchestrator is not None
        assert orchestrator.self_improvement_engine is not None
        assert orchestrator.enable_learning is True
        
        # Test it works
        def simple_task(params: Dict[str, Any]) -> int:
            return 42
        
        result = orchestrator.execute_task(
            task_id="test_1",
            task_type="test",
            description="Test",
            parameters={},
            executor=simple_task
        )
        
        assert result.success is True
        assert result.result == 42
        
        # Cleanup
        orchestrator.self_improvement_engine.close()
        time.sleep(0.1)


@pytest.mark.integration
class TestOrchestratorPerformance:
    """Performance tests for orchestrator integration."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            try:
                os.unlink(path)
            except:
                pass
    
    @pytest.fixture
    def orchestrator(self, temp_db):
        """Create orchestrator with learning."""
        orchestrator = create_orchestrator_with_learning(temp_db)
        
        # Register a strategy
        orchestrator.self_improvement_engine.strategy_optimizer.register_strategy(
            strategy_id="perf_strategy",
            name="Performance Strategy",
            description="For performance testing",
            task_types=["perf_test"],
            parameters={}
        )
        
        yield orchestrator
        orchestrator.self_improvement_engine.close()
        time.sleep(0.1)
    
    def test_orchestration_overhead(self, orchestrator):
        """
        Test that orchestration overhead is reasonable.
        
        Validates: Requirement 15.6
        
        Note: This test measures absolute overhead rather than percentage
        because the baseline task is too fast for meaningful percentage comparison.
        """
        # Simple fast task
        def fast_task(params: Dict[str, Any]) -> int:
            return params["value"] + 1
        
        # Measure task execution time with orchestration
        start = time.perf_counter()
        for i in range(100):
            result = orchestrator.execute_task(
                task_id=f"perf_{i}",
                task_type="perf_test",
                description="Performance test",
                parameters={"value": i},
                executor=fast_task
            )
        orchestrated_time = time.perf_counter() - start
        
        # Calculate average time per task
        avg_time_per_task_ms = (orchestrated_time / 100) * 1000
        
        print(f"\nOrchestration performance:")
        print(f"Total time: {orchestrated_time*1000:.2f}ms")
        print(f"Average per task: {avg_time_per_task_ms:.2f}ms")
        
        # Average time per task should be reasonable (<100ms)
        # This includes strategy selection, execution, and outcome recording
        assert avg_time_per_task_ms < 100, f"Average time {avg_time_per_task_ms:.2f}ms exceeds 100ms threshold"
    
    def test_concurrent_task_execution(self, orchestrator):
        """Test that multiple tasks can be tracked concurrently."""
        import threading
        
        results = []
        
        def task_executor(params: Dict[str, Any]) -> int:
            time.sleep(0.01)  # Simulate work
            return params["value"] * 2
        
        def execute_task(task_id: str, value: int):
            result = orchestrator.execute_task(
                task_id=task_id,
                task_type="concurrent_test",
                description="Concurrent test",
                parameters={"value": value},
                executor=task_executor
            )
            results.append(result)
        
        # Execute tasks concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=execute_task,
                args=(f"concurrent_{i}", i)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # Verify all succeeded
        assert len(results) == 10
        assert all(r.success for r in results)
        
        # Verify all recorded
        metrics = orchestrator.self_improvement_engine.get_improvement_metrics()
        assert metrics["total_tasks"] >= 10
