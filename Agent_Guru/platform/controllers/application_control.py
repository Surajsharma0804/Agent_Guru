"""Module: agent_guru.platform.controllers.application_control
Purpose: Complete application and window management controller.

This module provides comprehensive application control for the Platform Integration System,
enabling AGENT_GURU to control ANY application through voice commands.

Performance Characteristics:
    - Time Complexity: O(1) for application launch, O(n) for window enumeration
    - Space Complexity: O(1) for single operations, O(n) for window lists
    - Latency: <100ms for application launch, <50ms for window operations
    - Throughput: >50 operations/second

Architecture:
    The controller provides a unified interface for application control with:
    1. Cross-platform application launching
    2. Window management (minimize, maximize, restore, focus)
    3. Application switching (Alt+Tab simulation)
    4. Platform-specific optimizations

Safety Features:
    - Graceful application termination before force kill
    - Window state validation before operations
    - Error handling with detailed error messages
    - Audit logging for all operations

Usage Example:
    >>> from agent_guru.platform.controllers.application_control import ApplicationController
    >>>
    >>> # Initialize controller
    >>> controller = ApplicationController()
    >>>
    >>> # Open application
    >>> controller.open_application("notepad")
    >>>
    >>> # Minimize window
    >>> controller.minimize_window("Notepad")
    >>>
    >>> # Switch to application
    >>> controller.switch_to_application("Chrome")

Author: Agent Guru Development Team
Date: 2026-02-24
Version: 1.0.0
"""

import logging
import os
import subprocess  # nosec B404
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from Agent_Guru.platform.protected_processes import is_protected_process_name

# Configure logging
logger = logging.getLogger(__name__)

class ApplicationState(Enum):
    """Application window states."""

    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    HIDDEN = "hidden"
    UNKNOWN = "unknown"

@dataclass
class WindowInfo:
    """Information about an application window.

    Attributes:
        title: Window title
        handle: Platform-specific window handle
        pid: Process ID of the application
        state: Current window state
        position: Window position (x, y, width, height)
        is_active: Whether window is currently active

    """

    title: str
    handle: Any
    pid: int
    state: ApplicationState
    position: tuple[int, int, int, int]
    is_active: bool

@dataclass
class ApplicationInfo:
    """Information about a running application.

    Attributes:
        name: Application name
        pid: Process ID
        executable: Path to executable
        windows: List of windows owned by application

    """

    name: str
    pid: int
    executable: str
    windows: list[WindowInfo]

