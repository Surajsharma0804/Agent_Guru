"""
Exception hierarchy for Goal Manager.

Defines all custom exceptions used throughout the Goal Manager system.
This module provides a comprehensive exception hierarchy for error handling
across all Goal Manager components.

Exception Hierarchy:
    GoalManagerError (base)
    ├── StorageError
    ├── DecompositionError
    ├── ValidationError
    └── ExecutionError

Usage:
    from Agent_Guru.goal_manager.exceptions import (
        GoalManagerError,
        StorageError,
        DecompositionError,
        ValidationError,
        ExecutionError
    )

    try:
        await storage.store_goal(goal)
    except StorageError as e:
        logger.error("Storage operation failed: %s", e)
"""


class GoalManagerError(Exception):
    """
    Base exception for all Goal Manager errors.

    This is the root exception class for the Goal Manager system. All other
    Goal Manager exceptions inherit from this class, allowing callers to catch
    all Goal Manager-specific errors with a single except clause.

    Attributes:
        message: Human-readable error message
        context: Optional dictionary containing error context (goal_id, operation, etc.)

    Example:
        try:
            await goal_manager.create_goal("Test goal")
        except GoalManagerError as e:
            # Catches all Goal Manager errors
            logger.error("Goal Manager error: %s", e)

    Note:
        This exception should not be raised directly. Use one of the specific
        subclasses (StorageError, DecompositionError, etc.) instead.
    """

    def __init__(self, message: str, context: dict = None):
        """
        Initialize GoalManagerError.

        Args:
            message: Human-readable error message
            context: Optional dictionary with error context
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}


class StorageError(GoalManagerError):
    """
    Raised when storage operations fail.

    This exception is raised when any storage operation (store, update, retrieve,
    query) fails due to database errors, file system errors, or data corruption.

    Common Causes:
        - Database connection failures
        - Disk full or I/O errors
        - SQLite locking conflicts
        - Data corruption or invalid schema
        - Serialization/deserialization failures

    Recovery Strategy:
        - Retry operation with exponential backoff (up to 3 attempts)
        - Log error with full context (goal_id, operation type, error message)
        - Notify user if persistence fails after retries
        - Never lose in-memory state

    Example:
        try:
            await storage.store_goal(goal)
        except StorageError as e:
            logger.error(f"Failed to store goal {goal.id}: {e}")
            # Retry with backoff or notify user

    Attributes:
        message: Human-readable error message
        context: Dictionary with error context (goal_id, operation, error_details)
    """



class DecompositionError(GoalManagerError):
    """
    Raised when goal decomposition fails.

    This exception is raised when the LLM-powered goal decomposition process
    fails due to LLM Runtime errors, invalid responses, or validation failures.

    Common Causes:
        - LLM Runtime unavailable or timeout
        - LLM returns invalid JSON response
        - LLM returns empty or malformed sub-goals
        - Sub-goals fail validation (too short, too many, etc.)
        - Memory System unavailable for context retrieval

    Recovery Strategy:
        - Retry with exponential backoff (1s, 2s, 4s delays)
        - After 3 failures, mark goal as failed with error message
        - Log LLM request and response for debugging
        - Allow manual retry by user

    Example:
        try:
            sub_goals = await decomposer.decompose(goal)
        except DecompositionError as e:
            logger.error(f"Failed to decompose goal {goal.id}: {e}")
            goal.status = GoalStatus.FAILED
            goal.error_message = str(e)

    Attributes:
        message: Human-readable error message
        context: Dictionary with error context (goal_id, llm_response, validation_errors)
    """



class ValidationError(GoalManagerError):
    """
    Raised when validation fails.

    This exception is raised when data validation fails, including circular
    dependency detection, invalid goal data, schema validation failures, and
    constraint violations.

    Common Causes:
        - Circular dependencies detected (A → B → C → A)
        - Invalid goal data (missing required fields, invalid types)
        - Schema validation failures during deserialization
        - Constraint violations (invalid progress range, timestamp ordering)
        - Invalid enum values (status, priority)

    Recovery Strategy:
        - Fail fast with descriptive error message
        - Do not modify system state
        - Log validation failure details
        - Return error to user immediately
        - Suggest corrective actions (e.g., which goals form cycle)

    Example:
        try:
            dependency_resolver.validate_dependencies(goal)
        except ValidationError as e:
            logger.error(f"Validation failed for goal {goal.id}: {e}")
            # Return error to user with suggested fix

    Attributes:
        message: Human-readable error message
        context: Dictionary with error context (goal_id, validation_type, details)
    """



class ExecutionError(GoalManagerError):
    """
    Raised when goal execution fails.

    This exception is raised when goal execution fails due to Agent Orchestration
    errors, task failures, GitHub commit failures, or other execution-related issues.

    Common Causes:
        - Agent Orchestration unavailable or timeout
        - Task creation or execution failure
        - Sub-goal execution failure
        - GitHub commit or push failure
        - Self-Improvement Engine reporting failure

    Recovery Strategy:
        - Queue tasks if Agent Orchestration unavailable
        - Retry task creation with exponential backoff
        - Mark sub-goal as failed if task fails
        - Propagate failure to parent goal
        - Log execution failure details
        - GitHub failures are logged but don't fail the goal

    Example:
        try:
            await executor.execute_goal(goal_id)
        except ExecutionError as e:
            logger.error("Failed to execute goal %s: %s", goal_id, e)
            goal.status = GoalStatus.FAILED
            goal.error_message = str(e)

    Attributes:
        message: Human-readable error message
        context: Dictionary with error context (goal_id, task_id, error_details)
    """



# Aliases for backward compatibility with tests
DatabaseError = StorageError


class GoalNotFoundError(GoalManagerError):
    """Raised when a goal cannot be found by ID."""


class CircularDependencyError(ValidationError):
    """Raised when a circular dependency is detected."""


class InvalidGoalStateError(ValidationError):
    """Raised when an operation is invalid for the current goal state."""
