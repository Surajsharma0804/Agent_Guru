"""Module: agent_guru.goal_manager.dependency_resolver
Purpose: Manages goal dependencies and execution readiness with cycle detection.

This module implements dependency management for the Goal Manager system,
ensuring goals execute in the correct order and detecting circular dependencies.

Performance Characteristics:
    - Time Complexity: O(V + E) for cycle detection (DFS)
    - Time Complexity: O(D) for readiness check where D is number of dependencies
    - Time Complexity: O(V + E) for blocking propagation
    - Space Complexity: O(V) for visited/recursion stack in DFS
    - Correctness: Detects all cycles using depth-first search

Architecture:
    The dependency resolver uses:
    1. Depth-first search (DFS) for cycle detection
    2. Recursion stack to track current path
    3. Visited set to avoid redundant checks
    4. Recursive propagation for blocking dependent goals

Optimization Techniques:
    - Early termination on cycle detection
    - Visited set to avoid redundant DFS traversals
    - Direct status checks for readiness (no graph traversal)

Author: Kiro AI
Date: 2024-01-15
Version: 1.0.0
"""

from .exceptions import CircularDependencyError
from .goal_storage import GoalStorage
from .models import Goal, GoalStatus


class DependencyResolver:
    """Manages goal dependencies and execution readiness.

    Detects cycles using depth-first search and determines when goals
    are ready for execution based on dependency satisfaction.

    Time Complexity:
        - validate_dependencies: O(V + E) - DFS traversal
        - is_ready: O(D) where D is number of dependencies
        - mark_blocked: O(V + E) - recursive propagation

    Space Complexity: O(V) for DFS visited/recursion stack

    Example:
        >>> resolver = DependencyResolver(storage)
        >>> goal_a = Goal(description="Goal A")
        >>> goal_b = Goal(description="Goal B", dependency_ids=[goal_a.id])
        >>> resolver.validate_dependencies(goal_b)  # OK
        >>> goal_a.dependency_ids = [goal_b.id]
        >>> resolver.validate_dependencies(goal_a)  # Raises ValidationError

    """

    def __init__(self, storage: GoalStorage) -> None:
        """Initialize with storage.

        Args:
            storage: GoalStorage instance for querying goals

        """
        self.storage = storage

    async def validate_dependencies(self, goal: Goal) -> None:
        """Validate goal dependencies don't form cycles.

        Uses depth-first search to detect circular dependencies.
        A cycle exists if we encounter a goal that's already in the
        current recursion stack.

        Time Complexity: O(V + E) where V is goals, E is dependencies
        Space Complexity: O(V) for visited and recursion stack

        Args:
            goal: Goal to validate (uses goal.dependency_ids as the
                  authoritative deps for this node, overriding storage)

        Raises:
            ValidationError: If circular dependencies detected

        """
        # Pass the goal's current dependency_ids as an override so that
        # the DFS uses the *new* deps for the starting node rather than
        # whatever is currently persisted in storage.
        override: dict = {goal.id: goal.dependency_ids}
        if await self._has_cycle(goal, override):
            msg = f"Circular dependency detected for goal {goal.id}"
            raise CircularDependencyError(msg)

    async def _has_cycle(self, goal: Goal, override: dict) -> bool:
        """Check if goal has circular dependencies using DFS.

        Performs depth-first search starting from the goal,
        tracking visited nodes and the current recursion stack.

        Time Complexity: O(V + E) - visits each goal once
        Space Complexity: O(V) - visited and recursion stack

        Args:
            goal: Starting goal for cycle detection
            override: Dict mapping goal_id -> dependency_ids to use
                      instead of storage values (for in-flight updates)

        Returns:
            True if cycle detected, False otherwise

        """
        visited: set[str] = set()
        rec_stack: set[str] = set()

        return await self._has_cycle_util(goal.id, visited, rec_stack, override)

    async def _has_cycle_util(
        self,
        goal_id: str,
        visited: set[str],
        rec_stack: set[str],
        override: dict,
    ) -> bool:
        """DFS utility for cycle detection.

        Recursive helper that performs depth-first search with
        recursion stack tracking. A cycle exists if we encounter
        a goal that's already in the current recursion stack.

        Algorithm:
        1. Mark current goal as visited and add to recursion stack
        2. For each dependency:
           a. If not visited, recursively check for cycles
           b. If in recursion stack, cycle detected
        3. Remove from recursion stack before returning

        Time Complexity: O(V + E) - visits each goal once
        Space Complexity: O(V) - recursion depth + sets

        Args:
            goal_id: Current goal ID
            visited: Set of visited goal IDs
            rec_stack: Set of goal IDs in current recursion path
            override: Dict mapping goal_id -> dependency_ids to use
                      instead of storage (for the node being validated)

        Returns:
            True if cycle detected, False otherwise

        """
        # Mark as visited and add to recursion stack
        visited.add(goal_id)
        rec_stack.add(goal_id)

        # Use override deps if provided, otherwise fetch from storage
        if goal_id in override:
            dep_ids = override[goal_id]
        else:
            goal = await self.storage.get_goal(goal_id)
            if not goal:
                # Goal doesn't exist, no cycle from this path
                rec_stack.remove(goal_id)
                return False
            dep_ids = goal.dependency_ids

        # Check all dependencies
        for dep_id in dep_ids:
            if dep_id not in visited:
                # Recursively check unvisited dependency
                if await self._has_cycle_util(dep_id, visited, rec_stack, override):
                    return True
            elif dep_id in rec_stack:
                # Dependency is in current path - cycle detected!
                return True

        # Remove from recursion stack before returning
        rec_stack.remove(goal_id)
        return False

    async def is_ready(self, goal: Goal) -> bool:
        """Check if goal is ready for execution.

        A goal is ready if all its dependencies are complete.
        Goals with no dependencies are always ready.

        Time Complexity: O(D) where D is number of dependencies
        Space Complexity: O(1) - no additional memory

        Args:
            goal: Goal to check

        Returns:
            True if ready for execution, False otherwise

        """
        # No dependencies means ready
        if not goal.dependency_ids:
            return True

        # Check all dependencies are complete
        for dep_id in goal.dependency_ids:
            dep = await self.storage.get_goal(dep_id)
            if not dep or dep.status != GoalStatus.COMPLETE:
                return False

        return True

    async def check_dependencies(self, goal: Goal) -> bool:
        """Alias for is_ready — check if all dependencies are satisfied.

        Args:
            goal: Goal to check

        Returns:
            True if all dependencies are complete, False otherwise

        """
        return await self.is_ready(goal)

    async def mark_blocked(self, goal_id: str) -> None:
        """Mark goal as blocked due to failed dependency.

        Recursively propagates blocking to all dependent goals.
        This ensures that if a goal fails, all goals depending on it
        are also marked as blocked.

        Time Complexity: O(V + E) - visits all dependent goals
        Space Complexity: O(V) - recursion depth

        Args:
            goal_id: Goal to mark as blocked

        """
        # Get goal
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            return

        # Mark as blocked
        goal.status = GoalStatus.BLOCKED
        await self.storage.update_goal(goal)

        # Recursively block dependent goals
        all_goals = await self.storage.query_goals()
        for g in all_goals:
            if goal_id in g.dependency_ids:
                await self.mark_blocked(g.id)
