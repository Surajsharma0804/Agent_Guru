"""Suppression manager for proactive notifications."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict


SUPPRESSION_COOLDOWN_S = 86400  # 24 hours
DISMISSAL_THRESHOLD = 3


class SuppressionManager:
    """Tracks dismissals and enforces suppression after repeated dismissals."""

    def __init__(
        self,
        dismissal_threshold: int = DISMISSAL_THRESHOLD,
        cooldown_s: float = SUPPRESSION_COOLDOWN_S,
    ) -> None:
        self.dismissal_threshold = dismissal_threshold
        self.cooldown_s = cooldown_s
        self._dismissals: Dict[str, int] = defaultdict(int)
        self._suppressed_until: Dict[str, float] = {}

    def record_dismissal(self, suggestion_type: str) -> None:
        """Record a dismissal for a suggestion type."""
        self._dismissals[suggestion_type] += 1
        if self._dismissals[suggestion_type] >= self.dismissal_threshold:
            self._suppressed_until[suggestion_type] = time.time() + self.cooldown_s
            self._dismissals[suggestion_type] = 0

    def record_acceptance(self, suggestion_type: str) -> None:
        """Reset dismissal count on acceptance."""
        self._dismissals[suggestion_type] = 0
        self._suppressed_until.pop(suggestion_type, None)

    def is_suppressed(self, suggestion_type: str) -> bool:
        """Check if a suggestion type is currently suppressed."""
        until = self._suppressed_until.get(suggestion_type)
        if until is None:
            return False
        if time.time() >= until:
            del self._suppressed_until[suggestion_type]
            return False
        return True

    def dismissal_count(self, suggestion_type: str) -> int:
        return self._dismissals[suggestion_type]
