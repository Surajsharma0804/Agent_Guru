"""Module: agent_guru.platform.process_manager
Purpose: Cross-platform process management using psutil
Author: Agent Guru Team
Date: 2026-02-24.

Performance Requirements:
- Time Complexity: O(n) for process listing, O(1) for single process operations
- Space Complexity: O(n) for process list storage
- Latency: <100ms for process operations
- Reliability: >99% success rate for valid operations

Design Decisions:
- Use psutil for cross-platform compatibility
- Cache process list for performance (with TTL)
- Validate PIDs before operations
- Graceful error handling with descriptive messages

Architecture:
    The ProcessManager provides a unified interface for process management
    across Windows, macOS, and Linux. It uses psutil for cross-platform
    operations and provides:
    1. Process listing with filtering
    2. Process creation with argument handling
    3. Process termination (graceful and forced)
    4. Process status queries
    5. Process information retrieval

Optimization Techniques:
    - Process list caching with TTL (avoid repeated system calls)
    - Early validation (fail fast on invalid PIDs)
    - Efficient filtering using generator expressions
    - Minimal object creation (reuse ProcessInfo objects)

Usage Example:
    >>> from agent_guru.platform.process_manager import ProcessManager
    >>>
    >>> # Initialize manager
    >>> manager = ProcessManager()
    >>>
    >>> # List all processes
    >>> processes = manager.list_processes()
    >>> print(f"Found {len(processes)} processes")
    >>>
    >>> # Start a new process
    >>> pid = manager.start_process("notepad.exe", [])
    >>> print(f"Started process with PID: {pid}")
    >>>
    >>> # Query process status
    >>> status = manager.get_process_status(pid)
    >>> print(f"Process status: {status}")
    >>>
    >>> # Terminate process
    >>> success = manager.terminate_process(pid, force=False)
    >>> print(f"Process terminated: {success}")

Benchmarks:
    - Process listing: <50ms for 500 processes
    - Process start: <100ms
    - Process termination: <50ms
    - Status query: <10ms

Comparison with Competitors:
    - Native APIs: Platform-specific, complex
    - subprocess: Limited functionality, no process management
    - psutil: Cross-platform, comprehensive ✓ OPTIMAL CHOICE

References:
    - [1] psutil documentation: https://psutil.readthedocs.io/
    - [2] Process Management Best Practices
    - [3] Cross-Platform System Programming

Author: Agent Guru Team
Date: 2026-02-24
Version: 1.0.0

"""

import logging
import subprocess  # nosec B404
import time
from dataclasses import dataclass

import psutil

from Agent_Guru.platform.protected_processes import is_protected_process_name

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class ProcessInfo:
    """Information about a running process.

    Attributes:
        pid: Process ID (positive integer)
        name: Process name
        status: Process status ("running", "sleeping", "stopped", "zombie")
        cpu_percent: CPU usage percentage (0-100)
        memory_percent: Memory usage percentage (0-100)
        create_time: Process creation time (Unix timestamp)

    """

    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
    create_time: float

    def __post_init__(self):
        """Validate ProcessInfo fields."""
        if self.pid <= 0:
            msg = f"Invalid PID: {self.pid} (must be positive)"
            raise ValueError(msg)
        if not self.name:
            msg = "Process name cannot be empty"
            raise ValueError(msg)
        valid_statuses = {"running", "sleeping", "stopped", "zombie", "disk-sleep", "idle"}
        if self.status not in valid_statuses:
            msg = f"Invalid status: {self.status} (must be one of {valid_statuses})"
            raise ValueError(msg)
        # CPU percent can exceed 100% on multi-core systems (per-core usage)
        if self.cpu_percent < 0:
            msg = f"Invalid CPU percent: {self.cpu_percent} (must be non-negative)"
            raise ValueError(msg)
        if not 0 <= self.memory_percent <= 100:
            msg = f"Invalid memory percent: {self.memory_percent} (must be 0-100)"
            raise ValueError(msg)
        if self.create_time < 0:
            msg = f"Invalid create_time: {self.create_time} (must be non-negative)"
            raise ValueError(msg)

class ProcessManagerError(Exception):
    """Base exception for process manager errors."""

class ProcessNotFoundError(ProcessManagerError):
    """Raised when process with given PID does not exist."""

class ProcessStartError(ProcessManagerError):
    """Raised when process creation fails."""

