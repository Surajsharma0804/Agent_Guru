"""Example usage of FailureAnalyzer.

Demonstrates how to:
- Initialize the failure analyzer
- Record different types of failures
- Query failure patterns
- Analyze failure trends

This example shows the core functionality of the failure analysis system.
"""

import os
import tempfile
from datetime import UTC, datetime

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.failure_analyzer import FailureAnalyzer, FailureType, TaskExecution


def main() -> None:
    """Run failure analyzer example."""
    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "example.db")

        # Initialize database schema
        DatabaseSchema.create_schema(db_path)

        # Create connection pool
        pool = ConnectionPool(db_path, min_size=2, max_size=10)

        # Create failure analyzer
        analyzer = FailureAnalyzer(pool)

        # Example 1: Record reasoning error
        reasoning_failure = TaskExecution(
            task_id="task_001",
            task_type="code_generation",
            strategy_id="strategy_basic",
            timestamp=datetime.now(tz=UTC),
            success=False,
            execution_time_ms=150.5,
            failure_type=FailureType.REASONING_ERROR,
            error_details={
                "reasoning_step": "step_3_logical_inference",
                "error_message": "Invalid logical inference in conditional branch",
            },
            context={
                "user_input": "Generate function to calculate fibonacci",
                "language": "python",
            },
        )
        analyzer.analyze_failure(reasoning_failure)

        # Example 2: Record tool error
        tool_failure = TaskExecution(
            task_id="task_002",
            task_type="file_operation",
            strategy_id="strategy_basic",
            timestamp=datetime.now(tz=UTC),
            success=False,
            execution_time_ms=75.2,
            failure_type=FailureType.TOOL_ERROR,
            error_details={
                "tool_name": "file_writer",
                "error_message": "Permission denied: /protected/file.txt",
            },
            context={"file_path": "/protected/file.txt", "operation": "write"},
        )
        analyzer.analyze_failure(tool_failure)

        # Example 3: Record hallucination
        hallucination_failure = TaskExecution(
            task_id="task_003",
            task_type="information_retrieval",
            strategy_id="strategy_advanced",
            timestamp=datetime.now(tz=UTC),
            success=False,
            execution_time_ms=200.0,
            failure_type=FailureType.HALLUCINATION,
            error_details={
                "hallucination_content": "The Eiffel Tower is located in London",
                "correct_information": "The Eiffel Tower is located in Paris",
            },
            context={"query": "Where is the Eiffel Tower located?", "source": "llm_response"},
        )
        analyzer.analyze_failure(hallucination_failure)

        # Example 4: Record multiple similar failures to create pattern
        for i in range(5):
            similar_failure = TaskExecution(
                task_id=f"task_pattern_{i}",
                task_type="api_call",
                strategy_id="strategy_api",
                timestamp=datetime.now(tz=UTC),
                success=False,
                execution_time_ms=5000.0,
                failure_type=FailureType.TIMEOUT,
                error_details={"timeout_ms": 5000, "endpoint": "/api/slow-endpoint"},
                context={"api_endpoint": "/api/slow-endpoint", "method": "GET"},
            )
            analyzer.analyze_failure(similar_failure)

        # Example 5: Query failure statistics
        # BUG FIX: all five return values used to be computed and immediately
        # discarded -- the comment says "Query failure statistics" but nothing
        # was ever reported. Restored.
        total_failures = analyzer.get_failure_count()
        reasoning_failures = analyzer.get_failure_count(failure_type=FailureType.REASONING_ERROR)
        tool_failures = analyzer.get_failure_count(failure_type=FailureType.TOOL_ERROR)
        hallucination_failures = analyzer.get_failure_count(failure_type=FailureType.HALLUCINATION)
        timeout_failures = analyzer.get_failure_count(failure_type=FailureType.TIMEOUT)
        print("\nFailure counts:")
        print(f"  Total: {total_failures}")
        print(f"  Reasoning errors: {reasoning_failures}")
        print(f"  Tool errors: {tool_failures}")
        print(f"  Hallucinations: {hallucination_failures}")
        print(f"  Timeouts: {timeout_failures}")

        # Example 6: Get identified patterns
        # BUG FIX: this loop used to be `pass` -- the identified patterns were
        # computed via a real query but never shown. Restored.
        patterns = analyzer.get_failure_patterns(min_occurrences=2)
        print(f"\nIdentified patterns ({len(patterns)}):")
        for _pattern in patterns:
            print(
                f"  - {_pattern.pattern_id}: {_pattern.failure_type.value} "
                f"(occurrences={_pattern.occurrence_count}, "
                f"confidence={_pattern.confidence_score:.2f})",
            )

        # Example 7: Get recent failures
        # BUG FIX: identical pattern to the patterns loop above -- restored.
        recent = analyzer.get_recent_failures(limit=3)
        print(f"\nRecent failures ({len(recent)}):")
        for _failure in recent:
            print(
                f"  - {_failure['task_id']} ({_failure['failure_type']}) "
                f"at {_failure['timestamp']}",
            )

        # Example 8: Record hallucination from LLM Runtime
        analyzer.record_hallucination(
            prompt_id="prompt_v1_001",
            hallucination_content="Python was invented in 1995",
            task_id="task_llm_001",
        )

        # Example 9: Get connection pool statistics
        # BUG FIX: the returned ConnectionStats used to be computed and
        # immediately discarded. Restored.
        stats = pool.get_stats()
        print("\nConnection pool stats:")
        print(f"  Total connections: {stats.total_connections}")
        print(f"  Active: {stats.active_connections}")
        print(f"  Idle: {stats.idle_connections}")
        print(f"  Total acquisitions: {stats.total_acquisitions}")
        print(f"  Total releases: {stats.total_releases}")
        print(f"  Avg acquisition time: {stats.avg_acquisition_time_ms:.2f}ms")
        print(f"  Avg transaction time: {stats.avg_transaction_time_ms:.2f}ms")
        print(f"  Failed acquisitions: {stats.failed_acquisitions}")
        print(f"  Failed transactions: {stats.failed_transactions}")

        # Cleanup
        pool.close_all()


if __name__ == "__main__":
    main()
