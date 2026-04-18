"""
Async execution engine with timeout and cancellation support.

Performance Requirements:
- Time Complexity: O(1) per action execution
- Space Complexity: O(1) (no unbounded growth)
- Latency: Configurable per-action timeout
- Cancellation: Graceful cancellation with cleanup

Design Decisions:
- Use asyncio.wait_for for timeout enforcement
- Support cancellation with asyncio.CancelledError
- Return partial results on timeout
- Track in-flight operations for graceful shutdown

Author: Kiro AI
Date: 2026-02-21
Version: 1.0.0
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from Agent_Guru.reasoning.models.action import Action


@dataclass
class AsyncExecutionResult:
    """Result of asynchronous action execution.

    Attributes:
        success: Whether execution succeeded
        result_data: Result data if successful
        error: Error information if failed
        execution_time: Time taken to execute (seconds)
        action_id: ID of executed action
        task_id: Unique task identifier
        cancelled: Whether execution was cancelled
        timed_out: Whether execution timed out
        partial_result: Partial result if available on timeout
        timestamp: When execution completed
    """

    success: bool
    result_data: Any | None = None
    error: dict[str, Any] | None = None
    execution_time: float = 0.0
    action_id: str = ""
    task_id: str = field(default_factory=lambda: str(uuid4()))
    cancelled: bool = False
    timed_out: bool = False
    partial_result: Any | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "result_data": self.result_data,
            "error": self.error,
            "execution_time": self.execution_time,
            "action_id": self.action_id,
            "task_id": self.task_id,
            "cancelled": self.cancelled,
            "timed_out": self.timed_out,
            "partial_result": self.partial_result,
            "timestamp": self.timestamp.isoformat(),
        }


class AsyncTimeoutExecutor:
    """Async action executor with timeout and cancellation support.

    Time Complexity: O(1) per execution
    Space Complexity: O(n) where n is number of in-flight tasks

    Example:
        >>> executor = AsyncTimeoutExecutor(default_timeout=5.0)
        >>> action = Action(action_id="1", tool_id="test", parameters={})
        >>> result = await executor.execute_async(action, async_tool_function)
        >>> print(f"Success: {result.success}, Time: {result.execution_time}s")
        >>> # Cancel in-flight task
        >>> await executor.cancel_task(result.task_id)
    """

    def __init__(
        self,
        default_timeout: float = 5.0,
        enable_partial_results: bool = True,
    ) -> None:
        """Initialize async timeout executor.

        Args:
            default_timeout: Default timeout in seconds (default: 5.0)
            enable_partial_results: Whether to return partial results on timeout

        Raises:
            ValueError: If parameters are invalid
        """
        if default_timeout <= 0:
            raise ValueError(f"Invalid default_timeout: {default_timeout}")

        self.default_timeout = default_timeout
        self.enable_partial_results = enable_partial_results

        # Track in-flight tasks for cancellation
        self._in_flight_tasks: dict[str, asyncio.Task] = {}

        # Track partial results for timeout handling
        self._partial_results: dict[str, Any] = {}

    async def execute_async(
        self,
        action: Action,
        tool_function: Callable[[dict[str, Any]], Awaitable[Any]],
        timeout: float | None = None,
    ) -> AsyncExecutionResult:
        """Execute action asynchronously with timeout and cancellation support.

        Time Complexity: O(1) per execution
        Space Complexity: O(1)

        Args:
            action: Action to execute
            tool_function: Async function to execute (takes parameters dict)
            timeout: Timeout in seconds (uses default if None)

        Returns:
            AsyncExecutionResult with success/failure information

        Raises:
            Never raises - all errors captured in AsyncExecutionResult
        """
        timeout = timeout or self.default_timeout
        task_id = str(uuid4())
        start_time = time.perf_counter()

        try:
            # Create task for execution
            task = asyncio.create_task(
                self._execute_with_partial_tracking(tool_function, action.parameters, task_id)
            )

            # Track task for cancellation
            self._in_flight_tasks[task_id] = task

            try:
                # Execute with timeout
                result_data = await asyncio.wait_for(task, timeout=timeout)

                # Success
                execution_time = time.perf_counter() - start_time
                return AsyncExecutionResult(
                    success=True,
                    result_data=result_data,
                    execution_time=execution_time,
                    action_id=action.action_id,
                    task_id=task_id,
                )

            except asyncio.TimeoutError:
                # Timeout - cancel task and return partial result
                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass

                execution_time = time.perf_counter() - start_time
                partial_result = self._partial_results.pop(task_id, None)

                return AsyncExecutionResult(
                    success=False,
                    error={
                        "error_code": "TIMEOUT",
                        "message": f"Execution exceeded timeout of {timeout}s",
                        "details": {"timeout": timeout},
                        "recoverable": False,
                    },
                    execution_time=execution_time,
                    action_id=action.action_id,
                    task_id=task_id,
                    timed_out=True,
                    partial_result=partial_result if self.enable_partial_results else None,
                )

            except asyncio.CancelledError:
                # Cancelled by user
                execution_time = time.perf_counter() - start_time
                partial_result = self._partial_results.pop(task_id, None)

                return AsyncExecutionResult(
                    success=False,
                    error={
                        "error_code": "CANCELLED",
                        "message": "Execution was cancelled",
                        "details": {},
                        "recoverable": False,
                    },
                    execution_time=execution_time,
                    action_id=action.action_id,
                    task_id=task_id,
                    cancelled=True,
                    partial_result=partial_result if self.enable_partial_results else None,
                )

        except Exception as e:
            # Unexpected error
            execution_time = time.perf_counter() - start_time
            return AsyncExecutionResult(
                success=False,
                error={
                    "error_code": type(e).__name__,
                    "message": str(e),
                    "details": {"exception_type": type(e).__name__},
                    "recoverable": False,
                },
                execution_time=execution_time,
                action_id=action.action_id,
                task_id=task_id,
            )

        finally:
            # Cleanup
            self._in_flight_tasks.pop(task_id, None)
            self._partial_results.pop(task_id, None)

    async def _execute_with_partial_tracking(
        self,
        tool_function: Callable[[dict[str, Any]], Awaitable[Any]],
        parameters: dict[str, Any],
        task_id: str,
    ) -> Any:
        """Execute function with partial result tracking.

        Args:
            tool_function: Async function to execute
            parameters: Parameters to pass
            task_id: Task identifier for tracking

        Returns:
            Function result

        Raises:
            Exception: Any exception from tool_function
        """
        # Execute tool function
        result = await tool_function(parameters)
        return result

    def store_partial_result(self, task_id: str, partial_result: Any) -> None:
        """Store partial result for task (called by tool functions).

        Args:
            task_id: Task identifier
            partial_result: Partial result to store
        """
        self._partial_results[task_id] = partial_result

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel in-flight task.

        Args:
            task_id: Task identifier

        Returns:
            True if task was cancelled, False if not found
        """
        task = self._in_flight_tasks.get(task_id)
        if task is None:
            return False

        # Cancel task
        task.cancel()

        # Wait for cancellation to complete
        try:
            await task
        except asyncio.CancelledError:
            pass

        return True

    async def cancel_all_tasks(self) -> int:
        """Cancel all in-flight tasks.

        Returns:
            Number of tasks cancelled
        """
        task_ids = list(self._in_flight_tasks.keys())

        for task_id in task_ids:
            await self.cancel_task(task_id)

        return len(task_ids)

    def get_in_flight_tasks(self) -> list[str]:
        """Get list of in-flight task IDs.

        Returns:
            List of task IDs
        """
        return list(self._in_flight_tasks.keys())

    async def execute_with_retry(
        self,
        action: Action,
        tool_function: Callable[[dict[str, Any]], Awaitable[Any]],
        timeout: float | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ) -> AsyncExecutionResult:
        """Execute action with retry logic.

        Args:
            action: Action to execute
            tool_function: Async function to execute
            timeout: Timeout in seconds
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay in seconds

        Returns:
            AsyncExecutionResult with success/failure information
        """
        retries = 0

        while retries <= max_retries:
            result = await self.execute_async(action, tool_function, timeout)

            # Success or non-recoverable error
            if result.success or (result.error and not result.error.get("recoverable", False)):
                return result

            # Retry on recoverable error
            if retries < max_retries:
                retries += 1
                delay = retry_delay * (2 ** (retries - 1))
                await asyncio.sleep(delay)
                continue

            # Max retries reached
            return result

        # Should never reach here
        return result


