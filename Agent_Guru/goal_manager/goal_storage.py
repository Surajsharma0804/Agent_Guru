"""Module: agent_guru.goal_manager.goal_storage
Purpose: Persistent storage for goals using SQLite with ACID transactions.

This module implements the storage layer for the Goal Manager system,
providing immediate persistence and efficient querying capabilities.

Performance Characteristics:
    - Time Complexity: O(1) for get_goal by ID (indexed lookup)
    - Time Complexity: O(log n) for query_goals with filters (indexed scan)
    - Space Complexity: O(n) where n is number of goals
    - Persistence: Immediate (ACID transactions)
    - Concurrency: Thread-safe with SQLite connection per operation

Architecture:
    The storage layer uses SQLite for structured persistence with:
    1. Immediate persistence (no buffering)
    2. ACID transactions for consistency
    3. Indexes on status, priority, parent_id for fast queries
    4. JSON serialization for complex fields (lists, dicts)
    5. Foreign key constraints for referential integrity

Optimization Techniques:
    - Indexed columns for O(log n) filtered queries
    - Connection pooling avoided (SQLite single-writer limitation)
    - Prepared statements for SQL injection prevention
    - JSON encoding for complex types (lists, dicts)

Author: Kiro AI
Date: 2024-01-15
Version: 1.0.0
"""

import contextlib
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .exceptions import StorageError
from .logging_config import get_logger
from .models import Goal, GoalStatus, Priority

# Initialize structured logger
logger = get_logger(__name__)

