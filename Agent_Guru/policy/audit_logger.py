"""
Audit Logger - Immutable audit trail for all policy decisions.

Stores records in SQLite with indexed fields for efficient querying.
Each record includes a context hash for tamper detection.

Performance Characteristics:
    - Write: O(1) per record
    - Query: O(log n) with indexes

Validates: Requirement 6 (Audit Trail)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from Agent_Guru.policy.models import AccessDecision, AuditRecord, PolicyEffect

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    action TEXT NOT NULL,
    effect TEXT NOT NULL CHECK(effect IN ('ALLOW', 'DENY', 'ABSTAIN')),
    applicable_policies TEXT NOT NULL,
    context_hash TEXT NOT NULL,
    evaluation_time_ms REAL NOT NULL,
    decision_reason TEXT,
    record_hash TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_principal ON audit_log(principal_id);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_effect ON audit_log(effect);
"""

# Column added after the initial release, for verify_integrity()'s tamper
# hash. Existing on-disk databases created before this column existed need
# an explicit migration since `CREATE TABLE IF NOT EXISTS` does not alter an
# already-existing table.
_MIGRATE_ADD_RECORD_HASH = (
    "ALTER TABLE audit_log ADD COLUMN record_hash TEXT NOT NULL DEFAULT ''"
)


