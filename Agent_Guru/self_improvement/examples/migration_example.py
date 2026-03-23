"""
Example usage of the migration system.

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


def example_basic_usage():
    """Example: Basic migration usage."""
    print("\n=== Example 1: Basic Usage ===\n")

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize database with base schema
        print(f"Creating database: {db_path}")
        DatabaseSchema.create_schema(db_path)

        # Simple migration to latest
        print("\nMigrating to latest version...")
        migrate_database(db_path)

        # Check status
        system = MigrationSystem(db_path)
        status = system.get_migration_status()

        print("\n✓ Migration complete!")
        print(f"  Current version: {status['current_version']}")
        print(f"  Latest version: {status['latest_version']}")
        print(f"  Up to date: {status['is_up_to_date']}")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def example_step_by_step():
    """Example: Step-by-step migration."""
    print("\n=== Example 2: Step-by-Step Migration ===\n")

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize database
        print(f"Creating database: {db_path}")
        DatabaseSchema.create_schema(db_path)

        # Create migration system
        system = MigrationSystem(db_path)

        # Show initial status
        print("\nInitial status:")
        status = system.get_migration_status()
        print(f"  Current version: {status['current_version']}")
        print(f"  Latest version: {status['latest_version']}")
        print(f"  Pending migrations: {len(status['pending_migrations'])}")

        # Show pending migrations
        if status['pending_migrations']:
            print("\nPending migrations:")
            for m in status['pending_migrations']:
                print(f"  v{m['version']}: {m['description']}")

        # Apply migrations one by one
        print("\nApplying migrations...")
        for version in range(1, status['latest_version'] + 1):
            print(f"\n  Migrating to version {version}...")
            system.migrate_to_version(version)
            print(f"  ✓ Version {version} applied")

        # Show final status
        print("\nFinal status:")
        status = system.get_migration_status()
        print(f"  Current version: {status['current_version']}")
        print(f"  Up to date: {status['is_up_to_date']}")

        # Show applied migrations
        print("\nApplied migrations:")
        applied = system.get_applied_migrations()
        for version, description, applied_at in applied:
            print(f"  v{version}: {description}")
            print(f"    Applied at: {applied_at}")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def example_rollback():
    """Example: Rolling back migrations."""
    print("\n=== Example 3: Rollback Migrations ===\n")

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize and migrate to latest
        print(f"Creating database: {db_path}")
        DatabaseSchema.create_schema(db_path)

        system = MigrationSystem(db_path)
        latest = system.get_latest_version()

        print(f"\nMigrating to latest version ({latest})...")
        system.migrate_to_latest()
        print(f"✓ At version {system.get_current_version()}")

        # Rollback to version 2
        print("\nRolling back to version 2...")
        system.migrate_to_version(2)
        print(f"✓ At version {system.get_current_version()}")

        # Show current migrations
        applied = system.get_applied_migrations()
        print(f"\nApplied migrations: {len(applied)}")
        for version, description, _applied_at in applied:
            print(f"  v{version}: {description}")

        # Migrate forward again
        print("\nMigrating back to latest...")
        system.migrate_to_latest()
        print(f"✓ At version {system.get_current_version()}")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def example_error_handling():
    """Example: Error handling."""
    print("\n=== Example 4: Error Handling ===\n")

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize database
        print(f"Creating database: {db_path}")
        DatabaseSchema.create_schema(db_path)

        system = MigrationSystem(db_path)

        # Try to migrate to invalid version
        print("\nTrying to migrate to invalid version 999...")
        try:
            system.migrate_to_version(999)
        except ValueError as e:
            print(f"✓ Error caught: {e}")

        # Try to migrate to same version (no-op)
        print("\nMigrating to version 1...")
        system.migrate_to_version(1)
        print(f"✓ At version {system.get_current_version()}")

        print("\nTrying to migrate to same version again...")
        system.migrate_to_version(1)
        print(f"✓ No-op: still at version {system.get_current_version()}")

        # Try to rollback migration 1 (should fail)
        print("\nTrying to rollback migration 1 (should fail)...")
        try:
            system.migrate_to_version(0)
        except ValueError as e:
            print(f"✓ Error caught: {e}")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def example_monitoring():
    """Example: Monitoring migration status."""
    print("\n=== Example 5: Monitoring ===\n")

    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize database
        print(f"Creating database: {db_path}")
        DatabaseSchema.create_schema(db_path)

        system = MigrationSystem(db_path)

        # Get comprehensive status
        status = system.get_migration_status()

        print("\n=== Migration Status ===")
        print(f"Current version: {status['current_version']}")
        print(f"Latest version: {status['latest_version']}")
        print(f"Up to date: {status['is_up_to_date']}")

        if status['pending_migrations']:
            print(f"\n⚠ Warning: {len(status['pending_migrations'])} pending migrations")
            for m in status['pending_migrations']:
                print(f"  • v{m['version']}: {m['description']}")
        else:
            print("\n✓ All migrations applied")

        if status['applied_migrations']:
            print(f"\nApplied migrations: {len(status['applied_migrations'])}")
            for m in status['applied_migrations']:
                print(f"  • v{m['version']}: {m['description']}")
                print(f"    Applied: {m['applied_at']}")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


def main():
    """Run all examples."""
    print("=" * 60)
    print("Migration System Examples")
    print("=" * 60)

    try:
        example_basic_usage()
        example_step_by_step()
        example_rollback()
        example_error_handling()
        example_monitoring()

        print("\n" + "=" * 60)
        print("All examples completed successfully! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
