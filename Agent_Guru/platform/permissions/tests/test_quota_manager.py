"""
Tests for Agent_Guru.platform.permissions.quota_manager
Coverage Target: >80% (enforced by CI/CD)
"""

import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json
from hypothesis import given, strategies as st

from Agent_Guru.platform.permissions.quota_manager import (
    QuotaManager,
    QuotaConfig,
    QuotaStatus,
    OperationType,
    UserQuotaCounters,
    QuotaExceededException
)


class TestQuotaConfig:
    """Unit tests for QuotaConfig."""
    
    def test_valid_config(self):
        """Test valid quota configuration."""
        config = QuotaConfig(per_hour=100, per_day=1000)
        assert config.per_hour == 100
        assert config.per_day == 1000
    
    def test_invalid_per_hour(self):
        """Test invalid per_hour value."""
        with pytest.raises(ValueError, match="per_hour must be positive"):
            QuotaConfig(per_hour=0, per_day=1000)
        
        with pytest.raises(ValueError, match="per_hour must be positive"):
            QuotaConfig(per_hour=-1, per_day=1000)
    
    def test_invalid_per_day(self):
        """Test invalid per_day value."""
        with pytest.raises(ValueError, match="per_day must be positive"):
            QuotaConfig(per_hour=100, per_day=0)
        
        with pytest.raises(ValueError, match="per_day must be positive"):
            QuotaConfig(per_hour=100, per_day=-1)
    
    def test_per_day_less_than_per_hour(self):
        """Test per_day < per_hour validation."""
        with pytest.raises(ValueError, match="per_day.*must be >= per_hour"):
            QuotaConfig(per_hour=1000, per_day=100)


class TestQuotaStatus:
    """Unit tests for QuotaStatus."""
    
    def test_hour_remaining(self):
        """Test hour_remaining calculation."""
        status = QuotaStatus(
            operation_type=OperationType.FILE_OPERATION,
            current_hour=50,
            current_day=500,
            limit_hour=100,
            limit_day=1000,
            available=True,
            reset_hour_at=datetime.now() + timedelta(hours=1),
            reset_day_at=datetime.now() + timedelta(days=1)
        )
        assert status.hour_remaining == 50
    
    def test_day_remaining(self):
        """Test day_remaining calculation."""
        status = QuotaStatus(
            operation_type=OperationType.FILE_OPERATION,
            current_hour=50,
            current_day=500,
            limit_hour=100,
            limit_day=1000,
            available=True,
            reset_hour_at=datetime.now() + timedelta(hours=1),
            reset_day_at=datetime.now() + timedelta(days=1)
        )
        assert status.day_remaining == 500
    
    def test_hour_exceeded(self):
        """Test hour_exceeded property."""
        status = QuotaStatus(
            operation_type=OperationType.FILE_OPERATION,
            current_hour=100,
            current_day=500,
            limit_hour=100,
            limit_day=1000,
            available=False,
            reset_hour_at=datetime.now() + timedelta(hours=1),
            reset_day_at=datetime.now() + timedelta(days=1)
        )
        assert status.hour_exceeded is True
    
    def test_day_exceeded(self):
        """Test day_exceeded property."""
        status = QuotaStatus(
            operation_type=OperationType.FILE_OPERATION,
            current_hour=50,
            current_day=1000,
            limit_hour=100,
            limit_day=1000,
            available=False,
            reset_hour_at=datetime.now() + timedelta(hours=1),
            reset_day_at=datetime.now() + timedelta(days=1)
        )
        assert status.day_exceeded is True
    
    def test_to_dict(self):
        """Test to_dict serialization."""
        now = datetime.now()
        status = QuotaStatus(
            operation_type=OperationType.FILE_OPERATION,
            current_hour=50,
            current_day=500,
            limit_hour=100,
            limit_day=1000,
            available=True,
            reset_hour_at=now + timedelta(hours=1),
            reset_day_at=now + timedelta(days=1)
        )
        
        data = status.to_dict()
        assert data["operation_type"] == "file_operation"
        assert data["current_hour"] == 50
        assert data["current_day"] == 500
        assert data["hour_remaining"] == 50
        assert data["day_remaining"] == 500
        assert data["available"] is True


