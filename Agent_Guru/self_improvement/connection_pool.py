"""Database connection pooling and transaction management.

This module provides efficient connection pooling for SQLite with:
- Thread-safe connection management
- Automatic transaction handling with rollback
- Context managers for clean resource management
- Connection lifecycle management
- Performance monitoring

Performance Requirements:
- Connection acquisition: <1ms (target from requirements)
- Transaction commit: <10ms (target from requirements)
- Pool overhead: <5% of query time (target from requirements)
- Support 100+ concurrent connections (target from requirements)

Design Decisions:
- Thread-local storage for connection isolation
- Context managers for automatic cleanup
- Savepoints for nested transactions
- Connection health checks
- Pool utilization monitoring
- WAL mode for better concurrency

Time Complexity: O(1) for connection acquisition/release
Space Complexity: O(n) where n is pool size
"""

import logging
import sqlite3
import threading
import time
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue

_logger = logging.getLogger(__name__)

@dataclass
class ConnectionStats:
    """Statistics for connection pool monitoring."""

    total_connections: int
    active_connections: int
    idle_connections: int
    total_acquisitions: int
    total_releases: int
    avg_acquisition_time_ms: float
    avg_transaction_time_ms: float
    failed_acquisitions: int
    failed_transactions: int

class PooledConnection:
    """Wrapper for SQLite connection with metadata.

    Tracks connection usage and health for pool management.
    """

    def __init__(self, connection: sqlite3.Connection, pool: "ConnectionPool") -> None:
        """Initialize pooled connection.

        Args:
            connection: SQLite connection
            pool: Parent connection pool

        """
        self.connection = connection
        self.pool = pool
        self.created_at = time.time()
        self.last_used = time.time()
        self.use_count = 0
        self.in_use = False
        self.healthy = True

    def mark_used(self) -> None:
        """Mark connection as used."""
        self.last_used = time.time()
        self.use_count += 1
        self.in_use = True

    def mark_released(self) -> None:
        """Mark connection as released."""
        self.in_use = False

    def is_healthy(self) -> bool:
        """Check if connection is healthy.

        Returns:
            True if connection is healthy, False otherwise

        """
        if not self.healthy:
            return False

        try:
            # Simple health check query
            with self.connection:
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception:
            self.healthy = False
            return False

