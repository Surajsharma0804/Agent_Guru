"""
Tests for WorldState Persistence.

Coverage target: >80%
"""

import asyncio
import os
import tempfile

import pytest

from Agent_Guru.reasoning.models.world_state import DeviceStatus, SystemResources
from Agent_Guru.reasoning.state.world_state_engine import WorldStateEngine
from Agent_Guru.reasoning.state.world_state_persistence import WorldStatePersistence


class TestWorldStatePersistence:
    """Unit tests for WorldStatePersistence."""

    @pytest.fixture
    async def temp_db(self):
        """Create temporary database."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    async def persistence(self, temp_db):
        """Create persistence instance."""
        p = WorldStatePersistence(temp_db)
        await p.initialize()
        return p

    @pytest.mark.asyncio
    async def test_initialization(self, temp_db):
        """Test persistence initialization."""
        persistence = WorldStatePersistence(temp_db)
        await persistence.initialize()

        # Database file should exist
        assert os.path.exists(temp_db)  # nosec B101

    @pytest.mark.asyncio
    async def test_save_and_restore_state(self, persistence):
        """Test saving and restoring state."""
        engine = WorldStateEngine()

        # Set some state
        device_status = DeviceStatus(battery_level=75, charging=True)
        await engine.update_state(device_status=device_status)

        # Save state
        await persistence.save_state(engine)

        # Create new engine and restore
        new_engine = WorldStateEngine()
        restored = await persistence.restore_state(new_engine)

        assert restored is True  # nosec B101

        # Verify restored state
        state = await new_engine.get_state()
        assert state.device_status.battery_level == 75  # nosec B101
        assert state.device_status.charging is True  # nosec B101

    @pytest.mark.asyncio
    async def test_restore_nonexistent_state(self, persistence):
        """Test restoring when no state exists."""
        engine = WorldStateEngine()

        restored = await persistence.restore_state(engine)
        assert restored is False  # nosec B101

    @pytest.mark.asyncio
    async def test_save_with_backup(self, persistence):
        """Test saving with backup creation."""
        engine = WorldStateEngine()

        device_status = DeviceStatus(battery_level=80)
        await engine.update_state(device_status=device_status)

        # Save with backup
        await persistence.save_state(engine, create_backup=True)

        # Check backup count
        count = await persistence.get_backup_count()
        assert count == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_save_without_backup(self, persistence):
        """Test saving without backup creation."""
        engine = WorldStateEngine()

        device_status = DeviceStatus(battery_level=80)
        await engine.update_state(device_status=device_status)

        # Save without backup
        await persistence.save_state(engine, create_backup=False)

        # Check backup count
        count = await persistence.get_backup_count()
        assert count == 0  # nosec B101

    @pytest.mark.asyncio
    async def test_multiple_saves_create_backups(self, persistence):
        """Test multiple saves create multiple backups."""
        engine = WorldStateEngine()

        # Save multiple times
        for i in range(5):
            device_status = DeviceStatus(battery_level=100 - i * 10)
            await engine.update_state(device_status=device_status)
            await persistence.save_state(engine, create_backup=True)

        # Check backup count
        count = await persistence.get_backup_count()
        assert count == 5  # nosec B101

    @pytest.mark.asyncio
    async def test_get_version(self, persistence):
        """Test getting state version."""
        # No state yet
        version = await persistence.get_version()
        assert version is None  # nosec B101

        # Save state
        engine = WorldStateEngine()
        await persistence.save_state(engine)

        # Check version
        version = await persistence.get_version()
        assert version == WorldStatePersistence.CURRENT_VERSION  # nosec B101

    @pytest.mark.asyncio
    async def test_restore_from_backup(self, persistence):
        """Test restoring from specific backup."""
        engine = WorldStateEngine()

        # Create multiple backups
        for i in range(3):
            device_status = DeviceStatus(battery_level=100 - i * 20)
            await engine.update_state(device_status=device_status)
            await persistence.save_state(engine, create_backup=True)

        # Restore from first backup (battery_level=100)
        new_engine = WorldStateEngine()
        restored = await persistence.restore_from_backup(new_engine, backup_id=1)

        assert restored is True  # nosec B101

        state = await new_engine.get_state()
        assert state.device_status.battery_level == 100  # nosec B101

    @pytest.mark.asyncio
    async def test_restore_from_nonexistent_backup(self, persistence):
        """Test restoring from nonexistent backup."""
        engine = WorldStateEngine()

        restored = await persistence.restore_from_backup(engine, backup_id=999)
        assert restored is False  # nosec B101

    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, persistence):
        """Test cleaning up old backups."""
        engine = WorldStateEngine()

        # Create 15 backups
        for i in range(15):
            device_status = DeviceStatus(battery_level=100 - i)
            await engine.update_state(device_status=device_status)
            await persistence.save_state(engine, create_backup=True)
            await asyncio.sleep(0.01)  # Ensure different timestamps

        # Cleanup, keeping only 10
        deleted = await persistence.cleanup_old_backups(keep_count=10)

        assert deleted == 5  # nosec B101

        # Check remaining count
        count = await persistence.get_backup_count()
        assert count == 10  # nosec B101

    @pytest.mark.asyncio
    async def test_cleanup_with_fewer_backups(self, persistence):
        """Test cleanup when fewer backups than keep_count."""
        engine = WorldStateEngine()

        # Create 5 backups
        for i in range(5):
            device_status = DeviceStatus(battery_level=100 - i * 10)
            await engine.update_state(device_status=device_status)
            await persistence.save_state(engine, create_backup=True)

        # Cleanup, keeping 10 (more than we have)
        deleted = await persistence.cleanup_old_backups(keep_count=10)

        assert deleted == 0  # nosec B101

        # All backups should remain
        count = await persistence.get_backup_count()
        assert count == 5  # nosec B101

    @pytest.mark.asyncio
    async def test_concurrent_saves(self, persistence):
        """Test concurrent save operations."""
        engine = WorldStateEngine()

        # Create concurrent save tasks
        tasks = []
        for i in range(10):
            device_status = DeviceStatus(battery_level=100 - i)
            await engine.update_state(device_status=device_status)
            task = persistence.save_state(engine, create_backup=True)
            tasks.append(task)

        # Wait for all saves
        await asyncio.gather(*tasks)

        # All saves should succeed
        count = await persistence.get_backup_count()
        assert count == 10  # nosec B101

    @pytest.mark.asyncio
    async def test_state_with_complex_data(self, persistence):
        """Test saving and restoring complex state."""
        engine = WorldStateEngine()

        # Set complex state
        device_status = DeviceStatus(
            battery_level=85,
            charging=True,
            network_type="cellular",
            screen_state="on",
            do_not_disturb=True,
        )
        resources = SystemResources(
            cpu_usage=45.5,
            memory_usage=60.0,
            disk_space_available=5000,
        )
        await engine.update_state(
            device_status=device_status,
            system_resources=resources,
            active_apps=["app1", "app2", "app3"],
            active_tasks=["task1", "task2"],
        )

        # Save and restore
        await persistence.save_state(engine)

        new_engine = WorldStateEngine()
        await persistence.restore_state(new_engine)

        # Verify all fields
        state = await new_engine.get_state()
        assert state.device_status.battery_level == 85  # nosec B101
        assert state.device_status.charging is True  # nosec B101
        assert state.device_status.network_type == "cellular"  # nosec B101
        assert state.system_resources.cpu_usage == 45.5  # nosec B101
        assert state.system_resources.memory_usage == 60.0  # nosec B101
        assert len(state.active_apps) == 3  # nosec B101
        assert len(state.active_tasks) == 2  # nosec B101