class AuditLogger:
    """Maintains an immutable audit trail of all policy decisions.

    Validates: Requirements 6.1–6.6
    """

    def __init__(self, db_path: str = ":memory:", retention_days: int = 90) -> None:
        """Initialise the audit logger.

        Args:
            db_path: Path to SQLite database (":memory:" for in-memory).
            retention_days: Days to retain audit records before archival.
        """
        self.db_path = db_path
        self.retention_days = retention_days
        self._persistent_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:", check_same_thread=False)  # persistent; closed when object is GC'd
            self._persistent_conn.row_factory = sqlite3.Row
            self._persistent_conn.executescript(_CREATE_TABLE)
            self._persistent_conn.commit()
        else:
            self._init_db()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_CREATE_TABLE)
            self._migrate_record_hash_column(conn)

    @staticmethod
    def _migrate_record_hash_column(conn: sqlite3.Connection) -> None:
        """Add record_hash to an on-disk audit_log table created before this
        column existed. `CREATE TABLE IF NOT EXISTS` above is a no-op against
        an already-existing table, so a persisted database from before this
        fix needs an explicit ALTER TABLE the first time it's reopened.
        (Not needed for :memory: databases -- those are always created fresh
        with the current schema.)
        """
        columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)").fetchall()}
        if "record_hash" not in columns:
            conn.execute(_MIGRATE_ADD_RECORD_HASH)

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        if self._persistent_conn is not None:
            try:
                yield self._persistent_conn
                self._persistent_conn.commit()
            except Exception as e:
                self._persistent_conn.rollback()
                raise
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def log_decision(
        self,
        principal_id: str,
        resource_id: str,
        resource_type: str,
        action: str,
        decision: AccessDecision,
        context: dict[str, Any],
    ) -> str:
        """Log an access decision.

        Args:
            principal_id: ID of the requesting principal.
            resource_id: ID of the target resource.
            resource_type: Type of the target resource.
            action: Requested action.
            decision: The access decision.
            context: Evaluation context dict for tamper detection.

        Returns:
            Audit record ID.

        Validates: Requirement 6.1
        """
        record_id = str(uuid.uuid4())
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        context_hash = self._hash_context(context)
        policies_json = json.dumps(decision.applicable_policies)
        record_hash = self._compute_record_hash(
            record_id=record_id,
            timestamp=timestamp,
            principal_id=principal_id,
            resource_id=resource_id,
            resource_type=resource_type,
            action=action,
            effect=decision.effect.value,
            applicable_policies=policies_json,
            context_hash=context_hash,
            evaluation_time_ms=decision.evaluation_time_ms,
            decision_reason=decision.reason,
        )

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                    (id, timestamp, principal_id, resource_id, resource_type,
                     action, effect, applicable_policies, context_hash,
                     evaluation_time_ms, decision_reason, record_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    timestamp,
                    principal_id,
                    resource_id,
                    resource_type,
                    action,
                    decision.effect.value,
                    policies_json,
                    context_hash,
                    decision.evaluation_time_ms,
                    decision.reason,
                    record_hash,
                ),
            )

        return record_id

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        principal_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        effect: Optional[str] = None,
        limit: int = 1000,
    ) -> list[AuditRecord]:
        """Query audit logs with optional filters.

        Returns records ordered by timestamp descending.

        Validates: Requirement 6.3
        """
        clauses: list[str] = []
        params: list[Any] = []

        if start_time:
            clauses.append("timestamp >= ?")
            params.append(start_time.isoformat())
        if end_time:
            clauses.append("timestamp <= ?")
            params.append(end_time.isoformat())
        if principal_id:
            clauses.append("principal_id = ?")
            params.append(principal_id)
        if resource_id:
            clauses.append("resource_id = ?")
            params.append(resource_id)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if effect:
            clauses.append("effect = ?")
            params.append(effect)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)

        with self._conn() as conn:
            # where is built from hardcoded condition strings with ? placeholders only
            rows = conn.execute(
                "SELECT * FROM audit_log " + where + " ORDER BY timestamp DESC LIMIT ?",  # nosec B608
                params,
            ).fetchall()

        return [self._row_to_record(row) for row in rows]

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    def verify_integrity(self, record_id: str) -> bool:
        """Verify an audit record has not been tampered with.

        BUG FIX: this used to just check that the stored context_hash was a
        syntactically valid 64-character hex string -- it never recomputed
        or compared anything, so it returned True for a record no matter
        what its fields said, including one whose effect/action/etc. had
        been altered directly in the database (e.g. `UPDATE audit_log SET
        effect='ALLOW' WHERE id=...`). It also hashed the *input* evaluation
        context rather than the persisted row, and the raw context was never
        stored, so there was nothing to recompute against even in principle.
        This was a placebo tamper check: it always passed.

        record_hash now covers every field actually persisted for this
        record (computed once at write time in log_decision() /
        _compute_record_hash()). Verification recomputes that same hash from
        the row's *current* contents and compares -- any modification to any
        column changes the recomputed hash and correctly fails verification.

        Note: records written before this fix (or before the record_hash
        column existed on an on-disk database -- see _migrate_record_hash_
        column) have record_hash='' and will report False here. That is
        intentional, not a false positive: those records were never sealed,
        so their integrity genuinely cannot be vouched for.

        Validates: Requirement 6.4
        """
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT id, timestamp, principal_id, resource_id, resource_type,
                       action, effect, applicable_policies, context_hash,
                       evaluation_time_ms, decision_reason, record_hash
                FROM audit_log WHERE id = ?
                """,
                (record_id,),
            ).fetchone()

        if not row:
            return False

        expected = self._compute_record_hash(
            record_id=row["id"],
            timestamp=row["timestamp"],
            principal_id=row["principal_id"],
            resource_id=row["resource_id"],
            resource_type=row["resource_type"],
            action=row["action"],
            effect=row["effect"],
            applicable_policies=row["applicable_policies"],
            context_hash=row["context_hash"],
            evaluation_time_ms=row["evaluation_time_ms"],
            decision_reason=row["decision_reason"],
        )
        return hmac.compare_digest(expected, row["record_hash"] or "")

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def archive_old_records(self) -> int:
        """Delete records older than the retention period.

        Returns:
            Number of records deleted.

        Validates: Requirements 6.5, 6.6
        """
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM audit_log WHERE timestamp < ?", (cutoff,)
            )
            return cursor.rowcount

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_context(context: dict[str, Any]) -> str:
        """Compute SHA256 hash of context dict."""
        serialized = json.dumps(context, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    def _compute_record_hash(
        *,
        record_id: str,
        timestamp: str,
        principal_id: str,
        resource_id: str,
        resource_type: str,
        action: str,
        effect: str,
        applicable_policies: str,
        context_hash: str,
        evaluation_time_ms: float,
        decision_reason: str | None,
    ) -> str:
        """Compute a tamper-evident hash over every persisted audit field.

        Used both to seal a record at write time (log_decision) and to
        re-derive the expected hash at verification time (verify_integrity).
        Any change to any of these fields after the record was written
        changes this hash, so a mismatch is proof of tampering.
        """
        payload = {
            "id": record_id,
            "timestamp": timestamp,
            "principal_id": principal_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "action": action,
            "effect": effect,
            "applicable_policies": applicable_policies,
            "context_hash": context_hash,
            "evaluation_time_ms": evaluation_time_ms,
            "decision_reason": decision_reason or "",
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AuditRecord:
        return AuditRecord(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            principal_id=row["principal_id"],
            resource_id=row["resource_id"],
            resource_type=row["resource_type"],
            action=row["action"],
            effect=PolicyEffect(row["effect"]),
            applicable_policies=json.loads(row["applicable_policies"]),
            context_hash=row["context_hash"],
            evaluation_time_ms=row["evaluation_time_ms"],
            decision_reason=row["decision_reason"] or "",
        )
