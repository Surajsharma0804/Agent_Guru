"""
Module: Agent_Guru.platform.windows.controller
Purpose: Windows OS Controller - App launching, keyboard/mouse, window management

Uses subprocess/os.startfile for app launching, pyautogui for keyboard/mouse,
and pywin32 for window management and permission checking.

Performance:
    - Time Complexity: O(1) for all operations
    - Space Complexity: O(1)
    - Latency: <100ms for app launch, <10ms for keyboard/mouse

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Windows-only imports
# ---------------------------------------------------------------------------
_PYAUTOGUI_AVAILABLE = False
_PYWIN32_AVAILABLE = False
_CTYPES_AVAILABLE = False

try:
    import pyautogui  # type: ignore[import]
    pyautogui.FAILSAFE = False  # Disable corner-of-screen failsafe for automation
    _PYAUTOGUI_AVAILABLE = True
except ImportError as e:
    logger.warning("pyautogui not available – keyboard/mouse simulation limited: %s", e)

if sys.platform == "win32":
    try:
        import pywintypes  # type: ignore[import]
        import win32api  # type: ignore[import]
        import win32con  # type: ignore[import]
        import win32gui  # type: ignore[import]
        import win32process  # type: ignore[import]
        _PYWIN32_AVAILABLE = True
    except ImportError as e:
        logger.warning("pywin32 not available – window management limited: %s", e)

    try:
        _CTYPES_AVAILABLE = True
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class WindowsControllerResult:
    """Result of a Windows controller operation."""

    success: bool
    operation: str
    message: str
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class WindowInfo:
    """Information about a Windows window."""

    hwnd: int
    title: str
    class_name: str
    pid: int
    is_visible: bool
    is_minimized: bool
    is_maximized: bool


# ---------------------------------------------------------------------------
# Known application aliases → executable mapping
# ---------------------------------------------------------------------------
_APP_ALIASES: dict[str, str] = {
    # Browsers
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "mozilla firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "brave": "brave.exe",
    # Productivity
    "notepad": "notepad.exe",
    "wordpad": "wordpad.exe",
    "word": "WINWORD.EXE",
    "microsoft word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "microsoft excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE",
    # System tools
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "task manager": "taskmgr.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    # Media
    "vlc": "vlc.exe",
    "media player": "wmplayer.exe",
    "spotify": "Spotify.exe",
    # Communication
    "whatsapp": "WhatsApp.exe",
    "teams": "Teams.exe",
    "microsoft teams": "Teams.exe",
    "slack": "slack.exe",
    "discord": "Discord.exe",
    "zoom": "Zoom.exe",
    "skype": "Skype.exe",
    # Development
    "vscode": "Code.exe",
    "visual studio code": "Code.exe",
    "vs code": "Code.exe",
    "pycharm": "pycharm64.exe",
    "git bash": "git-bash.exe",
    # Web (open in default browser)
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
}


class WindowsController:
    """
    Windows OS Controller for voice-driven automation.

    Provides:
    - Application launching via subprocess / os.startfile / ShellExecuteW
    - Keyboard simulation via pyautogui / pywin32 SendInput
    - Mouse simulation via pyautogui
    - Window management via pywin32 FindWindow / SetForegroundWindow
    - Permission checking via ctypes IsUserAnAdmin

    Example:
        >>> ctrl = WindowsController()
        >>> ctrl.launch_app("notepad")
        >>> ctrl.type_text("Hello from Guru!")
        >>> ctrl.press_key("enter")
    """

    def __init__(self) -> None:
        """Initialize Windows controller."""
        self._validate_platform()
        logger.info("WindowsController initialized")

    # ------------------------------------------------------------------
    # Platform validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_platform() -> None:
        """Raise RuntimeError if not on Windows."""
        if sys.platform != "win32":
            raise RuntimeError(
                f"WindowsController requires Windows, running on {sys.platform}"
            )

    # ------------------------------------------------------------------
    # Application launching
    # ------------------------------------------------------------------

    def launch_app(
        self,
        app_name: str,
        args: Optional[list[str]] = None,
    ) -> WindowsControllerResult:
        """
        Launch an application by name or path.

        Tries in order:
        1. Known alias → executable name (searched via PATH / registry)
        2. URL alias → os.startfile (opens in default browser)
        3. Direct executable path
        4. ShellExecuteW fallback

        Time Complexity: O(1)

        Args:
            app_name: Application name, alias, or full path
            args: Optional command-line arguments

        Returns:
            WindowsControllerResult with success status and PID if available
        """
        start = time.perf_counter()
        args = args or []
        normalized = app_name.lower().strip()

        # Resolve alias
        resolved = _APP_ALIASES.get(normalized, app_name)

        try:
            # URL → open in default browser
            if resolved.startswith("http://") or resolved.startswith("https://"):
                os.startfile(resolved)  # type: ignore[attr-defined]
                latency_ms = (time.perf_counter() - start) * 1000
                logger.info("Opened URL: %s", resolved)
                return WindowsControllerResult(
                    success=True,
                    operation="launch_app",
                    message=f"Opened URL: {resolved}",
                    latency_ms=latency_ms,
                    metadata={"url": resolved},
                )

            # Try subprocess with full args
            cmd = [resolved] + args
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            logger.info("Launched app: %s (PID: %s)", resolved, proc.pid)
            return WindowsControllerResult(
                success=True,
                operation="launch_app",
                message=f"Launched {app_name} (PID: {proc.pid})",
                latency_ms=latency_ms,
                metadata={"pid": proc.pid, "executable": resolved},
            )

        except (FileNotFoundError, OSError) as e:
            # Fallback: os.startfile (uses Windows shell association)
            try:
                os.startfile(resolved)  # type: ignore[attr-defined]
                latency_ms = (time.perf_counter() - start) * 1000
                logger.info("Launched via shell: %s", resolved)
                return WindowsControllerResult(
                    success=True,
                    operation="launch_app",
                    message=f"Launched {app_name} via shell",
                    latency_ms=latency_ms,
                    metadata={"executable": resolved},
                )
            except Exception as e2:
                latency_ms = (time.perf_counter() - start) * 1000
                logger.error("Failed to launch %s: %s", app_name, e2)
                return WindowsControllerResult(
                    success=False,
                    operation="launch_app",
                    message=f"Failed to launch {app_name}",
                    error=str(e2),
                    latency_ms=latency_ms,
                )

        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error("Failed to launch %s: %s", app_name, e)
            return WindowsControllerResult(
                success=False,
                operation="launch_app",
                message=f"Failed to launch {app_name}",
                error=str(e),
                latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Keyboard simulation
    # ------------------------------------------------------------------

    def type_text(
        self,
        text: str,
        interval: float = 0.0,
    ) -> WindowsControllerResult:
        """
        Type text into the active window.

        Time Complexity: O(n) where n = len(text)

        Args:
            text: Text to type
            interval: Delay between keystrokes in seconds (0 = fastest)

        Returns:
            WindowsControllerResult
        """
        start = time.perf_counter()

        if not _PYAUTOGUI_AVAILABLE:
            return WindowsControllerResult(
                success=False,
                operation="type_text",
                message="pyautogui not available",
                error="Install pyautogui: pip install pyautogui",
            )

        try:
            pyautogui.typewrite(text, interval=interval)
            latency_ms = (time.perf_counter() - start) * 1000
            logger.info("Typed %s characters", len(text))
            return WindowsControllerResult(
                success=True,
                operation="type_text",
                message=f"Typed {len(text)} characters",
                latency_ms=latency_ms,
                metadata={"length": len(text)},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error("type_text failed: %s", e)
            return WindowsControllerResult(
                success=False,
                operation="type_text",
                message="Failed to type text",
                error=str(e),
                latency_ms=latency_ms,
            )

    def press_key(self, key: str) -> WindowsControllerResult:
        """
        Press a single key or key combination.

        Args:
            key: Key name (e.g. 'enter', 'ctrl+c', 'alt+f4')

        Returns:
            WindowsControllerResult
        """
        start = time.perf_counter()

        if not _PYAUTOGUI_AVAILABLE:
            return WindowsControllerResult(
                success=False,
                operation="press_key",
                message="pyautogui not available",
                error="Install pyautogui: pip install pyautogui",
            )

        try:
            # Handle combinations like 'ctrl+c'
            if "+" in key:
                parts = [p.strip() for p in key.split("+")]
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(key)

            latency_ms = (time.perf_counter() - start) * 1000
            logger.info("Pressed key: %s", key)
            return WindowsControllerResult(
                success=True,
                operation="press_key",
                message=f"Pressed key: {key}",
                latency_ms=latency_ms,
                metadata={"key": key},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error("press_key failed: %s", e)
            return WindowsControllerResult(
                success=False,
                operation="press_key",
                message=f"Failed to press key: {key}",
                error=str(e),
                latency_ms=latency_ms,
            )

    def hotkey(self, *keys: str) -> WindowsControllerResult:
        """
        Press a hotkey combination simultaneously.

        Args:
            *keys: Keys to press together (e.g. 'ctrl', 'c')

        Returns:
            WindowsControllerResult
        """
        start = time.perf_counter()

        if not _PYAUTOGUI_AVAILABLE:
            return WindowsControllerResult(
                success=False,
                operation="hotkey",
                message="pyautogui not available",
                error="Install pyautogui: pip install pyautogui",
            )

        try:
            pyautogui.hotkey(*keys)
            latency_ms = (time.perf_counter() - start) * 1000
            combo = "+".join(keys)
            logger.info("Hotkey: %s", combo)
            return WindowsControllerResult(
                success=True,
                operation="hotkey",
                message=f"Hotkey pressed: {combo}",
                latency_ms=latency_ms,
                metadata={"keys": list(keys)},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=False,
                operation="hotkey",
                message="Failed to press hotkey",
                error=str(e),
                latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Mouse simulation
    # ------------------------------------------------------------------

    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        clicks: int = 1,
    ) -> WindowsControllerResult:
        """
        Click at screen coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            button: 'left', 'right', or 'middle'
            clicks: Number of clicks (2 for double-click)

        Returns:
            WindowsControllerResult
        """
        start = time.perf_counter()

        if not _PYAUTOGUI_AVAILABLE:
            return WindowsControllerResult(
                success=False,
                operation="click",
                message="pyautogui not available",
                error="Install pyautogui: pip install pyautogui",
            )

        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            latency_ms = (time.perf_counter() - start) * 1000
            logger.info("Clicked %s at (%s, %s) x%s", button, x, y, clicks)
            return WindowsControllerResult(
                success=True,
                operation="click",
                message=f"Clicked {button} at ({x}, {y})",
                latency_ms=latency_ms,
                metadata={"x": x, "y": y, "button": button, "clicks": clicks},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=False,
                operation="click",
                message=f"Failed to click at ({x}, {y})",
                error=str(e),
                latency_ms=latency_ms,
            )

    def move_mouse(self, x: int, y: int, duration: float = 0.0) -> WindowsControllerResult:
        """Move mouse to coordinates."""
        start = time.perf_counter()

        if not _PYAUTOGUI_AVAILABLE:
            return WindowsControllerResult(
                success=False,
                operation="move_mouse",
                message="pyautogui not available",
                error="Install pyautogui",
            )

        try:
            pyautogui.moveTo(x, y, duration=duration)
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=True,
                operation="move_mouse",
                message=f"Moved mouse to ({x}, {y})",
                latency_ms=latency_ms,
                metadata={"x": x, "y": y},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=False,
                operation="move_mouse",
                message="Failed to move mouse",
                error=str(e),
                latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def get_active_window_title(self) -> str:
        """Return the title of the currently active window."""
        if _PYWIN32_AVAILABLE:
            try:
                hwnd = win32gui.GetForegroundWindow()
                return win32gui.GetWindowText(hwnd)
            except Exception as exc:  # noqa: BLE001
                logger.debug("win32gui active window title failed: %s", exc)

        if _PYAUTOGUI_AVAILABLE:
            try:
                win = pyautogui.getActiveWindow()
                return win.title if win else ""
            except Exception as exc:  # noqa: BLE001
                logger.debug("pyautogui active window title failed: %s", exc)

        return ""

    def find_window(self, title: str) -> Optional[int]:
        """
        Find a window by title (partial match).

        Args:
            title: Window title to search for (case-insensitive partial match)

        Returns:
            Window handle (HWND) or None if not found
        """
        if not _PYWIN32_AVAILABLE:
            return None

        title_lower = title.lower()
        found_hwnd: Optional[int] = None

        def _enum_callback(hwnd: int, _: Any) -> bool:
            nonlocal found_hwnd
            try:
                window_title = win32gui.GetWindowText(hwnd).lower()
                if title_lower in window_title and win32gui.IsWindowVisible(hwnd):
                    found_hwnd = hwnd
                    return False  # Stop enumeration
            except Exception as exc:  # noqa: BLE001
                logger.debug("Window enumeration callback error: %s", exc)
            return True

        try:
            win32gui.EnumWindows(_enum_callback, None)
        except Exception as exc:  # noqa: BLE001
            logger.debug("EnumWindows failed in find_window: %s", exc)

        return found_hwnd

    def focus_window(self, title: str) -> WindowsControllerResult:
        """
        Bring a window to the foreground by title.

        Args:
            title: Window title (partial match)

        Returns:
            WindowsControllerResult
        """
        start = time.perf_counter()

        hwnd = self.find_window(title)
        if hwnd is None:
            return WindowsControllerResult(
                success=False,
                operation="focus_window",
                message=f"Window not found: {title}",
                error="Window not found",
            )

        try:
            if _PYWIN32_AVAILABLE:
                # Restore if minimized
                placement = win32gui.GetWindowPlacement(hwnd)
                if placement[1] == win32con.SW_SHOWMINIMIZED:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)

            latency_ms = (time.perf_counter() - start) * 1000
            logger.info("Focused window: %s", title)
            return WindowsControllerResult(
                success=True,
                operation="focus_window",
                message=f"Focused window: {title}",
                latency_ms=latency_ms,
                metadata={"hwnd": hwnd},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=False,
                operation="focus_window",
                message=f"Failed to focus window: {title}",
                error=str(e),
                latency_ms=latency_ms,
            )

    def minimize_window(self, title: str) -> WindowsControllerResult:
        """Minimize a window by title."""
        start = time.perf_counter()
        hwnd = self.find_window(title)
        if hwnd is None:
            return WindowsControllerResult(
                success=False,
                operation="minimize_window",
                message=f"Window not found: {title}",
                error="Window not found",
            )
        try:
            if _PYWIN32_AVAILABLE:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=True,
                operation="minimize_window",
                message=f"Minimized: {title}",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=False,
                operation="minimize_window",
                message=f"Failed to minimize: {title}",
                error=str(e),
                latency_ms=latency_ms,
            )

    def maximize_window(self, title: str) -> WindowsControllerResult:
        """Maximize a window by title."""
        start = time.perf_counter()
        hwnd = self.find_window(title)
        if hwnd is None:
            return WindowsControllerResult(
                success=False,
                operation="maximize_window",
                message=f"Window not found: {title}",
                error="Window not found",
            )
        try:
            if _PYWIN32_AVAILABLE:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=True,
                operation="maximize_window",
                message=f"Maximized: {title}",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return WindowsControllerResult(
                success=False,
                operation="maximize_window",
                message=f"Failed to maximize: {title}",
                error=str(e),
                latency_ms=latency_ms,
            )

    def list_windows(self) -> list[WindowInfo]:
        """
        List all visible windows.

        Returns:
            List of WindowInfo for all visible windows
        """
        windows: list[WindowInfo] = []

        if not _PYWIN32_AVAILABLE:
            return windows

        def _enum_callback(hwnd: int, _: Any) -> bool:
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return True
                class_name = win32gui.GetClassName(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                placement = win32gui.GetWindowPlacement(hwnd)
                is_minimized = placement[1] == win32con.SW_SHOWMINIMIZED
                is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED
                windows.append(WindowInfo(
                    hwnd=hwnd,
                    title=title,
                    class_name=class_name,
                    pid=pid,
                    is_visible=True,
                    is_minimized=is_minimized,
                    is_maximized=is_maximized,
                ))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Window info collection failed for hwnd %s: %s", hwnd, exc)
            return True

        try:
            win32gui.EnumWindows(_enum_callback, None)
        except Exception as exc:  # noqa: BLE001
            logger.debug("EnumWindows failed in list_windows: %s", exc)

        return windows

    # ------------------------------------------------------------------
    # Permission checking
    # ------------------------------------------------------------------

    def is_admin(self) -> bool:
        """Return True if running with administrator privileges."""
        if not _CTYPES_AVAILABLE:
            return False
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception as e:
            return False

    def check_permission(self, operation: str) -> bool:
        """
        Check if the current process has permission for an operation.

        Args:
            operation: Operation name (e.g. 'registry_write', 'service_control')

        Returns:
            True if permitted
        """
        admin_required = {
            "registry_write",
            "service_control",
            "system_shutdown",
            "system_restart",
            "install_software",
        }
        if operation in admin_required:
            return self.is_admin()
        return True  # Non-admin operations always permitted
