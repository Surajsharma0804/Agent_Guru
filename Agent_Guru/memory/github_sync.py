"""GitHub Sync Engine.

Persists memory updates to GitHub asynchronously with:
- README.md-only constraint (Property 44)
- Exponential backoff retry: 100ms, 200ms, 400ms, 800ms, 1600ms (Property 45)
- Persistent SQLite queue that survives restarts (Property 47)
- Batching window of 5 seconds
- Continued local operation when GitHub unavailable

All sync operations are non-blocking — they never delay memory writes.
"""

from __future__ import annotations

import html
import logging
import sqlite3
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from Agent_Guru.memory.models import SyncOperation, SyncStatus
from Agent_Guru.security.path_utils import safe_path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()

# Exponential backoff delays in seconds
_BACKOFF_DELAYS = [0.1, 0.2, 0.4, 0.8, 1.6]
_README_FILENAME = "README.md"
_BATCH_WINDOW_SECONDS = 5.0


class ReadmeOnlyViolationError(ValueError):
    """Raised when a sync operation targets a non-README file."""


class GitHubClientProtocol:
    """Protocol for the GitHub API client (swap for real implementation)."""

    def push(self, file_path: str, content: str, commit_message: str) -> str:
        """Push content to GitHub. Returns commit SHA."""
        raise NotImplementedError

    def is_available(self) -> bool:
        return False


class StubGitHubClient(GitHubClientProtocol):
    """In-memory stub for testing — records all pushes."""

    def __init__(self, fail_times: int = 0) -> None:
        self.pushes: list[dict[str, Any]] = []
        self._fail_times = fail_times
        self._call_count = 0

    def push(self, file_path: str, content: str, commit_message: str) -> str:
        self._call_count += 1
        if self._call_count <= self._fail_times:
            raise ConnectionError(f"Simulated failure #{self._call_count}")
        sha = str(uuid4())[:8]
        self.pushes.append({"file_path": file_path, "content": content, "commit_message": commit_message, "sha": sha})
        return sha

    def is_available(self) -> bool:
        return True


class PersistentSyncQueue:
    """SQLite-backed queue that survives process restarts (Property 47)."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection = sqlite3.connect(db_path, check_same_thread=False)  # persistent; closed in close()
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_queue (
                    operation_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    commit_message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def enqueue(self, op: SyncOperation) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO sync_queue
                (operation_id, file_path, content, commit_message, status, retry_count, last_error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(op.operation_id),
                    op.file_path,
                    op.content,
                    op.commit_message,
                    op.status.value,
                    op.retry_count,
                    op.last_error,
                    op.timestamp.isoformat(),
                ),
            )

    def dequeue_pending(self, limit: int = 50) -> list[SyncOperation]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT * FROM sync_queue WHERE status = 'pending' ORDER BY created_at LIMIT ?",
                (limit,),
            ).fetchall()
        ops = []
        for row in rows:
            ops.append(
                SyncOperation(
                    operation_id=UUID(row[0]),
                    file_path=row[1],
                    content=row[2],
                    commit_message=row[3],
                    status=SyncStatus(row[4]),
                    retry_count=row[5],
                    last_error=row[6],
                    timestamp=datetime.fromisoformat(row[7]),
                )
            )
        return ops

    def update_status(self, operation_id: UUID, status: SyncStatus, error: str | None = None, retry_count: int = 0) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE sync_queue SET status = ?, last_error = ?, retry_count = ? WHERE operation_id = ?",
                (status.value, error, retry_count, str(operation_id)),
            )

    def count_by_status(self, status: SyncStatus) -> int:
        with self._conn:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM sync_queue WHERE status = ?", (status.value,)
            ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()


class GitHubSyncEngine:
    """Async GitHub sync engine with retry, batching, and README-only constraint."""

    def __init__(
        self,
        client: GitHubClientProtocol | None = None,
        db_path: str = ":memory:",
        batch_window_seconds: float = _BATCH_WINDOW_SECONDS,
        max_retries: int = 5,
    ) -> None:
        self._client = client or StubGitHubClient()
        self._queue = PersistentSyncQueue(db_path)
        self._batch_window = batch_window_seconds
        self._max_retries = max_retries
        # In-memory buffer for batching
        self._buffer: deque[SyncOperation] = deque()
        self._last_flush = time.monotonic()

    # ------------------------------------------------------------------
    # README-only constraint (Property 44)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_file_path(file_path: str) -> None:
        """Raise if file_path is not README.md."""
        resolved = safe_path(file_path, BASE_DIR)
        if resolved.name != _README_FILENAME:
            raise ReadmeOnlyViolationError(
                f"Only '{_README_FILENAME}' is allowed; got '{file_path}'"
            )

    # ------------------------------------------------------------------
    # Commit message generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_commit_message(
        component: str,
        entity_count: int = 0,
        preference_count: int = 0,
        experience_count: int = 0,
        personality_count: int = 0,
    ) -> str:
        return (
            f"[Memory Update] {html.escape(str(component))}: learned information\n\n"
            f"- Entity updates: {entity_count}\n"
            f"- Preference updates: {preference_count}\n"
            f"- Experience updates: {experience_count}\n"
            f"- Personality updates: {personality_count}\n\n"
            f"Triggered by: {html.escape(str(component))}"
        )

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------

    def queue_sync(self, op: SyncOperation) -> UUID:
        """Enqueue a sync operation. Never blocks. (Property 44 enforced here)"""
        self.validate_file_path(op.file_path)
        self._queue.enqueue(op)
        logger.debug("Queued sync op %s", op.operation_id)
        return op.operation_id

    # ------------------------------------------------------------------
    # Processing with exponential backoff (Property 45)
    # ------------------------------------------------------------------

    def process_sync_queue(self) -> dict[str, int]:
        """Process all pending operations. Returns stats dict."""
        if not self._client.is_available():
            logger.warning("GitHub unavailable — skipping sync, operations remain queued")
            return {"processed": 0, "succeeded": 0, "failed": 0}

        pending = self._queue.dequeue_pending()
        succeeded = failed = 0

        for op in pending:
            result = self._process_with_retry(op)
            if result:
                succeeded += 1
            else:
                failed += 1

        return {"processed": len(pending), "succeeded": succeeded, "failed": failed}

    def _process_with_retry(self, op: SyncOperation) -> bool:
        """Attempt to push with exponential backoff. Returns True on success."""
        delays = _BACKOFF_DELAYS[: self._max_retries]
        for attempt, delay in enumerate(delays):
            try:
                self._client.push(op.file_path, op.content, op.commit_message)
                self._queue.update_status(op.operation_id, SyncStatus.COMPLETED, retry_count=attempt)
                logger.debug("Sync op %s succeeded on attempt %d", op.operation_id, attempt + 1)
                return True
            except Exception as exc:
                logger.warning("Sync attempt %d failed for %s: %s", attempt + 1, op.operation_id, exc)
                if attempt < len(delays) - 1:
                    time.sleep(delay)
        # All retries exhausted
        self._queue.update_status(
            op.operation_id,
            SyncStatus.FAILED,
            error=f"Failed after {len(delays)} attempts",
            retry_count=len(delays),
        )
        return False

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def pending_count(self) -> int:
        return self._queue.count_by_status(SyncStatus.PENDING)

    def completed_count(self) -> int:
        return self._queue.count_by_status(SyncStatus.COMPLETED)

    def failed_count(self) -> int:
        return self._queue.count_by_status(SyncStatus.FAILED)