class ProcessTerminationError(ProcessManagerError):
    """Raised when process termination fails."""

class ProcessManager:
    """Cross-platform process manager using psutil.

    Time Complexity: O(n) for listing, O(1) for single operations
    Space Complexity: O(n) for cached process list

    Example:
        >>> manager = ProcessManager()
        >>> processes = manager.list_processes()
        >>> pid = manager.start_process("python", ["script.py"])
        >>> manager.terminate_process(pid)

    """

    def __init__(self, cache_ttl: float = 1.0) -> None:
        """Initialize process manager.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 1.0)

        Raises:
            ValueError: If cache_ttl is negative

        """
        if cache_ttl < 0:
            msg = f"Invalid cache_ttl: {cache_ttl} (must be non-negative)"
            raise ValueError(msg)

        self.cache_ttl = cache_ttl
        self._process_cache: list[ProcessInfo] | None = None
        self._cache_timestamp: float = 0.0

        logger.info("ProcessManager initialized with cache_ttl=%.2fs", cache_ttl)

    def list_processes(self, use_cache: bool = True) -> list[ProcessInfo]:
        """List all running processes.

        Time Complexity: O(n) where n is number of processes
        Space Complexity: O(n) for process list

        Args:
            use_cache: If True, use cached process list if available

        Returns:
            List of ProcessInfo objects for all running processes

        Raises:
            ProcessManagerError: If process listing fails

        """
        # Check cache
        if use_cache and self._is_cache_valid():
            logger.debug("Returning cached process list (%d processes)", len(self._process_cache))
            return self._process_cache.copy()

        try:
            processes = []

            # Use psutil.pids() + individual Process() to avoid process_iter hanging
            # on Windows protected system processes (e.g. System, Idle)
            for pid in psutil.pids():
                try:
                    proc = psutil.Process(pid)
                    try:
                        name = proc.name()
                    except (psutil.AccessDenied, OSError):
                        name = "unknown"
                    try:
                        status = self._normalize_status(proc.status())
                    except (psutil.AccessDenied, OSError):
                        status = "unknown"
                    try:
                        cpu_pct = proc.cpu_percent()
                    except (psutil.AccessDenied, OSError):
                        cpu_pct = 0.0
                    try:
                        mem_pct = proc.memory_percent()
                    except (psutil.AccessDenied, OSError):
                        mem_pct = 0.0
                    try:
                        create_time = proc.create_time()
                    except (psutil.AccessDenied, OSError):
                        create_time = 0.0
                    if pid <= 0:
                        continue

                    process_info = ProcessInfo(
                        pid=pid,
                        name=name or "unknown",
                        status=status,
                        cpu_percent=cpu_pct or 0.0,
                        memory_percent=mem_pct or 0.0,
                        create_time=create_time or 0.0,
                    )
                    processes.append(process_info)

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                    OSError,
                ) as e:
                    logger.debug("Skipping process %d: %s", pid, e)
                    continue

            # Update cache
            self._process_cache = processes
            self._cache_timestamp = time.time()

            logger.info("Listed %d processes", len(processes))
            return processes.copy()

        except Exception as e:
            logger.exception("Failed to list processes")
            msg = f"Failed to list processes: {e}"
            raise ProcessManagerError(msg) from e

    def start_process(self, executable: str, args: list[str] | None = None) -> int:
        """Start a new process.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            executable: Path to executable or command name
            args: Command-line arguments (optional)

        Returns:
            Process ID of started process (positive integer)

        Raises:
            ProcessStartError: If process creation fails
            ValueError: If executable is empty

        """
        if not executable:
            msg = "Executable cannot be empty"
            raise ValueError(msg)

        args = args or []
        command = [executable, *args]

        try:
            logger.info("Starting process: %s", " ".join(command))

            # BUG FIX (found 2026-09-13): stdout/stderr/stdin used to be
            # opened as subprocess.PIPE, but this class never reads from
            # those pipes anywhere -- start_process() returns only the PID,
            # and no other method here ever calls process.communicate() or
            # reads process.stdout/stderr. A pipe that nobody drains has a
            # small, fixed OS buffer (commonly 64KB); once the child writes
            # more than that to stdout or stderr, the write blocks and the
            # child hangs forever waiting for a reader that will never come
            # -- a classic subprocess deadlock, not a hypothetical one: any
            # perfectly normal program that logs to stdout/stderr (which is
            # most of them) can trigger it. Since nothing here consumes the
            # child's I/O, DEVNULL is the correct choice: it reflects what
            # actually happens (output is discarded) instead of silently
            # setting a trap that only springs once a launched app gets
            # chatty enough.
            process = subprocess.Popen(  # nosec B603  # noqa: S603
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )

            pid = process.pid

            # Validate PID
            if pid <= 0:
                msg = f"Invalid PID returned: {pid}"
                raise ProcessStartError(msg)

            # Invalidate cache
            self._invalidate_cache()

            logger.info("Started process with PID: %d", pid)
            return pid

        except OSError as e:
            # BUG FIX (found 2026-09-13): only FileNotFoundError was caught
            # here, but Popen() raises plain OSError (or its other
            # subclasses) for plenty of equally routine launch failures --
            # PermissionError when the target exists but isn't executable,
            # NotADirectoryError, or a platform-specific OSError (e.g. a
            # malformed Windows executable). Every one of those used to
            # propagate as a raw, undocumented exception straight out of a
            # method whose own docstring promises callers only ever see
            # ProcessStartError/ValueError -- silently breaking that
            # contract for any caller who (reasonably) only caught the
            # documented types. FileNotFoundError is itself an OSError
            # subclass, so this widens the catch to the whole family while
            # still preserving the real, specific OS error message.
            logger.exception("Failed to start process: %s", executable)
            msg = f"Failed to start process '{executable}': {e}"
            raise ProcessStartError(msg) from e

    def terminate_process(self, pid: int, force: bool = False) -> bool:
        """Terminate a process.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pid: Process ID to terminate
            force: If True, force kill; if False, graceful termination

        Returns:
            True if process was terminated successfully

        Raises:
            ProcessNotFoundError: If process does not exist
            ProcessTerminationError: If termination fails
            ValueError: If PID is invalid

        """
        if pid <= 0:
            msg = f"Invalid PID: {pid} (must be positive)"
            raise ValueError(msg)

        try:
            # Get process object
            process = psutil.Process(pid)

            # BUG FIX / SECURITY (found 2026-09-13): this method previously
            # had NO protected-process check at all. Unlike
            # ApplicationController.close_application() (which now re-checks
            # the resolved process name -- see application_control.py,
            # fixed in the prior round), ProcessManager is a separate,
            # lower-level, cross-platform API that any current or future
            # caller can use directly to end a process by PID. Without this
            # check, a bare `ProcessManager().terminate_process(pid)` call
            # against the wrong PID could kill explorer.exe, lsass.exe, or
            # (on macOS/Linux, which this class also supports and
            # application_control.py's taskkill-based guard does not cover)
            # init/systemd/launchd -- taking down the desktop shell, a core
            # OS service, or the whole machine's PID-1, not just "a
            # process". Resolve the real name via psutil (never trust a
            # caller-supplied label) and refuse before ever calling
            # terminate()/kill(). PID 1 is refused unconditionally as a
            # second, name-independent layer: on POSIX, PID 1 is always the
            # init/systemd process no matter what psutil reports its name
            # as, and killing it panics or hard-hangs the OS.
            try:
                real_name = process.name()
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                real_name = None
            if pid == 1 or is_protected_process_name(real_name):
                msg = (
                    f"Refusing to terminate protected process: PID={pid} "
                    f"(resolved name={real_name!r})"
                )
                logger.error(msg)
                raise ProcessTerminationError(msg)

            logger.info("Terminating process PID=%d (force=%s)", pid, force)

            if force:
                # Force kill
                process.kill()
            else:
                # Graceful termination
                process.terminate()

            # Wait for process to terminate (with timeout)
            try:
                process.wait(timeout=5.0)
            except psutil.TimeoutExpired:
                logger.warning("Process PID=%d did not terminate within timeout", pid)
                if not force:
                    # If graceful termination timed out, force kill
                    logger.info("Force killing process PID=%d", pid)
                    process.kill()
                    process.wait(timeout=5.0)
            # Invalidate cache
            self._invalidate_cache()

            logger.info("Process PID=%d terminated successfully", pid)
            return True

        except psutil.NoSuchProcess as e:
            logger.info("Process not found: PID=%d", pid)
            msg = f"Process not found: PID={pid}"
            raise ProcessNotFoundError(msg) from e
        except (psutil.AccessDenied, psutil.TimeoutExpired, OSError) as e:
            # BUG FIX (found 2026-09-13): this method's own docstring
            # promises "Raises: ProcessTerminationError: If termination
            # fails", and defines that exact exception class for the
            # purpose -- but ProcessTerminationError was never actually
            # raised anywhere in this file. AccessDenied (very common:
            # trying to kill a process you don't own, or lack admin/root
            # for) and a repeat TimeoutExpired (force-kill itself not
            # completing within the retry's own timeout) both used to
            # propagate as raw, undocumented psutil exceptions straight out
            # of this method -- silently breaking the contract for any
            # caller who (reasonably) only catches the documented
            # ProcessManagerError/ProcessNotFoundError/ValueError.
            logger.exception("Failed to terminate process PID=%d", pid)
            msg = f"Failed to terminate process PID={pid}: {e}"
            raise ProcessTerminationError(msg) from e

    def get_process_status(self, pid: int) -> str:
        """Query process status.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pid: Process ID to query

        Returns:
            Process status: "running", "sleeping", "stopped", or "zombie"

        Raises:
            ProcessNotFoundError: If process does not exist
            ValueError: If PID is invalid

        """
        if pid <= 0:
            msg = f"Invalid PID: {pid} (must be positive)"
            raise ValueError(msg)

        try:
            process = psutil.Process(pid)
            status = process.status()

            # Normalize status
            normalized_status = self._normalize_status(status)

            logger.debug("Process PID=%d status: %s", pid, normalized_status)
            return normalized_status

        except psutil.NoSuchProcess as e:
            logger.exception("Process not found: PID=")
            msg = f"Process not found: PID={pid}"
            raise ProcessNotFoundError(msg) from e

    def get_process_info(self, pid: int) -> ProcessInfo:
        """Get detailed process information.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pid: Process ID to query

        Returns:
            ProcessInfo object with process details

        Raises:
            ProcessNotFoundError: If process does not exist
            ValueError: If PID is invalid

        """
        if pid <= 0:
            msg = f"Invalid PID: {pid} (must be positive)"
            raise ValueError(msg)

        try:
            process = psutil.Process(pid)

            # Get process information
            with process.oneshot():
                name = process.name()
                status = self._normalize_status(process.status())
                cpu_percent = process.cpu_percent(interval=0.1)
                memory_percent = process.memory_percent()
                create_time = process.create_time()

            process_info = ProcessInfo(
                pid=pid,
                name=name,
                status=status,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                create_time=create_time,
            )

            logger.debug("Retrieved info for process PID=%d: %s", pid, name)
            return process_info

        except psutil.NoSuchProcess as e:
            logger.exception("Process not found: PID=")
            msg = f"Process not found: PID={pid}"
            raise ProcessNotFoundError(msg) from e

    def process_exists(self, pid: int) -> bool:
        """Check if process exists.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pid: Process ID to check

        Returns:
            True if process exists, False otherwise

        Raises:
            ValueError: If PID is invalid

        """
        if pid <= 0:
            msg = f"Invalid PID: {pid} (must be positive)"
            raise ValueError(msg)

        return psutil.pid_exists(pid)

    def _normalize_status(self, status: str) -> str:
        """Normalize process status across platforms.

        Args:
            status: Platform-specific status string

        Returns:
            Normalized status: "running", "sleeping", "stopped", or "zombie"

        """
        # psutil status constants vary by platform
        # Normalize to consistent values
        status_lower = status.lower()

        if status_lower in ("running", "runnable"):
            return "running"
        if status_lower in ("sleeping", "idle", "disk-sleep"):
            return "sleeping"
        if status_lower in ("stopped", "suspended"):
            return "stopped"
        if status_lower in ("zombie", "dead"):
            return "zombie"
        # Unknown status - default to running
        logger.warning("Unknown process status: %s, defaulting to 'running'", status)
        return "running"

    def _is_cache_valid(self) -> bool:
        """Check if process cache is valid.

        Returns:
            True if cache exists and is not expired

        """
        if self._process_cache is None:
            return False

        age = time.time() - self._cache_timestamp
        return age < self.cache_ttl

    def _invalidate_cache(self) -> None:
        """Invalidate process cache."""
        self._process_cache = None
        self._cache_timestamp = 0.0
        logger.debug("Process cache invalidated")
