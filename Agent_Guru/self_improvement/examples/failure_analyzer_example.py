"""
Example usage of FailureAnalyzer.

Demonstrates how to:
- Initialize the failure analyzer
- Record different types of failures
- Query failure patterns
- Analyze failure trends

This example shows the core functionality of the failure analysis system.
"""

import os
import tempfile
from datetime import datetime

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.failure_analyzer import FailureAnalyzer, FailureType, TaskExecution


def main():
    """Run failure analyzer example."""
    print("=" * 60)
    print("FailureAnalyzer Example")
    print("=" * 60)
    print()

    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "example.db")

        # Initialize database schema
        print("1. Initializing database...")
        DatabaseSchema.create_schema(db_path)
        print(f"   ✓ Database created at: {db_path}")
        print()

        # Create connection pool
        print("2. Creating connection pool...")
        pool = ConnectionPool(db_path, min_size=2, max_size=10)
        print("   ✓ Pool created (min_size=2, max_size=10)")
        print()

        # Create failure analyzer
        print("3. Creating failure analyzer...")
        analyzer = FailureAnalyzer(pool)
        print("   ✓ Analyzer initialized")
        print()

        # Example 1: Record reasoning error
        print("4. Recording reasoning error...")
        reasoning_failure = TaskExecution(
            task_id="task_001",
            task_type="code_generation",
            strategy_id="strategy_basic",
            timestamp=datetime.now(),
            success=False,
            execution_time_ms=150.5,
            failure_type=FailureType.REASONING_ERROR,
            error_details={
                "reasoning_step": "step_3_logical_inference",
                "error_message": "Invalid logical inference in conditional branch"
            },
            context={
                "user_input": "Generate function to calculate fibonacci",
                "language": "python"
            }
        )
        analyzer.analyze_failure(reasoning_failure)
        print("   ✓ Reasoning error recorded")
        print(f"      Task: {reasoning_failure.task_id}")
        print(f"      Type: {reasoning_failure.failure_type.value}")
        print(f"      Step: {reasoning_failure.error_details['reasoning_step']}")
        print()

        # Example 2: Record tool error
        print("5. Recording tool error...")
        tool_failure = TaskExecution(
            task_id="task_002",
            task_type="file_operation",
            strategy_id="strategy_basic",
            timestamp=datetime.now(),
            success=False,
            execution_time_ms=75.2,
            failure_type=FailureType.TOOL_ERROR,
            error_details={
                "tool_name": "file_writer",
                "error_message": "Permission denied: /protected/file.txt"
            },
            context={
                "file_path": "/protected/file.txt",
                "operation": "write"
            }
        )
        analyzer.analyze_failure(tool_failure)
        print("   ✓ Tool error recorded")
        print(f"      Task: {tool_failure.task_id}")
        print(f"      Tool: {tool_failure.error_details['tool_name']}")
        print()

        # Example 3: Record hallucination
        print("6. Recording hallucination...")
        hallucination_failure = TaskExecution(
            task_id="task_003",
            task_type="information_retrieval",
            strategy_id="strategy_advanced",
            timestamp=datetime.now(),
            success=False,
            execution_time_ms=200.0,
            failure_type=FailureType.HALLUCINATION,
            error_details={
                "hallucination_content": "The Eiffel Tower is located in London",
                "correct_information": "The Eiffel Tower is located in Paris"
            },
            context={
                "query": "Where is the Eiffel Tower located?",
                "source": "llm_response"
            }
        )
        analyzer.analyze_failure(hallucination_failure)
        print("   ✓ Hallucination recorded")
        print(f"      Task: {hallucination_failure.task_id}")
        print(f"      Fabricated: {hallucination_failure.error_details['hallucination_content']}")
        print(f"      Correct: {hallucination_failure.error_details['correct_information']}")
        print()

        # Example 4: Record multiple similar failures to create pattern
        print("7. Recording similar failures to create pattern...")
        for i in range(5):
            similar_failure = TaskExecution(
                task_id=f"task_pattern_{i}",
                task_type="api_call",
                strategy_id="strategy_api",
                timestamp=datetime.now(),
                success=False,
                execution_time_ms=5000.0,
                failure_type=FailureType.TIMEOUT,
                error_details={
                    "timeout_ms": 5000,
                    "endpoint": "/api/slow-endpoint"
                },
                context={
                    "api_endpoint": "/api/slow-endpoint",
                    "method": "GET"
                }
            )
            analyzer.analyze_failure(similar_failure)
        print("   ✓ Recorded 5 similar timeout failures")
        print()

        # Example 5: Query failure statistics
        print("8. Querying failure statistics...")
        total_failures = analyzer.get_failure_count()
        reasoning_errors = analyzer.get_failure_count(failure_type=FailureType.REASONING_ERROR)
        tool_errors = analyzer.get_failure_count(failure_type=FailureType.TOOL_ERROR)
        hallucinations = analyzer.get_failure_count(failure_type=FailureType.HALLUCINATION)
        timeouts = analyzer.get_failure_count(failure_type=FailureType.TIMEOUT)

        print(f"   Total failures: {total_failures}")
        print(f"   Reasoning errors: {reasoning_errors}")
        print(f"   Tool errors: {tool_errors}")
        print(f"   Hallucinations: {hallucinations}")
        print(f"   Timeouts: {timeouts}")
        print()

        # Example 6: Get identified patterns
        print("9. Retrieving identified patterns...")
        patterns = analyzer.get_failure_patterns(min_occurrences=2)
        print(f"   Found {len(patterns)} patterns with 2+ occurrences:")
        for pattern in patterns:
            print(f"      - Pattern: {pattern.pattern_id}")
            print(f"        Type: {pattern.failure_type.value}")
            print(f"        Occurrences: {pattern.occurrence_count}")
            print(f"        Confidence: {pattern.confidence_score:.2f}")
            print(f"        Features: {pattern.common_features}")
            print()

        # Example 7: Get recent failures
        print("10. Retrieving recent failures...")
        recent = analyzer.get_recent_failures(limit=3)
        print(f"    Last {len(recent)} failures:")
        for failure in recent:
            print(f"       - Task: {failure['task_id']}")
            print(f"         Type: {failure['failure_type']}")
            print(f"         Time: {failure['execution_time_ms']:.1f}ms")
            print()

        # Example 8: Record hallucination from LLM Runtime
        print("11. Recording hallucination from LLM Runtime...")
        analyzer.record_hallucination(
            prompt_id="prompt_v1_001",
            hallucination_content="Python was invented in 1995",
            task_id="task_llm_001"
        )
        print("    ✓ Hallucination recorded from LLM Runtime")
        print("       Prompt: prompt_v1_001")
        print("       Content: Python was invented in 1995")
        print()

        # Example 9: Get connection pool statistics
        print("12. Connection pool statistics...")
        stats = pool.get_stats()
        print(f"    Total connections: {stats.total_connections}")
        print(f"    Active connections: {stats.active_connections}")
        print(f"    Idle connections: {stats.idle_connections}")
        print(f"    Total acquisitions: {stats.total_acquisitions}")
        print(f"    Avg acquisition time: {stats.avg_acquisition_time_ms:.2f}ms")
        print()

        # Cleanup
        print("13. Cleaning up...")
        pool.close_all()
        print("    ✓ Connection pool closed")
        print()

        print("=" * 60)
        print("Example completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    main()
