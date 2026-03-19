"""
Vision Event Bus for the Agent Guru Vision System.

Provides async pub/sub delivery of VisionEvents to registered subscribers,
with optional filtering by event type, minimum confidence, and source module.

Design goals:
- All subscribers notified within 10 ms of event publication.
- Subscriber exceptions are isolated (logged, not re-raised).
- Module suspension: tracks subscriber counts per source module so the
  Frame Dispatcher can skip modules with zero subscribers.
- Standalone importability: no other Agent Guru components required.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

import structlog

from Agent_Guru.vision.vision_models import VisionEvent

logger: structlog.BoundLogger = structlog.get_logger(__name__)

# Type alias for async subscriber callbacks
AsyncCallback = Callable[[VisionEvent], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Internal subscription record
# ---------------------------------------------------------------------------


@dataclass
class _Subscription:
    """Internal record for a single subscriber registration."""

    subscription_id: str
    callback: AsyncCallback
    event_types: list[str]  # empty list = subscribe to all types
    min_confidence: float
    source_module: str  # empty string = any module


# ---------------------------------------------------------------------------
# VisionEventBus
# ---------------------------------------------------------------------------


class VisionEventBus:
    """Async publish/subscribe bus for VisionEvents.

    Usage::

        bus = VisionEventBus()

        async def handler(event: VisionEvent) -> None:
            print(event)

        sub_id = bus.subscribe(["object_detected"], handler, min_confidence=0.5)
        await bus.publish(VisionEvent(...))
        bus.unsubscribe(sub_id)
    """

    def __init__(self) -> None:
        # subscription_id → _Subscription
        self._subscriptions: dict[str, _Subscription] = {}
        # source_module → count of active subscribers interested in that module
        self._module_subscriber_counts: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Subscribe / unsubscribe
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_types: list[str],
        callback: AsyncCallback,
        min_confidence: float = 0.0,
        source_module: str = "",
    ) -> str:
        """Register a subscriber and return its unique subscription ID.

        Args:
            event_types: List of event type strings to receive.  An empty
                list means "subscribe to all event types".
            callback: Async callable invoked for each matching event.
            min_confidence: Minimum event confidence required for delivery.
            source_module: If non-empty, only events from this module are
                delivered.

        Returns:
            A unique subscription ID string (UUID4).
        """
        sub_id = str(uuid.uuid4())
        sub = _Subscription(
            subscription_id=sub_id,
            callback=callback,
            event_types=list(event_types),
            min_confidence=min_confidence,
            source_module=source_module,
        )
        self._subscriptions[sub_id] = sub

        # Update module subscriber counts
        if source_module:
            self._module_subscriber_counts[source_module] += 1

        logger.debug(
            "Subscriber registered",
            sub_id=sub_id,
            event_types=event_types,
            min_confidence=min_confidence,
            source_module=source_module,
        )
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscriber by its subscription ID.

        Args:
            subscription_id: The ID returned by :meth:`subscribe`.

        Raises:
            KeyError: If the subscription ID is not found.
        """
        sub = self._subscriptions.pop(subscription_id, None)
        if sub is None:
            raise KeyError(f"Unknown subscription_id: {subscription_id!r}")

        if sub.source_module:
            count = self._module_subscriber_counts.get(sub.source_module, 0)
            if count > 0:
                self._module_subscriber_counts[sub.source_module] = count - 1

        logger.debug("Subscriber removed", sub_id=subscription_id)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, event: VisionEvent) -> None:
        """Deliver an event to all matching subscribers concurrently.

        Subscriber exceptions are caught, logged, and do not prevent
        delivery to other subscribers.

        Args:
            event: The VisionEvent to publish.
        """
        matching = [
            sub
            for sub in self._subscriptions.values()
            if self._matches(sub, event)
        ]

        if not matching:
            return

        async def _safe_call(sub: _Subscription) -> None:
            try:
                await sub.callback(event)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Subscriber callback raised exception",
                    sub_id=sub.subscription_id,
                    event_type=event.event_type,
                    error=str(exc),
                )

        await asyncio.gather(*(_safe_call(sub) for sub in matching))

    # ------------------------------------------------------------------
    # Request-response
    # ------------------------------------------------------------------

    async def request(
        self,
        event_type: str,
        timeout: float = 1.0,
    ) -> Optional[VisionEvent]:
        """One-shot request: wait for the next event of the given type.

        Registers a temporary subscriber, waits up to ``timeout`` seconds
        for the first matching event, then unsubscribes.

        Args:
            event_type: The event type to wait for.
            timeout: Maximum wait time in seconds.

        Returns:
            The first matching VisionEvent, or ``None`` on timeout.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future[VisionEvent] = loop.create_future()

        async def _one_shot(event: VisionEvent) -> None:
            if not future.done():
                future.set_result(event)

        sub_id = self.subscribe([event_type], _one_shot)
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            try:
                self.unsubscribe(sub_id)
            except KeyError:
                pass  # Already removed

    # ------------------------------------------------------------------
    # Module suspension helpers
    # ------------------------------------------------------------------

    def get_subscriber_count(self, source_module: str) -> int:
        """Return the number of subscribers interested in a given module.

        The Frame Dispatcher uses this to decide whether to invoke a module.

        Args:
            source_module: Module name to query.

        Returns:
            Number of active subscribers for that module.
        """
        # Count subscriptions that match this module (either explicitly or via wildcard)
        count = 0
        for sub in self._subscriptions.values():
            if sub.source_module == "" or sub.source_module == source_module:
                count += 1
        return count

    def has_subscribers(self, source_module: str) -> bool:
        """Return True when at least one subscriber is interested in the module.

        Args:
            source_module: Module name to check.

        Returns:
            True if any subscriber would receive events from this module.
        """
        return self.get_subscriber_count(source_module) > 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(sub: _Subscription, event: VisionEvent) -> bool:
        """Return True when the event passes all of the subscription's filters."""
        # Event type filter
        if sub.event_types and event.event_type not in sub.event_types:
            return False
        # Confidence filter
        if event.confidence < sub.min_confidence:
            return False
        # Source module filter
        if sub.source_module and event.source_module != sub.source_module:
            return False
        return True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def subscription_count(self) -> int:
        """Total number of active subscriptions."""
        return len(self._subscriptions)
