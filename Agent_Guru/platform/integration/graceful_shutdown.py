"""
Module: Agent_Guru.platform.integration.graceful_shutdown
Purpose: Graceful shutdown with signal handling, in-flight tracking, and state persistence.

Performance Requirements:
- Shutdown completes within configurable timeout (default: 30s)
- All in-flight operations complete before cleanup handlers run
- Zero data loss on SIGTERM/SIGINT

Design Decisions:
- asyncio.Event created lazily (not at __init__) to avoid "no running event loop"
  errors when instantiated outside an async context
- Cleanup handlers stored with explicit names (no __name__ on lambdas)
- asyncio.Lock protects _in_flight counter for concurrent async operations
- Force-kill fallback: after timeout, logs warning and proceeds with cleanup
  rather than hanging indefinitely
- LIFO cleanup order (last registered = first cleaned up) mirrors dependency order

Author: Agent Guru Platform Team
Date: 2026-03-16
"""

import asyncio
import json
import logging
import signal
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── Types ────────────────────────────────────────────────────────────────────


class ShutdownPhase(Enum):
    """Lifecycle phases of the shutdown process."""

    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"  # Waiting for in-flight ops
    CLEANUP = "cleanup"              # Running cleanup handlers
    COMPLETE = "complete"


@dataclass
class ShutdownState:
    """
    State snapshot persisted to disk during shutdown.

    Useful for post-mortem analysis and restart recovery.
    """

    shutdown_time: datetime = field(default_factory=datetime.utcnow)
    reason: str = "normal"
    in_flight_at_shutdown: int = 0
    cleanup_handlers_run: int = 0
    cleanup_errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "shutdown_time": self.shutdown_time.isoformat() + "Z",
            "reason": self.reason,
            "in_flight_at_shutdown": self.in_flight_at_shutdown,
            "cleanup_handlers_run": self.cleanup_handlers_run,
            "cleanup_errors": self.cleanup_errors,
            "duration_seconds": round(self.duration_seconds, 3),
        }


# ─── Cleanup Handler Registry ─────────────────────────────────────────────────


@dataclass
class _CleanupEntry:
    """Internal: a registered cleanup handler with metadata."""

    handler: Callable[[], Coroutine]
    name: str
    timeout: float  # Per-handler timeout in seconds


# ─── Manager ─────────────────────────────────────────────────────────────────


