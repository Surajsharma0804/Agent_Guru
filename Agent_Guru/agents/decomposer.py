"""
Command Decomposer - Parses voice commands into structured sub-tasks.

Transforms natural language voice commands (e.g. "open YouTube and play music")
into ordered lists of atomic SubTask objects with dependency analysis.

Performance Characteristics:
    - Time Complexity: O(n) where n is command token count
    - Space Complexity: O(k) where k is number of sub-tasks produced
    - Latency: <5ms per decomposition

Validates: Requirements 1 (Agent Registration), 2 (Task Decomposition)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .task_decomposer import Task

# ---------------------------------------------------------------------------
# Voice command patterns
# ---------------------------------------------------------------------------

# Conjunctions / sequencing words that split a command into multiple steps
_SPLIT_PATTERNS: list[str] = [
    r"\band\s+then\b",
    r"\bthen\b",
    r"\bafter\s+that\b",
    r"\bafterwards\b",
    r"\bnext\b",
    r"\bfollowed\s+by\b",
    r"\band\b",
    r"\balso\b",
    r"\bfinally\b",
]

# Compiled single regex that splits on any of the above
_SPLIT_RE = re.compile(
    "|".join(_SPLIT_PATTERNS),
    re.IGNORECASE,
)

# Mapping from action verb → task_type
_VERB_TO_TASK_TYPE: dict[str, str] = {
    # Browser / navigation
    "open": "navigation",
    "launch": "navigation",
    "start": "navigation",
    "go": "navigation",
    "navigate": "navigation",
    "visit": "navigation",
    # Media
    "play": "media_control",
    "pause": "media_control",
    "stop": "media_control",
    "resume": "media_control",
    "skip": "media_control",
    "mute": "media_control",
    "unmute": "media_control",
    "volume": "media_control",
    # Messaging / communication
    "send": "communication",
    "message": "communication",
    "email": "communication",
    "call": "communication",
    "text": "communication",
    "reply": "communication",
    # Search
    "search": "search",
    "find": "search",
    "look": "search",
    "google": "search",
    # File / document
    "create": "file_operation",
    "write": "file_operation",
    "save": "file_operation",
    "delete": "file_operation",
    "rename": "file_operation",
    "move": "file_operation",
    "copy": "file_operation",
    # System
    "set": "system_control",
    "turn": "system_control",
    "enable": "system_control",
    "disable": "system_control",
    "restart": "system_control",
    "shutdown": "system_control",
    "screenshot": "system_control",
    "capture": "system_control",
    # Reminder / calendar
    "remind": "reminder",
    "schedule": "reminder",
    "add": "reminder",
    "cancel": "reminder",
}

# Capabilities required per task_type
_TASK_TYPE_CAPABILITIES: dict[str, list[str]] = {
    "navigation": ["platform_control", "browser_control"],
    "media_control": ["platform_control", "media_control"],
    "communication": ["platform_control", "messaging"],
    "search": ["browser_control", "search"],
    "file_operation": ["platform_control", "file_system"],
    "system_control": ["platform_control"],
    "reminder": ["platform_control", "calendar"],
    "generic": ["platform_control"],
}

# Dependency rules: task_type → list of task_types it depends on
# (i.e. these must complete before the current step)
_DEPENDENCY_RULES: dict[str, list[str]] = {
    "media_control": ["navigation"],   # must open app before controlling media
    "search": ["navigation"],          # must open browser before searching
    "file_operation": ["navigation"],  # may need app open first
    "communication": ["navigation"],   # may need app open first
}


# ---------------------------------------------------------------------------
# ParsedStep – intermediate representation
# ---------------------------------------------------------------------------


@dataclass
class ParsedStep:
    """A single atomic step parsed from a voice command.

    Attributes:
        raw_text: The original text fragment for this step.
        action_verb: The leading action verb (lower-cased), if detected.
        task_type: Inferred task type based on action_verb.
        target: The object/target of the action (remainder after verb).
        capabilities: Required capabilities for this step.
    """

    raw_text: str
    action_verb: str
    task_type: str
    target: str
    capabilities: list[str]


# ---------------------------------------------------------------------------
# CommandDecomposer
# ---------------------------------------------------------------------------


class CommandDecomposer:
    """Parses natural language voice commands into ordered, dependency-aware sub-tasks.

    The decomposer:
    1. Strips wake-word prefixes ("Hey Guru", "Hey Maya").
    2. Splits the command on conjunctions / sequencing words.
    3. Identifies the action verb and infers task_type for each step.
    4. Builds dependency edges between steps based on semantic rules.
    5. Returns a list of :class:`~Agent_Guru.agents.task_decomposer.Task` objects
       with ``dependencies`` referencing sibling task IDs.

    Time Complexity: O(n) where n is command token count
    Space Complexity: O(k) where k is number of sub-tasks

    Example:
        >>> decomposer = CommandDecomposer()
        >>> tasks = await decomposer.decompose("open YouTube and play music")
        >>> for t in tasks:
        ...     print(t.task_type, t.dependencies)
        navigation []
        media_control ['<id_of_navigation_task>']

    Validates: Requirements 1 (Agent Registration), 2 (Task Decomposition)
    """

    # Wake-word prefixes to strip before parsing
    _WAKE_WORD_RE = re.compile(
        r"^(hey\s+guru|hey\s+maya|ok\s+guru|ok\s+maya|guru|maya)[,\s]+",
        re.IGNORECASE,
    )

    def __init__(
        self,
        max_steps: int = 10,
        default_priority: int = 100,
    ) -> None:
        """Initialise the command decomposer.

        Args:
            max_steps: Maximum number of atomic steps to produce (excess is dropped).
            default_priority: Default task priority assigned to each sub-task.

        Raises:
            ValueError: If max_steps < 1 or default_priority < 0.
        """
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if default_priority < 0:
            raise ValueError("default_priority must be >= 0")

        self.max_steps = max_steps
        self.default_priority = default_priority

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def decompose(
        self,
        command: str,
        parent_task_id: Optional[str] = None,
        base_requirements: Optional[dict[str, object]] = None,
    ) -> list[Task]:
        """Decompose a voice command into an ordered list of atomic Tasks.

        Args:
            command: Raw voice command string (may include wake-word prefix).
            parent_task_id: Optional ID of the parent task for audit linkage.
            base_requirements: Optional requirements dict to merge into each sub-task.

        Returns:
            Ordered list of :class:`Task` objects.  Each task's ``dependencies``
            field contains the IDs of tasks that must complete before it.
            Returns a single generic task when the command cannot be split.

        Time Complexity: O(n) where n is command token count
        Validates: Requirements 2.1, 2.6
        """
        if not command or not command.strip():
            return []

        cleaned = self._strip_wake_word(command.strip())
        steps = self._split_into_steps(cleaned)
        steps = steps[: self.max_steps]

        parsed = [self._parse_step(s) for s in steps]
        return self._build_tasks(parsed, parent_task_id, base_requirements or {})

    async def parse_command(self, command: str) -> list[ParsedStep]:
        """Parse a voice command into intermediate ParsedStep objects.

        Useful for inspection / debugging without building full Task objects.

        Args:
            command: Raw voice command string.

        Returns:
            List of :class:`ParsedStep` objects.

        Time Complexity: O(n)
        Validates: Requirements 2.1
        """
        if not command or not command.strip():
            return []

        cleaned = self._strip_wake_word(command.strip())
        steps = self._split_into_steps(cleaned)
        steps = steps[: self.max_steps]
        return [self._parse_step(s) for s in steps]

    async def analyze_dependencies(
        self, tasks: list[Task]
    ) -> dict[str, list[str]]:
        """Return a dependency map for a list of tasks.

        Args:
            tasks: List of Task objects (typically from :meth:`decompose`).

        Returns:
            Dict mapping each task ID to its list of dependency IDs.

        Time Complexity: O(k) where k is number of tasks
        Validates: Requirements 2.6
        """
        return {t.id: list(t.dependencies) for t in tasks}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _strip_wake_word(self, command: str) -> str:
        """Remove wake-word prefix from command.

        Args:
            command: Raw command string.

        Returns:
            Command with wake-word prefix removed.

        Time Complexity: O(n)
        """
        return self._WAKE_WORD_RE.sub("", command).strip()

    def _split_into_steps(self, command: str) -> list[str]:
        """Split a command string into atomic step fragments.

        Splits on conjunctions / sequencing words, then strips whitespace
        and drops empty fragments.

        Args:
            command: Cleaned command string (wake-word already removed).

        Returns:
            Non-empty list of step strings.

        Time Complexity: O(n)
        """
        parts = _SPLIT_RE.split(command)
        steps = [p.strip() for p in parts if p and p.strip()]
        return steps if steps else [command.strip()]

    def _parse_step(self, step_text: str) -> ParsedStep:
        """Parse a single step fragment into a :class:`ParsedStep`.

        Extracts the leading action verb, infers task_type, and identifies
        the target (remainder of the step after the verb).

        Args:
            step_text: A single atomic step string.

        Returns:
            :class:`ParsedStep` with all fields populated.

        Time Complexity: O(v) where v is vocabulary size (constant)
        """
        tokens = step_text.lower().split()
        action_verb, task_type = self._identify_verb(tokens)
        target = self._extract_target(step_text, action_verb)
        capabilities = _TASK_TYPE_CAPABILITIES.get(task_type, ["platform_control"])

        return ParsedStep(
            raw_text=step_text,
            action_verb=action_verb,
            task_type=task_type,
            target=target,
            capabilities=list(capabilities),
        )

    def _identify_verb(self, tokens: list[str]) -> tuple[str, str]:
        """Identify the action verb and corresponding task_type from tokens.

        Checks the first two tokens for a known verb.

        Args:
            tokens: Lower-cased word tokens from a step fragment.

        Returns:
            Tuple of (action_verb, task_type).  Falls back to ("", "generic").

        Time Complexity: O(1) – dict lookup
        """
        for token in tokens[:2]:
            # Strip trailing punctuation
            clean = token.rstrip(".,!?")
            if clean in _VERB_TO_TASK_TYPE:
                return clean, _VERB_TO_TASK_TYPE[clean]
        return "", "generic"

    def _extract_target(self, step_text: str, action_verb: str) -> str:
        """Extract the target/object from a step fragment.

        Removes the leading action verb (case-insensitive) and returns
        the remainder as the target string.

        Args:
            step_text: Original step text (mixed case).
            action_verb: The identified action verb (lower-cased).

        Returns:
            Target string, stripped of leading/trailing whitespace.

        Time Complexity: O(n)
        """
        if not action_verb:
            return step_text.strip()

        pattern = re.compile(r"^\s*" + re.escape(action_verb) + r"\s*", re.IGNORECASE)
        return pattern.sub("", step_text).strip()

    def _build_tasks(
        self,
        parsed_steps: list[ParsedStep],
        parent_task_id: Optional[str],
        base_requirements: dict[str, object],
    ) -> list[Task]:
        """Convert ParsedStep objects into Task objects with dependency edges.

        Dependency rules (from ``_DEPENDENCY_RULES``):
        - A step of type T depends on the *most recent preceding* step whose
          task_type is listed in ``_DEPENDENCY_RULES[T]``.

        Args:
            parsed_steps: Ordered list of parsed steps.
            parent_task_id: Optional parent task ID.
            base_requirements: Base requirements dict merged into each task.

        Returns:
            Ordered list of :class:`Task` objects.

        Time Complexity: O(k²) worst case, O(k) typical
        """
        import uuid

        # Assign stable IDs up-front so dependencies can reference them
        step_ids = [str(uuid.uuid4()) for _ in parsed_steps]

        tasks: list[Task] = []
        # Track the most recent task ID for each task_type
        latest_by_type: dict[str, str] = {}

        for i, (step, step_id) in enumerate(zip(parsed_steps, step_ids)):
            # Determine dependencies for this step
            dep_ids: list[str] = []
            required_predecessors = _DEPENDENCY_RULES.get(step.task_type, [])
            for pred_type in required_predecessors:
                if pred_type in latest_by_type:
                    dep_id = latest_by_type[pred_type]
                    if dep_id not in dep_ids:
                        dep_ids.append(dep_id)

            # Build requirements dict
            requirements: dict[str, object] = dict(base_requirements)
            requirements["capabilities"] = step.capabilities
            requirements["target"] = step.target

            metadata: dict[str, str] = {
                "step_index": str(i),
                "can_parallelize": str(len(dep_ids) == 0),
            }

            task = Task(
                id=step_id,
                description=step.raw_text,
                task_type=step.task_type,
                requirements=requirements,
                success_criteria=[f"Complete: {step.raw_text}"],
                priority=self.default_priority,
                dependencies=dep_ids,
                parent_task_id=parent_task_id,
                metadata=metadata,
            )

            tasks.append(task)
            latest_by_type[step.task_type] = step_id

        return tasks
