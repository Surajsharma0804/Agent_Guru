"""
System Event Integration for WorldState.

This module provides integration between system events and WorldState updates.

Performance: <10ms event processing latency
"""

from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from Agent_Guru.reasoning.models.world_state import (
    Activity,
    AppState,
    CalendarEvent,
    Contact,
    DeviceStatus,
    LocationState,
)
from Agent_Guru.reasoning.state.world_state_engine import WorldStateEngine

logger = structlog.get_logger(__name__)


class SystemEventType(Enum):
    """Types of system events."""

    APP_OPENED = "app_opened"
    APP_CLOSED = "app_closed"
    BATTERY_CHANGED = "battery_changed"
    NETWORK_CHANGED = "network_changed"
    LOCATION_CHANGED = "location_changed"
    CALENDAR_EVENT_ADDED = "calendar_event_added"
    CALENDAR_EVENT_UPDATED = "calendar_event_updated"
    CONTACT_ADDED = "contact_added"
    CONTACT_UPDATED = "contact_updated"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    USER_ACTION = "user_action"


class SystemEvent:
    """System event with metadata."""

    def __init__(
        self,
        event_type: SystemEventType,
        timestamp: datetime,
        data: dict[str, Any],
    ):
        """Initialize system event.

        Args:
            event_type: Type of event
            timestamp: When event occurred
            data: Event-specific data
        """
        self.event_type = event_type
        self.timestamp = timestamp
        self.data = data


