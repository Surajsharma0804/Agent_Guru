"""Tests for WorldState data models."""

from datetime import datetime, timedelta, timezone

import pytest

from Agent_Guru.reasoning.models.world_state import (
    Activity,
    AppState,
    CalendarEvent,
    Contact,
    DeviceStatus,
    LocationState,
    SystemResources,
    WorldState,
)


class TestDeviceStatus:
    def test_valid_device_status(self):
        status = DeviceStatus(
            battery_level=75.0,
            charging=True,
            network_type="wifi",
            screen_state="on",
            do_not_disturb=False,
        )
        assert status.battery_level == 75.0  # nosec B101
        assert status.charging is True  # nosec B101

    def test_invalid_battery_level(self):
        with pytest.raises(ValueError):
            DeviceStatus(battery_level=150.0)

    def test_invalid_network_type(self):
        with pytest.raises(ValueError, match="network_type must be one of"):
            DeviceStatus(battery_level=50.0, network_type="invalid")


class TestSystemResources:
    def test_valid_resources(self):
        resources = SystemResources(
            cpu_usage=45.5,
            memory_usage=60.0,
            disk_space_available=50000,
        )
        assert resources.cpu_usage == 45.5  # nosec B101
        assert resources.disk_space_available == 50000  # nosec B101


class TestAppState:
    def test_valid_app_state(self):
        app = AppState(
            app_id="com.example.app",
            is_active=True,
            last_used=datetime.now(tz=timezone.utc),
            usage_duration=3600.0,
        )
        assert app.app_id == "com.example.app"  # nosec B101
        assert app.is_active is True  # nosec B101


class TestCalendarEvent:
    def test_valid_event(self):
        start = datetime.now(tz=timezone.utc)
        end = start + timedelta(hours=1)

        event = CalendarEvent(
            event_id="evt_1",
            title="Meeting",
            start_time=start,
            end_time=end,
            location="Office",
            attendees=["alice@example.com"],
        )
        assert event.title == "Meeting"  # nosec B101
        assert event.end_time > event.start_time  # nosec B101

    def test_invalid_end_time(self):
        start = datetime.now(tz=timezone.utc)
        end = start - timedelta(hours=1)

        with pytest.raises(ValueError, match="end_time must be after start_time"):
            CalendarEvent(
                event_id="evt_1",
                title="Meeting",
                start_time=start,
                end_time=end,
            )


class TestContact:
    def test_valid_contact(self):
        contact = Contact(
            contact_id="c1",
            name="John Doe",
            phone_numbers=["+1234567890"],
            email_addresses=["john@example.com"],
            relationship="friend",
        )
        assert contact.name == "John Doe"  # nosec B101
        assert len(contact.phone_numbers) == 1  # nosec B101


class TestLocationState:
    def test_valid_location(self):
        location = LocationState(
            latitude=37.7749,
            longitude=-122.4194,
            accuracy=10.0,
            place_name="San Francisco",
            place_type="city",
        )
        assert location.latitude == 37.7749  # nosec B101
        assert location.place_name == "San Francisco"  # nosec B101

    def test_invalid_latitude(self):
        with pytest.raises(ValueError):
            LocationState(latitude=100.0, longitude=0.0, accuracy=10.0)


class TestActivity:
    def test_valid_activity(self):
        activity = Activity(
            activity_id="act_1",
            activity_type="call",
            timestamp=datetime.now(tz=timezone.utc),
            details={"duration": 300, "contact": "John"},
        )
        assert activity.activity_type == "call"  # nosec B101
        assert "duration" in activity.details  # nosec B101


class TestWorldState:
    @pytest.fixture
    def sample_world_state(self):
        return WorldState(
            device_status=DeviceStatus(
                battery_level=80.0,
                charging=False,
                network_type="wifi",
            ),
            system_resources=SystemResources(
                cpu_usage=30.0,
                memory_usage=50.0,
                disk_space_available=100000,
            ),
            active_apps=["app1", "app2"],
            calendar_events=[
                CalendarEvent(
                    event_id="evt_1",
                    title="Meeting",
                    start_time=datetime.now(tz=timezone.utc) + timedelta(hours=2),
                    end_time=datetime.now(tz=timezone.utc) + timedelta(hours=3),
                )
            ],
        )

    def test_world_state_creation(self, sample_world_state):
        assert sample_world_state.device_status.battery_level == 80.0  # nosec B101
        assert len(sample_world_state.active_apps) == 2  # nosec B101

    def test_get_active_app_count(self, sample_world_state):
        assert sample_world_state.get_active_app_count() == 2  # nosec B101

    def test_is_battery_low(self, sample_world_state):
        assert not sample_world_state.is_battery_low()  # nosec B101

        low_battery_state = WorldState(
            device_status=DeviceStatus(battery_level=15.0),
            system_resources=SystemResources(
                cpu_usage=30.0,
                memory_usage=50.0,
                disk_space_available=100000,
            ),
        )
        assert low_battery_state.is_battery_low()  # nosec B101

    def test_get_upcoming_events(self, sample_world_state):
        events = sample_world_state.get_upcoming_events(hours=24)
        assert len(events) == 1  # nosec B101
        assert events[0].title == "Meeting"  # nosec B101

    def test_get_contact_by_name(self):
        state = WorldState(
            device_status=DeviceStatus(battery_level=80.0),
            system_resources=SystemResources(
                cpu_usage=30.0,
                memory_usage=50.0,
                disk_space_available=100000,
            ),
            contacts={
                "c1": Contact(
                    contact_id="c1",
                    name="John Doe",
                    phone_numbers=["+1234567890"],
                )
            },
        )

        contact = state.get_contact_by_name("John Doe")
        assert contact is not None  # nosec B101
        assert contact.name == "John Doe"  # nosec B101

        # Case insensitive
        contact = state.get_contact_by_name("john doe")
        assert contact is not None  # nosec B101

        # Not found
        contact = state.get_contact_by_name("Jane Smith")
        assert contact is None  # nosec B101
