"""Property-based tests for asynchronous execution engine.

**Validates: Requirements 6.4**
**Property 19: Async execution returns immediately**

These tests verify that async execution returns immediately without blocking,
regardless of action duration, across many random inputs using Hypothesis.

Note: These tests use mocking to avoid Redis/Celery infrastructure dependencies.
"""

import statistics
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.execution.async_executor import (
    AsyncExecutionController,
    AsyncExecutionResult,
    AsyncExecutor,
    TaskStatus,
)
from Agent_Guru.reasoning.models.action import Action


def _assert_handed_off_not_run(mock_task: Mock, action_spy: Mock, submissions: int = 1) -> None:
    """What "returns immediately" means: each action went to the queue and none ran here.

    These tests used to assert that submission took under 100 ms of wall
    clock. Submission does no I/O (the Celery task is mocked), so that only
    measured how busy the machine was: under load one run took 898 ms and
    failed, while a regression that ran the action inline would not have
    been caught, because the action is time.sleep and is replaced here.
    The action is a spy, so running it inline is seen directly, on any
    machine. Speed is measured by test_submission_median_latency below.
    """
    assert action_spy.call_count == 0, "the action ran during submission instead of being queued"  # nosec B101
    assert mock_task.apply_async.call_count == submissions  # nosec B101
    assert not mock_task.called, "the task was called directly instead of queued"  # nosec B101
    assert not mock_task.apply.called and not mock_task.delay.called  # nosec B101

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
        ) as mock_task, patch("time.sleep") as action_spy:
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
            result = executor.execute_async(
                action,
                tool_module="time",
                tool_function_name="sleep",
            )

            # Property assertions - immediate return
            _assert_handed_off_not_run(mock_task, action_spy)

            # Property assertions - result structure
            assert isinstance(result, AsyncExecutionResult), (  # nosec B101
                f"execute_async must return AsyncExecutionResult, " f"got {type(result)}"
            )

            # Property assertions - initial state
            assert result.task_id is not None, "Task ID must be assigned"  # nosec B101
            assert isinstance(  # nosec B101
                result.task_id, str
            ), f"Task ID must be string, got {type(result.task_id)}"
            assert len(result.task_id) > 0, "Task ID must not be empty"  # nosec B101

            assert result.status in [  # nosec B101
                TaskStatus.PENDING,
                TaskStatus.RUNNING,
            ], f"Initial status should be PENDING or RUNNING, got {result.status}"

            assert result.action_id == action_id, (  # nosec B101
                f"Action ID should be preserved: expected {action_id}, " f"got {result.action_id}"
            )

            assert result.started_at is not None, "Started timestamp must be set"  # nosec B101

            # Property assertions - task not completed yet
            assert result.progress < 100.0, (  # nosec B101
                f"Task should not be completed immediately, " f"but progress is {result.progress}%"
            )
            assert (  # nosec B101
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
        ) as mock_task, patch("time.sleep") as action_spy:
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

            short_result = executor.execute_async(
                short_action,
                tool_module="time",
                tool_function_name="sleep",
            )

            # Submit long duration task
            long_action = Action(
                action_id=f"{action_id_prefix}_long",
                tool_id="test_tool",
                parameters={"duration": long_duration},
            )

            long_result = executor.execute_async(
                long_action,
                tool_module="time",
                tool_function_name="sleep",
            )

            # Property assertions - neither waited for its action, and both were
            # submitted the same way whatever their duration.
            _assert_handed_off_not_run(mock_task, action_spy, submissions=2)
            submitted = [c.kwargs["args"][1:] for c in mock_task.apply_async.call_args_list]
            assert submitted == [["time", "sleep"], ["time", "sleep"]]  # nosec B101

            # Property assertions - both tasks submitted successfully
            assert (  # nosec B101
                short_result.task_id != long_result.task_id
            ), "Each task should have unique task ID"
            assert short_result.action_id == f"{action_id_prefix}_short"  # nosec B101
            assert long_result.action_id == f"{action_id_prefix}_long"  # nosec B101

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
        ) as mock_task, patch("time.sleep") as action_spy:
            # Create mock async results for each task
            mock_results = []
            for i in range(num_tasks):
                mock_result = Mock()
                mock_result.id = f"task_{action_id_prefix}_{i}_{int(time.time() * 1000)}"
                mock_results.append(mock_result)

            mock_task.apply_async.side_effect = mock_results

            executor = AsyncExecutor()

            results = []

            # Submit multiple tasks
            for i in range(num_tasks):
                action = Action(
                    action_id=f"{action_id_prefix}_{i}",
                    tool_id="test_tool",
                    parameters={"duration": task_duration},
                )

                result = executor.execute_async(
                    action,
                    tool_module="time",
                    tool_function_name="sleep",
                )

                results.append(result)


            # Property assertions - every task was queued, none ran here
            _assert_handed_off_not_run(mock_task, action_spy, submissions=num_tasks)

            # Property assertions - all tasks submitted successfully
            assert len(results) == num_tasks, f"Should have {num_tasks} results, got {len(results)}"  # nosec B101

            task_ids = [r.task_id for r in results]
            assert len(set(task_ids)) == num_tasks, "All tasks should have unique task IDs"  # nosec B101

            for i, result in enumerate(results):
                assert (  # nosec B101
                    result.action_id == f"{action_id_prefix}_{i}"
                ), f"Task {i} action_id should match"
                assert result.status in [  # nosec B101
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
        ) as mock_task, patch("time.sleep") as action_spy:
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
            result = executor.execute_async(
                action,
                tool_module="time",
                tool_function_name="sleep",
            )

            # Property assertions - immediate return
            _assert_handed_off_not_run(mock_task, action_spy)

            # Property assertions - metadata preserved
            assert result.action_id == "test_action_metadata", (  # nosec B101
                f"Action ID should be preserved: expected test_action_metadata, "
                f"got {result.action_id}"
            )

            assert result.task_id is not None, "Task ID must be assigned"  # nosec B101
            assert isinstance(result.task_id, str), "Task ID must be string"  # nosec B101

            assert result.started_at is not None, "Started timestamp must be set"  # nosec B101

            # Property assertions - initial state correct
            assert result.status in [  # nosec B101
                TaskStatus.PENDING,
                TaskStatus.RUNNING,
            ], f"Initial status should be PENDING or RUNNING, got {result.status}"
            assert result.progress >= 0.0, "Progress should be non-negative"  # nosec B101
            assert result.progress < 100.0, "Progress should not be 100% immediately"  # nosec B101
            assert result.completed_at is None, "Should not be completed immediately"  # nosec B101
            assert result.result_data is None, "Should not have result data immediately"  # nosec B101

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
        ) as mock_task, patch("time.sleep") as action_spy:
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
            result = controller.execute_async(
                action,
                tool_module="time",
                tool_function_name="sleep",
            )

            # Property assertions - immediate return
            _assert_handed_off_not_run(mock_task, action_spy)

            # Property assertions - result structure
            assert isinstance(  # nosec B101
                result, AsyncExecutionResult
            ), f"Controller must return AsyncExecutionResult, got {type(result)}"

            assert result.task_id is not None, "Task ID must be assigned"  # nosec B101
            assert result.action_id == action_id, "Action ID should be preserved"  # nosec B101
            assert result.status in [  # nosec B101
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
        ) as mock_task, patch("time.sleep") as action_spy:
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
            result = executor.execute_async(
                action,
                tool_module="time",
                tool_function_name="sleep",
            )

            # Property assertions - immediate return
            _assert_handed_off_not_run(mock_task, action_spy)

            # Property assertions - serializable while the task is still pending
            result_dict = result.to_dict()

            # Property assertions - serialized structure
            assert isinstance(  # nosec B101
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
                assert field in result_dict, f"Serialized result missing required field: {field}"  # nosec B101

            # Property assertions - serialized values
            assert result_dict["task_id"] == result.task_id  # nosec B101
            assert result_dict["status"] == result.status.value  # nosec B101
            assert result_dict["action_id"] == action_id  # nosec B101
            assert result_dict["progress"] < 100.0, "Progress should not be 100% immediately"  # nosec B101
            assert result_dict["completed_at"] is None, "Should not be completed immediately"  # nosec B101


@pytest.mark.performance
def test_submission_median_latency():
    """Submitting a task stays far below a millisecond, measured as a median.

    Method: 200 submissions with the Celery task mocked, as in the property
    tests above; the median is compared with 5 ms. A median ignores the
    occasional scheduler stall that made single wall-clock checks fail
    under load. Measured on the development laptop (Intel 12th generation,
    Windows 11, Python 3.13): median 0.013 ms, p95 0.047 ms. The bound
    leaves room for slow CI runners and still fails if submission starts
    waiting on a broker connection or on the action itself.
    """
    with patch(
        "Agent_Guru.reasoning.execution.async_executor.execute_action_task"
    ) as mock_task, patch("time.sleep") as action_spy:
        mock_task.apply_async.return_value = Mock(id="task_latency")
        executor = AsyncExecutor()
        action = Action(action_id="latency", tool_id="test_tool", parameters={"duration": 1.0})
        times = []
        for _ in range(200):
            started = time.perf_counter()
            executor.execute_async(action, tool_module="time", tool_function_name="sleep")
            times.append(time.perf_counter() - started)
        _assert_handed_off_not_run(mock_task, action_spy, submissions=200)
    assert statistics.median(times) < 0.005, f"median {statistics.median(times) * 1000:.3f} ms"  # nosec B101