class AsyncExecutionController:
    """Controller for managing async action execution with timeout and cancellation.

    Provides unified interface for async execution with timeout enforcement,
    graceful cancellation, and partial result handling.

    Example:
        >>> controller = AsyncExecutionController()
        >>> action = Action(action_id="1", tool_id="test", parameters={})
        >>> result = await controller.execute_async(action, async_tool_function)
        >>> # Cancel if needed
        >>> await controller.cancel_task(result.task_id)
    """

    def __init__(
        self,
        default_timeout: float = 5.0,
        enable_partial_results: bool = True,
    ) -> None:
        """Initialize async execution controller.

        Args:
            default_timeout: Default timeout in seconds
            enable_partial_results: Whether to return partial results on timeout
        """
        self.executor = AsyncTimeoutExecutor(
            default_timeout=default_timeout,
            enable_partial_results=enable_partial_results,
        )

    async def execute_async(
        self,
        action: Action,
        tool_function: Callable[[dict[str, Any]], Awaitable[Any]],
        timeout: float | None = None,
    ) -> AsyncExecutionResult:
        """Execute action asynchronously.

        Args:
            action: Action to execute
            tool_function: Async function to execute
            timeout: Timeout in seconds (uses default if None)

        Returns:
            AsyncExecutionResult with success/failure information
        """
        return await self.executor.execute_async(action, tool_function, timeout)

    async def execute_with_retry(
        self,
        action: Action,
        tool_function: Callable[[dict[str, Any]], Awaitable[Any]],
        timeout: float | None = None,
        max_retries: int = 3,
    ) -> AsyncExecutionResult:
        """Execute action with retry logic.

        Args:
            action: Action to execute
            tool_function: Async function to execute
            timeout: Timeout in seconds
            max_retries: Maximum retry attempts

        Returns:
            AsyncExecutionResult with success/failure information
        """
        return await self.executor.execute_with_retry(action, tool_function, timeout, max_retries)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel in-flight task.

        Args:
            task_id: Task identifier

        Returns:
            True if task was cancelled, False if not found
        """
        return await self.executor.cancel_task(task_id)

    async def cancel_all_tasks(self) -> int:
        """Cancel all in-flight tasks.

        Returns:
            Number of tasks cancelled
        """
        return await self.executor.cancel_all_tasks()

    def get_in_flight_tasks(self) -> list[str]:
        """Get list of in-flight task IDs.

        Returns:
            List of task IDs
        """
        return self.executor.get_in_flight_tasks()

    def store_partial_result(self, task_id: str, partial_result: Any) -> None:
        """Store partial result for task.

        Args:
            task_id: Task identifier
            partial_result: Partial result to store
        """
        self.executor.store_partial_result(task_id, partial_result)
