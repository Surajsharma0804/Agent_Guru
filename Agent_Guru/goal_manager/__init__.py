"""Goal Manager - Persistent autonomous goal management system.

This module provides persistent, self-managing goal execution across multiple
sessions with LLM-powered decomposition, progress tracking, and GitHub integration.

Core Components:
- GoalManager: Main API for goal lifecycle management
- GoalStorage: SQLite-based persistent storage
- GoalDecomposer: LLM-powered goal decomposition
- ProgressTracker: Progress calculation and status propagation
- PriorityManager: Priority assignment and selection
- GoalExecutor: Task coordination with Agent Orchestration
- DependencyResolver: Dependency management and cycle detection
- SessionManager: Session persistence and recovery

Example Usage:
    >>> from Agent_Guru.goal_manager import GoalManager, Priority
    >>>
    >>> # Initialize Goal Manager
    >>> manager = GoalManager(
    ...     storage_path="goals.db",
    ...     git_repo_path=".",
    ...     llm_runtime=llm,
    ...     agent_orchestration=orchestrator,
    ...     memory_system=memory,
    ...     self_improvement_engine=engine
    ... )
    >>>
    >>> # Create a goal
    >>> goal = await manager.create_goal(
    ...     description="Implement user authentication",
    ...     priority=Priority.HIGH
    ... )
    >>>
    >>> # Query goals
    >>> pending_goals = await manager.query_goals(status=GoalStatus.PENDING)
    >>>
    >>> # Get summary
    >>> summary = await manager.get_summary()
    >>> print(f"Progress: {summary['overall_progress']:.1%}")

Author: Agent_Guru Team
Version: 1.0.0
"""

from Agent_Guru.goal_manager.dependency_resolver import DependencyResolver
from Agent_Guru.goal_manager.exceptions import (
    DecompositionError,
    ExecutionError,
    GoalManagerError,
    StorageError,
    ValidationError,
)
from Agent_Guru.goal_manager.goal_decomposer import GoalDecomposer
from Agent_Guru.goal_manager.goal_executor import GoalExecutor
from Agent_Guru.goal_manager.goal_manager import GoalManager
from Agent_Guru.goal_manager.goal_storage import GoalStorage
from Agent_Guru.goal_manager.models import (
    Goal,
    GoalStatus,
    Priority,
)
from Agent_Guru.goal_manager.priority_manager import PriorityManager
from Agent_Guru.goal_manager.progress_tracker import ProgressTracker
from Agent_Guru.goal_manager.session_manager import SessionManager
from Agent_Guru.goal_manager.utils import retry_with_backoff

__all__ = [
    "DecompositionError",
    "DependencyResolver",
    "ExecutionError",
    # Models
    "Goal",
    "GoalDecomposer",
    "GoalExecutor",
    # Main API
    "GoalManager",
    # Exceptions
    "GoalManagerError",
    "GoalStatus",
    # Components
    "GoalStorage",
    "Priority",
    "PriorityManager",
    "ProgressTracker",
    "SessionManager",
    "StorageError",
    "ValidationError",
    # Utilities
    "retry_with_backoff",
]

__version__ = "1.0.0"
