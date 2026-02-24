"""Audit logging for safety decisions."""

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import structlog
from cryptography.fernet import Fernet

from Agent_Guru.reasoning.models.action import ActionSensitivity

logger = structlog.get_logger(__name__)


@dataclass
class AuditLogEntry:
    """Audit log entry for safety decision.

    Attributes:
        entry_id: Unique identifier for this entry
        timestamp: When decision was made
        user_id: User who requested action
        tool_id: Tool that was validated
        parameters: Tool parameters (may be encrypted)
        sensitivity: Classified sensitivity level
        decision: Whether action was allowed
        requires_confirmation: Whether confirmation was required
        reason: Reason for decision
        validation_time: Time taken for validation
        metadata: Additional metadata
    """

    entry_id: int
    timestamp: float
    user_id: str
    tool_id: str
    parameters: dict[str, Any]
    sensitivity: str
    decision: str  # "allowed", "blocked", "confirmed", "denied"
    requires_confirmation: bool
    reason: str
    validation_time: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "tool_id": self.tool_id,
            "parameters": self.parameters,
            "sensitivity": self.sensitivity,
            "decision": self.decision,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
            "validation_time": self.validation_time,
            "metadata": self.metadata,
        }


class AuditLogger:
    """Audit logger for safety decisions.

    Provides append-only audit logging with encryption at rest,
    retention policies, and query capabilities.

    Time Complexity: O(1) for append, O(n) for queries
    Space Complexity: O(n) where n is number of log entries
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        encryption_key: Optional[bytes] = None,
        retention_days: int = 90,
    ) -> None:
        """
        Initialize audit logger.

        Args:
            db_path: Path to SQLite database (None for in-memory)
            encryption_key: Encryption key for sensitive data (None = generate)
            retention_days: Number of days to retain logs (minimum 90)
        """
        self._db_path = db_path or ":memory:"
        self._retention_days = max(retention_days, 90)  # Minimum 90 days
        self._conn: Optional[sqlite3.Connection] = None

        # Initialize encryption
        if encryption_key is None:
            encryption_key = Fernet.generate_key()
        self._encryption_key = encryption_key  # Store for get_encryption_key()
        self._cipher = Fernet(encryption_key)

        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema."""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()

        # Create audit log table (append-only)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                user_id TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                parameters_encrypted BLOB NOT NULL,
                sensitivity TEXT NOT NULL,
                decision TEXT NOT NULL,
                requires_confirmation INTEGER NOT NULL,
                reason TEXT NOT NULL,
                validation_time REAL NOT NULL,
                metadata TEXT
            )
        """)

        # Create indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
            ON audit_log(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user 
            ON audit_log(user_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_tool 
            ON audit_log(tool_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_decision 
            ON audit_log(decision)
        """)

        self._conn.commit()

        logger.info("audit_database_initialized", db_path=self._db_path)

    def log_decision(
        self,
        user_id: str,
        tool_id: str,
        parameters: dict[str, Any],
        sensitivity: ActionSensitivity,
        decision: str,
        requires_confirmation: bool,
        reason: str,
        validation_time: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """
        Log safety decision to audit trail.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            user_id: User who requested action
            tool_id: Tool that was validated
            parameters: Tool parameters
            sensitivity: Classified sensitivity level
            decision: Decision made ("allowed", "blocked", "confirmed", "denied")
            requires_confirmation: Whether confirmation was required
            reason: Reason for decision
            validation_time: Time taken for validation
            metadata: Additional metadata

        Returns:
            Entry ID of logged decision
        """
        timestamp = time.time()

        # Encrypt sensitive parameters
        parameters_json = json.dumps(parameters)
        parameters_encrypted = self._cipher.encrypt(parameters_json.encode())

        # Store in database
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log 
            (timestamp, user_id, tool_id, parameters_encrypted, sensitivity, 
             decision, requires_confirmation, reason, validation_time, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            user_id,
            tool_id,
            parameters_encrypted,
            sensitivity.value,
            decision,
            1 if requires_confirmation else 0,
            reason,
            validation_time,
            json.dumps(metadata) if metadata else None,
        ))
        self._conn.commit()

        entry_id = cursor.lastrowid
        if entry_id is None:
            raise RuntimeError("Failed to get entry ID from database")

        logger.info(
            "audit_decision_logged",
            entry_id=entry_id,
            user_id=user_id,
            tool_id=tool_id,
            decision=decision,
        )

        return entry_id

    def query_logs(
        self,
        user_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        decision: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """
        Query audit logs with filters.

        Time Complexity: O(n) where n is number of matching entries
        Space Complexity: O(n)

        Args:
            user_id: Filter by user ID (None for all)
            tool_id: Filter by tool ID (None for all)
            decision: Filter by decision (None for all)
            start_time: Filter by start timestamp (None for no limit)
            end_time: Filter by end timestamp (None for no limit)
            limit: Maximum number of entries to return

        Returns:
            List of AuditLogEntry objects
        """
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        
        cursor = self._conn.cursor()

        # Build query with filters
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list[str | float] = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        if tool_id:
            query += " AND tool_id = ?"
            params.append(tool_id)

        if decision:
            query += " AND decision = ?"
            params.append(decision)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(str(start_time))

        if end_time:
            query += " AND timestamp <= ?"
            params.append(str(end_time))

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(str(limit))

        cursor.execute(query, params)

        entries = []
        for row in cursor.fetchall():
            # Decrypt parameters
            parameters_encrypted = row["parameters_encrypted"]
            parameters_json = self._cipher.decrypt(parameters_encrypted).decode()
            parameters = json.loads(parameters_json)

            # Parse metadata
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}

            entry = AuditLogEntry(
                entry_id=row["entry_id"],
                timestamp=row["timestamp"],
                user_id=row["user_id"],
                tool_id=row["tool_id"],
                parameters=parameters,
                sensitivity=row["sensitivity"],
                decision=row["decision"],
                requires_confirmation=bool(row["requires_confirmation"]),
                reason=row["reason"],
                validation_time=row["validation_time"],
                metadata=metadata,
            )
            entries.append(entry)

        return entries

    def get_statistics(
        self,
        user_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Get audit log statistics.

        Args:
            user_id: Filter by user ID (None for all)
            start_time: Filter by start timestamp (None for no limit)
            end_time: Filter by end timestamp (None for no limit)

        Returns:
            Dictionary with statistics
        """
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        
        cursor = self._conn.cursor()

        # Build base query
        where_clause = "WHERE 1=1"
        params: list[str | float] = []

        if user_id:
            where_clause += " AND user_id = ?"
            params.append(user_id)

        if start_time:
            where_clause += " AND timestamp >= ?"
            params.append(str(start_time))

        if end_time:
            where_clause += " AND timestamp <= ?"
            params.append(str(end_time))

        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM audit_log {where_clause}", params)
        total_count = cursor.fetchone()[0]

        # Get counts by decision
        cursor.execute(
            f"SELECT decision, COUNT(*) FROM audit_log {where_clause} GROUP BY decision",
            params
        )
        decision_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Get counts by sensitivity
        cursor.execute(
            f"SELECT sensitivity, COUNT(*) FROM audit_log {where_clause} GROUP BY sensitivity",
            params
        )
        sensitivity_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Get average validation time
        cursor.execute(
            f"SELECT AVG(validation_time) FROM audit_log {where_clause}",
            params
        )
        avg_validation_time = cursor.fetchone()[0] or 0.0

        return {
            "total_count": total_count,
            "decision_counts": decision_counts,
            "sensitivity_counts": sensitivity_counts,
            "average_validation_time": avg_validation_time,
        }

    def apply_retention_policy(self) -> int:
        """
        Apply retention policy by deleting old logs.

        Deletes logs older than retention_days.

        Returns:
            Number of entries deleted
        """
        if self._conn is None:
            raise RuntimeError("Database connection not initialized")
        
        cutoff_time = time.time() - (self._retention_days * 24 * 60 * 60)

        cursor = self._conn.cursor()

        # Count entries to delete
        cursor.execute(
            "SELECT COUNT(*) FROM audit_log WHERE timestamp < ?",
            (cutoff_time,)
        )
        result = cursor.fetchone()
        count = int(result[0]) if result else 0

        if count > 0:
            # Delete old entries
            cursor.execute(
                "DELETE FROM audit_log WHERE timestamp < ?",
                (cutoff_time,)
            )
            self._conn.commit()

            logger.info(
                "audit_retention_policy_applied",
                deleted_count=count,
                retention_days=self._retention_days,
            )

        return count

    def export_logs(
        self,
        output_path: str,
        user_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> int:
        """
        Export audit logs to JSON file.

        Args:
            output_path: Path to output file
            user_id: Filter by user ID (None for all)
            start_time: Filter by start timestamp (None for no limit)
            end_time: Filter by end timestamp (None for no limit)

        Returns:
            Number of entries exported
        """
        entries = self.query_logs(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=1000000,  # Large limit for export
        )

        # Convert to dictionaries
        entries_dict = [entry.to_dict() for entry in entries]

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(entries_dict, f, indent=2)

        logger.info(
            "audit_logs_exported",
            output_path=output_path,
            count=len(entries),
        )

        return len(entries)

    def get_encryption_key(self) -> bytes:
        """
        Get encryption key (for backup/restore).

        WARNING: Keep this key secure!

        Returns:
            Encryption key bytes (Fernet key format)
        """
        # Return the original Fernet key, not the internal components
        # We need to extract it from the cipher object
        # Since Fernet doesn't expose the key directly, we'll store it during init
        return self._encryption_key

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("audit_database_closed")

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()
