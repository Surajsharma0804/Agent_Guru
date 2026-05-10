"""Module: Agent_Guru.platform.windows.integration
Purpose: Windows-specific platform integration using pywin32
Author: Agent Guru Team
Date: 2026-02-23.

Performance Requirements:
- Time Complexity: O(1) for registry operations, O(n) for process listing
- Space Complexity: O(1) for single operations, O(n) for process lists
- Latency: <100ms for registry operations, <500ms for service queries

Design Decisions:
- Use pywin32 for native Windows API access
- Use winreg for registry operations (built-in, no external dependency)
- Implement permission validation before all write operations
- Use psutil for cross-platform process management where possible
"""

import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import psutil

# winreg is Windows-only (built-in on Windows, absent on other platforms)
if sys.platform == "win32":
    try:
        import winreg

        WINREG_AVAILABLE = True
    except ImportError:
        WINREG_AVAILABLE = False
        logging.warning("winreg not available")
else:
    WINREG_AVAILABLE = False
    winreg = None  # type: ignore[assignment]

# Windows-specific imports (only available on Windows)
if sys.platform == "win32":
    try:
        import pywintypes
        import win32api
        import win32con
        import win32security
        import win32service
        import win32serviceutil

        PYWIN32_AVAILABLE = True
    except ImportError:
        PYWIN32_AVAILABLE = False
        logging.warning("pywin32 not available - some Windows features will be limited")
else:
    PYWIN32_AVAILABLE = False
    win32service = None  # type: ignore[assignment]
    win32serviceutil = None  # type: ignore[assignment]
    win32api = None  # type: ignore[assignment]
    win32con = None  # type: ignore[assignment]
    win32security = None  # type: ignore[assignment]
    pywintypes = None  # type: ignore[assignment]


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
    """Windows service status information."""

    name: str
    status: str  # "running", "stopped", "disabled"
    startup_type: str  # "automatic", "manual", "disabled"


class RegistryKeyNotFoundError(Exception):
    """Raised when Windows registry key not found."""


