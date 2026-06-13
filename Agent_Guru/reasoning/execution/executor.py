"""Synchronous execution engine for Core Reasoning Engine.

Performance Requirements:
- Time Complexity: O(1) per action execution
- Space Complexity: O(1) (no unbounded growth)
- Latency: <3s default timeout (configurable)
- Retry: Max 3 retries for transient failures

Design Decisions:
- Use timeout enforcement with signal/threading
- Track execution latency per tool
- Implement exponential backoff for retries
- Capture structured results with error handling
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from Agent_Guru.reasoning.models.action import Action


@dataclass
class ExecutionResult:
    """Result of action execution.

    Attributes:
        success: Whether execution succeeded
        result_data: Result data if successful
        error: Error information if failed
        execution_time: Time taken to execute (seconds)
        action_id: ID of executed action
        retries: Number of retries attempted
        timed_out: Whether execution timed out
        timestamp: When execution completed

    """

    success: bool
    result_data: Any | None = None
    error: dict[str, Any] | None = None
    execution_time: float = 0.0
    action_id: str = ""
    retries: int = 0
    timed_out: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "result_data": self.result_data,
            "error": self.error,
            "execution_time": self.execution_time,
            "action_id": self.action_id,
            "retries": self.retries,
            "timed_out": self.timed_out,
            "timestamp": self.timestamp.isoformat(),
        }


class SyncExecutor:
    """Synchronous action executor with timeout and retry support.

    Time Complexity: O(1) per execution
    Space Complexity: O(1)

    Example:
        >>> executor = SyncExecutor(default_timeout=3.0, max_retries=3)
        >>> action = Action(action_id="1", tool_id="test", parameters={})
        >>> result = executor.execute(action, tool_function)
        >>> print(f"Success: {result.success}, Time: {result.execution_time}s")

    """

    def __init__(
        self,
        default_timeout: float = 3.0,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ) -> None:
        """Initialize synchronous executor.

        Args:
            default_timeout: Default timeout in seconds (default: 3.0)
            max_retries: Maximum retry attempts (default: 3)
            retry_delay: Initial retry delay in seconds (default: 0.5)

        Raises:
            ValueError: If parameters are invalid

        """
        if default_timeout <= 0:
            msg = f"Invalid default_timeout: {default_timeout}"
            raise ValueError(msg)
        if max_retries < 0:
            msg = f"Invalid max_retries: {max_retries}"
            raise ValueError(msg)
        if retry_delay < 0:
            msg = f"Invalid retry_delay: {retry_delay}"
            raise ValueError(msg)

        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Track execution latency per tool
        self._latency_stats: dict[str, list[float]] = {}

    def execute(
        self,
        action: Action,
        tool_function: Callable[[dict[str, Any]], Any],
        timeout: float | None = None,
        cancellation_token: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Execute action synchronously with timeout and retry.

        Time Complexity: O(1) per execution
        Space Complexity: O(1)

        Args:
            action: Action to execute
            tool_function: Function to execute (takes parameters dict)
            timeout: Timeout in seconds (uses default if None)
            cancellation_token: Optional dict with 'check_fn' callable for cancellation

        Returns:
            ExecutionResult with success/failure information

        Raises:
            Never raises - all errors captured in ExecutionResult

        """
        timeout = timeout or self.default_timeout
        start_time = time.perf_counter()
        retries = 0

        # Try execution with retries
        while retries <= self.max_retries:
            # Check cancellation before execution
            if cancellation_token:
                check_fn = cancellation_token.get("check_fn")
                if check_fn and check_fn():
                    execution_time = time.perf_counter() - start_time
                    return ExecutionResult(
                        success=False,
                        error={
                            "error_code": "CANCELLED",
                            "message": "Execution was cancelled",
                            "details": {},
                            "recoverable": False,
                        },
                        execution_time=execution_time,
                        action_id=action.action_id,
                        retries=retries,
                    )

            try:
                # Execute with timeout
                result_data = self._execute_with_timeout(
                    tool_function,
                    action.parameters,
                    timeout,
                    cancellation_token,
                )

                # Success - record latency and return
                execution_time = time.perf_counter() - start_time
                self._record_latency(action.tool_id, execution_time)

                return ExecutionResult(
                    success=True,
                    result_data=result_data,
                    execution_time=execution_time,
                    action_id=action.action_id,
                    retries=retries,
                )

            except TimeoutError as e:
                # Actual timeout - don't retry
                execution_time = time.perf_counter() - start_time
                return ExecutionResult(
                    success=False,
                    error={
                        "error_code": "TIMEOUT",
                        "message": f"Execution exceeded timeout of {timeout}s",
                        "details": {"timeout": timeout},
                        "recoverable": False,
                    },
                    execution_time=execution_time,
                    action_id=action.action_id,
                    retries=retries,
                    timed_out=True,
                )
                # Check if this is a cancellation error (from ErrorManager)
                if "cancelled" in str(e).lower():
                    execution_time = time.perf_counter() - start_time
                    return ExecutionResult(
                        success=False,
                        error={
                            "error_code": "CANCELLED",
                            "message": "Execution was cancelled",
                            "details": {},
                            "recoverable": False,
                        },
                        execution_time=execution_time,
                        action_id=action.action_id,
                        retries=retries,
                    )
                # Not a cancellation - treat as regular error
                # Check if error is transient and retryable
                if retries < self.max_retries and self._is_transient_error(e):
                    retries += 1
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** (retries - 1))
                    time.sleep(delay)
                    continue
                # Non-transient error or max retries reached
                execution_time = time.perf_counter() - start_time
                return ExecutionResult(
                    success=False,
                    error={
                        "error_code": type(e).__name__,
                        "message": str(e),
                        "details": {"exception_type": type(e).__name__},
                        "recoverable": self._is_transient_error(e),
                    },
                    execution_time=execution_time,
                    action_id=action.action_id,
                    retries=retries,
                )
                # Check if error is transient and retryable
                if retries < self.max_retries and self._is_transient_error(e):
                    retries += 1
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** (retries - 1))
                    time.sleep(delay)
                    continue
                # Non-transient error or max retries reached
                execution_time = time.perf_counter() - start_time
                return ExecutionResult(
                    success=False,
                    error={
                        "error_code": type(e).__name__,
                        "message": str(e),
                        "details": {"exception_type": type(e).__name__},
                        "recoverable": self._is_transient_error(e),
                    },
                    execution_time=execution_time,
                    action_id=action.action_id,
                    retries=retries,
                )
        # Should never reach here, but handle gracefully
        execution_time = time.perf_counter() - start_time
        return ExecutionResult(
            success=False,
            error={
                "error_code": "MAX_RETRIES",
                "message": f"Max retries ({self.max_retries}) exceeded",
                "details": {"retries": retries},
                "recoverable": False,
            },
            execution_time=execution_time,
            action_id=action.action_id,
            retries=retries,
        )

    def _execute_with_timeout(
        self,
        tool_function: Callable[[dict[str, Any]], Any],
        parameters: dict[str, Any],
        timeout: float,
        cancellation_token: dict[str, Any] | None = None,
    ) -> Any:
        """Execute function with timeout enforcement.

        Args:
            tool_function: Function to execute
            parameters: Parameters to pass
            timeout: Timeout in seconds
            cancellation_token: Optional dict with 'check_fn' callable for cancellation

        Returns:
            Function result

        Raises:
            TimeoutError: If execution exceeds timeout
            Exception: Any exception from tool_function

        """
        import concurrent.futures

        # Use ThreadPoolExecutor for timeout enforcement
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tool_function, parameters)

            try:
                # Wait for result with timeout, checking cancellation periodically
                if cancellation_token and "check_fn" in cancellation_token:
                    check_fn = cancellation_token["check_fn"]
                    # Poll for cancellation while waiting
                    elapsed = 0.0
                    poll_interval = 0.1  # Check every 100ms

                    while elapsed < timeout:
                        # Check if cancelled
                        if check_fn():
                            future.cancel()
                            # Raise cancellation error
                            msg = "Execution was cancelled"
                            raise ValueError(msg)

                        # Try to get result with short timeout
                        try:
                            return future.result(timeout=poll_interval)
                        except concurrent.futures.TimeoutError:
                            # Not done yet, continue polling
                            elapsed += poll_interval
                            continue
                    # Timeout exceeded
                    future.cancel()
                    msg = f"Execution exceeded timeout of {timeout}s"
                    raise TimeoutError(msg)
                # No cancellation token, just wait for result
                return future.result(timeout=timeout)

            except concurrent.futures.TimeoutError as e:
                # Cancel the future
                future.cancel()
                msg = f"Execution exceeded timeout of {timeout}s"
                raise TimeoutError(msg) from e

    def _is_transient_error(self, error: Exception) -> bool:
        """Check if error is transient and retryable.

        Args:
            error: Exception to check

        Returns:
            True if error is transient, False otherwise

        """
        # Common transient error types
        transient_types = (
            ConnectionError,
            TimeoutError,
            OSError,
        )

        # Check error type
        if isinstance(error, transient_types):
            return True

        # Check error message for transient indicators
        error_msg = str(error).lower()
        transient_indicators = [
            "timeout",
            "connection",
            "temporary",
            "unavailable",
            "retry",
        ]

        return any(indicator in error_msg for indicator in transient_indicators)

    def _record_latency(self, tool_id: str, latency: float) -> None:
        """Record execution latency for tool.

        Args:
            tool_id: Tool identifier
            latency: Execution time in seconds

        """
        if tool_id not in self._latency_stats:
            self._latency_stats[tool_id] = []

        # Keep last 100 measurements per tool — use deque for O(1) eviction
        stats = self._latency_stats[tool_id]
        stats.append(latency)
        if len(stats) > 100:
            del stats[0]  # O(n) but only triggers once per 100 samples

    def get_latency_stats(self, tool_id: str) -> dict[str, float]:
        """Get latency statistics for tool.

        Args:
            tool_id: Tool identifier

        Returns:
            Dictionary with min, max, avg, p95 latency

        """
        if tool_id not in self._latency_stats or not self._latency_stats[tool_id]:
            return {
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p95": 0.0,
                "count": 0,
            }

        stats = self._latency_stats[tool_id]
        sorted_stats = sorted(stats)
        count = len(stats)

        return {
            "min": sorted_stats[0],
            "max": sorted_stats[-1],
            "avg": sum(stats) / count,
            "p95": sorted_stats[int(count * 0.95)] if count > 0 else 0.0,
            "count": count,
        }

    def clear_latency_stats(self, tool_id: str | None = None) -> None:
        """Clear latency statistics.

        Args:
            tool_id: Tool to clear stats for (clears all if None)

        """
        if tool_id is None:
            self._latency_stats.clear()
        elif tool_id in self._latency_stats:
            del self._latency_stats[tool_id]