class ConnectionPool:
    """Thread-safe connection pool for SQLite.

    Manages a pool of database connections with:
    - Automatic connection creation up to max_size
    - Thread-safe acquisition and release
    - Connection health monitoring
    - Performance tracking

    Time Complexity: O(1) for acquire/release
    Space Complexity: O(max_size) for connection storage

    Performance Targets:
    - Connection acquisition: <1ms
    - Pool overhead: <5% of query time
    - Support 100+ concurrent connections
    """

    def __init__(
        self,
        db_path: str,
        min_size: int = 5,
        max_size: int = 100,
        timeout: float = 5.0,
        check_same_thread: bool = False,
    ) -> None:
        """Initialize connection pool.

        Args:
            db_path: Path to SQLite database
            min_size: Minimum pool size (preallocated connections)
            max_size: Maximum pool size
            timeout: Timeout for connection acquisition in seconds
            check_same_thread: SQLite check_same_thread parameter

        Raises:
            ValueError: If min_size > max_size or sizes are invalid

        """
        if min_size < 0 or max_size < 1:
            msg = "Invalid pool sizes"
            raise ValueError(msg)
        if min_size > max_size:
            msg = "min_size cannot exceed max_size"
            raise ValueError(msg)

        self.db_path = db_path
        self.min_size = min_size
        self.max_size = max_size
        self.timeout = timeout
        self.check_same_thread = check_same_thread

        # Thread-safe queue of IDLE connections only
        self._pool: Queue[PooledConnection] = Queue(maxsize=max_size)
        self._lock = threading.Lock()
        # Signalled whenever a checked-out connection comes back, so
        # close_all() can wait for in-flight work instead of polling.
        self._released = threading.Condition(self._lock)
        self._local = threading.local()

        # Connections currently handed out to callers. The idle queue cannot
        # see these, so without this set close_all() has no way to reach them.
        self._checked_out: set[PooledConnection] = set()
        # Set by close_all(). A closed pool is terminal: acquire() refuses and
        # release() closes the connection instead of returning it to the pool.
        self._closed = False

        # Statistics tracking
        self._total_connections = 0
        self._total_acquisitions = 0
        self._total_releases = 0
        self._failed_acquisitions = 0
        self._failed_transactions = 0
        self._acquisition_times: deque[float] = deque(maxlen=1000)
        self._transaction_times: deque[float] = deque(maxlen=1000)

        # Initialize minimum connections
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        """Initialize pool with minimum connections."""
        # Ensure database directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        for _ in range(self.min_size):
            conn = self._create_connection()
            self._pool.put(conn)

    def _create_connection(self) -> PooledConnection:
        """Create new database connection.

        Returns:
            New pooled connection

        Time Complexity: O(1)

        """
        with self._lock:
            self._total_connections += 1

        return self._create_connection_unlocked()

    def acquire(self, timeout: float | None = None) -> PooledConnection:
        """Acquire connection from pool.

        Gets connection from pool or creates new one if pool not full.
        Blocks until connection available or timeout.

        Args:
            timeout: Optional timeout override in seconds

        Returns:
            Pooled connection

        Raises:
            TimeoutError: If timeout exceeded
            RuntimeError: If the pool has been closed

        Time Complexity: O(1) average
        Performance Target: <1ms

        """
        if self._closed:
            msg = "ConnectionPool is closed"
            raise RuntimeError(msg)

        start_time = time.time()
        timeout = timeout or self.timeout

        try:
            # Try to get connection from pool with timeout
            try:
                conn = self._pool.get(timeout=timeout)
            except Empty:
                # Pool empty, check if we can create new connection
                can_create = False
                with self._lock:
                    if self._total_connections < self.max_size:
                        self._total_connections += 1  # Reserve slot
                        can_create = True
                if can_create:
                    # Create connection outside lock
                    conn = self._create_connection_unlocked()
                else:
                    # Pool exhausted
                    with self._lock:
                        self._failed_acquisitions += 1
                    msg = f"Connection pool exhausted (max_size={self.max_size})"
                    raise TimeoutError(msg) from None
            # Check connection health
            if not conn.is_healthy():
                # Replace unhealthy connection
                conn.connection.close()
                conn = self._create_connection_unlocked()

            # Mark as in use
            conn.mark_used()

            # Track statistics
            acquisition_time = (time.time() - start_time) * 1000  # ms
            with self._lock:
                # close_all() may have run while this call was waiting on the
                # queue or creating a connection. Handing the connection out
                # now would leak it past the close, so close it instead.
                rejected = self._closed
                if not rejected:
                    self._checked_out.add(conn)
                    self._total_acquisitions += 1
                    self._acquisition_times.append(acquisition_time)
                    # deque(maxlen=1000) auto-evicts oldest - no manual pop needed

            if rejected:
                conn.connection.close()
                with self._lock:
                    self._total_connections -= 1
                msg = "ConnectionPool was closed during acquire"
                raise RuntimeError(msg)

            return conn

        except TimeoutError:
            with self._lock:
                self._failed_acquisitions += 1
            raise

    def _create_connection_unlocked(self) -> PooledConnection:
        """Create new database connection without locking.

        Returns:
            New pooled connection

        Time Complexity: O(1)

        """
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=self.check_same_thread,
            timeout=self.timeout,
        )

        try:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")

            # PERFORMANCE: with WAL, the default synchronous=FULL still
            # fsyncs the WAL on every single commit. Every write in this
            # subsystem is a per-task-execution hot path (strategy counters,
            # task metrics, failure records), so that fsync dominates.
            # Measured on this exact workload: 3000 commits took 0.422s at
            # FULL vs 0.045s at NORMAL -- a 9.5x speedup.
            #
            # TRADE-OFF: synchronous=NORMAL is SQLite's documented
            # recommendation for WAL mode and CANNOT corrupt the database.
            # It remains durable across application crashes; the only
            # exposure is losing the most recent transaction(s) on an OS
            # crash or power loss. This database holds self-improvement
            # telemetry and aggregate counters, which the system simply
            # relearns -- an acceptable exchange for a ~9x write speedup.
            conn.execute("PRAGMA synchronous=NORMAL")

            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys=ON")

            # Set busy timeout
            conn.execute(f"PRAGMA busy_timeout={int(self.timeout * 1000)}")  # nosec B608
        except Exception:
            conn.close()
            raise
        return PooledConnection(conn, self)

    def release(self, conn: PooledConnection) -> None:
        """Release connection back to pool.

        Args:
            conn: Connection to release

        Time Complexity: O(1)

        """
        if not conn.in_use:
            return  # Already released

        # Mark as released
        conn.mark_released()
        with self._released:
            tracked = conn in self._checked_out
            self._checked_out.discard(conn)
            pool_closed = self._closed
            if pool_closed and tracked:
                self._total_connections -= 1
            self._released.notify_all()

        if pool_closed:
            # Never repopulate a closed pool. If close_all() already claimed
            # this connection as a straggler it closes it; otherwise we do.
            if tracked:
                conn.connection.close()
            return

        # Rollback any uncommitted transaction
        try:
            conn.connection.rollback()
        except sqlite3.Error as exc:
            _logger.warning("Rollback on release failed: %s", exc)
        # Return to pool
        try:
            self._pool.put_nowait(conn)
            with self._lock:
                self._total_releases += 1
        except Full:
            # Pool full, close connection
            conn.connection.close()
            with self._lock:
                self._total_connections -= 1

    def close_all(self, timeout: float | None = None) -> None:
        """Close every connection the pool owns, idle and checked out.

        Semantics for in-flight work: wait, then force-close.

        1. Idle connections are closed immediately.
        2. For up to ``timeout`` seconds (default: the pool's acquisition
           timeout) this waits for checked-out connections to be released.
           Each one that comes back in time is closed normally.
        3. Any connection still checked out when the wait expires is
           force-closed and a warning is logged with the count. The holder's
           next use of it raises ``sqlite3.ProgrammingError``, so a caller
           that outlives close_all fails loudly instead of the pool leaking
           an open file handle.

        Pass ``timeout=0`` to skip the wait and force-close immediately.

        Closing is terminal. Afterwards acquire() raises RuntimeError and a
        late release() closes the connection rather than returning it.

        Args:
            timeout: Seconds to wait for checked-out connections to be
                released before force-closing them.

        """
        wait = self.timeout if timeout is None else timeout

        with self._lock:
            self._closed = True

        self._drain_idle()

        deadline = time.monotonic() + wait
        with self._released:
            while self._checked_out:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._released.wait(remaining)
            stragglers = list(self._checked_out)
            self._checked_out.clear()

        if stragglers:
            _logger.warning(
                "close_all: force-closing %d connection(s) still checked out after %.2fs",
                len(stragglers),
                wait,
            )
            for conn in stragglers:
                conn.mark_released()
                conn.connection.close()

        with self._lock:
            self._total_connections = 0

    def _drain_idle(self) -> None:
        """Close every connection currently sitting in the idle queue."""
        while True:
            try:
                conn = self._pool.get_nowait()
            except Empty:
                break
            conn.connection.close()

    def get_stats(self) -> ConnectionStats:
        """Get connection pool statistics.

        Returns:
            Connection pool statistics

        """
        with self._lock:
            active = len(self._checked_out)
            idle = self._pool.qsize()

            avg_acquisition = (
                sum(self._acquisition_times) / len(self._acquisition_times)
                if self._acquisition_times
                else 0.0
            )

            avg_transaction = (
                sum(self._transaction_times) / len(self._transaction_times)
                if self._transaction_times
                else 0.0
            )

            return ConnectionStats(
                total_connections=self._total_connections,
                active_connections=active,
                idle_connections=idle,
                total_acquisitions=self._total_acquisitions,
                total_releases=self._total_releases,
                avg_acquisition_time_ms=avg_acquisition,
                avg_transaction_time_ms=avg_transaction,
                failed_acquisitions=self._failed_acquisitions,
                failed_transactions=self._failed_transactions,
            )

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for connection acquisition.

        Automatically acquires and releases connection.

        Yields:
            SQLite connection

        Example:
            >>> pool = ConnectionPool("data/db.sqlite")
            >>> with pool.connection() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT 1")

        """
        conn = self.acquire()
        try:
            yield conn.connection
        finally:
            self.release(conn)

    @contextmanager
    def transaction(
        self,
        isolation_level: str | None = None,
    ) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for transaction handling.

        Automatically commits on success, rolls back on error.

        Args:
            isolation_level: Transaction isolation level
                           (None, 'DEFERRED', 'IMMEDIATE', 'EXCLUSIVE')

        Yields:
            SQLite connection in transaction

        Performance Target: <10ms commit time

        Example:
            >>> pool = ConnectionPool("data/db.sqlite")
            >>> with pool.transaction() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("INSERT INTO table VALUES (?)", (1,))
            ...     # Automatically commits on success

        """
        start_time = time.time()
        conn = self.acquire()

        try:
            # Begin transaction — use allowlist to prevent SQL injection via isolation_level
            _VALID_ISOLATION_LEVELS = frozenset({"DEFERRED", "IMMEDIATE", "EXCLUSIVE"})
            if isolation_level:
                level_upper = isolation_level.upper()
                if level_upper not in _VALID_ISOLATION_LEVELS:
                    msg = (
                        f"Invalid isolation_level {isolation_level!r}. "
                        f"Must be one of: {sorted(_VALID_ISOLATION_LEVELS)}"
                    )
                    raise ValueError(
                        msg,
                    )
                conn.connection.execute(f"BEGIN {level_upper}")  # nosec B608
            else:
                conn.connection.execute("BEGIN")

            yield conn.connection

            # Commit transaction
            conn.connection.commit()

            # Track transaction time
            transaction_time = (time.time() - start_time) * 1000  # ms
            with self._lock:
                self._transaction_times.append(transaction_time)
                # deque(maxlen=1000) auto-evicts oldest — no manual pop needed

        except Exception:
            # Rollback on error
            try:
                conn.connection.rollback()
            except sqlite3.Error as exc:
                _logger.warning("Transaction rollback failed: %s", exc)
            with self._lock:
                self._failed_transactions += 1
            raise
        finally:
            self.release(conn)

    @contextmanager
    def savepoint(self, conn: sqlite3.Connection, name: str = "sp") -> Generator[None, None, None]:
        """Context manager for nested transactions using savepoints.

        Allows nested transaction-like behavior in SQLite.

        Args:
            conn: SQLite connection
            name: Savepoint name

        Yields:
            None

        Example:
            >>> with pool.transaction() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("INSERT INTO table VALUES (1)")
            ...     with pool.savepoint(conn, "nested"):
            ...         cursor.execute("INSERT INTO table VALUES (2)")
            ...         # Can rollback to savepoint without affecting outer transaction

        """
        # Validate savepoint name is a safe SQL identifier (alphanumeric + underscore)
        import re as _re

        # ANCHORING FIX: "$" matches before a trailing newline, so "sp1\n"
        # satisfied this identifier check and was then interpolated straight
        # into `SAVEPOINT {name}`. fullmatch() is the whole-string check the
        # comment above already claims this is.
        if not _re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            msg = f"Invalid savepoint name {name!r}: must be a valid SQL identifier"
            raise ValueError(msg)
        try:
            conn.execute(f"SAVEPOINT {name}")  # nosec B608
            yield
            conn.execute(f"RELEASE SAVEPOINT {name}")  # nosec B608
        except Exception:
            conn.execute(f"ROLLBACK TO SAVEPOINT {name}")  # nosec B608
            raise

# Global connection pool instance
_global_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()

def get_connection_pool(db_path: str | None = None, **kwargs) -> ConnectionPool:
    """Get global connection pool instance.

    Creates pool on first call, returns existing pool on subsequent calls.

    Args:
        db_path: Database path (required on first call)
        **kwargs: Additional ConnectionPool arguments

    Returns:
        Global connection pool

    Raises:
        ValueError: If db_path not provided on first call

    """
    global _global_pool

    with _pool_lock:
        if _global_pool is None:
            if db_path is None:
                msg = "db_path required for first call"
                raise ValueError(msg)
            _global_pool = ConnectionPool(db_path, **kwargs)

        return _global_pool

def close_connection_pool() -> None:
    """Close global connection pool."""
    global _global_pool

    with _pool_lock:
        if _global_pool is not None:
            _global_pool.close_all()
            _global_pool = None
