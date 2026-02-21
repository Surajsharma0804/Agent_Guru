"""
Tests for asynchronous execution engine with Celery.

Coverage Target: 80%+
"""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from Agent_Guru.reasoning.execution.async_executor import (
    AsyncExecutionController,
    AsyncExecutionResult,
    AsyncExecutor,
    TaskStatus,
    execute_action_task,
)
from Agent_Guru.reasoning.models.action import Action


class TestAsyncExecutionResult:
    """Tests for AsyncExecutionResult data model."""

    def test_initialization(self):
        """Test AsyncExecutionResult initialization."""
        result = AsyncExecutionResult(
            task_id="task_123",
            status=TaskStatus.PENDING,
            action_id="action_1",
        )

        assert result.task_id == "task_123"
        assert result.status == TaskStatus.PENDING
        assert result.progress == 0.0
        assert result.result_data is None
        assert result.error is None
        assert result.action_id == "action_1"
        assert result.cancellable is True

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = AsyncExecutionResult(
            task_id="task_123",
            status=TaskStatus.SUCCESS,
            progress=100.0,
            result_data={"output": "test"},
            action_id="action_1",
        )

        result_dict = result.to_dict()

        assert result_dict["task_id"] == "task_123"
        assert result_dict["status"] == "success"
        assert result_dict["progress"] == 100.0
        assert result_dict["result_data"] == {"output": "test"}
        assert result_dict["action_id"] == "action_1"


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILURE.value == "failure"
        assert TaskStatus.CANCELLED.value == "cancelled"


@pytest.mark.skipif(
    True,  # Skip by default - requires Redis and Celery worker
    reason="Requires Redis and Celery worker running",
)
class TestExecuteActionTask:
    """Tests for Celery task execution."""

    def test_execute_action_task_success(self):
        """Test successful task execution."""
        # Mock tool function
        def mock_tool(params):
            return {"result": "success"}

        action_dict = {
            "action_id": "action_1",
            "tool_id": "test_tool",
            "parameters": {"param1": "value1"},
        }

        # Execute task
        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            mock_module.mock_tool = mock_tool
            mock_import.return_value = mock_module

            result = execute_action_task(action_dict, "test_module", "mock_tool")

        assert result["success"] is True
        assert result["result_data"] == {"result": "success"}
        assert result["action_id"] == "action_1"
        assert result["execution_time"] > 0

    def test_execute_action_task_failure(self):
        """Test task execution with error."""

        def mock_tool(params):
            raise ValueError("Test error")

        action_dict = {
            "action_id": "action_1",
            "tool_id": "test_tool",
            "parameters": {},
        }

        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            mock_module.mock_tool = mock_tool
            mock_import.return_value = mock_module

            result = execute_action_task(action_dict, "test_module", "mock_tool")

        assert result["success"] is False
        assert result["error"]["error_code"] == "ValueError"
        assert "Test error" in result["error"]["message"]


class TestAsyncExecutor:
    """Tests for AsyncExecutor."""

    @patch("Agent_Guru.reasoning.execution.async_executor.execute_action_task")
    def test_execute_async(self, mock_task):
        """Test async execution submission."""
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = "task_123"
        mock_task.apply_async.return_value = mock_result

        executor = AsyncExecutor()
        action = Action(
            action_id="action_1",
            tool_id="test_tool",
            parameters={"param1": "value1"},
        )

        result = executor.execute_async(action, "test_module", "test_function")

        assert result.task_id == "task_123"
        assert result.status == TaskStatus.PENDING
        assert result.action_id == "action_1"
        assert result.started_at is not None

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_get_task_status_pending(self, mock_async_result):
        """Test getting status of pending task."""
        mock_result = Mock()
        mock_result.state = "PENDING"
        mock_result.info = None
        mock_async_result.return_value = mock_result

        executor = AsyncExecutor()
        status = executor.get_task_status("task_123")

        assert status.task_id == "task_123"
        assert status.status == TaskStatus.PENDING
        assert status.progress == 0.0

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_get_task_status_running(self, mock_async_result):
        """Test getting status of running task."""
        mock_result = Mock()
        mock_result.state = "PROGRESS"
        mock_result.info = {"progress": 50.0, "message": "Processing"}
        mock_async_result.return_value = mock_result

        executor = AsyncExecutor()
        status = executor.get_task_status("task_123")

        assert status.status == TaskStatus.RUNNING
        assert status.progress == 50.0

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_get_task_status_success(self, mock_async_result):
        """Test getting status of successful task."""
        mock_result = Mock()
        mock_result.state = "SUCCESS"
        mock_result.result = {
            "success": True,
            "result_data": {"output": "test"},
            "execution_time": 1.5,
            "action_id": "action_1",
        }
        mock_async_result.return_value = mock_result

        executor = AsyncExecutor()
        status = executor.get_task_status("task_123")

        assert status.status == TaskStatus.SUCCESS
        assert status.progress == 100.0
        assert status.result_data == {"output": "test"}
        assert status.execution_time == 1.5
        assert status.completed_at is not None

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_get_task_status_failure(self, mock_async_result):
        """Test getting status of failed task."""
        mock_result = Mock()
        mock_result.state = "FAILURE"
        mock_result.info = Exception("Test error")
        mock_async_result.return_value = mock_result

        executor = AsyncExecutor()
        status = executor.get_task_status("task_123")

        assert status.status == TaskStatus.FAILURE
        assert status.error is not None
        assert "Test error" in status.error["message"]

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_cancel_task(self, mock_async_result):
        """Test task cancellation."""
        mock_result = Mock()
        mock_async_result.return_value = mock_result

        executor = AsyncExecutor()
        success = executor.cancel_task("task_123")

        assert success is True
        mock_result.revoke.assert_called_once_with(terminate=True)

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_wait_for_task_success(self, mock_async_result):
        """Test waiting for task to complete successfully."""
        # Mock task that completes after 2 polls
        mock_result = Mock()
        mock_result.state = "SUCCESS"
        mock_result.result = {
            "success": True,
            "result_data": {"output": "test"},
            "execution_time": 1.0,
            "action_id": "action_1",
        }
        mock_async_result.return_value = mock_result

        executor = AsyncExecutor()
        result = executor.wait_for_task("task_123", timeout=5.0, poll_interval=0.1)

        assert result.status == TaskStatus.SUCCESS
        assert result.result_data == {"output": "test"}

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_wait_for_task_timeout(self, mock_async_result):
        """Test waiting for task with timeout."""
        # Mock task that never completes
        mock_result = Mock()
        mock_result.state = "PENDING"
        mock_async_result.return_value = mock_result

        executor = AsyncExecutor()

        with pytest.raises(TimeoutError) as exc_info:
            executor.wait_for_task("task_123", timeout=0.2, poll_interval=0.1)

        assert "did not complete" in str(exc_info.value)


