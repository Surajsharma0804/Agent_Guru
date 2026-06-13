"""Activity classifier for ambient context."""

from __future__ import annotations

from typing import Any, ClassVar


class ActivityClassifier:
    """Lightweight activity classifier using sensors, calendar, and time patterns."""

    ACTIVITIES: ClassVar[list[str]] = [
        "working",
        "commuting",
        "exercising",
        "sleeping",
        "meeting",
        "idle",
    ]

    def classify(self, signals: dict[str, Any]) -> tuple[str, float]:
        """Classify current activity. Returns (activity, confidence)."""
        # Stub: simple heuristic classifier
        hour = signals.get("hour", 12)
        motion = signals.get("motion_level", 0.0)
        calendar_event = signals.get("calendar_event")

        if calendar_event:
            return "meeting", 0.85
        if 0 <= hour < 6:
            return "sleeping", 0.90
        if motion > 0.7:
            return "exercising", 0.75
        if 9 <= hour <= 17:
            return "working", 0.70
        return "idle", 0.60
