"""
Tests for WorldState Integration.

Coverage target: >80%
"""

from datetime import datetime, timedelta, timezone

import pytest

from Agent_Guru.reasoning.models.world_state import (
    CalendarEvent,
    DeviceStatus,
    LocationState,
    SystemResources,
    WorldState,
)
from Agent_Guru.reasoning.state.world_state_integration import WorldStateContextGenerator


class TestWorldStateContextGenerator:
    """Unit tests for WorldStateContextGenerator."""

    @pytest.fixture
    def generator(self):
        """Create context generator."""
        return WorldStateContextGenerator()

    @pytest.fixture
    def basic_state(self):
        """Create basic world state."""
        return WorldState()

    def test_initialization(self, generator):
        """Test generator initialization."""
        assert generator is not None  # nosec B101

    def test_generate_llm_context_basic(self, generator, basic_state):
        """Test LLM context generation with basic state."""
        context = generator.generate_llm_context(basic_state)

        assert isinstance(context, str)  # nosec B101
        assert "battery" in context.lower()  # nosec B101
        assert "network" in context.lower()  # nosec B101

    def test_generate_llm_context_with_location(self, generator):
        """Test LLM context with location."""
        state = WorldState()
        state.location_context = LocationState(
            latitude=37.7749,
            longitude=-122.4194,
            accuracy=10.0,
            place_name="San Francisco",
        )

        context = generator.generate_llm_context(state)
        assert "San Francisco" in context  # nosec B101

    def test_generate_llm_context_with_active_apps(self, generator):
        """Test LLM context with active apps."""
        state = WorldState()
        state.active_apps = ["app1", "app2", "app3"]

        context = generator.generate_llm_context(state)
        assert "Active apps: 3" in context  # nosec B101

    def test_generate_llm_context_with_upcoming_events(self, generator):
        """Test LLM context with upcoming events."""
        state = WorldState()
        now = datetime.now(tz=timezone.utc)
        state.calendar_events = [
            CalendarEvent(
                event_id="event1",
                title="Meeting",
                start_time=now + timedelta(hours=1),
                end_time=now + timedelta(hours=2),
            )
        ]

        context = generator.generate_llm_context(state)
        assert "Upcoming" in context  # nosec B101

    def test_check_constraints_battery_low(self, generator):
        """Test constraint checking with low battery."""
        state = WorldState()
        state.device_status = DeviceStatus(battery_level=15.0)

        constraints = generator.check_constraints(state)
        assert constraints["battery_low"] is True  # nosec B101
        assert constraints["battery_critical"] is False  # nosec B101

    def test_check_constraints_battery_critical(self, generator):
        """Test constraint checking with critical battery."""
        state = WorldState()
        state.device_status = DeviceStatus(battery_level=5.0)

        constraints = generator.check_constraints(state)
        assert constraints["battery_low"] is True  # nosec B101
        assert constraints["battery_critical"] is True  # nosec B101

    def test_check_constraints_network_offline(self, generator):
        """Test constraint checking with offline network."""
        state = WorldState()
        state.device_status = DeviceStatus(
            battery_level=100.0,
            network_type="offline",
        )

        constraints = generator.check_constraints(state)
        assert constraints["network_available"] is False  # nosec B101

    def test_check_constraints_do_not_disturb(self, generator):
        """Test constraint checking with DND."""
        state = WorldState()
        state.device_status = DeviceStatus(
            battery_level=100.0,
            do_not_disturb=True,
        )

        constraints = generator.check_constraints(state)
        assert constraints["do_not_disturb"] is True  # nosec B101

    def test_check_constraints_high_cpu(self, generator):
        """Test constraint checking with high CPU."""
        state = WorldState()
        state.system_resources = SystemResources(
            cpu_usage=85.0,
            memory_usage=50.0,
        )

        constraints = generator.check_constraints(state)
        assert constraints["high_cpu"] is True  # nosec B101

    def test_get_app_availability_active(self, generator):
        """Test app availability check for active app."""
        state = WorldState()
        state.active_apps = ["com.example.app"]

        available = generator.get_app_availability(state, "com.example.app")
        assert available is True  # nosec B101

    def test_get_app_availability_inactive(self, generator):
        """Test app availability check for inactive app."""
        state = WorldState()

        available = generator.get_app_availability(state, "com.example.app")
        assert available is False  # nosec B101

    def test_get_calendar_conflicts_no_conflict(self, generator):
        """Test calendar conflict check with no conflicts."""
        state = WorldState()
        now = datetime.now(tz=timezone.utc)
        state.calendar_events = [
            CalendarEvent(
                event_id="event1",
                title="Meeting",
                start_time=now + timedelta(hours=2),
                end_time=now + timedelta(hours=3),
            )
        ]

        conflicts = generator.get_calendar_conflicts(
            state,
            (now + timedelta(hours=4)).isoformat(),
            (now + timedelta(hours=5)).isoformat(),
        )

        assert len(conflicts) == 0  # nosec B101

    def test_get_calendar_conflicts_with_conflict(self, generator):
        """Test calendar conflict check with conflicts."""
        state = WorldState()
        now = datetime.now(tz=timezone.utc)
        state.calendar_events = [
            CalendarEvent(
                event_id="event1",
                title="Meeting",
                start_time=now + timedelta(hours=2),
                end_time=now + timedelta(hours=3),
            )
        ]

        # Overlapping time
        conflicts = generator.get_calendar_conflicts(
            state,
            (now + timedelta(hours=2, minutes=30)).isoformat(),
            (now + timedelta(hours=3, minutes=30)).isoformat(),
        )

        assert len(conflicts) == 1  # nosec B101
        assert "event1" in conflicts  # nosec B101

    def test_get_calendar_conflicts_invalid_format(self, generator):
        """Test calendar conflict check with invalid datetime."""
        state = WorldState()

        conflicts = generator.get_calendar_conflicts(
            state,
            "invalid",
            "invalid",
        )

        assert len(conflicts) == 0  # nosec B101

    def test_should_use_brief_response_low_battery(self, generator):
        """Test brief response mode with low battery."""
        state = WorldState()
        state.device_status = DeviceStatus(battery_level=10.0)

        brief = generator.should_use_brief_response(state)
        assert brief is True  # nosec B101

    def test_should_use_brief_response_dnd(self, generator):
        """Test brief response mode with DND."""
        state = WorldState()
        state.device_status = DeviceStatus(
            battery_level=100.0,
            do_not_disturb=True,
        )

        brief = generator.should_use_brief_response(state)
        assert brief is True  # nosec B101

    def test_should_use_brief_response_high_cpu(self, generator):
        """Test brief response mode with high CPU."""
        state = WorldState()
        state.system_resources = SystemResources(
            cpu_usage=95.0,
            memory_usage=50.0,
        )

        brief = generator.should_use_brief_response(state)
        assert brief is True  # nosec B101

    def test_should_use_brief_response_normal(self, generator):
        """Test brief response mode with normal conditions."""
        state = WorldState()

        brief = generator.should_use_brief_response(state)
        assert brief is False  # nosec B101

    def test_get_location_constraints_no_location(self, generator):
        """Test location constraints with no location."""
        state = WorldState()

        constraints = generator.get_location_constraints(state)
        assert constraints["has_location"] is False  # nosec B101

    def test_get_location_constraints_with_location(self, generator):
        """Test location constraints with location."""
        state = WorldState()
        state.location_context = LocationState(
            latitude=37.7749,
            longitude=-122.4194,
            accuracy=10.0,
            place_name="Office",
            place_type="work",
        )

        constraints = generator.get_location_constraints(state)
        assert constraints["has_location"] is True  # nosec B101
        assert constraints["place_name"] == "Office"  # nosec B101
        assert constraints["is_work"] is True  # nosec B101
        assert constraints["is_home"] is False  # nosec B101

    def test_generate_context_summary(self, generator):
        """Test comprehensive context summary generation."""
        state = WorldState()
        state.device_status = DeviceStatus(battery_level=50.0)
        state.active_apps = ["app1", "app2"]
        state.active_tasks = ["task1"]

        summary = generator.generate_context_summary(state)

        assert "llm_context" in summary  # nosec B101
        assert "constraints" in summary  # nosec B101
        assert "brief_response_mode" in summary  # nosec B101
        assert "location" in summary  # nosec B101
        assert summary["active_app_count"] == 2  # nosec B101
        assert summary["active_task_count"] == 1  # nosec B101
