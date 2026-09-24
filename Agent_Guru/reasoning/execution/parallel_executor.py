"""Parallel execution engine for independent steps in multi-step plans.

Performance Requirements:
- Time Complexity: O(n) for dependency analysis, O(1) per parallel batch
- Space Complexity: O(n) for dependency graph
- Latency: Parallel execution reduces total time by executing independent steps concurrently
- Throughput: Limited by available resources and step complexity

Design Decisions:
- Use asyncio.gather for concurrent execution
- Build dependency graph to identify independent steps
- Execute steps in batches (parallel within batch, sequential between batches)
- Handle partial failures gracefully
- Aggregate results from all executions

Author: Kiro AI
Date: 2026-02-21
Version: 1.0.0
"""

import asyncio
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from Agent_Guru.reasoning.execution.executor import ExecutionResult

@dataclass
class StepExecution:
    """Represents a step to be executed.

    Attributes:
        step_id: Unique step identifier
        tool_function: Function to execute
        parameters: Parameters for execution
        depends_on: List of step IDs this step depends on
        timeout: Execution timeout in seconds

    """

    step_id: str
    tool_function: Callable[[dict[str, Any]], Any]
    parameters: dict[str, Any]
    depends_on: list[str]
    timeout: float = 3.0

@dataclass
class ParallelExecutionResult:
    """Result of parallel execution.

    Attributes:
        success: Whether all steps succeeded
        step_results: Dictionary mapping step_id to ExecutionResult
        total_time: Total execution time (wall clock)
        parallel_batches: Number of parallel batches executed
        failed_steps: List of step IDs that failed

    """

    success: bool
    step_results: dict[str, ExecutionResult]
    total_time: float
    parallel_batches: int
    failed_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "step_results": {
                step_id: result.to_dict() for step_id, result in self.step_results.items()
            },
            "total_time": self.total_time,
            "parallel_batches": self.parallel_batches,
            "failed_steps": self.failed_steps,
        }

