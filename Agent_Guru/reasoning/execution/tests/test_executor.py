"""Tests for synchronous execution engine."""

import time

import pytest

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
