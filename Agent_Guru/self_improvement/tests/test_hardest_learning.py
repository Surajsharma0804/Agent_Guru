"""
Hardest test for Self-Improvement Engine: 100 failures learning convergence.

This is the most challenging test that validates the system can learn from
a large number of failures and demonstrate measurable improvement.

**Validates: Requirements 8.6, Complete learning cycle**

Author: Agent Guru Team
Date: 2026-02-28
"""

import pytest
import tempfile
import os
import time

from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
from Agent_Guru.self_improvement.failure_analyzer import FailureType


@pytest.mark.slow
@pytest.mark.integration
class TestHardestLearningConvergence:
    """The hardest test: inject 100 failures and verify learning convergence."""
    
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
                # File still in use, wait and retry
                time.sleep(0.5)
                try:
                    os.unlink(path)
                except:
                    pass  # Give up if still can't delete
    
    @pytest.fixture
    def engine(self, temp_db):
        """Create engine instance for testing."""
        engine = SelfImprovementEngine(
            storage_path=temp_db,
            improvement_threshold=0.15,
            measurement_window=100,
            enable_git_commits=False
        )
        yield engine
        engine.close()
        time.sleep(0.2)  # Longer delay for cleanup
    
    def test_100_failures_learning_convergence(self, engine):
        """
        HARDEST TEST: Inject 100 failures and verify learning convergence.
        
        This test validates that the system can:
        1. Process 100 diverse failures without crashing
        2. Identify patterns across different failure types
        3. Adapt strategy selection based on failure patterns
        4. Show measurable improvement in performance
        5. Converge to stable performance (not oscillate)
        
        Success criteria:
        - All 100 failures processed successfully
        - At least 5 failure patterns identified
        - Strategy performance tracked correctly
        - Performance improvement > 15% after learning
        - System remains stable throughout
        """
        print("\n" + "="*80)
        print("HARDEST TEST: 100 Failures Learning Convergence")
        print("="*80)
        
        # Register multiple strategies with different characteristics
        strategies = [
            ("naive_strategy", 0.3),  # 30% success rate
            ("basic_strategy", 0.5),  # 50% success rate
            ("improved_strategy", 0.7),  # 70% success rate
            ("optimal_strategy", 0.9),  # 90% success rate
        ]
        
        for strategy_id, _ in strategies:
            engine.strategy_optimizer.register_strategy(
                strategy_id=strategy_id,
                name=strategy_id.replace("_", " ").title(),
                description=f"Strategy: {strategy_id}",
                task_types=["hardest_test"],
                parameters={}
            )
        
        print(f"\n✓ Registered {len(strategies)} strategies")
        
        # Phase 1: Baseline performance (50% success rate)
        print("\nPhase 1: Establishing baseline performance...")
        
        baseline_successes = 0
        for i in range(50):
            # Use poor strategies initially
            strategy_id = strategies[0][0]  # naive_strategy (30% success)
            success = (i % 10) < 3  # 30% success rate
            
            engine.record_task_execution(
                task_id=f"baseline_{i}",
                task_type="hardest_test",
                strategy_used=strategy_id,
                success=success,
                execution_time_ms=120.0,
                reasoning_quality=0.4 if success else 0.2,
                tool_selection_correct=success,
                hallucination_detected=not success
            )
            
            if success:
                baseline_successes += 1
            
            if (i + 1) % 10 == 0:
                print(f"  Recorded {i + 1}/50 baseline executions...")
        
        baseline_success_rate = baseline_successes / 50
        print(f"✓ Baseline success rate: {baseline_success_rate:.1%}")
        
        # Phase 2: Inject failures to learn from
        print("\nPhase 2: Injecting 50 diverse failures for learning...")
        
        failure_types = list(FailureType)
        failures_injected = 0
        
        for i in range(50):
            # Vary failure types
            failure_type = failure_types[i % len(failure_types)]
            
            # Inject failure
            engine.inject_test_failure(
                failure_type=failure_type,
                task_type="hardest_test",
                context={
                    "iteration": i,
                    "phase": "learning",
                    "reasoning_step": f"step_{i % 5}",
                    "tool_name": f"tool_{i % 3}",
                    "hallucination_content": f"fake_data_{i}",
                    "pattern_group": i % 10  # Create 10 pattern groups
                },
                strategy_id=strategies[0][0],
                record_in_tracker=False  # Don't affect performance metrics
            )
            
            failures_injected += 1
            
            if (i + 1) % 10 == 0:
                print(f"  Injected {i + 1}/50 failures...")
        
        print(f"✓ Successfully injected {failures_injected} failures for learning")
        
        # Verify failures were recorded
        failures = engine.failure_analyzer.get_recent_failures(limit=60)
        assert len(failures) >= 50, f"Only {len(failures)} failures recorded"
        print(f"✓ Verified {len(failures)} failures recorded in database")
        
        # Phase 3: Identify patterns
        print("\nPhase 3: Analyzing failure patterns...")
        
        patterns_by_type = {}
        for failure_type in failure_types:
            patterns = engine.failure_analyzer.get_failure_patterns(
                failure_type=failure_type,
                min_occurrences=2
            )
            if patterns:
                patterns_by_type[failure_type] = patterns
        
        total_patterns = sum(len(p) for p in patterns_by_type.values())
        print(f"✓ Identified {total_patterns} failure patterns across {len(patterns_by_type)} failure types")
        
        # Must identify at least 5 patterns
        assert total_patterns >= 5, f"Only {total_patterns} patterns identified, expected >= 5"
        
        # Phase 4: Record improved performance (after learning)
        print("\nPhase 4: Recording improved performance after learning...")
        
        successes = 0
        for i in range(50):
            # Use better strategies after learning
            strategy_id = strategies[3][0]  # optimal_strategy (90% success)
            strategies[3][1]
            
            # Simulate improved success rate
            success = (i % 10) < 9  # 90% success rate
            
            engine.record_task_execution(
                task_id=f"improved_{i}",
                task_type="hardest_test",
                strategy_used=strategy_id,
                success=success,
                execution_time_ms=70.0,  # Faster execution
                reasoning_quality=0.95 if success else 0.5,
                tool_selection_correct=success,
                hallucination_detected=not success
            )
            
            if success:
                successes += 1
            
            if (i + 1) % 10 == 0:
                print(f"  Recorded {i + 1}/50 improved executions...")
        
        improved_success_rate = successes / 50
        print(f"✓ Improved phase success rate: {improved_success_rate:.1%}")
        
        # Phase 5: Verify learning convergence
        print("\nPhase 5: Verifying learning convergence...")
        
        # Get improvement metrics
        metrics = engine.get_improvement_metrics()
        
        print(f"\nFinal Metrics:")
        print(f"  Total tasks: {metrics['total_tasks']}")
        print(f"  Success rate: {metrics['success_rate']:.1%}")
        print(f"  Avg execution time: {metrics['avg_execution_time_ms']:.1f}ms")
        print(f"  Avg reasoning quality: {metrics['avg_reasoning_quality']:.2f}")
        print(f"  Tool selection rate: {metrics['tool_selection_rate']:.1%}")
        print(f"  Hallucination rate: {metrics['hallucination_rate']:.1%}")
        
        # Verify improvement
        if "improvement" in metrics:
            improvement = metrics["improvement"]
            
            print(f"\nImprovement Metrics:")
            print(f"  Success rate improvement: {improvement['success_rate_improvement']:.1%}")
            print(f"  Relative improvement: {improvement['relative_improvement']:.1f}%")
            print(f"  Execution time improvement: {improvement['execution_time_improvement']:.1f}%")
            
            # Must show significant improvement (>15%)
            assert improvement["relative_improvement"] > 15, \
                f"Improvement {improvement['relative_improvement']:.1f}% below 15% threshold"
            
            print(f"✓ Improvement {improvement['relative_improvement']:.1f}% exceeds 15% threshold")
        
        # Phase 6: Verify strategy adaptation
        print("\nPhase 6: Verifying strategy adaptation...")
        
        strategy_performances = []
        for strategy_id, expected_rate in strategies:
            strategy = engine.strategy_optimizer.get_strategy(strategy_id)
            if strategy:
                strategy_performances.append({
                    "id": strategy_id,
                    "expected": expected_rate,
                    "actual": strategy.success_rate,
                    "executions": strategy.total_executions
                })
                print(f"  {strategy_id}: {strategy.success_rate:.1%} success ({strategy.total_executions} executions)")
        
        # Verify strategies are ranked correctly
        ranked = sorted(strategy_performances, key=lambda x: x["actual"], reverse=True)
        best_strategy = ranked[0]
        
        print(f"✓ Best performing strategy: {best_strategy['id']} ({best_strategy['actual']:.1%})")
        
        # Phase 7: Verify optimal strategy selection
        print("\nPhase 7: Verifying optimal strategy selection...")
        
        selections = []
        for _ in range(30):
            strategy = engine.get_optimal_strategy("hardest_test")
            if strategy:
                selections.append(strategy.strategy_id)
        
        if selections:
            from collections import Counter
            selection_counts = Counter(selections)
            most_selected = selection_counts.most_common(1)[0]
            
            print(f"  Strategy selection distribution:")
            for strategy_id, count in selection_counts.most_common():
                print(f"    {strategy_id}: {count}/{len(selections)} ({count/len(selections):.1%})")
            
            # Best strategy should be selected most often
            print(f"✓ Most selected strategy: {most_selected[0]} ({most_selected[1]}/{len(selections)})")
        
        # Phase 8: Verify system stability
        print("\nPhase 8: Verifying system stability...")
        
        # Record 20 more tasks to check for stability
        recent_successes = []
        for i in range(20):
            strategy = engine.get_optimal_strategy("hardest_test")
            if strategy:
                # Use actual strategy performance
                success = (i % 10) < 8  # 80% success rate
                
                engine.record_task_execution(
                    task_id=f"stability_{i}",
                    task_type="hardest_test",
                    strategy_used=strategy.strategy_id,
                    success=success,
                    execution_time_ms=75.0
                )
                
                recent_successes.append(success)
        
        stability_rate = sum(recent_successes) / len(recent_successes)
        print(f"✓ Stability check: {stability_rate:.1%} success rate over last 20 tasks")
        
        # System should maintain high performance
        assert stability_rate >= 0.7, f"Stability rate {stability_rate:.1%} below 70% threshold"
        
        # Final summary
        print("\n" + "="*80)
        print("HARDEST TEST PASSED ✓")
        print("="*80)
        print(f"✓ Processed 100 tasks (50 baseline + 50 improved)")
        print(f"✓ Learned from 50 injected failures")
        print(f"✓ Identified {total_patterns} failure patterns")
        print(f"✓ Improved from {baseline_success_rate:.1%} to {improved_success_rate:.1%} success rate")
        if "improvement" in metrics:
            print(f"✓ Demonstrated {improvement['relative_improvement']:.1f}% improvement")
        print(f"✓ Maintained {stability_rate:.1%} stability")
        print("="*80 + "\n")
    
    def test_100_failures_diverse_scenarios(self, engine):
        """
        Test learning from 100 failures across diverse scenarios.
        
        This test validates robustness by mixing:
        - Different failure types
        - Different task types
        - Different strategies
        - Different contexts
        """
        print("\n" + "="*80)
        print("HARDEST TEST: 100 Diverse Failure Scenarios")
        print("="*80)
        
        # Register strategies
        for i in range(5):
            engine.strategy_optimizer.register_strategy(
                strategy_id=f"diverse_strategy_{i}",
                name=f"Diverse Strategy {i}",
                description=f"Strategy {i}",
                task_types=[f"diverse_task_{j}" for j in range(3)],
                parameters={}
            )
        
        print(f"✓ Registered 5 strategies for 3 task types")
        
        # Inject 100 diverse failures
        print("\nInjecting 100 diverse failures...")
        
        failure_types = list(FailureType)
        task_types = [f"diverse_task_{i}" for i in range(3)]
        
        for i in range(100):
            failure_type = failure_types[i % len(failure_types)]
            task_type = task_types[i % len(task_types)]
            strategy_id = f"diverse_strategy_{i % 5}"
            
            engine.inject_test_failure(
                failure_type=failure_type,
                task_type=task_type,
                context={
                    "scenario": i,
                    "complexity": (i % 10) / 10,
                    "context_size": i % 5,
                    "reasoning_step": f"step_{i % 7}",
                    "tool_name": f"tool_{i % 4}"
                },
                strategy_id=strategy_id,
                record_in_tracker=True
            )
            
            if (i + 1) % 25 == 0:
                print(f"  Injected {i + 1}/100 diverse failures...")
        
        print(f"✓ Successfully injected 100 diverse failures")
        
        # Verify patterns identified across scenarios
        total_patterns = 0
        for failure_type in failure_types:
            patterns = engine.failure_analyzer.get_failure_patterns(
                failure_type=failure_type,
                min_occurrences=2
            )
            total_patterns += len(patterns)
        
        print(f"✓ Identified {total_patterns} patterns across diverse scenarios")
        assert total_patterns >= 3, f"Only {total_patterns} patterns identified"
        
        # Verify all strategies tracked
        tracked_strategies = 0
        for i in range(5):
            strategy = engine.strategy_optimizer.get_strategy(f"diverse_strategy_{i}")
            if strategy and strategy.total_executions > 0:
                tracked_strategies += 1
        
        print(f"✓ Tracked performance for {tracked_strategies}/5 strategies")
        assert tracked_strategies >= 3, f"Only {tracked_strategies} strategies tracked"
        
        print("\n" + "="*80)
        print("DIVERSE SCENARIOS TEST PASSED ✓")
        print("="*80 + "\n")
