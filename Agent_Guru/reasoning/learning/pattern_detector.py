"""
Time-based pattern detection system.

This module detects behavioral patterns based on time-of-day, day-of-week,
and other temporal factors to enable proactive suggestions.

Performance Requirements:
- Time Complexity: O(n) for pattern detection where n is command history
- Space Complexity: O(p) where p is number of detected patterns
- Latency: <100ms for pattern detection

Author: Kiro AI
Date: 2024
"""

import asyncio
import json
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from Agent_Guru.reasoning.models.behavioral import PatternType, TimePattern


class PatternDetector:
    """
    Detects time-based behavioral patterns.

    Analyzes command history to identify:
    - Time-of-day patterns (morning routine, evening routine)
    - Day-of-week patterns (weekly meetings, weekend activities)
    - Recurring sequences

    Time Complexity: O(n) for detection where n is history size
    Space Complexity: O(p) where p is number of patterns

    Example:
        >>> detector = PatternDetector("behavioral.db")
        >>> await detector.initialize()
        >>> await detector.detect_patterns("user123")
        >>> patterns = await detector.get_patterns("user123")
    """

    def __init__(
        self,
        db_path: str = "behavioral.db",
        min_occurrences: int = 3,
        time_window_hours: int = 2,
    ):
        """
        Initialize pattern detector.

        Args:
            db_path: Path to SQLite database
            min_occurrences: Minimum occurrences to consider a pattern
            time_window_hours: Time window for grouping (hours)
        """
        self.db_path = Path(db_path)
        self.min_occurrences = min_occurrences
        self.time_window_hours = time_window_hours
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

                # Time patterns table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS time_patterns (
                        pattern_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        pattern_type TEXT NOT NULL,
                        command TEXT NOT NULL,
                        time_of_day INTEGER,
                        day_of_week INTEGER,
                        frequency INTEGER NOT NULL DEFAULT 1,
                        confidence REAL NOT NULL DEFAULT 0.5,
                        last_occurrence TEXT NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """
                )

                # Command history table (for pattern detection)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS command_history (
                        history_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        command TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        hour_of_day INTEGER NOT NULL,
                        day_of_week INTEGER NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}'
                    )
                """
                )

                # Create indexes
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_patterns_user_id
                    ON time_patterns(user_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_patterns_confidence
                    ON time_patterns(user_id, confidence DESC)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_history_user_id
                    ON command_history(user_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_history_timestamp
                    ON command_history(user_id, timestamp DESC)
                """
                )

                conn.commit()
            finally:
                conn.close()

            self._initialized = True

    async def record_command(
        self, user_id: str, command: str, timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record command execution for pattern detection.

        Time Complexity: O(1)

        Args:
            user_id: User identifier
            command: Command executed
            timestamp: Execution time (default: now)
        """
        if not self._initialized:
            await self.initialize()

        if timestamp is None:
            timestamp = datetime.utcnow()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO command_history (
                        history_id, user_id, command, timestamp,
                        hour_of_day, day_of_week, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        command,
                        timestamp.isoformat(),
                        timestamp.hour,
                        timestamp.weekday(),
                        json.dumps({}),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    async def detect_patterns(self, user_id: str, lookback_days: int = 30) -> list[TimePattern]:
        """
        Detect time-based patterns from command history.

        Time Complexity: O(n) where n is history size

        Args:
            user_id: User identifier
            lookback_days: Number of days to analyze

        Returns:
            List of detected patterns
        """
        if not self._initialized:
            await self.initialize()

        since = datetime.utcnow() - timedelta(days=lookback_days)

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Get command history
                cursor.execute(
                    """
                    SELECT command, hour_of_day, day_of_week, timestamp
                    FROM command_history
                    WHERE user_id = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """,
                    (user_id, since.isoformat()),
                )
                history = cursor.fetchall()

                if not history:
                    return []

                # Detect time-of-day patterns
                time_patterns = self._detect_time_of_day_patterns(user_id, history)

                # Detect day-of-week patterns
                day_patterns = self._detect_day_of_week_patterns(user_id, history)

                # Combine patterns
                all_patterns = time_patterns + day_patterns

                # Store patterns
                for pattern in all_patterns:
                    await self._store_pattern(pattern)

                return all_patterns
            finally:
                conn.close()

    def _detect_time_of_day_patterns(self, user_id: str, history: list[tuple]) -> list[TimePattern]:
        """
        Detect time-of-day patterns.

        Groups commands by hour windows and identifies recurring patterns.

        Args:
            user_id: User identifier
            history: Command history tuples

        Returns:
            List of time-of-day patterns
        """
        # Group by command and hour window
        command_hours: dict[str, dict[int, list[datetime]]] = defaultdict(lambda: defaultdict(list))

        for command, hour, _day, timestamp_str in history:
            timestamp = datetime.fromisoformat(timestamp_str)
            # Group into time windows (e.g., 8-10am, 10-12pm)
            hour_window = (hour // self.time_window_hours) * self.time_window_hours
            command_hours[command][hour_window].append(timestamp)

        # Identify patterns
        patterns = []
        for command, hours in command_hours.items():
            for hour_window, timestamps in hours.items():
                if len(timestamps) >= self.min_occurrences:
                    # Calculate confidence based on frequency and consistency
                    frequency = len(timestamps)
                    confidence = min(0.95, 1.0 - (1.0 / (1.0 + frequency * 0.1)))

                    pattern = TimePattern(
                        pattern_id=str(uuid.uuid4()),
                        user_id=user_id,
                        pattern_type=PatternType.TIME_OF_DAY,
                        command=command,
                        time_of_day=hour_window,
                        day_of_week=None,
                        frequency=frequency,
                        confidence=confidence,
                        last_occurrence=max(timestamps),
                        metadata={
                            "hour_window": f"{hour_window:02d}:00-{hour_window+self.time_window_hours:02d}:00",
                            "timestamps": [t.isoformat() for t in timestamps[-5:]],
                        },
                    )
                    patterns.append(pattern)

        return patterns

    def _detect_day_of_week_patterns(self, user_id: str, history: list[tuple]) -> list[TimePattern]:
        """
        Detect day-of-week patterns.

        Identifies commands that occur on specific days of the week.

        Args:
            user_id: User identifier
            history: Command history tuples

        Returns:
            List of day-of-week patterns
        """
        # Group by command and day of week
        command_days: dict[str, dict[int, list[datetime]]] = defaultdict(lambda: defaultdict(list))

        for command, _hour, day, timestamp_str in history:
            timestamp = datetime.fromisoformat(timestamp_str)
            command_days[command][day].append(timestamp)

        # Identify patterns
        patterns = []
        for command, days in command_days.items():
            for day, timestamps in days.items():
                if len(timestamps) >= self.min_occurrences:
                    # Calculate confidence
                    frequency = len(timestamps)
                    confidence = min(0.95, 1.0 - (1.0 / (1.0 + frequency * 0.1)))

                    # Get day name
                    day_names = [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ]

                    pattern = TimePattern(
                        pattern_id=str(uuid.uuid4()),
                        user_id=user_id,
                        pattern_type=PatternType.DAY_OF_WEEK,
                        command=command,
                        time_of_day=None,
                        day_of_week=day,
                        frequency=frequency,
                        confidence=confidence,
                        last_occurrence=max(timestamps),
                        metadata={
                            "day_name": day_names[day],
                            "timestamps": [t.isoformat() for t in timestamps[-5:]],
                        },
                    )
                    patterns.append(pattern)

        return patterns

    async def _store_pattern(self, pattern: TimePattern) -> None:
        """
        Store or update pattern in database.

        Args:
            pattern: Pattern to store
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()

            # Check if pattern exists
            cursor.execute(
                """
                SELECT pattern_id FROM time_patterns
                WHERE user_id = ? AND pattern_type = ? AND command = ?
                AND time_of_day IS ? AND day_of_week IS ?
            """,
                (
                    pattern.user_id,
                    pattern.pattern_type.value,
                    pattern.command,
                    pattern.time_of_day,
                    pattern.day_of_week,
                ),
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing pattern
                cursor.execute(
                    """
                    UPDATE time_patterns
                    SET frequency = ?,
                        confidence = ?,
                        last_occurrence = ?,
                        metadata = ?,
                        updated_at = ?
                    WHERE pattern_id = ?
                """,
                    (
                        pattern.frequency,
                        pattern.confidence,
                        pattern.last_occurrence.isoformat(),
                        json.dumps(pattern.metadata),
                        datetime.utcnow().isoformat(),
                        existing[0],
                    ),
                )
            else:
                # Insert new pattern
                now = datetime.utcnow().isoformat()
                cursor.execute(
                    """
                    INSERT INTO time_patterns (
                        pattern_id, user_id, pattern_type, command,
                        time_of_day, day_of_week, frequency, confidence,
                        last_occurrence, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        pattern.pattern_id,
                        pattern.user_id,
                        pattern.pattern_type.value,
                        pattern.command,
                        pattern.time_of_day,
                        pattern.day_of_week,
                        pattern.frequency,
                        pattern.confidence,
                        pattern.last_occurrence.isoformat(),
                        json.dumps(pattern.metadata),
                        now,
                        now,
                    ),
                )

            conn.commit()
        finally:
            conn.close()

    async def get_patterns(
        self,
        user_id: str,
        pattern_type: Optional[PatternType] = None,
        min_confidence: float = 0.5,
    ) -> list[TimePattern]:
        """
        Get detected patterns for a user.

        Time Complexity: O(n) where n is number of patterns

        Args:
            user_id: User identifier
            pattern_type: Filter by pattern type (optional)
            min_confidence: Minimum confidence threshold

        Returns:
            List of patterns
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                if pattern_type:
                    cursor.execute(
                        """
                        SELECT * FROM time_patterns
                        WHERE user_id = ? AND pattern_type = ? AND confidence >= ?
                        ORDER BY confidence DESC
                    """,
                        (user_id, pattern_type.value, min_confidence),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM time_patterns
                        WHERE user_id = ? AND confidence >= ?
                        ORDER BY confidence DESC
                    """,
                        (user_id, min_confidence),
                    )

                rows = cursor.fetchall()
                return [self._row_to_pattern(row) for row in rows]
            finally:
                conn.close()

    async def get_patterns_for_time(
        self, user_id: str, hour: int, day: int, min_confidence: float = 0.6
    ) -> list[TimePattern]:
        """
        Get patterns matching current time.

        Args:
            user_id: User identifier
            hour: Hour of day (0-23)
            day: Day of week (0-6, Monday=0)
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching patterns
        """
        if not self._initialized:
            await self.initialize()

        # Calculate hour window
        hour_window = (hour // self.time_window_hours) * self.time_window_hours

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Get time-of-day patterns
                cursor.execute(
                    """
                    SELECT * FROM time_patterns
                    WHERE user_id = ? AND pattern_type = ?
                    AND time_of_day = ? AND confidence >= ?
                    ORDER BY confidence DESC
                """,
                    (user_id, PatternType.TIME_OF_DAY.value, hour_window, min_confidence),
                )
                time_patterns = [self._row_to_pattern(row) for row in cursor.fetchall()]

                # Get day-of-week patterns
                cursor.execute(
                    """
                    SELECT * FROM time_patterns
                    WHERE user_id = ? AND pattern_type = ?
                    AND day_of_week = ? AND confidence >= ?
                    ORDER BY confidence DESC
                """,
                    (user_id, PatternType.DAY_OF_WEEK.value, day, min_confidence),
                )
                day_patterns = [self._row_to_pattern(row) for row in cursor.fetchall()]

                return time_patterns + day_patterns
            finally:
                conn.close()

    def _row_to_pattern(self, row: tuple) -> TimePattern:
        """Convert database row to TimePattern object."""
        return TimePattern(
            pattern_id=row[0],
            user_id=row[1],
            pattern_type=PatternType(row[2]),
            command=row[3],
            time_of_day=row[4],
            day_of_week=row[5],
            frequency=row[6],
            confidence=row[7],
            last_occurrence=datetime.fromisoformat(row[8]),
            metadata=json.loads(row[9]),
        )
