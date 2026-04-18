"""Proactive Notifications and Predictive Assistance Engine."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from Agent_Guru.proactive.suppression import SuppressionManager

logger = logging.getLogger(__name__)

# Token bucket: 3/hour active, 1/hour idle
_ACTIVE_RATE = 3.0 / 3600.0   # tokens per second
_IDLE_RATE = 1.0 / 3600.0
_BUCKET_CAPACITY_ACTIVE = 3.0
_BUCKET_CAPACITY_IDLE = 1.0


@dataclass
class ProactiveSuggestion:
    """A proactive suggestion to deliver to the user."""
    suggestion_id: str
    suggestion_type: str
    content: str
    priority: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryResult:
    """Result of attempting to deliver a proactive suggestion."""
    delivered: bool
    suggestion_id: str
    reason: Optional[str] = None


class _TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity
        self._last_refill = time.time()

    def consume(self, tokens: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    @property
    def available(self) -> float:
        return self._tokens


class ProactiveEngine:
    """Evaluates context and delivers proactive suggestions with rate limiting."""

    def __init__(
        self,
        quiet_hours: Optional[tuple[int, int]] = None,
        suppression_manager: Optional[SuppressionManager] = None,
    ) -> None:
        self.quiet_hours = quiet_hours  # (start_hour, end_hour) in 24h
        self.suppression = suppression_manager or SuppressionManager()
        self._active_bucket = _TokenBucket(_ACTIVE_RATE, _BUCKET_CAPACITY_ACTIVE)
        self._idle_bucket = _TokenBucket(_IDLE_RATE, _BUCKET_CAPACITY_IDLE)
        self._is_active = True
        self._dnd_queue: list[ProactiveSuggestion] = []
        # Simple online classifier weights (SGD stub)
        self._relevance_weights: dict[str, float] = {}

    def set_active(self, active: bool) -> None:
        self._is_active = active

    def _in_quiet_hours(self) -> bool:
        if self.quiet_hours is None:
            return False
        from datetime import datetime, timezone
        hour = datetime.now(tz=timezone.utc).hour
        start, end = self.quiet_hours
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end

    def _rate_limit_ok(self) -> bool:
        bucket = self._active_bucket if self._is_active else self._idle_bucket
        return bucket.consume()

    def evaluate_context(self, context: dict[str, Any]) -> Optional[ProactiveSuggestion]:
        """Evaluate context and return a suggestion if appropriate."""
        suggestion_type = context.get("type", "general")
        content = context.get("content", "")
        if not content:
            return None
        return ProactiveSuggestion(
            suggestion_id=f"{suggestion_type}_{int(time.time())}",
            suggestion_type=suggestion_type,
            content=content,
            priority=context.get("priority", 0.5),
        )

    def deliver(self, suggestion: ProactiveSuggestion) -> DeliveryResult:
        """Attempt to deliver a suggestion, respecting rate limits and suppression."""
        if self._in_quiet_hours():
            self._dnd_queue.append(suggestion)
            return DeliveryResult(
                delivered=False,
                suggestion_id=suggestion.suggestion_id,
                reason="quiet_hours",
            )
        if self.suppression.is_suppressed(suggestion.suggestion_type):
            return DeliveryResult(
                delivered=False,
                suggestion_id=suggestion.suggestion_id,
                reason="suppressed",
            )
        if not self._rate_limit_ok():
            return DeliveryResult(
                delivered=False,
                suggestion_id=suggestion.suggestion_id,
                reason="rate_limited",
            )
        logger.info("Delivering suggestion: %s", suggestion.content)
        return DeliveryResult(delivered=True, suggestion_id=suggestion.suggestion_id)

    def record_feedback(self, suggestion_id: str, accepted: bool) -> None:
        """Update online classifier based on user feedback."""
        # SGD stub: update weight for suggestion type
        parts = suggestion_id.split("_")
        stype = parts[0] if parts else "general"
        current = self._relevance_weights.get(stype, 0.5)
        lr = 0.1
        target = 1.0 if accepted else 0.0
        self._relevance_weights[stype] = current + lr * (target - current)
        if accepted:
            self.suppression.record_acceptance(stype)
        else:
            self.suppression.record_dismissal(stype)

    def flush_dnd_queue(self) -> list[DeliveryResult]:
        """Deliver queued suggestions after DND ends."""
        results = []
        remaining = []
        for suggestion in self._dnd_queue:
            result = self.deliver(suggestion)
            results.append(result)
            if not result.delivered and result.reason == "quiet_hours":
                remaining.append(suggestion)
        self._dnd_queue = remaining
        return results
