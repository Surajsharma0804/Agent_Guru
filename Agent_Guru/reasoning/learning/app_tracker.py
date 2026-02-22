"""
Application usage tracking system.

This module tracks application usage patterns including open count, duration,
and usage patterns to enable context-aware suggestions.

Performance Requirements:
- Time Complexity: O(1) for tracking, O(n log n) for analysis
- Space Complexity: O(n) where n is number of tracked apps
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

from Agent_Guru.reasoning.models.behavioral import AppUsage


class AppTracker:
    """
    Tracks application usage patterns per user.

    Time Complexity: O(1) for tracking, O(n log n) for analysis
    Space Complexity: O(n) where n is number of apps

    Example:
        >>> tracker = AppTracker("behavioral.db")
        >>> await tracker.initialize()
        >>> await tracker.track_app_open("user123", "spotify", "Spotify")
        >>> await tracker.track_app_close("user123", "spotify", duration=300.0)
        >>> usage = await tracker.get_app_usage("user123", "spotify")
    """

    def __init__(self, db_path: str = "behavioral.db"):
        """
        Initialize app tracker.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False
        self._active_sessions: dict[tuple[str, str], datetime] = {}

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

                # App usage table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_usage (
                        app_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        app_name TEXT NOT NULL,
                        open_count INTEGER NOT NULL DEFAULT 0,
                        total_duration REAL NOT NULL DEFAULT 0.0,
                        avg_duration REAL NOT NULL DEFAULT 0.0,
                        last_used TEXT NOT NULL,
                        usage_patterns TEXT NOT NULL DEFAULT '[]',
                        metadata TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (user_id, app_id)
                    )
                """
                )

                # Create indexes
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_app_user_id
                    ON app_usage(user_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_app_open_count
                    ON app_usage(user_id, open_count DESC)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_app_last_used
                    ON app_usage(user_id, last_used DESC)
                """
                )

                conn.commit()
            finally:
                conn.close()

            self._initialized = True

    async def track_app_open(
        self, user_id: str, app_id: str, app_name: str, metadata: Optional[dict] = None
    ) -> AppUsage:
        """
        Track app open event.

        Time Complexity: O(1)

        Args:
            user_id: User identifier
            app_id: Application identifier
            app_name: Application name
            metadata: Additional tracking data

        Returns:
            Updated app usage
        """
        if not self._initialized:
            await self.initialize()

        # Record session start time
        session_key = (user_id, app_id)
        self._active_sessions[session_key] = datetime.utcnow()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Get existing record
                cursor.execute(
                    """
                    SELECT * FROM app_usage
                    WHERE user_id = ? AND app_id = ?
                """,
                    (user_id, app_id),
                )
                row = cursor.fetchone()

                if row:
                    # Update existing record
                    usage = self._row_to_usage(row)
                    usage.open_count += 1
                    usage.last_used = datetime.utcnow()

                    cursor.execute(
                        """
                        UPDATE app_usage
                        SET open_count = ?,
                            last_used = ?,
                            updated_at = ?
                        WHERE user_id = ? AND app_id = ?
                    """,
                        (
                            usage.open_count,
                            usage.last_used.isoformat(),
                            datetime.utcnow().isoformat(),
                            user_id,
                            app_id,
                        ),
                    )
                else:
                    # Create new record
                    usage = AppUsage(
                        app_id=app_id,
                        user_id=user_id,
                        app_name=app_name,
                        open_count=1,
                        total_duration=0.0,
                        avg_duration=0.0,
                        last_used=datetime.utcnow(),
                        usage_patterns=[],
                        metadata=metadata or {},
                    )

                    now = datetime.utcnow().isoformat()
                    cursor.execute(
                        """
                        INSERT INTO app_usage (
                            app_id, user_id, app_name, open_count,
                            total_duration, avg_duration, last_used,
                            usage_patterns, metadata, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            app_id,
                            user_id,
                            app_name,
                            usage.open_count,
                            usage.total_duration,
                            usage.avg_duration,
                            usage.last_used.isoformat(),
                            json.dumps(usage.usage_patterns),
                            json.dumps(usage.metadata),
                            now,
                            now,
                        ),
                    )

                conn.commit()
                return usage
            finally:
                conn.close()

    async def track_app_close(
        self, user_id: str, app_id: str, duration: Optional[float] = None
    ) -> AppUsage:
        """
        Track app close event.

        Time Complexity: O(1)

        Args:
            user_id: User identifier
            app_id: Application identifier
            duration: Session duration in seconds (auto-calculated if None)

        Returns:
            Updated app usage
        """
        if not self._initialized:
            await self.initialize()

        # Calculate duration if not provided
        session_key = (user_id, app_id)
        if duration is None and session_key in self._active_sessions:
            start_time = self._active_sessions[session_key]
            duration = (datetime.utcnow() - start_time).total_seconds()
            del self._active_sessions[session_key]

        if duration is None:
            duration = 0.0

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Get existing record
                cursor.execute(
                    """
                    SELECT * FROM app_usage
                    WHERE user_id = ? AND app_id = ?
                """,
                    (user_id, app_id),
                )
                row = cursor.fetchone()

                if row:
                    # Update existing record
                    usage = self._row_to_usage(row)
                    usage.update_usage(duration)

                    cursor.execute(
                        """
                        UPDATE app_usage
                        SET total_duration = ?,
                            avg_duration = ?,
                            last_used = ?,
                            updated_at = ?
                        WHERE user_id = ? AND app_id = ?
                    """,
                        (
                            usage.total_duration,
                            usage.avg_duration,
                            usage.last_used.isoformat(),
                            datetime.utcnow().isoformat(),
                            user_id,
                            app_id,
                        ),
                    )

                    conn.commit()
                    return usage
                else:
                    # No existing record, create minimal one
                    usage = AppUsage(
                        app_id=app_id,
                        user_id=user_id,
                        app_name=app_id,  # Use app_id as name
                        open_count=1,
                        total_duration=duration,
                        avg_duration=duration,
                        last_used=datetime.utcnow(),
                        usage_patterns=[],
                        metadata={},
                    )

                    now = datetime.utcnow().isoformat()
                    cursor.execute(
                        """
                        INSERT INTO app_usage (
                            app_id, user_id, app_name, open_count,
                            total_duration, avg_duration, last_used,
                            usage_patterns, metadata, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            app_id,
                            user_id,
                            usage.app_name,
                            usage.open_count,
                            usage.total_duration,
                            usage.avg_duration,
                            usage.last_used.isoformat(),
                            json.dumps(usage.usage_patterns),
                            json.dumps(usage.metadata),
                            now,
                            now,
                        ),
                    )

                    conn.commit()
                    return usage
            finally:
                conn.close()

    async def get_app_usage(self, user_id: str, app_id: str) -> Optional[AppUsage]:
        """
        Get usage data for a specific app.

        Time Complexity: O(1) with index

        Args:
            user_id: User identifier
            app_id: Application identifier

        Returns:
            App usage or None
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM app_usage
                    WHERE user_id = ? AND app_id = ?
                """,
                    (user_id, app_id),
                )
                row = cursor.fetchone()
                return self._row_to_usage(row) if row else None
            finally:
                conn.close()

    async def get_most_used_apps(
        self, user_id: str, limit: int = 10, min_open_count: int = 1
    ) -> list[AppUsage]:
        """
        Get most frequently used apps.

        Time Complexity: O(n log n) for sorting

        Args:
            user_id: User identifier
            limit: Maximum number of apps to return
            min_open_count: Minimum open count threshold

        Returns:
            List of app usage sorted by open count
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM app_usage
                    WHERE user_id = ? AND open_count >= ?
                    ORDER BY open_count DESC
                    LIMIT ?
                """,
                    (user_id, min_open_count, limit),
                )
                rows = cursor.fetchall()
                return [self._row_to_usage(row) for row in rows]
            finally:
                conn.close()

    async def get_recently_used_apps(
        self, user_id: str, since: Optional[datetime] = None, limit: int = 20
    ) -> list[AppUsage]:
        """
        Get recently used apps.

        Time Complexity: O(n log n) for sorting

        Args:
            user_id: User identifier
            since: Get apps used after this time (default: last 7 days)
            limit: Maximum number of apps

        Returns:
            List of app usage sorted by last used
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
                    SELECT * FROM app_usage
                    WHERE user_id = ? AND last_used >= ?
                    ORDER BY last_used DESC
                    LIMIT ?
                """,
                    (user_id, since.isoformat(), limit),
                )
                rows = cursor.fetchall()
                return [self._row_to_usage(row) for row in rows]
            finally:
                conn.close()

    async def analyze_usage(self, user_id: str) -> dict:
        """
        Analyze app usage patterns.

        Time Complexity: O(n) where n is number of apps

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

                # Get all apps
                cursor.execute(
                    """
                    SELECT * FROM app_usage
                    WHERE user_id = ?
                """,
                    (user_id,),
                )
                rows = cursor.fetchall()
                apps = [self._row_to_usage(row) for row in rows]

                if not apps:
                    return {
                        "total_apps": 0,
                        "total_opens": 0,
                        "total_duration": 0.0,
                        "avg_session_duration": 0.0,
                        "most_used": [],
                        "longest_sessions": [],
                    }

                # Calculate statistics
                total_opens = sum(a.open_count for a in apps)
                total_duration = sum(a.total_duration for a in apps)
                avg_session_duration = total_duration / total_opens if total_opens > 0 else 0.0

                # Get most used
                most_used = sorted(apps, key=lambda a: a.open_count, reverse=True)[:10]

                # Get longest average sessions
                longest_sessions = sorted(apps, key=lambda a: a.avg_duration, reverse=True)[:5]

                return {
                    "total_apps": len(apps),
                    "total_opens": total_opens,
                    "total_duration": total_duration,
                    "avg_session_duration": avg_session_duration,
                    "most_used": [
                        {"app_name": a.app_name, "open_count": a.open_count} for a in most_used
                    ],
                    "longest_sessions": [
                        {"app_name": a.app_name, "avg_duration": a.avg_duration}
                        for a in longest_sessions
                    ],
                }
            finally:
                conn.close()

    async def get_app_count(self, user_id: str) -> int:
        """
        Get total number of tracked apps for a user.

        Time Complexity: O(1) with index

        Args:
            user_id: User identifier

        Returns:
            Number of tracked apps
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM app_usage
                    WHERE user_id = ?
                """,
                    (user_id,),
                )
                return cursor.fetchone()[0]
            finally:
                conn.close()

    def _row_to_usage(self, row: tuple) -> AppUsage:
        """Convert database row to AppUsage object."""
        return AppUsage(
            app_id=row[0],
            user_id=row[1],
            app_name=row[2],
            open_count=row[3],
            total_duration=row[4],
            avg_duration=row[5],
            last_used=datetime.fromisoformat(row[6]),
            usage_patterns=json.loads(row[7]),
            metadata=json.loads(row[8]),
        )
