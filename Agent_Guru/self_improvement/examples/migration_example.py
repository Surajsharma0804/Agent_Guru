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

import contextlib

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
        system = MigrationSystem(db_path)
        system.get_migration_status()

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

        # Show pending migrations
        if status["pending_migrations"]:
            for _m in status["pending_migrations"]:
                pass

        # Apply migrations one by one
        for version in range(1, status["latest_version"] + 1):
            system.migrate_to_version(version)

        # Show final status
        status = system.get_migration_status()

        # Show applied migrations
        applied = system.get_applied_migrations()
        for _version, _description, _applied_at in applied:
            pass

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
        system.get_latest_version()

        system.migrate_to_latest()

        # Rollback to version 2
        system.migrate_to_version(2)

        # Show current migrations
        applied = system.get_applied_migrations()
        for _version, _description, _applied_at in applied:
            pass

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
        with contextlib.suppress(ValueError):
            system.migrate_to_version(999)

        # Try to migrate to same version (no-op)
        system.migrate_to_version(1)

        system.migrate_to_version(1)

        # Try to rollback migration 1 (should fail)
        with contextlib.suppress(ValueError):
            system.migrate_to_version(0)

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
        status = system.get_migration_status()

        if status["pending_migrations"]:
            for _m in status["pending_migrations"]:
                pass
        else:
            pass

        if status["applied_migrations"]:
            for _m in status["applied_migrations"]:
                pass

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
