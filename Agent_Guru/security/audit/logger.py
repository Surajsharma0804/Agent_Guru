"""Immutable audit logging with cryptographic signatures.

Each log entry is signed with an Ed25519 key to ensure tamper-evidence.
Entries are stored in SQLite and signatures are verified on query.

Performance target: <50ms per log_event call.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from Agent_Guru.security.crypto.errors import AuditLogError

# Sensitive keys that must be scrubbed from log details
_SENSITIVE_KEYS = frozenset(
    {
        "private_key",
        "secret",
        "password",
        "passphrase",
        "key_material",
        "token",
        "api_key",
        "credential",
    }
)


class EventType(str, Enum):
    """Security event types."""

    KEY_GENERATED = "key_generated"
    KEY_ROTATED = "key_rotated"
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    ZK_PROOF_GENERATED = "zk_proof_generated"
    ZK_PROOF_VERIFIED = "zk_proof_verified"
    TRUST_RELATIONSHIP_CREATED = "trust_relationship_created"
    TRUST_RELATIONSHIP_REVOKED = "trust_relationship_revoked"
    POLICY_VIOLATION = "policy_violation"
    POLICY_ALLOWED = "policy_allowed"


@dataclass
class AuditLogEntry:
    """Immutable audit log entry."""

    entry_id: str
    timestamp: datetime
    event_type: EventType
    actor_id: Optional[str]
    target_id: Optional[str]
    outcome: str  # "success", "failure", "denied"
    details: dict[str, Any]
    signature: bytes  # Ed25519 signature of entry content
    tampered: bool = False


@dataclass
class LogQuery:
    """Query parameters for audit logs."""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    event_types: Optional[list[EventType]] = None
    actor_id: Optional[str] = None
    target_id: Optional[str] = None
    outcome: Optional[str] = None


class AuditLogger:
    """Immutable audit logging with cryptographic signatures.

    Each entry is signed with an Ed25519 key. Signatures are verified
    on query to detect tampering.

    Args:
        storage_path: SQLite path or ":memory:".
        signing_key: Optional Ed25519 private key bytes for signing.
                     If None, a new key is generated.
    """

    def __init__(
        self,
        storage_path: str = ":memory:",
        signing_key: Optional[bytes] = None,
    ) -> None:
        self._conn = sqlite3.connect(storage_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

        # Set up signing key
        if signing_key is not None:
            self._private_key = Ed25519PrivateKey.from_private_bytes(signing_key)
        else:
            self._private_key = Ed25519PrivateKey.generate()

        self._public_key = self._private_key.public_key()
        self._public_key_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_event(
        self,
        event_type: EventType,
        actor_id: Optional[str],
        target_id: Optional[str],
        outcome: str,
        details: dict[str, Any],
    ) -> AuditLogEntry:
        """Log security event with cryptographic signature.

        Performance: <50ms

        Args:
            event_type: Type of security event.
            actor_id: Identity performing action.
            target_id: Identity affected by action.
            outcome: Result of action ("success", "failure", "denied").
            details: Additional event details (will be sanitized).

        Returns:
            Signed AuditLogEntry.

        Raises:
            AuditLogError: If logging fails.
        """
        try:
            entry_id = str(uuid.uuid4())
            timestamp = datetime.now(tz=timezone.utc)
            sanitized_details = self._sanitize_details(details)

            # Build signable content
            content = self._build_signable_content(
                entry_id, timestamp, event_type, actor_id, target_id, outcome, sanitized_details
            )
            signature = self._private_key.sign(content)

            entry = AuditLogEntry(
                entry_id=entry_id,
                timestamp=timestamp,
                event_type=event_type,
                actor_id=actor_id,
                target_id=target_id,
                outcome=outcome,
                details=sanitized_details,
                signature=signature,
            )

            self._persist_entry(entry)
            return entry

        except Exception as exc:
            raise AuditLogError(f"Failed to log event: type={type(exc).__name__}") from exc

    def query_logs(self, query: LogQuery) -> list[AuditLogEntry]:
        """Query audit logs with filters.

        Verifies signatures and marks tampered entries.

        Args:
            query: Query parameters.

        Returns:
            List of matching log entries.
        """
        rows = self._fetch_rows(query)
        entries = []
        for row in rows:
            entry = self._row_to_entry(row)
            # Verify signature
            if not self.verify_log_integrity(entry):
                entry.tampered = True
            entries.append(entry)
        return entries

    def export_logs(self, query: LogQuery, format: str = "json") -> str:
        """Export audit logs in structured format.

        Args:
            query: Query parameters.
            format: Export format ("json" or "csv").

        Returns:
            Formatted log data.
        """
        entries = self.query_logs(query)

        if format == "json":
            return self._export_json(entries)
        elif format == "csv":
            return self._export_csv(entries)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def verify_log_integrity(self, entry: AuditLogEntry) -> bool:
        """Verify cryptographic signature of log entry.

        Returns:
            True if signature is valid.
        """
        try:
            content = self._build_signable_content(
                entry.entry_id,
                entry.timestamp,
                entry.event_type,
                entry.actor_id,
                entry.target_id,
                entry.outcome,
                entry.details,
            )
            self._public_key.verify(entry.signature, content)
            return True
        except Exception as e:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    entry_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT,
                    target_id TEXT,
                    outcome TEXT NOT NULL,
                    details TEXT NOT NULL,
                    signature BLOB NOT NULL
                )
                """
            )

    def _persist_entry(self, entry: AuditLogEntry) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO audit_logs
                    (entry_id, timestamp, event_type, actor_id, target_id, outcome, details, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.timestamp.isoformat(),
                    entry.event_type.value,
                    entry.actor_id,
                    entry.target_id,
                    entry.outcome,
                    json.dumps(entry.details),
                    entry.signature,
                ),
            )

    def _fetch_rows(self, query: LogQuery) -> list:
        conditions = []
        params: list = []

        if query.start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(query.start_time.isoformat())

        if query.end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(query.end_time.isoformat())

        if query.event_types is not None:
            placeholders = ",".join("?" * len(query.event_types))
            conditions.append(f"event_type IN ({placeholders})")
            params.extend(et.value for et in query.event_types)

        if query.actor_id is not None:
            conditions.append("actor_id = ?")
            params.append(query.actor_id)

        if query.target_id is not None:
            conditions.append("target_id = ?")
            params.append(query.target_id)

        if query.outcome is not None:
            conditions.append("outcome = ?")
            params.append(query.outcome)

        sql = "SELECT * FROM audit_logs"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY timestamp ASC"

        return self._conn.execute(sql, params).fetchall()

    def _row_to_entry(self, row: sqlite3.Row) -> AuditLogEntry:
        return AuditLogEntry(
            entry_id=row["entry_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=EventType(row["event_type"]),
            actor_id=row["actor_id"],
            target_id=row["target_id"],
            outcome=row["outcome"],
            details=json.loads(row["details"]),
            signature=bytes(row["signature"]),
        )

    @staticmethod
    def _build_signable_content(
        entry_id: str,
        timestamp: datetime,
        event_type: EventType,
        actor_id: Optional[str],
        target_id: Optional[str],
        outcome: str,
        details: dict[str, Any],
    ) -> bytes:
        """Build deterministic bytes to sign."""
        data = {
            "entry_id": entry_id,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type.value if isinstance(event_type, EventType) else event_type,
            "actor_id": actor_id,
            "target_id": target_id,
            "outcome": outcome,
            "details": details,
        }
        return json.dumps(data, sort_keys=True).encode("utf-8")

    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Remove secrets and sensitive data from log details."""
        sanitized = {}
        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in _SENSITIVE_KEYS):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            else:
                sanitized[key] = value
        return sanitized

    def _export_json(self, entries: list[AuditLogEntry]) -> str:
        data = []
        for entry in entries:
            data.append(
                {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "event_type": entry.event_type.value,
                    "actor_id": entry.actor_id,
                    "target_id": entry.target_id,
                    "outcome": entry.outcome,
                    "details": entry.details,
                    "signature": entry.signature.hex(),
                    "signature_valid": not entry.tampered,
                }
            )
        return json.dumps(data, indent=2)

    def _export_csv(self, entries: list[AuditLogEntry]) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "entry_id",
                "timestamp",
                "event_type",
                "actor_id",
                "target_id",
                "outcome",
                "details",
                "signature_valid",
            ],
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "event_type": entry.event_type.value,
                    "actor_id": entry.actor_id or "",
                    "target_id": entry.target_id or "",
                    "outcome": entry.outcome,
                    "details": json.dumps(entry.details),
                    "signature_valid": not entry.tampered,
                }
            )
        return output.getvalue()
