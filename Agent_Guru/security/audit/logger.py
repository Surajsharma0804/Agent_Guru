"""Immutable audit logging with cryptographic signatures.

Each log entry is signed with an Ed25519 key to ensure tamper-evidence.
Entries are stored in SQLite and signatures are verified on query.

Entries are also chained: each one records the hash of the entry before it,
and that hash is part of what is signed. A signature alone shows an entry
was not edited; it cannot show that one was deleted or reordered, and the
chain can. Entries written before the chain existed keep verifying with the
content they were signed with; the chain starts after them. Deleting the
newest entries is not detectable from the log alone.

Performance target: <50ms per log_event call.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import sqlite3
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from Agent_Guru.security.crypto.errors import AuditLogError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_KEY_DESCRIPTION = "Agent Guru audit signing key"


def signing_key_at(path: Path) -> bytes:
    """The audit log's Ed25519 signing key kept at *path*, created on first use.

    A log kept on disk needs the same key on every start: with a fresh key
    each run, every entry from an earlier run fails verification. On Windows
    the key is encrypted with DPAPI for the current user account, so another
    account, or the file copied to another machine, cannot use it, and no
    password is asked for. Elsewhere the file is readable by its owner only.

    Raises:
        OSError, ValueError or pywintypes.error when an existing key file
        cannot be read or decrypted. It is never replaced silently: a new
        key would make every earlier entry fail verification.

    """
    from Agent_Guru.utils.secure_file import secure_write_bytes

    if path.exists():
        stored = path.read_bytes()
        if sys.platform == "win32":
            import win32crypt  # type: ignore[import-untyped]

            _, stored = win32crypt.CryptUnprotectData(stored, None, None, None, 0)
        Ed25519PrivateKey.from_private_bytes(stored)
        return stored
    key = Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    stored = key
    if sys.platform == "win32":
        import win32crypt  # type: ignore[import-untyped]

        stored = win32crypt.CryptProtectData(key, _KEY_DESCRIPTION, None, None, None, 0)
    secure_write_bytes(path, stored)
    return key

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
    },
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
    #: A call to a tool on an external (MCP) server, allowed or not.
    EXTERNAL_TOOL_CALL = "external_tool_call"


@dataclass
class AuditLogEntry:
    """Immutable audit log entry."""

    entry_id: str
    timestamp: datetime
    event_type: EventType
    actor_id: str | None
    target_id: str | None
    outcome: str  # "success", "failure", "denied"
    details: dict[str, Any]
    signature: bytes  # Ed25519 signature of entry content
    tampered: bool = False
    # Hash of the entry before this one ("" for the first chained entry) and
    # of this entry. None for entries written before the chain existed.
    prev_hash: str | None = None
    entry_hash: str | None = None


@dataclass
class LogQuery:
    """Query parameters for audit logs."""

    start_time: datetime | None = None
    end_time: datetime | None = None
    event_types: list[EventType] | None = None
    actor_id: str | None = None
    target_id: str | None = None
    outcome: str | None = None


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
        signing_key: bytes | None = None,
    ) -> None:
        self._conn = sqlite3.connect(storage_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # check_same_thread=False only disables sqlite3's own cross-thread
        # check, it doesn't make the connection itself safe for concurrent
        # use - this lock serializes every operation against self._conn, the
        # same fix applied to KeyStore and TrustManager in this same round
        # (all three share the identical unprotected-shared-connection
        # pattern found and fixed in memory/github_sync.py last round).
        self._lock = threading.Lock()
        self._init_schema()

        # Set up signing key
        if signing_key is not None:
            self._private_key = Ed25519PrivateKey.from_private_bytes(signing_key)
        elif storage_path != ":memory:":
            # A persistent audit log with no explicit signing_key generates
            # a brand-new random key on every single instantiation. Since
            # verify_log_integrity() recomputes each entry's signable
            # content and checks it against *this instance's* public key,
            # every entry written by a *previous* process (a different,
            # already-discarded random key) will fail verification the
            # moment this process restarts - reported as tampered=True even
            # though nothing was actually tampered with. This doesn't
            # silently corrupt anything, but it makes the audit log's core
            # promise ("tamper-evidence") produce false positives on every
            # restart unless the caller persists and re-supplies the same
            # signing_key bytes (e.g. via KeyStore) across instantiations
            # against the same storage_path - surfacing that here rather
            # than leaving it a silent, confusing surprise.
            logger.warning(
                "AuditLogger(storage_path=%r) created with no signing_key: "
                "a new random Ed25519 key was generated for this process. "
                "Log entries written by a previous process will report "
                "tampered=True on verify_log_integrity()/query_logs() even "
                "though they were not tampered with. Pass the same "
                "signing_key bytes (persisted via KeyStore) across "
                "instantiations against this storage_path for durable "
                "tamper-evidence.",
                storage_path,
            )
            self._private_key = Ed25519PrivateKey.generate()
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
        actor_id: str | None,
        target_id: str | None,
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
            timestamp = datetime.now(tz=UTC)
            sanitized_details = self._sanitize_details(details)

            # Reading the previous hash and inserting must not interleave
            # with another writer, or two entries would claim the same
            # predecessor and the chain would fork.
            with self._lock:
                prev_hash = self._tail_hash()
                content = self._build_signable_content(
                    entry_id,
                    timestamp,
                    event_type,
                    actor_id,
                    target_id,
                    outcome,
                    sanitized_details,
                    prev_hash,
                )
                entry = AuditLogEntry(
                    entry_id=entry_id,
                    timestamp=timestamp,
                    event_type=event_type,
                    actor_id=actor_id,
                    target_id=target_id,
                    outcome=outcome,
                    details=sanitized_details,
                    signature=self._private_key.sign(content),
                    prev_hash=prev_hash,
                    entry_hash=hashlib.sha256(content).hexdigest(),
                )
                self._persist_entry(entry)
            return entry

        except Exception as exc:
            msg = f"Failed to log event: type={type(exc).__name__}"
            raise AuditLogError(msg) from exc

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
        if format == "csv":
            return self._export_csv(entries)
        msg = f"Unsupported format: {format}"
        raise ValueError(msg)

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
                entry.prev_hash,
            )
            self._public_key.verify(entry.signature, content)
            return entry.entry_hash is None or entry.entry_hash == hashlib.sha256(content).hexdigest()
        except Exception:
            return False

    def verify_chain(self) -> tuple[bool, str | None]:
        """Check every entry's signature and its link to the one before.

        Returns:
            (True, None) when the log is intact, else (False, entry_id) for
            the first entry that was edited, or whose predecessor was
            deleted or moved.

        """
        with self._lock:
            rows = self._conn.execute("SELECT * FROM audit_logs ORDER BY rowid").fetchall()
        expected_prev: str | None = None
        for row in rows:
            entry = self._row_to_entry(row)
            if not self.verify_log_integrity(entry):
                return False, entry.entry_id
            if entry.prev_hash is None:
                continue  # written before the chain existed
            if entry.prev_hash != (expected_prev or ""):
                return False, entry.entry_id
            expected_prev = entry.entry_hash
        return True, None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock, self._conn:
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
                """,
            )
            columns = {row[1] for row in self._conn.execute("PRAGMA table_info(audit_logs)")}
            for column in ("prev_hash", "entry_hash"):
                if column not in columns:
                    self._conn.execute(f"ALTER TABLE audit_logs ADD COLUMN {column} TEXT")

    def _tail_hash(self) -> str:
        """The newest chained entry's hash, "" if none; call with self._lock held."""
        row = self._conn.execute(
            "SELECT entry_hash FROM audit_logs WHERE entry_hash IS NOT NULL ORDER BY rowid DESC LIMIT 1",
        ).fetchone()
        return row[0] if row else ""

    def _persist_entry(self, entry: AuditLogEntry) -> None:
        """Insert *entry*; call with self._lock held."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO audit_logs
                    (entry_id, timestamp, event_type, actor_id, target_id, outcome, details, signature,
                     prev_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    entry.prev_hash,
                    entry.entry_hash,
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

        with self._lock:
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
            prev_hash=row["prev_hash"],
            entry_hash=row["entry_hash"],
        )

    @staticmethod
    def _build_signable_content(
        entry_id: str,
        timestamp: datetime,
        event_type: EventType,
        actor_id: str | None,
        target_id: str | None,
        outcome: str,
        details: dict[str, Any],
        prev_hash: str | None = None,
    ) -> bytes:
        """Build deterministic bytes to sign.

        prev_hash is included only for chained entries, so an entry written
        before the chain existed is checked against exactly the bytes it was
        signed with.
        """
        data = {
            "entry_id": entry_id,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type.value if isinstance(event_type, EventType) else event_type,
            "actor_id": actor_id,
            "target_id": target_id,
            "outcome": outcome,
            "details": details,
        }
        if prev_hash is not None:
            data["prev_hash"] = prev_hash
        return json.dumps(data, sort_keys=True).encode("utf-8")

    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Remove secrets and sensitive data from log details."""
        sanitized = {}
        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in _SENSITIVE_KEYS):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = self._sanitize_value(value)
        return sanitized

    def _sanitize_value(self, value: Any) -> Any:
        """Recursively sanitize a value that may itself carry sensitive keys.

        The previous version only recursed into `dict` values directly under
        a details dict - a sensitive key nested one level deeper through a
        `list` (e.g. `details={"items": [{"api_key": "..."}]}`) was never
        inspected at all and got persisted to the audit log, and included in
        export_logs() output, completely unredacted despite `api_key` being
        listed in _SENSITIVE_KEYS. This recurses into lists/tuples too, so
        any dict found at any nesting depth still gets sanitized.
        """
        if isinstance(value, dict):
            return self._sanitize_details(value)
        if isinstance(value, (list, tuple)):
            return [self._sanitize_value(v) for v in value]
        return value

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
                },
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
                },
            )
        return output.getvalue()


def open_owner_audit_log() -> AuditLogger:
    """The owner's audit log on disk (audit.db in the data folder), signed with the key kept beside it.

    Used by the assistant at start and by commands run beside it (such as
    `python -m Agent_Guru mcp call`), so both write to one chained log.
    Raises if the log or its key cannot be opened; the caller decides
    whether to go on without it.
    """
    from Agent_Guru.utils.path_utils import app_data_dir
    from Agent_Guru.utils.secure_file import restrict_file_permissions

    path = app_data_dir("audit.db")
    audit = AuditLogger(str(path), signing_key=signing_key_at(app_data_dir("audit_signing.key")))
    restrict_file_permissions(path)
    return audit
