"""
Example: Automatic Rollback System

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
from datetime import datetime, timedelta

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


def example_basic_rollback():
    """Example 1: Basic rollback of recent changes."""
    print("\n=== Example 1: Basic Rollback ===\n")

    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record some strategy changes
        print("Recording strategy changes...")
        for i in range(3):
            change_id = manager.record_change(
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
            print(f"  ✓ Recorded change: {change_id}")

        # Rollback recent changes
        print("\nRolling back changes from last 24 hours...")
        result = manager.rollback_recent_changes(hours=24)

        print(f"  ✓ Success: {result.success}")
        print(f"  ✓ Changes rolled back: {result.changes_rolled_back}")
        print(f"  ✓ Components affected: {result.components_affected}")
        if result.performance_restored:
            print(f"  ✓ Performance restored: {result.performance_restored}")

        pool.close_all()

    finally:
        os.unlink(db_path)


def example_degradation_triggered_rollback():
    """Example 2: Rollback triggered by performance degradation."""
    print("\n=== Example 2: Degradation-Triggered Rollback ===\n")

    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record changes that caused degradation
        print("Recording changes...")
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

        print("  ✓ Recorded 2 changes that caused degradation")

        # Create degradation alert
        print("\nDetecting performance degradation...")
        alert = DegradationAlert(
            severity=DegradationSeverity.SEVERE,
            degraded_metrics=[
                DegradationMetric.SUCCESS_RATE,
                DegradationMetric.HALLUCINATION_RATE,
            ],
            detection_timestamp=datetime.now(),
            recent_window_start=datetime.now() - timedelta(hours=1),
            recent_window_end=datetime.now(),
            historical_window_start=datetime.now() - timedelta(hours=100),
            historical_window_end=datetime.now() - timedelta(hours=1),
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

        print(f"  ✓ Severity: {alert.severity.value}")
        print(f"  ✓ Degraded metrics: {[m.value for m in alert.degraded_metrics]}")
        print(f"  ✓ Recommendation: {alert.recommended_action}")

        # Automatic rollback based on degradation
        print("\nTriggering automatic rollback...")
        result = manager.rollback_on_degradation(alert)

        print(f"  ✓ Success: {result.success}")
        print(f"  ✓ Changes rolled back: {result.changes_rolled_back}")
        print(f"  ✓ Components affected: {result.components_affected}")
        if result.performance_restored:
            print("  ✓ Performance restored:")
            for metric, value in result.performance_restored.items():
                print(f"      - {metric}: {value:.2f}")

        pool.close_all()

    finally:
        os.unlink(db_path)


def example_selective_rollback():
    """Example 3: Selective rollback by component type."""
    print("\n=== Example 3: Selective Rollback ===\n")

    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record different types of changes
        print("Recording mixed changes...")
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

        print("  ✓ Recorded 2 strategy changes and 1 prompt change")

        # Rollback only strategy changes
        print("\nRolling back only strategy changes...")
        result = manager.rollback_recent_changes(
            hours=24, change_types=[ChangeType.STRATEGY_UPDATE]
        )

        print(f"  ✓ Success: {result.success}")
        print(f"  ✓ Changes rolled back: {result.changes_rolled_back}")
        print(f"  ✓ Components affected: {result.components_affected}")

        # Verify prompt change was not rolled back
        history = manager.get_change_history(hours=24, include_rolled_back=False)
        prompt_changes = [
            h for h in history if h.change_type == ChangeType.PROMPT_UPDATE
        ]
        print(f"  ✓ Prompt changes still active: {len(prompt_changes)}")

        pool.close_all()

    finally:
        os.unlink(db_path)


def example_rollback_statistics():
    """Example 4: Analyzing rollback statistics."""
    print("\n=== Example 4: Rollback Statistics ===\n")

    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record and rollback some changes
        print("Recording changes...")
        for i in range(10):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.80},
                new_state={"success_rate": 0.85},
                performance_before={"success_rate": 0.80},
            )

        print("  ✓ Recorded 10 strategy changes")

        # Rollback half of them
        print("\nRolling back 5 changes...")
        manager.rollback_recent_changes(
            hours=24,
            component_ids=[f"strategy_{i}" for i in range(5)],
        )

        # Get statistics
        print("\nRollback Statistics:")
        stats = manager.get_rollback_statistics(hours=24)

        print(f"  ✓ Total changes: {stats['total_changes']}")
        print(f"  ✓ Rolled back: {stats['rolled_back_changes']}")
        print(f"  ✓ Rollback rate: {stats['rollback_rate']:.1%}")

        if stats["changes_by_type"]:
            print("\n  Changes by type:")
            for change_type, counts in stats["changes_by_type"].items():
                print(f"    - {change_type}:")
                print(f"        Total: {counts['total']}")
                print(f"        Rolled back: {counts['rolled_back']}")

        if stats["most_rolled_back_components"]:
            print("\n  Most rolled back components:")
            for component in stats["most_rolled_back_components"][:5]:
                print(f"    - {component['component_id']}: {component['count']} rollbacks")

        pool.close_all()

    finally:
        os.unlink(db_path)


def example_change_history():
    """Example 5: Viewing change history."""
    print("\n=== Example 5: Change History ===\n")

    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize
        DatabaseSchema.create_schema(db_path)
        pool = ConnectionPool(db_path, min_size=1, max_size=5)
        manager = RollbackManager(pool)

        # Record some changes
        print("Recording changes...")
        for i in range(5):
            manager.record_change(
                change_type=ChangeType.STRATEGY_UPDATE,
                component_id=f"strategy_{i}",
                previous_state={"success_rate": 0.80 + i * 0.01},
                new_state={"success_rate": 0.85 + i * 0.01},
                performance_before={"success_rate": 0.80 + i * 0.01},
                performance_after={"success_rate": 0.85 + i * 0.01},
            )

        print("  ✓ Recorded 5 changes")

        # Rollback some
        manager.rollback_recent_changes(
            hours=24, component_ids=["strategy_0", "strategy_2"]
        )

        # View history
        print("\nChange History (all changes):")
        history = manager.get_change_history(hours=24, include_rolled_back=True)

        for record in history:
            status = "ROLLED BACK" if record.rolled_back else "ACTIVE"
            print(f"  - {record.component_id}: {status}")
            print(f"      Type: {record.change_type.value}")
            print(f"      Timestamp: {record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            if record.performance_before:
                print(f"      Performance before: {record.performance_before}")
            if record.performance_after:
                print(f"      Performance after: {record.performance_after}")

        # View only active changes
        print("\nActive Changes (not rolled back):")
        active_history = manager.get_change_history(
            hours=24, include_rolled_back=False
        )
        print(f"  ✓ {len(active_history)} active changes")
        for record in active_history:
            print(f"    - {record.component_id}")

        pool.close_all()

    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    print("=" * 60)
    print("Automatic Rollback System Examples")
    print("=" * 60)

    try:
        example_basic_rollback()
        example_degradation_triggered_rollback()
        example_selective_rollback()
        example_rollback_statistics()
        example_change_history()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
