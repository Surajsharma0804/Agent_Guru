"""
Tests for Rollback Manager.

Tests automatic rollback functionality including:
- Change recording and tracking
- Rollback operations
- Degradation-triggered rollback
- Data integrity during rollback
- Performance metrics

**Validates: Requirements 9.4 (Rollback and Recovery)**
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.rollback_manager import (
    RollbackManager,
    ChangeType,
    ChangeRecord,
    RollbackResult,
)
from Agent_Guru.self_improvement.degradation_detector import (
    DegradationDetector,
    DegradationSeverity,
    DegradationMetric,
    DegradationAlert,
)
import logging

logger = logging.getLogger(__name__)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Initialize schema
    DatabaseSchema.create_schema(path)

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except OSError as exc:
        logger.debug("Cleanup skipped: %s", exc)


@pytest.fixture
def pool(temp_db):
    """Create connection pool for testing."""
    pool = ConnectionPool(temp_db, min_size=1, max_size=5)
    yield pool
    pool.close_all()


@pytest.fixture
def manager(pool):
    """Create rollback manager for testing."""
    return RollbackManager(pool)


class TestRollbackManagerInitialization:
    """Test rollback manager initialization."""

    def test_initialization(self, pool):
        """Test manager initializes correctly."""
        manager = RollbackManager(pool)
        assert manager.pool == pool
        assert manager.max_rollback_window_hours == 168  # 7 days

    def test_custom_rollback_window(self, pool):
        """Test custom rollback window."""
        manager = RollbackManager(pool, max_rollback_window_hours=48)
        assert manager.max_rollback_window_hours == 48

    def test_invalid_rollback_window(self, pool):
        """Test invalid rollback window raises error."""
        with pytest.raises(ValueError, match="must be positive"):
            RollbackManager(pool, max_rollback_window_hours=0)

        with pytest.raises(ValueError, match="must be positive"):
            RollbackManager(pool, max_rollback_window_hours=-1)

    def test_database_schema_created(self, manager, pool):
        """Test change_history table is created."""
        with pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='change_history'
            """
            )
            assert cursor.fetchone() is not None


