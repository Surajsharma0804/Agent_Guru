"""
Module: agent_guru.goal_manager.priority_manager
Purpose: Manages goal priorities and selection logic

This module implements priority management for the Goal Manager system,
handling priority updates and intelligent goal selection for execution.

Performance Characteristics:
    - Time Complexity: O(1) for update_priority (single database update)
    - Time Complexity: O(n log n) for select_next_goal (sorting ready goals)
    - Space Complexity: O(n) where n is number of ready goals
    - Persistence: Immediate (updates persisted via storage)

Architecture:
    The priority manager provides:
    1. Priority updates with immediate persistence
    2. Intelligent goal selection based on priority and age
    3. Selection criteria: READY status, highest priority, oldest first

Selection Algorithm:
    1. Query all goals with status READY
    2. Sort by priority (CRITICAL > HIGH > MEDIUM > LOW)
    3. For equal priority, sort by created_at (oldest first)
    4. Return first goal (highest priority, oldest)

Optimization Techniques:
    - Delegate storage operations to GoalStorage (O(1) updates)
    - Use Python's built-in sort (Timsort, O(n log n))
    - Minimal memory allocation (single sort operation)

Author: Kiro AI
Date: 2024-01-15
Version: 1.0.0
"""

from typing import Optional

from .models import Goal, GoalStatus, Priority
from .goal_storage import GoalStorage
from .exceptions import StorageError


class PriorityManager:
    """
    Manages goal priorities and selection logic.
    
    Handles priority assignment, updates, and intelligent selection
    of the next goal for execution based on priority and age.
    
    Time Complexity:
        - update_priority: O(1) - single database update
        - select_next_goal: O(n log n) - sorting ready goals
    
    Space Complexity: O(n) where n is number of ready goals
    
    Example:
        >>> storage = GoalStorage("goals.db")
        >>> manager = PriorityManager(storage)
        >>> 
        >>> # Update priority
        >>> await manager.update_priority(goal_id, Priority.HIGH)
        >>> 
        >>> # Select next goal
        >>> next_goal = await manager.select_next_goal()
        >>> if next_goal:
        ...     print(f"Executing: {next_goal.description}")
    """
    
    def __init__(self, storage: GoalStorage):
        """
        Initialize with storage.
        
        Args:
            storage: GoalStorage instance for persistence
        """
        self.storage = storage
    
    async def update_priority(self, goal_id: str, priority: Priority) -> None:
        """
        Update goal priority with immediate persistence.
        
        Retrieves goal, updates priority field, and persists immediately.
        
        Time Complexity: O(1) - single get + single update
        Space Complexity: O(1) - single goal object
        
        Args:
            goal_id: Goal identifier
            priority: New priority level
            
        Raises:
            ValueError: If goal not found
            StorageError: If persistence fails
        """
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        
        goal.priority = priority
        await self.storage.update_goal(goal)
    
    async def select_next_goal(self) -> Optional[Goal]:
        """
        Select next goal for execution.
        
        Selection criteria (in order):
        1. Status must be READY
        2. Highest priority first (CRITICAL > HIGH > MEDIUM > LOW)
        3. Oldest goal (earliest created_at) for tie-breaking
        
        Time Complexity: O(n log n) where n is number of ready goals
        Space Complexity: O(n) for ready goals list
        
        Returns:
            Next goal to execute, or None if no ready goals
            
        Raises:
            StorageError: If query fails
        """
        ready_goals = await self.storage.query_goals(status=GoalStatus.READY)
        
        if not ready_goals:
            return None
        
        # Sort by priority (descending) then by created_at (ascending)
        # Priority order: CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3
        }
        
        sorted_goals = sorted(
            ready_goals,
            key=lambda g: (priority_order[g.priority], g.created_at)
        )
        
        return sorted_goals[0]
