"""Module: Agent_Guru.core.error_handler
Purpose: Comprehensive error handling, retry, and recovery for Agent Guru.

Provides:
- ErrorHandler: Centralized error handling with speech feedback. Automatic
  recovery for critical component failures is implemented directly on this
  class via register_recovery_handler()/_attempt_recovery() (there is no
  separate RecoveryManager class - this docstring previously advertised one
  that was never implemented; corrected in Round 25 to match reality).
- RetryPolicy: Exponential backoff for transient failures
- ErrorLogger: Structured error logging with rotation

Requirements: 20.1, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8

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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

if os.name == "nt":
    _DEFAULT_LOG_PATH = (
        Path(os.environ.get("AGENT_GURU_LOG_DIR", ""))
        if os.environ.get("AGENT_GURU_LOG_DIR")
        else Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        / "agent_guru"
        / "logs"
        / "errors.log"
    )
else:
    _DEFAULT_LOG_PATH = (
        Path(os.environ.get("AGENT_GURU_LOG_DIR", ""))
        if os.environ.get("AGENT_GURU_LOG_DIR")
        else Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        / "agent_guru"
        / "logs"
        / "errors.log"
    )
_MAX_LOG_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
_MAX_ROTATED_FILES = 5  # Keep .log.1 through .log.5

# Retry defaults
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY_S = 0.5
_DEFAULT_MAX_DELAY_S = 30.0
_DEFAULT_BACKOFF_FACTOR = 2.0


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for routing and recovery."""

    MICROPHONE = "microphone"
    STT = "stt"
    INTENT = "intent"
    LLM = "llm"
    TTS = "tts"
    OS_ACTION = "os_action"
    AUDIO_PLAYBACK = "audio_playback"
    NETWORK = "network"
    SECURITY = "security"
    UNKNOWN = "unknown"


@dataclass
class ErrorRecord:
    """A structured error record.

    Attributes:
        timestamp: ISO-format timestamp
        category: Error category
        severity: Error severity
        component: Component that raised the error
        message: Error message
        context: Additional context dict
        recovery_attempted: Whether recovery was attempted
        recovered: Whether recovery succeeded

    """

    timestamp: str
    category: ErrorCategory
    severity: ErrorSeverity
    component: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovered: bool = False

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "category": self.category.value,
            "severity": self.severity.value,
            "component": self.component,
            "message": self.message,
            "context": self.context,
            "recovery_attempted": self.recovery_attempted,
            "recovered": self.recovered,
        }


class RetryPolicy:
    """Exponential backoff retry policy for transient failures.

    Algorithm:
        delay = min(base_delay * backoff_factor^attempt, max_delay)
        With optional jitter to prevent thundering herd.

    Performance:
        - execute(): O(n) where n = max_retries
        - Space: O(1)

    Example:
        >>> policy = RetryPolicy(max_retries=3, base_delay=0.5)
        >>> result = policy.execute(lambda: call_api())

    """

    def __init__(
        self,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_delay: float = _DEFAULT_BASE_DELAY_S,
        max_delay: float = _DEFAULT_MAX_DELAY_S,
        backoff_factor: float = _DEFAULT_BACKOFF_FACTOR,
        retryable_exceptions: tuple | None = None,
    ) -> None:
        """Initialize retry policy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Multiplier for each retry
            retryable_exceptions: Exception types to retry (None = all)

        Raises:
            ValueError: If parameters are invalid

        """
        if max_retries < 0:
            msg = f"max_retries must be >= 0, got {max_retries}"
            raise ValueError(msg)
        if base_delay < 0:
            msg = f"base_delay must be >= 0, got {base_delay}"
            raise ValueError(msg)
        if max_delay < base_delay:
            msg = "max_delay must be >= base_delay"
            raise ValueError(msg)
        if backoff_factor < 1.0:
            msg = f"backoff_factor must be >= 1.0, got {backoff_factor}"
            raise ValueError(msg)

        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor
        self._retryable = retryable_exceptions or (Exception,)

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry on failure.

        Time Complexity: O(max_retries)

        Args:
            func: Callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func on success

        Raises:
            Last exception if all retries exhausted

        """
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return func(*args, **kwargs)
            except self._retryable as e:
                last_exc = e
                if attempt < self._max_retries:
                    delay = min(
                        self._base_delay * (self._backoff_factor**attempt),
                        self._max_delay,
                    )
                    logger.exception(
                        "Attempt %d/%d failed: %s. Retrying in %.2fs",
                        attempt + 1,
                        self._max_retries + 1,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.exception("All %d attempts failed", self._max_retries + 1)

        raise last_exc  # type: ignore

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: Zero-based attempt number

        Returns:
            Delay in seconds

        """
        return min(
            self._base_delay * (self._backoff_factor**attempt),
            self._max_delay,
        )

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def base_delay(self) -> float:
        return self._base_delay

    @property
    def max_delay(self) -> float:
        return self._max_delay

    @property
    def backoff_factor(self) -> float:
        return self._backoff_factor


