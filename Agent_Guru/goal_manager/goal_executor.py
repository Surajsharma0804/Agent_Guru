"""Goal Executor - Coordinates goal execution with Agent Orchestration.

This module handles the execution of goals by converting them into tasks for
Agent Orchestration, tracking execution progress, committing to GitHub, and
reporting metrics to the Self-Improvement Engine.

Performance Characteristics:
- Time Complexity: O(n) for n sub-goals (sequential execution)
- Space Complexity: O(k) for k active executions
- Execution: Sequential sub-goal processing
- GitHub: Async commit after each sub-goal completion

Architecture:
    The executor manages the complete lifecycle of goal execution:
    1. Mark goal as IN_PROGRESS
    2. Execute sub-goals sequentially (depth-first for hierarchies)
    3. Create tasks in Agent Orchestration for leaf goals
    4. Track active executions
    5. Commit to GitHub on completion
    6. Report metrics to Self-Improvement Engine
    7. Handle failures and propagate to parent

Author: Agent_Guru Team
Date: 2024
Version: 1.0.0
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from git import Repo

from Agent_Guru.goal_manager.exceptions import ExecutionError
from Agent_Guru.goal_manager.goal_storage import GoalStorage
from Agent_Guru.goal_manager.logging_config import get_logger
from Agent_Guru.goal_manager.models import Goal, GoalStatus

# Initialize structured logger
logger = get_logger(__name__)


# Upper bound on the background `git push` performed after a goal completes.
# GitPython kills the git process when this elapses, so an unreachable remote
# cannot pin a worker thread indefinitely.
_GIT_PUSH_TIMEOUT_S = 60.0


class GoalExecutor:
    """Coordinates goal execution with Agent Orchestration.

    Creates tasks, tracks execution, commits to GitHub, and reports metrics.

    Time Complexity: O(n) per goal where n is number of sub-goals
    Space Complexity: O(k) where k is number of active executions

    Attributes:
        agent_orchestration: Agent Orchestration system for task execution
        storage: Goal storage for persistence
        git_repo: GitPython Repo object for commits
        self_improvement_engine: Self-Improvement Engine for metrics
        active_executions: Dict mapping goal_id to task_id for tracking

    Example:
        >>> executor = GoalExecutor(
        ...     agent_orchestration=orchestrator,
        ...     storage=storage,
        ...     git_repo_path=".",
        ...     self_improvement_engine=engine
        ... )
        >>> await executor.execute_goal(goal_id)

    """

    def __init__(
        self,
        agent_orchestration: Any,  # Type: 'AgentOrchestration'
        storage: GoalStorage,
        git_repo_path: str,
        self_improvement_engine: Any,  # Type: 'SelfImprovementEngine'
    ) -> None:
        """Initialize Goal Executor with dependencies.

        Args:
            agent_orchestration: Agent Orchestration system for task execution
            storage: Goal storage for persistence
            git_repo_path: Path to Git repository for commits
            self_improvement_engine: Self-Improvement Engine for metrics reporting

        Raises:
            ExecutionError: If git_repo_path is invalid or not a Git repository

        """
        self.agent_orchestration = agent_orchestration
        self.storage = storage
        self.self_improvement_engine = self_improvement_engine

        # Initialize Git repository
        try:
            self.git_repo = Repo(git_repo_path)
        except Exception as e:
            logger.exception(
                "git_repo_initialization_failed",
                operation="init",
                git_repo_path=git_repo_path,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Gracefully degrade — GitHub commits will be skipped
            self.git_repo = None

        # Track active executions: goal_id -> task_id
        self.active_executions: dict[str, str] = {}

    async def execute_goal(self, goal_id: str) -> None:
        """Execute goal by processing sub-goals sequentially.

        This method implements the main execution logic:
        1. Mark goal as IN_PROGRESS with timestamp
        2. Iterate through sub_goal_ids sequentially
        3. Handle recursive execution for sub-goals with children
        4. Handle leaf sub-goal execution via _execute_sub_goal()
        5. Check for failures and propagate to parent
        6. Mark goal as COMPLETE when all sub-goals done

        Time Complexity: O(n) where n is total number of sub-goals in hierarchy
        Space Complexity: O(d) where d is depth of recursion

        Args:
            goal_id: Goal to execute

        Raises:
            ExecutionError: If goal not found or execution fails critically

        Example:
            >>> await executor.execute_goal("goal-uuid-123")

        """
        # Retrieve goal from storage
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            logger.error(
                "goal_execution_failed",
                goal_id=goal_id,
                operation="execute",
                error="Goal not found",
            )
            msg = f"Goal {goal_id} not found"
            raise ExecutionError(msg)

        # Mark as IN_PROGRESS with timestamp
        goal.status = GoalStatus.IN_PROGRESS
        goal.started_at = datetime.now(tz=UTC)
        await self.storage.update_goal(goal)

        # If no sub-goals and agent_orchestration is set, execute as leaf task
        if not goal.sub_goal_ids and self.agent_orchestration is not None:
            await self._execute_sub_goal(goal)
            # BUG FIX: this used to return here without ever calling
            # _report_completion(). _execute_sub_goal() itself only commits
            # to GitHub on success -- it never reports to the
            # Self-Improvement Engine (that happens exclusively in the
            # multi-sub-goal loop below). A top-level goal with no
            # decomposition (the common case for a single, non-decomposed
            # task) would therefore complete and commit successfully while
            # silently never being recorded as a completed task for
            # learning/metrics purposes -- an asymmetry with the
            # multi-sub-goal path, which always reports on full completion.
            # _execute_sub_goal(goal) mutates `goal` in place (same object),
            # so goal.status already reflects the outcome here.
            if goal.status == GoalStatus.COMPLETE:
                await self._report_completion(goal)
            return

        # Execute sub-goals sequentially
        for sub_goal_id in goal.sub_goal_ids:
            # Retrieve sub-goal
            sub_goal = await self.storage.get_goal(sub_goal_id)
            if not sub_goal:
                # Log warning but continue with other sub-goals
                continue

            # Check if sub-goal has its own sub-goals (recursive case)
            if sub_goal.sub_goal_ids:
                # Recursively execute sub-goal with children
                await self.execute_goal(sub_goal_id)
            else:
                # Execute leaf sub-goal as task
                await self._execute_sub_goal(sub_goal)

            # Refresh sub-goal state after execution
            sub_goal = await self.storage.get_goal(sub_goal_id)

            # Check if sub-goal failed
            if sub_goal and sub_goal.status == GoalStatus.FAILED:
                # Propagate failure to parent
                goal.status = GoalStatus.FAILED
                goal.error_message = f"Sub-goal {sub_goal_id} failed: {sub_goal.error_message}"
                goal.completed_at = datetime.now(tz=UTC)
                await self.storage.update_goal(goal)
                return

        # All sub-goals completed successfully
        goal.status = GoalStatus.COMPLETE
        goal.progress = 1.0
        goal.completed_at = datetime.now(tz=UTC)
        await self.storage.update_goal(goal)

        # Report completion to Self-Improvement Engine
        await self._report_completion(goal)

    async def _execute_sub_goal(self, sub_goal: Goal) -> None:
        """Execute a single leaf sub-goal as a task.

        This method implements the execution logic for individual leaf sub-goals:
        1. Mark sub-goal as IN_PROGRESS with timestamp
        2. Create task in Agent Orchestration with metadata
        3. Track task_id in active_executions
        4. Wait for task completion
        5. Handle success: mark COMPLETE, commit to GitHub
        6. Handle failure: mark FAILED with error message
        7. Clean up active_executions entry

        Time Complexity: O(1) for task creation, O(t) for waiting where t is task duration
        Space Complexity: O(1)

        Args:
            sub_goal: Leaf sub-goal to execute

        Raises:
            ExecutionError: If task creation fails critically

        Example:
            >>> await executor._execute_sub_goal(leaf_goal)

        """
        # Mark sub-goal as IN_PROGRESS with timestamp
        sub_goal.status = GoalStatus.IN_PROGRESS
        sub_goal.started_at = datetime.now(tz=UTC)
        await self.storage.update_goal(sub_goal)

        try:
            # If no agent orchestration, mark complete directly (standalone mode)
            if self.agent_orchestration is None:
                sub_goal.status = GoalStatus.COMPLETE
                sub_goal.progress = 1.0
                sub_goal.completed_at = datetime.now(tz=UTC)
                await self.storage.update_goal(sub_goal)
                return

            # Create task for Agent Orchestration with metadata
            task = await self.agent_orchestration.create_task(
                name=f"Goal: {sub_goal.description}",
                description=sub_goal.description,
                task_type="goal_execution",
                metadata={"goal_id": sub_goal.id},
            )

            # Track task_id in active_executions
            self.active_executions[sub_goal.id] = task.task_id

            # Wait for task completion
            result = await self.agent_orchestration.wait_for_task(task.task_id)

            # Handle success
            if result.success:
                # Mark sub-goal as COMPLETE
                sub_goal.status = GoalStatus.COMPLETE
                sub_goal.progress = 1.0
                sub_goal.completed_at = datetime.now(tz=UTC)
                await self.storage.update_goal(sub_goal)

                # Commit to GitHub (will be implemented in task 10.4)
                await self._commit_to_github(sub_goal)
            else:
                # Handle failure: mark FAILED with error message
                logger.error(
                    "task_execution_failed",
                    goal_id=sub_goal.id,
                    operation="execute_sub_goal",
                    error=result.error_message,
                )
                sub_goal.status = GoalStatus.FAILED
                sub_goal.error_message = result.error_message
                sub_goal.completed_at = datetime.now(tz=UTC)
                await self.storage.update_goal(sub_goal)

        except Exception as e:
            # Handle any unexpected errors during execution
            logger.exception(
                "subgoal_execution_exception",
                goal_id=sub_goal.id,
                operation="execute_sub_goal",
                error=str(e),
                error_type=type(e).__name__,
            )
            sub_goal.status = GoalStatus.FAILED
            sub_goal.error_message = str(e)
            sub_goal.completed_at = datetime.now(tz=UTC)
            await self.storage.update_goal(sub_goal)

        finally:
            # Clean up active_executions entry
            if sub_goal.id in self.active_executions:
                del self.active_executions[sub_goal.id]

    async def _report_completion(self, goal: Goal) -> None:
        """Report goal completion to Self-Improvement Engine.

        Reports metrics about goal execution to the Self-Improvement Engine for
        tracking and learning. Includes task_id, task_type, strategy, success status,
        execution time, and error details if failed.

        Errors are handled gracefully - if reporting fails, the error is logged but
        the goal is not marked as failed. This ensures that Self-Improvement Engine
        connectivity issues don't prevent goal completion.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            goal: Completed goal to report

        Example:
            >>> await executor._report_completion(completed_goal)

        Note:
            This method handles errors gracefully - if Self-Improvement Engine
            operations fail, the error is logged but the goal is not marked as failed.

        """
        try:
            if self.self_improvement_engine is None:
                return

            # Calculate execution_time_ms from timestamps
            execution_time_ms = 0.0
            if goal.completed_at and goal.started_at:
                execution_time_ms = (goal.completed_at - goal.started_at).total_seconds() * 1000

            # Determine success status
            success = goal.status == GoalStatus.COMPLETE

            # Prepare error_details if failed
            error_details = None
            if not success and goal.error_message:
                error_details = {"error": goal.error_message}

            # Call Self-Improvement Engine record_task_execution()
            self.self_improvement_engine.record_task_execution(
                task_id=goal.id,
                task_type="goal",
                strategy_used="goal_manager",
                success=success,
                execution_time_ms=execution_time_ms,
                error_details=error_details,
            )

        except Exception as e:
            # Log error but don't fail goal (graceful degradation)
            logger.exception(
                "self_improvement_reporting_failed",
                goal_id=goal.id,
                operation="report_completion",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Note: Goal execution continues successfully despite reporting failure

    async def _commit_to_github(self, goal: Goal) -> None:
        """Commit goal completion to GitHub.

        Creates a commit with the goal description and ID, then pushes to remote origin.
        Errors are logged but do not fail the goal execution (graceful degradation).

        Time Complexity: O(1) for git operations
        Space Complexity: O(1)

        Args:
            goal: Completed goal to commit

        Example:
            >>> await executor._commit_to_github(completed_goal)

        Note:
            This method handles errors gracefully - if GitHub operations fail,
            the error is logged but the goal is not marked as failed. This ensures
            that GitHub connectivity issues don't prevent goal completion.

        """
        try:
            if self.git_repo is None:
                return

            def _git_work() -> None:
                # EVENT-LOOP FIX: all three of these are blocking. `git add -A`
                # walks the worktree, `index.commit()` writes objects, and
                # `origin.push()` is a NETWORK operation that can take seconds
                # to minutes -- and every one of them ran directly inside this
                # `async def`, freezing the entire assistant for the duration.
                # Goal completion is a background bookkeeping step; it must not
                # be able to stall the voice pipeline.

                # Stage all changes with git.add(A=True)
                self.git_repo.git.add(A=True)

                # Create commit with goal description and ID
                commit_message = (
                    f"Goal completed: {goal.description}\n\nGoal ID: {goal.id}"
                )
                self.git_repo.index.commit(commit_message)

                # HANG FIX: origin.push() had no time limit at all. An
                # unreachable or hanging remote (a VPN drop, a wedged SSH
                # connection) pinned this forever. GitPython's push() takes
                # kill_after_timeout, which terminates the underlying git
                # process rather than merely abandoning the wait -- verified
                # against the installed GitPython (3.1.x:
                # Remote.push(refspec, progress, kill_after_timeout, ...)).
                origin = self.git_repo.remote(name="origin")
                origin.push(kill_after_timeout=_GIT_PUSH_TIMEOUT_S)

            await asyncio.to_thread(_git_work)

        except Exception as e:
            # Log error but don't fail goal (graceful degradation)
            logger.exception(
                "github_commit_failed",
                goal_id=goal.id,
                operation="commit_to_github",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Note: Goal execution continues successfully despite GitHub failure

    async def stop_execution(self, goal_id: str) -> None:
        """Stop execution of a goal.

        This method stops the execution of an in-progress goal by canceling its
        associated task in Agent Orchestration and removing it from active tracking.

        If the goal is not currently executing (not in active_executions), this
        method does nothing (idempotent operation).

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            goal_id: Goal to stop execution for

        Example:
            >>> await executor.stop_execution("goal-uuid-123")

        Note:
            This method is idempotent - calling it multiple times or on a
            non-executing goal has no adverse effects.

        """
        # Check if goal_id in active_executions
        if goal_id in self.active_executions:
            # Get task_id for cancellation
            task_id = self.active_executions[goal_id]

            try:
                # Cancel task in Agent Orchestration
                await self.agent_orchestration.cancel_task(task_id)
            except Exception as e:
                # Log error but continue with cleanup
                logger.exception(
                    "task_cancellation_failed",
                    goal_id=goal_id,
                    task_id=task_id,
                    operation="stop_execution",
                    error=str(e),
                    error_type=type(e).__name__,
                )
            # (already logged above via logger.error)

            # Remove from active_executions (cleanup regardless of cancellation result)
            del self.active_executions[goal_id]

    async def resume_goal(self, goal_id: str) -> None:
        """Resume execution of an interrupted goal.

        This method resumes execution of a goal that was interrupted (e.g., due to
        system restart). It finds the last completed sub-goal and continues execution
        from the next sub-goal in the sequence.

        The method implements the following logic:
        1. Retrieve goal from storage
        2. Find last completed sub-goal index
        3. Resume from next sub-goal (last_completed_idx + 1)
        4. Execute remaining sub-goals sequentially

        If all sub-goals are already complete, this method does nothing (idempotent).
        If no sub-goals are complete, execution starts from the first sub-goal.

        Time Complexity: O(n) where n is number of remaining sub-goals
        Space Complexity: O(d) where d is depth of recursion

        Args:
            goal_id: Goal to resume execution for

        Raises:
            ExecutionError: If goal not found

        Example:
            >>> # Goal was interrupted after completing 2 of 5 sub-goals
            >>> await executor.resume_goal("goal-uuid-123")
            >>> # Execution resumes from sub-goal 3

        Note:
            This method is idempotent - if the goal is already complete or has no
            remaining sub-goals to execute, it does nothing.

        """
        # Retrieve goal from storage
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            logger.error(
                "goal_resume_failed",
                goal_id=goal_id,
                operation="resume",
                error="Goal not found",
            )
            msg = f"Goal {goal_id} not found"
            raise ExecutionError(msg)

        # Find last completed sub-goal index
        last_completed_idx = -1
        for i, sub_goal_id in enumerate(goal.sub_goal_ids):
            sub_goal = await self.storage.get_goal(sub_goal_id)
            if sub_goal and sub_goal.status == GoalStatus.COMPLETE:
                last_completed_idx = i
            else:
                # Stop at first non-complete sub-goal
                break

        # Resume from next sub-goal (last_completed_idx + 1)
        # If last_completed_idx is -1, starts from 0 (first sub-goal)
        # If last_completed_idx is len-1, range is empty (all complete, nothing to do)
        for i in range(last_completed_idx + 1, len(goal.sub_goal_ids)):
            sub_goal_id = goal.sub_goal_ids[i]

            # Retrieve sub-goal
            sub_goal = await self.storage.get_goal(sub_goal_id)
            if not sub_goal:
                # Log warning but continue with other sub-goals
                continue

            # Check if sub-goal has its own sub-goals (recursive case)
            if sub_goal.sub_goal_ids:
                # Recursively execute sub-goal with children
                await self.execute_goal(sub_goal_id)
            else:
                # Execute leaf sub-goal as task
                await self._execute_sub_goal(sub_goal)

            # Refresh sub-goal state after execution
            sub_goal = await self.storage.get_goal(sub_goal_id)

            # Check if sub-goal failed
            if sub_goal and sub_goal.status == GoalStatus.FAILED:
                # Propagate failure to parent
                goal.status = GoalStatus.FAILED
                goal.error_message = f"Sub-goal {sub_goal_id} failed: {sub_goal.error_message}"
                goal.completed_at = datetime.now(tz=UTC)
                await self.storage.update_goal(goal)
                return

        # All remaining sub-goals completed successfully
        # Check if ALL sub-goals are now complete
        all_complete = True
        for sub_goal_id in goal.sub_goal_ids:
            sub_goal = await self.storage.get_goal(sub_goal_id)
            if not sub_goal or sub_goal.status != GoalStatus.COMPLETE:
                all_complete = False
                break

        # Only mark goal as complete if ALL sub-goals are complete
        if all_complete:
            goal.status = GoalStatus.COMPLETE
            goal.progress = 1.0
            goal.completed_at = datetime.now(tz=UTC)
            await self.storage.update_goal(goal)

            # Report completion to Self-Improvement Engine
            await self._report_completion(goal)
