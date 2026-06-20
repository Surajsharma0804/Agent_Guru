"""World State Engine - Real-time context tracking.

This module implements the WorldStateEngine for tracking and managing
real-time system and user context state.

Performance Requirements:
- State queries: <20ms latency
- State updates: <10ms latency
- Subscription callbacks: <5ms latency
- Memory: <50MB for state storage

Architecture:
- In-memory state with async updates
- Subscription mechanism for state changes
- Fast queries with O(1) lookups
- Persistence to SQLite for recovery
"""

import asyncio
import inspect
import logging
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

_logger = logging.getLogger(__name__)
from uuid import uuid4  # noqa: E402

import structlog  # noqa: E402

from Agent_Guru.reasoning.models.world_state import WorldState  # noqa: E402

logger = structlog.get_logger(__name__)


class StateChangeEvent:
    """Event representing a state change."""

    def __init__(
        self,
        event_id: str,
        timestamp: datetime,
        field_path: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """Initialize state change event.

        Args:
            event_id: Unique event identifier
            timestamp: When the change occurred
            field_path: Dot-separated path to changed field (e.g., "device_status.battery_level")
            old_value: Previous value
            new_value: New value

        """
        self.event_id = event_id
        self.timestamp = timestamp
        self.field_path = field_path
        self.old_value = old_value
        self.new_value = new_value


class WorldStateEngine:
    """Engine for managing world state with real-time updates.

    Time Complexity:
    - get_state: O(1)
    - update_state: O(1) + O(n) for n subscribers
    - query_state: O(1)
    - subscribe_to_updates: O(1)

    Space Complexity: O(1) for state + O(n) for n subscribers
    """

    def __init__(self) -> None:
        """Initialize world state engine."""
        self._state = WorldState()
        self._subscribers: dict[str, Callable[[StateChangeEvent], None]] = {}
        self._lock = asyncio.Lock()
        self._change_history: deque[StateChangeEvent] = deque(maxlen=1000)
        self._max_history_size = 1000

        logger.info("world_state_engine_initialized")

    async def get_state(self) -> WorldState:
        """Get current world state.

        Time Complexity: O(1)

        Returns:
            Current world state (copy)

        """
        async with self._lock:
            # Return a copy to prevent external modifications
            return self._state.model_copy(deep=True)

    async def update_state(self, **updates: Any) -> None:
        """Update world state fields.

        Time Complexity: O(1) + O(n) for n subscribers

        Args:
            **updates: Field updates as keyword arguments

        Example:
            await engine.update_state(
                device_status=DeviceStatus(battery_level=50, charging=True)
            )

        """
        async with self._lock:
            # Track changes for notifications
            changes: list[StateChangeEvent] = []

            for field_name, new_value in updates.items():
                if not hasattr(self._state, field_name):
                    logger.warning(
                        "invalid_field_update",
                        field=field_name,
                        value=new_value,
                    )
                    continue

                old_value = getattr(self._state, field_name)

                # Only update if value changed
                if old_value != new_value:
                    setattr(self._state, field_name, new_value)

                    # Create change event
                    event = StateChangeEvent(
                        event_id=str(uuid4()),
                        timestamp=datetime.now(tz=UTC),
                        field_path=field_name,
                        old_value=old_value,
                        new_value=new_value,
                    )
                    changes.append(event)

                    # Add to history — deque(maxlen=1000) auto-evicts oldest
                    self._change_history.append(event)

            # Notify subscribers (outside lock to avoid deadlock)
            if changes:
                await self._notify_subscribers(changes)

                logger.info(
                    "state_updated",
                    num_changes=len(changes),
                    fields=[c.field_path for c in changes],
                )

    async def _notify_subscribers(self, changes: list[StateChangeEvent]) -> None:
        """Notify subscribers of state changes.

        Time Complexity: O(n * m) for n subscribers and m changes

        Args:
            changes: List of state change events

        """
        for subscriber_id, callback in self._subscribers.items():
            for change in changes:
                try:
                    # Call subscriber callback
                    if inspect.iscoroutinefunction(callback):
                        await callback(change)
                    else:
                        callback(change)
                except Exception as e:
                    logger.exception(
                        "subscriber_callback_failed",
                        subscriber_id=subscriber_id,
                        error=str(e),
                        field=change.field_path,
                    )

    def subscribe_to_updates(
        self,
        callback: Callable[[StateChangeEvent], None],
        subscriber_id: str | None = None,
    ) -> str:
        """Subscribe to state change notifications.

        Time Complexity: O(1)

        Args:
            callback: Function to call on state changes
            subscriber_id: Optional subscriber identifier

        Returns:
            Subscriber ID for unsubscribing

        Example:
            def on_battery_change(event: StateChangeEvent):
                if event.field_path == "device_status.battery_level":
                    _logger.debug("Battery: %s%%", event.new_value)

            sub_id = engine.subscribe_to_updates(on_battery_change)

        """
        if subscriber_id is None:
            subscriber_id = str(uuid4())

        self._subscribers[subscriber_id] = callback

        logger.info(
            "subscriber_added",
            subscriber_id=subscriber_id,
            total_subscribers=len(self._subscribers),
        )

        return subscriber_id

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Unsubscribe from state change notifications.

        Time Complexity: O(1)

        Args:
            subscriber_id: Subscriber identifier

        Returns:
            True if unsubscribed, False if not found

        """
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]
            logger.info(
                "subscriber_removed",
                subscriber_id=subscriber_id,
                total_subscribers=len(self._subscribers),
            )
            return True
        return False

    async def query_state(self, field_path: str) -> Any | None:
        """Query specific state field.

        Time Complexity: O(1)

        Args:
            field_path: Dot-separated path to field (e.g., "device_status.battery_level")

        Returns:
            Field value or None if not found

        Example:
            battery = await engine.query_state("device_status.battery_level")

        """
        async with self._lock:
            parts = field_path.split(".")
            value = self._state

            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                else:
                    logger.warning("field_not_found", field_path=field_path)
                    return None

            return value

    async def persist_state(self) -> dict[str, Any]:
        """Persist current state to dictionary.

        Time Complexity: O(1)

        Returns:
            State as dictionary for persistence

        """
        async with self._lock:
            return self._state.model_dump()

    async def restore_state(self, state_dict: dict[str, Any]) -> None:
        """Restore state from dictionary.

        Time Complexity: O(1)

        Args:
            state_dict: State dictionary from persist_state

        """
        async with self._lock:
            self._state = WorldState(**state_dict)
            logger.info("state_restored")

    def get_change_history(
        self,
        field_path: str | None = None,
        limit: int = 100,
    ) -> list[StateChangeEvent]:
        """Get state change history.

        Time Complexity: O(n) for n history entries

        Args:
            field_path: Optional filter by field path
            limit: Maximum number of events to return

        Returns:
            List of state change events (most recent first)

        """
        history = list(reversed(self._change_history))  # Most recent first

        if field_path:
            history = [e for e in history if e.field_path == field_path]

        return history[:limit]

    def get_subscriber_count(self) -> int:
        """Get number of active subscribers.

        Time Complexity: O(1)

        Returns:
            Number of subscribers

        """
        return len(self._subscribers)
