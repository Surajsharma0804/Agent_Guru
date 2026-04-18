"""
Loop Detector - Detects infinite loops in agent reasoning and delegation.

Tracks action patterns and delegation patterns using sliding windows.
Detects both identical-action loops and alternating-pattern loops.

Performance Characteristics:
    - Time Complexity: O(w) where w is pattern_window size
    - Space Complexity: O(n * w) where n is number of agents
    - Latency: <1ms per detection check

Validates: Requirements 11.3, 11.4, 11.5
"""

from __future__ import annotations

from collections import defaultdict, deque


class LoopDetector:
    """Detects infinite loops in agent action and delegation patterns.

    Two detection modes:
    - Action loops: an agent repeats the same action (or alternates A-B-A-B)
      within a sliding window.
    - Delegation loops: the same (from, to) delegation pair repeats for a
      given task type.

    Time Complexity: O(w) per detection where w is pattern_window
    Space Complexity: O(n * w) where n is number of agents

    Example:
        >>> detector = LoopDetector(pattern_window=6, repetition_threshold=3)
        >>> detector.record_action("agent_1", "search")
        >>> detector.record_action("agent_1", "search")
        >>> detector.record_action("agent_1", "search")
        >>> detector.detect_action_loop("agent_1")
        True

    Validates: Requirements 11.3, 11.4, 11.5
    """

    def __init__(
        self,
        pattern_window: int = 10,
        repetition_threshold: int = 3,
    ) -> None:
        """Initialise the loop detector.

        Args:
            pattern_window: Maximum number of recent actions to retain per agent.
            repetition_threshold: Number of repetitions that trigger loop detection.

        Raises:
            ValueError: If parameters are out of valid range.

        Validates: Requirements 11.3, 11.4
        """
        if pattern_window < 2:
            raise ValueError("pattern_window must be >= 2")
        if repetition_threshold < 2:
            raise ValueError("repetition_threshold must be >= 2")
        if repetition_threshold > pattern_window:
            raise ValueError("repetition_threshold must be <= pattern_window")

        self.pattern_window = pattern_window
        self.repetition_threshold = repetition_threshold
        # agent_id -> recent action deque (bounded by pattern_window)
        self._action_history: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=self.pattern_window))
        # task_type -> recent (from, to) delegation pairs
        self._delegation_history: dict[str, deque[tuple[str, str]]] = defaultdict(lambda: deque(maxlen=self.pattern_window))

    # ------------------------------------------------------------------
    # Action loop detection
    # ------------------------------------------------------------------

    def record_action(self, agent_id: str, action: str) -> None:
        """Record an action taken by an agent.

        Maintains a bounded sliding window of recent actions.

        Args:
            agent_id: Agent that performed the action.
            action: Action identifier string.

        Time Complexity: O(1) amortized
        Validates: Requirement 11.3
        """
        history = self._action_history[agent_id]
        history.append(action)
        # deque(maxlen=pattern_window) auto-evicts oldest — no manual pop needed

    def detect_action_loop(self, agent_id: str) -> bool:
        """Detect whether an agent is stuck in an action loop.

        Checks for:
        1. All recent actions identical (A-A-A-A).
        2. Alternating two-action pattern (A-B-A-B-A-B).

        Args:
            agent_id: Agent to check.

        Returns:
            True if a loop is detected.

        Time Complexity: O(w) where w is pattern_window
        Validates: Requirements 11.3, 11.4
        """
        history = self._action_history.get(agent_id)
        if history is None or len(history) < self.repetition_threshold:
            return False

        recent = list(history)[-self.repetition_threshold:]

        # Pattern 1: all identical
        if len(set(recent)) == 1:
            return True

        # Pattern 2: alternating A-B-A-B (requires at least 4 actions)
        if len(recent) >= 4:
            pattern = recent[:2]
            if all(recent[i] == pattern[i % 2] for i in range(len(recent))):
                return True

        return False

    def clear_action_history(self, agent_id: str) -> None:
        """Clear action history for an agent (e.g. after loop intervention).

        Args:
            agent_id: Agent whose history to clear.

        Time Complexity: O(1)
        Validates: Requirement 11.5
        """
        self._action_history.pop(agent_id, None)

    # ------------------------------------------------------------------
    # Delegation loop detection
    # ------------------------------------------------------------------

    def record_delegation(
        self,
        from_agent: str,
        to_agent: str,
        task_type: str,
    ) -> None:
        """Record a delegation event.

        Args:
            from_agent: Delegating agent.
            to_agent: Receiving agent.
            task_type: Type of task being delegated.

        Time Complexity: O(1) amortized
        Validates: Requirement 11.3
        """
        history = self._delegation_history[task_type]
        history.append((from_agent, to_agent))
        # deque(maxlen=pattern_window) auto-evicts oldest — no manual pop needed

    def detect_delegation_loop(self, task_type: str) -> bool:
        """Detect whether a task type has a delegation loop.

        Checks if the same (from, to) pair has been repeated at least
        ``repetition_threshold`` times in the recent window.

        Args:
            task_type: Task type to check.

        Returns:
            True if a delegation loop is detected.

        Time Complexity: O(w) where w is pattern_window
        Validates: Requirements 11.3, 11.4
        """
        history = self._delegation_history.get(task_type)
        if history is None or len(history) < self.repetition_threshold:
            return False

        recent = list(history)[-self.repetition_threshold:]

        # All recent delegations are the same pair
        if len(set(recent)) == 1:
            return True

        return False

    def clear_delegation_history(self, task_type: str) -> None:
        """Clear delegation history for a task type.

        Args:
            task_type: Task type whose history to clear.

        Time Complexity: O(1)
        Validates: Requirement 11.5
        """
        self._delegation_history.pop(task_type, None)