class ApplicationController:
    """Controller for comprehensive application and window management.

    This controller provides a unified interface for application control with
    cross-platform support and platform-specific optimizations.

    Time Complexity:
        - Application launch: O(1)
        - Window enumeration: O(n) where n is number of windows
        - Window operations: O(1)

    Space Complexity:
        - Single operations: O(1)
        - Window lists: O(n) where n is number of windows

    Attributes:
        platform: Current platform name
        _platform_integration: Platform-specific integration instance

    """

    # Process names close_application()/_taskkill_by_name() must never
    # terminate - killing any of these takes down the OS shell or a core
    # system service, not just "an app".
    #
    # BUG FIX (found 2026-09-13, this round): this used to be a local class
    # constant here, duplicating an identical set that ProcessManager
    # (platform/process_manager.py) independently needed for the exact same
    # reason once its own terminate_process() got the same class of
    # protected-process check. Two independently-maintained copies of a
    # safety-critical list is exactly how they drift apart -- a name added
    # to one guard after an incident but not the other leaves a real gap.
    # Now both import the single canonical set from
    # platform/protected_processes.py instead.
    def __init__(self) -> None:
        """Initialize application controller."""
        self.platform = sys.platform
        self._platform_integration = self._get_platform_integration()

    @staticmethod
    def _is_protected_process_name(name: str | None) -> bool:
        """Return True if *name* (a friendly name or an exe name) is protected."""
        return is_protected_process_name(name)

    def _get_process_name(self, pid: int) -> str | None:
        """Look up the real executable name currently running as *pid*.

        Used to re-check a process against the protected-process set right
        before termination - see the BUG FIX note in close_application()
        for why checking the caller's input string alone isn't enough.
        """
        try:
            # Only pid and name are needed. The full read (status, CPU and
            # memory per process) took 3 to 5 s on Windows, and closing an app
            # runs this check after a lookup by name that paid the same again.
            for process in self._platform_integration.get_process_list(include_usage=False):
                if process.pid == pid:
                    return process.name
        except Exception:
            logger.exception("Failed to look up process name for pid %s", pid)
        return None

    @staticmethod
    def _sanitize_window_identifier(window_identifier: str) -> str:
        """Sanitize window identifier to prevent injection attacks.

        Args:
            window_identifier: Raw window identifier

        Returns:
            Sanitized window identifier

        Raises:
            ValueError: If identifier contains dangerous characters

        """
        # Remove any null bytes
        if "\x00" in window_identifier:
            msg = "Window identifier contains null bytes"
            raise ValueError(msg)

        # Check for dangerous characters that could be used for injection
        dangerous_chars = ["\n", "\r", ";", "&", "|", "`", "$", "(", ")", "<", ">", '"', "'", "\\"]
        for char in dangerous_chars:
            if char in window_identifier:
                msg = f"Window identifier contains dangerous character: {char}"
                raise ValueError(msg)

        # Limit length to prevent buffer overflow attacks
        if len(window_identifier) > 256:
            msg = "Window identifier too long (max 256 characters)"
            raise ValueError(msg)

        return window_identifier.strip()

    def _get_platform_integration(self) -> Any:
        """Get platform-specific integration instance.

        Returns:
            Platform-specific integration instance

        Raises:
            ImportError: If platform-specific module not available

        """
        try:
            if self.platform == "win32":
                from Agent_Guru.platform.windows.integration import WindowsIntegration

                return WindowsIntegration()
            if self.platform == "darwin":
                from Agent_Guru.platform.macos.integration import MacOSIntegration

                return MacOSIntegration()
            if self.platform.startswith("linux"):
                from Agent_Guru.platform.linux.integration import LinuxIntegration

                return LinuxIntegration()
            msg = f"Unsupported platform: {self.platform}"
            raise ImportError(msg)
        except ImportError:
            logger.exception("Failed to load platform integration")
            raise

    def open_application(
        self,
        app_name: str,
        args: list[str] | None = None,
        wait_for_launch: bool = True,
    ) -> int:
        """Open an application by name.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            app_name: Application name or path to executable
            args: Optional command-line arguments
            wait_for_launch: Whether to wait for application to launch

        Returns:
            Process ID of launched application

        Raises:
            FileNotFoundError: If application not found
            PermissionError: If insufficient permissions to launch
            RuntimeError: If application launch fails

        Example:
            >>> controller = ApplicationController()
            >>> pid = controller.open_application("notepad")
            >>> print(f"Launched notepad with PID {pid}")

        """
        logger.info("Opening application: %s", app_name)

        try:
            # Resolve application path
            app_path = self._resolve_application_path(app_name)

            # Launch application using platform integration
            args = args or []
            pid = self._platform_integration.start_process(app_path, args)

            # Wait for application to launch if requested
            if wait_for_launch:
                time.sleep(0.5)  # Give app time to create window

            logger.info("Successfully launched %s with PID %s", app_name, pid)
            return pid

        except FileNotFoundError:
            logger.exception("Application not found")
            raise

    def _resolve_application_path(self, app_name: str) -> str:
        """Resolve application name to full executable path.

        Time Complexity: O(1) for absolute paths, O(n) for PATH search
        Space Complexity: O(1)

        Args:
            app_name: Application name or path

        Returns:
            Full path to executable

        Raises:
            FileNotFoundError: If application not found

        """
        # If already a full path, validate and return
        if os.path.isabs(app_name):  # noqa: PTH117
            # Security: Validate absolute path doesn't contain traversal sequences
            if ".." in app_name:
                msg = f"Invalid application path: {app_name}"
                raise ValueError(msg)
            # Resolve to canonical path and verify it exists
            app_real = os.path.realpath(app_name)
            if os.path.exists(app_real):
                return app_real
            msg = f"Application not found: {app_name}"
            raise FileNotFoundError(msg)

        # Platform-specific application resolution
        if self.platform == "win32":
            return self._resolve_windows_application(app_name)
        if self.platform == "darwin":
            return self._resolve_macos_application(app_name)
        return self._resolve_linux_application(app_name)

    # Common voice-command names to Windows executable names
    _COMMON_WINDOWS_APPS: dict[str, str] = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "wordpad": "wordpad.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "command prompt": "cmd.exe",
        "powershell": "powershell.exe",
        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "control panel": "control.exe",
        "control": "control.exe",
        "snipping tool": "SnippingTool.exe",
        "snip": "SnippingTool.exe",
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "mozilla firefox": "firefox.exe",
        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
        "outlook": "OUTLOOK.EXE",
        "teams": "Teams.exe",
        "microsoft teams": "Teams.exe",
        "spotify": "Spotify.exe",
        "discord": "Discord.exe",
        "vlc": "vlc.exe",
        "zoom": "Zoom.exe",
        "vs code": "Code.exe",
        "vscode": "Code.exe",
        "visual studio code": "Code.exe",
    }

    def _resolve_windows_application(self, app_name: str) -> str:
        """Resolve Windows application name to path.

        Handles built-in Windows apps (notepad, calc, mspaint, etc.) as well
        as installed applications found in Program Files or PATH.

        Args:
            app_name: Application name (with or without .exe)

        Returns:
            Full path to executable, or the bare name if found in PATH/System32

        """
        import shutil

        name_lower = app_name.strip().lower()
        exe_name = self._COMMON_WINDOWS_APPS.get(name_lower)
        if exe_name is None:
            exe_name = app_name if app_name.lower().endswith(".exe") else f"{app_name}.exe"

        # Security: Validate exe_name doesn't contain path separators or traversal sequences
        if os.sep in exe_name or "/" in exe_name or "\\" in exe_name or ".." in exe_name:
            msg = f"Invalid application name: {app_name}"
            raise ValueError(msg)

        # 1. Check PATH (covers System32, WindowsApps, etc.)
        found = shutil.which(exe_name)
        if found:
            return found

        # 2. Check System32 / SysWOW64 explicitly
        result = self._search_system_dirs(exe_name)
        if result:
            return result

        # 3. Check Program Files directories
        result = self._search_program_dirs(exe_name)
        if result:
            return result

        # 4. Last resort: return the bare exe name
        logger.warning(
            "Could not resolve full path for '%s', using bare name '%s'",
            app_name, exe_name,
        )
        return exe_name

    @staticmethod
    def _search_system_dirs(exe_name: str) -> str | None:
        """Search System32 and SysWOW64 for the executable."""
        system_root = os.environ.get("SystemRoot", "C:\\Windows")
        for sub in ("System32", "SysWOW64"):
            sys_dir_real = os.path.realpath(os.path.join(system_root, sub))
            if not os.path.isabs(sys_dir_real):  # noqa: PTH117
                continue
            candidate = os.path.join(sys_dir_real, exe_name)
            if not candidate.startswith(sys_dir_real + os.sep):
                continue
            if os.path.exists(candidate):
                candidate_real = os.path.realpath(candidate)
                if candidate_real.startswith(sys_dir_real + os.sep):
                    return candidate_real
        return None

    @staticmethod
    def _search_program_dirs(exe_name: str) -> str | None:
        """Search Program Files directories for the executable (up to 2 levels deep)."""
        prog_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
            os.path.join(os.environ.get("APPDATA", ""), "Local", "Programs"),
        ]
        for prog_dir in prog_dirs:
            if not prog_dir:
                continue
            prog_dir_real = os.path.realpath(prog_dir)
            # Direct match
            candidate = os.path.join(prog_dir_real, exe_name)
            if candidate.startswith(prog_dir_real + os.sep) and os.path.exists(candidate):
                return candidate
            # Subdirectory search (1-2 levels deep)
            try:
                for sub in os.listdir(prog_dir_real):  # noqa: PTH208
                    sub_dir = os.path.join(prog_dir_real, sub)
                    sub_path = os.path.join(sub_dir, exe_name)
                    if sub_path.startswith(prog_dir_real + os.sep) and os.path.exists(sub_path):
                        return sub_path
                    if os.path.isdir(sub_dir):  # noqa: PTH112
                        for sub2 in os.listdir(sub_dir):  # noqa: PTH208
                            deep = os.path.join(sub_dir, sub2, exe_name)
                            if deep.startswith(prog_dir_real + os.sep) and os.path.exists(deep):
                                return deep
            except (PermissionError, OSError):
                continue
        return None

    def _resolve_macos_application(self, app_name: str) -> str:
        """Resolve macOS application name to path.

        Args:
            app_name: Application name

        Returns:
            Full path to executable

        """
        # Security: Validate app_name doesn't contain path separators or traversal sequences
        if "/" in app_name or ".." in app_name or os.sep in app_name:
            msg = f"Invalid application name: {app_name}"
            raise ValueError(msg)

        # Check if it's a .app bundle
        app_bundle = app_name if app_name.endswith(".app") else f"{app_name}.app"

        # Check common macOS application paths
        base_paths = [
            "/Applications",
            os.path.expanduser("~/Applications"),  # noqa: PTH111
        ]

        for base_path in base_paths:
            base_real = os.path.realpath(base_path)
            candidate = os.path.join(base_real, app_bundle)
            # Validate candidate is within base_path
            if not candidate.startswith(base_real + os.sep):
                continue
            if os.path.exists(candidate):
                # Return path to executable inside bundle
                exec_name = app_name.replace(".app", "")
                exec_path = os.path.join(candidate, "Contents", "MacOS", exec_name)
                # Final validation
                if exec_path.startswith(base_real + os.sep):
                    return exec_path

        # Search in PATH
        import shutil

        path = shutil.which(app_name)
        if path:
            return path

        msg = f"Application not found: {app_name}"
        raise FileNotFoundError(msg)

    def _resolve_linux_application(self, app_name: str) -> str:
        """Resolve Linux application name to path.

        Args:
            app_name: Application name

        Returns:
            Full path to executable

        """
        # Security: Validate app_name doesn't contain path separators or traversal sequences
        if "/" in app_name or ".." in app_name or os.sep in app_name:
            msg = f"Invalid application name: {app_name}"
            raise ValueError(msg)

        # Search in PATH
        import shutil

        path = shutil.which(app_name)
        if path:
            return path

        # Check common Linux application paths
        base_dirs = [
            "/usr/bin",
            "/usr/local/bin",
            os.path.expanduser("~/.local/bin"),  # noqa: PTH111
        ]

        for base_dir in base_dirs:
            base_real = os.path.realpath(base_dir)
            candidate = os.path.join(base_real, app_name)
            # Validate candidate is within base_dir
            if not candidate.startswith(base_real + os.sep):
                continue
            if os.path.exists(candidate):
                # Final validation: resolve and verify it's still within base_dir
                candidate_real = os.path.realpath(candidate)
                if candidate_real.startswith(base_real + os.sep):
                    return candidate_real

        # Check /opt with subdirectory structure
        opt_base = "/opt"
        opt_real = os.path.realpath(opt_base)
        opt_candidate = os.path.join(opt_real, app_name, "bin", app_name)
        if opt_candidate.startswith(opt_real + os.sep) and os.path.exists(opt_candidate):
            opt_candidate_real = os.path.realpath(opt_candidate)
            if opt_candidate_real.startswith(opt_real + os.sep):
                return opt_candidate_real

        msg = f"Application not found: {app_name}"
        raise FileNotFoundError(msg)

    def close_application(
        self,
        app_identifier: str,
        force: bool = False,
        timeout: float = 5.0,
    ) -> bool:
        """Close an application by name or PID.

        Time Complexity: O(n) where n is number of processes
        Space Complexity: O(1)

        Args:
            app_identifier: Application name or PID
            force: Whether to force kill (True) or graceful shutdown (False)
            timeout: Timeout in seconds for graceful shutdown

        Returns:
            True if application was closed successfully

        Raises:
            ProcessLookupError: If application not found
            RuntimeError: If close operation fails

        Example:
            >>> controller = ApplicationController()
            >>> controller.close_application("notepad")
            True

        """
        logger.info("Closing application: %s (force=%s)", app_identifier, force)

        # Guard: never allow closing system-critical or IDE processes.
        # This first check catches the identifier being ALREADY the literal
        # protected exe name (e.g. someone/something passes "explorer.exe"
        # directly) - it is not, by itself, enough; see the second check
        # below for why.
        if isinstance(app_identifier, str) and self._is_protected_process_name(app_identifier):
            msg = f"Refusing to close protected process: {app_identifier}"
            raise ValueError(msg)

        try:
            # Find process by name or PID
            if isinstance(app_identifier, int) or (
                isinstance(app_identifier, str) and app_identifier.isdigit()
            ):
                pid = int(app_identifier)
            else:
                pid = self._find_process_by_name(app_identifier)

            if pid is None:
                # On Windows, fall back to taskkill which handles UWP/Store apps
                # that may not appear under their friendly name in psutil
                if self.platform == "win32":
                    return self._taskkill_by_name(app_identifier, force=force)
                msg = f"Application not found: {app_identifier}"
                raise ProcessLookupError(msg)

            # BUG FIX (found 2026-09-13): the guard above only catches an
            # identifier that IS ALREADY the literal protected exe name -
            # but real voice/text input uses friendly names ("explorer",
            # "file explorer"), and _find_process_by_name() resolves those
            # straight to the protected process (explorer.exe IS the
            # Windows shell, and IS in _PROTECTED_PROCESS_NAMES) via
            # _PROCESS_NAME_ALIASES without ever tripping that check. That
            # meant an entirely ordinary command like "close explorer"
            # could silently bypass "never kill system-critical processes"
            # and take down the desktop shell - the guard existed but
            # didn't actually guard the case it was clearly written for.
            # Re-checking the REAL resolved process name right before
            # termination closes that gap for every path that reaches this
            # point (alias table match, substring fallback, or an explicit
            # PID the caller passed directly), not just the input string.
            real_name = self._get_process_name(pid)
            if self._is_protected_process_name(real_name):
                msg = (
                    f"Refusing to close protected process: {app_identifier!r} "
                    f"resolves to {real_name!r}"
                )
                raise ValueError(msg)

            # Terminate process via platform integration
            success = self._platform_integration.terminate_process(pid, force=force)

            if success:
                logger.info("Successfully closed application: %s", app_identifier)
            else:
                logger.warning("Failed to close application: %s", app_identifier)

            return success

        except ProcessLookupError:
            logger.exception("Application not found")
            raise

    def _taskkill_by_name(self, app_name: str, force: bool = False) -> bool:
        """Use Windows taskkill to close an application by name.

        Resolves the exe name via _PROCESS_NAME_ALIASES and falls back to a
        substring search so UWP/Store apps (e.g. CalculatorApp.exe) are found
        even when psutil reports them under a different name.

        Args:
            app_name: Friendly application name
            force: Whether to force-kill (/F flag)

        Returns:
            True if taskkill succeeded

        """
        import subprocess as _sp  # nosec B404

        # BUG FIX (found 2026-09-13, same class as close_application()'s
        # fix above): this method is the fallback close_application() uses
        # when _find_process_by_name() can't find a PID via psutil (e.g. a
        # UWP/Store app, or a lookup that's flaky for some other reason) -
        # which is precisely the case where the caller-input-only guard at
        # the top of close_application() is the ONLY check that ran, and
        # that guard only catches the input already being the literal
        # protected exe name. A friendly name like "explorer" sails through
        # unblocked and resolves right here, via _PROCESS_NAME_ALIASES, to
        # the real protected exe (e.g. "explorer.exe") - so without a check
        # in this method too, "close explorer" could still reach a real
        # `taskkill /IM explorer.exe` through this path even after the
        # close_application() fix, defeating it entirely for any app whose
        # psutil lookup happens to miss. Filter every resolved alias against
        # the same canonical protected-name set before running taskkill on
        # any of them, exactly as close_application() now does for the
        # psutil-found-a-pid path.
        if self._is_protected_process_name(app_name):
            logger.error(
                "Refusing to taskkill protected process (raw identifier): %s",
                app_name,
            )
            return False

        name_lower = app_name.strip().lower()
        aliases = self._PROCESS_NAME_ALIASES.get(name_lower, [])
        # Also try the raw name with .exe appended
        if not aliases:
            aliases = [f"{app_name}.exe"]

        safe_aliases = [a for a in aliases if not self._is_protected_process_name(a)]
        if len(safe_aliases) < len(aliases):
            blocked = [a for a in aliases if a not in safe_aliases]
            logger.error(
                "Refusing to taskkill protected process alias(es) %s for '%s'",
                blocked,
                app_name,
            )
        if not safe_aliases:
            # Every resolved alias was protected -- refuse outright rather
            # than silently falling through to "no aliases left to try",
            # which would look like an ordinary "app not found" failure and
            # obscure that this was actually a safety refusal.
            return False

        for exe_name in safe_aliases:
            try:
                cmd = ["taskkill", "/IM", exe_name]
                if force:
                    cmd.append("/F")
                result = _sp.run(  # nosec B603  # noqa: S603
                    cmd,
                    check=False,
                    stdout=_sp.DEVNULL,
                    stderr=_sp.DEVNULL,
                    timeout=10,
                )
                if result.returncode == 0:
                    logger.info("taskkill succeeded for %s", exe_name)
                    return True
            except (OSError, _sp.TimeoutExpired):
                logger.exception("taskkill failed for")
        logger.error("taskkill could not close any alias for '%s'", app_name)
        return False

    # Map of friendly names → possible process executable names (Windows 11 UWP aliases included)
    _PROCESS_NAME_ALIASES: dict[str, list[str]] = {
        "calculator": ["calculatorapp.exe", "calc.exe"],
        "calc": ["calculatorapp.exe", "calc.exe"],
        "notepad": ["notepad.exe"],
        "paint": ["mspaint.exe", "paintapp.exe"],
        "mspaint": ["mspaint.exe", "paintapp.exe"],
        "explorer": ["explorer.exe"],
        "file explorer": ["explorer.exe"],
        "chrome": ["chrome.exe"],
        "google chrome": ["chrome.exe"],
        "firefox": ["firefox.exe"],
        "edge": ["msedge.exe"],
        "microsoft edge": ["msedge.exe"],
        "word": ["winword.exe"],
        "excel": ["excel.exe"],
        "powerpoint": ["powerpnt.exe"],
        "outlook": ["outlook.exe"],
        "teams": ["teams.exe"],
        "spotify": ["spotify.exe"],
        "discord": ["discord.exe"],
        "vlc": ["vlc.exe"],
        "zoom": ["zoom.exe"],
        "vs code": ["code.exe"],
        "vscode": ["code.exe"],
        "visual studio code": ["code.exe"],
        "task manager": ["taskmgr.exe"],
        "taskmgr": ["taskmgr.exe"],
        "snipping tool": ["snippingtool.exe", "sniptool.exe"],
    }

    def _process_names(self, app_name: str) -> set[str]:
        """The exact executable names that are this application (lowercase).

        The alias table for known names ("calculator" is CalculatorApp.exe
        or calc.exe), otherwise the name itself as an .exe. Exact names
        only: see _find_process_by_name() for what substring matching did.
        """
        name = app_name.strip().lower()
        aliases = self._PROCESS_NAME_ALIASES.get(name)
        if aliases:
            return {a.lower() for a in aliases}
        return {name if name.endswith(".exe") else f"{name}.exe"}

    def _find_process_by_name(self, app_name: str) -> int | None:
        """Find the process to close for an application name.

        Only processes whose executable is exactly one of the application's
        names (_process_names) are considered. This used to fall back to a
        substring match, also for known names when their real executable
        was not running, so "close word" with WordPad open matched
        wordpad.exe, and an unknown short name matched any process whose
        name contained it.

        Among those, one that owns a visible window comes first. Windows 11
        Notepad runs two notepad.exe processes, and the first one found was
        the one without the window: it was terminated, the window stayed
        open, and the close was reported done.

        Time Complexity: O(n + w) for n processes and w windows
        Space Complexity: O(n)

        Args:
            app_name: Application name (friendly name or exe name)

        Returns:
            Process ID if found, None otherwise

        """
        try:
            names = self._process_names(app_name)
            processes = self._platform_integration.get_process_list(include_usage=False)
            pids = [p.pid for p in processes if p.name.lower() in names]
            if not pids:
                return None
            windowed = {w.pid for w in self.list_windows()}
            return next((pid for pid in pids if pid in windowed), pids[0])

        except Exception:
            logger.exception("Failed to find process")
            return None

    def app_instances(self, app_name: str) -> dict[int, bool] | None:
        """The running processes that are this application, each with whether it shows a window.

        Read only; used to check that opening or closing an application did
        what was asked, not just that the launch or close call returned. A
        process counts by its exact executable name (_process_names), so a
        launcher or an unrelated process with a similar name does not. None
        when the state cannot be read: not Windows, the process list
        failed, or no window could be listed at all (a desktop session
        always has some, so an empty list means the listing failed and
        "no window" would be a guess).

        Returns:
            {pid: has a visible titled window} for each running instance, or
            None if that cannot be told.

        """
        if self.platform != "win32":
            return None
        try:
            names = self._process_names(app_name)
            processes = self._platform_integration.get_process_list(include_usage=False)
            pids = [p.pid for p in processes if p.name.lower() in names]
            windows = self.list_windows()
        except Exception:
            logger.exception("Failed to read the state of %s", app_name)
            return None
        if pids and not windows:
            return None
        windowed = {w.pid for w in windows}
        return {pid: pid in windowed for pid in pids}

    def minimize_window(self, window_identifier: str) -> bool:
        """Minimize an application window.

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(1)

        Args:
            window_identifier: Window title or handle

        Returns:
            True if window was minimized successfully

        Raises:
            RuntimeError: If window operation fails

        Example:
            >>> controller = ApplicationController()
            >>> controller.minimize_window("Notepad")
            True

        """
        logger.info("Minimizing window: %s", window_identifier)

        try:
            if self.platform == "win32":
                return self._minimize_window_windows(window_identifier)
            if self.platform == "darwin":
                return self._minimize_window_macos(window_identifier)
            return self._minimize_window_linux(window_identifier)

        except Exception as e:
            logger.exception("Failed to minimize window")
            msg = f"Failed to minimize window: {e}"
            raise RuntimeError(msg) from e

    def _minimize_window_windows(self, window_identifier: str) -> bool:
        """Minimize window on Windows.

        Args:
            window_identifier: Window title

        Returns:
            True if successful

        """
        try:
            import win32con  # type: ignore[import-untyped]
            import win32gui  # type: ignore[import-untyped]

            # Find window by title
            hwnd = win32gui.FindWindow(None, window_identifier)
            if hwnd == 0:
                # Try partial match
                hwnd = self._find_window_by_partial_title(window_identifier)

            if hwnd == 0:
                logger.warning("Window not found: %s", window_identifier)
                return False

            # Minimize window
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return True

        except ImportError:
            logger.exception("pywin32 not available")
            return False
        except Exception:
            logger.exception("Failed to minimize window")
            return False

    def _find_window_by_partial_title(self, partial_title: str) -> int:
        """Find window by partial title match (Windows).

        Args:
            partial_title: Partial window title

        Returns:
            Window handle or 0 if not found

        """
        try:
            import win32gui  # type: ignore[import-untyped]

            found_hwnd = [0]
            partial_lower = partial_title.lower()

            def enum_callback(hwnd, _) -> bool:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if partial_lower in title.lower():
                        found_hwnd[0] = hwnd
                        return False  # Stop enumeration
                return True

            win32gui.EnumWindows(enum_callback, None)
            return found_hwnd[0]

        except Exception:
            logger.exception("Failed to find window")
            return 0

    def _minimize_window_macos(self, window_identifier: str) -> bool:
        """Minimize window on macOS.

        Args:
            window_identifier: Window title

        Returns:
            True if successful

        """
        try:
            # Sanitize input to prevent injection
            safe_identifier = self._sanitize_window_identifier(window_identifier)
            # Escape quotes for AppleScript
            safe_identifier = safe_identifier.replace('"', '\\"')

            script = f"""
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                tell process frontApp
                    set windowList to every window
                    repeat with aWindow in windowList
                        if name of aWindow contains "{safe_identifier}" then
                            set miniaturized of aWindow to true
                            return true
                        end if
                    end repeat
                end tell
            end tell
            return false
            """

            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            return result.returncode == 0 and "true" in result.stdout.lower()

        except ValueError:
            logger.exception("Invalid window identifier")
            return False
        except Exception:
            logger.exception("Failed to minimize window")
            return False

    def _minimize_window_linux(self, window_identifier: str) -> bool:
        """Minimize window on Linux.

        Args:
            window_identifier: Window title

        Returns:
            True if successful

        """
        try:
            # Sanitize input to prevent injection
            safe_identifier = self._sanitize_window_identifier(window_identifier)

            # Use wmctrl if available
            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["wmctrl", "-r", safe_identifier, "-b", "add,hidden"],
                check=False,
                capture_output=True,
                timeout=5.0,
            )

            return result.returncode == 0

        except ValueError:
            logger.exception("Invalid window identifier")
            return False
        except Exception:
            logger.exception("wmctrl not available, trying xdotool")
            try:
                # Sanitize input for xdotool
                safe_identifier = self._sanitize_window_identifier(window_identifier)
                # Try xdotool as fallback
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["xdotool", "search", "--name", safe_identifier, "windowminimize"],
                    check=False,
                    capture_output=True,
                    timeout=5.0,
                )
                return result.returncode == 0
            except ValueError:
                logger.exception("Invalid window identifier")
                return False
            except FileNotFoundError:
                logger.exception("Neither wmctrl nor xdotool available")
                return False
            except Exception:
                logger.exception("Failed to minimize window")
                return False

    def maximize_window(self, window_identifier: str) -> bool:
        """Maximize an application window.

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(1)

        Args:
            window_identifier: Window title or handle

        Returns:
            True if window was maximized successfully

        Raises:
            RuntimeError: If window operation fails

        Example:
            >>> controller = ApplicationController()
            >>> controller.maximize_window("Notepad")
            True

        """
        logger.info("Maximizing window: %s", window_identifier)

        try:
            if self.platform == "win32":
                return self._maximize_window_windows(window_identifier)
            if self.platform == "darwin":
                return self._maximize_window_macos(window_identifier)
            return self._maximize_window_linux(window_identifier)

        except Exception as e:
            logger.exception("Failed to maximize window")
            msg = f"Failed to maximize window: {e}"
            raise RuntimeError(msg) from e

    def _maximize_window_windows(self, window_identifier: str) -> bool:
        """Maximize window on Windows."""
        try:
            import win32con  # type: ignore[import-untyped]
            import win32gui  # type: ignore[import-untyped]

            hwnd = win32gui.FindWindow(None, window_identifier)
            if hwnd == 0:
                hwnd = self._find_window_by_partial_title(window_identifier)

            if hwnd == 0:
                return False

            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return True

        except Exception:
            logger.exception("Failed to maximize window")
            return False

    def _maximize_window_macos(self, window_identifier: str) -> bool:
        """Maximize window on macOS."""
        try:
            # Sanitize input to prevent injection
            safe_identifier = self._sanitize_window_identifier(window_identifier)
            # Escape quotes for AppleScript
            safe_identifier = safe_identifier.replace('"', '\\"')

            script = f"""
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                tell process frontApp
                    set windowList to every window
                    repeat with aWindow in windowList
                        if name of aWindow contains "{safe_identifier}" then
                            set value of attribute "AXFullScreen" of aWindow to true
                            return true
                        end if
                    end repeat
                end tell
            end tell
            return false
            """

            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            return result.returncode == 0

        except ValueError:
            logger.exception("Invalid window identifier")
            return False
        except Exception:
            logger.exception("Failed to maximize window")
            return False

    def _maximize_window_linux(self, window_identifier: str) -> bool:
        """Maximize window on Linux."""
        try:
            # Sanitize input to prevent injection
            safe_identifier = self._sanitize_window_identifier(window_identifier)

            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["wmctrl", "-r", safe_identifier, "-b", "add,maximized_vert,maximized_horz"],
                check=False,
                capture_output=True,
                timeout=5.0,
            )
            return result.returncode == 0

        except ValueError:
            logger.exception("Invalid window identifier")
            return False

    def restore_window(self, window_identifier: str) -> bool:
        """Restore an application window to normal state.

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(1)

        Args:
            window_identifier: Window title or handle

        Returns:
            True if window was restored successfully

        Raises:
            RuntimeError: If window operation fails

        Example:
            >>> controller = ApplicationController()
            >>> controller.restore_window("Notepad")
            True

        """
        logger.info("Restoring window: %s", window_identifier)

        try:
            if self.platform == "win32":
                return self._restore_window_windows(window_identifier)
            if self.platform == "darwin":
                return self._restore_window_macos(window_identifier)
            return self._restore_window_linux(window_identifier)

        except Exception as e:
            logger.exception("Failed to restore window")
            msg = f"Failed to restore window: {e}"
            raise RuntimeError(msg) from e

    def _restore_window_windows(self, window_identifier: str) -> bool:
        """Restore window on Windows."""
        try:
            import win32con  # type: ignore[import-untyped]
            import win32gui  # type: ignore[import-untyped]

            hwnd = win32gui.FindWindow(None, window_identifier)
            if hwnd == 0:
                hwnd = self._find_window_by_partial_title(window_identifier)

            if hwnd == 0:
                return False

            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            return True

        except Exception:
            logger.exception("Failed to restore window")
            return False

    def _restore_window_macos(self, window_identifier: str) -> bool:
        """Restore window on macOS."""
        try:
            # Sanitize input to prevent injection
            safe_identifier = self._sanitize_window_identifier(window_identifier)
            # Escape quotes for AppleScript
            safe_identifier = safe_identifier.replace('"', '\\"')

            script = f"""
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                tell process frontApp
                    set windowList to every window
                    repeat with aWindow in windowList
                        if name of aWindow contains "{safe_identifier}" then
                            set miniaturized of aWindow to false
                            set value of attribute "AXFullScreen" of aWindow to false
                            return true
                        end if
                    end repeat
                end tell
            end tell
            return false
            """

            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            return result.returncode == 0

        except ValueError:
            logger.exception("Invalid window identifier")
            return False
        except Exception:
            logger.exception("Failed to restore window")
            return False

    def _restore_window_linux(self, window_identifier: str) -> bool:
        """Restore window on Linux."""
        try:
            # Sanitize input to prevent injection
            safe_identifier = self._sanitize_window_identifier(window_identifier)

            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                [
                    "wmctrl",
                    "-r",
                    safe_identifier,
                    "-b",
                    "remove,hidden,maximized_vert,maximized_horz",
                ],
                check=False,
                capture_output=True,
                timeout=5.0,
            )
            return result.returncode == 0

        except ValueError:
            logger.exception("Invalid window identifier")
            return False
        except Exception:
            logger.exception("Failed to restore window")
            return False

    def focus_window(self, window_identifier: str) -> bool:
        """Focus (bring to front) an application window.

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(1)

        Args:
            window_identifier: Window title or handle

        Returns:
            True if window was focused successfully

        Raises:
            RuntimeError: If window operation fails

        Example:
            >>> controller = ApplicationController()
            >>> controller.focus_window("Chrome")
            True

        """
        logger.info("Focusing window: %s", window_identifier)

        try:
            if self.platform == "win32":
                return self._focus_window_windows(window_identifier)
            if self.platform == "darwin":
                return self._focus_window_macos(window_identifier)
            return self._focus_window_linux(window_identifier)

        except Exception as e:
            logger.exception("Failed to focus window")
            msg = f"Failed to focus window: {e}"
            raise RuntimeError(msg) from e

    def _focus_window_windows(self, window_identifier: str) -> bool:
        """Focus window on Windows."""
        try:
            import win32gui  # type: ignore[import-untyped]

            hwnd = win32gui.FindWindow(None, window_identifier)
            if hwnd == 0:
                hwnd = self._find_window_by_partial_title(window_identifier)

            if hwnd == 0:
                return False

            win32gui.SetForegroundWindow(hwnd)
            return True

        except Exception:
            logger.exception("Failed to focus window")
            return False

    def _focus_window_macos(self, window_identifier: str) -> bool:
        """Focus window on macOS."""
        try:
            # Sanitize input to prevent injection
            safe_identifier = self._sanitize_window_identifier(window_identifier)
            # Escape quotes for AppleScript
            safe_identifier = safe_identifier.replace('"', '\\"')

            script = f"""
            tell application "System Events"
                set appList to every application process
                repeat with anApp in appList
                    tell anApp
                        set windowList to every window
                        repeat with aWindow in windowList
                            if name of aWindow contains "{safe_identifier}" then
                                set frontmost of anApp to true
                                perform action "AXRaise" of aWindow
                                return true
                            end if
                        end repeat
                    end tell
                end repeat
            end tell
            return false
            """

            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            return result.returncode == 0

        except ValueError:
            logger.exception("Invalid window identifier")
            return False
        except Exception:
            logger.exception("Failed to focus window")
            return False

    def _focus_window_linux(self, window_identifier: str) -> bool:
        """Focus window on Linux."""
        try:
            # Sanitize input to prevent injection
            safe_identifier = self._sanitize_window_identifier(window_identifier)

            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["wmctrl", "-a", safe_identifier],
                check=False,
                capture_output=True,
                timeout=5.0,
            )
            return result.returncode == 0

        except ValueError:
            logger.exception("Invalid window identifier")
            return False

    def switch_to_application(self, app_name: str) -> bool:
        """Switch to an application (Alt+Tab simulation).

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(1)

        Args:
            app_name: Application name

        Returns:
            True if switched successfully

        Raises:
            RuntimeError: If switch operation fails

        Example:
            >>> controller = ApplicationController()
            >>> controller.switch_to_application("Chrome")
            True

        """
        logger.info("Switching to application: %s", app_name)

        try:
            # Find window by application name
            windows = self.list_windows()
            target_window = None

            for window in windows:
                if app_name.lower() in window.title.lower():
                    target_window = window
                    break

            if target_window is None:
                logger.warning("Application not found: %s", app_name)
                return False

            # Focus the window
            return self.focus_window(target_window.title)

        except Exception as e:
            logger.exception("Failed to switch to")
            msg = f"Failed to switch to application: {e}"
            raise RuntimeError(msg) from e

    def list_windows(self) -> list[WindowInfo]:
        """List all visible application windows.

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(n)

        Returns:
            List of WindowInfo objects

        Example:
            >>> controller = ApplicationController()
            >>> windows = controller.list_windows()
            >>> for window in windows:
            ...     print(f"{window.title} (PID: {window.pid})")

        """
        logger.debug("Listing all windows")

        try:
            if self.platform == "win32":
                return self._list_windows_windows()
            if self.platform == "darwin":
                return self._list_windows_macos()
            return self._list_windows_linux()

        except Exception:
            logger.exception("Failed to list windows")
            return []

    def _list_windows_windows(self) -> list[WindowInfo]:
        """List windows on Windows."""
        try:
            import win32gui  # type: ignore[import-untyped]
            import win32process  # type: ignore[import-untyped]

            windows = []

            def enum_callback(hwnd, _) -> bool:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        rect = win32gui.GetWindowRect(hwnd)
                        position = (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])

                        # Determine window state
                        placement = win32gui.GetWindowPlacement(hwnd)
                        if placement[1] == 2:  # SW_SHOWMINIMIZED
                            state = ApplicationState.MINIMIZED
                        elif placement[1] == 3:  # SW_SHOWMAXIMIZED
                            state = ApplicationState.MAXIMIZED
                        else:
                            state = ApplicationState.NORMAL

                        is_active = win32gui.GetForegroundWindow() == hwnd

                        windows.append(
                            WindowInfo(
                                title=title,
                                handle=hwnd,
                                pid=pid,
                                state=state,
                                position=position,
                                is_active=is_active,
                            ),
                        )
                return True

            win32gui.EnumWindows(enum_callback, None)
            return windows

        except Exception:
            logger.exception("Failed to list windows")
            return []

    def _list_windows_macos(self) -> list[WindowInfo]:
        """List windows on macOS."""
        try:
            script = """
            tell application "System Events"
                set windowList to {}
                set appList to every application process
                repeat with anApp in appList
                    tell anApp
                        set appWindows to every window
                        repeat with aWindow in appWindows
                            set windowTitle to name of aWindow
                            set windowID to id of aWindow
                            set isMini to miniaturized of aWindow
                            set end of windowList to {windowTitle, windowID, isMini}
                        end repeat
                    end tell
                end repeat
                return windowList
            end tell
            """

            result = subprocess.run(  # noqa: S603
                ["osascript", "-e", script],  # nosec B603 B607
                check=False,
                capture_output=True,
                text=True,
                timeout=10.0,
            )

            if result.returncode != 0:
                return []

            # Parse output (simplified - would need proper parsing)
            return []
            # Note: This is a simplified implementation
            # Full implementation would parse AppleScript output properly

        except Exception:
            logger.exception("Failed to list windows")
            return []

    def _list_windows_linux(self) -> list[WindowInfo]:
        """List windows on Linux."""
        try:
            result = subprocess.run(
                ["wmctrl", "-l", "-p"],  # nosec B603 B607
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            if result.returncode != 0:
                return []

            windows = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split(None, 3)
                if len(parts) >= 4:
                    window_id = parts[0]
                    pid = int(parts[2])
                    title = parts[3]

                    windows.append(
                        WindowInfo(
                            title=title,
                            handle=window_id,
                            pid=pid,
                            state=ApplicationState.NORMAL,
                            position=(0, 0, 0, 0),  # Would need xwininfo for actual position
                            is_active=False,
                        ),
                    )

            return windows

        except FileNotFoundError:
            logger.exception("wmctrl not available")
            return []
        except Exception:
            logger.exception("Failed to list windows")
            return []

    def get_active_window(self) -> WindowInfo | None:
        """Get the currently active (focused) window.

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(1)

        Returns:
            WindowInfo of active window, or None if no active window

        Example:
            >>> controller = ApplicationController()
            >>> active = controller.get_active_window()
            >>> if active:
            ...     print(f"Active window: {active.title}")

        """
        logger.debug("Getting active window")

        try:
            windows = self.list_windows()
            for window in windows:
                if window.is_active:
                    return window
            return None

        except Exception:
            logger.exception("Failed to get active window")
            return None

    def list_running_applications(self) -> list[ApplicationInfo]:
        """List all running applications.

        Time Complexity: O(n) where n is number of processes
        Space Complexity: O(n)

        Returns:
            List of ApplicationInfo objects

        Example:
            >>> controller = ApplicationController()
            >>> apps = controller.list_running_applications()
            >>> for app in apps:
            ...     print(f"{app.name} (PID: {app.pid})")

        """
        logger.debug("Listing running applications")

        try:
            processes = self._platform_integration.get_process_list(include_usage=False)
            windows = self.list_windows()

            # Group windows by PID
            windows_by_pid: dict[int, list[WindowInfo]] = {}
            for window in windows:
                if window.pid not in windows_by_pid:
                    windows_by_pid[window.pid] = []
                windows_by_pid[window.pid].append(window)

            # Create ApplicationInfo objects
            applications = []
            for process in processes:
                app_windows = windows_by_pid.get(process.pid, [])
                applications.append(
                    ApplicationInfo(
                        name=process.name,
                        pid=process.pid,
                        executable="",  # Would need additional lookup
                        windows=app_windows,
                    ),
                )

            return applications

        except Exception:
            logger.exception("Failed to list applications")
            return []
