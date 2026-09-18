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

        # BUG FIX: this used to be `if result.performance_restored: pass` --
        # the restored-performance data was computed and immediately
        # discarded either way.
        if result.performance_restored:
            print(f"Rollback restored performance: {result.performance_restored}")
        else:
            print(f"Rolled back {result.changes_rolled_back} change(s) (success={result.success}).")

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
        # BUG FIX (crash): rollback_on_degradation() genuinely returns a
        # `tuple[RollbackResult, Any]` (the rollback result and an optional
        # root-cause investigation report) -- this used to bind the whole
        # tuple to `result` and then access `result.performance_restored`,
        # which raises AttributeError every time this function actually
        # runs (a plain tuple has no such attribute). Since this module runs
        # all 5 examples inside one try/except with no per-example recovery,
        # this silently prevented every example after this one from ever
        # running. Fixed by unpacking the real 2-tuple.
        result, _investigation = manager.rollback_on_degradation(alert)

        # BUG FIX (no-op): this loop used to be `pass` -- the restored
        # per-metric performance values were computed and discarded.
        if result.performance_restored:
            print(f"Degradation rollback restored {result.changes_rolled_back} change(s):")
            for _metric, _value in result.performance_restored.items():
                print(f"  - {_metric}: {_value:.2f}")

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
        # BUG FIX: this used to be a bare list-comprehension expression
        # statement -- the filtered list was computed and immediately
        # discarded, so the verification never actually reported anything.
        history = manager.get_change_history(hours=24, include_rolled_back=False)
        remaining_prompt_changes = [h for h in history if h.change_type == ChangeType.PROMPT_UPDATE]
        print(f"Prompt changes not rolled back: {len(remaining_prompt_changes)} (expected 1).")

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
        # BUG FIX: both loops below used to be `pass` no-ops -- the
        # per-type breakdown and per-component rollback counts were
        # computed via real queries but never shown. Restored.
        stats = manager.get_rollback_statistics(hours=24)
        print(
            f"Rollback stats: {stats['rolled_back_changes']}/{stats['total_changes']} "
            f"changes rolled back ({stats['rollback_rate']:.0%}).",
        )

        if stats["changes_by_type"]:
            print("Changes by type:")
            for _change_type, _counts in stats["changes_by_type"].items():
                print(
                    f"  - {_change_type}: {_counts['total']} total, "
                    f"{_counts['rolled_back']} rolled back",
                )

        if stats["most_rolled_back_components"]:
            print("Most rolled back components:")
            for _component in stats["most_rolled_back_components"][:5]:
                print(f"  - {_component['component_id']}: {_component['count']} rollback(s)")

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
        # BUG FIX: this loop used to check `record.performance_before`/
        # `record.performance_after` and discard both via `pass` -- the
        # real per-record performance data was computed but never shown.
        # A record status header was also added since the before/after
        # prints are meaningless without identifying which record they
        # belong to.
        history = manager.get_change_history(hours=24, include_rolled_back=True)
        print(f"Change history ({len(history)} record(s), including rolled back):")

        for record in history:
            status = "rolled back" if record.rolled_back else "active"
            print(f"  - {record.component_id} ({record.change_type.value}, {status})")
            if record.performance_before:
                print(f"      before: {record.performance_before}")
            if record.performance_after:
                print(f"      after: {record.performance_after}")

        # View only active changes
        # BUG FIX: this loop used to be `pass` -- restored.
        active_history = manager.get_change_history(hours=24, include_rolled_back=False)
        print(f"Active (not rolled back) changes: {len(active_history)}")
        for _record in active_history:
            print(f"  - {_record.component_id}")

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
