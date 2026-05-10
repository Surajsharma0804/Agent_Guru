"""Module: Agent_Guru.platform.linux.integration
Purpose: Linux-specific platform integration using D-Bus and systemd
Author: Agent Guru Team
Date: 2026-02-24.

Performance Requirements:
- Time Complexity: O(1) for D-Bus operations, O(n) for process listing
- Space Complexity: O(1) for single operations, O(n) for process lists
- Latency: <100ms for D-Bus operations, <500ms for service queries

Design Decisions:
- Use dbus-python for D-Bus service management (native Linux IPC)
- Use subprocess for systemd service control (systemctl commands)
- Implement permission validation before all write operations
- Use psutil for cross-platform process management where possible
- Graceful fallback when dbus-python unavailable
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import psutil

# Linux-specific imports (only available on Linux)
try:
    import dbus

    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logging.warning("dbus-python not available - some Linux features will be limited")
logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of command execution."""

    stdout: str
    stderr: str
    return_code: int
    execution_time: float  # seconds


@dataclass
class ProcessInfo:
    """Information about a running process."""

    pid: int
    name: str
    status: str  # "running", "sleeping", "stopped", "zombie"
    cpu_percent: float
    memory_percent: float
    create_time: float  # Unix timestamp


@dataclass
class SystemInfo:
    """System information."""

    hostname: str
    platform: str
    platform_version: str
    architecture: str
    processor: str
    cpu_count_physical: int
    cpu_count_logical: int
    boot_time: float  # Unix timestamp


@dataclass
class ServiceStatus:
    """Linux systemd service status information."""

    name: str
    status: str  # "running", "stopped", "disabled"
    startup_type: str  # "automatic", "manual", "disabled"


class DBusError(Exception):
    """Raised when D-Bus operation fails."""


