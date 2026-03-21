"""
Module: agent_guru.goal_manager.session_manager
Purpose: Manages goal persistence and restoration across system restarts

This module implements the session management layer for the Goal Manager system,
handling startup, shutdown, and recovery operations.

Performance Characteristics:
    - Time Complexity: O(n) for load_goals where n is number of goals
    - Time Complexity: O(1) for persist_all (no-op with immediate persistence)
    - Space Complexity: O(1) - no additional memory allocation
    - Recovery: Graceful handling of corrupted data

Architecture:
    The session manager coordinates with GoalStorage to:
    1. Load all goals on system startup
    2. Validate goal data integrity
    3. Attempt recovery for corrupted goals
    4. Provide consistent API for shutdown (no-op with immediate persistence)

Design Decisions:
    - Immediate persistence strategy means persist_all is a no-op
    - Validation checks required fields and timestamp ordering
    - Recovery marks corrupted goals as FAILED rather than deleting
    - Logging provides visibility into corruption issues

Author: Kiro AI
Date: 2024-01-15
Version: 1.0.0
"""

from typing import List
import json
from datetime import datetime
from .goal_storage import GoalStorage
from .models import Goal, GoalStatus, Priority
from .logging_config import get_logger

# Initialize structured logger
logger = get_logger(__name__)