class TestAsyncExecutionController:
    """Tests for AsyncExecutionController."""

    @patch("Agent_Guru.reasoning.execution.async_executor.execute_action_task")
    def test_execute_async(self, mock_task):
        """Test async execution through controller."""
        mock_result = Mock()
        mock_result.id = "task_123"
        mock_task.apply_async.return_value = mock_result

        controller = AsyncExecutionController()
        action = Action(
            action_id="action_1",
            tool_id="test_tool",
            parameters={"param1": "value1"},
        )

        result = controller.execute_async(action, "test_module", "test_function")

        assert result.task_id == "task_123"
        assert result.status == TaskStatus.PENDING

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_get_status(self, mock_async_result):
        """Test getting task status through controller."""
        mock_result = Mock()
        mock_result.state = "SUCCESS"
        mock_result.result = {
            "success": True,
            "result_data": {"output": "test"},
            "execution_time": 1.0,
            "action_id": "action_1",
        }
        mock_async_result.return_value = mock_result

        controller = AsyncExecutionController()
        status = controller.get_status("task_123")

        assert status.status == TaskStatus.SUCCESS
        assert status.result_data == {"output": "test"}

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_cancel(self, mock_async_result):
        """Test cancelling task through controller."""
        mock_result = Mock()
        mock_async_result.return_value = mock_result

        controller = AsyncExecutionController()
        success = controller.cancel("task_123")

        assert success is True
        mock_result.revoke.assert_called_once()

    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_wait(self, mock_async_result):
        """Test waiting for task through controller."""
        mock_result = Mock()
        mock_result.state = "SUCCESS"
        mock_result.result = {
            "success": True,
            "result_data": {"output": "test"},
            "execution_time": 1.0,
            "action_id": "action_1",
        }
        mock_async_result.return_value = mock_result

        controller = AsyncExecutionController()
        result = controller.wait("task_123", timeout=5.0)

        assert result.status == TaskStatus.SUCCESS


class TestIntegration:
    """Integration tests for async execution."""

    @patch("Agent_Guru.reasoning.execution.async_executor.execute_action_task")
    @patch("Agent_Guru.reasoning.execution.async_executor.AsyncResult")
    def test_full_async_workflow(self, mock_async_result, mock_task):
        """Test complete async execution workflow."""
        # Mock task submission
        mock_task_result = Mock()
        mock_task_result.id = "task_123"
        mock_task.apply_async.return_value = mock_task_result

        # Mock status checks with progression
        call_count = [0]

        def create_mock_result():
            mock_result = Mock()
            states = ["PENDING", "STARTED", "PROGRESS", "SUCCESS"]
            idx = min(call_count[0], len(states) - 1)
            call_count[0] += 1

            mock_result.state = states[idx]
            if states[idx] == "PROGRESS":
                mock_result.info = {"progress": 50.0}
            elif states[idx] == "SUCCESS":
                mock_result.result = {
                    "success": True,
                    "result_data": {"output": "test"},
                    "execution_time": 2.0,
                    "action_id": "action_1",
                }
            else:
                mock_result.info = None
                mock_result.result = None

            return mock_result

        mock_async_result.side_effect = lambda *args, **kwargs: create_mock_result()

        # Execute workflow
        controller = AsyncExecutionController()
        action = Action(
            action_id="action_1",
            tool_id="test_tool",
            parameters={"param1": "value1"},
        )

        # Submit task
        result = controller.execute_async(action, "test_module", "test_function")
        assert result.status == TaskStatus.PENDING

        # Check status multiple times to simulate progression
        for _ in range(3):
            status = controller.get_status(result.task_id)
            time.sleep(0.1)

        # Final status should be success
        final_status = controller.get_status(result.task_id)
        assert final_status.status == TaskStatus.SUCCESS
