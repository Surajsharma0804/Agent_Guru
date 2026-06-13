"""Loop Detector for the Verifier System.

Detects infinite loops in agent reasoning by tracking state hashes
and execution traces.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, deque
from typing import Any

from Agent_Guru.verifier.models import LoopDetectionResult


class LoopDetector:
    """Detects infinite loops via state hashing and trace analysis.

    Maintains a sliding window of state hashes. When the same state
    appears more than `threshold` times, a loop is detected.
    """

    def __init__(self, threshold: int = 3, window_size: int = 50) -> None:
        self._threshold = threshold
        self._window_size = window_size
        # Per-session state tracking: session_id -> deque of state hashes (bounded)
        self._traces: dict[str, deque[str]] = {}

    def record_state(self, session_id: str, state: Any) -> LoopDetectionResult:
        """Record a new state and check for loops.

        Args:
            session_id: Unique identifier for the agent session
            state: Current state (will be hashed)

        Returns:
            LoopDetectionResult — loop_detected=True if threshold exceeded

        """
        state_hash = self._hash_state(state)

        if session_id not in self._traces:
            self._traces[session_id] = deque(maxlen=self._window_size)

        trace = self._traces[session_id]
        trace.append(state_hash)
        # deque(maxlen=window_size) auto-evicts oldest — no manual pop needed

        # Count occurrences
        counts = Counter(trace)
        max_count = counts.most_common(1)[0][1] if counts else 0
        repeated_hash = counts.most_common(1)[0][0] if counts else ""

        loop_detected = max_count >= self._threshold

        # Extract loop pattern (the repeated state hash prefix)
        pattern = repeated_hash[:16] if loop_detected else ""

        return LoopDetectionResult(
            loop_detected=loop_detected,
            repetition_count=max_count,
            loop_pattern=pattern,
            trace_length=len(trace),
            details=(
                f"State '{pattern}' repeated {max_count} times (threshold: {self._threshold})"
                if loop_detected
                else f"No loop detected (max repetitions: {max_count})"
            ),
        )

    def check_sequence(
        self,
        states: list[Any],
        threshold: int | None = None,
    ) -> LoopDetectionResult:
        """Check a sequence of states for loops without storing.

        Args:
            states: List of states to analyze
            threshold: Override default threshold

        Returns:
            LoopDetectionResult

        """
        t = threshold if threshold is not None else self._threshold
        hashes = [self._hash_state(s) for s in states]
        counts = Counter(hashes)
        max_count = counts.most_common(1)[0][1] if counts else 0
        repeated_hash = counts.most_common(1)[0][0] if counts else ""

        loop_detected = max_count >= t
        pattern = repeated_hash[:16] if loop_detected else ""

        return LoopDetectionResult(
            loop_detected=loop_detected,
            repetition_count=max_count,
            loop_pattern=pattern,
            trace_length=len(states),
            details=(
                f"Loop pattern '{pattern}' repeated {max_count} times"
                if loop_detected
                else f"No loop (max repetitions: {max_count})"
            ),
        )

    def reset_session(self, session_id: str) -> None:
        """Clear trace for a session."""
        self._traces.pop(session_id, None)

    def get_trace(self, session_id: str) -> list[str]:
        """Get the state hash trace for a session."""
        return list(self._traces.get(session_id, []))

    @staticmethod
    def _hash_state(state: Any) -> str:
        """Compute a deterministic hash of a state."""
        try:
            if isinstance(state, str):
                serialized = state
            elif isinstance(state, (dict, list)):
                serialized = json.dumps(state, sort_keys=True, default=str)
            else:
                serialized = str(state)
        except Exception:
            serialized = repr(state)

        return hashlib.sha256(serialized.encode()).hexdigest()