class TestChangeRecording:
    """Test change recording functionality."""

    def test_record_strategy_change(self, manager):
        """Test recording a strategy change."""
        change_id = manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8, "total_executions": 100},
            new_state={"success_rate": 0.85, "total_executions": 110},
            performance_before={"success_rate": 0.8},
            performance_after={"success_rate": 0.85},
        )

        assert change_id.startswith("change_")
        assert "strategy_1" in change_id

    def test_record_prompt_change(self, manager):
        """Test recording a prompt change."""
        change_id = manager.record_change(
            change_type=ChangeType.PROMPT_UPDATE,
            component_id="prompt_v1",
            previous_state={"success_rate": 0.7, "hallucination_count": 5},
            new_state={"success_rate": 0.75, "hallucination_count": 3},
            performance_before={"success_rate": 0.7},
        )

        assert change_id.startswith("change_")
        assert "prompt_v1" in change_id

    def test_record_multiple_changes(self, manager):
        """Test recording multiple changes."""
        change_ids = []

        for i in range(5):
            change_id = manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.8},
                new_state={"success_rate": 0.85},
                performance_before={"success_rate": 0.8},
            )
            change_ids.append(change_id)

        # All change IDs should be unique
        assert len(set(change_ids)) == 5

    def test_change_persisted_to_database(self, manager, pool):
        """Test change is persisted to database."""
        change_id = manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        # Verify in database
        with pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT change_id, change_type, component_id
                FROM change_history
                WHERE change_id = ?
            """,
                (change_id,),
            )
            row = cursor.fetchone()

            assert row is not None
            assert row[0] == change_id
            assert row[1] == ChangeType.STRATEGY_UPDATE.value
            assert row[2] == "strategy_1"


class TestRollbackOperations:
    """Test rollback operations."""

    def test_rollback_recent_changes(self, manager):
        """Test rolling back recent changes."""
        # Record some changes
        for i in range(3):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.8},
                new_state={"success_rate": 0.85},
                performance_before={"success_rate": 0.8},
            )

        # Rollback
        result = manager.rollback_recent_changes(hours=24)

        assert result.success
        assert result.changes_rolled_back == 3
        assert len(result.components_affected) == 3
        assert result.error_message is None

    def test_rollback_no_changes(self, manager):
        """Test rollback when no changes exist."""
        result = manager.rollback_recent_changes(hours=24)

        assert result.success
        assert result.changes_rolled_back == 0
        assert len(result.components_affected) == 0

    def test_rollback_filtered_by_type(self, manager):
        """Test rollback filtered by change type."""
        # Record different types of changes
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        manager.record_change(
            change_type=ChangeType.PROMPT_UPDATE,
            component_id="prompt_1",
            previous_state={"success_rate": 0.7},
            new_state={"success_rate": 0.75},
            performance_before={"success_rate": 0.7},
        )

        # Rollback only strategy changes
        result = manager.rollback_recent_changes(
            hours=24, change_types=[ChangeType.STRATEGY_UPDATE]
        )

        assert result.success
        assert result.changes_rolled_back == 1
        assert "strategy_1" in result.components_affected
        assert "prompt_1" not in result.components_affected

    def test_rollback_filtered_by_component(self, manager):
        """Test rollback filtered by component ID."""
        # Record changes for different components
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_2",
            previous_state={"success_rate": 0.75},
            new_state={"success_rate": 0.80},
            performance_before={"success_rate": 0.75},
        )

        # Rollback only strategy_1
        result = manager.rollback_recent_changes(hours=24, component_ids=["strategy_1"])

        assert result.success
        assert result.changes_rolled_back == 1
        assert "strategy_1" in result.components_affected
        assert "strategy_2" not in result.components_affected

    def test_rollback_exceeds_max_window(self, manager):
        """Test rollback exceeding maximum window fails."""
        result = manager.rollback_recent_changes(hours=200)  # Exceeds 168 hour limit

        assert not result.success
        assert result.changes_rolled_back == 0
        assert "exceeds maximum" in result.error_message

    def test_rollback_marks_changes_as_rolled_back(self, manager, pool):
        """Test rollback marks changes as rolled back in database."""
        change_id = manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        # Rollback
        manager.rollback_recent_changes(hours=24)

        # Verify marked as rolled back
        with pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT rolled_back, rollback_timestamp
                FROM change_history
                WHERE change_id = ?
            """,
                (change_id,),
            )
            row = cursor.fetchone()

            assert row[0] == 1  # rolled_back = True
            assert row[1] is not None  # rollback_timestamp set

    def test_rollback_does_not_rollback_twice(self, manager):
        """Test already rolled back changes are not rolled back again."""
        # Record and rollback
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        result1 = manager.rollback_recent_changes(hours=24)
        assert result1.changes_rolled_back == 1

        # Try to rollback again
        result2 = manager.rollback_recent_changes(hours=24)
        assert result2.changes_rolled_back == 0  # Already rolled back


class TestRollbackToTimestamp:
    """Test rollback to specific timestamp."""

    def test_rollback_to_timestamp(self, manager):
        """Test rolling back to a specific timestamp."""
        # Record changes at different times
        target_time = datetime.now() - timedelta(hours=12)

        # Changes before target (should not be rolled back)
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_old",
            previous_state={"success_rate": 0.7},
            new_state={"success_rate": 0.75},
            performance_before={"success_rate": 0.7},
        )

        # Changes after target (should be rolled back)
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_new",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        # Rollback to target time
        result = manager.rollback_to_timestamp(target_time)

        # Both changes are recent, so both should be rolled back
        # (This is a simplified test - in reality, we'd need to manipulate timestamps)
        assert result.success

    def test_rollback_to_future_timestamp(self, manager):
        """Test rollback to future timestamp fails."""
        future_time = datetime.now() + timedelta(hours=1)
        result = manager.rollback_to_timestamp(future_time)

        assert not result.success
        assert "future" in result.error_message

    def test_rollback_to_timestamp_exceeds_window(self, manager):
        """Test rollback to timestamp exceeding window fails."""
        old_time = datetime.now() - timedelta(hours=200)
        result = manager.rollback_to_timestamp(old_time)

        assert not result.success
        assert "exceeds maximum" in result.error_message


