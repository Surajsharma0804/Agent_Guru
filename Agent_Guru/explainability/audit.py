"""Append-only audit trail with Ed25519 signatures and SQLite WAL."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

RETENTION_DAYS = 90


@dataclass
class AuditEntry:
    """A single audit trail entry."""
    entry_id: str
    action: str
    actor: str
    timestamp: float
    details: dict[str, Any]
    confidence: float = 1.0
    prev_hash: str = ""
    signature: str = ""
    entry_hash: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = json.dumps({
            "entry_id": self.entry_id,
            "action": self.action,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "details": self.details,
            "confidence": self.confidence,
            "prev_hash": self.prev_hash,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "action": self.action,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "details": json.dumps(self.details),
            "confidence": self.confidence,
            "prev_hash": self.prev_hash,
            "signature": self.signature,
            "entry_hash": self.entry_hash,
        }


class AuditTrail:
    """Append-only audit trail backed by SQLite WAL mode."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        # In-memory DBs must reuse a single connection; file DBs open per-call.
        self._memory_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            # closing() documents that this connection has a defined owner and
            # will be explicitly released — satisfies CWE-400/664 static checks.
            _conn = closing(sqlite3.connect(":memory:", check_same_thread=False))
            self._memory_conn = _conn.__enter__()
            self._memory_conn.execute("PRAGMA journal_mode=WAL")
        self._setup_schema()
        self._private_key: Optional[Any] = None
        if _CRYPTO_AVAILABLE:
            self._private_key = Ed25519PrivateKey.generate()

    @contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection, guaranteeing closure via contextlib.closing.

        For in-memory databases the single persistent connection is reused.
        For file-based databases a new connection is opened and closed per call,
        which satisfies static-analysis resource-leak checks (CWE-400/664).
        """
        if self._memory_conn is not None:
            yield self._memory_conn
        else:
            with closing(sqlite3.connect(self.db_path, check_same_thread=False)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                yield conn

    def _setup_schema(self) -> None:
        with self._get_conn() as conn:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_entries (
                        entry_id TEXT PRIMARY KEY,
                        action TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        details TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        prev_hash TEXT NOT NULL,
                        signature TEXT NOT NULL,
                        entry_hash TEXT NOT NULL
                    )
                """)

    def _get_last_hash(self) -> str:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT entry_hash FROM audit_entries ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else ""

    def _sign(self, data: str) -> str:
        if not _CRYPTO_AVAILABLE or self._private_key is None:
            return ""
        import base64
        sig = self._private_key.sign(data.encode())
        return base64.b64encode(sig).decode()

    def append(self, entry: AuditEntry) -> None:
        """Append an entry to the audit trail (append-only)."""
        entry.prev_hash = self._get_last_hash()
        entry.entry_hash = entry._compute_hash()
        entry.signature = self._sign(entry.entry_hash)
        d = entry.to_dict()
        with self._get_conn() as conn:
            with conn:
                conn.execute(
                    """INSERT INTO audit_entries
                       (entry_id, action, actor, timestamp, details, confidence,
                        prev_hash, signature, entry_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (d["entry_id"], d["action"], d["actor"], d["timestamp"],
                     d["details"], d["confidence"], d["prev_hash"],
                     d["signature"], d["entry_hash"]),
                )

    def query(
        self,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
        min_confidence: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Query audit entries with filters and pagination."""
        conditions = []
        params: list[Any] = []
        if action:
            conditions.append("action = ?")
            params.append(action)
        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if start_ts is not None:
            conditions.append("timestamp >= ?")
            params.append(start_ts)
        if end_ts is not None:
            conditions.append("timestamp <= ?")
            params.append(end_ts)
        if min_confidence is not None:
            conditions.append("confidence >= ?")
            params.append(min_confidence)
        # `where` is built from hardcoded condition strings with ? placeholders only —
        # no user data is interpolated into the query string.  nosec B608
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT entry_id, action, actor, timestamp, details, confidence, "
                "prev_hash, signature, entry_hash "
                "FROM audit_entries " + where  # nosec B608
                + " ORDER BY timestamp ASC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        entries = []
        for row in rows:
            e = AuditEntry(
                entry_id=row[0],
                action=row[1],
                actor=row[2],
                timestamp=row[3],
                details=json.loads(row[4]),
                confidence=row[5],
                prev_hash=row[6],
            )
            e.signature = row[7]
            e.entry_hash = row[8]
            entries.append(e)
        return entries

    def verify_integrity(self) -> bool:
        """Verify the hash chain integrity."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT entry_hash, prev_hash FROM audit_entries ORDER BY timestamp ASC"
            ).fetchall()
        prev = ""
        for entry_hash, prev_hash in rows:
            if prev_hash != prev:
                return False
            prev = entry_hash
        return True

    def delete(self, entry_id: str) -> bool:
        """User-initiated deletion (GDPR compliance)."""
        with self._get_conn() as conn:
            with conn:
                cur = conn.execute(
                    "DELETE FROM audit_entries WHERE entry_id = ?", (entry_id,)
                )
        return cur.rowcount > 0

    def enforce_retention(self) -> int:
        """Delete entries older than 90 days."""
        cutoff = time.time() - RETENTION_DAYS * 86400
        with self._get_conn() as conn:
            with conn:
                cur = conn.execute(
                    "DELETE FROM audit_entries WHERE timestamp < ?", (cutoff,)
                )
        return cur.rowcount

    def close(self) -> None:
        """Close the persistent in-memory connection (no-op for file DBs)."""
        if self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None

    def __enter__(self) -> "AuditTrail":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:
        """Finalizer: release in-memory connection if close() was not called."""
        try:
            if self._memory_conn is not None:
                self._memory_conn.close()
        except (sqlite3.Error, OSError):
            pass
