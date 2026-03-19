"""
Module: Agent_Guru.platform.audit_logger
Purpose: Audit logging for all OS-level operations

Writes JSONL (newline-delimited JSON) entries to .kiro/logs/os_audit.jsonl
with automatic log rotation at 100MB.

Performance:
    - Time Complexity: O(1) per log entry
    - Space Complexity: O(1) (streaming writes, no buffering)
    - Latency: <1ms per entry (async-safe, thread-safe)

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default log path
_DEFAULT_LOG_PATH = Path(".kiro") / "logs" / "os_audit.jsonl"

# Rotation threshold: 100 MB
_MAX_LOG_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

# Maximum number of rotated files to keep
_MAX_ROTATED_FILES = 5


@dataclass
class AuditEntry:
    """A single audit log entry.

    Attributes:
        timestamp: ISO 8601 UTC timestamp
        component: Component that performed the operation (e.g. 'WindowsController')
        operation: Operation name (e.g. 'launch_app')
        success: Whether the operation succeeded
        parameters: Operation parameters (sanitized, no secrets)
        result: Operation result summary
        error: Error message if operation failed
        user: OS username
        platform: Platform identifier (win32, darwin, linux)
        latency_ms: Operation latency in milliseconds
    """

    timestamp: str
    component: str
    operation: str
    success: bool
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    user: Optional[str] = None
    platform: Optional[str] = None
    latency_ms: float = 0.0

    def to_jsonl(self) -> str:
        """Serialize to a single JSON line (no trailing newline)."""
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


class AuditLogger:
    """
    Thread-safe audit logger for OS operations.

    Writes JSONL entries to a configurable log file with automatic
    rotation when the file exceeds 100 MB.

    Example:
        >>> audit = AuditLogger()
        >>> audit.log(
        ...     component="WindowsController",
        ...     operation="launch_app",
        ...     success=True,
        ...     parameters={"app": "notepad"},
        ...     latency_ms=45.2,
        ... )

    Thread Safety:
        All public methods are thread-safe via an internal lock.
    """

    def __init__(
        self,
        log_path: str | Path = _DEFAULT_LOG_PATH,
        max_size_bytes: int = _MAX_LOG_SIZE_BYTES,
        max_rotated_files: int = _MAX_ROTATED_FILES,
    ) -> None:
        """
        Initialize the audit logger.

        Args:
            log_path: Path to the JSONL log file
            max_size_bytes: Maximum file size before rotation (default 100 MB)
            max_rotated_files: Number of rotated files to keep (default 5)
        """
        self._log_path = Path(log_path)
        self._max_size = max_size_bytes
        self._max_rotated = max_rotated_files
        self._lock = threading.Lock()
        self._platform = _get_platform()
        self._user = _get_username()

        # Ensure log directory exists
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"AuditLogger initialized: {self._log_path}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(
        self,
        component: str,
        operation: str,
        success: bool,
        parameters: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
        latency_ms: float = 0.0,
    ) -> None:
        """
        Write an audit log entry.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            component: Component name (e.g. 'WindowsController')
            operation: Operation name (e.g. 'launch_app')
            success: Whether the operation succeeded
            parameters: Operation parameters (will be sanitized)
            result: Human-readable result summary
            error: Error message if failed
            latency_ms: Operation latency in milliseconds
        """
        entry = AuditEntry(
            timestamp=_utc_now(),
            component=component,
            operation=operation,
            success=success,
            parameters=_sanitize(parameters or {}),
            result=result,
            error=error,
            user=self._user,
            platform=self._platform,
            latency_ms=latency_ms,
        )

        with self._lock:
            self._maybe_rotate()
            self._write(entry)

    def log_result(
        self,
        component: str,
        operation: str,
        result: Any,
        parameters: Optional[Dict[str, Any]] = None,
        latency_ms: float = 0.0,
    ) -> None:
        """
        Convenience method: log from a result object that has .success and .error.

        Args:
            component: Component name
            operation: Operation name
            result: Object with .success (bool) and optional .error (str)
            parameters: Operation parameters
            latency_ms: Operation latency
        """
        success = getattr(result, "success", False)
        error = getattr(result, "error", None)
        message = getattr(result, "message", None)
        self.log(
            component=component,
            operation=operation,
            success=success,
            parameters=parameters,
            result=message,
            error=error,
            latency_ms=latency_ms,
        )

    def get_log_path(self) -> Path:
        """Return the current log file path."""
        return self._log_path

    def get_log_size_bytes(self) -> int:
        """Return current log file size in bytes."""
        try:
            return self._log_path.stat().st_size
        except FileNotFoundError:
            return 0

    def read_recent(self, n: int = 100) -> list[AuditEntry]:
        """
        Read the most recent n log entries.

        Args:
            n: Number of entries to return (most recent first)

        Returns:
            List of AuditEntry objects
        """
        entries: list[AuditEntry] = []
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines[-n:]):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(AuditEntry(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
        except FileNotFoundError:
            pass
        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, entry: AuditEntry) -> None:
        """Write a single entry to the log file (must hold lock)."""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(entry.to_jsonl() + "\n")
        except Exception as e:
            logger.error(f"AuditLogger write failed: {e}")

    def _maybe_rotate(self) -> None:
        """Rotate log file if it exceeds max size (must hold lock)."""
        try:
            if not self._log_path.exists():
                return
            size = self._log_path.stat().st_size
            if size < self._max_size:
                return

            # Rotate: rename existing files
            for i in range(self._max_rotated - 1, 0, -1):
                old = self._log_path.with_suffix(f".{i}.jsonl")
                new = self._log_path.with_suffix(f".{i + 1}.jsonl")
                if old.exists():
                    old.rename(new)

            # Rename current → .1.jsonl
            rotated = self._log_path.with_suffix(".1.jsonl")
            self._log_path.rename(rotated)

            # Remove oldest if over limit
            oldest = self._log_path.with_suffix(f".{self._max_rotated + 1}.jsonl")
            if oldest.exists():
                oldest.unlink()

            logger.info(
                f"AuditLogger rotated: {self._log_path} → {rotated} "
                f"(was {size / 1024 / 1024:.1f} MB)"
            )
        except Exception as e:
            logger.error(f"AuditLogger rotation failed: {e}")


# ---------------------------------------------------------------------------
# Module-level singleton for convenience
# ---------------------------------------------------------------------------

_default_logger: Optional[AuditLogger] = None
_default_logger_lock = threading.Lock()


def get_audit_logger(log_path: str | Path = _DEFAULT_LOG_PATH) -> AuditLogger:
    """
    Get or create the module-level singleton AuditLogger.

    Args:
        log_path: Log file path (only used on first call)

    Returns:
        Shared AuditLogger instance
    """
    global _default_logger
    with _default_logger_lock:
        if _default_logger is None:
            _default_logger = AuditLogger(log_path=log_path)
        return _default_logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _get_platform() -> str:
    """Return platform identifier."""
    import sys
    return sys.platform


def _get_username() -> str:
    """Return current OS username."""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "key", "credential", "auth", "authorization", "bearer",
})


def _sanitize(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove sensitive keys from parameters dict.

    Args:
        params: Raw parameters

    Returns:
        Sanitized copy with sensitive values replaced by '***'
    """
    sanitized: Dict[str, Any] = {}
    for k, v in params.items():
        if k.lower() in _SENSITIVE_KEYS:
            sanitized[k] = "***"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize(v)
        else:
            sanitized[k] = v
    return sanitized