class TestUserQuotaCounters:
    """Unit tests for UserQuotaCounters."""
    
    def test_initialization(self):
        """Test counter initialization."""
        counters = UserQuotaCounters()
        
        for op_type in OperationType:
            assert counters.get_hour_count(op_type) == 0
            assert counters.get_day_count(op_type) == 0
    
    def test_increment(self):
        """Test counter increment."""
        counters = UserQuotaCounters()
        
        counters.increment(OperationType.FILE_OPERATION)
        assert counters.get_hour_count(OperationType.FILE_OPERATION) == 1
        assert counters.get_day_count(OperationType.FILE_OPERATION) == 1
        
        counters.increment(OperationType.FILE_OPERATION)
        assert counters.get_hour_count(OperationType.FILE_OPERATION) == 2
        assert counters.get_day_count(OperationType.FILE_OPERATION) == 2
    
    def test_reset_hour(self):
        """Test hourly reset."""
        counters = UserQuotaCounters()
        
        counters.increment(OperationType.FILE_OPERATION)
        counters.increment(OperationType.COMMAND_EXECUTION)
        
        counters.reset_hour()
        
        assert counters.get_hour_count(OperationType.FILE_OPERATION) == 0
        assert counters.get_day_count(OperationType.FILE_OPERATION) == 1
        assert counters.get_hour_count(OperationType.COMMAND_EXECUTION) == 0
        assert counters.get_day_count(OperationType.COMMAND_EXECUTION) == 1
    
    def test_reset_day(self):
        """Test daily reset."""
        counters = UserQuotaCounters()
        
        counters.increment(OperationType.FILE_OPERATION)
        counters.increment(OperationType.COMMAND_EXECUTION)
        
        counters.reset_day()
        
        assert counters.get_hour_count(OperationType.FILE_OPERATION) == 0
        assert counters.get_day_count(OperationType.FILE_OPERATION) == 0
        assert counters.get_hour_count(OperationType.COMMAND_EXECUTION) == 0
        assert counters.get_day_count(OperationType.COMMAND_EXECUTION) == 0


