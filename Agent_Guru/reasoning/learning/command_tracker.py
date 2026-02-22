"""
Command frequency tracking system.

This module tracks user command frequency, success rates, and execution patterns
to enable learning and optimization of the reasoning engine.

Performance Requirements:
- Time Complexity: O(1) for tracking, O(n log n) for frequency analysis
- Space Complexity: O(n) where n is number of unique commands
- Latency: <10ms for tracking, <50ms for analysis

Author: Kiro AI
Date: 2024
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from Agent_Guru.reasoning.models.behavioral import CommandFrequency


class CommandTracker:
    """
    Tracks command frequency and success rates per user.

    Time Complexity: O(1) for tracking, O(n log n) for analysis
    Space Complexity: O(n) where n is unique commands

    Example:
        >>> tracker = CommandTracker("commands.db")
        >>> await tracker.initialize()
        >>> await tracker.track_command("user123", "set_timer", success=True, latency=0.5)
        >>> freq = await tracker.get_command_frequency("user123", "set_timer")
    """

    def __init__(self, db_path: str = "behavioral.db"):
        """
        Initialize command tracker.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        async with self._lock:
            if self._initialized:
                return

            # Create database directory
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create tables
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Command frequency table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS command_frequency (
                        command TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        frequency INTEGER NOT NULL DEFAULT 0,
                        last_used TEXT NOT NULL,
                        success_rate REAL NOT NULL DEFAULT 1.0,
                        total_executions INTEGER NOT NULL DEFAULT 0,
                        successful_executions INTEGER NOT NULL DEFAULT 0,
                        avg_latency REAL NOT NULL DEFAULT 0.0,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (user_id, command)
                    )
                """
                )

                # Create indexes
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_command_user_id
                    ON command_frequency(user_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_command_frequency
                    ON command_frequency(user_id, frequency DESC)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_command_last_used
                    ON command_frequency(user_id, last_used DESC)
                """
                )

                conn.commit()
            finally:
                conn.close()

            self._initialized = True

    async def track_command(
        self,
        user_id: str,
        command: str,
        success: bool = True,
        latency: float = 0.0,
        metadata: Optional[dict] = None,
    ) -> CommandFrequency:
        """
        Track command execution.

        Time Complexity: O(1)

        Args:
            user_id: User identifier
            command: Command text or intent type
            success: Whether execution was successful
            latency: Execution latency in seconds
            metadata: Additional tracking data

        Returns:
            Updated command frequency
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Get existing record
                cursor.execute(
                    """
                    SELECT * FROM command_frequency
                    WHERE user_id = ? AND command = ?
                """,
                    (user_id, command),
                )
                row = cursor.fetchone()

                if row:
                    # Update existing record
                    freq = self._row_to_frequency(row)
                    freq.update_execution(success, latency)

                    cursor.execute(
                        """
                        UPDATE command_frequency
                        SET frequency = ?,
                            last_used = ?,
                            success_rate = ?,
                            total_executions = ?,
                            successful_executions = ?,
                            avg_latency = ?,
                            metadata = ?,
                            updated_at = ?
                        WHERE user_id = ? AND command = ?
                    """,
                        (
                            freq.frequency,
                            freq.last_used.isoformat(),
                            freq.success_rate,
                            freq.total_executions,
                            freq.successful_executions,
                            freq.avg_latency,
                            json.dumps(freq.metadata),
                            datetime.utcnow().isoformat(),
                            user_id,
                            command,
                        ),
                    )
                else:
                    # Create new record
                    freq = CommandFrequency(
                        command=command,
                        user_id=user_id,
                        frequency=1,
                        last_used=datetime.utcnow(),
                        success_rate=1.0 if success else 0.0,
                        total_executions=1,
                        successful_executions=1 if success else 0,
                        avg_latency=latency,
                        metadata=metadata or {},
                    )

                    now = datetime.utcnow().isoformat()
                    cursor.execute(
                        """
                        INSERT INTO command_frequency (
                            command, user_id, frequency, last_used,
                            success_rate, total_executions, successful_executions,
                            avg_latency, metadata, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            command,
                            user_id,
                            freq.frequency,
                            freq.last_used.isoformat(),
                            freq.success_rate,
                            freq.total_executions,
                            freq.successful_executions,
                            freq.avg_latency,
                            json.dumps(freq.metadata),
                            now,
                            now,
                        ),
                    )

                conn.commit()
                return freq
            finally:
                conn.close()

    async def get_command_frequency(self, user_id: str, command: str) -> Optional[CommandFrequency]:
        """
        Get frequency data for a specific command.

        Time Complexity: O(1) with index

        Args:
            user_id: User identifier
            command: Command text

        Returns:
            Command frequency or None
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM command_frequency
                    WHERE user_id = ? AND command = ?
                """,
                    (user_id, command),
                )
                row = cursor.fetchone()
                return self._row_to_frequency(row) if row else None
            finally:
                conn.close()

    async def get_most_frequent_commands(
        self, user_id: str, limit: int = 10, min_frequency: int = 1
    ) -> list[CommandFrequency]:
        """
        Get most frequent commands for a user.

        Time Complexity: O(n log n) for sorting

        Args:
            user_id: User identifier
            limit: Maximum number of commands to return
            min_frequency: Minimum frequency threshold

        Returns:
            List of command frequencies sorted by frequency
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM command_frequency
                    WHERE user_id = ? AND frequency >= ?
                    ORDER BY frequency DESC
                    LIMIT ?
                """,
                    (user_id, min_frequency, limit),
                )
                rows = cursor.fetchall()
                return [self._row_to_frequency(row) for row in rows]
            finally:
                conn.close()

    async def get_recent_commands(
        self, user_id: str, since: Optional[datetime] = None, limit: int = 100
    ) -> list[CommandFrequency]:
        """
        Get recently used commands.

        Time Complexity: O(n log n) for sorting

        Args:
            user_id: User identifier
            since: Get commands used after this time (default: last 7 days)
            limit: Maximum number of commands

        Returns:
            List of command frequencies sorted by last used
        """
        if not self._initialized:
            await self.initialize()

        if since is None:
            since = datetime.utcnow() - timedelta(days=7)

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM command_frequency
                    WHERE user_id = ? AND last_used >= ?
                    ORDER BY last_used DESC
                    LIMIT ?
                """,
                    (user_id, since.isoformat(), limit),
                )
                rows = cursor.fetchall()
                return [self._row_to_frequency(row) for row in rows]
            finally:
                conn.close()

    async def analyze_frequency(self, user_id: str) -> dict:
        """
        Analyze command frequency patterns.

        Time Complexity: O(n) where n is number of commands

        Args:
            user_id: User identifier

        Returns:
            Analysis dictionary with statistics
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Get all commands
                cursor.execute(
                    """
                    SELECT * FROM command_frequency
                    WHERE user_id = ?
                """,
                    (user_id,),
                )
                rows = cursor.fetchall()
                commands = [self._row_to_frequency(row) for row in rows]

                if not commands:
                    return {
                        "total_commands": 0,
                        "unique_commands": 0,
                        "total_executions": 0,
                        "avg_success_rate": 0.0,
                        "avg_latency": 0.0,
                        "most_frequent": [],
                        "least_successful": [],
                    }

                # Calculate statistics
                total_executions = sum(c.total_executions for c in commands)
                avg_success_rate = sum(c.success_rate for c in commands) / len(commands)
                avg_latency = sum(c.avg_latency for c in commands) / len(commands)

                # Get most frequent
                most_frequent = sorted(commands, key=lambda c: c.frequency, reverse=True)[:10]

                # Get least successful (with min 5 executions)
                least_successful = sorted(
                    [c for c in commands if c.total_executions >= 5],
                    key=lambda c: c.success_rate,
                )[:5]

                return {
                    "total_commands": len(commands),
                    "unique_commands": len(commands),
                    "total_executions": total_executions,
                    "avg_success_rate": avg_success_rate,
                    "avg_latency": avg_latency,
                    "most_frequent": [
                        {"command": c.command, "frequency": c.frequency} for c in most_frequent
                    ],
                    "least_successful": [
                        {"command": c.command, "success_rate": c.success_rate}
                        for c in least_successful
                    ],
                }
            finally:
                conn.close()

    async def get_command_count(self, user_id: str) -> int:
        """
        Get total number of unique commands for a user.

        Time Complexity: O(1) with index

        Args:
            user_id: User identifier

        Returns:
            Number of unique commands
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM command_frequency
                    WHERE user_id = ?
                """,
                    (user_id,),
                )
                return cursor.fetchone()[0]
            finally:
                conn.close()

    def _row_to_frequency(self, row: tuple) -> CommandFrequency:
        """Convert database row to CommandFrequency object."""
        return CommandFrequency(
            command=row[0],
            user_id=row[1],
            frequency=row[2],
            last_used=datetime.fromisoformat(row[3]),
            success_rate=row[4],
            total_executions=row[5],
            successful_executions=row[6],
            avg_latency=row[7],
            metadata=json.loads(row[8]),
        )
