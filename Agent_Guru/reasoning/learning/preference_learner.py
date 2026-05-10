"""User preference learning system.

This module learns user preferences from behavior including tone, confirmation,
tool choices, and other interaction patterns.

Performance Requirements:
- Time Complexity: O(1) for updates, O(n) for queries
- Space Complexity: O(n) where n is number of preferences
- Latency: <10ms for updates, <20ms for queries

Author: Kiro AI
Date: 2024
"""

import asyncio
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from Agent_Guru.reasoning.models.behavioral import PreferenceType, UserPreference


class PreferenceLearner:
    """Learns and manages user preferences.

    Tracks preferences for:
    - Tone (professional vs casual)
    - Confirmation (always confirm vs trust)
    - Tool choices (preferred services)
    - Verbosity (concise vs detailed)
    - Proactivity (suggestions on/off)

    Time Complexity: O(1) for updates, O(n) for queries
    Space Complexity: O(n) where n is preferences

    Example:
        >>> learner = PreferenceLearner("behavioral.db")
        >>> await learner.initialize()
        >>> await learner.learn_preference(
        ...     "user123", PreferenceType.TOOL, "music_service", "spotify"
        ... )
        >>> pref = await learner.get_preference("user123", "music_service")

    """

    def __init__(self, db_path: str = "behavioral.db", decay_weight: float = 0.2) -> None:
        """Initialize preference learner.

        Args:
            db_path: Path to SQLite database
            decay_weight: Weight for new observations (0.0-1.0)

        """
        self.db_path = Path(db_path)
        self.decay_weight = decay_weight
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

                # User preferences table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        preference_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        preference_type TEXT NOT NULL,
                        preference_key TEXT NOT NULL,
                        preference_value TEXT NOT NULL,
                        confidence REAL NOT NULL DEFAULT 0.5,
                        learned_from TEXT NOT NULL,
                        sample_count INTEGER NOT NULL DEFAULT 1,
                        last_updated TEXT NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        UNIQUE(user_id, preference_key)
                    )
                """,
                )

                # Create indexes
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_pref_user_id
                    ON user_preferences(user_id)
                """,
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_pref_type
                    ON user_preferences(user_id, preference_type)
                """,
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_pref_confidence
                    ON user_preferences(user_id, confidence DESC)
                """,
                )

                conn.commit()
            finally:
                conn.close()

            self._initialized = True

    async def learn_preference(
        self,
        user_id: str,
        preference_type: PreferenceType,
        preference_key: str,
        preference_value: Any,  # noqa: ANN401
        learned_from: str = "behavior",
        metadata: dict | None = None,
    ) -> UserPreference:
        """Learn or update user preference.

        Time Complexity: O(1)

        Args:
            user_id: User identifier
            preference_type: Type of preference
            preference_key: Preference key
            preference_value: Preference value
            learned_from: How preference was learned
            metadata: Additional context

        Returns:
            Updated preference

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Get existing preference
                cursor.execute(
                    """
                    SELECT * FROM user_preferences
                    WHERE user_id = ? AND preference_key = ?
                """,
                    (user_id, preference_key),
                )
                row = cursor.fetchone()

                if row:
                    # Update existing preference
                    pref = self._row_to_preference(row)
                    pref.update_preference(preference_value, self.decay_weight)

                    cursor.execute(
                        """
                        UPDATE user_preferences
                        SET preference_value = ?,
                            confidence = ?,
                            sample_count = ?,
                            last_updated = ?,
                            metadata = ?
                        WHERE preference_id = ?
                    """,
                        (
                            json.dumps(pref.preference_value),
                            pref.confidence,
                            pref.sample_count,
                            pref.last_updated.isoformat(),
                            json.dumps(pref.metadata),
                            pref.preference_id,
                        ),
                    )
                else:
                    # Create new preference
                    pref = UserPreference(
                        preference_id=str(uuid.uuid4()),
                        user_id=user_id,
                        preference_type=preference_type,
                        preference_key=preference_key,
                        preference_value=preference_value,
                        confidence=0.5,
                        learned_from=learned_from,
                        sample_count=1,
                        last_updated=datetime.now(tz=UTC),
                        metadata=metadata or {},
                    )

                    now = datetime.now(tz=UTC).isoformat()
                    cursor.execute(
                        """
                        INSERT INTO user_preferences (
                            preference_id, user_id, preference_type, preference_key,
                            preference_value, confidence, learned_from, sample_count,
                            last_updated, metadata, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            pref.preference_id,
                            user_id,
                            preference_type.value,
                            preference_key,
                            json.dumps(preference_value),
                            pref.confidence,
                            learned_from,
                            pref.sample_count,
                            pref.last_updated.isoformat(),
                            json.dumps(pref.metadata),
                            now,
                        ),
                    )

                conn.commit()
                return pref
            finally:
                conn.close()

    async def get_preference(self, user_id: str, preference_key: str) -> UserPreference | None:
        """Get user preference by key.

        Time Complexity: O(1) with index

        Args:
            user_id: User identifier
            preference_key: Preference key

        Returns:
            User preference or None

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM user_preferences
                    WHERE user_id = ? AND preference_key = ?
                """,
                    (user_id, preference_key),
                )
                row = cursor.fetchone()
                return self._row_to_preference(row) if row else None
            finally:
                conn.close()

    async def get_preferences_by_type(
        self,
        user_id: str,
        preference_type: PreferenceType,
        min_confidence: float = 0.5,
    ) -> list[UserPreference]:
        """Get all preferences of a specific type.

        Time Complexity: O(n) where n is matching preferences

        Args:
            user_id: User identifier
            preference_type: Type of preference
            min_confidence: Minimum confidence threshold

        Returns:
            List of preferences

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM user_preferences
                    WHERE user_id = ? AND preference_type = ? AND confidence >= ?
                    ORDER BY confidence DESC
                """,
                    (user_id, preference_type.value, min_confidence),
                )
                rows = cursor.fetchall()
                return [self._row_to_preference(row) for row in rows]
            finally:
                conn.close()

    async def get_all_preferences(
        self,
        user_id: str,
        min_confidence: float = 0.5,
    ) -> list[UserPreference]:
        """Get all preferences for a user.

        Time Complexity: O(n) where n is total preferences

        Args:
            user_id: User identifier
            min_confidence: Minimum confidence threshold

        Returns:
            List of all preferences

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM user_preferences
                    WHERE user_id = ? AND confidence >= ?
                    ORDER BY confidence DESC
                """,
                    (user_id, min_confidence),
                )
                rows = cursor.fetchall()
                return [self._row_to_preference(row) for row in rows]
            finally:
                conn.close()

    async def learn_tone_preference(
        self,
        user_id: str,
        tone: str,
        context: dict | None = None,
    ) -> UserPreference:
        """Learn tone preference (professional vs casual).

        Args:
            user_id: User identifier
            tone: Tone value ("professional", "casual", "friendly", etc.)
            context: Context where tone was observed

        Returns:
            Updated preference

        """
        return await self.learn_preference(
            user_id=user_id,
            preference_type=PreferenceType.TONE,
            preference_key="tone",
            preference_value=tone,
            learned_from="interaction",
            metadata=context or {},
        )

    async def learn_confirmation_preference(
        self,
        user_id: str,
        always_confirm: bool,
        context: dict | None = None,
    ) -> UserPreference:
        """Learn confirmation preference.

        Args:
            user_id: User identifier
            always_confirm: Whether user prefers confirmations
            context: Context where preference was observed

        Returns:
            Updated preference

        """
        return await self.learn_preference(
            user_id=user_id,
            preference_type=PreferenceType.CONFIRMATION,
            preference_key="always_confirm",
            preference_value=always_confirm,
            learned_from="interaction",
            metadata=context or {},
        )

    async def learn_tool_preference(
        self,
        user_id: str,
        tool_category: str,
        tool_id: str,
        context: dict | None = None,
    ) -> UserPreference:
        """Learn tool preference (e.g., preferred music service).

        Args:
            user_id: User identifier
            tool_category: Category of tool (e.g., "music_service")
            tool_id: Preferred tool identifier
            context: Context where preference was observed

        Returns:
            Updated preference

        """
        return await self.learn_preference(
            user_id=user_id,
            preference_type=PreferenceType.TOOL,
            preference_key=tool_category,
            preference_value=tool_id,
            learned_from="tool_selection",
            metadata=context or {},
        )

    async def learn_verbosity_preference(
        self,
        user_id: str,
        verbosity: str,
        context: dict | None = None,
    ) -> UserPreference:
        """Learn verbosity preference (concise vs detailed).

        Args:
            user_id: User identifier
            verbosity: Verbosity level ("concise", "detailed", "balanced")
            context: Context where preference was observed

        Returns:
            Updated preference

        """
        return await self.learn_preference(
            user_id=user_id,
            preference_type=PreferenceType.VERBOSITY,
            preference_key="verbosity",
            preference_value=verbosity,
            learned_from="interaction",
            metadata=context or {},
        )

    async def learn_proactivity_preference(
        self,
        user_id: str,
        proactive: bool,
        context: dict | None = None,
    ) -> UserPreference:
        """Learn proactivity preference (suggestions on/off).

        Args:
            user_id: User identifier
            proactive: Whether user wants proactive suggestions
            context: Context where preference was observed

        Returns:
            Updated preference

        """
        return await self.learn_preference(
            user_id=user_id,
            preference_type=PreferenceType.PROACTIVITY,
            preference_key="proactive_suggestions",
            preference_value=proactive,
            learned_from="interaction",
            metadata=context or {},
        )

    async def get_preference_summary(self, user_id: str) -> dict:
        """Get summary of all learned preferences.

        Time Complexity: O(n) where n is total preferences

        Args:
            user_id: User identifier

        Returns:
            Summary dictionary

        """
        if not self._initialized:
            await self.initialize()

        prefs = await self.get_all_preferences(user_id, min_confidence=0.5)

        # Group by type
        by_type: dict[str, list[dict]] = {}
        for pref in prefs:
            pref_type = pref.preference_type.value
            if pref_type not in by_type:
                by_type[pref_type] = []

            by_type[pref_type].append(
                {
                    "key": pref.preference_key,
                    "value": pref.preference_value,
                    "confidence": pref.confidence,
                    "sample_count": pref.sample_count,
                },
            )

        return {
            "user_id": user_id,
            "total_preferences": len(prefs),
            "by_type": by_type,
            "high_confidence": [
                {"key": p.preference_key, "value": p.preference_value, "confidence": p.confidence}
                for p in prefs
                if p.confidence >= 0.8  # noqa: PLR2004 - Threshold value

            ],
        }

    async def delete_preference(self, user_id: str, preference_key: str) -> bool:
        """Delete a user preference.

        Args:
            user_id: User identifier
            preference_key: Preference key to delete

        Returns:
            True if deleted, False if not found

        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM user_preferences
                    WHERE user_id = ? AND preference_key = ?
                """,
                    (user_id, preference_key),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def _row_to_preference(self, row: tuple) -> UserPreference:
        """Convert database row to UserPreference object."""
        return UserPreference(
            preference_id=row[0],
            user_id=row[1],
            preference_type=PreferenceType(row[2]),
            preference_key=row[3],
            preference_value=json.loads(row[4]),
            confidence=row[5],
            learned_from=row[6],
            sample_count=row[7],
            last_updated=datetime.fromisoformat(row[8]),
            metadata=json.loads(row[9]),
        )
