"""
Feedback storage system for online learning.

This module provides persistent storage for user feedback on intent predictions,
enabling continuous model improvement through online learning.

Performance Requirements:
- Time Complexity: O(1) for insert, O(n) for queries
- Space Complexity: O(n) where n is number of feedback entries
- Latency: <50ms for feedback storage, <200ms for queries

Author: Kiro AI
Date: 2024
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from Agent_Guru.reasoning.models.feedback import (
    FeedbackType,
    IntentFeedback,
    ModelPerformanceMetrics,
)


class FeedbackStore:
    """
    Persistent storage for intent feedback with SQLite backend.

    Time Complexity: O(1) for insert, O(n) for queries
    Space Complexity: O(n) where n is number of feedback entries

    Example:
        >>> store = FeedbackStore("feedback.db")
        >>> await store.initialize()
        >>> feedback = IntentFeedback(...)
        >>> await store.store_feedback(feedback)
    """

    def __init__(self, db_path: str = "feedback.db"):
        """
        Initialize feedback store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        async with self._lock:
            if self._initialized:
                return

            # Create database directory if needed
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create tables
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                # Feedback table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        feedback_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        original_input TEXT NOT NULL,
                        predicted_intent TEXT NOT NULL,
                        predicted_entities TEXT NOT NULL,
                        predicted_confidence REAL NOT NULL,
                        correct_intent TEXT,
                        correct_entities TEXT,
                        feedback_type TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """
                )

                # Performance metrics table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        metric_id TEXT PRIMARY KEY,
                        model_version TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        total_predictions INTEGER NOT NULL,
                        correct_predictions INTEGER NOT NULL,
                        accuracy REAL NOT NULL,
                        intent_accuracies TEXT NOT NULL,
                        avg_confidence REAL NOT NULL,
                        low_confidence_rate REAL NOT NULL,
                        correction_rate REAL NOT NULL,
                        metadata TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """
                )

                # Create indexes for common queries
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_feedback_user_id
                    ON feedback(user_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
                    ON feedback(timestamp)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_feedback_model_version
                    ON feedback(model_version)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_metrics_model_version
                    ON performance_metrics(model_version)
                """
                )

                conn.commit()
            finally:
                conn.close()

            self._initialized = True

    async def store_feedback(self, feedback: IntentFeedback) -> None:
        """
        Store feedback entry.

        Time Complexity: O(1)

        Args:
            feedback: Feedback to store
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO feedback (
                        feedback_id, user_id, timestamp, original_input,
                        predicted_intent, predicted_entities, predicted_confidence,
                        correct_intent, correct_entities, feedback_type,
                        model_version, metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        feedback.feedback_id,
                        feedback.user_id,
                        feedback.timestamp.isoformat(),
                        feedback.original_input,
                        feedback.predicted_intent,
                        json.dumps(feedback.predicted_entities),
                        feedback.predicted_confidence,
                        feedback.correct_intent,
                        json.dumps(feedback.correct_entities)
                        if feedback.correct_entities
                        else None,
                        feedback.feedback_type.value,
                        feedback.model_version,
                        json.dumps(feedback.metadata),
                        datetime.utcnow().isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    async def get_feedback_since(
        self, since: datetime, model_version: Optional[str] = None
    ) -> list[IntentFeedback]:
        """
        Get feedback entries since a given time.

        Time Complexity: O(n) where n is number of matching entries

        Args:
            since: Get feedback after this time
            model_version: Filter by model version (optional)

        Returns:
            List of feedback entries
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                if model_version:
                    cursor.execute(
                        """
                        SELECT * FROM feedback
                        WHERE timestamp >= ? AND model_version = ?
                        ORDER BY timestamp DESC
                    """,
                        (since.isoformat(), model_version),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM feedback
                        WHERE timestamp >= ?
                        ORDER BY timestamp DESC
                    """,
                        (since.isoformat(),),
                    )

                rows = cursor.fetchall()
                return [self._row_to_feedback(row) for row in rows]
            finally:
                conn.close()

    async def get_corrections_for_training(
        self, model_version: str, limit: Optional[int] = None
    ) -> list[IntentFeedback]:
        """
        Get feedback corrections for model retraining.

        Time Complexity: O(n) where n is number of corrections

        Args:
            model_version: Model version to get corrections for
            limit: Maximum number of corrections to return

        Returns:
            List of feedback with corrections
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                query = """
                    SELECT * FROM feedback
                    WHERE model_version = ?
                    AND feedback_type IN ('intent_correction', 'entity_correction', 'negative')
                    ORDER BY timestamp DESC
                """

                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query, (model_version,))
                rows = cursor.fetchall()
                return [self._row_to_feedback(row) for row in rows]
            finally:
                conn.close()

    async def store_metrics(self, metrics: ModelPerformanceMetrics) -> None:
        """
        Store performance metrics.

        Time Complexity: O(1)

        Args:
            metrics: Metrics to store
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO performance_metrics (
                        metric_id, model_version, timestamp, total_predictions,
                        correct_predictions, accuracy, intent_accuracies,
                        avg_confidence, low_confidence_rate, correction_rate,
                        metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        metrics.metric_id,
                        metrics.model_version,
                        metrics.timestamp.isoformat(),
                        metrics.total_predictions,
                        metrics.correct_predictions,
                        metrics.accuracy,
                        json.dumps(metrics.intent_accuracies),
                        metrics.avg_confidence,
                        metrics.low_confidence_rate,
                        metrics.correction_rate,
                        json.dumps(metrics.metadata),
                        datetime.utcnow().isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    async def get_latest_metrics(self, model_version: str) -> Optional[ModelPerformanceMetrics]:
        """
        Get latest performance metrics for a model version.

        Time Complexity: O(log n) due to index

        Args:
            model_version: Model version

        Returns:
            Latest metrics or None
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM performance_metrics
                    WHERE model_version = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """,
                    (model_version,),
                )

                row = cursor.fetchone()
                return self._row_to_metrics(row) if row else None
            finally:
                conn.close()

    async def get_feedback_count(
        self, model_version: Optional[str] = None, since: Optional[datetime] = None
    ) -> int:
        """
        Get count of feedback entries.

        Time Complexity: O(1) with index

        Args:
            model_version: Filter by model version (optional)
            since: Count feedback after this time (optional)

        Returns:
            Number of feedback entries
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.cursor()

                query = "SELECT COUNT(*) FROM feedback WHERE 1=1"
                params: list[Any] = []

                if model_version:
                    query += " AND model_version = ?"
                    params.append(model_version)

                if since:
                    query += " AND timestamp >= ?"
                    params.append(since.isoformat())

                cursor.execute(query, params)
                result = cursor.fetchone()
                return int(result[0]) if result else 0
            finally:
                conn.close()

    def _row_to_feedback(self, row: tuple) -> IntentFeedback:
        """Convert database row to IntentFeedback object."""
        return IntentFeedback(
            feedback_id=row[0],
            user_id=row[1],
            timestamp=datetime.fromisoformat(row[2]),
            original_input=row[3],
            predicted_intent=row[4],
            predicted_entities=json.loads(row[5]),
            predicted_confidence=row[6],
            correct_intent=row[7],
            correct_entities=json.loads(row[8]) if row[8] else None,
            feedback_type=FeedbackType(row[9]),
            model_version=row[10],
            metadata=json.loads(row[11]),
        )

    def _row_to_metrics(self, row: tuple) -> ModelPerformanceMetrics:
        """Convert database row to ModelPerformanceMetrics object."""
        return ModelPerformanceMetrics(
            metric_id=row[0],
            model_version=row[1],
            timestamp=datetime.fromisoformat(row[2]),
            total_predictions=row[3],
            correct_predictions=row[4],
            accuracy=row[5],
            intent_accuracies=json.loads(row[6]),
            avg_confidence=row[7],
            low_confidence_rate=row[8],
            correction_rate=row[9],
            metadata=json.loads(row[10]),
        )