class WindowsIntegration:
    r"""Windows-specific platform integration.

    Provides:
    - Registry operations (read, write, delete)
    - Windows service management
    - Process management
    - Permission validation

    Time Complexity: O(1) for most operations, O(n) for process listing
    Space Complexity: O(1) for single operations

    Example:
        >>> integration = WindowsIntegration()
        >>> value = integration.read_registry_key(
        ...     winreg.HKEY_LOCAL_MACHINE,
        ...     r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
        ...     "ProgramFilesDir"
        ... )
        >>> print(f"Program Files: {value}")

    """

    def __init__(self) -> None:
        """Initialize Windows integration."""
        if not PYWIN32_AVAILABLE:
            logger.warning(
                "pywin32 not available - service management features will be limited. "
                "Install with: pip install pywin32",
            )

        self._validate_windows_platform()

    def _validate_windows_platform(self) -> None:
        """Validate that we're running on Windows.

        Raises:
            RuntimeError: If not running on Windows

        """
        import platform

        system_name = platform.system()
        if system_name != "Windows":
            msg = f"WindowsIntegration requires Windows, but running on {system_name}"
            raise RuntimeError(msg)

    # Registry Operations

    def read_registry_key(self, hive: int, key_path: str, value_name: str) -> Any:  # noqa: ANN401
        r"""Read a Windows registry key.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            hive: Registry hive (e.g., winreg.HKEY_LOCAL_MACHINE)
            key_path: Path to registry key
            value_name: Name of value to read

        Returns:
            Registry value (type depends on registry value type)

        Raises:
            RegistryKeyNotFoundError: If key doesn't exist
            PermissionError: If insufficient permissions

        Example:
            >>> value = integration.read_registry_key(
            ...     winreg.HKEY_LOCAL_MACHINE,
            ...     r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
            ...     "ProgramFilesDir"
            ... )

        """
        try:
            # Open registry key for reading
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                value, value_type = winreg.QueryValueEx(key, value_name)
                logger.debug(
                    f"Read registry key: {key_path}\\{value_name} = {value} (type: {value_type})",
                )
                return value

        except FileNotFoundError as e:
            error_msg = f"Registry key not found: {key_path}\\{value_name}"
            logger.exception(error_msg)
            raise RegistryKeyNotFoundError(error_msg) from e
            error_msg = (
                f"Permission denied reading registry key: {key_path}\\{value_name}. "
                f"Administrator privileges may be required."
            )
            logger.exception(error_msg)
            raise PermissionError(error_msg) from e
            error_msg = f"Error reading registry key {key_path}\\{value_name}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def write_registry_key(
        self,
        hive: int,
        key_path: str,
        value_name: str,
        value: Any,  # noqa: ANN401
        value_type: int = 1,  # winreg.REG_SZ = 1
    ) -> None:
        r"""Write a Windows registry key.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            hive: Registry hive (e.g., winreg.HKEY_LOCAL_MACHINE)
            key_path: Path to registry key
            value_name: Name of value to write
            value: Value to write
            value_type: Registry value type (default: REG_SZ for string)

        Raises:
            PermissionError: If insufficient permissions

        Example:
            >>> integration.write_registry_key(
            ...     winreg.HKEY_CURRENT_USER,
            ...     r"SOFTWARE\\MyApp",
            ...     "Setting",
            ...     "Value"
            ... )

        """
        try:
            # Create or open registry key for writing
            with winreg.CreateKey(hive, key_path) as key:
                winreg.SetValueEx(key, value_name, 0, value_type, value)
                logger.info(
                    f"Wrote registry key: {key_path}\\{value_name} = {value} (type: {value_type})",
                )

        except PermissionError as e:
            error_msg = (
                f"Permission denied writing registry key: {key_path}\\{value_name}. "
                f"Administrator privileges required."
            )
            logger.exception(error_msg)
            raise PermissionError(error_msg) from e
            error_msg = f"Error writing registry key {key_path}\\{value_name}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def delete_registry_key(self, hive: int, key_path: str, value_name: str | None = None) -> None:
        r"""Delete a Windows registry key or value.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            hive: Registry hive (e.g., winreg.HKEY_LOCAL_MACHINE)
            key_path: Path to registry key
            value_name: Name of value to delete (if None, deletes entire key)

        Raises:
            PermissionError: If insufficient permissions
            RegistryKeyNotFoundError: If key doesn't exist

        Example:
            >>> # Delete a value
            >>> integration.delete_registry_key(
            ...     winreg.HKEY_CURRENT_USER,
            ...     r"SOFTWARE\\MyApp",
            ...     "Setting"
            ... )
            >>> # Delete entire key
            >>> integration.delete_registry_key(
            ...     winreg.HKEY_CURRENT_USER,
            ...     r"SOFTWARE\\MyApp"
            ... )

        """
        try:
            if value_name is not None:
                # Delete a specific value
                with winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, value_name)
                    logger.info("Deleted registry value: %s\\%s", key_path, value_name)
            else:
                # Delete entire key
                winreg.DeleteKey(hive, key_path)
                logger.info("Deleted registry key: %s", key_path)

        except FileNotFoundError as e:
            error_msg = f"Registry key not found: {key_path}"
            if value_name:
                error_msg += f"\\{value_name}"
            logger.exception(error_msg)
            raise RegistryKeyNotFoundError(error_msg) from e
            error_msg = (
                f"Permission denied deleting registry key: {key_path}. "
                f"Administrator privileges required."
            )
            logger.exception(error_msg)
            raise PermissionError(error_msg) from e
            error_msg = f"Error deleting registry key {key_path}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    # Service Management

    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get Windows service status.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            service_name: Name of the Windows service

        Returns:
            ServiceStatus with current status and startup type

        Raises:
            RuntimeError: If pywin32 not available or service not found

        Example:
            >>> status = integration.get_service_status("wuauserv")
            >>> print(f"Windows Update: {status.status}")

        """
        if not PYWIN32_AVAILABLE:
            msg = "pywin32 required for service management. Install with: pip install pywin32"
            raise RuntimeError(
                msg,
            )

        try:
            # Query service status
            status = win32serviceutil.QueryServiceStatus(service_name)

            # Map Windows service states to our status strings
            state_map = {
                win32service.SERVICE_STOPPED: "stopped",
                win32service.SERVICE_START_PENDING: "starting",
                win32service.SERVICE_STOP_PENDING: "stopping",
                win32service.SERVICE_RUNNING: "running",
                win32service.SERVICE_CONTINUE_PENDING: "running",
                win32service.SERVICE_PAUSE_PENDING: "paused",
                win32service.SERVICE_PAUSED: "paused",
            }

            service_status = state_map.get(status[1], "unknown")

            # Get startup type
            startup_type = self._get_service_startup_type(service_name)

            logger.debug(
                "Service %s: status=%s, startup=%s",
                service_name,
                service_status,
                startup_type,
            )

            return ServiceStatus(
                name=service_name,
                status=service_status,
                startup_type=startup_type,
            )

        except pywintypes.error as e:
            error_msg = f"Service not found or access denied: {service_name}"
            logger.exception("%s: %s")
            raise RuntimeError(error_msg) from e
            error_msg = f"Error querying service {service_name}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def _get_service_startup_type(self, service_name: str) -> str:
        """Get service startup type from registry.

        Args:
            service_name: Name of the service

        Returns:
            Startup type: "automatic", "manual", or "disabled"

        """
        try:
            if not WINREG_AVAILABLE or winreg is None:
                return "unknown"
            key_path = f"SYSTEM\\CurrentControlSet\\Services\\{service_name}"
            start_value = self.read_registry_key(winreg.HKEY_LOCAL_MACHINE, key_path, "Start")

            # Map Windows start values to our startup types
            startup_map = {
                2: "automatic",  # SERVICE_AUTO_START
                3: "manual",  # SERVICE_DEMAND_START
                4: "disabled",  # SERVICE_DISABLED
            }

            return startup_map.get(start_value, "unknown")

        except Exception:
            return "unknown"
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
        attrs = ["pid", "name", "status", "cpu_percent", "memory_percent", "create_time"]

        for proc in psutil.process_iter(attrs=attrs):
            try:
                info = proc.info
                processes.append(
                    ProcessInfo(
                        pid=info.get("pid") or 0,
                        name=info.get("name") or "unknown",
                        status=info.get("status") or "unknown",
                        cpu_percent=info.get("cpu_percent") or 0.0,
                        memory_percent=info.get("memory_percent") or 0.0,
                        create_time=info.get("create_time") or 0.0,
                    ),
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                continue
        logger.debug("Retrieved %s processes", len(processes))
        return processes

    def start_process(self, executable: str, args: list[str]) -> int:
        """Start a new process.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            executable: Path to executable or bare executable name
            args: Command-line arguments

        Returns:
            Process ID of started process

        Raises:
            FileNotFoundError: If executable not found
            PermissionError: If insufficient permissions

        Example:
            >>> pid = integration.start_process("notepad.exe", [])
            >>> print(f"Started notepad with PID: {pid}")

        """
        try:
            cmd = [executable, *args]

            # Try direct Popen first (works for full paths and PATH-resolved names).
            # Use DETACHED_PROCESS so the child is fully independent and doesn't
            # inherit our stdio handles (avoids the "handle is invalid" error when
            # running without a console).
            try:
                process = subprocess.Popen(  # noqa: S603
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=(
                        subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    ),
                )
                logger.info("Started process: %s (PID: %s)", executable, process.pid)
                return process.pid
            except (FileNotFoundError, OSError):
                pass
            # Fallback: Check if executable exists using shutil.which before trying shell=True
            import shutil

            if not args and shutil.which(executable):
                try:
                    proc = subprocess.Popen(
                        executable,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                    )
                    logger.info("Started process via shell: %s (PID: %s)", executable, proc.pid)
                    return proc.pid
                except (OSError, FileNotFoundError):
                    logger.exception("Shell launch failed for %r: %s")
                    # Fall through to raise FileNotFoundError below
            # If we reach here, all attempts failed - executable not found
            msg = f"Executable not found: '{executable}'"
            raise FileNotFoundError(msg)

        except FileNotFoundError as e:
            logger.exception("Executable not found")
            raise
            logger.exception("Permission denied starting process")
            raise
            error_msg = f"Error starting process {executable}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def terminate_process(self, pid: int, force: bool = False) -> bool:
        """Terminate a process.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            pid: Process ID
            force: If True, force kill; if False, graceful termination

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
                process.kill()  # SIGKILL equivalent
                logger.info("Force killed process %s", pid)
            else:
                process.terminate()  # SIGTERM equivalent
                logger.info("Terminated process %s", pid)

            return True

        except psutil.NoSuchProcess as e:
            error_msg = f"Process not found: PID {pid}"
            logger.exception(error_msg)
            raise ProcessLookupError(error_msg) from e
            error_msg = (
                f"Permission denied terminating process {pid}. "
                f"Administrator privileges may be required."
            )
            logger.exception(error_msg)
            raise PermissionError(error_msg) from e
            error_msg = f"Error terminating process {pid}: {e}"
            logger.exception(error_msg)
            raise RuntimeError(error_msg) from e
    def execute_command(self, command: str, args: list[str]) -> CommandResult:
        """Execute a Windows command.

        Time Complexity: O(1) + command execution time
        Space Complexity: O(output_size)

        Args:
            command: Command to execute
            args: Command arguments

        Returns:
            CommandResult with stdout, stderr, and return code

        Example:
            >>> result = integration.execute_command("cmd", ["/c", "echo", "Hello"])
            >>> print(result.stdout)

        """
        import time

        try:
            start_time = time.time()

            # Build command
            cmd = [command, *args]

            # Reject privileged commands unless running as admin (Issue #16)
            _PRIVILEGED_COMMANDS = {"net", "sc", "reg", "bcdedit", "diskpart", "icacls", "takeown"}
            cmd_lower = command.lower()
            cmd_lower = cmd_lower.removesuffix(".exe")
            if cmd_lower in _PRIVILEGED_COMMANDS and not self.is_admin():
                msg = (
                    f"Privileged command '{command}' requires administrator rights. "
                    "Verify permissions before calling execute_command with privileged tools."
                )
                raise PermissionError(
                    msg,
                )

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
        """Get Windows system information.

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
            platform="Windows",
            platform_version=platform.version(),
            architecture=platform.machine(),
            processor=platform.processor(),
            cpu_count_physical=psutil.cpu_count(logical=False) or 0,
            cpu_count_logical=psutil.cpu_count(logical=True) or 0,
            boot_time=psutil.boot_time(),
        )

    # Permission Validation

    def is_admin(self) -> bool:
        """Check if running with administrator privileges.

        Returns:
            True if running as administrator

        Example:
            >>> if integration.is_admin():
            ...     print("Running as administrator")

        """
        try:
            import ctypes

            result: int = ctypes.windll.shell32.IsUserAnAdmin()
            return result != 0
        except Exception:
            return False