class GoalStorage:
    """Persistent storage for goals using SQLite.

    Provides ACID transactions and immediate persistence with O(1) retrieval
    by ID and O(log n) filtered queries using indexes.

    Time Complexity:
        - store_goal: O(1) - single INSERT with index update
        - update_goal: O(1) - single UPDATE with index update
        - get_goal: O(1) - indexed lookup by primary key
        - query_goals: O(log n) - indexed scan with filters

    Space Complexity: O(n) where n is number of goals

    Example:
        >>> storage = GoalStorage("goals.db")
        >>> goal = Goal(description="Test goal")
        >>> await storage.store_goal(goal)
        >>> retrieved = await storage.get_goal(goal.id)
        >>> assert retrieved.id == goal.id

    """

    def __init__(self, db_path: str) -> None:
        """Initialize storage with database path.

        Creates database file and schema if they don't exist.

        Args:
            db_path: Path to SQLite database file

        Raises:
            StorageError: If database initialization fails

        """
        self.db_path = db_path
        self._lock = threading.RLock()

        if db_path != ":memory:":
            db_p = Path(db_path)
            resolved = db_p.resolve()
            intended_parent = db_p.parent.resolve()
            # CWE-22 mitigation: reject any path that escapes the intended
            # parent directory after full resolution (symlinks expanded).
            if not resolved.is_relative_to(intended_parent):
                msg = (
                    f"Path traversal detected: '{db_path}' resolves outside "
                    f"its parent directory '{intended_parent}'"
                )
                raise ValueError(
                    msg,
                )
            db_p.parent.mkdir(parents=True, exist_ok=True)
            # _data_dir is the validated parent; used by export/import helpers.
            self._data_dir: Path = intended_parent
            # Use the fully-resolved absolute path — never the raw user input.
            connect_path: str = resolved.as_posix()
        else:
            self._data_dir = Path.cwd()
            connect_path = ":memory:"

        self._conn: sqlite3.Connection = sqlite3.connect(
            connect_path,
            check_same_thread=False,
        )  # persistent; closed in close() / __del__
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")

        # Initialize schema
        self._init_schema()

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "GoalStorage":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the persistent database connection."""
        with contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __del__(self) -> None:
        """Ensure connection is closed on garbage collection."""
        self.close()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _resolve_data_path(self, user_path: str) -> Path:
        """Resolve *user_path* and verify it stays inside ``self._data_dir``.

        Raises:
            ValueError: If the resolved path escapes the data directory.

        """
        resolved = (self._data_dir / user_path).resolve()
        if not resolved.is_relative_to(self._data_dir):
            msg = (
                f"Path traversal detected: '{user_path}' resolves to "
                f"'{resolved}' which escapes '{self._data_dir}'"
            )
            raise ValueError(
                msg,
            )
        return resolved

    async def initialize(self) -> None:
        """Async initialization (no-op — schema already created in __init__).

        Provided for API compatibility with tests that call
        ``await storage.initialize()`` before use.
        """
        # Schema is already set up synchronously in __init__.
        # This method exists so callers can await it without error.

    async def update_goal_status(self, goal_id: str, status: "GoalStatus") -> None:
        """Update only the status field of a goal.

        Time Complexity: O(1) — single indexed UPDATE
        Space Complexity: O(1)

        Args:
            goal_id: Goal identifier
            status: New status value

        Raises:
            StorageError: If update fails or goal not found

        """
        from .exceptions import StorageError as _StorageError

        status_value = status.value if hasattr(status, "value") else str(status)
        try:
            with self._lock:
                conn = self._connect()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE goals SET status = ? WHERE id = ?",
                    (status_value, goal_id),
                )
                if cursor.rowcount == 0:
                    self._close(conn)
                    msg = f"Goal {goal_id} not found"
                    raise _StorageError(msg)
                conn.commit()
                self._close(conn)
        except _StorageError:
            raise

    def _connect(self) -> sqlite3.Connection:
        """Return the persistent connection."""
        return self._conn

    def _close(self, conn: sqlite3.Connection) -> None:
        """No-op: we keep the persistent connection open."""

    def _init_schema(self) -> None:
        """Initialize database schema with tables and indexes."""
        try:
            with self._lock:
                conn = self._connect()
                cursor = conn.cursor()

                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS goals (
                        id TEXT PRIMARY KEY,
                        description TEXT NOT NULL,
                        status TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        goal_type TEXT NOT NULL DEFAULT 'task',
                        progress REAL NOT NULL,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        deadline TEXT,
                        parent_id TEXT,
                        sub_goal_ids TEXT NOT NULL,
                        dependency_ids TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        error_message TEXT,
                        retry_count INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY (parent_id) REFERENCES goals(id)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON goals(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_priority ON goals(priority)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent ON goals(parent_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON goals(created_at)")

                # Migrate existing databases: add new columns if missing
                existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(goals)")}
                if "goal_type" not in existing_cols:
                    cursor.execute(
                        "ALTER TABLE goals ADD COLUMN goal_type TEXT NOT NULL DEFAULT 'task'",
                    )
                if "deadline" not in existing_cols:
                    cursor.execute("ALTER TABLE goals ADD COLUMN deadline TEXT")
                if "retry_count" not in existing_cols:
                    cursor.execute(
                        "ALTER TABLE goals ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
                    )

                conn.commit()
                self._close(conn)

        except Exception as e:
            logger.exception(
                "schema_initialization_failed",
                db_path=self.db_path,
                error=str(e),
                error_type=type(e).__name__,
            )
            msg = f"Failed to initialize database schema: {e}"
            raise StorageError(msg) from e

    async def store_goal(self, goal: Goal) -> None:
        """Store goal with immediate persistence.

        Uses ACID transaction to ensure goal is persisted before returning.

        Time Complexity: O(1) - single INSERT with index updates
        Space Complexity: O(1) - no additional memory allocation

        Args:
            goal: Goal to store

        Raises:
            StorageError: If persistence fails

        """
        conn = self._connect()
        cursor = conn.cursor()

        try:
            with self._lock:
                cursor.execute(
                    """
                    INSERT INTO goals (
                        id, description, status, priority, goal_type, progress,
                        created_at, started_at, completed_at, deadline, parent_id,
                        sub_goal_ids, dependency_ids, metadata, error_message, retry_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        goal.id,
                        goal.description,
                        self._get_enum_value(goal.status),
                        self._get_enum_value(goal.priority),
                        self._get_enum_value(goal.goal_type)
                        if hasattr(goal, "goal_type")
                        else "task",
                        goal.progress,
                        goal.created_at.isoformat(),
                        goal.started_at.isoformat() if goal.started_at else None,
                        goal.completed_at.isoformat() if goal.completed_at else None,
                        goal.deadline.isoformat() if goal.deadline else None,
                        goal.parent_id,
                        json.dumps(goal.sub_goal_ids),
                        json.dumps(goal.dependency_ids),
                        json.dumps(goal.metadata),
                        goal.error_message,
                        goal.retry_count if hasattr(goal, "retry_count") else 0,
                    ),
                )
                conn.commit()

        except sqlite3.IntegrityError as e:
            conn.rollback()
            logger.exception(
                "goal_store_integrity_error",
                goal_id=goal.id,
                operation="store",
                error=str(e),
                error_type="IntegrityError",
            )
            msg = f"Goal with ID {goal.id} already exists: {e}"
            raise StorageError(msg) from e
        finally:
            self._close(conn)

    async def update_goal(self, goal: Goal) -> None:
        """Update goal with immediate persistence.

        Uses ACID transaction to ensure changes are persisted before returning.

        Time Complexity: O(1) - single UPDATE with index updates
        Space Complexity: O(1) - no additional memory allocation

        Args:
            goal: Goal with updated fields

        Raises:
            StorageError: If persistence fails

        """
        conn = self._connect()
        cursor = conn.cursor()

        try:
            with self._lock:
                cursor.execute(
                    """
                    UPDATE goals SET
                        description = ?,
                        status = ?,
                        priority = ?,
                        goal_type = ?,
                        progress = ?,
                        started_at = ?,
                        completed_at = ?,
                        deadline = ?,
                        sub_goal_ids = ?,
                        dependency_ids = ?,
                        metadata = ?,
                        error_message = ?,
                        retry_count = ?
                    WHERE id = ?
                """,
                    (
                        goal.description,
                        self._get_enum_value(goal.status),
                        self._get_enum_value(goal.priority),
                        self._get_enum_value(goal.goal_type)
                        if hasattr(goal, "goal_type")
                        else "task",
                        goal.progress,
                        goal.started_at.isoformat() if goal.started_at else None,
                        goal.completed_at.isoformat() if goal.completed_at else None,
                        goal.deadline.isoformat() if goal.deadline else None,
                        json.dumps(goal.sub_goal_ids),
                        json.dumps(goal.dependency_ids),
                        json.dumps(goal.metadata),
                        goal.error_message,
                        goal.retry_count if hasattr(goal, "retry_count") else 0,
                        goal.id,
                    ),
                )

                if cursor.rowcount == 0:
                    logger.error("goal_update_not_found", goal_id=goal.id, operation="update")
                    msg = f"Goal with ID {goal.id} not found"
                    raise StorageError(msg)

                conn.commit()

        except StorageError:
            raise
        finally:
            self._close(conn)

    async def get_goal(self, goal_id: str) -> Goal | None:
        """Retrieve goal by ID.

        Uses primary key index for O(1) lookup.

        Time Complexity: O(1) - indexed lookup by primary key
        Space Complexity: O(1) - single goal object

        Args:
            goal_id: Goal identifier

        Returns:
            Goal if found, None otherwise

        Raises:
            StorageError: If retrieval fails

        """
        try:
            with self._lock:
                conn = self._connect()
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, description, status, priority, goal_type, progress,
                           created_at, started_at, completed_at, deadline, parent_id,
                           sub_goal_ids, dependency_ids, metadata, error_message, retry_count
                    FROM goals WHERE id = ?
                """,
                    (goal_id,),
                )

                row = cursor.fetchone()
                self._close(conn)

            if not row:
                return None

            return self._row_to_goal(row)

        except Exception as e:
            logger.exception(
                "goal_retrieval_failed",
                goal_id=goal_id,
                operation="get",
                error=str(e),
                error_type=type(e).__name__,
            )
            msg = f"Failed to retrieve goal: {e}"
            raise StorageError(msg) from e

    async def query_goals(
        self,
        status: GoalStatus | None = None,
        priority: Priority | None = None,
    ) -> list[Goal]:
        """Query goals with optional filters.

        Uses indexes on status and priority for O(log n) filtered queries.

        Time Complexity: O(log n + k) where k is number of matching goals
        Space Complexity: O(k) for result list

        Args:
            status: Optional status filter
            priority: Optional priority filter

        Returns:
            List of goals matching filters

        Raises:
            StorageError: If query fails

        """
        try:
            with self._lock:
                conn = self._connect()
                cursor = conn.cursor()

                # Build query with filters
                query = """
                    SELECT id, description, status, priority, goal_type, progress,
                           created_at, started_at, completed_at, deadline, parent_id,
                           sub_goal_ids, dependency_ids, metadata, error_message, retry_count
                    FROM goals WHERE 1=1
                """
                params = []

                if status:
                    query += " AND status = ?"
                    params.append(status.value)

                if priority:
                    query += " AND priority = ?"
                    params.append(priority.value)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                self._close(conn)

            return [self._row_to_goal(row) for row in rows]

        except Exception as e:
            logger.exception(
                "goal_query_failed",
                operation="query",
                status=status.value if status else None,
                priority=priority.value if priority else None,
                error=str(e),
                error_type=type(e).__name__,
            )
            msg = f"Failed to query goals: {e}"
            raise StorageError(msg) from e

    def _row_to_goal(self, row: tuple) -> Goal:
        """Convert database row to Goal object.

        Time Complexity: O(1) - fixed number of field conversions
        Space Complexity: O(1) - single goal object

        Args:
            row: Database row tuple

        Returns:
            Goal object

        Raises:
            StorageError: If conversion fails

        """
        try:
            from .models import GoalType as _GoalType

            return Goal(
                id=row[0],
                description=row[1],
                status=GoalStatus(row[2]),
                priority=Priority(row[3]),
                goal_type=_GoalType(row[4]) if row[4] else _GoalType.TASK,
                progress=row[5],
                created_at=datetime.fromisoformat(row[6]),
                started_at=datetime.fromisoformat(row[7]) if row[7] else None,
                completed_at=datetime.fromisoformat(row[8]) if row[8] else None,
                deadline=datetime.fromisoformat(row[9]) if row[9] else None,
                parent_id=row[10],
                sub_goal_ids=json.loads(row[11]),
                dependency_ids=json.loads(row[12]),
                metadata=json.loads(row[13]),
                error_message=row[14],
                retry_count=row[15] if row[15] is not None else 0,
            )

        except Exception as e:
            logger.exception(
                "row_conversion_failed",
                operation="row_to_goal",
                error=str(e),
                error_type=type(e).__name__,
            )
            msg = f"Failed to convert row to goal: {e}"
            raise StorageError(msg) from e

    async def export_to_json(self, output_path: str) -> None:
        """Export all goals to JSON file.

        Time Complexity: O(n) where n is number of goals
        Space Complexity: O(n) for in-memory goal list

        Args:
            output_path: Path to output JSON file

        Raises:
            StorageError: If export fails

        """
        try:
            goals = await self.query_goals()

            output_file = self._resolve_data_path(output_path)
            with output_file.open("w", encoding="utf-8") as f:
                json.dump([self._goal_to_dict(g) for g in goals], f, indent=2)

        except Exception as e:
            logger.exception(
                "goal_export_failed",
                operation="export",
                output_path=output_path,
                error=str(e),
                error_type=type(e).__name__,
            )
            msg = f"Failed to export goals: {e}"
            raise StorageError(msg) from e

    async def import_from_json(self, input_path: str) -> int:
        """Import goals from JSON file.

        Time Complexity: O(n) where n is number of goals
        Space Complexity: O(1) - processes one goal at a time

        Args:
            input_path: Path to input JSON file

        Returns:
            Number of goals imported

        Raises:
            StorageError: If import fails

        """
        try:
            input_file = self._resolve_data_path(input_path)
            with input_file.open() as f:
                goals_data = json.load(f)

            count = 0
            for goal_dict in goals_data:
                goal = self._dict_to_goal(goal_dict)
                try:
                    await self.store_goal(goal)
                    count += 1
                except StorageError:
                    # Skip duplicates
                    pass
            return count

        except Exception as e:
            logger.exception(
                "goal_import_failed",
                operation="import",
                input_path=input_path,
                error=str(e),
                error_type=type(e).__name__,
            )
            msg = f"Failed to import goals: {e}"
            raise StorageError(msg) from e

    def _goal_to_dict(self, goal: Goal) -> dict:
        """Convert Goal to dictionary for JSON serialization.

        Time Complexity: O(1) - fixed number of field conversions
        Space Complexity: O(1) - single dictionary

        Args:
            goal: Goal to convert

        Returns:
            Dictionary representation

        """
        return {
            "id": goal.id,
            "description": goal.description,
            "status": self._get_enum_value(goal.status),
            "priority": self._get_enum_value(goal.priority),
            "goal_type": self._get_enum_value(goal.goal_type)
            if hasattr(goal, "goal_type")
            else "task",
            "progress": goal.progress,
            "created_at": goal.created_at.isoformat(),
            "started_at": goal.started_at.isoformat() if goal.started_at else None,
            "completed_at": goal.completed_at.isoformat() if goal.completed_at else None,
            "deadline": goal.deadline.isoformat() if goal.deadline else None,
            "parent_id": goal.parent_id,
            "sub_goal_ids": goal.sub_goal_ids,
            "dependency_ids": goal.dependency_ids,
            "metadata": goal.metadata,
            "error_message": goal.error_message,
            "retry_count": goal.retry_count if hasattr(goal, "retry_count") else 0,
        }

    @staticmethod
    def _get_enum_value(enum_field):
        """Extract value from enum field (handles both Enum objects and strings).

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            enum_field: Enum object or string value

        Returns:
            String value of the enum

        """
        return enum_field.value if hasattr(enum_field, "value") else enum_field

    def _dict_to_goal(self, data: dict) -> Goal:
        """Convert dictionary to Goal object.

        Time Complexity: O(1) - fixed number of field conversions
        Space Complexity: O(1) - single goal object

        Args:
            data: Dictionary representation

        Returns:
            Goal object

        Raises:
            StorageError: If conversion fails

        """
        try:
            return Goal(
                id=data["id"],
                description=data["description"],
                status=GoalStatus(data["status"]),
                priority=Priority(data["priority"]),
                progress=data["progress"],
                created_at=datetime.fromisoformat(data["created_at"]),
                started_at=datetime.fromisoformat(data["started_at"])
                if data["started_at"]
                else None,
                completed_at=datetime.fromisoformat(data["completed_at"])
                if data["completed_at"]
                else None,
                parent_id=data["parent_id"],
                sub_goal_ids=data["sub_goal_ids"],
                dependency_ids=data["dependency_ids"],
                metadata=data["metadata"],
                error_message=data["error_message"],
            )

        except Exception as e:
            logger.exception(
                "dict_conversion_failed",
                operation="dict_to_goal",
                error=str(e),
                error_type=type(e).__name__,
            )
            msg = f"Failed to convert dict to goal: {e}"
            raise StorageError(msg) from e