class TestQuotaManager:
    """Unit tests for QuotaManager."""
    
    @pytest.fixture
    def quota_configs(self):
        """Create test quota configurations."""
        return {
            OperationType.FILE_OPERATION: QuotaConfig(per_hour=100, per_day=1000),
            OperationType.COMMAND_EXECUTION: QuotaConfig(per_hour=50, per_day=500),
            OperationType.NETWORK_REQUEST: QuotaConfig(per_hour=1000, per_day=10000)
        }
    
    @pytest.fixture
    def manager(self, quota_configs):
        """Create test quota manager."""
        return QuotaManager(quota_configs)
    
    def test_initialization(self, quota_configs):
        """Test manager initialization."""
        manager = QuotaManager(quota_configs)
        assert manager.quota_configs == quota_configs
        assert len(manager._user_quotas) == 0
    
    def test_initialization_empty_config(self):
        """Test initialization with empty config."""
        with pytest.raises(ValueError, match="quota_configs cannot be empty"):
            QuotaManager({})
    
    def test_check_and_consume_first_operation(self, manager):
        """Test first operation consumes quota."""
        status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        
        assert status.available is True
        assert status.current_hour == 1
        assert status.current_day == 1
        assert status.hour_remaining == 99
        assert status.day_remaining == 999
    
    def test_check_and_consume_multiple_operations(self, manager):
        """Test multiple operations consume quota."""
        for i in range(5):
            status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
            assert status.available is True
            assert status.current_hour == i + 1
            assert status.current_day == i + 1
    
    def test_check_and_consume_hour_limit(self, manager):
        """Test hourly limit enforcement."""
        # Consume up to limit
        for i in range(100):
            status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
            assert status.available is True
        
        # Next operation should fail
        status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        assert status.available is False
        assert status.hour_exceeded is True
        assert status.current_hour == 100
    
    def test_check_and_consume_day_limit(self, manager):
        """Test daily limit enforcement."""
        # This test needs to simulate multiple hours to reach daily limit
        # without hitting hourly limit each time.
        
        # Consume 100 operations per hour for 10 hours = 1000 operations
        for hour in range(10):
            # Consume 100 operations (hourly limit)
            for i in range(100):
                status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
                assert status.available is True
            
            # Simulate hour passing - manually reset hourly counter
            if hour < 9:  # Don't reset after last hour
                manager._last_hour_reset = datetime.now() - timedelta(hours=1)
                manager._reset_quotas_if_needed()
        
        # Next operation should fail (daily limit reached)
        status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        assert status.available is False
        assert status.day_exceeded is True
        assert status.current_day == 1000
    
    def test_check_and_consume_raise_on_exceeded(self, manager):
        """Test exception raising when quota exceeded."""
        # Consume up to limit
        for i in range(100):
            manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        
        # Next operation should raise exception
        with pytest.raises(QuotaExceededException) as exc_info:
            manager.check_and_consume(
                "user123",
                OperationType.FILE_OPERATION,
                raise_on_exceeded=True
            )
        
        assert exc_info.value.status.hour_exceeded is True
    
    def test_get_status_without_consuming(self, manager):
        """Test getting status without consuming quota."""
        # Consume some quota
        manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        
        # Get status without consuming
        status = manager.get_status("user123", OperationType.FILE_OPERATION)
        assert status.current_hour == 2
        assert status.current_day == 2
        
        # Verify quota not consumed
        status2 = manager.get_status("user123", OperationType.FILE_OPERATION)
        assert status2.current_hour == 2
        assert status2.current_day == 2
    
    def test_get_all_statuses(self, manager):
        """Test getting all statuses for a user."""
        # Consume different amounts for each operation type
        manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        manager.check_and_consume("user123", OperationType.COMMAND_EXECUTION)
        
        statuses = manager.get_all_statuses("user123")
        
        assert len(statuses) == 3
        assert statuses[OperationType.FILE_OPERATION].current_hour == 2
        assert statuses[OperationType.COMMAND_EXECUTION].current_hour == 1
        assert statuses[OperationType.NETWORK_REQUEST].current_hour == 0
    
    def test_reset_user_quotas(self, manager):
        """Test resetting user quotas."""
        # Consume some quota
        manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        manager.check_and_consume("user123", OperationType.COMMAND_EXECUTION)
        
        # Reset quotas
        manager.reset_user_quotas("user123")
        
        # Verify reset
        status1 = manager.get_status("user123", OperationType.FILE_OPERATION)
        status2 = manager.get_status("user123", OperationType.COMMAND_EXECUTION)
        
        assert status1.current_hour == 0
        assert status1.current_day == 0
        assert status2.current_hour == 0
        assert status2.current_day == 0
    
    def test_multiple_users(self, manager):
        """Test quota tracking for multiple users."""
        # User 1 consumes quota
        manager.check_and_consume("user1", OperationType.FILE_OPERATION)
        manager.check_and_consume("user1", OperationType.FILE_OPERATION)
        
        # User 2 consumes quota
        manager.check_and_consume("user2", OperationType.FILE_OPERATION)
        
        # Verify separate tracking
        status1 = manager.get_status("user1", OperationType.FILE_OPERATION)
        status2 = manager.get_status("user2", OperationType.FILE_OPERATION)
        
        assert status1.current_hour == 2
        assert status2.current_hour == 1
    
    def test_get_statistics(self, manager):
        """Test statistics generation."""
        # Consume quota for multiple users
        manager.check_and_consume("user1", OperationType.FILE_OPERATION)
        manager.check_and_consume("user1", OperationType.FILE_OPERATION)
        manager.check_and_consume("user2", OperationType.FILE_OPERATION)
        manager.check_and_consume("user2", OperationType.COMMAND_EXECUTION)
        
        stats = manager.get_statistics()
        
        assert stats["total_users"] == 2
        assert stats["per_operation_stats"]["file_operation"]["total_hour"] == 3
        assert stats["per_operation_stats"]["command_execution"]["total_hour"] == 1