class ErrorLogger:
    """Structured error logger with file rotation.

    Writes JSONL-format error records to disk.
    Rotates log file when it exceeds max_size_bytes.

    Performance:
        - log(): O(1) amortized
        - Space: O(max_size_bytes) on disk
    """

    def __init__(
        self,
        log_path: Path = _DEFAULT_LOG_PATH,
        max_size_bytes: int = _MAX_LOG_SIZE_BYTES,
    ) -> None:
        self._log_path = log_path
        self._max_size_bytes = max_size_bytes
        self._lock = threading.Lock()
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: ErrorRecord) -> None:
        """Write an error record to the log file.

        Args:
            record: ErrorRecord to log

        """
        with self._lock:
            self._rotate_if_needed()
            try:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record.to_dict()) + "\n")
            except OSError:
                logger.exception("ErrorLogger: could not write to %s", self._log_path)

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size.

        Uses numbered rotation: .log.1 (newest) through .log.N (oldest).
        Previous .log.N is deleted to bound disk usage.
        """
        try:
            if self._log_path.exists() and self._log_path.stat().st_size >= self._max_size_bytes:
                # Shift existing rotated files: .log.4 -> .log.5, .log.3 -> .log.4, etc.
                for i in range(_MAX_ROTATED_FILES, 1, -1):
                    src = self._log_path.with_suffix(f".log.{i - 1}")
                    dst = self._log_path.with_suffix(f".log.{i}")
                    if src.exists():
                        if dst.exists():
                            dst.unlink()
                        src.rename(dst)
                # Current -> .log.1
                rotated = self._log_path.with_suffix(".log.1")
                if rotated.exists():
                    rotated.unlink()
                self._log_path.rename(rotated)
                logger.info("ErrorLogger: rotated %s → %s", self._log_path, rotated)
        except OSError:
            logger.exception("ErrorLogger: rotation failed")

    def get_recent_errors(self, n: int = 100) -> list[ErrorRecord]:
        """Read the n most recent error records.

        Reads only the tail of the file to avoid loading a 100MB log
        into memory. Seeks backward in 64KB chunks to find the last N lines.

        Args:
            n: Number of records to return

        Returns:
            List of ErrorRecord (most recent last)

        """
        if not self._log_path.exists():
            return []

        records = []
        try:
            # Read only the tail of the file (avoid O(filesize) memory)
            chunk_size = 65536  # 64KB - enough for ~100 JSONL records
            with open(self._log_path, "rb") as f:
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                read_size = min(file_size, chunk_size * max(1, n // 50))
                f.seek(max(0, file_size - read_size))
                tail = f.read().decode("utf-8", errors="replace")

            lines = tail.strip().splitlines()
            for line in lines[-n:]:
                try:
                    d = json.loads(line.strip())
                    records.append(
                        ErrorRecord(
                            timestamp=d.get("timestamp", ""),
                            category=ErrorCategory(d.get("category", "unknown")),
                            severity=ErrorSeverity(d.get("severity", "error")),
                            component=d.get("component", ""),
                            message=d.get("message", ""),
                            context=d.get("context", {}),
                            recovery_attempted=d.get("recovery_attempted", False),
                            recovered=d.get("recovered", False),
                        ),
                    )
                except (json.JSONDecodeError, ValueError):
                    continue
        except OSError:
            # Returning a silently-empty error history made a broken
            # persistence path indistinguishable from "no errors have ever
            # occurred". Whatever was parsed before the failure is still
            # returned; the failure itself is now reported.
            logger.warning(
                "Could not read the persisted error log; returning %d partial record(s)",
                len(records),
                exc_info=True,
            )

        return records


class ErrorHandler:
    """Centralized error handler for the voice pipeline.

    Handles:
    - Microphone errors with retry
    - LLM provider fallback (delegates to FailoverRouter)
    - OS action errors reported via speech
    - Audio playback errors
    - Automatic recovery for critical failures

    Example:
        >>> handler = ErrorHandler()
        >>> handler.handle(ErrorCategory.MICROPHONE, "Device disconnected")

    """

    def __init__(
        self,
        error_logger: ErrorLogger | None = None,
        speech_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize error handler.

        Args:
            error_logger: ErrorLogger instance (creates default if None)
            speech_callback: Callback to speak error messages to user

        """
        self._logger = error_logger or ErrorLogger()
        self._speech_callback = speech_callback
        self._recovery_handlers: dict[ErrorCategory, Callable] = {}
        self._error_counts: dict[ErrorCategory, int] = dict.fromkeys(ErrorCategory, 0)
        self._lock = threading.Lock()

    def handle(
        self,
        category: ErrorCategory,
        message: str,
        component: str = "unknown",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: dict[str, Any] | None = None,
        speak_error: bool = True,
    ) -> bool:
        """Handle an error.

        Args:
            category: Error category
            message: Error message
            component: Component that raised the error
            severity: Error severity
            context: Additional context
            speak_error: Whether to speak error to user

        Returns:
            True if error was recovered, False otherwise

        """
        with self._lock:
            self._error_counts[category] += 1

        record = ErrorRecord(
            timestamp=datetime.now(tz=UTC).isoformat(),
            category=category,
            severity=severity,
            component=component,
            message=message,
            context=context or {},
        )

        self._logger.log(record)
        # BUG-013: replaced f-string logger call with %s lazy-format
        logger.error("[%s] %s: %s", category.value, component, message)

        # Attempt recovery
        recovered = self._attempt_recovery(category, record)
        record.recovery_attempted = True
        record.recovered = recovered

        # Speak error to user if callback available
        if speak_error and self._speech_callback:
            user_message = self._get_user_message(category, message)
            try:
                self._speech_callback(user_message)
            except Exception:
                logger.exception("Speech callback failed")

        return recovered

    def register_recovery_handler(self, category: ErrorCategory, handler: Callable) -> None:
        """Register a recovery handler for an error category.

        Args:
            category: Error category
            handler: Callable that attempts recovery, returns True on success

        """
        self._recovery_handlers[category] = handler

    def get_error_count(self, category: ErrorCategory) -> int:
        """Return total error count for a category."""
        return self._error_counts[category]

    def get_total_errors(self) -> int:
        """Return total error count across all categories."""
        return sum(self._error_counts.values())

    def _attempt_recovery(self, category: ErrorCategory, record: ErrorRecord) -> bool:
        """Attempt automatic recovery for an error category."""
        handler = self._recovery_handlers.get(category)
        if handler is None:
            return False
        try:
            return bool(handler(record))
        except Exception:
            # BUG-013: replaced f-string logger call with %s lazy-format
            logger.exception("Recovery handler failed for %s", category.value)
            return False

    @staticmethod
    def _get_user_message(category: ErrorCategory, message: str) -> str:
        """Get a user-friendly error message for speech output."""
        messages = {
            ErrorCategory.MICROPHONE: "I'm having trouble hearing you. Please check your microphone.",
            ErrorCategory.STT: "I couldn't understand that. Could you please repeat?",
            ErrorCategory.INTENT: "I'm not sure what you'd like me to do. Could you rephrase?",
            ErrorCategory.LLM: "I'm having trouble connecting to my AI service. Please try again.",
            ErrorCategory.TTS: "I'm having trouble speaking right now.",
            ErrorCategory.OS_ACTION: "I couldn't complete that action: " + message,
            ErrorCategory.AUDIO_PLAYBACK: "There was an audio playback issue.",
            ErrorCategory.NETWORK: "I'm having network connectivity issues.",
            ErrorCategory.SECURITY: "A security check failed. Please try again.",
            ErrorCategory.UNKNOWN: "Something went wrong. Please try again.",
        }
        return messages.get(category, "An error occurred. Please try again.")
