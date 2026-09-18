"""Task Executor - Executes tasks in dependency order with monitoring.

Handles sequential and parallel task execution, dependency resolution,
timeout enforcement, and execution status tracking.

Performance Characteristics:
    - Time Complexity: O(n) for dependency sort, O(1) per status update
    - Space Complexity: O(n) for active task tracking
    - Latency: <100ms overhead per task

Validates: Requirements 2, 7 (Task Execution and Coordination)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from .task_decomposer import Task

class ExecutionStatus(Enum):
    """Status of a task during execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class ExecutionResult:
    """Result of a single task execution.

    Attributes:
        task_id: ID of the executed task.
        status: Final execution status.
        output: Task output data, if any.
        error: Error message on failure.
        started_at: When execution began.
        finished_at: When execution ended.
        duration_ms: Total execution time in milliseconds.

    """

    def __init__(
        self,
        task_id: str,
        status: ExecutionStatus,
        output: Any | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        self.task_id = task_id
        self.status = status
        self.output = output
        self.error = error
        self.started_at = started_at or datetime.now(tz=UTC)
        self.finished_at = finished_at or datetime.now(tz=UTC)
        delta = self.finished_at - self.started_at
        self.duration_ms = int(delta.total_seconds() * 1000)

# Type alias for a task handler coroutine
TaskHandler = Callable[[Task], Coroutine[Any, Any, Any]]

class TaskExecutor:
    """Executes tasks in dependency order with timeout and monitoring.

    Supports:
    - Sequential execution respecting dependency order
    - Parallel execution for independent tasks
    - Per-task timeout enforcement
    - Execution status tracking

    Time Complexity: O(n) for topological sort, O(1) per status lookup
    Space Complexity: O(n) for status and result storage

    Example:
        >>> async def my_handler(task: Task) -> str:
        ...     return f"done: {task.description}"
        >>> executor = TaskExecutor(handler=my_handler, default_timeout_seconds=30)
        >>> results = await executor.execute(tasks)

    Validates: Requirements 2, 7

    """

    def __init__(
        self,
        handler: TaskHandler,
        default_timeout_seconds: int = 30,
        max_parallel: int = 10,
    ) -> None:
        """Initialise the executor.

        Args:
            handler: Async callable that executes a single Task.
            default_timeout_seconds: Timeout applied to each task.
            max_parallel: Maximum tasks to run in parallel.

        Raises:
            ValueError: If default_timeout_seconds < 1 or max_parallel < 1.

        """
        if default_timeout_seconds < 1:
            msg = "default_timeout_seconds must be >= 1"
            raise ValueError(msg)
        if max_parallel < 1:
            msg = "max_parallel must be >= 1"
            raise ValueError(msg)

        self.handler = handler
        self.default_timeout = default_timeout_seconds
        self.max_parallel = max_parallel

        self._statuses: dict[str, ExecutionStatus] = {}
        self._results: dict[str, ExecutionResult] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(self, tasks: list[Task]) -> list[ExecutionResult]:
        """Execute a list of tasks respecting their dependency order.

        Tasks with no unmet dependencies are run in parallel (up to
        max_parallel). Tasks with dependencies wait until all their
        dependencies complete successfully.

        Args:
            tasks: Tasks to execute (may be in any order).

        Returns:
            List of ExecutionResult in the same order as input tasks.

        Time Complexity: O(n) for sort + O(n) for execution
        Validates: Requirements 2.6, 7.1, 7.5

        """
        if not tasks:
            return []

        # Initialise all statuses to PENDING
        for task in tasks:
            self._statuses[task.id] = ExecutionStatus.PENDING

        # Build id → task map for dependency lookup (used for future extension)
        _task_map = {t.id: t for t in tasks}

        # Execute in waves: each wave contains tasks whose deps are done
        completed_ids: set[str] = set()
        # BUG FIX: track failed task IDs too, so a stalled wave can tell
        # "blocked by a dependency that genuinely failed" apart from a
        # real cycle or dangling dependency ID (see below).
        failed_ids: set[str] = set()
        remaining = list(tasks)

        while remaining:
            # Find tasks whose dependencies are all completed
            ready = [t for t in remaining if all(dep in completed_ids for dep in t.dependencies)]

            if not ready:
                # BUG FIX: previously every remaining task got the same
                # generic "cycle detected" message, even when the real
                # cause was that a dependency genuinely ran and failed --
                # a completely different, far more common situation than
                # an actual cycle. Report the specific failed dependency
                # IDs when that's the real cause; fall back to the
                # cycle/unresolvable message only when nothing explains
                # the stall that way (a true cycle or a dangling/missing
                # dependency ID).
                for t in remaining:
                    blocking_failed = sorted(dep for dep in t.dependencies if dep in failed_ids)
                    self._statuses[t.id] = ExecutionStatus.FAILED
                    if blocking_failed:
                        error = (
                            "Blocked by failed dependency/dependencies: "
                            + ", ".join(blocking_failed)
                        )
                    else:
                        error = "Unresolvable dependency or cycle detected"
                    self._results[t.id] = ExecutionResult(
                        task_id=t.id,
                        status=ExecutionStatus.FAILED,
                        error=error,
                    )
                    failed_ids.add(t.id)
                break

            # Run ready tasks in parallel batches
            semaphore = asyncio.Semaphore(self.max_parallel)
            batch_results = await asyncio.gather(
                *[self._run_with_semaphore(t, semaphore) for t in ready],
                return_exceptions=False,
            )

            for result in batch_results:
                self._results[result.task_id] = result
                self._statuses[result.task_id] = result.status
                if result.status == ExecutionStatus.COMPLETED:
                    completed_ids.add(result.task_id)
                else:
                    failed_ids.add(result.task_id)

            # Remove executed tasks from remaining
            executed_ids = {t.id for t in ready}
            remaining = [t for t in remaining if t.id not in executed_ids]

        return [self._results[t.id] for t in tasks]

    def get_status(self, task_id: str) -> ExecutionStatus | None:
        """Return current execution status for a task.

        Args:
            task_id: Task identifier.

        Returns:
            ExecutionStatus or None if task is unknown.

        Time Complexity: O(1)

        """
        return self._statuses.get(task_id)

    def get_result(self, task_id: str) -> ExecutionResult | None:
        """Return execution result for a completed task.

        Args:
            task_id: Task identifier.

        Returns:
            ExecutionResult or None if not yet completed.

        Time Complexity: O(1)

        """
        return self._results.get(task_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_with_semaphore(
        self,
        task: Task,
        semaphore: asyncio.Semaphore,
    ) -> ExecutionResult:
        """Run a single task under a semaphore for concurrency control.

        Args:
            task: Task to execute.
            semaphore: Concurrency limiter.

        Returns:
            ExecutionResult for the task.

        """
        async with semaphore:
            return await self._run_task(task)

    async def _run_task(self, task: Task) -> ExecutionResult:
        """Execute a single task with timeout enforcement.

        Args:
            task: Task to execute.

        Returns:
            ExecutionResult with status COMPLETED, FAILED, or TIMEOUT.

        Time Complexity: O(1) overhead
        Validates: Requirements 7.2, 7.4, 7.5

        """
        started_at = datetime.now(tz=UTC)
        self._statuses[task.id] = ExecutionStatus.IN_PROGRESS
        timeout = task.requirements.get("timeout_seconds", self.default_timeout)

        try:
            output = await asyncio.wait_for(
                self.handler(task),
                timeout=float(timeout),
            )
            finished_at = datetime.now(tz=UTC)
            return ExecutionResult(
                task_id=task.id,
                status=ExecutionStatus.COMPLETED,
                output=output,
                started_at=started_at,
                finished_at=finished_at,
            )
        except TimeoutError:
            finished_at = datetime.now(tz=UTC)
            return ExecutionResult(
                task_id=task.id,
                status=ExecutionStatus.TIMEOUT,
                error=f"Task timed out after {timeout}s",
                started_at=started_at,
                finished_at=finished_at,
            )
        except asyncio.CancelledError:
            # BUG FIX: never swallow cancellation -- it must propagate so
            # the caller's own cancellation (e.g. a shutdown or a halt())
            # actually takes effect instead of being reported as a task
            # failure.
            raise
        except Exception as exc:
            # BUG FIX: previously ANY non-timeout exception from the task
            # handler (the ordinary case -- a handler doing real work and
            # failing for a real reason) propagated straight out of this
            # method, which crashed the surrounding
            # asyncio.gather(..., return_exceptions=False) call in
            # execute() and silently abandoned every OTHER still-running
            # task in that wave with no recorded result. Catching it here
            # and returning a normal FAILED ExecutionResult restores the
            # class's own documented contract (COMPLETED, FAILED, or
            # TIMEOUT) and lets the rest of the wave finish normally.
            finished_at = datetime.now(tz=UTC)
            return ExecutionResult(
                task_id=task.id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
                started_at=started_at,
                finished_at=finished_at,
            )
