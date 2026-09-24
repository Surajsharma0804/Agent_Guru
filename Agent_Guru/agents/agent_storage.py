"""Agent Storage - SQLite-based storage for agent data and performance history.

This module provides persistent storage for agents, performance records,
and evolution events using SQLite as the backend.

**Key Features**:
- CRUD operations for agents
- Performance record storage and retrieval
- Evolution event tracking
- Efficient querying with indexes

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import asyncio
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agent_lifecycle import Agent, AgentStatus, PerformanceRecord


class AgentStorage:
    """SQLite-based storage for agent orchestration system.

    Provides persistent storage for:
    - Agent data (capabilities, specializations, metadata)
    - Performance records (task outcomes, metrics)
    - Evolution events (creation, merge, split, retirement)

    Time Complexity: O(1) for single operations, O(n) for queries
    Space Complexity: O(n) where n is number of agents

    Concurrency: every public method is `async def`, but the underlying
    sqlite3 driver is synchronous. Each method's actual database work is
    run via `asyncio.to_thread()` so the blocking I/O happens on a worker
    thread instead of the event loop - see the BUG FIX note below.

    Example:
        >>> storage = AgentStorage("data/agents.db")
        >>> await storage.store_agent(agent)
        >>> retrieved = await storage.get_agent(agent.id)

    Validates: Requirements 1.1, 1.2, 1.4, 12.1, 12.5

    """

    def __init__(self, db_path: str) -> None:
        """Initialize storage with database path.

        Args:
            db_path: Path to SQLite database file

        Time Complexity: O(1)

        """
        self.db_path = db_path
        # Cache for active agents - invalidated on any write
        self._active_agents_cache: list | None = None
        # BUG FIX: guards the read-modify-write sequence in
        # record_task_assignment() below against a lost-update race
        # when two coroutines assign different tasks to the SAME agent
        # concurrently -- see that method's own comment for the full
        # explanation.
        self._metadata_lock = asyncio.Lock()
        self._ensure_database()

    @contextmanager
    def _get_conn(self):
        """Open a SQLite connection, yield it, and guarantee closure.

        WAL mode + synchronous=NORMAL reduces fsync overhead while maintaining
        crash safety. contextlib.closing ensures the connection is always
        released even if an exception is raised.

        Every caller of this context manager must run entirely inside a
        single asyncio.to_thread() call (see each public method below) - the
        connection is opened with the default check_same_thread=True, so it
        must never be used from a different thread than the one that opened
        it, and it must never be handed back across the async/thread
        boundary.

        Time Complexity: O(1)
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn

    def _ensure_database(self) -> None:
        """Create database and tables if they don't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Agents table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    capabilities TEXT NOT NULL,
                    specializations TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_active TEXT NOT NULL,
                    total_tasks INTEGER NOT NULL,
                    successful_tasks INTEGER NOT NULL,
                    metadata TEXT NOT NULL
                )
            """,
            )

            # Performance records table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    completion_time_ms REAL NOT NULL,
                    resource_usage TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agents(id)
                )
            """,
            )

            # Evolution events table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evolution_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    agent_ids TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    details TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """,
            )

            # Create indexes for efficient queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agents_status
                ON agents(status)
            """,
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_performance_agent_type
                ON performance_records(agent_id, task_type)
            """,
            )

            # Additional indexes for hot query paths
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_performance_timestamp
                ON performance_records(timestamp)
            """,
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evolution_type
                ON evolution_events(event_type)
            """,
            )

            # Only create the task_assignments index if the table exists
            if cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='task_assignments'",
            ).fetchone():
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_task_assignments_agent
                    ON task_assignments(agent_id)
                """,
                )

            conn.commit()

    async def store_agent(self, agent: Agent) -> None:
        """Store new agent in database.

        Args:
            agent: Agent to store

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirement 1.1

        """

        # BUG FIX: this method was declared `async def` but every previous
        # version ran sqlite3 (a synchronous driver) directly inline, so the
        # actual database I/O executed synchronously on the event loop
        # thread - "async in name only". Every other coroutine scheduled on
        # this process's event loop (wake-word detection, STT/TTS streaming,
        # any concurrent voice command) would stall for the full duration of
        # every agent write. Wrapping the blocking body in asyncio.to_thread
        # moves the actual I/O onto a worker thread so the event loop stays
        # responsive, without changing this method's signature, return
        # value, or SQL. The sqlite3 connection is opened, used, and closed
        # entirely inside the thread function below - it is never passed
        # across the thread boundary, which is required since it's opened
        # with the default check_same_thread=True.
        def _write() -> None:
            with self._get_conn() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO agents (
                        id, status, capabilities, specializations,
                        created_at, last_active, total_tasks, successful_tasks, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        await asyncio.to_thread(_write)
        self._active_agents_cache = None  # Invalidate cache

    async def get_agent(self, agent_id: str) -> Agent | None:
        # BUG FIX: see store_agent() above - same asyncio.to_thread fix,
        # applied consistently to every method in this class that touches
        # the database.
        def _read() -> tuple | None:
            with self._get_conn() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, status, capabilities, specializations,
                           created_at, last_active, total_tasks, successful_tasks, metadata
                    FROM agents WHERE id = ?
                """,
                    (agent_id,),
                )

                return cursor.fetchone()

        row = await asyncio.to_thread(_read)

        if not row:
            return None

        # Get performance history
        performance_history = await self.get_performance_records(agent_id)

        return Agent(
            id=row[0],
            status=AgentStatus(row[1]),
            capabilities=json.loads(row[2]),
            specializations=json.loads(row[3]),
            performance_history=performance_history,
            created_at=datetime.fromisoformat(row[4]),
            last_active=datetime.fromisoformat(row[5]),
            total_tasks=row[6],
            successful_tasks=row[7],
            metadata=json.loads(row[8]),
        )

    async def update_agent(self, agent: Agent) -> None:
        """Update existing agent.

        Args:
            agent: Agent with updated data

        Time Complexity: O(1)
        Performance Target: <5ms

        """

        # BUG FIX: see store_agent() above.
        def _write() -> None:
            with self._get_conn() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    UPDATE agents SET
                        status = ?,
                        capabilities = ?,
                        specializations = ?,
                        last_active = ?,
                        total_tasks = ?,
                        successful_tasks = ?,
                        metadata = ?
                    WHERE id = ?
                """,
                    (
                        agent.status.value,
                        json.dumps(agent.capabilities),
                        json.dumps(agent.specializations),
                        agent.last_active.isoformat(),
                        agent.total_tasks,
                        agent.successful_tasks,
                        json.dumps(agent.metadata),
                        agent.id,
                    ),
                )

                conn.commit()

        await asyncio.to_thread(_write)
        self._active_agents_cache = None  # Invalidate cache

    async def get_performance_records_bulk(
        self,
        agent_ids: list[str],
    ) -> dict[str, list[PerformanceRecord]]:
        """Fetch performance records for multiple agents in a single query.

        Args:
            agent_ids: List of agent IDs to fetch records for.

        Returns:
            Dict mapping agent_id → list of PerformanceRecord (most recent first).
            Agents with no records map to an empty list.

        Time Complexity: O(n) where n is total matching records
        Performance Target: <20ms for 1000 records across 100 agents

        """
        if not agent_ids:
            return {}
        # Placeholders are a fixed-length sequence of literal "?" tokens -
        # no user data ever enters the query string itself. Values are bound
        # via the parameterized execute() call below (CWE-89 safe).
        placeholders = ",".join(["?"] * len(agent_ids))
        query = (
            "SELECT agent_id, task_id, task_type, success,"  # noqa: S608 - SQL parameterization reviewed  # nosec B608
            " completion_time_ms, resource_usage, timestamp"
            " FROM performance_records"
            f" WHERE agent_id IN ({placeholders})"
            " ORDER BY timestamp DESC"
        )

        # BUG FIX: see store_agent() above.
        def _read() -> list[tuple]:
            with self._get_conn() as conn:
                return conn.execute(query, agent_ids).fetchall()

        rows = await asyncio.to_thread(_read)

        result: dict[str, list[PerformanceRecord]] = {aid: [] for aid in agent_ids}
        for row in rows:
            record = PerformanceRecord(
                task_id=row[1],
                task_type=row[2],
                success=bool(row[3]),
                completion_time_ms=row[4],
                resource_usage=json.loads(row[5]),
                timestamp=datetime.fromisoformat(row[6]),
            )
            result[row[0]].append(record)
        return result

    async def query_agents(self, status: AgentStatus | None = None) -> list[Agent]:
        """Query agents by status.

        Args:
            status: Filter by status (None for all agents)

        Returns:
            List of matching agents

        Time Complexity: O(n) where n is matching agents
        Performance Target: <50ms for 1000 agents

        """

        # BUG FIX: see store_agent() above.
        def _read() -> list[tuple]:
            with self._get_conn() as conn:
                if status:
                    return conn.execute(
                        """SELECT id, status, capabilities, specializations,
                                  created_at, last_active, total_tasks, successful_tasks, metadata
                           FROM agents WHERE status = ?""",
                        (status.value,),
                    ).fetchall()
                return conn.execute(
                    """SELECT id, status, capabilities, specializations,
                              created_at, last_active, total_tasks, successful_tasks, metadata
                       FROM agents""",
                ).fetchall()

        rows = await asyncio.to_thread(_read)

        if not rows:
            return []

        # Single bulk query for all performance records - eliminates N+1
        agent_ids = [row[0] for row in rows]
        perf_map = await self.get_performance_records_bulk(agent_ids)

        agents = []
        for row in rows:
            agent = Agent(
                id=row[0],
                status=AgentStatus(row[1]),
                capabilities=json.loads(row[2]),
                specializations=json.loads(row[3]),
                performance_history=perf_map.get(row[0], []),
                created_at=datetime.fromisoformat(row[4]),
                last_active=datetime.fromisoformat(row[5]),
                total_tasks=row[6],
                successful_tasks=row[7],
                metadata=json.loads(row[8]),
            )
            agents.append(agent)
        return agents

    async def count_agents(self, status: AgentStatus | None = None) -> int:
        """Count agents by status, without materializing Agent objects
        or fetching any performance history.

        Added as a lightweight alternative to `len(await
        query_agents(...))` for callers that only need a count --
        query_agents() constructs a full Agent object per row AND
        bulk-fetches every one of those agents' complete performance
        record history (see get_performance_records_bulk()), which is
        pure waste when only a count is needed. Motivating caller:
        PopulationManager.evaluate_population_size(), which previously
        called the unfiltered query_agents() on every evaluation purely
        to compute a total count.

        Args:
            status: Filter by status (None for all agents)

        Returns:
            Number of matching agents

        Time Complexity: O(1) -- a single COUNT(*) query, no row
        materialization
        Performance Target: <5ms for any population size

        """

        def _read() -> int:
            with self._get_conn() as conn:
                if status:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM agents WHERE status = ?",
                        (status.value,),
                    ).fetchone()
                else:
                    row = conn.execute("SELECT COUNT(*) FROM agents").fetchone()
                return row[0] if row else 0

        return await asyncio.to_thread(_read)

    async def get_active_agents(self) -> list[Agent]:
        """Get all active agents.

        Returns:
            List of active agents

        Time Complexity: O(1) cached, O(n) on cache miss
        Performance Target: <50ms for 1000 agents

        Validates: Requirement 7.5

        """
        if self._active_agents_cache is not None:
            return list(self._active_agents_cache)
        agents = await self.query_agents(status=AgentStatus.ACTIVE)
        self._active_agents_cache = agents
        return list(agents)

    async def store_performance_record(self, agent_id: str, record: PerformanceRecord) -> None:
        """Store performance record for agent.

        Args:
            agent_id: Agent identifier
            record: Performance record to store

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirement 12.1, 12.5

        """

        # BUG FIX: see store_agent() above.
        def _write() -> None:
            with self._get_conn() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO performance_records (
                        agent_id, task_id, task_type, success,
                        completion_time_ms, resource_usage, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        agent_id,
                        record.task_id,
                        record.task_type,
                        1 if record.success else 0,
                        record.completion_time_ms,
                        json.dumps(record.resource_usage),
                        record.timestamp.isoformat(),
                    ),
                )

                conn.commit()

        await asyncio.to_thread(_write)
        # BUG FIX: cached Agent objects returned by get_active_agents()
        # carry a performance_history snapshot taken at cache-population
        # time (see query_agents() -> get_performance_records_bulk()).
        # Without invalidating here, a newly stored performance record
        # would not be reflected in get_active_agents() results until
        # some unrelated agent-level write (store_agent/update_agent/
        # create_agent_atomic) happened to invalidate the cache for a
        # different reason -- stale performance data feeding whatever
        # strategy/assignment logic reads it in the meantime.
        self._active_agents_cache = None  # Invalidate cache

    async def get_performance_records(
        self,
        agent_id: str,
        task_type: str | None = None,
        limit: int | None = None,
    ) -> list[PerformanceRecord]:
        """Get performance records for agent.

        Args:
            agent_id: Agent identifier
            task_type: Filter by task type (None for all)
            limit: Maximum number of records (None for all)

        Returns:
            List of performance records, most recent first

        Time Complexity: O(n) where n is matching records
        Performance Target: <20ms for 1000 records

        """
        if task_type:
            query = """
                SELECT task_id, task_type, success, completion_time_ms,
                       resource_usage, timestamp
                FROM performance_records
                WHERE agent_id = ? AND task_type = ?
                ORDER BY timestamp DESC
            """
            params: tuple = (agent_id, task_type)
        else:
            query = """
                SELECT task_id, task_type, success, completion_time_ms,
                       resource_usage, timestamp
                FROM performance_records
                WHERE agent_id = ?
                ORDER BY timestamp DESC
            """
            params = (agent_id,)

        if limit:
            query += " LIMIT ?"
            params = (*params, limit)

        # BUG FIX: see store_agent() above.
        def _read() -> list[tuple]:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()

        rows = await asyncio.to_thread(_read)

        records = []
        for row in rows:
            record = PerformanceRecord(
                task_id=row[0],
                task_type=row[1],
                success=bool(row[2]),
                completion_time_ms=row[3],
                resource_usage=json.loads(row[4]),
                timestamp=datetime.fromisoformat(row[5]),
            )
            records.append(record)

        return records

    async def store_evolution_event(self, event: dict[str, Any]) -> None:
        """Store evolution event.

        Args:
            event: Evolution event data

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirements 1.4, 3.5, 5.3, 20.1

        """

        # BUG FIX: see store_agent() above.
        def _write() -> None:
            with self._get_conn() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO evolution_events (
                        event_type, agent_ids, reason, details, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        event["event_type"],
                        json.dumps(event["agent_ids"]),
                        event["reason"],
                        json.dumps(event["details"]),
                        event["timestamp"],
                    ),
                )

                conn.commit()

        await asyncio.to_thread(_write)

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
        Performance Target: <5ms

        Validates: Requirement 7.4

        """
        # For now, store as metadata in agent
        # In production, would have separate assignments table
        #
        # BUG FIX: this is a read-modify-write on agent.metadata --
        # get_agent() reads the current row, then update_agent() writes
        # a whole new metadata blob back. Without serialization, two
        # concurrent calls to this method for the SAME agent_id (e.g.
        # two tasks assigned to the same agent at nearly the same time)
        # can both read the agent before either writes, so whichever
        # update_agent() call commits last silently overwrites the
        # other's appended assignment entry -- a genuine lost-update
        # race with no error raised anywhere. The instance-level
        # asyncio.Lock below serializes this sequence.
        async with self._metadata_lock:
            agent = await self.get_agent(agent_id)
            if agent:
                if "assignments" not in agent.metadata:
                    agent.metadata["assignments"] = []
                agent.metadata["assignments"].append(
                    {"task_id": task_id, "timestamp": timestamp.isoformat()},
                )
                await self.update_agent(agent)

    async def create_agent_atomic(self, agent: "Agent", task_requirements: dict[str, Any]) -> None:
        """Store a new agent and its creation event in a single transaction.

        Batches the INSERT for the agent row and the evolution event into one
        commit, reducing round-trips from 3 to 1 and eliminating the separate
        UPDATE for status transition.

        Args:
            agent: Agent to persist (status already set to ACTIVE)
            task_requirements: Requirements that triggered creation

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirements 1.1, 1.4

        """

        # BUG FIX: see store_agent() above.
        def _write() -> None:
            with self._get_conn() as conn:
                cursor = conn.cursor()

                now_iso = datetime.now(tz=UTC).isoformat()

                cursor.execute(
                    """
                    INSERT INTO agents (
                        id, status, capabilities, specializations,
                        created_at, last_active, total_tasks, successful_tasks, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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

                cursor.execute(
                    """
                    INSERT INTO evolution_events (
                        event_type, agent_ids, reason, details, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "creation",
                        json.dumps([agent.id]),
                        "task_requirements",
                        json.dumps(task_requirements),
                        now_iso,
                    ),
                )

                conn.commit()

        await asyncio.to_thread(_write)
        self._active_agents_cache = None
