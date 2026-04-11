"""
Tests for System Event Integration.

Coverage target: >80%
"""

from datetime import datetime, timezone

import pytest

from Agent_Guru.reasoning.state.system_events import (
    SystemEvent,
    SystemEventIntegration,
    SystemEventType,
)
from Agent_Guru.reasoning.state.world_state_engine import WorldStateEngine


class TestSystemEventIntegration:
    """Unit tests for SystemEventIntegration."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test integration initialization."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        assert integration is not None

    @pytest.mark.asyncio
    async def test_app_opened_event(self):
        """Test app opened event processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        event = SystemEvent(
            event_type=SystemEventType.APP_OPENED,
            timestamp=datetime.now(tz=timezone.utc),
            data={"app_id": "com.example.app"},
        )

        await integration.process_event(event)

        state = await engine.get_state()
        assert "com.example.app" in state.active_apps
        assert "com.example.app" in state.app_states
        assert state.app_states["com.example.app"].is_active is True

    @pytest.mark.asyncio
    async def test_app_closed_event(self):
        """Test app closed event processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        # First open the app
        open_event = SystemEvent(
            event_type=SystemEventType.APP_OPENED,
            timestamp=datetime.now(tz=timezone.utc),
            data={"app_id": "com.example.app"},
        )
        await integration.process_event(open_event)

        # Then close it
        close_event = SystemEvent(
            event_type=SystemEventType.APP_CLOSED,
            timestamp=datetime.now(tz=timezone.utc),
            data={"app_id": "com.example.app"},
        )
        await integration.process_event(close_event)

        state = await engine.get_state()
        assert "com.example.app" not in state.active_apps
        assert state.app_states["com.example.app"].is_active is False

    @pytest.mark.asyncio
    async def test_battery_changed_event(self):
        """Test battery changed event processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        event = SystemEvent(
            event_type=SystemEventType.BATTERY_CHANGED,
            timestamp=datetime.now(tz=timezone.utc),
            data={"battery_level": 75.0, "charging": True},
        )

        await integration.process_event(event)

        state = await engine.get_state()
        assert state.device_status.battery_level == 75.0
        assert state.device_status.charging is True

    @pytest.mark.asyncio
    async def test_network_changed_event(self):
        """Test network changed event processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        event = SystemEvent(
            event_type=SystemEventType.NETWORK_CHANGED,
            timestamp=datetime.now(tz=timezone.utc),
            data={"network_type": "cellular"},
        )

        await integration.process_event(event)

        state = await engine.get_state()
        assert state.device_status.network_type == "cellular"

    @pytest.mark.asyncio
    async def test_location_changed_event(self):
        """Test location changed event processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        event = SystemEvent(
            event_type=SystemEventType.LOCATION_CHANGED,
            timestamp=datetime.now(tz=timezone.utc),
            data={
                "latitude": 37.7749,
                "longitude": -122.4194,
                "address": "San Francisco, CA",
            },
        )

        await integration.process_event(event)

        state = await engine.get_state()
        assert state.location_context is not None
        assert state.location_context.latitude == 37.7749
        assert state.location_context.longitude == -122.4194

    @pytest.mark.asyncio
    async def test_calendar_event_added(self):
        """Test calendar event added processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        now = datetime.now(tz=timezone.utc)
        event = SystemEvent(
            event_type=SystemEventType.CALENDAR_EVENT_ADDED,
            timestamp=now,
            data={
                "event": {
                    "event_id": "event1",
                    "title": "Meeting",
                    "start_time": now,
                    "end_time": now,
                }
            },
        )

        await integration.process_event(event)

        state = await engine.get_state()
        assert len(state.calendar_events) == 1
        assert state.calendar_events[0].event_id == "event1"

    @pytest.mark.asyncio
    async def test_contact_added(self):
        """Test contact added processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        event = SystemEvent(
            event_type=SystemEventType.CONTACT_ADDED,
            timestamp=datetime.now(tz=timezone.utc),
            data={
                "contact": {
                    "name": "John Doe",
                    "phone_numbers": ["+1234567890"],
                    "email_addresses": ["john@example.com"],
                }
            },
        )

        await integration.process_event(event)

        state = await engine.get_state()
        assert "John Doe" in state.contacts
        assert state.contacts["John Doe"].phone_numbers == ["+1234567890"]

    @pytest.mark.asyncio
    async def test_task_started_event(self):
        """Test task started event processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        event = SystemEvent(
            event_type=SystemEventType.TASK_STARTED,
            timestamp=datetime.now(tz=timezone.utc),
            data={"task_id": "task123"},
        )

        await integration.process_event(event)

        state = await engine.get_state()
        assert "task123" in state.active_tasks

    @pytest.mark.asyncio
    async def test_task_completed_event(self):
        """Test task completed event processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        # Start task first
        start_event = SystemEvent(
            event_type=SystemEventType.TASK_STARTED,
            timestamp=datetime.now(tz=timezone.utc),
            data={"task_id": "task123"},
        )
        await integration.process_event(start_event)

        # Complete task
        complete_event = SystemEvent(
            event_type=SystemEventType.TASK_COMPLETED,
            timestamp=datetime.now(tz=timezone.utc),
            data={"task_id": "task123"},
        )
        await integration.process_event(complete_event)

        state = await engine.get_state()
        assert "task123" not in state.active_tasks
        assert len(state.recent_activities) > 0

    @pytest.mark.asyncio
    async def test_user_action_event(self):
        """Test user action event processing."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        event = SystemEvent(
            event_type=SystemEventType.USER_ACTION,
            timestamp=datetime.now(tz=timezone.utc),
            data={
                "action_type": "manual_update",
                "description": "User manually updated settings",
                "metadata": {"setting": "theme", "value": "dark"},
            },
        )

        await integration.process_event(event)

        state = await engine.get_state()
        assert len(state.recent_activities) > 0
        assert state.recent_activities[0].activity_type == "manual_update"

    @pytest.mark.asyncio
    async def test_invalid_event_data(self):
        """Test handling of invalid event data."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        # Event with missing required data
        event = SystemEvent(
            event_type=SystemEventType.APP_OPENED,
            timestamp=datetime.now(tz=timezone.utc),
            data={},  # Missing app_id
        )

        # Should not raise error
        await integration.process_event(event)

        state = await engine.get_state()
        assert len(state.active_apps) == 0

    @pytest.mark.asyncio
    async def test_multiple_events_sequence(self):
        """Test processing multiple events in sequence."""
        engine = WorldStateEngine()
        integration = SystemEventIntegration(engine)

        events = [
            SystemEvent(
                event_type=SystemEventType.BATTERY_CHANGED,
                timestamp=datetime.now(tz=timezone.utc),
                data={"battery_level": 100.0, "charging": True},
            ),
            SystemEvent(
                event_type=SystemEventType.APP_OPENED,
                timestamp=datetime.now(tz=timezone.utc),
                data={"app_id": "app1"},
            ),
            SystemEvent(
                event_type=SystemEventType.APP_OPENED,
                timestamp=datetime.now(tz=timezone.utc),
                data={"app_id": "app2"},
            ),
        ]

        for event in events:
            await integration.process_event(event)

        state = await engine.get_state()
        assert state.device_status.battery_level == 100.0
        assert len(state.active_apps) == 2
        assert "app1" in state.active_apps
        assert "app2" in state.active_apps
