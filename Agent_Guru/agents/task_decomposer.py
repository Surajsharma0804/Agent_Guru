"""Task Decomposer - Decomposes complex tasks into sub-tasks with dependencies.

Analyzes task complexity and breaks complex tasks into smaller, manageable
sub-tasks with clear dependencies and parallelization hints.

Performance Characteristics:
    - Time Complexity: O(n) where n is description length
    - Space Complexity: O(k) where k is number of sub-tasks
    - Latency: <1ms per decomposition decision

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent_lifecycle import Agent  # noqa: F401 – re-exported for convenience

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """A task to be executed by an agent.

    Attributes:
        id: Unique task identifier
        description: Human-readable task description
        task_type: Category of work (e.g. "implementation", "design")
        requirements: Key/value requirements for the task
        success_criteria: List of conditions that define success
        priority: Execution priority (higher = more urgent)
        dependencies: IDs of tasks that must complete before this one
        parent_task_id: ID of the parent task if this is a sub-task
        metadata: Arbitrary additional data

    """

    id: str
    description: str
    task_type: str
    requirements: dict[str, Any]
    success_criteria: list[str]
    priority: int
    dependencies: list[str]
    parent_task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubTask:
    """Intermediate representation of a sub-task before Task creation.

    Attributes:
        description: Human-readable description
        task_type: Category of work
        requirements: Inherited or derived requirements
        dependencies: Indices into the sibling sub-task list
        can_parallelize: Whether this sub-task can run in parallel

    """

    description: str
    task_type: str
    requirements: dict[str, Any]
    dependencies: list[int]
    can_parallelize: bool


# ---------------------------------------------------------------------------
# Complexity keywords
# ---------------------------------------------------------------------------

_COMPLEX_TASK_TYPES = frozenset({"system_design", "architecture", "integration"})

_MULTI_STEP_KEYWORDS = frozenset(
    {
        "and",
        "then",
        "after",
        "before",
        "also",
        "additionally",
        "furthermore",
        "finally",
        "first",
        "second",
        "third",
        "next",
        "lastly",
    },
)

# Decomposition templates keyed by task_type
_DECOMPOSITION_TEMPLATES: dict[str, list[SubTask]] = {
    "implementation": [
        SubTask(
            description="Design",
            task_type="design",
            requirements={},
            dependencies=[],
            can_parallelize=False,
        ),
        SubTask(
            description="Implement",
            task_type="coding",
            requirements={},
            dependencies=[0],
            can_parallelize=False,
        ),
        SubTask(
            description="Test",
            task_type="testing",
            requirements={},
            dependencies=[1],
            can_parallelize=False,
        ),
    ],
    "system_design": [
        SubTask(
            description="Requirements analysis",
            task_type="analysis",
            requirements={},
            dependencies=[],
            can_parallelize=False,
        ),
        SubTask(
            description="High-level design",
            task_type="design",
            requirements={},
            dependencies=[0],
            can_parallelize=False,
        ),
        SubTask(
            description="Component specification",
            task_type="specification",
            requirements={},
            dependencies=[1],
            can_parallelize=True,
        ),
    ],
    "integration": [
        SubTask(
            description="Interface definition",
            task_type="specification",
            requirements={},
            dependencies=[],
            can_parallelize=False,
        ),
        SubTask(
            description="Integration implementation",
            task_type="coding",
            requirements={},
            dependencies=[0],
            can_parallelize=False,
        ),
        SubTask(
            description="Integration testing",
            task_type="testing",
            requirements={},
            dependencies=[1],
            can_parallelize=False,
        ),
    ],
}


# ---------------------------------------------------------------------------
# TaskDecomposer
# ---------------------------------------------------------------------------


class TaskDecomposer:
    """Decomposes complex tasks into sub-tasks with dependency tracking.

    Uses rule-based complexity analysis to decide whether a task should be
    broken down, then applies type-specific templates (or a generic fallback)
    to produce an ordered list of sub-tasks.

    Constraints enforced:
    - Decomposition depth is bounded by ``max_decomposition_depth``
    - Sub-task count is bounded by ``[min_subtask_count, max_subtask_count]``
    - Tasks below the complexity threshold are returned as-is

    Time Complexity: O(n) where n is description word count
    Space Complexity: O(k) where k is number of sub-tasks produced

    Example:
        >>> decomposer = TaskDecomposer()
        >>> task = Task(
        ...     id="t1",
        ...     description="Design and implement and test the payment module",
        ...     task_type="implementation",
        ...     requirements={"module": "payment", "currency": "USD", "gateway": "stripe",
        ...                   "retry": True, "logging": True, "monitoring": True},
        ...     success_criteria=["all tests pass", "latency < 200ms", "coverage > 80%",
        ...                       "no security issues", "docs complete", "reviewed"],
        ...     priority=1,
        ...     dependencies=[],
        ... )
        >>> subtasks = await decomposer.decompose(task)
        >>> print(len(subtasks))  # 3

    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5

    """

    def __init__(
        self,
        max_decomposition_depth: int = 3,
        min_subtask_count: int = 2,
        max_subtask_count: int = 7,
        complexity_threshold: float = 0.6,
    ) -> None:
        """Initialise the decomposer.

        Args:
            max_decomposition_depth: Maximum recursion depth for decomposition.
            min_subtask_count: Minimum number of sub-tasks required to decompose.
            max_subtask_count: Maximum number of sub-tasks to produce.
            complexity_threshold: Complexity score above which decomposition occurs.

        Raises:
            ValueError: If any parameter is out of valid range.

        Validates: Requirements 6.4, 6.5

        """
        if max_decomposition_depth < 1:
            msg = "max_decomposition_depth must be >= 1"
            raise ValueError(msg)
        if min_subtask_count < 2:  # noqa: PLR2004 - Small integer threshold

            msg = "min_subtask_count must be >= 2"
            raise ValueError(msg)
        if max_subtask_count < min_subtask_count:
            msg = "max_subtask_count must be >= min_subtask_count"
            raise ValueError(msg)
        if not 0.0 <= complexity_threshold <= 1.0:
            msg = "complexity_threshold must be in [0.0, 1.0]"
            raise ValueError(msg)

        self.max_depth = max_decomposition_depth
        self.min_subtasks = min_subtask_count
        self.max_subtasks = max_subtask_count
        self.complexity_threshold = complexity_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def should_decompose(self, task: Task) -> bool:
        """Decide whether a task is complex enough to decompose.

        Args:
            task: Task to evaluate.

        Returns:
            True if the complexity score exceeds the threshold.

        Time Complexity: O(n) where n is description word count
        Validates: Requirement 6.1

        """
        return self._calculate_complexity(task) > self.complexity_threshold

    async def decompose(
        self,
        task: Task,
        current_depth: int = 0,
    ) -> list[Task]:
        """Decompose a task into an ordered list of sub-tasks.

        If the task does not need decomposition, or the depth limit is
        reached, the original task is returned as a single-element list.

        Args:
            task: Task to decompose.
            current_depth: Current recursion depth (used internally).

        Returns:
            List of Task objects.  Sub-tasks carry ``parent_task_id`` and
            ``dependencies`` referencing sibling sub-task IDs.

        Time Complexity: O(k) where k is number of sub-tasks
        Validates: Requirements 6.2, 6.3, 6.4, 6.5

        """
        # Depth limit – return as-is
        if current_depth >= self.max_depth:
            return [task]

        if not await self.should_decompose(task):
            return [task]

        raw_subtasks = await self._identify_subtasks(task)

        # Enforce min/max bounds
        if len(raw_subtasks) < self.min_subtasks:
            return [task]

        raw_subtasks = raw_subtasks[: self.max_subtasks]

        # Assign stable IDs so dependencies can reference them
        sub_ids = [f"{task.id}_sub_{i}" for i in range(len(raw_subtasks))]

        task_objects: list[Task] = []
        for i, sub in enumerate(raw_subtasks):
            resolved_deps = [sub_ids[dep_idx] for dep_idx in sub.dependencies]
            task_objects.append(
                Task(
                    id=sub_ids[i],
                    description=f"{sub.description}: {task.description}",
                    task_type=sub.task_type,
                    requirements=task.requirements.copy(),
                    success_criteria=[],
                    priority=task.priority,
                    dependencies=resolved_deps,
                    parent_task_id=task.id,
                    metadata={
                        "parent_task": task.id,
                        "can_parallelize": sub.can_parallelize,
                    },
                ),
            )

        return task_objects

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_complexity(self, task: Task) -> float:
        """Calculate a complexity score in [0.0, 1.0].

        Scoring factors:
        - Description word count (>50 words → +0.3, >20 → +0.2)
        - Number of requirements (>5 → +0.3, >3 → +0.2)
        - Number of success criteria (>5 → +0.2, >3 → +0.1)
        - Task type is in the complex-types set (+0.2)
        - Description contains multi-step keywords (+0.1 per keyword, capped at +0.2)

        Returns:
            Complexity score clamped to [0.0, 1.0].

        Time Complexity: O(n) where n is description word count
        Validates: Requirement 6.1

        """
        score = 0.0

        # Factor 1: description length
        words = task.description.lower().split()
        if len(words) > 50:  # noqa: PLR2004 - Threshold

            score += 0.3
        elif len(words) > 20:  # noqa: PLR2004 - Threshold

            score += 0.2

        # Factor 2: number of requirements
        req_count = len(task.requirements)
        if req_count > 5:  # noqa: PLR2004 - Small integer threshold

            score += 0.3
        elif req_count > 3:  # noqa: PLR2004 - Small integer threshold

            score += 0.2

        # Factor 3: number of success criteria
        criteria_count = len(task.success_criteria)
        if criteria_count > 5:  # noqa: PLR2004 - Small integer threshold

            score += 0.2
        elif criteria_count > 3:  # noqa: PLR2004 - Small integer threshold

            score += 0.1

        # Factor 4: complex task type
        if task.task_type in _COMPLEX_TASK_TYPES:
            score += 0.2

        # Factor 5: multi-step keywords in description
        keyword_hits = sum(1 for w in words if w in _MULTI_STEP_KEYWORDS)
        score += min(keyword_hits * 0.1, 0.2)

        return min(score, 1.0)

    async def _identify_subtasks(self, task: Task) -> list[SubTask]:
        """Identify sub-tasks for a given task.

        Uses a template lookup for known task types, falling back to a
        generic three-step (analyse → execute → verify) decomposition.

        Args:
            task: Task to decompose.

        Returns:
            List of SubTask objects (may be empty).

        Time Complexity: O(1) – template lookup
        Validates: Requirements 6.2, 6.3

        """
        template = _DECOMPOSITION_TEMPLATES.get(task.task_type)
        if template:
            # Return fresh copies so callers cannot mutate the template
            return [
                SubTask(
                    description=sub.description,
                    task_type=sub.task_type,
                    requirements=task.requirements.copy(),
                    dependencies=list(sub.dependencies),
                    can_parallelize=sub.can_parallelize,
                )
                for sub in template
            ]

        # Generic fallback: analyse → execute → verify
        return [
            SubTask(
                description="Analyse",
                task_type="analysis",
                requirements=task.requirements.copy(),
                dependencies=[],
                can_parallelize=False,
            ),
            SubTask(
                description="Execute",
                task_type=task.task_type,
                requirements=task.requirements.copy(),
                dependencies=[0],
                can_parallelize=False,
            ),
            SubTask(
                description="Verify",
                task_type="verification",
                requirements=task.requirements.copy(),
                dependencies=[1],
                can_parallelize=False,
            ),
        ]
