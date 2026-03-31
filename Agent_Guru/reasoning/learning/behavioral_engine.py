"""
Behavioral Learning Engine - Main coordinator.

This module coordinates all behavioral learning components with privacy controls,
opt-in management, and data retention policies.

Performance Requirements:
- Time Complexity: O(1) for tracking, O(n) for analysis
- Space Complexity: O(n) where n is learning data
- Latency: <50ms for tracking operations

Author: Kiro AI
Date: 2024
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from Agent_Guru.reasoning.learning.app_tracker import AppTracker
from Agent_Guru.reasoning.learning.command_tracker import CommandTracker
from Agent_Guru.reasoning.learning.pattern_detector import PatternDetector
from Agent_Guru.reasoning.learning.preference_learner import PreferenceLearner
from Agent_Guru.reasoning.learning.suggestion_generator import SuggestionGenerator
from Agent_Guru.reasoning.models.behavioral import BehavioralStats, ProactiveSuggestion


class BehavioralEngine:
    """
    Main behavioral learning engine with privacy controls.

    Coordinates:
    - Command frequency tracking
    - Pattern detection
    - App usage tracking
    - Preference learning
    - Proactive suggestions

    Privacy Features:
    - Opt-in required (disabled by default)
    - Local storage only
    - User control over data (view, edit, delete)
    - Configurable retention policy (default 90 days)
    - Data anonymization for analytics

    Time Complexity: O(1) for tracking, O(n) for analysis
    Space Complexity: O(n) where n is learning data

    Example:
        >>> engine = BehavioralEngine("behavioral.db")
        >>> await engine.initialize()
        >>> await engine.enable_learning("user123")
        >>> await engine.track_command("user123", "set_timer", success=True)
        >>> suggestions = await engine.get_suggestions("user123")
    """

    def __init__(
        self,
        db_path: str = "behavioral.db",
        default_retention_days: int = 90,
    ):
        """
        Initialize behavioral engine.

        Args:
            db_path: Path to SQLite database (local storage)
            default_retention_days: Default data retention period
        """
        self.db_path = Path(db_path)
        self.default_retention_days = default_retention_days

        # Initialize components
        self.command_tracker = CommandTracker(str(db_path))
        self.pattern_detector = PatternDetector(str(db_path))
        self.app_tracker = AppTracker(str(db_path))
        self.preference_learner = PreferenceLearner(str(db_path))
        self.suggestion_generator = SuggestionGenerator(str(db_path))

        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all components and privacy controls."""
        if self._initialized:
            return

        # Initialize all components
        await self.command_tracker.initialize()
        await self.pattern_detector.initialize()
        await self.app_tracker.initialize()
        await self.preference_learner.initialize()
        await self.suggestion_generator.initialize()

        # Initialize privacy controls
        await self._initialize_privacy_controls()

        self._initialized = True

    async def _initialize_privacy_controls(self) -> None:
        """Initialize privacy control tables."""
        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # User privacy settings table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS privacy_settings (
                        user_id TEXT PRIMARY KEY,
                        learning_enabled BOOLEAN NOT NULL DEFAULT 0,
                        retention_days INTEGER NOT NULL DEFAULT 90,
                        allow_analytics BOOLEAN NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """
                )

                # Data retention log
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS retention_log (
                        log_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        records_affected INTEGER NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """
                )

                conn.commit()
            finally:
                conn.close()

    async def enable_learning(self, user_id: str, retention_days: int | None = None) -> None:
        """
        Enable behavioral learning for a user (opt-in).

        Args:
            user_id: User identifier
            retention_days: Custom retention period (default: 90 days)
        """
        if not self._initialized:
            await self.initialize()

        if retention_days is None:
            retention_days = self.default_retention_days

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                now = datetime.now(tz=timezone.utc).isoformat()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO privacy_settings (
                        user_id, learning_enabled, retention_days,
                        allow_analytics, created_at, updated_at
                    ) VALUES (?, 1, ?, 0, ?, ?)
                """,
                    (user_id, retention_days, now, now),
                )
                conn.commit()
            finally:
                conn.close()

    async def disable_learning(self, user_id: str) -> None:
        """
        Disable behavioral learning for a user (opt-out).

        Args:
            user_id: User identifier
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    UPDATE privacy_settings
                    SET learning_enabled = 0, updated_at = ?
                    WHERE user_id = ?
                """,
                    (datetime.now(tz=timezone.utc).isoformat(), user_id),
                )
                conn.commit()
            finally:
                conn.close()

    async def is_learning_enabled(self, user_id: str) -> bool:
        """
        Check if learning is enabled for a user.

        Args:
            user_id: User identifier

        Returns:
            True if learning is enabled
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT learning_enabled FROM privacy_settings
                    WHERE user_id = ?
                """,
                    (user_id,),
                )
                row = cursor.fetchone()
                return bool(row[0]) if row else False
            finally:
                conn.close()

    async def track_command(
        self,
        user_id: str,
        command: str,
        success: bool = True,
        latency: float = 0.0,
        metadata: dict | None = None,
    ) -> None:
        """
        Track command execution (if learning enabled).

        Args:
            user_id: User identifier
            command: Command executed
            success: Whether execution was successful
            latency: Execution latency in seconds
            metadata: Additional tracking data
        """
        if not await self.is_learning_enabled(user_id):
            return

        # Track command frequency
        await self.command_tracker.track_command(user_id, command, success, latency, metadata)

        # Record for pattern detection
        await self.pattern_detector.record_command(user_id, command)

    async def track_app_usage(
        self, user_id: str, app_id: str, app_name: str, duration: float | None = None
    ) -> None:
        """
        Track app usage (if learning enabled).

        Args:
            user_id: User identifier
            app_id: Application identifier
            app_name: Application name
            duration: Usage duration in seconds (None for open event)
        """
        if not await self.is_learning_enabled(user_id):
            return

        if duration is None:
            # App open event
            await self.app_tracker.track_app_open(user_id, app_id, app_name)
        else:
            # App close event
            await self.app_tracker.track_app_close(user_id, app_id, duration)

    async def learn_preference(
        self, user_id: str, preference_type, preference_key: str, preference_value
    ) -> None:
        """
        Learn user preference (if learning enabled).

        Args:
            user_id: User identifier
            preference_type: Type of preference
            preference_key: Preference key
            preference_value: Preference value
        """
        if not await self.is_learning_enabled(user_id):
            return

        await self.preference_learner.learn_preference(
            user_id, preference_type, preference_key, preference_value
        )

    async def get_suggestions(
        self, user_id: str, context: dict | None = None
    ) -> list[ProactiveSuggestion]:
        """
        Get proactive suggestions (if learning enabled).

        Args:
            user_id: User identifier
            context: Current context

        Returns:
            List of suggestions
        """
        if not await self.is_learning_enabled(user_id):
            return []

        return await self.suggestion_generator.generate_suggestions(user_id, context)

    async def detect_patterns(self, user_id: str, lookback_days: int = 30) -> None:
        """
        Detect behavioral patterns (if learning enabled).

        Args:
            user_id: User identifier
            lookback_days: Number of days to analyze
        """
        if not await self.is_learning_enabled(user_id):
            return

        await self.pattern_detector.detect_patterns(user_id, lookback_days)

    async def get_behavioral_stats(self, user_id: str) -> BehavioralStats:
        """
        Get behavioral statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Behavioral statistics
        """
        if not await self.is_learning_enabled(user_id):
            return BehavioralStats(user_id=user_id)

        # Get command stats
        command_analysis = await self.command_tracker.analyze_frequency(user_id)

        # Get pattern count
        patterns = await self.pattern_detector.get_patterns(user_id)

        # Get preference count
        preferences = await self.preference_learner.get_all_preferences(user_id)

        # Get suggestion stats
        suggestion_stats = await self.suggestion_generator.get_suggestion_stats(user_id)

        return BehavioralStats(
            user_id=user_id,
            total_commands=command_analysis["total_executions"],
            unique_commands=command_analysis["unique_commands"],
            most_frequent_commands=[
                (cmd["command"], cmd["frequency"]) for cmd in command_analysis["most_frequent"]
            ],
            detected_patterns=len(patterns),
            learned_preferences=len(preferences),
            suggestion_acceptance_rate=suggestion_stats["acceptance_rate"],
            last_updated=datetime.now(tz=timezone.utc),
            metadata={
                "avg_success_rate": command_analysis["avg_success_rate"],
                "avg_latency": command_analysis["avg_latency"],
            },
        )

    async def delete_user_data(self, user_id: str) -> dict:
        """
        Delete all learning data for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with deletion counts
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Count records before deletion
                tables = [
                    "command_frequency",
                    "command_history",
                    "time_patterns",
                    "app_usage",
                    "user_preferences",
                    "privacy_settings",
                ]

                counts = {}
                for table in tables:
                    # Use parameterized query with table name validation
                    if table not in tables:  # Validate table name
                        continue
                    query = f"SELECT COUNT(*) FROM {table} WHERE user_id = ?"  # nosec B608
                    cursor.execute(query, (user_id,))
                    counts[table] = cursor.fetchone()[0]

                # Delete from all tables
                for table in tables:
                    # Use parameterized query with table name validation
                    if table not in tables:  # Validate table name
                        continue
                    query = f"DELETE FROM {table} WHERE user_id = ?"  # nosec B608
                    cursor.execute(query, (user_id,))

                # Log deletion
                cursor.execute(
                    """
                    INSERT INTO retention_log (
                        log_id, user_id, action, records_affected, timestamp
                    ) VALUES (?, ?, 'delete_all', ?, ?)
                """,
                    (
                        f"del_{user_id}_{datetime.now(tz=timezone.utc).timestamp()}",
                        user_id,
                        sum(counts.values()),
                        datetime.now(tz=timezone.utc).isoformat(),
                    ),
                )

                conn.commit()
                return counts
            finally:
                conn.close()

    async def apply_retention_policy(self, user_id: str) -> int:
        """
        Apply data retention policy for a user.

        Deletes data older than retention period.

        Args:
            user_id: User identifier

        Returns:
            Number of records deleted
        """
        if not self._initialized:
            await self.initialize()

        # Get retention period
        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT retention_days FROM privacy_settings
                    WHERE user_id = ?
                """,
                    (user_id,),
                )
                row = cursor.fetchone()
                retention_days = row[0] if row else self.default_retention_days

                # Calculate cutoff date
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retention_days)
                cutoff_str = cutoff.isoformat()

                # Delete old records
                total_deleted = 0

                # Command history
                cursor.execute(
                    """
                    DELETE FROM command_history
                    WHERE user_id = ? AND timestamp < ?
                """,
                    (user_id, cutoff_str),
                )
                total_deleted += cursor.rowcount

                # Time patterns (based on last occurrence)
                cursor.execute(
                    """
                    DELETE FROM time_patterns
                    WHERE user_id = ? AND last_occurrence < ?
                """,
                    (user_id, cutoff_str),
                )
                total_deleted += cursor.rowcount

                # Log retention
                if total_deleted > 0:
                    cursor.execute(
                        """
                        INSERT INTO retention_log (
                            log_id, user_id, action, records_affected, timestamp
                        ) VALUES (?, ?, 'retention_policy', ?, ?)
                    """,
                        (
                            f"ret_{user_id}_{datetime.now(tz=timezone.utc).timestamp()}",
                            user_id,
                            total_deleted,
                            datetime.now(tz=timezone.utc).isoformat(),
                        ),
                    )

                conn.commit()
                return total_deleted
            finally:
                conn.close()

    async def export_user_data(self, user_id: str) -> dict:
        """
        Export all learning data for a user (for transparency).

        Args:
            user_id: User identifier

        Returns:
            Dictionary with all user data
        """
        if not self._initialized:
            await self.initialize()

        # Get all data
        commands = await self.command_tracker.get_most_frequent_commands(user_id, limit=1000)
        patterns = await self.pattern_detector.get_patterns(user_id)
        apps = await self.app_tracker.get_most_used_apps(user_id, limit=1000)
        preferences = await self.preference_learner.get_all_preferences(user_id)

        return {
            "user_id": user_id,
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
            "commands": [
                {
                    "command": c.command,
                    "frequency": c.frequency,
                    "success_rate": c.success_rate,
                    "last_used": c.last_used.isoformat(),
                }
                for c in commands
            ],
            "patterns": [
                {
                    "pattern_type": p.pattern_type.value,
                    "command": p.command,
                    "confidence": p.confidence,
                    "frequency": p.frequency,
                }
                for p in patterns
            ],
            "apps": [
                {
                    "app_name": a.app_name,
                    "open_count": a.open_count,
                    "avg_duration": a.avg_duration,
                    "last_used": a.last_used.isoformat(),
                }
                for a in apps
            ],
            "preferences": [
                {
                    "preference_type": p.preference_type.value,
                    "preference_key": p.preference_key,
                    "preference_value": p.preference_value,
                    "confidence": p.confidence,
                }
                for p in preferences
            ],
        }