class ExecutionController:
    """Controller for managing action execution.

    Coordinates synchronous and asynchronous execution,
    tracks execution state, and provides unified interface.

    Example:
        >>> controller = ExecutionController()
        >>> action = Action(action_id="1", tool_id="test", parameters={})
        >>> # Sync execution
        >>> result = controller.execute_sync(action, tool_function)
        >>> # Async execution
        >>> async_result = controller.execute_async(action, "module", "function")

    """

    def __init__(
        self,
        default_timeout: float = 3.0,
        max_retries: int = 3,
        enable_async: bool = True,
    ) -> None:
        """Initialize execution controller.

        Args:
            default_timeout: Default timeout in seconds
            max_retries: Maximum retry attempts
            enable_async: Whether to enable async execution (requires Celery)

        """
        self.sync_executor = SyncExecutor(
            default_timeout=default_timeout,
            max_retries=max_retries,
        )

        # Initialize async executor if enabled
        self.async_executor = None
        if enable_async:
            try:
                from Agent_Guru.reasoning.execution.async_executor import AsyncExecutionController

                self.async_executor = AsyncExecutionController()
            except ImportError:
                # Celery not available, async execution disabled
                pass

    def execute_sync(
        self,
        action: Action,
        tool_function: Callable[[dict[str, Any]], Any],
        timeout: float | None = None,
    ) -> ExecutionResult:
        """Execute action synchronously.

        Args:
            action: Action to execute
            tool_function: Function to execute
            timeout: Timeout in seconds (uses default if None)

        Returns:
            ExecutionResult with success/failure information

        """
        return self.sync_executor.execute(action, tool_function, timeout)

    def execute_async(
        self,
        action: Action,
        tool_module: str,
        tool_function_name: str,
    ) -> Any:
        """Execute action asynchronously.

        Args:
            action: Action to execute
            tool_module: Module containing tool function
            tool_function_name: Name of tool function

        Returns:
            AsyncExecutionResult with task ID

        Raises:
            RuntimeError: If async execution not enabled

        """
        if self.async_executor is None:
            msg = "Async execution not enabled. Install Celery and Redis, or set enable_async=False"
            raise RuntimeError(
                msg,
            )

        return self.async_executor.execute_async(action, tool_module, tool_function_name)

    def get_async_status(self, task_id: str) -> Any:
        """Get status of async task.

        Args:
            task_id: Task identifier

        Returns:
            AsyncExecutionResult with current status

        Raises:
            RuntimeError: If async execution not enabled

        """
        if self.async_executor is None:
            msg = "Async execution not enabled"
            raise RuntimeError(msg)

        return self.async_executor.get_status(task_id)

    def cancel_async(self, task_id: str) -> bool:
        """Cancel async task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancellation requested

        Raises:
            RuntimeError: If async execution not enabled

        """
        if self.async_executor is None:
            msg = "Async execution not enabled"
            raise RuntimeError(msg)

        return self.async_executor.cancel(task_id)

    def get_latency_stats(self, tool_id: str) -> dict[str, float]:
        """Get latency statistics for tool.

        Args:
            tool_id: Tool identifier

        Returns:
            Dictionary with latency statistics

        """
        return self.sync_executor.get_latency_stats(tool_id)
