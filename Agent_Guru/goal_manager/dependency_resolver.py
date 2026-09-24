"""Module: agent_guru.goal_manager.dependency_resolver
Purpose: Manages goal dependencies and execution readiness with cycle detection.

This module implements dependency management for the Goal Manager system,
ensuring goals execute in the correct order and detecting circular dependencies.

Performance Characteristics:
    - Time Complexity: O(V + E) for cycle detection (DFS)
    - Time Complexity: O(D) for readiness check where D is number of dependencies
    - Time Complexity: O(V + E) for blocking propagation
    - Space Complexity: O(V) for the colour map and explicit DFS stack
    - Correctness: Detects all cycles using depth-first search

Architecture:
    The dependency resolver uses:
    1. Iterative depth-first search (explicit stack) for cycle detection
    2. Three-colour marking to track the current path
    3. Colour map to avoid redundant checks
    4. Iterative propagation, over a prebuilt dependents index, for
       blocking dependent goals

Optimization Techniques:
    - Early termination on cycle detection
    - Colour marking to avoid redundant DFS traversals
    - A single goal read inverted into a dependents index, instead of one
      full-table scan per goal blocked
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
        - validate_dependencies: O(V + E) - iterative DFS traversal
        - is_ready: O(D) where D is number of dependencies
        - mark_blocked: O(V + E) - iterative propagation over a
          prebuilt dependents index

    Space Complexity: O(V) for the colour map and explicit DFS stack

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

        Uses an iterative depth-first search to detect circular
        dependencies. A cycle exists if we reach a goal that is already on
        the current path.

        Time Complexity: O(V + E) where V is goals, E is dependencies
        Space Complexity: O(V) for the colour map and explicit stack

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

    async def _dependencies_of(self, goal_id: str, override: dict) -> list[str] | None:
        """Return a goal's dependency ids, or None if the goal does not exist.

        `override` carries the in-flight dependency list for the node being
        validated, so validation runs against the deps about to be saved
        rather than whatever is currently persisted.
        """
        if goal_id in override:
            return list(override[goal_id])
        goal = await self.storage.get_goal(goal_id)
        if not goal:
            return None
        return list(goal.dependency_ids)

    async def _has_cycle(self, goal: Goal, override: dict) -> bool:
        """Check if goal has circular dependencies, iteratively.

        RECURSION FIX: this was a recursive DFS (`_has_cycle_util` calling
        itself once per edge). Dependency chains are user-authored data with
        no depth limit, so a chain of ~1000 goals exhausted Python's recursion
        limit and raised RecursionError -- which is NOT CircularDependencyError,
        so it escaped validate_dependencies() entirely instead of being
        reported as the invalid dependency graph it is. The traversal below is
        an explicit-stack DFS: identical semantics, bounded only by memory.

        Three-colour marking replaces the old visited/rec_stack pair and means
        exactly the same thing: WHITE = not yet reached, GREY = on the current
        path (a back-edge to GREY is a cycle), BLACK = fully explored.

        Time Complexity: O(V + E) -- each goal is expanded once.
        Space Complexity: O(V) for the colour map and the stack.

        Args:
            goal: Starting goal for cycle detection
            override: Dict mapping goal_id -> dependency_ids to use
                      instead of storage values (for in-flight updates)

        Returns:
            True if cycle detected, False otherwise

        """
        white, grey, black = 0, 1, 2
        colour: dict[str, int] = {}

        # Each frame is (goal_id, its dependency list or None if not yet
        # loaded, index of the next dependency to consider).
        stack: list[tuple[str, list[str] | None, int]] = [(goal.id, None, 0)]

        while stack:
            node, deps, index = stack.pop()

            if deps is None:
                if colour.get(node, white) != white:
                    continue
                colour[node] = grey
                deps = await self._dependencies_of(node, override)
                if deps is None:
                    # Goal doesn't exist: no cycle can run through it.
                    colour[node] = black
                    continue
                index = 0

            descended = False
            while index < len(deps):
                dep_id = deps[index]
                index += 1
                dep_colour = colour.get(dep_id, white)
                if dep_colour == grey:
                    # Back-edge into the current path: a cycle.
                    return True
                if dep_colour == white:
                    # Resume this frame after the child is fully explored.
                    stack.append((node, deps, index))
                    stack.append((dep_id, None, 0))
                    descended = True
                    break
                # black: already fully explored, cannot be part of a cycle
                # reachable from here.

            if not descended:
                colour[node] = black

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
        """Alias for is_ready - check if all dependencies are satisfied.

        Args:
            goal: Goal to check

        Returns:
            True if all dependencies are complete, False otherwise

        """
        return await self.is_ready(goal)

    async def mark_blocked(self, goal_id: str, _visited: set[str] | None = None) -> None:
        """Mark goal as blocked due to failed dependency.

        Propagates blocking to every transitively dependent goal.
        This ensures that if a goal fails, all goals depending on it
        are also marked as blocked.

        Time Complexity: O(V + E) with ONE full goal read, plus one
            get_goal/update_goal per goal actually blocked.
        Space Complexity: O(V + E) for the dependents index and worklist

        Args:
            goal_id: Goal to mark as blocked
            _visited: Internal - goal IDs already processed in this
                propagation, to avoid revisiting a goal reachable through
                multiple dependency paths. Callers should not pass this.

        """
        # BUG FIX: this used to recurse into every dependent goal with no
        # memoization at all. dependency_ids form a general DAG (a goal can
        # depend on several goals, and several goals can share a dependent),
        # not a tree, so a "diamond" shape -- e.g. D depends on both B and C,
        # which both depend on A -- caused D to be revisited and re-blocked
        # once per path into it. On a DAG with real fan-in/fan-out this is
        # not just wasted work: paths multiply combinatorially with depth, so
        # actual runtime could be exponential despite the O(V + E) claimed
        # above (which assumes each node is visited once, as a correct
        # implementation should). Worse, if a cycle ever ended up in storage
        # (e.g. via a race between two concurrent validate_dependencies()
        # calls each checking against a stale snapshot), this had no
        # recursion-stack guard at all and would recurse until RecursionError
        # instead of terminating. Tracking visited goal IDs fixes both: each
        # goal is blocked at most once, and a cycle can no longer cause
        # unbounded recursion.
        visited = _visited if _visited is not None else set()

        # N+1 FIX: the recursive form called storage.query_goals() -- an
        # unfiltered full-table read that opens its own connection -- ONCE PER
        # GOAL it blocked. Blocking a chain of k goals therefore performed k
        # full scans to answer the same question k times. The goal set is read
        # once here and inverted into a dependents index, which answers "who
        # depends on X" in O(1) for every step of the propagation.
        #
        # The index is used ONLY to find dependents. Each goal is still
        # re-read with get_goal() before being written, so a stale field from
        # this snapshot can never be written back over a concurrent update.
        all_goals = await self.storage.query_goals()
        dependents: dict[str, list[str]] = {}
        for other in all_goals:
            for dep_id in other.dependency_ids:
                dependents.setdefault(dep_id, []).append(other.id)

        # RECURSION FIX: an explicit worklist rather than recursion. The
        # visited set already stopped a cycle in storage from recursing
        # forever, but a long legitimate chain still hit Python's recursion
        # limit -- and RecursionError is not something a caller of
        # mark_blocked() can act on.
        pending: list[str] = [goal_id]
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)

            goal = await self.storage.get_goal(current)
            if not goal:
                continue

            goal.status = GoalStatus.BLOCKED
            await self.storage.update_goal(goal)

            pending.extend(dependents.get(current, ()))
