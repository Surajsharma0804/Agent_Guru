"""Module: Agent_Guru.platform.windows.controller
Purpose: Windows OS Controller - App launching, keyboard/mouse, window management.

Uses subprocess/os.startfile for app launching, pyautogui for keyboard/mouse,
and pywin32 for window management and permission checking.

Performance:
    - Time Complexity: O(1) for launching, focusing, and single key/click
      operations; O(n) for type_text where n = len(text) (one keystroke
      event per character via pyautogui)
    - Space Complexity: O(1) for all operations except list_windows, which
      is O(w) where w = number of visible windows
    - Latency: <100ms for app launch, <10ms for a single keyboard/mouse event

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess  # nosec B404
import sys
import time
from dataclasses import dataclass, field
from typing import Any

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
except ImportError:
    # Expected on non-Windows dev/CI machines (this import runs unconditionally
    # at module load, regardless of platform) and whenever the optional
    # dependency simply isn't installed - not an application error, so this
    # should not log a full ERROR-level traceback via logger.exception().
    logger.debug("pyautogui not available - keyboard/mouse simulation limited")
if sys.platform == "win32":
    try:
        import pywintypes  # type: ignore[import]  # noqa: F401
        import win32api  # type: ignore[import]  # noqa: F401
        import win32con  # type: ignore[import]
        import win32gui  # type: ignore[import]
        import win32process  # type: ignore[import]

        _PYWIN32_AVAILABLE = True
    except ImportError:
        logger.warning("pywin32 not available - window management limited")
    with contextlib.suppress(ImportError):
        import ctypes  # noqa: F401

        _CTYPES_AVAILABLE = True


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WindowsControllerResult:
    """Result of a Windows controller operation."""

    success: bool
    operation: str
    message: str
    error: str | None = None
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
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "mozilla firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "brave": "brave.exe",
    "notepad": "notepad.exe",
    "wordpad": "wordpad.exe",
    "word": "WINWORD.EXE",
    "microsoft word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "microsoft excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE",
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
    "vlc": "vlc.exe",
    "media player": "wmplayer.exe",
    "spotify": "Spotify.exe",
    "whatsapp": "WhatsApp.exe",
    "teams": "Teams.exe",
    "microsoft teams": "Teams.exe",
    "slack": "slack.exe",
    "discord": "Discord.exe",
    "zoom": "Zoom.exe",
    "skype": "Skype.exe",
    "vscode": "Code.exe",
    "visual studio code": "Code.exe",
    "vs code": "Code.exe",
    "pycharm": "pycharm64.exe",
    "git bash": "git-bash.exe",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
}


class WindowsController:
    """Windows OS Controller for voice-driven automation."""

    def __init__(self) -> None:
        """Initialize Windows controller."""
        self._validate_platform()
        logger.info("WindowsController initialized")

    @staticmethod
    def _validate_platform() -> None:
        """Raise RuntimeError if not on Windows."""
        if sys.platform != "win32":
            msg = f"WindowsController requires Windows, running on {sys.platform}"
            raise RuntimeError(msg)

    def launch_app(
        self,
        app_name: str,
        args: list[str] | None = None,
    ) -> WindowsControllerResult:
        """Launch an application by name or path."""
        start = time.perf_counter()
        args = args or []
        normalized = app_name.lower().strip()

        resolved = _APP_ALIASES.get(normalized, app_name)

        try:
            if resolved.startswith(("http://", "https://")):
                os.startfile(resolved)  # type: ignore[attr-defined]  # nosec B606
                latency_ms = (time.perf_counter() - start) * 1000
                logger.info("Opened URL: %s", resolved)
                return WindowsControllerResult(
                    success=True,
                    operation="launch_app",
                    message=f"Opened URL: {resolved}",
                    latency_ms=latency_ms,
                    metadata={"url": resolved},
                )

            cmd = [resolved, *args]
            proc = subprocess.Popen(  # nosec B603  # noqa: S603
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
            # Log the ORIGINAL failure before attempting the shell fallback -
            # previously this exception variable was bound but never used
            # (confirmed by ruff F841) after an earlier dead-code cleanup,
            # meaning the real reason the primary launch attempt failed was
            # silently discarded; only the fallback's own exception (e2)
            # ever reached the logs on ultimate failure.
            logger.debug(
                "Primary launch of %s failed (%s) - trying shell fallback",
                app_name,
                e,
            )
            try:
                os.startfile(resolved)  # type: ignore[attr-defined]  # nosec B606
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
                logger.exception("Failed to launch %s via shell", app_name)
                return WindowsControllerResult(
                    success=False,
                    operation="launch_app",
                    message=f"Failed to launch {app_name}",
                    error=str(e2),
                    latency_ms=latency_ms,
                )

    def type_text(
        self,
        text: str,
        interval: float = 0.0,
    ) -> WindowsControllerResult:
        """Type text into the active window."""
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
            logger.exception("type_text failed")
            return WindowsControllerResult(
                success=False,
                operation="type_text",
                message="Failed to type text",
                error=str(e),
                latency_ms=latency_ms,
            )

    def press_key(self, key: str) -> WindowsControllerResult:
        """Press a single key or key combination."""
        start = time.perf_counter()

        if not _PYAUTOGUI_AVAILABLE:
            return WindowsControllerResult(
                success=False,
                operation="press_key",
                message="pyautogui not available",
                error="Install pyautogui: pip install pyautogui",
            )

        try:
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
            logger.exception("press_key failed")
            return WindowsControllerResult(
                success=False,
                operation="press_key",
                message=f"Failed to press key: {key}",
                error=str(e),
                latency_ms=latency_ms,
            )

    def hotkey(self, *keys: str) -> WindowsControllerResult:
        """Press a hotkey combination simultaneously."""
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

    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        clicks: int = 1,
    ) -> WindowsControllerResult:
        """Click at screen coordinates."""
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

    def move_mouse(
        self, x: int, y: int, duration: float = 0.0
    ) -> WindowsControllerResult:
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

    def get_active_window_title(self) -> str:
        """Return the title of the currently active window."""
        if _PYWIN32_AVAILABLE:
            try:
                hwnd = win32gui.GetForegroundWindow()
                return win32gui.GetWindowText(hwnd)
            except Exception as exc:
                logger.debug("win32gui active window title failed: %s", exc)
        if _PYAUTOGUI_AVAILABLE:
            try:
                win = pyautogui.getActiveWindow()
                return win.title if win else ""
            except Exception as exc:
                logger.debug("pyautogui active window title failed: %s", exc)
        return ""

    def find_window(self, title: str) -> int | None:
        """Find a window by title (partial match)."""
        if not _PYWIN32_AVAILABLE:
            return None

        title_lower = title.lower()
        found_hwnd: int | None = None

        def _enum_callback(hwnd: int, _: Any) -> bool:
            nonlocal found_hwnd
            try:
                window_title = win32gui.GetWindowText(hwnd).lower()
                if title_lower in window_title and win32gui.IsWindowVisible(hwnd):
                    found_hwnd = hwnd
                    return False
            except Exception as exc:
                logger.debug("Window enumeration callback error: %s", exc)
            return True

        try:
            win32gui.EnumWindows(_enum_callback, None)
        except Exception as exc:
            logger.debug("EnumWindows failed in find_window: %s", exc)
        return found_hwnd

    def focus_window(self, title: str) -> WindowsControllerResult:
        """Bring a window to the foreground by title."""
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
        """List all visible windows."""
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
                windows.append(
                    WindowInfo(
                        hwnd=hwnd,
                        title=title,
                        class_name=class_name,
                        pid=pid,
                        is_visible=True,
                        is_minimized=is_minimized,
                        is_maximized=is_maximized,
                    ),
                )
            except Exception as exc:
                logger.debug("Window info collection failed for hwnd %s: %s", hwnd, exc)
            return True

        try:
            win32gui.EnumWindows(_enum_callback, None)
        except Exception as exc:
            logger.debug("EnumWindows failed in list_windows: %s", exc)
        return windows

    def is_admin(self) -> bool:
        """Return True if running with administrator privileges."""
        if not _CTYPES_AVAILABLE:
            return False
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def check_permission(self, operation: str) -> bool:
        """Check if the current process has permission for an operation."""
        admin_required = {
            "registry_write",
            "service_control",
            "system_shutdown",
            "system_restart",
            "install_software",
        }
        if operation in admin_required:
            return self.is_admin()
        return True