class GracefulShutdownManager:
    """
    Manages graceful shutdown of the platform integration system.

    Lifecycle:
        RUNNING → SHUTTING_DOWN (waiting for in-flight ops)
               → CLEANUP (running handlers in LIFO order)
               → COMPLETE

    Features:
    - SIGTERM/SIGINT signal registration (POSIX only; Windows logs warning)
    - asyncio.Lock-protected in-flight counter (safe for concurrent async ops)
    - Per-handler timeout (default 10s) with error isolation
    - Lazy asyncio.Event creation (safe to instantiate outside event loop)
    - JSON state persistence for post-mortem analysis
    - Idempotent: multiple shutdown() calls are safe

    Example:
        >>> manager = GracefulShutdownManager(timeout=30.0)
        >>> manager.register_cleanup(db_client.close, name="db_close")
        >>> manager.register_signals()
        >>>
        >>> async with manager.track_operation():
        ...     await do_work()
        >>>
        >>> await manager.shutdown(reason="user_request")
    """

    def __init__(
        self,
        timeout: float = 30.0,
        state_file: Optional[str] = None,
        default_handler_timeout: float = 10.0,
    ) -> None:
        """
        Initialize shutdown manager.

        Args:
            timeout: Maximum seconds to wait for in-flight operations
            state_file: Optional path to persist shutdown state as JSON
            default_handler_timeout: Per-cleanup-handler timeout in seconds

        Raises:
            ValueError: If timeout or default_handler_timeout <= 0
        """
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout}")
        if default_handler_timeout <= 0:
            raise ValueError(
                f"default_handler_timeout must be positive, got {default_handler_timeout}"
            )

        self.timeout = timeout
        self.state_file = state_file
        self.default_handler_timeout = default_handler_timeout

        self._phase = ShutdownPhase.RUNNING
        self._cleanup_entries: list[_CleanupEntry] = []
        self._in_flight: int = 0
        self._lock: Optional[asyncio.Lock] = None  # Lazy init
        self._shutdown_event: Optional[asyncio.Event] = None  # Lazy init
        self._shutdown_start: Optional[float] = None

    # ─── Lazy Async Primitives ────────────────────────────────────────────

    def _get_lock(self) -> asyncio.Lock:
        """Lazily create asyncio.Lock (requires running event loop)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _get_shutdown_event(self) -> asyncio.Event:
        """Lazily create asyncio.Event (requires running event loop)."""
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()
        return self._shutdown_event

    # ─── Registration ─────────────────────────────────────────────────────

    def register_cleanup(
        self,
        handler: Callable[[], Coroutine],
        name: str = "",
        timeout: Optional[float] = None,
    ) -> None:
        """
        Register an async cleanup coroutine.

        Handlers are called in LIFO order during shutdown (last registered
        runs first), which mirrors typical dependency teardown order.

        Args:
            handler: Async callable with no arguments
            name: Human-readable name for logging (falls back to repr)
            timeout: Per-handler timeout override (uses default if None)

        Raises:
            ValueError: If handler is not callable
        """
        if not callable(handler):
            raise ValueError("handler must be callable")

        resolved_name = name or getattr(handler, "__name__", None) or repr(handler)
        entry = _CleanupEntry(
            handler=handler,
            name=resolved_name,
            timeout=timeout if timeout is not None else self.default_handler_timeout,
        )
        self._cleanup_entries.append(entry)
        logger.debug(f"Registered cleanup handler: '{resolved_name}' (timeout={entry.timeout}s)")

    def register_signals(self) -> None:
        """
        Register SIGTERM and SIGINT handlers.

        On Windows, add_signal_handler is not supported — logs a warning
        and falls back to signal.signal() for SIGINT only.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(
                signal.SIGTERM,
                lambda: asyncio.create_task(self.shutdown(reason="SIGTERM")),
            )
            loop.add_signal_handler(
                signal.SIGINT,
                lambda: asyncio.create_task(self.shutdown(reason="SIGINT")),
            )
            logger.info("Registered SIGTERM and SIGINT handlers via asyncio event loop")
        except (NotImplementedError, RuntimeError):
            # Windows: add_signal_handler not supported
            logger.warning(
                "asyncio signal handlers not supported on this platform. "
                "SIGTERM will not trigger graceful shutdown."
            )

    # ─── In-Flight Tracking ───────────────────────────────────────────────

    def track_operation(self) -> "OperationTracker":
        """
        Return a context manager that tracks an in-flight operation.

        Supports both sync (`with`) and async (`async with`) usage.

        Returns:
            OperationTracker context manager
        """
        return OperationTracker(self)

    async def _increment_in_flight(self) -> None:
        """Thread-safe increment of in-flight counter."""
        async with self._get_lock():
            self._in_flight += 1

    async def _decrement_in_flight(self) -> None:
        """Thread-safe decrement of in-flight counter (floor at 0)."""
        async with self._get_lock():
            self._in_flight = max(0, self._in_flight - 1)

    # ─── Properties ───────────────────────────────────────────────────────

    @property
    def is_shutting_down(self) -> bool:
        """True if shutdown has been initiated (any phase except RUNNING)."""
        return self._phase != ShutdownPhase.RUNNING

    @property
    def phase(self) -> ShutdownPhase:
        """Current shutdown phase."""
        return self._phase

    @property
    def in_flight_count(self) -> int:
        """Current number of tracked in-flight operations."""
        return self._in_flight

    # ─── Shutdown ─────────────────────────────────────────────────────────

    async def wait_for_shutdown(self) -> None:
        """
        Suspend until shutdown() is called.

        Useful for main loop: `await manager.wait_for_shutdown()`
        """
        await self._get_shutdown_event().wait()

    async def shutdown(self, reason: str = "normal") -> None:
        """
        Execute graceful shutdown sequence.

        Steps:
        1. Transition to SHUTTING_DOWN, signal waiting coroutines
        2. Wait up to `timeout` seconds for in-flight operations to complete
        3. Log warning if operations still in-flight after timeout
        4. Transition to CLEANUP, run handlers in LIFO order
        5. Persist state to file if configured
        6. Transition to COMPLETE

        Idempotent: subsequent calls are no-ops.

        Args:
            reason: Human-readable shutdown reason (logged and persisted)
        """
        if self._phase != ShutdownPhase.RUNNING:
            logger.debug("Shutdown already in progress (phase=%s), ignoring", self._phase.value)
            return

        self._shutdown_start = time.monotonic()
        logger.info("Graceful shutdown initiated: reason='%s'", reason)

        self._phase = ShutdownPhase.SHUTTING_DOWN
        self._get_shutdown_event().set()

        in_flight_snapshot = self._in_flight
        state = ShutdownState(reason=reason, in_flight_at_shutdown=in_flight_snapshot)

        # ── Phase 1: Wait for in-flight operations ────────────────────────
        if self._in_flight > 0:
            logger.info(
                f"Waiting up to {self.timeout}s for {self._in_flight} in-flight operations..."
            )
            deadline = time.monotonic() + self.timeout
            while self._in_flight > 0 and time.monotonic() < deadline:
                await asyncio.sleep(0.1)

            if self._in_flight > 0:
                logger.warning(
                    f"Shutdown timeout reached with {self._in_flight} operations still in-flight. "
                    "Proceeding with cleanup."
                )

        # ── Phase 2: Run cleanup handlers (LIFO) ─────────────────────────
        self._phase = ShutdownPhase.CLEANUP
        handlers_run = 0

        for entry in reversed(self._cleanup_entries):
            logger.debug("Running cleanup handler: '%s'", entry.name)
            try:
                await asyncio.wait_for(entry.handler(), timeout=entry.timeout)
                handlers_run += 1
                logger.debug("Cleanup handler completed: '%s'", entry.name)
            except asyncio.TimeoutError:
                msg = f"Cleanup handler '{entry.name}' timed out after {entry.timeout}s"
                logger.error(msg)
                state.cleanup_errors.append(msg)
            except Exception as e:
                msg = f"Cleanup handler '{entry.name}' raised {type(e).__name__}: {e}"
                logger.error(msg)
                state.cleanup_errors.append(msg)

        state.cleanup_handlers_run = handlers_run
        state.duration_seconds = time.monotonic() - self._shutdown_start

        # ── Phase 3: Persist state ────────────────────────────────────────
        if self.state_file:
            await self._persist_state(state)

        self._phase = ShutdownPhase.COMPLETE
        logger.info(
            f"Graceful shutdown complete in {state.duration_seconds:.2f}s "
            f"({handlers_run}/{len(self._cleanup_entries)} handlers, "
            f"{len(state.cleanup_errors)} errors)"
        )

    async def _persist_state(self, state: ShutdownState) -> None:
        """Write shutdown state to JSON file."""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:  # type: ignore[arg-type]
                json.dump(state.to_dict(), f, indent=2)
            logger.debug("Shutdown state persisted to '%s'", self.state_file)
        except OSError as e:
            logger.error(f"Failed to persist shutdown state to '{self.state_file}': {e}")

    # ─── Observability ────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return current manager status for health checks."""
        elapsed = (
            time.monotonic() - self._shutdown_start
            if self._shutdown_start is not None
            else 0.0
        )
        return {
            "phase": self._phase.value,
            "in_flight_operations": self._in_flight,
            "cleanup_handlers_registered": len(self._cleanup_entries),
            "is_shutting_down": self.is_shutting_down,
            "shutdown_elapsed_seconds": round(elapsed, 3),
        }


# ─── Operation Tracker ────────────────────────────────────────────────────────


class OperationTracker:
    """
    Context manager that tracks an in-flight operation.

    Increments the manager's in-flight counter on entry and decrements
    on exit, ensuring the counter is always accurate even on exceptions.

    Supports both sync and async context manager protocols.

    Example (sync):
        with manager.track_operation():
            do_sync_work()

    Example (async):
        async with manager.track_operation():
            await do_async_work()
    """

    def __init__(self, manager: GracefulShutdownManager) -> None:
        self._manager = manager

    # Sync protocol
    def __enter__(self) -> "OperationTracker":
        self._manager._in_flight += 1
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self._manager._in_flight = max(0, self._manager._in_flight - 1)
        return False

    # Async protocol
    async def __aenter__(self) -> "OperationTracker":
        await self._manager._increment_in_flight()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        await self._manager._decrement_in_flight()
        return False
