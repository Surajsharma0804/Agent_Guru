"""Example: Automatic Rollback System.

Demonstrates how the rollback manager automatically reverts changes
when performance degradation is detected.

This example shows:
1. Recording changes to strategies and prompts
2. Detecting performance degradation
3. Automatically rolling back recent changes
4. Verifying rollback restored performance
5. Analyzing rollback statistics

Author: Agent Guru Team
Date: 2026-02-28
"""

import os
import tempfile
from datetime import UTC, datetime, timedelta

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.degradation_detector import (
    DegradationAlert,
    DegradationMetric,
    DegradationSeverity,
)
from Agent_Guru.self_improvement.rollback_manager import (
    ChangeType,
    RollbackManager,
)


def example_basic_rollback() -> None:
    """Example 1: Basic rollback of recent changes."""
    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record some strategy changes
        for i in range(3):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={
                    "success_rate": 0.80,
                    "total_executions": 100,
                },
                new_state={
                    "success_rate": 0.85,
                    "total_executions": 110,
                },
                performance_before={"success_rate": 0.80},
                performance_after={"success_rate": 0.85},
            )

        # Rollback recent changes
        result = manager.rollback_recent_changes(hours=24)

        if result.performance_restored:
            pass

        pool.close_all()

    finally:
        os.unlink(db_path)


def example_degradation_triggered_rollback() -> None:
    """Example 2: Rollback triggered by performance degradation."""
    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record changes that caused degradation
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_bad",
            previous_state={"success_rate": 0.85},
            new_state={"success_rate": 0.60},  # Degraded!
            performance_before={"success_rate": 0.85},
            performance_after={"success_rate": 0.60},
        )

        manager.record_change(
            change_type=ChangeType.PROMPT_UPDATE,
            component_id="prompt_bad",
            previous_state={"success_rate": 0.80, "hallucination_count": 2},
            new_state={"success_rate": 0.65, "hallucination_count": 10},  # Degraded!
            performance_before={"success_rate": 0.80},
            performance_after={"success_rate": 0.65},
        )

        # Create degradation alert
        alert = DegradationAlert(
            severity=DegradationSeverity.SEVERE,
            degraded_metrics=[
                DegradationMetric.SUCCESS_RATE,
                DegradationMetric.HALLUCINATION_RATE,
            ],
            detection_timestamp=datetime.now(tz=UTC),
            recent_window_start=datetime.now(tz=UTC) - timedelta(hours=1),
            recent_window_end=datetime.now(tz=UTC),
            historical_window_start=datetime.now(tz=UTC) - timedelta(hours=100),
            historical_window_end=datetime.now(tz=UTC) - timedelta(hours=1),
            metric_changes={
                "success_rate": -0.25,
                "hallucination_rate": 0.15,
            },
            statistical_significance={
                "p_value": 0.001,
                "is_significant": True,
                "cohens_d": -1.5,
            },
            recommended_action="Immediate rollback recommended",
            diagnostic_info={},
        )

        # Automatic rollback based on degradation
        result = manager.rollback_on_degradation(alert)

        if result.performance_restored:
            for _metric, _value in result.performance_restored.items():
                pass

        pool.close_all()

    finally:
        os.unlink(db_path)


def example_selective_rollback() -> None:
    """Example 3: Selective rollback by component type."""
    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record different types of changes
        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_1",
            previous_state={"success_rate": 0.80},
            new_state={"success_rate": 0.85},
            performance_before={"success_rate": 0.80},
        )

        manager.record_change(
            change_type=ChangeType.PROMPT_UPDATE,
            component_id="prompt_1",
            previous_state={"success_rate": 0.75},
            new_state={"success_rate": 0.80},
            performance_before={"success_rate": 0.75},
        )

        manager.record_change(
            change_type=ChangeType.STRATEGY_UPDATE,
            component_id="strategy_2",
            previous_state={"success_rate": 0.78},
            new_state={"success_rate": 0.82},
            performance_before={"success_rate": 0.78},
        )

        # Rollback only strategy changes
        manager.rollback_recent_changes(
            hours=24,
            change_types=[ChangeType.STRATEGY_UPDATE],
        )

        # Verify prompt change was not rolled back
        history = manager.get_change_history(hours=24, include_rolled_back=False)
        [h for h in history if h.change_type == ChangeType.PROMPT_UPDATE]

        pool.close_all()

    finally:
        os.unlink(db_path)


def example_rollback_statistics() -> None:
    """Example 4: Analyzing rollback statistics."""
    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record and rollback some changes
        for i in range(10):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.80},
                new_state={"success_rate": 0.85},
                performance_before={"success_rate": 0.80},
            )

        # Rollback half of them
        manager.rollback_recent_changes(
            hours=24,
            component_ids=[f"strategy_{i}" for i in range(5)],
        )

        # Get statistics
        stats = manager.get_rollback_statistics(hours=24)

        if stats["changes_by_type"]:
            for _counts in stats["changes_by_type"].values():
                pass

        if stats["most_rolled_back_components"]:
            for _component in stats["most_rolled_back_components"][:5]:
                pass

        pool.close_all()

    finally:
        os.unlink(db_path)


def example_change_history() -> None:
    """Example 5: Viewing change history."""
    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record some changes
        for i in range(5):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.80 + i * 0.01},
                new_state={"success_rate": 0.85 + i * 0.01},
                performance_before={"success_rate": 0.80 + i * 0.01},
                performance_after={"success_rate": 0.85 + i * 0.01},
            )

        # Rollback some
        manager.rollback_recent_changes(hours=24, component_ids=["strategy_0", "strategy_2"])

        # View history
        history = manager.get_change_history(hours=24, include_rolled_back=True)

        for record in history:
            if record.performance_before:
                pass
            if record.performance_after:
                pass

        # View only active changes
        active_history = manager.get_change_history(hours=24, include_rolled_back=False)
        for _record in active_history:
            pass

        pool.close_all()

    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    try:
        example_basic_rollback()
        example_degradation_triggered_rollback()
        example_selective_rollback()
        example_rollback_statistics()
        example_change_history()

    except Exception:
        import traceback

        traceback.print_exc()
