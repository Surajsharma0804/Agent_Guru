"""Tests for synchronous execution engine."""

import time
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.execution.executor import (
    ExecutionController,
    ExecutionResult,
    SyncExecutor,
)
from Agent_Guru.reasoning.models.action import Action


class TestExecutionResult:
    """Tests for ExecutionResult."""

    def test_result_creation_success(self):
        """Test creating successful result."""
        result = ExecutionResult(
            success=True,
            result_data={"value": 42},
            execution_time=0.5,
            action_id="test_1",
        )

        assert result.success is True
        assert result.result_data == {"value": 42}
        assert result.error is None
        assert result.execution_time == 0.5
        assert result.action_id == "test_1"
        assert result.retries == 0

    def test_result_creation_failure(self):
        """Test creating failed result."""
        error = {
            "error_code": "TEST_ERROR",
            "message": "Test error",
            "details": {},
            "recoverable": False,
        }

        result = ExecutionResult(
            success=False,
            error=error,
            execution_time=0.1,
            action_id="test_2",
            retries=2,
        )

        assert result.success is False
        assert result.result_data is None
        assert result.error == error
        assert result.execution_time == 0.1
        assert result.action_id == "test_2"
        assert result.retries == 2

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ExecutionResult(
            success=True,
            result_data={"value": 42},
            execution_time=0.5,
            action_id="test_1",
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["result_data"] == {"value": 42}
        assert result_dict["error"] is None
        assert result_dict["execution_time"] == 0.5
        assert result_dict["action_id"] == "test_1"
        assert result_dict["retries"] == 0
        assert "timestamp" in result_dict


class TestSyncExecutor:
    """Tests for SyncExecutor."""

    def test_executor_initialization(self):
        """Test executor initialization."""
        executor = SyncExecutor(
            default_timeout=5.0,
            max_retries=2,
            retry_delay=1.0,
        )

        assert executor.default_timeout == 5.0
        assert executor.max_retries == 2
        assert executor.retry_delay == 1.0

    def test_executor_invalid_timeout(self):
        """Test executor with invalid timeout."""
        with pytest.raises(ValueError):
            SyncExecutor(default_timeout=-1.0)

    def test_executor_invalid_retries(self):
        """Test executor with invalid retries."""
        with pytest.raises(ValueError):
            SyncExecutor(max_retries=-1)

    def test_executor_invalid_delay(self):
        """Test executor with invalid delay."""
        with pytest.raises(ValueError):
            SyncExecutor(retry_delay=-1.0)

    def test_execute_successful_action(self):
        """Test executing successful action."""
        executor = SyncExecutor()

        action = Action(
            action_id="test_1",
            tool_id="test_tool",
            parameters={"value": 42},
        )

        def tool_function(params):
            return {"result": params["value"] * 2}

        result = executor.execute(action, tool_function)

        assert result.success is True
        assert result.result_data == {"result": 84}
        assert result.error is None
        assert result.execution_time > 0
        assert result.action_id == "test_1"
        assert result.retries == 0

    def test_execute_action_with_error(self):
        """Test executing action that raises error."""
        executor = SyncExecutor(max_retries=0)

        action = Action(
            action_id="test_2",
            tool_id="test_tool",
            parameters={},
        )

        def tool_function(params):
            raise ValueError("Test error")

        result = executor.execute(action, tool_function)

        assert result.success is False
        assert result.result_data is None
        assert result.error is not None
        assert result.error["error_code"] == "ValueError"
        assert "Test error" in result.error["message"]
        assert result.action_id == "test_2"

    def test_execute_action_with_timeout(self):
        """Test executing action that times out."""
        executor = SyncExecutor(default_timeout=0.1)

        action = Action(
            action_id="test_3",
            tool_id="test_tool",
            parameters={},
        )

        def tool_function(params):
            time.sleep(0.2)  # Exceed timeout
            return {"result": "done"}

        result = executor.execute(action, tool_function)

        assert result.success is False
        assert result.error is not None
        assert result.error["error_code"] == "TIMEOUT"
        assert result.action_id == "test_3"

    def test_execute_with_custom_timeout(self):
        """Test executing with custom timeout."""
        executor = SyncExecutor(default_timeout=1.0)

        action = Action(
            action_id="test_4",
            tool_id="test_tool",
            parameters={},
        )

        def tool_function(params):
            time.sleep(0.05)
            return {"result": "done"}

        result = executor.execute(action, tool_function, timeout=0.5)

        assert result.success is True
        assert result.result_data == {"result": "done"}

    def test_execute_with_transient_error_retry(self):
        """Test retry on transient error."""
        executor = SyncExecutor(max_retries=2, retry_delay=0.01)

        action = Action(
            action_id="test_5",
            tool_id="test_tool",
            parameters={},
        )

        call_count = 0

        def tool_function(params):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary connection error")
            return {"result": "success"}

        result = executor.execute(action, tool_function)

        assert result.success is True
        assert result.result_data == {"result": "success"}
        assert result.retries == 1  # One retry
        assert call_count == 2

    def test_execute_max_retries_exceeded(self):
        """Test max retries exceeded."""
        executor = SyncExecutor(max_retries=2, retry_delay=0.01)

        action = Action(
            action_id="test_6",
            tool_id="test_tool",
            parameters={},
        )

        def tool_function(params):
            raise ConnectionError("Persistent connection error")

        result = executor.execute(action, tool_function)

        assert result.success is False
        assert result.error is not None
        assert result.retries == 2  # Max retries

    def test_execute_non_transient_error_no_retry(self):
        """Test non-transient error doesn't retry."""
        executor = SyncExecutor(max_retries=3, retry_delay=0.01)

        action = Action(
            action_id="test_7",
            tool_id="test_tool",
            parameters={},
        )

        call_count = 0

        def tool_function(params):
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-transient error")

        result = executor.execute(action, tool_function)

        assert result.success is False
        assert result.retries == 0  # No retries
        assert call_count == 1  # Only called once

    def test_latency_tracking(self):
        """Test latency tracking."""
        executor = SyncExecutor()

        action = Action(
            action_id="test_8",
            tool_id="test_tool",
            parameters={},
        )

        def tool_function(params):
            time.sleep(0.01)
            return {"result": "done"}

        # Execute multiple times
        for _ in range(5):
            executor.execute(action, tool_function)

        stats = executor.get_latency_stats("test_tool")

        assert stats["count"] == 5
        assert stats["min"] > 0
        assert stats["max"] > 0
        assert stats["avg"] > 0
        assert stats["p95"] > 0

    def test_latency_stats_empty(self):
        """Test latency stats for unknown tool."""
        executor = SyncExecutor()

        stats = executor.get_latency_stats("unknown_tool")

        assert stats["count"] == 0
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["avg"] == 0.0
        assert stats["p95"] == 0.0

    def test_latency_stats_limit(self):
        """Test latency stats limited to 100 entries."""
        executor = SyncExecutor()

        action = Action(
            action_id="test_9",
            tool_id="test_tool",
            parameters={},
        )

        def tool_function(params):
            return {"result": "done"}

        # Execute 150 times
        for _ in range(150):
            executor.execute(action, tool_function)

        stats = executor.get_latency_stats("test_tool")

        # Should only keep last 100
        assert stats["count"] == 100

    def test_clear_latency_stats_specific(self):
        """Test clearing latency stats for specific tool."""
        executor = SyncExecutor()

        action1 = Action(action_id="1", tool_id="tool1", parameters={})
        action2 = Action(action_id="2", tool_id="tool2", parameters={})

        def tool_function(params):
            return {"result": "done"}

        executor.execute(action1, tool_function)
        executor.execute(action2, tool_function)

        executor.clear_latency_stats("tool1")

        stats1 = executor.get_latency_stats("tool1")
        stats2 = executor.get_latency_stats("tool2")

        assert stats1["count"] == 0
        assert stats2["count"] == 1

    def test_clear_latency_stats_all(self):
        """Test clearing all latency stats."""
        executor = SyncExecutor()

        action1 = Action(action_id="1", tool_id="tool1", parameters={})
        action2 = Action(action_id="2", tool_id="tool2", parameters={})

        def tool_function(params):
            return {"result": "done"}

        executor.execute(action1, tool_function)
        executor.execute(action2, tool_function)

        executor.clear_latency_stats()

        stats1 = executor.get_latency_stats("tool1")
        stats2 = executor.get_latency_stats("tool2")

        assert stats1["count"] == 0
        assert stats2["count"] == 0


class TestExecutionController:
    """Tests for ExecutionController."""

    def test_controller_initialization(self):
        """Test controller initialization."""
        controller = ExecutionController(
            default_timeout=5.0,
            max_retries=2,
        )

        assert controller.sync_executor.default_timeout == 5.0
        assert controller.sync_executor.max_retries == 2

    def test_controller_execute_sync(self):
        """Test synchronous execution through controller."""
        controller = ExecutionController()

        action = Action(
            action_id="test_1",
            tool_id="test_tool",
            parameters={"value": 42},
        )

        def tool_function(params):
            return {"result": params["value"] * 2}

        result = controller.execute_sync(action, tool_function)

        assert result.success is True
        assert result.result_data == {"result": 84}

    def test_controller_get_latency_stats(self):
        """Test getting latency stats through controller."""
        controller = ExecutionController()

        action = Action(
            action_id="test_2",
            tool_id="test_tool",
            parameters={},
        )

        def tool_function(params):
            return {"result": "done"}

        controller.execute_sync(action, tool_function)

        stats = controller.get_latency_stats("test_tool")

        assert stats["count"] == 1
        assert stats["avg"] > 0


# ============================================================================
# Property-Based Tests for Execution Timeouts
# ============================================================================


class TestExecutionTimeoutProperties:
    """Property-based tests for execution timeout behavior.

    **Validates: Requirements 6.2, 10.1**
    **Property 17: Synchronous execution respects timeout**

    These tests verify that execution exceeding timeout is cancelled
    and returns a timeout error across many random inputs.
    """

    @settings(max_examples=100, deadline=None)
    @given(
        timeout=st.floats(min_value=0.01, max_value=0.2),
        execution_duration=st.floats(min_value=0.25, max_value=0.5),
        action_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), min_codepoint=ord("a"), max_codepoint=ord("z")
            ),
        ),
        tool_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), min_codepoint=ord("a"), max_codepoint=ord("z")
            ),
        ),
    )
    def test_property_17_timeout_enforcement(
        self,
        timeout: float,
        execution_duration: float,
        action_id: str,
        tool_id: str,
    ):
        """
        Property 17: Synchronous execution respects timeout.

        For any action with execution time exceeding the configured timeout,
        the executor should cancel the operation and return a timeout error.

        **Validates: Requirements 6.2, 10.1**
        """
        # Setup executor with no retries to avoid retry delays
        executor = SyncExecutor(default_timeout=timeout, max_retries=0)

        action = Action(
            action_id=action_id,
            tool_id=tool_id,
            parameters={"duration": execution_duration},
        )

        def slow_tool_function(params):
            """Tool function that takes longer than timeout."""
            time.sleep(params["duration"])
            return {"result": "completed"}

        # Execute action
        result = executor.execute(action, slow_tool_function)

        # Property assertions
        assert (
            result.success is False
        ), f"Expected failure for timeout={timeout}s, duration={execution_duration}s"
        assert result.error is not None, "Expected error information for timeout"
        assert (
            result.error["error_code"] == "TIMEOUT"
        ), f"Expected TIMEOUT error code, got {result.error['error_code']}"
        assert result.timed_out is True, "Expected timed_out flag to be True"
        assert result.action_id == action_id, "Action ID should be preserved"
        assert (
            result.execution_time >= timeout
        ), f"Execution time {result.execution_time}s should be >= timeout {timeout}s"
        assert "timeout" in result.error["message"].lower(), "Error message should mention timeout"
        assert result.error["recoverable"] is False, "Timeout errors should not be recoverable"

    @settings(max_examples=100, deadline=None)
    @given(
        timeout=st.floats(min_value=0.3, max_value=0.5),
        execution_duration=st.floats(min_value=0.01, max_value=0.2),
        result_value=st.integers(min_value=-1000, max_value=1000),
    )
    def test_property_17_no_timeout_when_within_budget(
        self,
        timeout: float,
        execution_duration: float,
        result_value: int,
    ):
        """
        Property 17 (inverse): Execution within timeout succeeds.

        For any action with execution time within the configured timeout,
        the executor should complete successfully without timeout error.

        **Validates: Requirements 6.2, 10.1**
        """
        executor = SyncExecutor(default_timeout=timeout, max_retries=0)

        action = Action(
            action_id="test_action",
            tool_id="fast_tool",
            parameters={"duration": execution_duration, "value": result_value},
        )

        def fast_tool_function(params):
            """Tool function that completes within timeout."""
            time.sleep(params["duration"])
            return {"result": params["value"] * 2}

        # Execute action
        result = executor.execute(action, fast_tool_function)

        # Property assertions
        assert (
            result.success is True
        ), f"Expected success for timeout={timeout}s, duration={execution_duration}s"
        assert result.error is None, "Expected no error for successful execution"
        assert result.timed_out is False, "Expected timed_out flag to be False"
        assert result.result_data == {
            "result": result_value * 2
        }, "Result data should match expected computation"
        assert (
            result.execution_time < timeout
        ), f"Execution time {result.execution_time}s should be < timeout {timeout}s"

    @settings(max_examples=100, deadline=None)
    @given(
        default_timeout=st.floats(min_value=0.4, max_value=0.6),
        custom_timeout=st.floats(min_value=0.01, max_value=0.15),
        execution_duration=st.floats(min_value=0.2, max_value=0.35),
    )
    def test_property_17_custom_timeout_overrides_default(
        self,
        default_timeout: float,
        custom_timeout: float,
        execution_duration: float,
    ):
        """
        Property 17 (custom timeout): Custom timeout overrides default.

        When a custom timeout is provided, it should be used instead of
        the default timeout, and timeout enforcement should respect it.

        **Validates: Requirements 6.2, 10.1**
        """
        executor = SyncExecutor(default_timeout=default_timeout, max_retries=0)

        action = Action(
            action_id="test_action",
            tool_id="test_tool",
            parameters={"duration": execution_duration},
        )

        def tool_function(params):
            time.sleep(params["duration"])
            return {"result": "done"}

        # Execute with custom timeout (shorter than execution duration)
        result = executor.execute(action, tool_function, timeout=custom_timeout)

        # Property assertions
        assert result.success is False, (
            f"Expected timeout with custom_timeout={custom_timeout}s, "
            f"duration={execution_duration}s"
        )
        assert result.error is not None, "Expected timeout error"
        assert result.error["error_code"] == "TIMEOUT", "Expected TIMEOUT error code"
        assert result.timed_out is True, "Expected timed_out flag to be True"
        # Execution time should be close to custom timeout, not default
        assert result.execution_time >= custom_timeout, (
            f"Execution time {result.execution_time}s should be >= "
            f"custom timeout {custom_timeout}s"
        )
        # Allow some tolerance for execution time measurement
        assert result.execution_time < default_timeout + 0.1, (
            f"Execution time {result.execution_time}s should be < "
            f"default timeout {default_timeout}s + tolerance (proving custom timeout was used)"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        timeout=st.floats(min_value=0.05, max_value=0.15),
        num_actions=st.integers(min_value=1, max_value=3),
        execution_duration=st.floats(min_value=0.2, max_value=0.4),
    )
    def test_property_17_timeout_applies_to_each_execution(
        self,
        timeout: float,
        num_actions: int,
        execution_duration: float,
    ):
        """
        Property 17 (multiple executions): Timeout applies independently.

        Each execution should have its own timeout enforcement,
        and multiple timeouts should not accumulate.

        **Validates: Requirements 6.2, 10.1**
        """
        executor = SyncExecutor(default_timeout=timeout, max_retries=0)

        def slow_tool_function(params):
            time.sleep(params["duration"])
            return {"result": "done"}

        # Execute multiple actions
        results = []
        for i in range(num_actions):
            action = Action(
                action_id=f"action_{i}",
                tool_id="test_tool",
                parameters={"duration": execution_duration},
            )
            result = executor.execute(action, slow_tool_function)
            results.append(result)

        # Property assertions - all should timeout independently
        assert len(results) == num_actions, "Should have result for each action"

        for i, result in enumerate(results):
            assert result.success is False, (
                f"Action {i} should timeout with timeout={timeout}s, "
                f"duration={execution_duration}s"
            )
            assert result.error is not None, f"Action {i} should have error"
            assert result.error["error_code"] == "TIMEOUT", f"Action {i} should have TIMEOUT error"
            assert result.timed_out is True, f"Action {i} should have timed_out flag set"
            # Each execution should timeout around the same time
            assert result.execution_time >= timeout, (
                f"Action {i} execution time {result.execution_time}s "
                f"should be >= timeout {timeout}s"
            )

    @settings(max_examples=100, deadline=None)
    @given(
        timeout=st.floats(min_value=0.05, max_value=0.2),
        execution_duration=st.floats(min_value=0.25, max_value=0.5),
        parameter_value=st.integers(min_value=0, max_value=1000),
    )
    def test_property_17_timeout_preserves_action_metadata(
        self,
        timeout: float,
        execution_duration: float,
        parameter_value: int,
    ):
        """
        Property 17 (metadata preservation): Timeout preserves action info.

        When an action times out, the result should preserve all action
        metadata including action_id, tool_id, and parameters.

        **Validates: Requirements 6.2, 10.1**
        """
        executor = SyncExecutor(default_timeout=timeout, max_retries=0)

        action_id = f"action_{parameter_value}"
        tool_id = f"tool_{parameter_value}"

        action = Action(
            action_id=action_id,
            tool_id=tool_id,
            parameters={"duration": execution_duration, "value": parameter_value},
        )

        def slow_tool_function(params):
            time.sleep(params["duration"])
            return {"result": params["value"]}

        # Execute action
        result = executor.execute(action, slow_tool_function)

        # Property assertions - metadata should be preserved
        assert result.success is False, "Expected timeout"
        assert result.error is not None, "Expected error information"
        assert result.error["error_code"] == "TIMEOUT", "Expected TIMEOUT error"
        assert result.timed_out is True, "Expected timed_out flag"

        # Verify metadata preservation
        assert result.action_id == action_id, (
            f"Action ID should be preserved: expected {action_id}, " f"got {result.action_id}"
        )
        assert result.execution_time > 0, "Execution time should be recorded"
        assert result.retries == 0, "No retries should occur for timeout"
        assert "timeout" in result.error["details"], "Error details should include timeout value"
        assert result.error["details"]["timeout"] == timeout, (
            f"Error details should record timeout value: expected {timeout}, "
            f"got {result.error['details']['timeout']}"
        )

    @settings(max_examples=100, deadline=None)
    @given(
        timeout=st.floats(min_value=0.05, max_value=0.2),
        execution_duration=st.floats(min_value=0.25, max_value=0.5),
    )
    def test_property_17_timeout_error_structure(
        self,
        timeout: float,
        execution_duration: float,
    ):
        """
        Property 17 (error structure): Timeout error has required fields.

        Timeout errors should have a consistent structure with all
        required fields: error_code, message, details, recoverable.

        **Validates: Requirements 6.2, 10.1**
        """
        executor = SyncExecutor(default_timeout=timeout, max_retries=0)

        action = Action(
            action_id="test_action",
            tool_id="test_tool",
            parameters={"duration": execution_duration},
        )

        def slow_tool_function(params):
            time.sleep(params["duration"])
            return {"result": "done"}

        # Execute action
        result = executor.execute(action, slow_tool_function)

        # Property assertions - error structure
        assert result.success is False, "Expected timeout failure"
        assert result.error is not None, "Expected error object"

        # Verify required error fields
        required_fields = ["error_code", "message", "details", "recoverable"]
        for field in required_fields:
            assert field in result.error, f"Error should contain required field: {field}"

        # Verify error field values
        assert result.error["error_code"] == "TIMEOUT", "Error code should be TIMEOUT"
        assert isinstance(result.error["message"], str), "Error message should be a string"
        assert len(result.error["message"]) > 0, "Error message should not be empty"
        assert isinstance(result.error["details"], dict), "Error details should be a dictionary"
        assert isinstance(
            result.error["recoverable"], bool
        ), "Error recoverable should be a boolean"
        assert result.error["recoverable"] is False, "Timeout errors should not be recoverable"

        # Verify timeout value in details
        assert "timeout" in result.error["details"], "Error details should include timeout value"
        assert result.error["details"]["timeout"] == timeout, (
            f"Error details timeout should match: expected {timeout}, "
            f"got {result.error['details']['timeout']}"
        )


