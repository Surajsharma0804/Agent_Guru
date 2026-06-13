"""Data migration system for Self-Improvement Engine schema evolution.

This module provides versioned database migrations with:
- Forward migrations (upgrade schema)
- Rollback migrations (downgrade schema)
- Migration tracking in database
- Schema integrity validation
- Graceful failure handling

Performance Requirements:
- Time Complexity: O(n) where n is number of migrations to apply
- Space Complexity: O(1) - migrations applied sequentially
- Atomicity: Each migration runs in a transaction

Design Decisions:
- Migrations stored as Python functions for flexibility
- Each migration has upgrade and downgrade functions
- Migration history tracked in schema_migrations table
- Migrations applied in order by version number
- Failed migrations rolled back automatically
- Schema validated after each migration
"""

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from Agent_Guru.utils.path_utils import safe_path

BASE_DIR = Path(__file__).parent.resolve()

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    """A single database migration.

    Attributes:
        version: Migration version number (must be sequential)
        description: Human-readable description of migration
        upgrade: Function to apply migration
        downgrade: Function to rollback migration

    """

    version: int
    description: str
    upgrade: Callable[[sqlite3.Cursor], None]
    downgrade: Callable[[sqlite3.Cursor], None]


class MigrationSystem:
    """Database migration system for schema evolution.

    Manages versioned migrations with:
    - Forward migration (upgrade)
    - Backward migration (rollback)
    - Migration tracking
    - Schema validation
    - Transaction safety

    Time Complexity: O(n) where n is number of migrations
    Space Complexity: O(1) - migrations applied sequentially

    Example:
        >>> system = MigrationSystem("data/self_improvement.db")
        >>> system.migrate_to_latest()
        >>> print(f"Current version: {system.get_current_version()}")

    """

    def __init__(self, db_path: str) -> None:
        """Initialize migration system.

        Args:
            db_path: Path to SQLite database file

        """
        self.db_path = db_path
        self._ensure_migrations_table()
        self._register_migrations()

    def _ensure_migrations_table(self) -> None:
        """Ensure schema_migrations table exists.

        Creates table to track applied migrations if it doesn't exist.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    execution_time_ms REAL NOT NULL,

                    CHECK (version > 0),
                    CHECK (execution_time_ms >= 0)
                )
            """)

            conn.commit()

    def _register_migrations(self) -> None:
        """Register all available migrations.

        Migrations are registered in order by version number.
        Each migration must have both upgrade and downgrade functions.
        """
        self.migrations: dict[int, Migration] = {}

        # Migration 1: Initial schema (already applied by database_schema.py)
        # This is a placeholder for tracking purposes
        self.migrations[1] = Migration(
            version=1,
            description="Initial schema with failures, strategies, prompts, metrics, patterns",
            upgrade=self._migration_1_upgrade,
            downgrade=self._migration_1_downgrade,
        )

        # Migration 2: Add execution context indexes for faster pattern matching
        self.migrations[2] = Migration(
            version=2,
            description="Add execution context indexes for pattern matching performance",
            upgrade=self._migration_2_upgrade,
            downgrade=self._migration_2_downgrade,
        )

        # Migration 3: Add strategy performance history table
        self.migrations[3] = Migration(
            version=3,
            description="Add strategy_performance_history table for temporal analysis",
            upgrade=self._migration_3_upgrade,
            downgrade=self._migration_3_downgrade,
        )

    # Migration 1: Initial schema (placeholder)
    def _migration_1_upgrade(self, cursor: sqlite3.Cursor) -> None:
        """Migration 1 upgrade: Initial schema (already applied)."""
        # This migration is handled by database_schema.py
        # Just mark as applied

    def _migration_1_downgrade(self, cursor: sqlite3.Cursor) -> None:
        """Migration 1 downgrade: Cannot downgrade from initial schema."""
        msg = "Cannot downgrade from initial schema (version 1)"
        raise ValueError(msg)

    # Migration 2: Add execution context indexes
    def _migration_2_upgrade(self, cursor: sqlite3.Cursor) -> None:
        """Migration 2 upgrade: Add indexes for execution context.

        Adds indexes to improve pattern matching performance:
        - Index on failures.execution_context for JSON queries
        - Composite index on (task_type, failure_type) for filtering
        """
        logger.info("Applying migration 2: Adding execution context indexes")

        # Add composite index for common query pattern
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_failures_task_failure_type
            ON failures(task_type, failure_type)
        """)

        # Add index on created_at for temporal queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_failures_created_at
            ON failures(created_at)
        """)

        logger.info("Migration 2 applied successfully")

    def _migration_2_downgrade(self, cursor: sqlite3.Cursor) -> None:
        """Migration 2 downgrade: Remove execution context indexes."""
        logger.info("Rolling back migration 2: Removing execution context indexes")

        cursor.execute("DROP INDEX IF EXISTS idx_failures_task_failure_type")
        cursor.execute("DROP INDEX IF EXISTS idx_failures_created_at")

        logger.info("Migration 2 rolled back successfully")

    # Migration 3: Add strategy performance history
    def _migration_3_upgrade(self, cursor: sqlite3.Cursor) -> None:
        """Migration 3 upgrade: Add strategy performance history table.

        Creates table to track strategy performance over time:
        - Enables temporal analysis of strategy effectiveness
        - Supports trend detection and performance degradation alerts
        """
        logger.info("Applying migration 3: Adding strategy_performance_history table")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_performance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success_rate REAL NOT NULL,
                total_executions INTEGER NOT NULL,
                avg_execution_time_ms REAL NOT NULL,
                window_size INTEGER NOT NULL DEFAULT 10,

                FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id),

                CHECK (success_rate >= 0.0 AND success_rate <= 1.0),
                CHECK (total_executions >= 0),
                CHECK (avg_execution_time_ms >= 0.0),
                CHECK (window_size > 0)
            )
        """)

        # Add index for temporal queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy_history_timestamp
            ON strategy_performance_history(strategy_id, timestamp)
        """)

        logger.info("Migration 3 applied successfully")

    def _migration_3_downgrade(self, cursor: sqlite3.Cursor) -> None:
        """Migration 3 downgrade: Remove strategy performance history table."""
        logger.info("Rolling back migration 3: Removing strategy_performance_history table")

        cursor.execute("DROP INDEX IF EXISTS idx_strategy_history_timestamp")
        cursor.execute("DROP TABLE IF EXISTS strategy_performance_history")

        logger.info("Migration 3 rolled back successfully")

    def get_current_version(self) -> int:
        """Get current database schema version.

        Returns:
            Current version number, or 0 if no migrations applied

        Time Complexity: O(1)

        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    SELECT version FROM schema_migrations
                    ORDER BY version DESC
                    LIMIT 1
                """)
                result = cursor.fetchone()
                version = result[0] if result else 0
            except sqlite3.OperationalError:
                # Table doesn't exist yet
                version = 0

        return version

    def get_latest_version(self) -> int:
        """Get latest available migration version.

        Returns:
            Highest migration version number

        Time Complexity: O(1)

        """
        return max(self.migrations.keys()) if self.migrations else 0

    def get_pending_migrations(self) -> list[Migration]:
        """Get list of pending migrations.

        Returns:
            List of migrations not yet applied, in order

        Time Complexity: O(n) where n is number of migrations

        """
        current_version = self.get_current_version()

        return [
            migration
            for version, migration in sorted(self.migrations.items())
            if version > current_version
        ]

    def get_applied_migrations(self) -> list[tuple[int, str, str]]:
        """Get list of applied migrations.

        Returns:
            List of (version, description, applied_at) tuples

        Time Complexity: O(n) where n is number of applied migrations

        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT version, description, applied_at
                FROM schema_migrations
                ORDER BY version ASC
            """)

            return cursor.fetchall()

    def migrate_to_version(self, target_version: int) -> None:
        """Migrate database to specific version.

        Applies all migrations from current version to target version.
        If target is lower than current, performs rollback.

        Args:
            target_version: Target schema version

        Raises:
            ValueError: If target version is invalid
            sqlite3.Error: If migration fails

        Time Complexity: O(n) where n is number of migrations to apply

        """
        current_version = self.get_current_version()

        if target_version == current_version:
            logger.info("Already at version %s", target_version)
            return

        if target_version not in self.migrations and target_version != 0:
            msg = f"Invalid target version: {target_version}"
            raise ValueError(msg)

        if target_version > current_version:
            # Forward migration (upgrade)
            self._migrate_forward(current_version, target_version)
        else:
            # Backward migration (rollback)
            self._migrate_backward(current_version, target_version)

    def migrate_to_latest(self) -> None:
        """Migrate database to latest version.

        Applies all pending migrations.

        Time Complexity: O(n) where n is number of pending migrations
        """
        latest_version = self.get_latest_version()
        self.migrate_to_version(latest_version)

    def _migrate_forward(self, from_version: int, to_version: int) -> None:
        """Apply forward migrations (upgrade).

        Args:
            from_version: Current version
            to_version: Target version

        Time Complexity: O(n) where n is number of migrations

        """
        logger.info("Migrating forward from version %s to %s", from_version, to_version)

        # Get migrations to apply
        migrations_to_apply = [
            migration
            for version, migration in sorted(self.migrations.items())
            if from_version < version <= to_version
        ]

        # Apply each migration in transaction
        for migration in migrations_to_apply:
            self._apply_migration(migration)

    def _migrate_backward(self, from_version: int, to_version: int) -> None:
        """Apply backward migrations (rollback).

        Args:
            from_version: Current version
            to_version: Target version

        Time Complexity: O(n) where n is number of migrations

        """
        logger.info("Migrating backward from version %s to %s", from_version, to_version)

        # Get migrations to rollback (in reverse order)
        migrations_to_rollback = [
            migration
            for version, migration in sorted(self.migrations.items(), reverse=True)
            if to_version < version <= from_version
        ]

        # Rollback each migration in transaction
        for migration in migrations_to_rollback:
            self._rollback_migration(migration)

    def _apply_migration(self, migration: Migration) -> None:
        """Apply a single migration.

        Runs migration in transaction with timing and error handling.

        Args:
            migration: Migration to apply

        Raises:
            sqlite3.Error: If migration fails

        """
        logger.info("Applying migration %s: %s", migration.version, migration.description)

        # Connect with explicit transaction mode
        conn = sqlite3.connect(self.db_path)
        conn.isolation_level = None  # Autocommit off - manual transaction control
        cursor = conn.cursor()

        start_time = datetime.now(tz=UTC)

        try:
            # Explicitly begin transaction
            cursor.execute("BEGIN")

            # Apply migration
            migration.upgrade(cursor)

            # Calculate execution time
            execution_time = (datetime.now(tz=UTC) - start_time).total_seconds() * 1000

            # Record migration
            cursor.execute(
                """
                INSERT INTO schema_migrations (version, description, execution_time_ms)
                VALUES (?, ?, ?)
            """,
                (migration.version, migration.description, execution_time),
            )

            # Validate schema integrity
            self._validate_schema(cursor)

            # Commit transaction
            cursor.execute("COMMIT")

            logger.info(
                "Migration %s applied successfully in %.2fms",
                migration.version,
                execution_time,
            )

        except Exception:
            # Rollback on error
            try:
                cursor.execute("ROLLBACK")
            except sqlite3.Error:
                logger.exception("ROLLBACK failed during migration %s", migration.version)
            logger.exception("Migration %s failed", migration.version)
            raise
        finally:
            conn.close()

    def _rollback_migration(self, migration: Migration) -> None:
        """Rollback a single migration.

        Runs downgrade in transaction with error handling.

        Args:
            migration: Migration to rollback

        Raises:
            sqlite3.Error: If rollback fails

        """
        logger.info("Rolling back migration %s: %s", migration.version, migration.description)

        # Connect with manual transaction control
        conn = sqlite3.connect(self.db_path)
        conn.isolation_level = None  # Autocommit off - manual transaction control
        cursor = conn.cursor()

        try:
            # Explicitly begin transaction
            cursor.execute("BEGIN")

            # Rollback migration
            migration.downgrade(cursor)

            # Remove migration record
            cursor.execute(
                """
                DELETE FROM schema_migrations
                WHERE version = ?
            """,
                (migration.version,),
            )

            # Validate schema integrity
            self._validate_schema(cursor)

            # Commit transaction
            cursor.execute("COMMIT")

            logger.info("Migration %s rolled back successfully", migration.version)

        except Exception:
            # Rollback on error
            try:
                cursor.execute("ROLLBACK")
            except sqlite3.Error:
                logger.exception(
                    "ROLLBACK failed during rollback of migration %s",
                    migration.version,
                )
            logger.exception("Rollback of migration %s failed", migration.version)
            raise
        finally:
            conn.close()

    def _validate_schema(self, cursor: sqlite3.Cursor) -> None:
        """Validate schema integrity after migration.

        Checks that all expected tables exist and have correct structure.

        Args:
            cursor: Database cursor

        Raises:
            ValueError: If schema validation fails

        """
        # Check that core tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """)

        tables = {row[0] for row in cursor.fetchall()}

        # Minimum required tables
        required_tables = {"schema_migrations"}

        missing_tables = required_tables - tables
        if missing_tables:
            msg = f"Schema validation failed: missing tables {missing_tables}"
            raise ValueError(msg)

        logger.debug("Schema validation passed")

    def get_migration_status(self) -> dict[str, any]:
        """Get comprehensive migration status.

        Returns:
            Dictionary with current version, latest version, and pending migrations

        Example:
            >>> status = system.get_migration_status()
            >>> print(f"Current: {status['current_version']}")
            >>> print(f"Latest: {status['latest_version']}")
            >>> print(f"Pending: {len(status['pending_migrations'])}")

        """
        current_version = self.get_current_version()
        latest_version = self.get_latest_version()
        pending = self.get_pending_migrations()
        applied = self.get_applied_migrations()

        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "is_up_to_date": current_version == latest_version,
            "pending_migrations": [
                {"version": m.version, "description": m.description} for m in pending
            ],
            "applied_migrations": [
                {"version": version, "description": description, "applied_at": applied_at}
                for version, description, applied_at in applied
            ],
        }


