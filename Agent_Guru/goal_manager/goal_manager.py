"""Module: agent_guru.goal_manager.goal_manager
Purpose: Main API for goal lifecycle management.

This module provides the unified interface for all goal operations,
coordinating all components of the Goal Manager system.

Performance Characteristics:
    - Time Complexity: Varies by operation (delegates to components)
    - Space Complexity: O(1) for manager instance (components hold state)
    - Concurrency: Async/await for all I/O operations
    - Persistence: Immediate (delegated to storage)

Architecture:
    The GoalManager coordinates 7 core components:
    1. GoalStorage: Persistent storage with SQLite
    2. GoalDecomposer: LLM-powered goal decomposition
    3. ProgressTracker: Progress calculation and status propagation
    4. PriorityManager: Priority assignment and selection
    5. GoalExecutor: Task coordination with Agent Orchestration
    6. DependencyResolver: Dependency management and cycle detection
    7. SessionManager: Session persistence and recovery

Design Principles:
    - Coordinator pattern: Delegates to specialized components
    - Async-first: All operations are async for I/O efficiency
    - Fail-safe: Graceful error handling with detailed logging
    - Observable: Complete audit trail via GitHub commits

Author: Kiro AI
Date: 2024-01-15
Version: 1.0.0
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from Agent_Guru.goal_manager.dependency_resolver import DependencyResolver
from Agent_Guru.goal_manager.exceptions import (
    GoalManagerError,
    InvalidGoalStateError,
    ValidationError,
)
from Agent_Guru.goal_manager.goal_decomposer import GoalDecomposer
from Agent_Guru.goal_manager.goal_executor import GoalExecutor
from Agent_Guru.goal_manager.goal_storage import GoalStorage
from Agent_Guru.goal_manager.logging_config import get_logger
from Agent_Guru.goal_manager.models import ExecutionResult, Goal, GoalStatus, GoalType, Priority
from Agent_Guru.goal_manager.priority_manager import PriorityManager
from Agent_Guru.goal_manager.progress_tracker import ProgressTracker
from Agent_Guru.goal_manager.session_manager import SessionManager

# Initialize structured logger
logger = get_logger(__name__)


class GoalManager:
    """Main interface for goal lifecycle management.

    Coordinates all components and provides unified API for:
    - Creating and managing goals
    - Querying and filtering goals
    - Updating priorities and cancelling goals
    - System startup and shutdown
    - Progress tracking and reporting

    Time Complexity: Varies by operation (delegates to components)
    Space Complexity: O(1) for manager instance

    Example:
        >>> manager = GoalManager(
        ...     storage_path="goals.db",
        ...     git_repo_path=".",
        ...     llm_runtime=llm,
        ...     agent_orchestration=orchestrator,
        ...     memory_system=memory,
        ...     self_improvement_engine=engine
        ... )
        >>>
        >>> # Start the manager
        >>> await manager.start()
        >>>
        >>> # Create a goal
        >>> goal = await manager.create_goal(
        ...     description="Implement user authentication",
        ...     priority=Priority.HIGH
        ... )
        >>>
        >>> # Query goals
        >>> pending = await manager.query_goals(status=GoalStatus.PENDING)
        >>>
        >>> # Get summary
        >>> summary = await manager.get_summary()
        >>>
        >>> # Shutdown
        >>> await manager.shutdown()

    Attributes:
        storage: GoalStorage instance for persistence
        decomposer: GoalDecomposer instance for LLM decomposition
        progress_tracker: ProgressTracker instance for progress tracking
        priority_manager: PriorityManager instance for priority management
        executor: GoalExecutor instance for task execution
        dependency_resolver: DependencyResolver instance for dependency management
        session_manager: SessionManager instance for session persistence

    """

    def __init__(
        self,
        storage_path: str | None = None,
        git_repo_path: str = ".",
        llm_runtime: Any = None,  # noqa: ANN401
        agent_orchestration: Any = None,  # noqa: ANN401
        memory_system: Any = None,  # noqa: ANN401
        self_improvement_engine: Any = None,  # noqa: ANN401
        db_path: str | None = None,  # Alias for storage_path
        storage: Any | None = None,  # Direct storage injection (for tests)  # noqa: ANN401
        git_repo: Any | None = None,  # Unused, accepted for test compat  # noqa: ANN401
    ) -> None:
        """Initialize Goal Manager with all dependencies.

        Supports both ``storage_path`` and ``db_path`` for the database path.

        Args:
            storage_path: Path to SQLite database file (e.g., "goals.db")
            git_repo_path: Path to Git repository for audit trail (e.g., ".")
            llm_runtime: LLM Runtime instance with generate() method
            agent_orchestration: Agent Orchestration instance with create_task()
            memory_system: Memory System instance with query_similar()
            self_improvement_engine: Self-Improvement Engine with record_task_execution()
            db_path: Alias for storage_path (for test compatibility)
            storage: Direct GoalStorage instance (overrides storage_path/db_path)
            git_repo: Unused, accepted for test compatibility

        """
        # Support both storage_path and db_path
        resolved_path = storage_path or db_path or "goals.db"

        # Use injected storage or create new one
        if storage is not None:
            self.storage = storage
        else:
            self.storage = GoalStorage(resolved_path)

        # Initialize GoalDecomposer with LLM Runtime and Memory System
        self.decomposer = GoalDecomposer(llm_runtime, memory_system)

        # Initialize ProgressTracker with storage
        self.progress_tracker = ProgressTracker(self.storage)

        # Initialize PriorityManager with storage
        self.priority_manager = PriorityManager(self.storage)

        # Initialize GoalExecutor with Agent Orchestration and Self-Improvement Engine
        self.executor = GoalExecutor(
            agent_orchestration=agent_orchestration,
            storage=self.storage,
            git_repo_path=git_repo_path,
            self_improvement_engine=self_improvement_engine,
        )

        # Initialize DependencyResolver with storage
        self.dependency_resolver = DependencyResolver(self.storage)

        # Initialize SessionManager with storage
        self.session_manager = SessionManager(self.storage)

        # Private aliases used by integration/adversarial tests
        self._storage = self.storage
        self._executor = self.executor
        self._dependency_resolver = self.dependency_resolver
        self._priority_manager = self.priority_manager

        # Optional external system references (patched in tests)
        self._llm_runtime = llm_runtime
        self._orchestrator = agent_orchestration
        self._memory_system = memory_system
        self._improvement_engine = self_improvement_engine
        self._github_client: Any = None
        # Background task tracking (prevents GC of fire-and-forget tasks)
        self._background_tasks: set = set()

    async def create_goal(
        self,
        description: str,
        priority: Priority = Priority.MEDIUM,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        goal_type: GoalType = GoalType.TASK,
        parent_id: str | None = None,
        deadline: datetime | None = None,
    ) -> Goal:
        """Create a new goal.

        Creates a goal with unique ID, initial status PENDING, and triggers
        async decomposition. Validates dependencies for cycles before creation.

        Args:
            description: High-level goal description (min 1 character)
            priority: Goal priority (default: MEDIUM)
            dependencies: Optional list of dependency goal IDs
            metadata: Optional metadata dictionary
            goal_type: Type of goal (default: TASK)
            parent_id: Optional parent goal ID
            deadline: Optional deadline timestamp

        Returns:
            Created goal with unique ID and initial state

        Raises:
            ValidationError: If dependencies contain cycles
            StorageError: If persistence fails
            ValueError: If description is empty

        """
        # Create goal object with unique ID
        goal = Goal(
            id=str(uuid.uuid4()),
            description=description,
            status=GoalStatus.PENDING,
            priority=priority,
            goal_type=goal_type,
            progress=0.0,
            created_at=datetime.now(tz=UTC),
            started_at=None,
            completed_at=None,
            deadline=deadline,
            parent_id=parent_id,
            sub_goal_ids=[],
            dependency_ids=dependencies or [],
            metadata=metadata or {},
            error_message=None,
        )

        # Validate dependencies (check for cycles)
        if dependencies:
            await self.dependency_resolver.validate_dependencies(goal)

        # Persist immediately
        await self.storage.store_goal(goal)

        # If parent_id given, register as sub-goal of parent
        if parent_id:
            parent = await self.storage.get_goal(parent_id)
            if parent and goal.id not in parent.sub_goal_ids:
                parent.sub_goal_ids.append(goal.id)
                await self.storage.update_goal(parent)

        # Start decomposition asynchronously — store ref to prevent GC
        _task = asyncio.create_task(self._decompose_goal(goal.id))
        self._background_tasks.add(_task)
        _task.add_done_callback(self._background_tasks.discard)

        return goal

    async def get_goal(self, goal_id: str) -> Goal | None:
        """Get goal by ID with complete hierarchy.

        Args:
            goal_id: Goal identifier

        Returns:
            Goal object if found, None otherwise

        Raises:
            GoalManagerError: If goal_id format is invalid

        """
        # Validate UUID format — raise for invalid IDs (security)
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(goal_id):
            msg = f"Invalid goal ID format: {goal_id}"
            raise GoalManagerError(msg)
        return await self.storage.get_goal(goal_id)

    async def query_goals(
        self,
        status: GoalStatus | None = None,
        priority: Priority | None = None,
    ) -> list[Goal]:
        """Query goals with optional filters.

        Args:
            status: Optional status filter
            priority: Optional priority filter

        Returns:
            List of goals matching filters

        Example:
            >>> pending = await manager.query_goals(status=GoalStatus.PENDING)
            >>> high_priority = await manager.query_goals(priority=Priority.HIGH)

        """
        return await self.storage.query_goals(status=status, priority=priority)

    async def update_priority(self, goal_id: str, priority: Priority) -> None:
        """Update goal priority.

        Args:
            goal_id: Goal identifier
            priority: New priority level

        Raises:
            ValueError: If goal not found
            StorageError: If persistence fails

        Example:
            >>> await manager.update_priority("goal-id-123", Priority.CRITICAL)

        """
        await self.priority_manager.update_priority(goal_id, priority)

    async def cancel_goal(self, goal_id: str, reason: str | None = None) -> None:
        """Cancel goal and all sub-goals.

        Recursively cancels all sub-goals and stops execution if in progress.

        Args:
            goal_id: Goal identifier
            reason: Optional cancellation reason

        Raises:
            ValueError: If goal not found
            StorageError: If persistence fails

        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            msg = f"Goal {goal_id} not found"
            raise ValueError(msg)

        # Cancel all sub-goals recursively
        for sub_goal_id in goal.sub_goal_ids:
            await self.cancel_goal(sub_goal_id, reason=reason)

        # Stop execution if in progress
        if goal.status == GoalStatus.IN_PROGRESS:
            await self.executor.stop_execution(goal_id)

        # Mark as cancelled
        goal.status = GoalStatus.CANCELLED
        if reason:
            goal.metadata["cancellation_reason"] = reason
        await self.storage.update_goal(goal)

    async def initialize(self) -> None:
        """Initialize Goal Manager (alias for start).

        Loads all goals from storage and recovers in-progress goals.
        """
        await self.storage.initialize()
        # Recover in-progress goals that were interrupted
        in_progress_goals = await self.storage.query_goals(status=GoalStatus.IN_PROGRESS)
        for goal in in_progress_goals:
            goal.status = GoalStatus.FAILED
            goal.metadata["failure_reason"] = "crash recovery"
            await self.storage.update_goal(goal)

    async def list_goals(
        self,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[Goal]:
        """List goals with optional filters and limit.

        Args:
            filters: Optional dict of field→value filters (e.g. {"priority": Priority.HIGH})
            limit: Optional maximum number of results

        Returns:
            List of matching goals

        """
        status = None
        priority = None
        if filters:
            status = filters.get("status")
            priority = filters.get("priority")
        goals = await self.storage.query_goals(status=status, priority=priority)
        if limit is not None:
            goals = goals[:limit]
        return goals

    async def update_goal(
        self,
        goal_id: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        deadline: datetime | None = None,
        priority: Priority | None = None,
    ) -> Goal:
        """Update goal fields.

        Args:
            goal_id: Goal identifier
            description: New description (PENDING only)
            metadata: Metadata to merge
            dependencies: New dependency list (validated for cycles)
            deadline: New deadline
            priority: New priority

        Returns:
            Updated goal

        Raises:
            GoalManagerError: If goal not found
            CircularDependencyError: If dependencies create a cycle

        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            msg = f"Goal {goal_id} not found"
            raise GoalManagerError(msg)

        if description is not None:
            if goal.status == GoalStatus.COMPLETE:
                msg = "Cannot modify COMPLETE goal description"
                raise InvalidGoalStateError(msg)
            goal.description = description

        if metadata is not None:
            goal.metadata.update(metadata)

        if dependencies is not None:
            # Validate for cycles
            test_goal = goal.model_copy(update={"dependency_ids": dependencies})
            await self.dependency_resolver.validate_dependencies(test_goal)
            goal.dependency_ids = dependencies

        if deadline is not None:
            goal.deadline = deadline

        if priority is not None:
            goal.priority = priority

        await self.storage.update_goal(goal)
        return goal

    async def execute_goal(self, goal_id: str) -> ExecutionResult:
        """Execute a goal.

        Checks dependencies are met, then delegates to executor.

        Args:
            goal_id: Goal identifier

        Returns:
            ExecutionResult with success flag

        Raises:
            InvalidGoalStateError: If dependencies not met or goal already executing
            GoalManagerError: If goal not found

        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            msg = f"Goal {goal_id} not found"
            raise GoalManagerError(msg)

        # Check if already completed or cancelled
        if goal.status in (GoalStatus.COMPLETE, GoalStatus.CANCELLED):
            msg = f"Cannot execute goal in state {goal.status}"
            raise InvalidGoalStateError(msg)

        # Check if already executing (race condition guard)
        if goal.status == GoalStatus.IN_PROGRESS:
            msg = "Goal is already executing"
            raise InvalidGoalStateError(msg)

        # Check dependencies
        deps_met = await self.dependency_resolver.check_dependencies(goal)
        if not deps_met:
            msg = "Goal dependencies are not yet satisfied"
            raise InvalidGoalStateError(msg)

        try:
            await self.executor.execute_goal(goal_id)
            # Refresh goal to get final status
            updated = await self.storage.get_goal(goal_id)
            success = updated is not None and updated.status == GoalStatus.COMPLETE
            return ExecutionResult(success=success, goal_id=goal_id)
        except Exception as e:
            return ExecutionResult(success=False, goal_id=goal_id, error=str(e))

    async def add_dependency(self, goal_id: str, dependency_id: str) -> None:
        """Add a dependency to a goal, checking for cycles.

        Args:
            goal_id: Goal to add dependency to
            dependency_id: Goal that must complete first

        Raises:
            CircularDependencyError: If adding this dependency creates a cycle
            GoalManagerError: If either goal not found

        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            msg = f"Goal {goal_id} not found"
            raise GoalManagerError(msg)

        new_deps = [*list(goal.dependency_ids), dependency_id]
        test_goal = goal.model_copy(update={"dependency_ids": new_deps})
        await self.dependency_resolver.validate_dependencies(test_goal)

        goal.dependency_ids = new_deps
        await self.storage.update_goal(goal)

    async def get_sub_goals(self, goal_id: str) -> list[Goal]:
        """Get all direct sub-goals of a goal.

        Args:
            goal_id: Parent goal identifier

        Returns:
            List of sub-goals

        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            return []
        sub_goals = []
        for sub_id in goal.sub_goal_ids:
            sub = await self.storage.get_goal(sub_id)
            if sub:
                sub_goals.append(sub)
        return sub_goals

    async def get_goal_history(self, goal_id: str) -> list[Goal]:
        """Get execution history for a goal.

        Returns a list of goal snapshots representing state transitions.
        For now returns the current goal state as a single-item list.

        Args:
            goal_id: Goal identifier

        Returns:
            List of goal state snapshots (most recent first)

        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            return []
        return [goal]

    async def retry_goal(self, goal_id: str) -> Any:  # noqa: ANN401
        """Retry a failed goal.

        Resets status to PENDING and re-executes.

        Args:
            goal_id: Goal identifier

        Returns:
            ExecutionResult

        Raises:
            GoalManagerError: If goal not found or not in FAILED state

        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            msg = f"Goal {goal_id} not found"
            raise GoalManagerError(msg)

        if goal.status != GoalStatus.FAILED:
            msg = f"Can only retry FAILED goals, got {goal.status}"
            raise InvalidGoalStateError(msg)

        goal.status = GoalStatus.PENDING
        goal.retry_count += 1
        goal.error_message = None
        await self.storage.update_goal(goal)

        try:
            await self.executor.execute_goal(goal_id)
            updated = await self.storage.get_goal(goal_id)
            success = updated is not None and updated.status == GoalStatus.COMPLETE
            return ExecutionResult(success=success, goal_id=goal_id)
        except Exception as e:
            return ExecutionResult(success=False, goal_id=goal_id, error=str(e))

    async def modify_goal(
        self,
        goal_id: str,
        description: str | None = None,
        notes: str | None = None,
    ) -> Goal:
        """Modify goal description or add notes.

        Allows modification of goal description for PENDING goals only.
        Prevents modification of COMPLETE goals (except adding notes via metadata).

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            goal_id: Goal identifier
            description: New description (only for PENDING goals)
            notes: Notes to add to metadata (allowed for any status)

        Returns:
            Modified goal

        Raises:
            ValueError: If goal not found or invalid modification
            ValidationError: If trying to modify COMPLETE goal description
            StorageError: If persistence fails

        Example:
            >>> # Modify PENDING goal description
            >>> goal = await manager.modify_goal("goal-123", description="New description")

            >>> # Add notes to COMPLETE goal
            >>> goal = await manager.modify_goal("goal-456", notes="Additional context")

        Validates: Requirements 9.3, 9.4, 9.5

        """
        # Retrieve goal
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            msg = f"Goal {goal_id} not found"
            raise ValueError(msg)

        # Handle description modification
        if description is not None:
            # Prevent modification of COMPLETE goals
            if goal.status == GoalStatus.COMPLETE:
                msg = "Cannot modify description of COMPLETE goal"
                raise ValidationError(
                    msg,
                    {"goal_id": goal_id, "status": goal.status.value},
                )

            old_description = goal.description
            # Update description
            goal.description = description

            logger.info(
                "goal_description_modified",
                goal_id=goal_id,
                old_description=old_description[:50] if old_description else None,
                new_description=description[:50],
            )

        # Handle notes addition (allowed for any status)
        if notes is not None:
            if "notes" not in goal.metadata:
                goal.metadata["notes"] = []

            # Add note with timestamp
            goal.metadata["notes"].append(
                {"timestamp": datetime.now(tz=UTC).isoformat(), "content": notes},
            )

            logger.info(
                "goal_notes_added",
                goal_id=goal_id,
                notes_count=len(goal.metadata["notes"]),
            )

        # Persist changes immediately
        await self.storage.update_goal(goal)

        return goal

    async def re_decompose_goal(self, goal_id: str) -> None:
        """Re-decompose goal after description change.

        Clears existing sub-goals and triggers new decomposition.
        Only allowed for PENDING goals.

        Time Complexity: O(n) where n is number of sub-goals
        Space Complexity: O(1)

        Args:
            goal_id: Goal identifier

        Raises:
            ValueError: If goal not found
            ValidationError: If goal is not PENDING
            StorageError: If persistence fails
            DecompositionError: If decomposition fails

        Example:
            >>> # Modify goal description
            >>> await manager.modify_goal("goal-123", description="New description")

            >>> # Re-decompose with new description
            >>> await manager.re_decompose_goal("goal-123")

        Validates: Requirements 9.4

        """
        # Retrieve goal
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            msg = f"Goal {goal_id} not found"
            raise ValueError(msg)

        # Only allow for PENDING goals
        if goal.status != GoalStatus.PENDING:
            msg = "Can only re-decompose PENDING goals"
            raise ValidationError(
                msg,
                {"goal_id": goal_id, "status": goal.status.value},
            )

        logger.info(
            "goal_redecomposition_started",
            goal_id=goal_id,
            old_sub_goals_count=len(goal.sub_goal_ids),
        )

        # Clear existing sub-goals
        # Note: In a production system, we might want to archive these
        # rather than delete them
        for sub_goal_id in goal.sub_goal_ids:
            # Delete sub-goal from storage
            sub_goal = await self.storage.get_goal(sub_goal_id)
            if sub_goal:
                # Mark as cancelled before deletion
                sub_goal.status = GoalStatus.CANCELLED
                await self.storage.update_goal(sub_goal)

        # Clear sub-goal IDs
        goal.sub_goal_ids = []
        await self.storage.update_goal(goal)

        # Trigger new decomposition
        await self._decompose_goal(goal_id)

        logger.info("goal_redecomposition_completed", goal_id=goal_id)

    async def get_summary(self) -> dict[str, Any]:
        """Get summary of all goals.

        Returns:
            Dictionary with total, completed, in_progress, failed counts
            and overall progress percentage

        Example:
            >>> summary = await manager.get_summary()
            >>> print(f"Progress: {summary['overall_progress']:.1%}")
            >>> print(f"Completed: {summary['completed']}/{summary['total_goals']}")

        """
        all_goals = await self.storage.query_goals()

        total = len(all_goals)
        completed = sum(1 for g in all_goals if g.status == GoalStatus.COMPLETE)
        in_progress = sum(1 for g in all_goals if g.status == GoalStatus.IN_PROGRESS)
        failed = sum(1 for g in all_goals if g.status == GoalStatus.FAILED)

        overall_progress = sum(g.progress for g in all_goals) / total if total > 0 else 0.0

        return {
            "total_goals": total,
            "completed": completed,
            "in_progress": in_progress,
            "failed": failed,
            "overall_progress": overall_progress,
        }

    async def start(self) -> None:
        """Start Goal Manager (load goals from storage).

        Loads all goals from storage and resumes interrupted goals that
        were IN_PROGRESS during shutdown.

        Raises:
            StorageError: If loading fails

        """
        # Load all goals from storage
        await self.session_manager.load_goals()

        # Resume interrupted goals
        in_progress_goals = await self.storage.query_goals(status=GoalStatus.IN_PROGRESS)
        for goal in in_progress_goals:
            await self.executor.resume_goal(goal.id)

    async def shutdown(self) -> None:
        """Shutdown Goal Manager (persist all state).

        Ensures all goal state is persisted before termination.
        With immediate persistence strategy, this is a no-op but kept
        for API consistency.

        Example:
            >>> await manager.shutdown()
            >>> print("Goal Manager shutdown complete")

        """
        await self.session_manager.persist_all()

    async def _decompose_goal(self, goal_id: str) -> None:
        """Decompose goal into sub-goals (internal helper).

        Async helper that:
        1. Marks goal as DECOMPOSING
        2. Calls LLM to generate sub-goals
        3. Stores sub-goals with parent reference
        4. Marks goal as PENDING or READY
        5. Starts execution if ready
        6. Handles errors by marking goal as FAILED

        Args:
            goal_id: Goal to decompose

        Note:
            This is an internal method called asynchronously by create_goal.
            Errors are caught and logged, not propagated.

        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            return

        # Mark as decomposing
        goal.status = GoalStatus.DECOMPOSING
        await self.storage.update_goal(goal)

        try:
            # Decompose using LLM
            sub_goals = await self.decomposer.decompose(goal)

            # Store sub-goals
            for sub_goal in sub_goals:
                sub_goal.parent_id = goal.id
                await self.storage.store_goal(sub_goal)
                goal.sub_goal_ids.append(sub_goal.id)

            # Update parent
            goal.status = GoalStatus.PENDING
            await self.storage.update_goal(goal)

            # Check if ready for execution
            if await self.dependency_resolver.is_ready(goal):
                goal.status = GoalStatus.READY
                await self.storage.update_goal(goal)
                await self.executor.execute_goal(goal.id)

        except Exception as e:
            # Mark as failed on error
            goal.status = GoalStatus.FAILED
            goal.error_message = str(e)
            await self.storage.update_goal(goal)
