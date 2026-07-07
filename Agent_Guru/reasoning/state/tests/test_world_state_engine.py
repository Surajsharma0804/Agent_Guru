"""
Tests for World State Engine.

Coverage target: >80%
"""

import asyncio

import pytest

from Agent_Guru.reasoning.models.world_state import (
    DeviceStatus,
    SystemResources,
)
from Agent_Guru.reasoning.state.world_state_engine import (
    StateChangeEvent,
    WorldStateEngine,
)


class TestWorldStateEngine:
    """Unit tests for WorldStateEngine."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test engine initialization."""
        engine = WorldStateEngine()

        state = await engine.get_state()
        assert state is not None  # nosec B101
        assert engine.get_subscriber_count() == 0  # nosec B101

    @pytest.mark.asyncio
    async def test_get_state_returns_copy(self):
        """Test that get_state returns a copy."""
        engine = WorldStateEngine()

        state1 = await engine.get_state()
        state2 = await engine.get_state()

        # Should be different objects
        assert state1 is not state2  # nosec B101

    @pytest.mark.asyncio
    async def test_update_device_status(self):
        """Test updating device status."""
        engine = WorldStateEngine()

        device_status = DeviceStatus(
            battery_level=75,
            charging=True,
            network_type="wifi",
            screen_state="on",
            do_not_disturb=False,
        )

        await engine.update_state(device_status=device_status)

        state = await engine.get_state()
        assert state.device_status.battery_level == 75  # nosec B101
        assert state.device_status.charging is True  # nosec B101

    @pytest.mark.asyncio
    async def test_update_system_resources(self):
        """Test updating system resources."""
        engine = WorldStateEngine()

        resources = SystemResources(
            cpu_usage=45.5,
            memory_usage=60.0,
            disk_space_available=1000,
        )

        await engine.update_state(system_resources=resources)

        state = await engine.get_state()
        assert state.system_resources.cpu_usage == 45.5  # nosec B101
        assert state.system_resources.memory_usage == 60.0  # nosec B101

    @pytest.mark.asyncio
    async def test_query_state_simple_field(self):
        """Test querying simple state field."""
        engine = WorldStateEngine()

        device_status = DeviceStatus(battery_level=80)
        await engine.update_state(device_status=device_status)

        result = await engine.query_state("device_status")
        assert result is not None  # nosec B101
        assert result.battery_level == 80  # nosec B101

    @pytest.mark.asyncio
    async def test_query_state_nested_field(self):
        """Test querying nested state field."""
        engine = WorldStateEngine()

        device_status = DeviceStatus(battery_level=80)
        await engine.update_state(device_status=device_status)

        result = await engine.query_state("device_status.battery_level")
        assert result == 80  # nosec B101

    @pytest.mark.asyncio
    async def test_query_state_invalid_field(self):
        """Test querying invalid field returns None."""
        engine = WorldStateEngine()

        result = await engine.query_state("invalid_field")
        assert result is None  # nosec B101

    @pytest.mark.asyncio
    async def test_subscribe_to_updates(self):
        """Test subscribing to state updates."""
        engine = WorldStateEngine()
        events_received = []

        def callback(event: StateChangeEvent):
            events_received.append(event)

        sub_id = engine.subscribe_to_updates(callback)
        assert sub_id is not None  # nosec B101
        assert engine.get_subscriber_count() == 1  # nosec B101

        # Trigger update
        device_status = DeviceStatus(battery_level=50)
        await engine.update_state(device_status=device_status)

        # Give callbacks time to execute
        await asyncio.sleep(0.1)

        assert len(events_received) == 1  # nosec B101
        assert events_received[0].field_path == "device_status"  # nosec B101
        assert events_received[0].new_value.battery_level == 50  # nosec B101

    @pytest.mark.asyncio
    async def test_subscribe_async_callback(self):
        """Test subscribing with async callback."""
        engine = WorldStateEngine()
        events_received = []

        async def async_callback(event: StateChangeEvent):
            await asyncio.sleep(0.01)  # Simulate async work
            events_received.append(event)

        engine.subscribe_to_updates(async_callback)

        # Trigger update
        device_status = DeviceStatus(battery_level=60)
        await engine.update_state(device_status=device_status)

        # Give callbacks time to execute
        await asyncio.sleep(0.1)

        assert len(events_received) == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Test unsubscribing from updates."""
        engine = WorldStateEngine()
        events_received = []

        def callback(event: StateChangeEvent):
            events_received.append(event)

        sub_id = engine.subscribe_to_updates(callback)
        assert engine.get_subscriber_count() == 1  # nosec B101

        # Unsubscribe
        result = engine.unsubscribe(sub_id)
        assert result is True  # nosec B101
        assert engine.get_subscriber_count() == 0  # nosec B101

        # Trigger update - should not receive event
        device_status = DeviceStatus(battery_level=40)
        await engine.update_state(device_status=device_status)

        await asyncio.sleep(0.1)
        assert len(events_received) == 0  # nosec B101

    @pytest.mark.asyncio
    async def test_unsubscribe_invalid_id(self):
        """Test unsubscribing with invalid ID."""
        engine = WorldStateEngine()

        result = engine.unsubscribe("invalid_id")
        assert result is False  # nosec B101

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test multiple subscribers receive updates."""
        engine = WorldStateEngine()
        events1 = []
        events2 = []

        def callback1(event: StateChangeEvent):
            events1.append(event)

        def callback2(event: StateChangeEvent):
            events2.append(event)

        engine.subscribe_to_updates(callback1)
        engine.subscribe_to_updates(callback2)
        assert engine.get_subscriber_count() == 2  # nosec B101

        # Trigger update
        device_status = DeviceStatus(battery_level=30)
        await engine.update_state(device_status=device_status)

        await asyncio.sleep(0.1)

        assert len(events1) == 1  # nosec B101
        assert len(events2) == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_persist_and_restore_state(self):
        """Test state persistence and restoration."""
        engine = WorldStateEngine()

        # Set some state
        device_status = DeviceStatus(battery_level=85, charging=True)
        resources = SystemResources(cpu_usage=50.0, memory_usage=60.0, disk_space_available=1000)
        await engine.update_state(
            device_status=device_status,
            system_resources=resources,
        )

        # Persist state
        state_dict = await engine.persist_state()
        assert state_dict is not None  # nosec B101
        assert "device_status" in state_dict  # nosec B101
        assert "system_resources" in state_dict  # nosec B101

        # Create new engine and restore
        new_engine = WorldStateEngine()
        await new_engine.restore_state(state_dict)

        # Verify restored state
        restored_state = await new_engine.get_state()
        assert restored_state.device_status.battery_level == 85  # nosec B101
        assert restored_state.device_status.charging is True  # nosec B101
        assert restored_state.system_resources.cpu_usage == 50.0  # nosec B101

    @pytest.mark.asyncio
    async def test_change_history(self):
        """Test change history tracking."""
        engine = WorldStateEngine()

        # Make several updates
        await engine.update_state(device_status=DeviceStatus(battery_level=100))
        await engine.update_state(device_status=DeviceStatus(battery_level=90))
        await engine.update_state(device_status=DeviceStatus(battery_level=80))

        # Get history
        history = engine.get_change_history()
        assert (  # nosec B101
            len(history) >= 2
        )  # At least 2 changes (100->90 and 90->80, first one might be same as default)

        # Most recent should be first
        assert history[0].new_value.battery_level == 80  # nosec B101

    @pytest.mark.asyncio
    async def test_change_history_filtered(self):
        """Test filtered change history."""
        engine = WorldStateEngine()

        # Update different fields
        await engine.update_state(device_status=DeviceStatus(battery_level=100))
        await engine.update_state(
            system_resources=SystemResources(cpu_usage=50.0, memory_usage=60.0)
        )
        await engine.update_state(device_status=DeviceStatus(battery_level=90))

        # Get filtered history
        history = engine.get_change_history(field_path="device_status")
        assert len(history) >= 1  # At least one device_status change  # nosec B101
        assert all(e.field_path == "device_status" for e in history)  # nosec B101

    @pytest.mark.asyncio
    async def test_change_history_limit(self):
        """Test change history limit."""
        engine = WorldStateEngine()

        # Make many updates
        for i in range(10):
            await engine.update_state(device_status=DeviceStatus(battery_level=100 - i))

        # Get limited history
        history = engine.get_change_history(limit=5)
        assert len(history) == 5  # nosec B101

    @pytest.mark.asyncio
    async def test_no_update_if_value_unchanged(self):
        """Test that no event is generated if value doesn't change."""
        engine = WorldStateEngine()
        events_received = []

        def callback(event: StateChangeEvent):
            events_received.append(event)

        engine.subscribe_to_updates(callback)

        # Set initial value (different from default)
        device_status = DeviceStatus(battery_level=50)
        await engine.update_state(device_status=device_status)

        await asyncio.sleep(0.1)
        initial_count = len(events_received)
        assert initial_count >= 1  # nosec B101

        # Update with same value
        await engine.update_state(device_status=device_status)

        await asyncio.sleep(0.1)
        # Should still be same count (no new event)
        assert len(events_received) == initial_count  # nosec B101

    @pytest.mark.asyncio
    async def test_invalid_field_update(self):
        """Test updating invalid field is ignored."""
        engine = WorldStateEngine()

        # Try to update invalid field
        await engine.update_state(invalid_field="value")

        # Should not raise error, just log warning
        state = await engine.get_state()
        assert not hasattr(state, "invalid_field")  # nosec B101

    @pytest.mark.asyncio
    async def test_subscriber_callback_error_handling(self):
        """Test that subscriber errors don't break engine."""
        engine = WorldStateEngine()
        events_received = []

        def bad_callback(event: StateChangeEvent):
            raise ValueError("Callback error")

        def good_callback(event: StateChangeEvent):
            events_received.append(event)

        engine.subscribe_to_updates(bad_callback)
        engine.subscribe_to_updates(good_callback)

        # Trigger update - should not raise despite bad callback
        device_status = DeviceStatus(battery_level=50)
        await engine.update_state(device_status=device_status)

        await asyncio.sleep(0.1)

        # Good callback should still receive event
        assert len(events_received) == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_concurrent_updates(self):
        """Test concurrent state updates."""
        engine = WorldStateEngine()

        # Create multiple concurrent updates
        tasks = []
        for i in range(10):
            task = engine.update_state(device_status=DeviceStatus(battery_level=100 - i))
            tasks.append(task)

        # Wait for all updates
        await asyncio.gather(*tasks)

        # State should be consistent
        state = await engine.get_state()
        assert state.device_status.battery_level >= 90  # nosec B101