class SessionManager:
    """
    Manages goal persistence across sessions.
    
    Handles system startup, shutdown, and recovery from corrupted data.
    Uses immediate persistence strategy where all updates are persisted
    immediately, making shutdown a no-op.
    
    Time Complexity:
        - load_goals: O(n) where n is number of goals
        - persist_all: O(1) - no-op with immediate persistence
        - _validate_goal_integrity: O(1) per goal
        - _attempt_recovery: O(1) per corrupted goal
    
    Space Complexity: O(1) - no additional memory allocation
    
    Example:
        >>> storage = GoalStorage("goals.db")
        >>> session_manager = SessionManager(storage)
        >>> await session_manager.load_goals()
        >>> # System operates...
        >>> await session_manager.persist_all()
    """
    
    def __init__(self, storage: GoalStorage):
        """
        Initialize session manager with storage dependency.
        
        Args:
            storage: GoalStorage instance for persistence operations
        """
        self.storage = storage
    
    async def load_goals(self) -> None:
        """
        Load all goals from storage on startup.
        
        Validates integrity of each goal and attempts recovery for
        corrupted goals. Logs warnings if corruption is detected.
        Handles cases where goals are so corrupted they can't be deserialized.
        
        Time Complexity: O(n) where n is number of goals
        Space Complexity: O(1) - processes goals one at a time
        
        Raises:
            StorageError: If storage operations fail catastrophically
        """
        from .exceptions import StorageError
        
        # Try to query all goals from storage
        # If this fails due to corruption, we need to handle it at the database level
        try:
            all_goals = await self.storage.query_goals()
        except StorageError as e:
            # If query_goals fails, it means some goals are so corrupted
            # they can't even be deserialized. We need to handle this at the DB level.
            logger.error(
                "severe_corruption_detected",
                operation="load_goals",
                error=str(e),
                error_type="StorageError"
            )
            print(f"Warning: Severe corruption detected during goal loading: {e}")
            
            # Try to recover by querying the database directly and handling each row
            all_goals = await self._load_goals_with_corruption_handling()
        
        # Validate integrity and collect corrupted goal IDs
        corrupted_goals: List[str] = []
        for goal in all_goals:
            if not self._validate_goal_integrity(goal):
                corrupted_goals.append(goal.id)
        
        # Log warning if corrupted goals found
        if corrupted_goals:
            logger.warning(
                "corrupted_goals_detected",
                operation="load_goals",
                count=len(corrupted_goals),
                goal_ids=corrupted_goals
            )
            print(f"Warning: {len(corrupted_goals)} corrupted goals detected")
            
            # Attempt recovery for each corrupted goal
            for goal_id in corrupted_goals:
                await self._attempt_recovery(goal_id)
    
    async def _load_goals_with_corruption_handling(self) -> List[Goal]:
        """
        Load goals with special handling for severely corrupted data.
        
        This method queries the database directly and attempts to deserialize
        each goal individually, skipping or recovering goals that can't be
        deserialized.
        
        Returns:
            List of successfully loaded goals (corrupted goals are recovered)
        """
        import sqlite3
        
        goals = []
        
        # Use the storage's persistent connection to avoid creating a new one
        conn = self.storage._conn
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id, description, status, priority, goal_type, progress, created_at, started_at, completed_at, deadline, parent_id, sub_goal_ids, dependency_ids, metadata, error_message, retry_count FROM goals")
            rows = cursor.fetchall()
            
            for row in rows:
                try:
                    # Try to convert row to goal
                    goal = self.storage._row_to_goal(row)
                    goals.append(goal)
                except Exception as e:
                    # Goal is severely corrupted - try to extract ID and mark as failed
                    logger.error(
                        "goal_deserialization_failed",
                        operation="load_with_corruption_handling",
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    try:
                        goal_id = row[0]  # ID is first column
                        if goal_id and len(goal_id) > 0:
                            # Preserve as many original fields as possible
                            original_description = row[1] if row[1] else "[Corrupted - no description]"
                            try:
                                original_priority = Priority(row[3])
                            except Exception:
                                original_priority = Priority.MEDIUM
                            try:
                                original_metadata = json.loads(row[13]) if row[13] else {}
                            except Exception:
                                original_metadata = {}
                            try:
                                original_sub_goal_ids = json.loads(row[11]) if row[11] else []
                            except Exception:
                                original_sub_goal_ids = []
                            try:
                                original_dependency_ids = json.loads(row[12]) if row[12] else []
                            except Exception:
                                original_dependency_ids = []
                            try:
                                original_created_at = datetime.fromisoformat(row[6]) if row[6] else datetime.now()
                            except Exception:
                                original_created_at = datetime.now()
                            try:
                                original_started_at = datetime.fromisoformat(row[7]) if row[7] else None
                            except Exception:
                                original_started_at = None

                            # Create a recovered goal preserving original data
                            goal = Goal(
                                id=goal_id,
                                description=original_description,
                                status=GoalStatus.FAILED,
                                priority=original_priority,
                                progress=0.0,
                                created_at=original_created_at,
                                started_at=original_started_at,
                                metadata=original_metadata,
                                sub_goal_ids=original_sub_goal_ids,
                                dependency_ids=original_dependency_ids,
                                error_message=f"Data corruption detected: {str(e)}"
                            )
                            goals.append(goal)
                            
                            # Update the database with the recovered goal
                            await self.storage.update_goal(goal)
                    except Exception:
                        # Can't even extract ID - skip this goal entirely
                        logger.error(
                            "goal_recovery_impossible",
                            operation="load_with_corruption_handling",
                            error="Cannot extract goal ID from corrupted data"
                        )
                        print(f"Warning: Skipping severely corrupted goal that can't be recovered")
        
        finally:
            pass  # Don't close the shared persistent connection
        
        return goals
    
    def _validate_goal_integrity(self, goal: Goal) -> bool:
        """
        Validate goal data integrity.
        
        Checks:
        - Required fields (id, description) are present
        - Timestamp ordering (created_at ≤ started_at ≤ completed_at)
        - Progress range (0.0 to 1.0)
        
        Time Complexity: O(1) - fixed number of checks
        Space Complexity: O(1) - no additional memory allocation
        
        Args:
            goal: Goal to validate
            
        Returns:
            True if goal is valid, False otherwise
        """
        # Check required fields
        if not goal.id or not goal.description:
            logger.warning(
                "goal_validation_failed",
                goal_id=goal.id if goal.id else "unknown",
                operation="validate",
                error="Missing required fields"
            )
            return False
        
        # Check timestamp ordering: created_at ≤ started_at
        if goal.started_at and goal.started_at < goal.created_at:
            logger.warning(
                "goal_validation_failed",
                goal_id=goal.id,
                operation="validate",
                error="Invalid timestamp ordering: started_at < created_at"
            )
            return False
        
        # Check timestamp ordering: started_at ≤ completed_at
        if goal.completed_at and goal.started_at and goal.completed_at < goal.started_at:
            logger.warning(
                "goal_validation_failed",
                goal_id=goal.id,
                operation="validate",
                error="Invalid timestamp ordering: completed_at < started_at"
            )
            return False
        
        # Check progress range
        if not (0.0 <= goal.progress <= 1.0):
            logger.warning(
                "goal_validation_failed",
                goal_id=goal.id,
                operation="validate",
                error=f"Invalid progress value: {goal.progress}"
            )
            return False
        
        return True
    
    async def _attempt_recovery(self, goal_id: str) -> None:
        """
        Attempt to recover corrupted goal.
        
        Recovery strategy: Mark goal as FAILED with error message
        indicating data corruption. This preserves the goal record
        for investigation while preventing further execution.
        
        Time Complexity: O(1) - single storage operation
        Space Complexity: O(1) - no additional memory allocation
        
        Args:
            goal_id: ID of corrupted goal
            
        Raises:
            StorageError: If storage operations fail
        """
        # Retrieve corrupted goal
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            logger.warning(
                "goal_recovery_skipped",
                goal_id=goal_id,
                operation="attempt_recovery",
                error="Goal not found"
            )
            return
        
        # Mark as FAILED with error message
        logger.info(
            "goal_recovered",
            goal_id=goal_id,
            operation="attempt_recovery",
            action="marked_as_failed"
        )
        goal.status = GoalStatus.FAILED
        goal.error_message = "Data corruption detected during recovery"
        
        # Update goal in storage
        await self.storage.update_goal(goal)
    
    async def persist_all(self) -> None:
        """
        Persist all goal state before shutdown.
        
        This is a no-op implementation because the Goal Manager uses
        immediate persistence strategy where all updates are persisted
        immediately to storage. Kept for API consistency.
        
        Time Complexity: O(1) - no-op
        Space Complexity: O(1) - no operations performed
        """
        # No-op: immediate persistence already handled by storage
        pass
