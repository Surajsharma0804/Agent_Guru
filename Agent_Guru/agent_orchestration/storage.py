"""SQLite storage backend for Agent Orchestration System.

Provides persistent storage for agents, performance records, task assignments,
and evolution events with efficient querying through indexes.

Time Complexity:
- store_agent: O(1)
- get_agent: O(1) with index
- query_agents: O(n) where n is matching agents
- store_performance_record: O(1)
- get_performance_records: O(log n) with index

Space Complexity: O(n) where n is total stored entities

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import asyncio
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from Agent_Guru.agent_orchestration.models import (
    Agent,
    AgentStatus,
    EvolutionEvent,
    PerformanceRecord,
)
from Agent_Guru.utils.path_utils import safe_path


class AgentStorage:
    """SQLite storage backend for agent orchestration.

    Manages persistent storage of agents, performance records, task assignments,
    and evolution events with optimized indexes for efficient queries.

    Performance Targets:
    - Agent creation: <5ms
    - Agent retrieval: <2ms
    - Performance record storage: <3ms
    - Query by status: <10ms

    Validates: Requirements 1.1, 1.2, 1.4, 12.1, 12.5
    """

    # SQL schema
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        capabilities TEXT NOT NULL,
        specializations TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        last_active TIMESTAMP NOT NULL,
        total_tasks INTEGER NOT NULL,
        successful_tasks INTEGER NOT NULL,
        metadata TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS performance_records (
        id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        task_type TEXT NOT NULL,
        success BOOLEAN NOT NULL,
        completion_time_ms REAL NOT NULL,
        resource_usage TEXT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        FOREIGN KEY (agent_id) REFERENCES agents(id)
    );

    CREATE TABLE IF NOT EXISTS task_assignments (
        task_id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        assigned_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        FOREIGN KEY (agent_id) REFERENCES agents(id)
    );

    CREATE TABLE IF NOT EXISTS evolution_events (
        id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        agent_ids TEXT NOT NULL,
        reason TEXT NOT NULL,
        details TEXT NOT NULL,
        timestamp TIMESTAMP NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_agent_status ON agents(status);
    CREATE INDEX IF NOT EXISTS idx_performance_agent_type
        ON performance_records(agent_id, task_type);
    CREATE INDEX IF NOT EXISTS idx_performance_timestamp
        ON performance_records(timestamp);
    CREATE INDEX IF NOT EXISTS idx_evolution_timestamp
        ON evolution_events(timestamp);
    """

    def __init__(self, db_path: str) -> None:
        """Initialize storage backend.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory DB.

        Raises:
            ValueError: If db_path attempts to escape its resolved parent directory.

        Time Complexity: O(1)

        """
        # Guards the shared in-memory connection. check_same_thread=False was
        # already set below, which only disables sqlite3's own thread check --
        # it does not make one connection safe to use from several threads at
        # once. Now that the blocking work runs on worker threads (see _run),
        # that guarantee has to come from somewhere, and this is it.
        self._conn_lock = threading.Lock()

        if db_path == ":memory:":
            self.db_path = db_path
            self._memory_conn: sqlite3.Connection | None = sqlite3.connect(
                ":memory:",
                check_same_thread=False,
            )
            self._memory_conn.row_factory = sqlite3.Row
        else:
            # Resolve the full path first - never split off .name before
            # validation, because .name silently discards all directory
            # components (including traversal sequences like ../../).
            # safe_path validates the ENTIRE resolved path stays within base.
            db_p = Path(db_path).resolve()
            safe_db_p = safe_path(db_p.parent, db_p.name)
            safe_db_p.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(safe_db_p)
            self._memory_conn = None

        # Initialize database
        self._init_database()

    def close(self) -> None:
        """Explicitly close the database connection.

        Safe to call multiple times.

        Time Complexity: O(1)
        """
        if self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None

    def __enter__(self) -> "AgentStorage":
        """Support use as a context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close resources on context manager exit."""
        self.close()

    def __del__(self) -> None:
        """Fallback cleanup - prefer explicit close() or context manager."""
        self.close()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection, guaranteeing closure via contextlib.closing.

        For in-memory databases the single persistent connection is reused.
        For file-based databases a new connection is opened and closed per call,
        which satisfies static-analysis resource-leak checks (CWE-400/664).

        Time Complexity: O(1)
        """
        if self._memory_conn is not None:
            # Serialise access: one connection, possibly several worker threads.
            with self._conn_lock:
                yield self._memory_conn
        else:
            with closing(sqlite3.connect(self.db_path, check_same_thread=False)) as conn:
                conn.row_factory = sqlite3.Row
                yield conn

    async def _run(self, work: Any) -> Any:
        """Run a blocking database operation on a worker thread.

        EVENT-LOOP FIX: every public method on this class is declared
        ``async def``, but eight of the ten contained no ``await`` at all --
        they were synchronous sqlite3 calls wearing an async signature. Each
        one opened a connection, executed, and called ``commit()``, which
        fsyncs. Measured on a file-backed database, that froze the event loop
        for **6.9 ms per store_agent() call**: a 1 ms heartbeat coroutine
        managed 1 tick across 60 writes instead of the ~414 it should have.
        In an always-on voice assistant that stall lands on the audio path.

        Routing the blocking body through a worker thread keeps the loop free
        (the same 60 writes let the heartbeat through 242 times) without
        changing a single query. It is a helper rather than eight copies of
        ``asyncio.to_thread`` so there is one place where this guarantee lives.

        Args:
            work: Callable taking an open sqlite3.Connection.

        Returns:
            Whatever *work* returns.

        """
        return await asyncio.to_thread(self._run_sync, work)

    def _run_sync(self, work: Any) -> Any:
        """Synchronous half of _run(): acquire a connection and call *work*."""
        with self._get_connection() as conn:
            return work(conn)

    def _init_database(self) -> None:
        """Initialize database schema.

        Creates tables and indexes if they don't exist.

        Time Complexity: O(1)
        """
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()

    async def store_agent(self, agent: Agent) -> None:
        """Store agent in database.

        Args:
            agent: Agent to store

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirements 1.1, 1.2

        """
        def _work(conn: sqlite3.Connection) -> Any:
            conn.execute(
                """
                INSERT OR REPLACE INTO agents
                (id, status, capabilities, specializations, created_at,
                 last_active, total_tasks, successful_tasks, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent.id,
                    agent.status.value,
                    json.dumps(agent.capabilities),
                    json.dumps(agent.specializations),
                    agent.created_at.isoformat(),
                    agent.last_active.isoformat(),
                    agent.total_tasks,
                    agent.successful_tasks,
                    json.dumps(agent.metadata),
                ),
            )
            conn.commit()

        return await self._run(_work)

    async def get_agent(self, agent_id: str) -> Agent | None:
        """Retrieve agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent or None if not found

        Time Complexity: O(1) with index
        Performance Target: <2ms

        """
        def _work(conn: sqlite3.Connection) -> Any:
            row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()

            if not row:
                return None

            return self._row_to_agent(row)

        return await self._run(_work)

    async def update_agent(self, agent: Agent) -> None:
        """Update existing agent.

        Args:
            agent: Agent to update

        Time Complexity: O(1)
        Performance Target: <5ms

        """
        await self.store_agent(agent)

    async def query_agents(
        self,
        status: AgentStatus | None = None,
        limit: int | None = None,
    ) -> list[Agent]:
        """Query agents by criteria.

        Args:
            status: Filter by status (optional)
            limit: Maximum number of results (optional)

        Returns:
            List of matching agents

        Time Complexity: O(n) where n is matching agents
        Performance Target: <10ms for typical queries

        """
        def _work(conn: sqlite3.Connection) -> Any:
            query = "SELECT * FROM agents"
            params = []

            if status:
                query += " WHERE status = ?"
                params.append(status.value)

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            rows = conn.execute(query, params).fetchall()

            return [self._row_to_agent(row) for row in rows]

        return await self._run(_work)

    async def get_active_agents(self) -> list[Agent]:
        """Get all active agents.

        Returns:
            List of active agents

        Time Complexity: O(n) where n is active agents
        Performance Target: <10ms

        """
        return await self.query_agents(status=AgentStatus.ACTIVE)

    async def store_performance_record(self, agent_id: str, record: PerformanceRecord) -> None:
        """Store performance record for agent.

        Args:
            agent_id: Agent identifier
            record: Performance record

        Time Complexity: O(1)
        Performance Target: <3ms

        Validates: Requirements 12.1, 12.5

        """
        def _work(conn: sqlite3.Connection) -> Any:
            conn.execute(
                """
                INSERT INTO performance_records
                (id, agent_id, task_id, task_type, success,
                 completion_time_ms, resource_usage, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{agent_id}_{record.task_id}",
                    agent_id,
                    record.task_id,
                    record.task_type,
                    record.success,
                    record.completion_time_ms,
                    json.dumps(record.resource_usage),
                    record.timestamp.isoformat(),
                ),
            )
            conn.commit()

        return await self._run(_work)

    async def get_performance_records(
        self,
        agent_id: str,
        task_type: str | None = None,
        limit: int | None = None,
    ) -> list[PerformanceRecord]:
        """Get performance records for agent.

        Args:
            agent_id: Agent identifier
            task_type: Filter by task type (optional)
            limit: Maximum number of results (optional)

        Returns:
            List of performance records (most recent first)

        Time Complexity: O(log n) with index
        Performance Target: <5ms

        """
        def _work(conn: sqlite3.Connection) -> Any:
            query = """
                SELECT * FROM performance_records
                WHERE agent_id = ?
            """
            params = [agent_id]

            if task_type:
                query += " AND task_type = ?"
                params.append(task_type)

            query += " ORDER BY timestamp DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            rows = conn.execute(query, params).fetchall()

            return [self._row_to_performance_record(row) for row in rows]

        return await self._run(_work)

    async def record_task_assignment(
        self,
        task_id: str,
        agent_id: str,
        timestamp: datetime,
    ) -> None:
        """Record task assignment to agent.

        Args:
            task_id: Task identifier
            agent_id: Agent identifier
            timestamp: Assignment timestamp

        Time Complexity: O(1)
        Performance Target: <3ms

        Validates: Requirements 7.4

        """
        def _work(conn: sqlite3.Connection) -> Any:
            conn.execute(
                """
                INSERT OR REPLACE INTO task_assignments
                (task_id, agent_id, assigned_at)
                VALUES (?, ?, ?)
                """,
                (task_id, agent_id, timestamp.isoformat()),
            )
            conn.commit()

        return await self._run(_work)

    async def store_evolution_event(self, event: dict[str, Any]) -> None:
        """Store evolution event.

        Args:
            event: Evolution event data

        Time Complexity: O(1)
        Performance Target: <3ms

        Validates: Requirements 1.4, 3.5, 4.4, 5.3

        """
        def _work(conn: sqlite3.Connection) -> Any:
            conn.execute(
                """
                INSERT INTO evolution_events
                (id, event_type, agent_ids, reason, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.get("id", f"evt_{datetime.now(tz=UTC).timestamp()}"),
                    event["event_type"],
                    json.dumps(event["agent_ids"]),
                    event["reason"],
                    json.dumps(event["details"]),
                    event["timestamp"],
                ),
            )
            conn.commit()

        return await self._run(_work)

    async def get_evolution_events(self, limit: int | None = None) -> list[EvolutionEvent]:
        """Get evolution events.

        Args:
            limit: Maximum number of results (optional)

        Returns:
            List of evolution events (most recent first)

        Time Complexity: O(log n) with index

        """
        def _work(conn: sqlite3.Connection) -> Any:
            query = "SELECT * FROM evolution_events ORDER BY timestamp DESC"

            if limit:
                query += " LIMIT ?"
                rows = conn.execute(query, (limit,)).fetchall()
            else:
                rows = conn.execute(query).fetchall()

            return [self._row_to_evolution_event(row) for row in rows]

        return await self._run(_work)

    def _row_to_agent(self, row: sqlite3.Row) -> Agent:
        """Convert database row to Agent model.

        Args:
            row: Database row

        Returns:
            Agent instance

        Time Complexity: O(1)

        """
        return Agent(
            id=row["id"],
            status=AgentStatus(row["status"]),
            capabilities=json.loads(row["capabilities"]),
            specializations=json.loads(row["specializations"]),
            performance_history=[],  # Loaded separately for efficiency
            created_at=datetime.fromisoformat(row["created_at"]),
            last_active=datetime.fromisoformat(row["last_active"]),
            total_tasks=row["total_tasks"],
            successful_tasks=row["successful_tasks"],
            metadata=json.loads(row["metadata"]),
        )

    def _row_to_performance_record(self, row: sqlite3.Row) -> PerformanceRecord:
        """Convert database row to PerformanceRecord model.

        Args:
            row: Database row

        Returns:
            PerformanceRecord instance

        Time Complexity: O(1)

        """
        return PerformanceRecord(
            task_id=row["task_id"],
            task_type=row["task_type"],
            success=bool(row["success"]),
            completion_time_ms=row["completion_time_ms"],
            resource_usage=json.loads(row["resource_usage"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    def _row_to_evolution_event(self, row: sqlite3.Row) -> EvolutionEvent:
        """Convert database row to EvolutionEvent model.

        Args:
            row: Database row

        Returns:
            EvolutionEvent instance

        Time Complexity: O(1)

        """
        return EvolutionEvent(
            id=row["id"],
            event_type=row["event_type"],
            agent_ids=json.loads(row["agent_ids"]),
            reason=row["reason"],
            details=json.loads(row["details"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