class SystemEventIntegration:
    """Integration between system events and WorldState.

    Time Complexity: O(1) per event
    Space Complexity: O(1)
    """

    def __init__(self, world_state_engine: WorldStateEngine):
        """Initialize system event integration.

        Args:
            world_state_engine: WorldState engine to update
        """
        self._engine = world_state_engine
        self._event_handlers: dict[SystemEventType, Callable] = {
            SystemEventType.APP_OPENED: self._handle_app_opened,
            SystemEventType.APP_CLOSED: self._handle_app_closed,
            SystemEventType.BATTERY_CHANGED: self._handle_battery_changed,
            SystemEventType.NETWORK_CHANGED: self._handle_network_changed,
            SystemEventType.LOCATION_CHANGED: self._handle_location_changed,
            SystemEventType.CALENDAR_EVENT_ADDED: self._handle_calendar_event_added,
            SystemEventType.CALENDAR_EVENT_UPDATED: self._handle_calendar_event_updated,
            SystemEventType.CONTACT_ADDED: self._handle_contact_added,
            SystemEventType.CONTACT_UPDATED: self._handle_contact_updated,
            SystemEventType.TASK_STARTED: self._handle_task_started,
            SystemEventType.TASK_COMPLETED: self._handle_task_completed,
            SystemEventType.USER_ACTION: self._handle_user_action,
        }

        logger.info("system_event_integration_initialized")

    async def process_event(self, event: SystemEvent) -> None:
        """Process system event and update WorldState.

        Time Complexity: O(1)

        Args:
            event: System event to process
        """
        handler = self._event_handlers.get(event.event_type)
        if handler:
            try:
                await handler(event)
                logger.info(
                    "event_processed",
                    event_type=event.event_type.value,
                    timestamp=event.timestamp.isoformat(),
                )
            except Exception as e:
                logger.error(
                    "event_processing_failed",
                    event_type=event.event_type.value,
                    error=str(e),
                )
        else:
            logger.warning(
                "unknown_event_type",
                event_type=event.event_type.value,
            )

    async def _handle_app_opened(self, event: SystemEvent) -> None:
        """Handle app opened event."""
        app_id = event.data.get("app_id")
        if not app_id:
            return

        # Get current state
        state = await self._engine.get_state()

        # Add to active apps if not already there
        if app_id not in state.active_apps:
            active_apps = state.active_apps + [app_id]
            await self._engine.update_state(active_apps=active_apps)

        # Update app state
        app_states = state.app_states.copy()
        app_states[app_id] = AppState(
            app_id=app_id,
            is_active=True,
            last_used=event.timestamp,
            usage_duration=0.0,
        )
        await self._engine.update_state(app_states=app_states)

    async def _handle_app_closed(self, event: SystemEvent) -> None:
        """Handle app closed event."""
        app_id = event.data.get("app_id")
        if not app_id:
            return

        # Get current state
        state = await self._engine.get_state()

        # Remove from active apps
        if app_id in state.active_apps:
            active_apps = [a for a in state.active_apps if a != app_id]
            await self._engine.update_state(active_apps=active_apps)

        # Update app state
        if app_id in state.app_states:
            app_states = state.app_states.copy()
            app_state = app_states[app_id]
            app_states[app_id] = AppState(
                app_id=app_id,
                is_active=False,
                last_used=event.timestamp,
                usage_duration=app_state.usage_duration,
            )
            await self._engine.update_state(app_states=app_states)

    async def _handle_battery_changed(self, event: SystemEvent) -> None:
        """Handle battery changed event."""
        battery_level = event.data.get("battery_level")
        charging = event.data.get("charging", False)

        if battery_level is None:
            return

        # Get current device status
        state = await self._engine.get_state()
        device_status = DeviceStatus(
            battery_level=battery_level,
            charging=charging,
            network_type=state.device_status.network_type,
            screen_state=state.device_status.screen_state,
            do_not_disturb=state.device_status.do_not_disturb,
        )

        await self._engine.update_state(device_status=device_status)

    async def _handle_network_changed(self, event: SystemEvent) -> None:
        """Handle network changed event."""
        network_type = event.data.get("network_type")
        if not network_type:
            return

        # Get current device status
        state = await self._engine.get_state()
        device_status = DeviceStatus(
            battery_level=state.device_status.battery_level,
            charging=state.device_status.charging,
            network_type=network_type,
            screen_state=state.device_status.screen_state,
            do_not_disturb=state.device_status.do_not_disturb,
        )

        await self._engine.update_state(device_status=device_status)

    async def _handle_location_changed(self, event: SystemEvent) -> None:
        """Handle location changed event."""
        latitude = event.data.get("latitude")
        longitude = event.data.get("longitude")
        accuracy = event.data.get("accuracy", 10.0)  # Default 10m accuracy
        place_name = event.data.get("place_name")

        if latitude is None or longitude is None:
            return

        location = LocationState(
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            place_name=place_name,
            arrival_time=event.timestamp,
        )

        await self._engine.update_state(location_context=location)

    async def _handle_calendar_event_added(self, event: SystemEvent) -> None:
        """Handle calendar event added."""
        event_data = event.data.get("event")
        if not event_data:
            return

        # Get current state
        state = await self._engine.get_state()

        # Add new event
        calendar_event = CalendarEvent(**event_data)
        calendar_events = state.calendar_events + [calendar_event]

        await self._engine.update_state(calendar_events=calendar_events)

    async def _handle_calendar_event_updated(self, event: SystemEvent) -> None:
        """Handle calendar event updated."""
        event_id = event.data.get("event_id")
        event_data = event.data.get("event")

        if not event_id or not event_data:
            return

        # Get current state
        state = await self._engine.get_state()

        # Update event
        calendar_events = [
            CalendarEvent(**event_data) if e.event_id == event_id else e
            for e in state.calendar_events
        ]

        await self._engine.update_state(calendar_events=calendar_events)

    async def _handle_contact_added(self, event: SystemEvent) -> None:
        """Handle contact added."""
        contact_data = event.data.get("contact")
        if not contact_data:
            return

        # Ensure contact_id is present
        if "contact_id" not in contact_data:
            contact_data["contact_id"] = contact_data.get("name", "unknown")

        # Get current state
        state = await self._engine.get_state()

        # Add new contact
        contact = Contact(**contact_data)
        contacts = state.contacts.copy()
        contacts[contact.name] = contact

        await self._engine.update_state(contacts=contacts)

    async def _handle_contact_updated(self, event: SystemEvent) -> None:
        """Handle contact updated."""
        contact_data = event.data.get("contact")
        if not contact_data:
            return

        # Ensure contact_id is present
        if "contact_id" not in contact_data:
            contact_data["contact_id"] = contact_data.get("name", "unknown")

        # Get current state
        state = await self._engine.get_state()

        # Update contact
        contact = Contact(**contact_data)
        contacts = state.contacts.copy()
        contacts[contact.name] = contact

        await self._engine.update_state(contacts=contacts)

    async def _handle_task_started(self, event: SystemEvent) -> None:
        """Handle task started."""
        task_id = event.data.get("task_id")
        if not task_id:
            return

        # Get current state
        state = await self._engine.get_state()

        # Add to active tasks
        if task_id not in state.active_tasks:
            active_tasks = state.active_tasks + [task_id]
            await self._engine.update_state(active_tasks=active_tasks)

    async def _handle_task_completed(self, event: SystemEvent) -> None:
        """Handle task completed."""
        task_id = event.data.get("task_id")
        if not task_id:
            return

        # Get current state
        state = await self._engine.get_state()

        # Remove from active tasks
        if task_id in state.active_tasks:
            active_tasks = [t for t in state.active_tasks if t != task_id]
            await self._engine.update_state(active_tasks=active_tasks)

        # Add to recent activities
        import uuid

        activity = Activity(
            activity_id=str(uuid.uuid4()),
            activity_type="task_completed",
            timestamp=event.timestamp,
            details={"task_id": task_id, "description": f"Completed task: {task_id}"},
        )
        recent_activities = state.recent_activities + [activity]

        await self._engine.update_state(recent_activities=recent_activities)

    async def _handle_user_action(self, event: SystemEvent) -> None:
        """Handle explicit user action."""
        action_type = event.data.get("action_type")
        description = event.data.get("description", "")

        if not action_type:
            return

        # Get current state
        state = await self._engine.get_state()

        # Add to recent activities
        import uuid

        activity = Activity(
            activity_id=str(uuid.uuid4()),
            activity_type=action_type,
            timestamp=event.timestamp,
            details={
                "description": description,
                **event.data.get("metadata", {}),
            },
        )
        recent_activities = state.recent_activities + [activity]

        await self._engine.update_state(recent_activities=recent_activities)