class ParallelExecutor:
    """Executor for parallel execution of independent steps.

    Time Complexity: O(n) for dependency analysis + O(b) for execution (b = number of batches)
    Space Complexity: O(n) for dependency graph

    Example:
        >>> executor = ParallelExecutor()
        >>> steps = [
        ...     StepExecution("step1", func1, {}, []),
        ...     StepExecution("step2", func2, {}, []),
        ...     StepExecution("step3", func3, {}, ["step1", "step2"]),
        ... ]
        >>> result = await executor.execute_parallel(steps)
        >>> print(f"Success: {result.success}, Batches: {result.parallel_batches}")

    """

    def __init__(self, max_concurrent: int = 10) -> None:
        """Initialize parallel executor.

        Args:
            max_concurrent: Maximum number of concurrent executions per batch

        """
        self.max_concurrent = max_concurrent

    async def execute_parallel(
        self,
        steps: list[StepExecution],
        fail_fast: bool = True,
    ) -> ParallelExecutionResult:
        """Execute steps in parallel where possible.

        Time Complexity: O(n) for dependency analysis + O(b) for execution
        Space Complexity: O(n)

        Args:
            steps: List of steps to execute
            fail_fast: If True, stop on first failure; if False, continue

        Returns:
            ParallelExecutionResult with execution results

        """
        import time

        start_time = time.perf_counter()

        # Build dependency graph and identify execution batches
        batches = self._build_execution_batches(steps)

        # Execute batches sequentially, steps within batch in parallel
        step_results: dict[str, ExecutionResult] = {}
        failed_steps: list[str] = []

        for _batch_idx, batch in enumerate(batches):
            # Execute all steps in this batch concurrently
            batch_results = await self._execute_batch(batch, fail_fast)

            # Store results
            for step_id, result in batch_results.items():
                step_results[step_id] = result
                if not result.success:
                    failed_steps.append(step_id)

            # Check if we should stop on failure
            if fail_fast and failed_steps:
                break

        total_time = time.perf_counter() - start_time

        return ParallelExecutionResult(
            success=len(failed_steps) == 0,
            step_results=step_results,
            total_time=total_time,
            parallel_batches=len(batches),
            failed_steps=failed_steps,
        )

    def _build_execution_batches(self, steps: list[StepExecution]) -> list[list[StepExecution]]:
        """Build execution batches based on dependencies.

        Steps in the same batch have no dependencies on each other.
        Batches are ordered such that all dependencies are satisfied.

        Time Complexity: O(n) using topological sort
        Space Complexity: O(n)

        Args:
            steps: List of steps to organize

        Returns:
            List of batches, where each batch is a list of independent steps

        """
        # Build dependency graph
        step_map = {step.step_id: step for step in steps}
        in_degree = {step.step_id: len(step.depends_on) for step in steps}
        dependents = defaultdict(list)

        for step in steps:
            for dep in step.depends_on:
                if dep in step_map:
                    dependents[dep].append(step.step_id)

        # Topological sort with level tracking (Kahn's algorithm)
        batches: list[list[StepExecution]] = []
        queue = deque([step.step_id for step in steps if in_degree[step.step_id] == 0])

        while queue:
            # All steps in queue can be executed in parallel (same batch)
            batch_size = len(queue)
            batch: list[StepExecution] = []

            for _ in range(batch_size):
                step_id = queue.popleft()
                batch.append(step_map[step_id])

                # Update dependents
                for dependent in dependents[step_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            batches.append(batch)

        return batches

    async def _execute_batch(
        self,
        batch: list[StepExecution],
        fail_fast: bool,
    ) -> dict[str, ExecutionResult]:
        """Execute a batch of independent steps concurrently.

        Time Complexity: O(1) for batch submission (actual execution is concurrent)
        Space Complexity: O(n) for results

        Args:
            batch: List of steps to execute concurrently
            fail_fast: Whether to cancel remaining on first failure

        Returns:
            Dictionary mapping step_id to ExecutionResult

        """
        # Create tasks for all steps in batch.
        #
        # BUG FIX: this list used to hold bare COROUTINE objects
        # (`self._execute_step_async(step)` without scheduling them). That is
        # fine for asyncio.gather(), which wraps them itself, but it broke the
        # fail_fast recovery path below in two separate ways:
        #   1. `task_obj.cancel()` -> AttributeError: 'coroutine' object has
        #      no attribute 'cancel'. So the very first step failure in
        #      fail_fast mode raised an AttributeError out of the executor
        #      instead of cancelling the siblings - the error the caller saw
        #      had nothing to do with the step that actually failed.
        #   2. `await task_obj` on a coroutine gather() had already consumed
        #      would raise "cannot reuse already awaited coroutine".
        # Scheduling them as real Tasks fixes both: Tasks are cancellable, and
        # awaiting an already-finished Task simply returns its stored result.
        tasks: list[asyncio.Task[ExecutionResult]] = []
        step_ids = []

        for step in batch:
            task = asyncio.ensure_future(self._execute_step_async(step))
            tasks.append(task)
            step_ids.append(step.step_id)

        # Execute all tasks concurrently
        if fail_fast:
            # Use return_exceptions=False to raise on first exception
            try:
                results_raw = await asyncio.gather(*tasks, return_exceptions=False)
                results = list(results_raw)
            except Exception:
                # Cancel remaining tasks
                for task_obj in tasks:
                    task_obj.cancel()
                # Collect results from completed tasks
                results = []
                for task_obj in tasks:
                    try:
                        results.append(await task_obj)
                    except asyncio.CancelledError:
                        results.append(
                            ExecutionResult(
                                success=False,
                                error={
                                    "error_code": "CANCELLED",
                                    "message": "Task cancelled due to failure in batch",
                                },
                            ),
                        )
                    except Exception as e:
                        results.append(
                            ExecutionResult(
                                success=False,
                                error={
                                    "error_code": type(e).__name__,
                                    "message": str(e),
                                },
                            ),
                        )
        else:
            # Use return_exceptions=True to collect all results
            results_raw = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to ExecutionResult
            results: list[ExecutionResult] = []
            for result in results_raw:
                if isinstance(result, Exception):
                    results.append(
                        ExecutionResult(
                            success=False,
                            error={
                                "error_code": type(result).__name__,
                                "message": str(result),
                            },
                        ),
                    )
                else:
                    results.append(result)

        # Map results to step IDs
        return dict(zip(step_ids, results, strict=False))

    async def _execute_step_async(self, step: StepExecution) -> ExecutionResult:
        """Execute a single step asynchronously.

        Args:
            step: Step to execute

        Returns:
            ExecutionResult

        """
        import time

        start_time = time.perf_counter()

        try:
            # Execute with timeout
            result_data = await asyncio.wait_for(
                asyncio.to_thread(step.tool_function, step.parameters),
                timeout=step.timeout,
            )

            execution_time = time.perf_counter() - start_time

            return ExecutionResult(
                success=True,
                result_data=result_data,
                execution_time=execution_time,
                action_id=step.step_id,
            )

        except TimeoutError:
            execution_time = time.perf_counter() - start_time
            return ExecutionResult(
                success=False,
                error={
                    "error_code": "TIMEOUT",
                    "message": f"Step exceeded timeout of {step.timeout}s",
                },
                execution_time=execution_time,
                action_id=step.step_id,
            )

    def detect_independent_steps(self, steps: list[StepExecution]) -> list[list[str]]:
        """Detect which steps can be executed in parallel.

        Args:
            steps: List of steps to analyze

        Returns:
            List of batches, where each batch contains step IDs that can run in parallel

        """
        batches = self._build_execution_batches(steps)
        return [[step.step_id for step in batch] for batch in batches]

class ParallelExecutionController:
    """Controller for managing parallel execution.

    Provides high-level interface for parallel execution of multi-step plans.

    Example:
        >>> controller = ParallelExecutionController()
        >>> steps = [...]
        >>> result = await controller.execute(steps)

    """

    def __init__(self, max_concurrent: int = 10) -> None:
        """Initialize parallel execution controller.

        Args:
            max_concurrent: Maximum concurrent executions per batch

        """
        self.executor = ParallelExecutor(max_concurrent=max_concurrent)

    async def execute(
        self,
        steps: list[StepExecution],
        fail_fast: bool = True,
    ) -> ParallelExecutionResult:
        """Execute steps with automatic parallelization.

        Args:
            steps: List of steps to execute
            fail_fast: Whether to stop on first failure

        Returns:
            ParallelExecutionResult

        """
        return await self.executor.execute_parallel(steps, fail_fast)

    def analyze_dependencies(self, steps: list[StepExecution]) -> dict[str, Any]:
        """Analyze step dependencies and parallelization opportunities.

        Args:
            steps: List of steps to analyze

        Returns:
            Dictionary with analysis results

        """
        batches = self.executor.detect_independent_steps(steps)

        return {
            "total_steps": len(steps),
            "parallel_batches": len(batches),
            "max_parallelism": max(len(batch) for batch in batches) if batches else 0,
            "batches": batches,
            "parallelization_ratio": len(batches) / len(steps) if steps else 0,
        }