class TestQuotaManagerPersistence:
    """Unit tests for quota persistence."""
    
    @pytest.fixture
    def quota_configs(self):
        """Create test quota configurations."""
        return {
            OperationType.FILE_OPERATION: QuotaConfig(per_hour=100, per_day=1000),
            OperationType.COMMAND_EXECUTION: QuotaConfig(per_hour=50, per_day=500),
            OperationType.NETWORK_REQUEST: QuotaConfig(per_hour=1000, per_day=10000)
        }
    
    @pytest.fixture
    def storage_path(self):
        """Create temporary storage path."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()
    
    def test_save_and_load(self, quota_configs, storage_path):
        """Test saving and loading quota counters."""
        # Create manager and consume quota
        manager1 = QuotaManager(quota_configs, storage_path=storage_path)
        manager1.check_and_consume("user123", OperationType.FILE_OPERATION)
        manager1.check_and_consume("user123", OperationType.FILE_OPERATION)
        manager1.check_and_consume("user123", OperationType.COMMAND_EXECUTION)
        
        # Create new manager with same storage
        manager2 = QuotaManager(quota_configs, storage_path=storage_path)
        
        # Verify loaded state
        status1 = manager2.get_status("user123", OperationType.FILE_OPERATION)
        status2 = manager2.get_status("user123", OperationType.COMMAND_EXECUTION)
        
        assert status1.current_hour == 2
        assert status1.current_day == 2
        assert status2.current_hour == 1
        assert status2.current_day == 1
    
    def test_storage_format(self, quota_configs, storage_path):
        """Test storage file format."""
        manager = QuotaManager(quota_configs, storage_path=storage_path)
        manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        
        # Read storage file
        with open(storage_path, 'r') as f:
            data = json.load(f)
        
        assert "last_hour_reset" in data
        assert "last_day_reset" in data
        assert "user_quotas" in data
        assert "user123" in data["user_quotas"]
        assert "file_operation" in data["user_quotas"]["user123"]


class TestQuotaManagerProperties:
    """Property-based tests for QuotaManager."""
    
    @given(
        per_hour=st.integers(min_value=1, max_value=10000),
        per_day=st.integers(min_value=1, max_value=100000)
    )
    def test_valid_config_always_works(self, per_hour, per_day):
        """Property: Valid config always creates manager."""
        # Ensure per_day >= per_hour
        if per_day < per_hour:
            per_day = per_hour
        
        config = {
            OperationType.FILE_OPERATION: QuotaConfig(per_hour=per_hour, per_day=per_day)
        }
        manager = QuotaManager(config)
        
        assert manager is not None
    
    @given(
        operations=st.integers(min_value=1, max_value=100)
    )
    def test_quota_consumption_monotonic(self, operations):
        """Property: Quota consumption is monotonically increasing."""
        config = {
            OperationType.FILE_OPERATION: QuotaConfig(per_hour=1000, per_day=10000)
        }
        manager = QuotaManager(config)
        
        prev_count = 0
        for i in range(operations):
            status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
            assert status.current_hour == prev_count + 1
            assert status.current_day == prev_count + 1
            prev_count = status.current_hour
    
    @given(
        user_id=st.text(min_size=1, max_size=50)
    )
    def test_user_isolation(self, user_id):
        """Property: Users have isolated quota counters."""
        config = {
            OperationType.FILE_OPERATION: QuotaConfig(per_hour=100, per_day=1000)
        }
        manager = QuotaManager(config)
        
        # Consume quota for user
        manager.check_and_consume(user_id, OperationType.FILE_OPERATION)
        
        # Verify other users unaffected
        status_other = manager.get_status("other_user", OperationType.FILE_OPERATION)
        assert status_other.current_hour == 0
        assert status_other.current_day == 0


@pytest.mark.integration
class TestQuotaManagerIntegration:
    """Integration tests for QuotaManager."""
    
    def test_quota_reset_integration(self):
        """Test quota reset in realistic scenario."""
        config = {
            OperationType.FILE_OPERATION: QuotaConfig(per_hour=10, per_day=100)
        }
        manager = QuotaManager(config)
        
        # Consume quota
        for i in range(10):
            status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
            assert status.available is True
        
        # Quota should be exhausted
        status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        assert status.available is False
        
        # Simulate hour passing (manually reset for testing)
        manager._last_hour_reset = datetime.now() - timedelta(hours=1)
        manager._reset_quotas_if_needed()
        
        # Quota should be available again
        status = manager.check_and_consume("user123", OperationType.FILE_OPERATION)
        assert status.available is True
        assert status.current_hour == 1
    
    def test_concurrent_users_integration(self):
        """Test multiple users consuming quota concurrently."""
        config = {
            OperationType.FILE_OPERATION: QuotaConfig(per_hour=100, per_day=1000),
            OperationType.COMMAND_EXECUTION: QuotaConfig(per_hour=50, per_day=500),
            OperationType.NETWORK_REQUEST: QuotaConfig(per_hour=1000, per_day=10000)
        }
        manager = QuotaManager(config)
        
        # Simulate multiple users
        users = [f"user{i}" for i in range(10)]
        
        for user in users:
            for _ in range(5):
                manager.check_and_consume(user, OperationType.FILE_OPERATION)
                manager.check_and_consume(user, OperationType.COMMAND_EXECUTION)
                manager.check_and_consume(user, OperationType.NETWORK_REQUEST)
        
        # Verify statistics
        stats = manager.get_statistics()
        assert stats["total_users"] == 10
        assert stats["per_operation_stats"]["file_operation"]["total_hour"] == 50
        assert stats["per_operation_stats"]["command_execution"]["total_hour"] == 50
        assert stats["per_operation_stats"]["network_request"]["total_hour"] == 50