class LinuxIntegration:
    """Linux-specific platform integration.

    Provides:
    - D-Bus service management
    - systemd service control
    - Process management
    - Permission validation

    Time Complexity: O(1) for most operations, O(n) for process listing
    Space Complexity: O(1) for single operations

    Example:
        >>> integration = LinuxIntegration()
        >>> status = integration.get_systemd_service_status("ssh")
        >>> print(f"SSH service: {status.status}")

    """

    def __init__(self) -> None:
        """Initialize Linux integration."""
        if not DBUS_AVAILABLE:
            logger.warning(
                "dbus-python not available - D-Bus features will be limited. "
                "Install with: pip install dbus-python",
            )

        self._validate_linux_platform()

        # Initialize D-Bus connection if available
        self._system_bus = None
        if DBUS_AVAILABLE:
            try:
                self._system_bus = dbus.SystemBus()
                logger.debug("D-Bus system bus connected")
            except Exception:
                logger.exception("Failed to connect to D-Bus system bus")
    def _validate_linux_platform(self) -> None:
        """Validate that we're running on Linux.

        Raises:
            RuntimeError: If not running on Linux

        """
        import platform

        system_name = platform.system()
        if system_name != "Linux":
            msg = f"LinuxIntegration requires Linux, but running on {system_name}"
            raise RuntimeError(msg)

    # D-Bus Operations

    def query_dbus_service(
        self,
        bus_name: str,
        object_path: str,
        interface: str,
        method: str,
        *args,
    ) -> Any:  # noqa: ANN401
        """Query a D-Bus service.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            bus_name: D-Bus service name (e.g., "org.freedesktop.systemd1")
            object_path: Object path (e.g., "/org/freedesktop/systemd1")
            interface: Interface name (e.g., "org.freedesktop.systemd1.Manager")
            method: Method to call
            *args: Method arguments

        Returns:
            Method result

        Raises:
            DBusError: If D-Bus operation fails
            RuntimeError: If dbus-python not available

        Example:
            >>> result = integration.query_dbus_service(
            ...     "org.freedesktop.systemd1",
            ...     "/org/freedesktop/systemd1",
            ...     "org.freedesktop.systemd1.Manager",
            ...     "ListUnits"
            ... )

        """
        if not DBUS_AVAILABLE:
            msg = "dbus-python required for D-Bus operations. Install with: pip install dbus-python"
            raise RuntimeError(
                msg,
            )

        if self._system_bus is None:
            msg = "D-Bus system bus not connected"
            raise DBusError(msg)

        try:
            # Get D-Bus object
            obj = self._system_bus.get_object(bus_name, object_path)

            # Get interface
            iface = dbus.Interface(obj, interface)

            # Call method
            method_func = getattr(iface, method)
            result = method_func(*args)

            logger.debug("D-Bus call: %s.%s() -> %s", bus_name, method, type(result).__name__)

            return result

        except dbus.exceptions.DBusException as e:
            error_msg = f"D-Bus error calling {bus_name}.{method}: {e}"
            logger.exception(error_msg)
            raise DBusError(error_msg) from e
            error_msg = f"Error calling D-Bus method {method}: {e}"
            logger.exception(error_msg)
            raise DBusError(error_msg) from e
    # systemd Service Management

    def get_systemd_service_status(self, service_name: str) -> ServiceStatus:
        """Get systemd service status.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            service_name: Name of the systemd service (e.g., "ssh", "nginx")

        Returns:
            ServiceStatus with current status and startup type

        Raises:
            RuntimeError: If service not found or systemctl unavailable

        Example:
            >>> status = integration.get_systemd_service_status("ssh")
            >>> print(f"SSH: {status.status}")

        """
        try:
            # Ensure service name has .service suffix
            if not service_name.endswith(".service"):
                service_name = f"{service_name}.service"

            # Query service status using systemctl
            result = subprocess.run(  # noqa: S603
                ["systemctl", "is-active", service_name],  # noqa: S607
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

            # Map systemctl output to our status strings
            status_output = result.stdout.strip()
            if status_output == "active":
                service_status = "running"
            elif status_output in {"inactive", "failed"}:
                service_status = "stopped"
            else:
                service_status = status_output  # unknown, activating, deactivating, etc.

            # Get startup type
            startup_type = self._get_service_startup_type(service_name)

            logger.debug("Service %s: status=%s, startup=%s", service_name, service_status, startup_type)

            return ServiceStatus(
                name=service_name,
                status=service_status,
                startup_type=startup_type,
            )

        except FileNotFoundError as e:
            error_msg = "systemctl not found. Is systemd installed?"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
            error_msg = f"Timeout querying service {service_name}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
            error_msg = f"Error querying service {service_name}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def _get_service_startup_type(self, service_name: str) -> str:
        """Get service startup type from systemctl.

        Args:
            service_name: Name of the service

        Returns:
            Startup type: "automatic", "manual", or "disabled"

        """
        try:
            result = subprocess.run(  # noqa: S603
                ["systemctl", "is-enabled", service_name],  # noqa: S607
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

            enabled_output = result.stdout.strip()

            # Map systemctl output to our startup types
            if enabled_output == "enabled":
                return "automatic"
            if enabled_output == "disabled":
                return "disabled"
            if enabled_output == "static":
                return "manual"
            if enabled_output == "masked":
                return "disabled"
            return "manual"  # Default for unknown states

        except Exception:
            return "unknown"
    def start_systemd_service(self, service_name: str) -> bool:
        """Start a systemd service.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            service_name: Name of the service to start

        Returns:
            True if service was started successfully

        Raises:
            PermissionError: If insufficient permissions (requires root/sudo)
            RuntimeError: If service start fails

        Example:
            >>> integration.start_systemd_service("nginx")

        """
        try:
            # Ensure service name has .service suffix
            if not service_name.endswith(".service"):
                service_name = f"{service_name}.service"

            # Start service using systemctl
            result = subprocess.run(  # noqa: S603
                ["systemctl", "start", service_name],  # noqa: S607
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Check if it's a permission error
                if (
                    "authentication" in result.stderr.lower()
                    or "permission" in result.stderr.lower()
                ):
                    error_msg = (
                        f"Permission denied starting service {service_name}. "
                        f"Root/sudo privileges required."
                    )
                    logger.error(error_msg)
                    raise PermissionError(error_msg)
                error_msg = f"Failed to start service {service_name}: {result.stderr.strip()}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info("Started service: %s", service_name)
            return True

        except subprocess.TimeoutExpired as e:
            error_msg = f"Timeout starting service {service_name}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
            if isinstance(e, PermissionError):
                raise
            error_msg = f"Error starting service {service_name}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def stop_systemd_service(self, service_name: str) -> bool:
        """Stop a systemd service.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            service_name: Name of the service to stop

        Returns:
            True if service was stopped successfully

        Raises:
            PermissionError: If insufficient permissions (requires root/sudo)
            RuntimeError: If service stop fails

        Example:
            >>> integration.stop_systemd_service("nginx")

        """
        try:
            # Ensure service name has .service suffix
            if not service_name.endswith(".service"):
                service_name = f"{service_name}.service"

            # Stop service using systemctl
            result = subprocess.run(  # noqa: S603
                ["systemctl", "stop", service_name],  # noqa: S607
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Check if it's a permission error
                if (
                    "authentication" in result.stderr.lower()
                    or "permission" in result.stderr.lower()
                ):
                    error_msg = (
                        f"Permission denied stopping service {service_name}. "
                        f"Root/sudo privileges required."
                    )
                    logger.error(error_msg)
                    raise PermissionError(error_msg)
                error_msg = f"Failed to stop service {service_name}: {result.stderr.strip()}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info("Stopped service: %s", service_name)
            return True

        except subprocess.TimeoutExpired as e:
            error_msg = f"Timeout stopping service {service_name}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
            if isinstance(e, PermissionError):
                raise
            error_msg = f"Error stopping service {service_name}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def restart_systemd_service(self, service_name: str) -> bool:
        """Restart a systemd service.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            service_name: Name of the service to restart

        Returns:
            True if service was restarted successfully

        Raises:
            PermissionError: If insufficient permissions (requires root/sudo)
            RuntimeError: If service restart fails

        Example:
            >>> integration.restart_systemd_service("nginx")

        """
        try:
            # Ensure service name has .service suffix
            if not service_name.endswith(".service"):
                service_name = f"{service_name}.service"

            # Restart service using systemctl
            result = subprocess.run(  # noqa: S603
                ["systemctl", "restart", service_name],  # noqa: S607
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Check if it's a permission error
                if (
                    "authentication" in result.stderr.lower()
                    or "permission" in result.stderr.lower()
                ):
                    error_msg = (
                        f"Permission denied restarting service {service_name}. "
                        f"Root/sudo privileges required."
                    )
                    logger.error(error_msg)
                    raise PermissionError(error_msg)
                error_msg = f"Failed to restart service {service_name}: {result.stderr.strip()}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            logger.info("Restarted service: %s", service_name)
            return True

        except subprocess.TimeoutExpired as e:
            error_msg = f"Timeout restarting service {service_name}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
            if isinstance(e, PermissionError):
                raise
            error_msg = f"Error restarting service {service_name}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    # Process Management

    def get_process_list(self) -> list[ProcessInfo]:
        """Get list of running processes.

        Time Complexity: O(n) where n is number of processes
        Space Complexity: O(n)

        Returns:
            List of ProcessInfo for all running processes

        Example:
            >>> processes = integration.get_process_list()
            >>> for proc in processes:
            ...     print(f"{proc.name} (PID: {proc.pid})")

        """
        processes = []

        for proc in psutil.process_iter(
            ["pid", "name", "status", "cpu_percent", "memory_percent", "create_time"],
        ):
            try:
                info = proc.info
                processes.append(
                    ProcessInfo(
                        pid=info["pid"],
                        name=info["name"],
                        status=info["status"],
                        cpu_percent=info["cpu_percent"] or 0.0,
                        memory_percent=info["memory_percent"] or 0.0,
                        create_time=info["create_time"],
                    ),
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process terminated or access denied - skip it
                continue
        logger.debug("Retrieved %s processes", len(processes))
        return processes

    def start_process(self, executable: str, args: list[str]) -> int:
        """Start a new process.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            executable: Path to executable
            args: Command-line arguments

        Returns:
            Process ID of started process

        Raises:
            FileNotFoundError: If executable not found
            PermissionError: If insufficient permissions

        Example:
            >>> pid = integration.start_process("/usr/bin/firefox", [])
            >>> print(f"Started Firefox with PID: {pid}")

        """
        try:
            # Build command
            cmd = [executable, *args]

            # Start process
            process = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,  # Linux equivalent of CREATE_NEW_PROCESS_GROUP
            )

            logger.info("Started process: %s (PID: %s)", executable, process.pid)
            return process.pid

        except FileNotFoundError as e:
            error_msg = f"Executable not found: {executable}"
            logger.exception(error_msg)
            raise FileNotFoundError(error_msg) from e
            error_msg = f"Permission denied starting process: {executable}"
            logger.exception(error_msg)
            raise PermissionError(error_msg) from e
            error_msg = f"Error starting process {executable}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def terminate_process(self, pid: int, force: bool = False) -> bool:
        """Terminate a process.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pid: Process ID
            force: If True, force kill (SIGKILL); if False, graceful termination (SIGTERM)

        Returns:
            True if process was terminated

        Raises:
            ProcessLookupError: If process not found
            PermissionError: If insufficient permissions

        Example:
            >>> integration.terminate_process(1234, force=False)

        """
        try:
            process = psutil.Process(pid)

            if force:
                process.kill()  # SIGKILL
                logger.info("Force killed process %s", pid)
            else:
                process.terminate()  # SIGTERM
                logger.info("Terminated process %s", pid)

            return True

        except psutil.NoSuchProcess as e:
            error_msg = f"Process not found: PID {pid}"
            logger.exception(error_msg)
            raise ProcessLookupError(error_msg) from e
            error_msg = (
                f"Permission denied terminating process {pid}. "
                f"Root/sudo privileges may be required."
            )
            logger.exception(error_msg)
            raise PermissionError(error_msg) from e
            error_msg = f"Error terminating process {pid}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def execute_command(self, command: str, args: list[str]) -> CommandResult:
        """Execute a Linux command.

        Time Complexity: O(1) + command execution time
        Space Complexity: O(output_size)

        Args:
            command: Command to execute
            args: Command arguments

        Returns:
            CommandResult with stdout, stderr, and return code

        Example:
            >>> result = integration.execute_command("echo", ["Hello"])
            >>> print(result.stdout)

        """
        try:
            start_time = time.time()

            # Build command
            cmd = [command, *args]

            # Execute command
            result = subprocess.run(  # noqa: S603
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            execution_time = time.time() - start_time

            logger.debug(
                f"Executed command: {command} (return code: {result.returncode}, "
                f"time: {execution_time:.3f}s)",
            )

            return CommandResult(
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                execution_time=execution_time,
            )

        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out: {command}"
            logger.exception(error_msg)
            raise TimeoutError(error_msg) from e
            error_msg = f"Error executing command {command}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def get_system_info(self) -> SystemInfo:
        """Get Linux system information.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            SystemInfo with system details

        Example:
            >>> info = integration.get_system_info()
            >>> print(f"Hostname: {info.hostname}")

        """
        import platform
        import socket

        return SystemInfo(
            hostname=socket.gethostname(),
            platform="Linux",
            platform_version=platform.release(),
            architecture=platform.machine(),
            processor=platform.processor() or "Unknown",
            cpu_count_physical=psutil.cpu_count(logical=False) or 0,
            cpu_count_logical=psutil.cpu_count(logical=True) or 0,
            boot_time=psutil.boot_time(),
        )

    # Permission Validation

    def is_root(self) -> bool:
        """Check if running with root privileges.

        Returns:
            True if running as root

        Example:
            >>> if integration.is_root():
            ...     print("Running as root")

        """
        try:
            import os

            return os.geteuid() == 0
        except Exception:
            return False
    def require_root(self) -> None:
        """Raise error if not running with root privileges.

        Raises:
            PermissionError: If not running as root

        Example:
            >>> integration.require_root()  # Raises if not root

        """
        if not self.is_root():
            msg = "This operation requires root privileges. Run with sudo or as root user."
            raise PermissionError(
                msg,
            )
