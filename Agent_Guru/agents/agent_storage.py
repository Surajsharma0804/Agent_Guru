"""
Agent Storage - SQLite-based storage for agent data and performance history.

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

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .agent_lifecycle import Agent, AgentStatus, PerformanceRecord


class AgentStorage:
    """
    SQLite-based storage for agent orchestration system.

    Provides persistent storage for:
    - Agent data (capabilities, specializations, metadata)
    - Performance records (task outcomes, metrics)
    - Evolution events (creation, merge, split, retirement)

    Time Complexity: O(1) for single operations, O(n) for queries
    Space Complexity: O(n) where n is number of agents

    Example:
        >>> storage = AgentStorage("data/agents.db")
        >>> await storage.store_agent(agent)
        >>> retrieved = await storage.get_agent(agent.id)

    Validates: Requirements 1.1, 1.2, 1.4, 12.1, 12.5
    """

    def __init__(self, db_path: str):
        """
        Initialize storage with database path.

        Args:
            db_path: Path to SQLite database file

        Time Complexity: O(1)
        """
        self.db_path = db_path
        # Cache for active agents — invalidated on any write
        self._active_agents_cache: Optional[list] = None
        self._ensure_database()

    @contextmanager
    def _get_conn(self):
        """Open a SQLite connection, yield it, and guarantee closure.

        WAL mode + synchronous=NORMAL reduces fsync overhead while maintaining
        crash safety. contextlib.closing ensures the connection is always
        released even if an exception is raised.

        Time Complexity: O(1)
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
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
            """
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
            """
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
            """
            )

            # Create indexes for efficient queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agents_status
                ON agents(status)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_performance_agent_type
                ON performance_records(agent_id, task_type)
            """
            )

            # Additional indexes for hot query paths
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_performance_timestamp
                ON performance_records(timestamp)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evolution_type
                ON evolution_events(event_type)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_assignments_agent
                ON task_assignments(agent_id)
            """
            ) if cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='task_assignments'"
            ).fetchone() else None

            conn.commit()

    async def store_agent(self, agent: Agent) -> None:
        """
        Store new agent in database.

        Args:
            agent: Agent to store

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirement 1.1
        """
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
        self._active_agents_cache = None  # Invalidate cache

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
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

            row = cursor.fetchone()

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
        """
        Update existing agent.

        Args:
            agent: Agent with updated data

        Time Complexity: O(1)
        Performance Target: <5ms
        """
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
        self._active_agents_cache = None  # Invalidate cache

    async def get_performance_records_bulk(
        self, agent_ids: list[str]
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
        # Placeholders are a fixed-length sequence of literal "?" tokens —
        # no user data ever enters the query string itself. Values are bound
        # via the parameterized execute() call below (CWE-89 safe).
        placeholders = ",".join(["?"] * len(agent_ids))
        query = (
            "SELECT agent_id, task_id, task_type, success,"
            " completion_time_ms, resource_usage, timestamp"
            " FROM performance_records"
            f" WHERE agent_id IN ({placeholders})"
            " ORDER BY timestamp DESC"
        )
        with self._get_conn() as conn:
            rows = conn.execute(query, agent_ids).fetchall()

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

    async def query_agents(self, status: Optional[AgentStatus] = None) -> list[Agent]:
        """
        Query agents by status.

        Args:
            status: Filter by status (None for all agents)

        Returns:
            List of matching agents

        Time Complexity: O(n) where n is matching agents
        Performance Target: <50ms for 1000 agents
        """
        with self._get_conn() as conn:
            if status:
                rows = conn.execute(
                    """SELECT id, status, capabilities, specializations,
                              created_at, last_active, total_tasks, successful_tasks, metadata
                       FROM agents WHERE status = ?""",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, status, capabilities, specializations,
                              created_at, last_active, total_tasks, successful_tasks, metadata
                       FROM agents"""
                ).fetchall()

        if not rows:
            return []

        # Single bulk query for all performance records — eliminates N+1
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

    async def get_active_agents(self) -> list[Agent]:
        """
        Get all active agents.

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
        """
        Store performance record for agent.

        Args:
            agent_id: Agent identifier
            record: Performance record to store

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirement 12.1, 12.5
        """
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

    async def get_performance_records(
        self, agent_id: str, task_type: Optional[str] = None, limit: Optional[int] = None
    ) -> list[PerformanceRecord]:
        """
        Get performance records for agent.

        Args:
            agent_id: Agent identifier
            task_type: Filter by task type (None for all)
            limit: Maximum number of records (None for all)

        Returns:
            List of performance records, most recent first

        Time Complexity: O(n) where n is matching records
        Performance Target: <20ms for 1000 records
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()

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

            cursor.execute(query, params)
            rows = cursor.fetchall()

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
        """
        Store evolution event.

        Args:
            event: Evolution event data

        Time Complexity: O(1)
        Performance Target: <5ms

        Validates: Requirements 1.4, 3.5, 5.3, 20.1
        """
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

    async def record_task_assignment(
        self, task_id: str, agent_id: str, timestamp: datetime
    ) -> None:
        """
        Record task assignment to agent.

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
        agent = await self.get_agent(agent_id)
        if agent:
            if "assignments" not in agent.metadata:
                agent.metadata["assignments"] = []
            agent.metadata["assignments"].append(
                {"task_id": task_id, "timestamp": timestamp.isoformat()}
            )
            await self.update_agent(agent)

    async def create_agent_atomic(
        self, agent: "Agent", task_requirements: dict[str, Any]
    ) -> None:
        """
        Store a new agent and its creation event in a single transaction.

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
        with self._get_conn() as conn:
            cursor = conn.cursor()

            now_iso = datetime.now().isoformat()

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
        self._active_agents_cache = None
