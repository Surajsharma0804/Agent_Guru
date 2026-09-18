"""Example usage of the migration system.

This script demonstrates:
- Creating a database with initial schema
- Checking migration status
- Applying migrations
- Rolling back migrations
- Viewing migration history
"""

import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.migrations import MigrationSystem, migrate_database


def example_basic_usage() -> None:
    """Example: Basic migration usage."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = f.name

    try:
        # Initialize database with base schema
        DatabaseSchema.create_schema(db_path)

        # Simple migration to latest
        migrate_database(db_path)

        # Check status
        # BUG FIX: the status dict used to be computed and immediately
        # discarded -- restored.
        system = MigrationSystem(db_path)
        status = system.get_migration_status()
        print(
            f"Status: current={status['current_version']}, "
            f"latest={status['latest_version']}, "
            f"up_to_date={status['is_up_to_date']}",
        )

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def example_step_by_step() -> None:
    """Example: Step-by-step migration."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = f.name

    try:
        # Initialize database
        DatabaseSchema.create_schema(db_path)

        # Create migration system
        system = MigrationSystem(db_path)

        # Show initial status
        status = system.get_migration_status()
        print(
            f"Initial status: current={status['current_version']}, "
            f"latest={status['latest_version']}",
        )

        # Show pending migrations
        # BUG FIX: this loop used to be `pass` -- the pending migrations
        # were computed via a real query but never shown. Restored.
        if status["pending_migrations"]:
            print(f"Pending migrations ({len(status['pending_migrations'])}):")
            for _m in status["pending_migrations"]:
                print(f"  - v{_m['version']}: {_m['description']}")

        # Apply migrations one by one
        for version in range(1, status["latest_version"] + 1):
            system.migrate_to_version(version)

        # Show final status
        # BUG FIX: this result used to be computed and immediately
        # discarded -- restored.
        status = system.get_migration_status()
        print(
            f"Final status: current={status['current_version']}, "
            f"latest={status['latest_version']}, "
            f"up_to_date={status['is_up_to_date']}",
        )

        # Show applied migrations
        # BUG FIX: identical `pass` no-op pattern as the pending-migrations
        # loop above -- restored.
        applied = system.get_applied_migrations()
        print(f"Applied migrations ({len(applied)}):")
        for _version, _description, _applied_at in applied:
            print(f"  - v{_version}: {_description} (applied at {_applied_at})")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def example_rollback() -> None:
    """Example: Rolling back migrations."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = f.name

    try:
        # Initialize and migrate to latest
        DatabaseSchema.create_schema(db_path)

        system = MigrationSystem(db_path)
        # BUG FIX: the latest-version number used to be computed and
        # immediately discarded -- restored.
        latest_version = system.get_latest_version()
        print(f"Latest available version: {latest_version}")

        system.migrate_to_latest()

        # Rollback to version 2
        system.migrate_to_version(2)

        # Show current migrations
        # BUG FIX: this loop used to be `pass` -- restored, same pattern as
        # example_step_by_step() above.
        applied = system.get_applied_migrations()
        print(f"Applied migrations after rollback ({len(applied)}):")
        for _version, _description, _applied_at in applied:
            print(f"  - v{_version}: {_description} (applied at {_applied_at})")

        # Migrate forward again
        system.migrate_to_latest()

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def example_error_handling() -> None:
    """Example: Error handling."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = f.name

    try:
        # Initialize database
        DatabaseSchema.create_schema(db_path)

        system = MigrationSystem(db_path)

        # Try to migrate to invalid version
        # BUG FIX: this used to silently swallow the ValueError via
        # contextlib.suppress with no report either way, defeating the
        # function's own stated purpose ("Example: Error handling"). The
        # exception is still suppressed exactly as before -- only the
        # missing confirmation is restored.
        try:
            system.migrate_to_version(999)
            print("ERROR: expected ValueError for invalid version 999, but none was raised.")
        except ValueError as e:
            print(f"Correctly rejected invalid target version 999: {e}")

        # Try to migrate to same version (no-op)
        system.migrate_to_version(1)

        system.migrate_to_version(1)

        # Try to rollback migration 1 (should fail)
        # BUG FIX: identical pattern to the invalid-version case above --
        # restored.
        try:
            system.migrate_to_version(0)
            print("ERROR: expected ValueError rolling back migration 1, but none was raised.")
        except ValueError as e:
            print(f"Correctly rejected rollback of migration 1: {e}")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def example_monitoring() -> None:
    """Example: Monitoring migration status."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = f.name

    try:
        # Initialize database
        DatabaseSchema.create_schema(db_path)

        system = MigrationSystem(db_path)

        # Get comprehensive status
        # BUG FIX: both loops below used to be `pass` no-ops (with the
        # else branch also a no-op) -- restored.
        status = system.get_migration_status()

        if status["pending_migrations"]:
            print(f"Pending migrations ({len(status['pending_migrations'])}):")
            for _m in status["pending_migrations"]:
                print(f"  - v{_m['version']}: {_m['description']}")
        else:
            print("No pending migrations.")

        if status["applied_migrations"]:
            print(f"Applied migrations ({len(status['applied_migrations'])}):")
            for _m in status["applied_migrations"]:
                print(f"  - v{_m['version']}: {_m['description']} (applied at {_m['applied_at']})")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def main() -> None:
    """Run all examples."""
    try:
        example_basic_usage()
        example_step_by_step()
        example_rollback()
        example_error_handling()
        example_monitoring()

    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
