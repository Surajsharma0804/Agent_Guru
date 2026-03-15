"""Verification Result Storage for the Verifier System.

SQLite-backed storage for verification results, audit trail,
and accuracy metrics computation.

Requirements: 16.1, 16.5, 8.5
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any
from uuid import UUID

from Agent_Guru.verifier.models import (
    AccuracyMetrics,
    VerificationLogEntry,
    VerificationResult,
    VerificationStatus,
)


class VerificationResultStorage:
    """SQLite-backed storage for verification results.

    Provides:
    - Result storage and retrieval
    - Accuracy metrics computation
    - Latency percentile calculation
    - Log querying with filters
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_log (
                entry_id TEXT PRIMARY KEY,
                result_id TEXT NOT NULL,
                status TEXT NOT NULL,
                confidence REAL NOT NULL,
                latency_ms REAL NOT NULL,
                hallucination_detected INTEGER NOT NULL,
                validation_passed INTEGER NOT NULL,
                loop_detected INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                context_type TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_status ON verification_log(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON verification_log(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_context_type ON verification_log(context_type)"
        )
        self._conn.commit()

    def store(
        self,
        result: VerificationResult,
        context_type: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> VerificationLogEntry:
        """Store a verification result."""
        entry = VerificationLogEntry(
            result_id=result.result_id,
            status=result.status,
            confidence=result.confidence,
            latency_ms=result.latency_ms,
            hallucination_detected=result.hallucination.detected,
            validation_passed=result.validation.valid,
            loop_detected=result.loop_detection.loop_detected,
            context_type=context_type,
            metadata=metadata or {},
        )
        self._conn.execute(
            """
            INSERT INTO verification_log
            (entry_id, result_id, status, confidence, latency_ms,
             hallucination_detected, validation_passed, loop_detected,
             timestamp, context_type, metadata)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(entry.entry_id),
                str(entry.result_id),
                entry.status.value,
                entry.confidence,
                entry.latency_ms,
                int(entry.hallucination_detected),
                int(entry.validation_passed),
                int(entry.loop_detected),
                entry.timestamp.isoformat(),
                entry.context_type,
                json.dumps(entry.metadata),
            ),
        )
        self._conn.commit()
        return entry

    def query(
        self,
        status: VerificationStatus | None = None,
        context_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[VerificationLogEntry]:
        """Query verification log with filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if context_type:
            conditions.append("context_type = ?")
            params.append(context_type)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        rows = self._conn.execute(
            f"SELECT entry_id, result_id, status, confidence, latency_ms, "
            f"hallucination_detected, validation_passed, loop_detected, "
            f"timestamp, context_type, metadata "
            f"FROM verification_log {where} ORDER BY timestamp DESC LIMIT ?",
            params,
        ).fetchall()

        return [
            VerificationLogEntry(
                entry_id=UUID(r[0]),
                result_id=UUID(r[1]),
                status=VerificationStatus(r[2]),
                confidence=r[3],
                latency_ms=r[4],
                hallucination_detected=bool(r[5]),
                validation_passed=bool(r[6]),
                loop_detected=bool(r[7]),
                timestamp=datetime.fromisoformat(r[8]),
                context_type=r[9],
                metadata=json.loads(r[10]),
            )
            for r in rows
        ]

    def compute_accuracy_metrics(self) -> AccuracyMetrics:
        """Compute accuracy metrics from stored results."""
        row = self._conn.execute(
            "SELECT COUNT(*), SUM(hallucination_detected), "
            "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) "
            "FROM verification_log"
        ).fetchone()

        total = row[0] or 0
        hallucinations_detected = row[1] or 0
        failures = row[2] or 0

        # Simplified metrics (without ground truth labels)
        return AccuracyMetrics(
            total_verifications=total,
            true_positives=hallucinations_detected,
            false_positives=max(0, failures - hallucinations_detected),
            true_negatives=max(0, total - failures),
            false_negatives=0,  # Can't compute without ground truth
        )

    def get_latency_percentile(self, percentile: float = 95.0) -> float:
        """Get latency at given percentile (e.g., 95th)."""
        rows = self._conn.execute(
            "SELECT latency_ms FROM verification_log ORDER BY latency_ms"
        ).fetchall()
        if not rows:
            return 0.0
        latencies = [r[0] for r in rows]
        idx = int(len(latencies) * percentile / 100)
        idx = min(idx, len(latencies) - 1)
        return latencies[idx]

    def count(self, status: VerificationStatus | None = None) -> int:
        """Count stored results, optionally filtered by status."""
        if status:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM verification_log WHERE status = ?",
                (status.value,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM verification_log"
            ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()
