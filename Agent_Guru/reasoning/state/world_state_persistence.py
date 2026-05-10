"""WorldState Persistence and Recovery.

This module provides persistence and recovery for WorldState with versioning.

Performance: <50ms save, <100ms restore
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import aiosqlite
import structlog

from Agent_Guru.reasoning.state.world_state_engine import WorldStateEngine

logger = structlog.get_logger(__name__)


class WorldStatePersistence:
    """Persistence layer for WorldState.

    Time Complexity:
    - save_state: O(1)
    - restore_state: O(1)
    - get_version: O(1)

    Space Complexity: O(1)
    """

    CURRENT_VERSION = 1

    def __init__(self, db_path: str = "world_state.db") -> None:
        """Initialize persistence layer.

        Args:
            db_path: Path to SQLite database

        """
        self._db_path = db_path
        self._lock = asyncio.Lock()

        logger.info("world_state_persistence_initialized", db_path=db_path)

    async def initialize(self) -> None:
        """Initialize database schema."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS world_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    last_updated TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """,
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS state_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    saved_at TIMESTAMP NOT NULL
                )
                """,
            )
            await db.commit()

        logger.info("database_initialized")

    async def save_state(
        self,
        engine: WorldStateEngine,
        create_backup: bool = True,
    ) -> None:
        """Save current WorldState to database.

        Time Complexity: O(1)

        Args:
            engine: WorldState engine to save
            create_backup: Whether to create backup in history

        """
        async with self._lock:
            await engine.get_state()
            state_dict = await engine.persist_state()
            state_json = json.dumps(state_dict, default=str)

            async with aiosqlite.connect(self._db_path) as db:
                # Save current state
                await db.execute(
                    """
                    INSERT OR REPLACE INTO world_state (id, version, state_json, last_updated, created_at)
                    VALUES (1, ?, ?, ?, COALESCE((SELECT created_at FROM world_state WHERE id = 1), ?))
                    """,
                    (
                        self.CURRENT_VERSION,
                        state_json,
                        datetime.now(tz=UTC).isoformat(),
                        datetime.now(tz=UTC).isoformat(),
                    ),
                )

                # Create backup if requested
                if create_backup:
                    await db.execute(
                        """
                        INSERT INTO state_history (version, state_json, saved_at)
                        VALUES (?, ?, ?)
                        """,
                        (
                            self.CURRENT_VERSION,
                            state_json,
                            datetime.now(tz=UTC).isoformat(),
                        ),
                    )

                await db.commit()

            logger.info("state_saved", version=self.CURRENT_VERSION)

    async def restore_state(self, engine: WorldStateEngine) -> bool:
        """Restore WorldState from database.

        Time Complexity: O(1)

        Args:
            engine: WorldState engine to restore into

        Returns:
            True if restored successfully, False if no state found

        """
        async with self._lock, aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT version, state_json FROM world_state WHERE id = 1",
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                logger.info("no_state_to_restore")
                return False

            version, state_json = row

            # Handle version migrations if needed
            state_dict = json.loads(state_json)
            if version < self.CURRENT_VERSION:
                state_dict = await self._migrate_state(state_dict, version)

            # Restore state
            await engine.restore_state(state_dict)

            logger.info("state_restored", version=version)
            return True

    async def _migrate_state(
        self,
        state_dict: dict[str, Any],
        from_version: int,
    ) -> dict[str, Any]:
        """Migrate state from old version to current.

        Args:
            state_dict: State dictionary to migrate
            from_version: Version to migrate from

        Returns:
            Migrated state dictionary

        """
        logger.info("migrating_state", from_version=from_version, to_version=self.CURRENT_VERSION)

        # Add migration logic here as versions evolve
        # For now, version 1 is the only version

        return state_dict

    async def get_version(self) -> int | None:
        """Get current state version.

        Returns:
            Version number or None if no state exists

        """
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT version FROM world_state WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def get_backup_count(self) -> int:
        """Get number of backups in history.

        Returns:
            Number of backups

        """
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM state_history") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def restore_from_backup(
        self,
        engine: WorldStateEngine,
        backup_id: int,
    ) -> bool:
        """Restore state from specific backup.

        Args:
            engine: WorldState engine to restore into
            backup_id: Backup ID to restore from

        Returns:
            True if restored successfully, False if backup not found

        """
        async with self._lock, aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT version, state_json FROM state_history WHERE id = ?",
                (backup_id,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                logger.warning("backup_not_found", backup_id=backup_id)
                return False

            version, state_json = row
            state_dict = json.loads(state_json)

            if version < self.CURRENT_VERSION:
                state_dict = await self._migrate_state(state_dict, version)

            await engine.restore_state(state_dict)

            logger.info("state_restored_from_backup", backup_id=backup_id)
            return True

    async def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """Clean up old backups, keeping only recent ones.

        Args:
            keep_count: Number of recent backups to keep

        Returns:
            Number of backups deleted

        """
        async with self._lock, aiosqlite.connect(self._db_path) as db:
            # Get count of backups to delete
            async with db.execute(
                """
                    SELECT COUNT(*) FROM state_history
                    WHERE id NOT IN (
                        SELECT id FROM state_history
                        ORDER BY saved_at DESC
                        LIMIT ?
                    )
                    """,
                (keep_count,),
            ) as cursor:
                row = await cursor.fetchone()
                delete_count = row[0] if row else 0

            # Delete old backups
            await db.execute(
                """
                    DELETE FROM state_history
                    WHERE id NOT IN (
                        SELECT id FROM state_history
                        ORDER BY saved_at DESC
                        LIMIT ?
                    )
                    """,
                (keep_count,),
            )
            await db.commit()

            logger.info("old_backups_cleaned", deleted=delete_count, kept=keep_count)
            return delete_count