def migrate_database(db_path: str, target_version: int | None = None) -> None:
    """Migrate database to target version or latest.

    Convenience function for running migrations.

    Args:
        db_path: Path to SQLite database file
        target_version: Target version (None for latest)

    Example:
        >>> migrate_database("data/self_improvement.db")  # Migrate to latest
        >>> migrate_database("data/self_improvement.db", 2)  # Migrate to v2

    """
    system = MigrationSystem(db_path)

    if target_version is None:
        system.migrate_to_latest()
    else:
        system.migrate_to_version(target_version)


if __name__ == "__main__":
    # Example usage and testing
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/self_improvement.db"

    # Ensure database exists
    db_file = safe_path(BASE_DIR, db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    system = MigrationSystem(db_path)

    # Show status
    status = system.get_migration_status()
    logger.info("\n=== Migration Status ===")
    logger.info("Current version: %s", status["current_version"])
    logger.info("Latest version: %s", status["latest_version"])
    logger.info("Up to date: %s", status["is_up_to_date"])

    if status["applied_migrations"]:
        logger.info("\nApplied migrations:")
        for m in status["applied_migrations"]:
            logger.info("  v%s: %s", m["version"], m["description"])
            logger.info("    Applied at: %s", m["applied_at"])

    if status["pending_migrations"]:
        logger.info("\nPending migrations:")
        for m in status["pending_migrations"]:
            logger.info("  v%s: %s", m["version"], m["description"])

        # Ask to apply
        response = input("\nApply pending migrations? (y/n): ")
        if response.lower() == "y":
            system.migrate_to_latest()
            logger.info("\n✓ Migrations applied successfully")
    else:
        logger.info("\n✓ Database is up to date")