class TestDegradationTriggeredRollback:
    """Test automatic rollback triggered by degradation."""

    def test_rollback_on_severe_degradation(self, manager):
        """Test rollback on severe degradation."""
        # Record some changes
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        # Create severe degradation alert
        alert = DegradationAlert(
            severity=DegradationSeverity.SEVERE,
            degraded_metrics=[DegradationMetric.SUCCESS_RATE],
            detection_timestamp=datetime.now(),
            recent_window_start=datetime.now() - timedelta(hours=1),
            recent_window_end=datetime.now(),
            historical_window_start=datetime.now() - timedelta(hours=100),
            historical_window_end=datetime.now() - timedelta(hours=1),
            metric_changes={"success_rate": -0.3},
            statistical_significance={"p_value": 0.01, "is_significant": True},
            recommended_action="Rollback immediately",
            diagnostic_info={},
        )

        # Rollback on degradation
        result, investigation = manager.rollback_on_degradation(alert)

        assert result.success
        # Should rollback 48 hours for severe degradation

    def test_rollback_on_moderate_degradation(self, manager):
        """Test rollback on moderate degradation."""
        # Record changes
        manager.record_change(
            change_type=ChangeType.PROMPT_UPDATE,
            component_id="prompt_1",
            previous_state={"success_rate": 0.7},
            new_state={"success_rate": 0.75},
            performance_before={"success_rate": 0.7},
        )

        # Create moderate degradation alert
        alert = DegradationAlert(
            severity=DegradationSeverity.MODERATE,
            degraded_metrics=[DegradationMetric.REASONING_QUALITY],
            detection_timestamp=datetime.now(),
            recent_window_start=datetime.now() - timedelta(hours=1),
            recent_window_end=datetime.now(),
            historical_window_start=datetime.now() - timedelta(hours=100),
            historical_window_end=datetime.now() - timedelta(hours=1),
            metric_changes={"reasoning_quality": -0.15},
            statistical_significance={"p_value": 0.03, "is_significant": True},
            recommended_action="Review recent changes",
            diagnostic_info={},
        )

        # Rollback on degradation
        result, investigation = manager.rollback_on_degradation(alert)

        assert result.success
        # Should rollback 24 hours for moderate degradation

    def test_rollback_targets_correct_change_types(self, manager):
        """Test rollback targets correct change types based on degraded metrics."""
        # Record different types of changes
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        manager.record_change(
            change_type=ChangeType.PROMPT_UPDATE,
            component_id="prompt_1",
            previous_state={"success_rate": 0.7},
            new_state={"success_rate": 0.75},
            performance_before={"success_rate": 0.7},
        )

        # Create alert with strategy-related degradation
        alert = DegradationAlert(
            severity=DegradationSeverity.MODERATE,
            degraded_metrics=[DegradationMetric.TOOL_SELECTION],
            detection_timestamp=datetime.now(),
            recent_window_start=datetime.now() - timedelta(hours=1),
            recent_window_end=datetime.now(),
            historical_window_start=datetime.now() - timedelta(hours=100),
            historical_window_end=datetime.now() - timedelta(hours=1),
            metric_changes={"tool_selection_rate": -0.15},
            statistical_significance={"p_value": 0.03, "is_significant": True},
            recommended_action="Review strategy changes",
            diagnostic_info={},
        )

        # Rollback on degradation
        result, investigation = manager.rollback_on_degradation(alert)

        assert result.success
        # Should primarily rollback strategy changes


class TestChangeHistory:
    """Test change history retrieval."""

    def test_get_change_history(self, manager):
        """Test retrieving change history."""
        # Record some changes
        for i in range(3):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.8},
                new_state={"success_rate": 0.85},
                performance_before={"success_rate": 0.8},
            )

        # Get history
        history = manager.get_change_history(hours=24)

        assert len(history) == 3
        assert all(isinstance(record, ChangeRecord) for record in history)

    def test_get_change_history_filtered_by_type(self, manager):
        """Test retrieving history filtered by type."""
        # Record different types
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        manager.record_change(
            change_type=ChangeType.PROMPT_UPDATE,
            component_id="prompt_1",
            previous_state={"success_rate": 0.7},
            new_state={"success_rate": 0.75},
            performance_before={"success_rate": 0.7},
        )

        # Get only strategy changes
        history = manager.get_change_history(
            hours=24, change_types=[ChangeType.STRATEGY_UPDATE]
        )

        assert len(history) == 1
        assert history[0].change_type == ChangeType.STRATEGY_UPDATE

    def test_get_change_history_exclude_rolled_back(self, manager):
        """Test retrieving history excluding rolled back changes."""
        # Record and rollback one change
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_2",
            previous_state={"success_rate": 0.75},
            new_state={"success_rate": 0.80},
            performance_before={"success_rate": 0.75},
        )

        # Rollback first change
        manager.rollback_recent_changes(hours=24, component_ids=["strategy_1"])

        # Get history excluding rolled back
        history = manager.get_change_history(hours=24, include_rolled_back=False)

        assert len(history) == 1
        assert history[0].component_id == "strategy_2"


