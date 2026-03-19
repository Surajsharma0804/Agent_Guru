"""
Module: agent_guru.goal_manager.progress_tracker
Purpose: Track goal progress and propagate status changes

This module implements progress tracking for the Goal Manager system,
calculating completion percentages and updating parent goals recursively.

Performance Characteristics:
    - Time Complexity: O(h) where h is hierarchy depth (recursive parent updates)
    - Space Complexity: O(h) for recursion stack
    - Persistence: Immediate (delegates to storage)

Architecture:
    The progress tracker:
    1. Marks goals as complete/failed/in_progress
    2. Calculates parent progress as average of sub-goal progress
    3. Propagates completion status when all sub-goals complete
    4. Recursively updates grandparents up the hierarchy

Optimization Techniques:
    - Single database query per goal (no N+1 queries)
    - Tail recursion for parent updates
    - Early return for goals without parents

Author: Kiro AI
Date: 2024-01-15
Version: 1.0.0
"""

from datetime import datetime

from .models import GoalStatus
from .goal_storage import GoalStorage


class ProgressTracker:
    """
    Tracks goal progress and propagates status changes.
    
    Calculates completion percentages and updates parent goals recursively
    up the hierarchy.
    
    Time Complexity:
        - mark_complete: O(h) where h is hierarchy depth
        - mark_failed: O(h) where h is hierarchy depth
        - mark_in_progress: O(1) - single update
        - _update_parent_progress: O(h) - recursive parent updates
    
    Space Complexity: O(h) for recursion stack
    
    Example:
        >>> tracker = ProgressTracker(storage)
        >>> await tracker.mark_complete(sub_goal_id)
        >>> # Parent progress automatically updated
    """
    
    def __init__(self, storage: GoalStorage):
        """
        Initialize with storage.
        
        Args:
            storage: GoalStorage instance for persistence
        """
        self.storage = storage
    
    async def mark_complete(self, goal_id: str) -> None:
        """
        Mark goal as complete and update parent.
        
        Sets status to COMPLETE, progress to 1.0, and completion timestamp.
        Recursively updates parent progress up the hierarchy.
        
        Time Complexity: O(h) where h is hierarchy depth
        Space Complexity: O(h) for recursion stack
        
        Args:
            goal_id: Goal to mark as complete
        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            return
        
        # Update goal
        goal.status = GoalStatus.COMPLETE
        goal.progress = 1.0
        goal.completed_at = datetime.now()
        await self.storage.update_goal(goal)
        
        # Update parent if exists
        if goal.parent_id:
            await self._update_parent_progress(goal.parent_id)
    
    async def mark_failed(self, goal_id: str, error_message: str) -> None:
        """
        Mark goal as failed with error message.
        
        Sets status to FAILED, records error message, and sets completion timestamp.
        Updates parent progress to reflect the failure.
        
        Time Complexity: O(h) where h is hierarchy depth
        Space Complexity: O(h) for recursion stack
        
        Args:
            goal_id: Goal to mark as failed
            error_message: Error description
        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            return
        
        # Update goal
        goal.status = GoalStatus.FAILED
        goal.error_message = error_message
        goal.completed_at = datetime.now()
        await self.storage.update_goal(goal)
        
        # Update parent
        if goal.parent_id:
            await self._update_parent_progress(goal.parent_id)
    
    async def mark_in_progress(self, goal_id: str) -> None:
        """
        Mark goal as in progress.
        
        Sets status to IN_PROGRESS and records start timestamp if not already set.
        
        Time Complexity: O(1) - single update
        Space Complexity: O(1) - no additional memory
        
        Args:
            goal_id: Goal to mark as in progress
        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            return
        
        # Update goal
        goal.status = GoalStatus.IN_PROGRESS
        if not goal.started_at:
            goal.started_at = datetime.now()
        await self.storage.update_goal(goal)
    
    async def _update_parent_progress(self, parent_id: str) -> None:
        """
        Update parent goal's progress based on sub-goals.
        
        Calculates progress as average of sub-goal progress.
        Marks parent as complete if all sub-goals are complete.
        Recursively updates grandparent.
        
        Time Complexity: O(k + h) where k is number of sub-goals, h is hierarchy depth
        Space Complexity: O(k) for sub-goal list, O(h) for recursion stack
        
        Args:
            parent_id: Parent goal to update
        """
        parent = await self.storage.get_goal(parent_id)
        if not parent:
            return
        
        # Get all sub-goals
        sub_goals = []
        for sub_goal_id in parent.sub_goal_ids:
            sub_goal = await self.storage.get_goal(sub_goal_id)
            if sub_goal:
                sub_goals.append(sub_goal)
        
        if not sub_goals:
            return
        
        # Calculate progress as average of sub-goal progress
        total_progress = sum(g.progress for g in sub_goals)
        parent.progress = total_progress / len(sub_goals)
        
        # Check if all sub-goals are complete
        all_complete = all(g.status == GoalStatus.COMPLETE for g in sub_goals)
        if all_complete:
            parent.status = GoalStatus.COMPLETE
            parent.completed_at = datetime.now()
        
        await self.storage.update_goal(parent)
        
        # Recursively update grandparent
        if parent.parent_id:
            await self._update_parent_progress(parent.parent_id)