class TestExecutionResultStructureProperties:
    """Property-based tests for execution result structure.

    **Validates: Requirements 6.5**
    **Property 18: Execution results are structured**

    These tests verify that all execution results (success or failure)
    contain required fields with correct types and values across many
    random inputs.
    """

    @settings(max_examples=100, deadline=None)
    @given(
        execution_duration=st.floats(min_value=0.001, max_value=0.1),
        result_value=st.one_of(
            st.integers(min_value=-1000, max_value=1000),
            st.text(min_size=0, max_size=100),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.one_of(st.integers(), st.text(), st.booleans()),
                min_size=0,
                max_size=5,
            ),
            st.lists(st.integers(), min_size=0, max_size=10),
            st.none(),
        ),
        action_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), min_codepoint=ord("a"), max_codepoint=ord("z")
            ),
        ),
        tool_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), min_codepoint=ord("a"), max_codepoint=ord("z")
            ),
        ),
    )
    def test_property_18_successful_execution_result_structure(
        self,
        execution_duration: float,
        result_value: Any,
        action_id: str,
        tool_id: str,
    ):
        """
        Property 18: Successful execution results are structured.

        For any successful action execution, the ExecutionResult should
        contain all required fields: success=True, result_data, execution_time,
        action_id, and error=None.

        **Validates: Requirements 6.5**
        """
        executor = SyncExecutor(default_timeout=1.0, max_retries=0)

        action = Action(
            action_id=action_id,
            tool_id=tool_id,
            parameters={"duration": execution_duration, "value": result_value},
        )

        def successful_tool_function(params):
            """Tool function that succeeds."""
            time.sleep(params["duration"])
            return params["value"]

        # Execute action
        result = executor.execute(action, successful_tool_function)

        # Property assertions - required fields present
        assert hasattr(result, "success"), "Result must have 'success' field"
        assert hasattr(result, "result_data"), "Result must have 'result_data' field"
        assert hasattr(result, "error"), "Result must have 'error' field"
        assert hasattr(result, "execution_time"), "Result must have 'execution_time' field"
        assert hasattr(result, "action_id"), "Result must have 'action_id' field"

        # Property assertions - field types
        assert isinstance(result.success, bool), f"success must be bool, got {type(result.success)}"
        assert isinstance(
            result.execution_time, (int, float)
        ), f"execution_time must be numeric, got {type(result.execution_time)}"
        assert isinstance(
            result.action_id, str
        ), f"action_id must be str, got {type(result.action_id)}"

        # Property assertions - success case values
        assert result.success is True, "Successful execution should have success=True"
        assert result.result_data == result_value, (
            f"result_data should match returned value: expected {result_value}, "
            f"got {result.result_data}"
        )
        assert result.error is None, "Successful execution should have error=None"
        assert (
            result.execution_time > 0
        ), f"execution_time should be positive, got {result.execution_time}"
        assert result.execution_time >= execution_duration, (
            f"execution_time {result.execution_time}s should be >= "
            f"actual duration {execution_duration}s"
        )
        assert (
            result.action_id == action_id
        ), f"action_id should be preserved: expected {action_id}, got {result.action_id}"

    @settings(max_examples=100, deadline=None)
    @given(
        error_type=st.sampled_from(
            [
                ValueError,
                RuntimeError,
                TypeError,
                KeyError,
                AttributeError,
            ]
        ),
        error_message=st.text(min_size=1, max_size=100),
        action_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), min_codepoint=ord("a"), max_codepoint=ord("z")
            ),
        ),
        tool_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), min_codepoint=ord("a"), max_codepoint=ord("z")
            ),
        ),
    )
    def test_property_18_failed_execution_result_structure(
        self,
        error_type: type,
        error_message: str,
        action_id: str,
        tool_id: str,
    ):
        """
        Property 18: Failed execution results are structured.

        For any failed action execution, the ExecutionResult should
        contain all required fields: success=False, error (with error_code,
        message, details, recoverable), execution_time, action_id, and
        result_data=None.

        **Validates: Requirements 6.5**
        """
        executor = SyncExecutor(default_timeout=1.0, max_retries=0)

        action = Action(
            action_id=action_id,
            tool_id=tool_id,
            parameters={"error_type": error_type, "message": error_message},
        )

        def failing_tool_function(params):
            """Tool function that raises an error."""
            error_class = params["error_type"]
            raise error_class(params["message"])

        # Execute action
        result = executor.execute(action, failing_tool_function)

        # Property assertions - required fields present
        assert hasattr(result, "success"), "Result must have 'success' field"
        assert hasattr(result, "result_data"), "Result must have 'result_data' field"
        assert hasattr(result, "error"), "Result must have 'error' field"
        assert hasattr(result, "execution_time"), "Result must have 'execution_time' field"
        assert hasattr(result, "action_id"), "Result must have 'action_id' field"

        # Property assertions - field types
        assert isinstance(result.success, bool), f"success must be bool, got {type(result.success)}"
        assert isinstance(
            result.execution_time, (int, float)
        ), f"execution_time must be numeric, got {type(result.execution_time)}"
        assert isinstance(
            result.action_id, str
        ), f"action_id must be str, got {type(result.action_id)}"

        # Property assertions - failure case values
        assert result.success is False, "Failed execution should have success=False"
        assert result.result_data is None, "Failed execution should have result_data=None"
        assert result.error is not None, "Failed execution must have error information"
        assert isinstance(result.error, dict), f"error must be dict, got {type(result.error)}"

        # Property assertions - error structure
        required_error_fields = ["error_code", "message", "details", "recoverable"]
        for field in required_error_fields:
            assert field in result.error, f"error must contain required field: {field}"

        # Property assertions - error field types
        assert isinstance(
            result.error["error_code"], str
        ), f"error_code must be str, got {type(result.error['error_code'])}"
        assert isinstance(
            result.error["message"], str
        ), f"error message must be str, got {type(result.error['message'])}"
        assert isinstance(
            result.error["details"], dict
        ), f"error details must be dict, got {type(result.error['details'])}"
        assert isinstance(
            result.error["recoverable"], bool
        ), f"error recoverable must be bool, got {type(result.error['recoverable'])}"

        # Property assertions - error field values
        assert result.error["error_code"] == error_type.__name__, (
            f"error_code should match exception type: expected {error_type.__name__}, "
            f"got {result.error['error_code']}"
        )
        assert len(result.error["message"]) > 0, "error message should not be empty"
        assert (
            result.execution_time > 0
        ), f"execution_time should be positive, got {result.execution_time}"
        assert (
            result.action_id == action_id
        ), f"action_id should be preserved: expected {action_id}, got {result.action_id}"

    @settings(max_examples=100, deadline=None)
    @given(
        timeout=st.floats(min_value=0.01, max_value=0.1),
        execution_duration=st.floats(min_value=0.15, max_value=0.3),
        action_id=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), min_codepoint=ord("a"), max_codepoint=ord("z")
            ),
        ),
    )
    def test_property_18_timeout_result_structure(
        self,
        timeout: float,
        execution_duration: float,
        action_id: str,
    ):
        """
        Property 18: Timeout execution results are structured.

        For any timed-out action execution, the ExecutionResult should
        contain all required fields with timeout-specific values.

        **Validates: Requirements 6.5**
        """
        executor = SyncExecutor(default_timeout=timeout, max_retries=0)

        action = Action(
            action_id=action_id,
            tool_id="slow_tool",
            parameters={"duration": execution_duration},
        )

        def slow_tool_function(params):
            time.sleep(params["duration"])
            return {"result": "done"}

        # Execute action
        result = executor.execute(action, slow_tool_function)

        # Property assertions - all required fields present
        assert hasattr(result, "success"), "Result must have 'success' field"
        assert hasattr(result, "result_data"), "Result must have 'result_data' field"
        assert hasattr(result, "error"), "Result must have 'error' field"
        assert hasattr(result, "execution_time"), "Result must have 'execution_time' field"
        assert hasattr(result, "action_id"), "Result must have 'action_id' field"
        assert hasattr(result, "timed_out"), "Result must have 'timed_out' field"

        # Property assertions - timeout case values
        assert result.success is False, "Timeout should have success=False"
        assert result.result_data is None, "Timeout should have result_data=None"
        assert result.error is not None, "Timeout must have error information"
        assert result.timed_out is True, "Timeout should have timed_out=True"
        assert (
            result.error["error_code"] == "TIMEOUT"
        ), f"Timeout error_code should be TIMEOUT, got {result.error['error_code']}"
        assert (
            result.execution_time >= timeout
        ), f"execution_time {result.execution_time}s should be >= timeout {timeout}s"
        assert (
            result.action_id == action_id
        ), f"action_id should be preserved: expected {action_id}, got {result.action_id}"

    @settings(max_examples=100, deadline=None)
    @given(
        execution_duration=st.floats(min_value=0.001, max_value=0.05),
        result_value=st.integers(min_value=0, max_value=1000),
        num_executions=st.integers(min_value=1, max_value=5),
    )
    def test_property_18_multiple_executions_consistent_structure(
        self,
        execution_duration: float,
        result_value: int,
        num_executions: int,
    ):
        """
        Property 18: Multiple executions have consistent structure.

        For any sequence of action executions, all ExecutionResults should
        have the same structure with all required fields present.

        **Validates: Requirements 6.5**
        """
        executor = SyncExecutor(default_timeout=1.0, max_retries=0)

        def tool_function(params):
            time.sleep(params["duration"])
            return params["value"] * 2

        # Execute multiple actions
        results = []
        for i in range(num_executions):
            action = Action(
                action_id=f"action_{i}",
                tool_id="test_tool",
                parameters={"duration": execution_duration, "value": result_value + i},
            )
            result = executor.execute(action, tool_function)
            results.append(result)

        # Property assertions - all results have consistent structure
        assert (
            len(results) == num_executions
        ), f"Should have {num_executions} results, got {len(results)}"

        required_fields = ["success", "result_data", "error", "execution_time", "action_id"]

        for i, result in enumerate(results):
            # Check all required fields present
            for field in required_fields:
                assert hasattr(result, field), f"Result {i} missing required field: {field}"

            # Check field types
            assert isinstance(result.success, bool), f"Result {i} success must be bool"
            assert isinstance(
                result.execution_time, (int, float)
            ), f"Result {i} execution_time must be numeric"
            assert isinstance(result.action_id, str), f"Result {i} action_id must be str"

            # Check success case values
            assert result.success is True, f"Result {i} should succeed"
            assert (
                result.result_data == (result_value + i) * 2
            ), f"Result {i} data should match computation"
            assert result.error is None, f"Result {i} should have no error"
            assert result.execution_time > 0, f"Result {i} execution_time should be positive"
            assert result.action_id == f"action_{i}", f"Result {i} action_id should match"

    @settings(max_examples=100, deadline=None)
    @given(
        execution_duration=st.floats(min_value=0.001, max_value=0.05),
        result_value=st.one_of(
            st.integers(),
            st.text(),
            st.booleans(),
            st.lists(st.integers()),
            st.dictionaries(st.text(), st.integers()),
        ),
    )
    def test_property_18_result_serialization(
        self,
        execution_duration: float,
        result_value: Any,
    ):
        """
        Property 18: Execution results can be serialized.

        For any execution result, calling to_dict() should produce a
        dictionary with all required fields that can be serialized to JSON.

        **Validates: Requirements 6.5**
        """
        executor = SyncExecutor(default_timeout=1.0, max_retries=0)

        action = Action(
            action_id="test_action",
            tool_id="test_tool",
            parameters={"duration": execution_duration, "value": result_value},
        )

        def tool_function(params):
            time.sleep(params["duration"])
            return params["value"]

        # Execute action
        result = executor.execute(action, tool_function)

        # Property assertions - serialization
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict), f"to_dict() must return dict, got {type(result_dict)}"

        # Check all required fields in serialized form
        required_fields = [
            "success",
            "result_data",
            "error",
            "execution_time",
            "action_id",
            "retries",
            "timed_out",
            "timestamp",
        ]

        for field in required_fields:
            assert field in result_dict, f"Serialized result missing required field: {field}"

        # Verify serialized values match original
        assert result_dict["success"] == result.success
        assert result_dict["result_data"] == result.result_data
        assert result_dict["error"] == result.error
        assert result_dict["execution_time"] == result.execution_time
        assert result_dict["action_id"] == result.action_id
        assert result_dict["retries"] == result.retries
        assert result_dict["timed_out"] == result.timed_out

        # Verify timestamp is ISO format string
        assert isinstance(result_dict["timestamp"], str), "timestamp must be serialized as string"
        # Should be parseable as ISO format
        from datetime import datetime

        try:
            datetime.fromisoformat(result_dict["timestamp"])
        except ValueError:
            pytest.fail(f"timestamp not in ISO format: {result_dict['timestamp']}")
