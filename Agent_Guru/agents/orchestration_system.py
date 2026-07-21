"""Orchestration System - Main API wiring all components together.

Validates: Requirements 6.1, 7.1, 8.1, 8.2, 8.3, 8.4, 15.1
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .delegation_manager import DelegationManager
from .loop_detector import LoopDetector
from .performance_tracker import PerformanceTracker
from .task_assigner import TaskAssigner
from .task_decomposer import Task, TaskDecomposer

if TYPE_CHECKING:
    from .agent_storage import AgentStorage

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_id: str
    success: bool
    output: Any
    agent_id: str | None
    sub_results: list["TaskResult"] = field(default_factory=list)
    error: str | None = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class OrchestrationSystem:
    """Main orchestration API — wires all components together.

    Receives tasks from the Goal Manager, decomposes them, assigns agents,
    executes in dependency order (with parallelism for independent sub-tasks),
    and aggregates results.

    Time Complexity: O(n) for task execution where n = sub-tasks
    Space Complexity: O(n) for result storage

    Example:
        >>> system = OrchestrationSystem(storage, decomposer, assigner, tracker)
        >>> result = await system.receive_task(task)
        >>> print(result.success)

    Validates: Requirements 6.1, 7.1, 8.1, 8.2, 8.3, 8.4, 15.1

    """

    def __init__(
        self,
        storage: "AgentStorage",
        decomposer: TaskDecomposer,
        assigner: TaskAssigner,
        tracker: PerformanceTracker,
        delegation_manager: DelegationManager | None = None,
        loop_detector: LoopDetector | None = None,
        executor: Any | None = None,
    ) -> None:
        self.storage = storage
        self.decomposer = decomposer
        self.assigner = assigner
        self.tracker = tracker
        self.delegation_manager = delegation_manager
        self.loop_detector = loop_detector
        # executor: callable(agent_id, task) -> (success, output)
        # If None, a stub that always succeeds is used
        self._executor = executor or self._default_executor

    async def receive_task(self, task: Task) -> TaskResult:
        """Receive a task from the Goal Manager and orchestrate execution.

        Flow:
        1. Decompose task if complex
        2. Assign each sub-task to an agent
        3. Execute in dependency order (parallel where possible)
        4. Aggregate results

        Validates: Requirements 6.1, 7.1, 8.1, 8.2, 8.3, 8.4, 15.1
        """
        sub_tasks = await self.decomposer.decompose(task)

        if len(sub_tasks) == 1 and sub_tasks[0].id == task.id:
            # Atomic task — execute directly
            return await self._execute_task(task)

        # Execute sub-tasks respecting dependencies
        results = await self._execute_with_dependencies(sub_tasks)
        return self._aggregate_results(task, results)

    async def _execute_with_dependencies(self, tasks: list[Task]) -> list[TaskResult]:
        """Execute tasks in dependency order, running independent tasks in parallel.

        Validates: Requirement 8.2 (dependency order), 8.3 (parallel execution)
        """
        completed: dict[str, TaskResult] = {}

        # Topological execution using dependency tracking
        remaining = list(tasks)
        while remaining:
            # Find tasks whose dependencies are all satisfied
            ready = [t for t in remaining if all(dep in completed for dep in t.dependencies)]

            if not ready:
                # Circular dependency or unresolvable — execute remaining sequentially
                logger.warning("Could not resolve dependencies, executing remaining sequentially")
                for t in remaining:
                    result = await self._execute_task(t)
                    completed[t.id] = result
                break

            # Execute ready tasks in parallel.
            # return_exceptions=True ensures one failure doesn't cancel siblings
            # and prevents resource-leaking zombie tasks.
            parallel_results = await asyncio.gather(
                *[self._execute_task(t) for t in ready],
                return_exceptions=True,
            )

            for task, result in zip(ready, parallel_results, strict=False):  # type: ignore[assignment]
                if isinstance(result, BaseException):
                    logger.error(
                        "Task %s failed with %s: %s",
                        task.id,
                        type(result).__name__,
                        result,
                    )
                    completed[task.id] = TaskResult(
                        task_id=task.id,
                        agent_id="error",
                        success=False,
                        output=None,
                        error=str(result),
                    )
                else:
                    completed[task.id] = result
                remaining.remove(task)

        return list(completed.values())

    async def _execute_task(self, task: Task) -> TaskResult:
        """Execute a single task by assigning it to an agent."""
        agent_id = await self.assigner.assign_task(task)

        if not agent_id:
            return TaskResult(
                task_id=task.id,
                success=False,
                output=None,
                agent_id=None,
                error="No agent available",
            )

        t0 = time.perf_counter()
        try:
            success, output = await self._executor(agent_id, task)
        except Exception:
            logger.exception("Task %s execution failed", task.id)
            success, output = False, None
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Record performance
        await self.tracker.record_performance(
            agent_id=agent_id,
            task_id=task.id,
            task_type=task.task_type,
            success=success,
            completion_time_ms=elapsed_ms,
            resource_usage={},
        )

        await self.assigner.task_completed(agent_id)

        return TaskResult(
            task_id=task.id,
            success=success,
            output=output,
            agent_id=agent_id,
        )

    def _aggregate_results(self, parent_task: Task, sub_results: list[TaskResult]) -> TaskResult:
        """Aggregate sub-task results into a parent result.

        Validates: Requirement 8.4
        """
        all_success = all(r.success for r in sub_results)
        outputs = [r.output for r in sub_results if r.output is not None]

        return TaskResult(
            task_id=parent_task.id,
            success=all_success,
            output=outputs if outputs else None,
            agent_id=None,
            sub_results=sub_results,
        )

    @staticmethod
    async def _default_executor(agent_id: str, task: Task):
        """Default stub executor — always succeeds with no output."""
        return True, None
