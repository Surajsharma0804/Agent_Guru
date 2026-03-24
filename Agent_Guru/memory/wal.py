"""Write-Ahead Log (WAL) for crash recovery.

Provides:
- WAL for all mutations: log before applying (Requirement 17.1)
- Log replay on startup to restore consistent state (Requirement 17.2)
- Retry logic with exponential backoff for transient failures (Requirement 17.3)
- Circuit breaker for external dependencies (Requirement 17.3)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

_BACKOFF_BASE = 0.1  # seconds
_MAX_RETRIES = 5


class WALEntryStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"


@dataclass
class WALEntry:
    entry_id: UUID = field(default_factory=uuid4)
    operation: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: WALEntryStatus = WALEntryStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None


class WriteAheadLog:
    """SQLite-backed WAL that survives restarts."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn: sqlite3.Connection = sqlite3.connect(db_path, check_same_thread=False)  # persistent; closed in close()
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wal (
                    entry_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    timestamp TEXT NOT NULL,
                    error TEXT
                )
                """
            )

    def append(self, operation: str, payload: dict[str, Any]) -> WALEntry:
        """Log a mutation before applying it."""
        entry = WALEntry(operation=operation, payload=payload)
        with self._conn:
            self._conn.execute(
                "INSERT INTO wal (entry_id, operation, payload, status, timestamp, error) VALUES (?,?,?,?,?,?)",
                (
                    str(entry.entry_id),
                    entry.operation,
                    json.dumps(entry.payload, default=str),
                    entry.status.value,
                    entry.timestamp.isoformat(),
                    entry.error,
                ),
            )
        return entry

    def mark_applied(self, entry_id: UUID) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE wal SET status = ? WHERE entry_id = ?",
                (WALEntryStatus.APPLIED.value, str(entry_id)),
            )

    def mark_failed(self, entry_id: UUID, error: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE wal SET status = ?, error = ? WHERE entry_id = ?",
                (WALEntryStatus.FAILED.value, error, str(entry_id)),
            )

    def get_pending(self) -> list[WALEntry]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT entry_id, operation, payload, status, timestamp, error FROM wal WHERE status = ? ORDER BY timestamp",
                (WALEntryStatus.PENDING.value,),
            ).fetchall()
        return [
            WALEntry(
                entry_id=UUID(r[0]),
                operation=r[1],
                payload=json.loads(r[2]),
                status=WALEntryStatus(r[3]),
                timestamp=datetime.fromisoformat(r[4]),
                error=r[5],
            )
            for r in rows
        ]

    def count_by_status(self, status: WALEntryStatus) -> int:
        with self._conn:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM wal WHERE status = ?", (status.value,)
            ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()


def retry_with_backoff(
    fn: Callable[[], Any],
    max_retries: int = _MAX_RETRIES,
    base_delay: float = _BACKOFF_BASE,
) -> Any:
    """Execute fn with exponential backoff on exception. Raises on final failure."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            delay = base_delay * (2 ** attempt)
            logger.warning("Attempt %d failed (%s); retrying in %.2fs", attempt + 1, exc, delay)
            if attempt < max_retries - 1:
                time.sleep(delay)
    raise RuntimeError(f"All {max_retries} retries failed") from last_exc


class CircuitBreaker:
    """Simple circuit breaker: CLOSED → OPEN after threshold failures, auto-resets after timeout."""

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 30.0) -> None:
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._failure_count = 0
        self._open_since: float | None = None

    @property
    def is_open(self) -> bool:
        if self._open_since is None:
            return False
        if time.monotonic() - self._open_since >= self._reset_timeout:
            # Auto-reset
            self._failure_count = 0
            self._open_since = None
            return False
        return True

    def call(self, fn: Callable[[], Any]) -> Any:
        if self.is_open:
            raise RuntimeError("Circuit breaker is OPEN — call rejected")
        try:
            result = fn()
            self._failure_count = 0  # Reset on success
            return result
        except Exception:
            self._failure_count += 1
            if self._failure_count >= self._threshold:
                self._open_since = time.monotonic()
                logger.error("Circuit breaker OPENED after %d failures", self._failure_count)
            raise

    def reset(self) -> None:
        self._failure_count = 0
        self._open_since = None