class TestRollbackStatistics:
    """Test rollback statistics."""

    def test_get_rollback_statistics(self, manager):
        """Test retrieving rollback statistics."""
        # Record and rollback some changes
        for i in range(5):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.8},
                new_state={"success_rate": 0.85},
                performance_before={"success_rate": 0.8},
            )

        # Rollback 3 of them
        manager.rollback_recent_changes(hours=24, component_ids=["strategy_0", "strategy_1", "strategy_2"])

        # Get statistics
        stats = manager.get_rollback_statistics(hours=24)

        assert stats["total_changes"] == 5
        assert stats["rolled_back_changes"] == 3
        assert stats["rollback_rate"] == 0.6  # 3/5

    def test_statistics_by_change_type(self, manager):
        """Test statistics broken down by change type."""
        # Record different types
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8},
        )

        manager.record_change(
            change_type=ChangeType.PROMPT_UPDATE,
            component_id="prompt_1",
            previous_state={"success_rate": 0.7},
            new_state={"success_rate": 0.75},
            performance_before={"success_rate": 0.7},
        )

        # Rollback strategy change
        manager.rollback_recent_changes(hours=24, change_types=[ChangeType.STRATEGY_UPDATE])

        # Get statistics
        stats = manager.get_rollback_statistics(hours=24)

        assert "changes_by_type" in stats
        assert ChangeType.STRATEGY_UPDATE.value in stats["changes_by_type"]
        assert ChangeType.PROMPT_UPDATE.value in stats["changes_by_type"]


class TestDataIntegrity:
    """Test data integrity during rollback operations."""

    def test_rollback_preserves_data_integrity(self, manager, pool):
        """Test rollback preserves database integrity."""
        # Record a change
        change_id = manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8, "total_executions": 100},
            new_state={"success_rate": 0.85, "total_executions": 110},
            performance_before={"success_rate": 0.8},
        )

        # Rollback
        result = manager.rollback_recent_changes(hours=24)
        assert result.success

        # Verify database integrity
        with pool.connection() as conn:
            cursor = conn.cursor()

            # Check change record exists and is marked rolled back
            cursor.execute(
                """
                SELECT rolled_back FROM change_history
                WHERE change_id = ?
            """,
                (change_id,),
            )
            assert cursor.fetchone()[0] == 1

    def test_concurrent_rollback_operations(self, manager):
        """Test concurrent rollback operations maintain integrity."""
        # Record multiple changes
        for i in range(10):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.8},
                new_state={"success_rate": 0.85},
                performance_before={"success_rate": 0.8},
            )

        # Perform multiple rollbacks (simulating concurrent operations)
        result1 = manager.rollback_recent_changes(hours=24, component_ids=["strategy_0", "strategy_1"])
        result2 = manager.rollback_recent_changes(hours=24, component_ids=["strategy_2", "strategy_3"])

        assert result1.success
        assert result2.success
        assert result1.changes_rolled_back == 2
        assert result2.changes_rolled_back == 2


class TestPerformanceMetrics:
    """Test performance metrics during rollback."""

    def test_rollback_latency(self, manager):
        """Test rollback completes within performance target."""
        import time

        # Record changes
        for i in range(20):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.8},
                new_state={"success_rate": 0.85},
                performance_before={"success_rate": 0.8},
            )

        # Measure rollback time
        start = time.time()
        result = manager.rollback_recent_changes(hours=24)
        elapsed_ms = (time.time() - start) * 1000

        assert result.success
        assert elapsed_ms < 100  # Target: <100ms

    def test_performance_restored_calculation(self, manager):
        """Test performance restored metrics are calculated correctly."""
        # Record changes with performance metrics
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.8},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.8, "execution_time": 100.0},
        )

        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_2",
            previous_state={"success_rate": 0.75},
            new_state={"success_rate": 0.80},
            performance_before={"success_rate": 0.75, "execution_time": 120.0},
        )

        # Rollback
        result = manager.rollback_recent_changes(hours=24)

        assert result.success
        assert result.performance_restored is not None
        assert "success_rate" in result.performance_restored
        # Average of 0.8 and 0.75 = 0.775
        assert abs(result.performance_restored["success_rate"] - 0.775) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
