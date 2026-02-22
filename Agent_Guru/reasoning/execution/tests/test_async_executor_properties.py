"""Property-based tests for asynchronous execution engine.

**Validates: Requirements 6.4**
**Property 19: Async execution returns immediately**

These tests verify that async execution returns immediately without blocking,
regardless of action duration, across many random inputs using Hypothesis.

Note: These tests use mocking to avoid Redis/Celery infrastructure dependencies.
"""

import time
from typing import Any
from unittest.mock import Mock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.execution.async_executor import (
    AsyncExecutionController,
    AsyncExecutionResult,
    AsyncExecutor,
    TaskStatus,
)
from Agent_Guru.reasoning.models.action import Action

# ============================================================================
# Property-Based Tests for Async Execution
# ============================================================================


class TestAsyncExecutionImmediateReturnProperties:
    """Property-based tests for async execution immediate return behavior.

    **Validates: Requirements 6.4**
    **Property 19: Async execution returns immediately**

    These tests verify that execute_async returns within 100ms regardless
    of action duration across many random inputs.
    """

    @settings(max_examples=100, deadline=None)
    @given(
        action_duration=st.floats(min_value=0.5, max_value=5.0),
        action_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
        ),
        tool_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
        ),
        parameter_value=st.integers(min_value=0, max_value=1000),
    )
    def test_property_19_async_execution_returns_immediately(
        self,
        action_duration: float,
        action_id: str,
        tool_id: str,
        parameter_value: int,
    ):
        """
        Property 19: Async execution returns immediately.

        For any action with any expected duration, execute_async should
        return within 100ms without waiting for the action to complete.

        **Validates: Requirements 6.4**
        """
        # Mock Celery task to avoid Redis dependency
        with patch(
            "Agent_Guru.reasoning.execution.async_executor.execute_action_task"
        ) as mock_task:
            # Create mock async result with task ID
            mock_async_result = Mock()
            mock_async_result.id = f"task_{action_id}_{int(time.time() * 1000)}"
            mock_task.apply_async.return_value = mock_async_result

            executor = AsyncExecutor()

            action = Action(
                action_id=action_id,
                tool_id=tool_id,
                parameters={
                    "duration": action_duration,
                    "value": parameter_value,
                },
            )

            # Measure time to submit async task
            start_time = time.perf_counter()
            result = executor.execute_async(
                action,
                tool_module="time",
                tool_function_name="sleep",
            )
            submission_time = time.perf_counter() - start_time

            # Property assertions - immediate return
            assert submission_time < 0.1, (
                f"Async execution should return within 100ms, "
                f"but took {submission_time * 1000:.2f}ms for action "
                f"with duration {action_duration}s"
            )

            # Property assertions - result structure
            assert isinstance(result, AsyncExecutionResult), (
                f"execute_async must return AsyncExecutionResult, " f"got {type(result)}"
            )

            # Property assertions - initial state
            assert result.task_id is not None, "Task ID must be assigned"
            assert isinstance(
                result.task_id, str
            ), f"Task ID must be string, got {type(result.task_id)}"
            assert len(result.task_id) > 0, "Task ID must not be empty"

            assert result.status in [
                TaskStatus.PENDING,
                TaskStatus.RUNNING,
            ], f"Initial status should be PENDING or RUNNING, got {result.status}"

            assert result.action_id == action_id, (
                f"Action ID should be preserved: expected {action_id}, " f"got {result.action_id}"
            )

            assert result.started_at is not None, "Started timestamp must be set"

            # Property assertions - task not completed yet
            assert result.progress < 100.0, (
                f"Task should not be completed immediately, " f"but progress is {result.progress}%"
            )
            assert (
                result.completed_at is None
            ), "Task should not have completion timestamp immediately"

    @settings(max_examples=100, deadline=None)
    @given(
        short_duration=st.floats(min_value=0.1, max_value=0.5),
        long_duration=st.floats(min_value=2.0, max_value=5.0),
        action_id_prefix=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
        ),
    )
    def test_property_19_submission_time_independent_of_duration(
        self,
        short_duration: float,
        long_duration: float,
        action_id_prefix: str,
    ):
        """
        Property 19: Submission time independent of action duration.

        The time to submit an async task should be independent of the
        action's expected duration. Both short and long tasks should
        submit in similar time (<100ms).

        **Validates: Requirements 6.4**
        """
        with patch(
            "Agent_Guru.reasoning.execution.async_executor.execute_action_task"
        ) as mock_task:
            # Create mock async results
            mock_short_result = Mock()
            mock_short_result.id = f"task_short_{int(time.time() * 1000)}"

            mock_long_result = Mock()
            mock_long_result.id = f"task_long_{int(time.time() * 1000) + 1}"

            # Configure mock to return different results for each call
            mock_task.apply_async.side_effect = [mock_short_result, mock_long_result]

            executor = AsyncExecutor()

            # Submit short duration task
            short_action = Action(
                action_id=f"{action_id_prefix}_short",
                tool_id="test_tool",
                parameters={"duration": short_duration},
            )

            start_time = time.perf_counter()
            short_result = executor.execute_async(
                short_action,
                tool_module="time",
                tool_function_name="sleep",
            )
            short_submission_time = time.perf_counter() - start_time

            # Submit long duration task
            long_action = Action(
                action_id=f"{action_id_prefix}_long",
                tool_id="test_tool",
                parameters={"duration": long_duration},
            )

            start_time = time.perf_counter()
            long_result = executor.execute_async(
                long_action,
                tool_module="time",
                tool_function_name="sleep",
            )
            long_submission_time = time.perf_counter() - start_time

            # Property assertions - both submit quickly
            assert short_submission_time < 0.1, (
                f"Short task submission should be <100ms, "
                f"took {short_submission_time * 1000:.2f}ms"
            )
            assert long_submission_time < 0.1, (
                f"Long task submission should be <100ms, "
                f"took {long_submission_time * 1000:.2f}ms"
            )

            # Property assertions - submission times similar
            # Allow 50ms difference (generous tolerance for system variance)
            time_difference = abs(short_submission_time - long_submission_time)
            assert time_difference < 0.05, (
                f"Submission times should be similar regardless of duration: "
                f"short={short_submission_time * 1000:.2f}ms, "
                f"long={long_submission_time * 1000:.2f}ms, "
                f"difference={time_difference * 1000:.2f}ms"
            )

            # Property assertions - both tasks submitted successfully
            assert (
                short_result.task_id != long_result.task_id
            ), "Each task should have unique task ID"
            assert short_result.action_id == f"{action_id_prefix}_short"
            assert long_result.action_id == f"{action_id_prefix}_long"

    @settings(max_examples=100, deadline=None)
    @given(
        num_tasks=st.integers(min_value=1, max_value=5),
        task_duration=st.floats(min_value=1.0, max_value=3.0),
        action_id_prefix=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
        ),
    )
    def test_property_19_multiple_async_submissions_all_immediate(
        self,
        num_tasks: int,
        task_duration: float,
        action_id_prefix: str,
    ):
        """
        Property 19: Multiple async submissions all return immediately.

        When submitting multiple async tasks, each submission should
        return within 100ms, and total submission time should scale
        linearly (not waiting for tasks to complete).

        **Validates: Requirements 6.4**
        """
        with patch(
            "Agent_Guru.reasoning.execution.async_executor.execute_action_task"
        ) as mock_task:
            # Create mock async results for each task
            mock_results = []
            for i in range(num_tasks):
                mock_result = Mock()
                mock_result.id = f"task_{action_id_prefix}_{i}_{int(time.time() * 1000)}"
                mock_results.append(mock_result)

            mock_task.apply_async.side_effect = mock_results

            executor = AsyncExecutor()

            submission_times = []
            results = []

            # Submit multiple tasks
            total_start = time.perf_counter()
            for i in range(num_tasks):
                action = Action(
                    action_id=f"{action_id_prefix}_{i}",
                    tool_id="test_tool",
                    parameters={"duration": task_duration},
                )

                start_time = time.perf_counter()
                result = executor.execute_async(
                    action,
                    tool_module="time",
                    tool_function_name="sleep",
                )
                submission_time = time.perf_counter() - start_time

                submission_times.append(submission_time)
                results.append(result)

            total_submission_time = time.perf_counter() - total_start

            # Property assertions - each submission immediate
            for i, submission_time in enumerate(submission_times):
                assert submission_time < 0.1, (
                    f"Task {i} submission should be <100ms, " f"took {submission_time * 1000:.2f}ms"
                )

            # Property assertions - total time reasonable
            # Total should be < (num_tasks * 100ms) + overhead
            max_expected_time = (num_tasks * 0.1) + 0.1  # 100ms per task + 100ms overhead
            assert total_submission_time < max_expected_time, (
                f"Total submission time for {num_tasks} tasks should be "
                f"<{max_expected_time}s, took {total_submission_time}s"
            )

            # Property assertions - NOT waiting for task completion
            # If we were waiting, total time would be >= num_tasks * task_duration
            min_completion_time = num_tasks * task_duration
            assert total_submission_time < min_completion_time, (
                f"Total submission time {total_submission_time}s should be much less "
                f"than sequential completion time {min_completion_time}s, "
                f"proving tasks are async"
            )

            # Property assertions - all tasks submitted successfully
            assert len(results) == num_tasks, f"Should have {num_tasks} results, got {len(results)}"

            task_ids = [r.task_id for r in results]
            assert len(set(task_ids)) == num_tasks, "All tasks should have unique task IDs"

            for i, result in enumerate(results):
                assert (
                    result.action_id == f"{action_id_prefix}_{i}"
                ), f"Task {i} action_id should match"
                assert result.status in [
                    TaskStatus.PENDING,
                    TaskStatus.RUNNING,
                ], f"Task {i} should not be completed immediately"

    @settings(max_examples=100, deadline=None)
    @given(
        action_duration=st.floats(min_value=0.5, max_value=3.0),
        parameter_dict=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(
                st.integers(min_value=0, max_value=1000),
                st.text(min_size=0, max_size=50),
                st.booleans(),
            ),
            min_size=0,
            max_size=5,
        ),
    )
    def test_property_19_immediate_return_preserves_action_metadata(
        self,
        action_duration: float,
        parameter_dict: dict[str, Any],
    ):
        """
        Property 19: Immediate return preserves action metadata.

        When async execution returns immediately, the result should
        preserve all action metadata including action_id, parameters,
        and tool information.

        **Validates: Requirements 6.4**
        """
        with patch(
            "Agent_Guru.reasoning.execution.async_executor.execute_action_task"
        ) as mock_task:
            mock_async_result = Mock()
            mock_async_result.id = f"task_metadata_{int(time.time() * 1000)}"
            mock_task.apply_async.return_value = mock_async_result

            executor = AsyncExecutor()

            # Add duration to parameters
            parameters = {**parameter_dict, "duration": action_duration}

            action = Action(
                action_id="test_action_metadata",
                tool_id="test_tool_metadata",
                parameters=parameters,
            )

            # Submit async task
            start_time = time.perf_counter()
            result = executor.execute_async(
                action,
                tool_module="time",
                tool_function_name="sleep",
            )
            submission_time = time.perf_counter() - start_time

            # Property assertions - immediate return
            assert (
                submission_time < 0.1
            ), f"Submission should be <100ms, took {submission_time * 1000:.2f}ms"

            # Property assertions - metadata preserved
            assert result.action_id == "test_action_metadata", (
                f"Action ID should be preserved: expected test_action_metadata, "
                f"got {result.action_id}"
            )

            assert result.task_id is not None, "Task ID must be assigned"
            assert isinstance(result.task_id, str), "Task ID must be string"

            assert result.started_at is not None, "Started timestamp must be set"

            # Property assertions - initial state correct
            assert result.status in [
                TaskStatus.PENDING,
                TaskStatus.RUNNING,
            ], f"Initial status should be PENDING or RUNNING, got {result.status}"
            assert result.progress >= 0.0, "Progress should be non-negative"
            assert result.progress < 100.0, "Progress should not be 100% immediately"
            assert result.completed_at is None, "Should not be completed immediately"
            assert result.result_data is None, "Should not have result data immediately"

    @settings(max_examples=100, deadline=None)
    @given(
        action_duration=st.floats(min_value=1.0, max_value=5.0),
        action_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
        ),
    )
    def test_property_19_async_controller_returns_immediately(
        self,
        action_duration: float,
        action_id: str,
    ):
        """
        Property 19: AsyncExecutionController returns immediately.

        The high-level AsyncExecutionController should also return
        immediately when executing async tasks, maintaining the same
        <100ms guarantee.

        **Validates: Requirements 6.4**
        """
        with patch(
            "Agent_Guru.reasoning.execution.async_executor.execute_action_task"
        ) as mock_task:
            mock_async_result = Mock()
            mock_async_result.id = f"task_controller_{action_id}_{int(time.time() * 1000)}"
            mock_task.apply_async.return_value = mock_async_result

            controller = AsyncExecutionController()

            action = Action(
                action_id=action_id,
                tool_id="test_tool",
                parameters={"duration": action_duration},
            )

            # Submit via controller
            start_time = time.perf_counter()
            result = controller.execute_async(
                action,
                tool_module="time",
                tool_function_name="sleep",
            )
            submission_time = time.perf_counter() - start_time

            # Property assertions - immediate return
            assert submission_time < 0.1, (
                f"Controller async execution should return within 100ms, "
                f"but took {submission_time * 1000:.2f}ms for action "
                f"with duration {action_duration}s"
            )

            # Property assertions - result structure
            assert isinstance(
                result, AsyncExecutionResult
            ), f"Controller must return AsyncExecutionResult, got {type(result)}"

            assert result.task_id is not None, "Task ID must be assigned"
            assert result.action_id == action_id, "Action ID should be preserved"
            assert result.status in [
                TaskStatus.PENDING,
                TaskStatus.RUNNING,
            ], f"Initial status should be PENDING or RUNNING, got {result.status}"

    @settings(max_examples=100, deadline=None)
    @given(
        action_duration=st.floats(min_value=0.5, max_value=5.0),
        action_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                min_codepoint=ord("a"),
                max_codepoint=ord("z"),
            ),
        ),
    )
    def test_property_19_result_serializable_immediately(
        self,
        action_duration: float,
        action_id: str,
    ):
        """
        Property 19: Async result is serializable immediately.

        The AsyncExecutionResult returned immediately should be
        serializable to dictionary format without waiting for
        task completion.

        **Validates: Requirements 6.4**
        """
        with patch(
            "Agent_Guru.reasoning.execution.async_executor.execute_action_task"
        ) as mock_task:
            mock_async_result = Mock()
            mock_async_result.id = f"task_serialize_{action_id}_{int(time.time() * 1000)}"
            mock_task.apply_async.return_value = mock_async_result

            executor = AsyncExecutor()

            action = Action(
                action_id=action_id,
                tool_id="test_tool",
                parameters={"duration": action_duration},
            )

            # Submit async task
            start_time = time.perf_counter()
            result = executor.execute_async(
                action,
                tool_module="time",
                tool_function_name="sleep",
            )
            submission_time = time.perf_counter() - start_time

            # Property assertions - immediate return
            assert (
                submission_time < 0.1
            ), f"Submission should be <100ms, took {submission_time * 1000:.2f}ms"

            # Property assertions - immediate serialization
            serialize_start = time.perf_counter()
            result_dict = result.to_dict()
            serialize_time = time.perf_counter() - serialize_start

            assert (
                serialize_time < 0.01
            ), f"Serialization should be <10ms, took {serialize_time * 1000:.2f}ms"

            # Property assertions - serialized structure
            assert isinstance(
                result_dict, dict
            ), f"to_dict() must return dict, got {type(result_dict)}"

            required_fields = [
                "task_id",
                "status",
                "progress",
                "result_data",
                "error",
                "execution_time",
                "action_id",
                "started_at",
                "completed_at",
                "cancellable",
            ]

            for field in required_fields:
                assert field in result_dict, f"Serialized result missing required field: {field}"

            # Property assertions - serialized values
            assert result_dict["task_id"] == result.task_id
            assert result_dict["status"] == result.status.value
            assert result_dict["action_id"] == action_id
            assert result_dict["progress"] < 100.0, "Progress should not be 100% immediately"
            assert result_dict["completed_at"] is None, "Should not be completed immediately"
