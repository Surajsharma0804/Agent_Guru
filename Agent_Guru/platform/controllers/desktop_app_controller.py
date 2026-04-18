"""Desktop application controller for Agent Guru.

Provides async application lifecycle management (open, close, minimize,
maximize, restore, switch) across Windows, macOS, and Linux.

Platform support:
    - Windows: subprocess + pyautogui + win32api (graceful fallback)
    - macOS:   subprocess ``open`` command + AppleScript via osascript
    - Linux:   xdg-open + wmctrl (graceful fallback if wmctrl unavailable)

Design Decisions:
    - All public methods are async (asyncio.create_subprocess_exec for I/O)
    - Returns True on success, False on failure — never raises for normal failures
    - Fuzzy app name matching: case-insensitive, partial match
    - Raises RuntimeError only on mobile platforms (android/ios) where
      desktop control is not applicable

Performance Characteristics:
    - Time Complexity: O(n) for fuzzy matching where n = len(app_name)
    - Space Complexity: O(1) per operation
    - Latency: <2 seconds for app launch (target)

Author: Agent Guru Team
Date: 2026-03-20
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from Agent_Guru.platform.platform_detector import PlatformDetector
from Agent_Guru.platform.utils import fuzzy_match as _fuzzy_match

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Thin wrapper — delegates to canonical PlatformDetector."""
    return PlatformDetector.detect().os_name.lower()


def _is_desktop(plat: str) -> bool:
    """Return True if *plat* is a desktop platform."""
    return plat in ("windows", "macos", "linux", "unknown")


def _is_mobile(plat: str) -> bool:
    """Return True if *plat* is a mobile platform."""
    return plat in ("android", "ios")


# ---------------------------------------------------------------------------
# DesktopApplicationController
# ---------------------------------------------------------------------------

class DesktopApplicationController:
    """Async controller for desktop application lifecycle management.

    Supports Windows, macOS, and Linux.  Raises :class:`RuntimeError` when
    instantiated on Android or iOS.

    Example::

        controller = DesktopApplicationController()
        await controller.initialize()

        opened = await controller.open_app("notepad")
        minimized = await controller.minimize_app("notepad")
        await controller.shutdown()

    All action methods return ``True`` on success and ``False`` on failure.
    They never raise exceptions for normal operational failures.
    """

    def __init__(self, platform_override: Optional[str] = None) -> None:
        """Create the controller.

        Args:
            platform_override: Force a specific platform string (for testing).
                When ``None`` the platform is auto-detected.

        Raises:
            RuntimeError: If the detected platform is ``"android"`` or ``"ios"``.
        """
        self._platform: str = platform_override or _detect_platform()
        self._initialized: bool = False

        if _is_mobile(self._platform):
            raise RuntimeError(
                f"DesktopApplicationController is not supported on mobile "
                f"platform '{self._platform}'. Use MobileApplicationController instead."
            )

        logger.info(
            "DesktopApplicationController created — platform=%s", self._platform
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the controller.

        Idempotent — safe to call multiple times.
        """
        if self._initialized:
            logger.debug("DesktopApplicationController already initialized")
            return

        self._initialized = True
        logger.info(
            "DesktopApplicationController initialized — platform=%s", self._platform
        )

    async def shutdown(self) -> None:
        """Shut down the controller and release resources."""
        self._initialized = False
        logger.info("DesktopApplicationController shut down")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def open_app(self, app_name: str) -> bool:
        """Launch an application by name.

        Args:
            app_name: Application name (fuzzy matched).

        Returns:
            ``True`` if the launch command succeeded, ``False`` otherwise.
        """
        if not app_name or not app_name.strip():
            logger.warning("open_app called with empty app_name")
            return False

        logger.info("open_app: %r (platform=%s)", app_name, self._platform)
        try:
            if self._platform == "windows":
                return await self._open_windows(app_name)
            elif self._platform == "macos":
                return await self._open_macos(app_name)
            else:  # linux / unknown
                return await self._open_linux(app_name)
        except Exception as exc:
            logger.error("open_app(%r) failed: %s", app_name, exc)
            return False

    async def close_app(self, app_name: str) -> bool:
        """Terminate an application by name.

        Args:
            app_name: Application name (fuzzy matched against running processes).

        Returns:
            ``True`` if at least one matching process was terminated.
        """
        if not app_name or not app_name.strip():
            logger.warning("close_app called with empty app_name")
            return False

        logger.info("close_app: %r (platform=%s)", app_name, self._platform)
        try:
            if self._platform == "windows":
                return await self._close_windows(app_name)
            elif self._platform == "macos":
                return await self._close_macos(app_name)
            else:
                return await self._close_linux(app_name)
        except Exception as exc:
            logger.error("close_app(%r) failed: %s", app_name, exc)
            return False

    async def minimize_app(self, app_name: str) -> bool:
        """Minimize the window of an application.

        Args:
            app_name: Application name (fuzzy matched).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        if not app_name or not app_name.strip():
            return False

        logger.info("minimize_app: %r (platform=%s)", app_name, self._platform)
        try:
            if self._platform == "windows":
                return await self._minimize_windows(app_name)
            elif self._platform == "macos":
                return await self._minimize_macos(app_name)
            else:
                return await self._minimize_linux(app_name)
        except Exception as exc:
            logger.error("minimize_app(%r) failed: %s", app_name, exc)
            return False

    async def maximize_app(self, app_name: str) -> bool:
        """Maximize the window of an application.

        Args:
            app_name: Application name (fuzzy matched).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        if not app_name or not app_name.strip():
            return False

        logger.info("maximize_app: %r (platform=%s)", app_name, self._platform)
        try:
            if self._platform == "windows":
                return await self._maximize_windows(app_name)
            elif self._platform == "macos":
                return await self._maximize_macos(app_name)
            else:
                return await self._maximize_linux(app_name)
        except Exception as exc:
            logger.error("maximize_app(%r) failed: %s", app_name, exc)
            return False

    async def restore_app(self, app_name: str) -> bool:
        """Restore a minimized/maximized application to its normal state.

        Args:
            app_name: Application name (fuzzy matched).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        if not app_name or not app_name.strip():
            return False

        logger.info("restore_app: %r (platform=%s)", app_name, self._platform)
        try:
            if self._platform == "windows":
                return await self._restore_windows(app_name)
            elif self._platform == "macos":
                return await self._restore_macos(app_name)
            else:
                return await self._restore_linux(app_name)
        except Exception as exc:
            logger.error("restore_app(%r) failed: %s", app_name, exc)
            return False

    async def switch_app(self, app_name: str) -> bool:
        """Switch focus to an application (Alt+Tab equivalent).

        Args:
            app_name: Application name (fuzzy matched).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        if not app_name or not app_name.strip():
            return False

        logger.info("switch_app: %r (platform=%s)", app_name, self._platform)
        try:
            if self._platform == "windows":
                return await self._switch_windows(app_name)
            elif self._platform == "macos":
                return await self._switch_macos(app_name)
            else:
                return await self._switch_linux(app_name)
        except Exception as exc:
            logger.error("switch_app(%r) failed: %s", app_name, exc)
            return False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform(self) -> str:
        """Current platform identifier."""
        return self._platform

    @property
    def is_initialized(self) -> bool:
        """Whether the controller has been initialized."""
        return self._initialized

    # ------------------------------------------------------------------
    # Windows implementations
    # ------------------------------------------------------------------

    async def _open_windows(self, app_name: str) -> bool:
        """Launch an application on Windows."""
        # Try os.startfile first (handles .exe, registered apps, documents)
        try:
            import os  # noqa: PLC0415
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, os.startfile, app_name
            )
            return True
        except (OSError, FileNotFoundError, RuntimeError) as exc:
            logger.debug("os.startfile failed for %r: %s", app_name, exc)
        except Exception as exc:
            logger.warning("Unexpected error in os.startfile for %r: %s", app_name, exc)

        # Fallback: shell start command
        try:
            proc = await asyncio.create_subprocess_exec(
                "cmd", "/c", "start", "", app_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return True
        except Exception as exc:
            logger.debug("Windows shell start failed for %r: %s", app_name, exc)
            return False

    async def _close_windows(self, app_name: str) -> bool:
        """Terminate an application on Windows."""
        # Try graceful close via win32api first
        closed = await self._close_windows_win32(app_name)
        if closed:
            return True

        # Fallback: taskkill
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "taskkill", "/F", "/IM", f"{app_name}.exe",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("taskkill failed for %r: %s", app_name, exc)
            return False

    async def _close_windows_win32(self, app_name: str) -> bool:
        """Graceful close via win32api (optional dependency)."""
        try:
            import win32con  # type: ignore[import]
            import win32gui  # type: ignore[import]

            hwnd = self._find_window_win32(app_name)
            if hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
            return False
        except ImportError as e:
            logger.debug("win32gui not available — skipping graceful close: %s", e)
            return False
        except Exception as exc:
            logger.debug("win32 close failed: %s", exc)
            return False

    def _find_window_win32(self, app_name: str) -> Optional[int]:
        """Find a window handle by fuzzy app name match."""
        try:
            import win32gui  # type: ignore[import]

            found: list[int] = []

            def _enum_cb(hwnd: int, _: object) -> None:
                title = win32gui.GetWindowText(hwnd)
                if title and _fuzzy_match(app_name, title):
                    found.append(hwnd)

            win32gui.EnumWindows(_enum_cb, None)
            return found[0] if found else None
        except Exception as e:
            return None

    async def _minimize_windows(self, app_name: str) -> bool:
        """Minimize a window on Windows."""
        # Try win32api
        try:
            import win32con  # type: ignore[import]
            import win32gui  # type: ignore[import]

            hwnd = self._find_window_win32(app_name)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                return True
        except ImportError as e:
            pass
        except Exception as exc:
            logger.debug("win32 minimize failed: %s", exc)

        # Fallback: pyautogui
        return await self._pyautogui_window_op(app_name, "minimize")

    async def _maximize_windows(self, app_name: str) -> bool:
        """Maximize a window on Windows."""
        try:
            import win32con  # type: ignore[import]
            import win32gui  # type: ignore[import]

            hwnd = self._find_window_win32(app_name)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                return True
        except ImportError as e:
            pass
        except Exception as exc:
            logger.debug("win32 maximize failed: %s", exc)

        return await self._pyautogui_window_op(app_name, "maximize")

    async def _restore_windows(self, app_name: str) -> bool:
        """Restore a window on Windows."""
        try:
            import win32con  # type: ignore[import]
            import win32gui  # type: ignore[import]

            hwnd = self._find_window_win32(app_name)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                return True
        except ImportError as e:
            pass
        except Exception as exc:
            logger.debug("win32 restore failed: %s", exc)

        return await self._pyautogui_window_op(app_name, "restore")

    async def _switch_windows(self, app_name: str) -> bool:
        """Switch focus to a window on Windows."""
        try:
            import win32gui  # type: ignore[import]

            hwnd = self._find_window_win32(app_name)
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
                return True
        except ImportError as e:
            pass
        except Exception as exc:
            logger.debug("win32 switch failed: %s", exc)

        return await self._pyautogui_window_op(app_name, "activate")

    async def _pyautogui_window_op(self, app_name: str, op: str) -> bool:
        """Perform a window operation via pyautogui (Windows fallback)."""
        try:
            import pyautogui  # type: ignore[import]

            windows = pyautogui.getAllWindows()  # type: ignore[attr-defined]
            for win in windows:
                if _fuzzy_match(app_name, win.title):
                    if op == "minimize":
                        win.minimize()
                    elif op == "maximize":
                        win.maximize()
                    elif op == "restore":
                        win.restore()
                    elif op == "activate":
                        win.activate()
                    return True
            return False
        except Exception as exc:
            logger.debug("pyautogui %s failed for %r: %s", op, app_name, exc)
            return False

    # ------------------------------------------------------------------
    # macOS implementations
    # ------------------------------------------------------------------

    async def _open_macos(self, app_name: str) -> bool:
        """Launch an application on macOS using ``open -a``."""
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "open", "-a", app_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("open -a failed for %r: %s", app_name, exc)
            return False

    async def _close_macos(self, app_name: str) -> bool:
        """Terminate an application on macOS via AppleScript."""
        script = f'tell application "{app_name}" to quit'
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "osascript", "-e", script,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("osascript quit failed for %r: %s", app_name, exc)
            return False

    async def _minimize_macos(self, app_name: str) -> bool:
        """Minimize a window on macOS via AppleScript."""
        script = (
            f'tell application "{app_name}" to set miniaturized of '
            f'front window to true'
        )
        return await self._run_osascript(script, app_name, "minimize")

    async def _maximize_macos(self, app_name: str) -> bool:
        """Maximize (zoom) a window on macOS via AppleScript."""
        script = (
            f'tell application "System Events" to tell process "{app_name}" '
            f'to set value of attribute "AXFullScreen" of window 1 to true'
        )
        return await self._run_osascript(script, app_name, "maximize")

    async def _restore_macos(self, app_name: str) -> bool:
        """Restore a window on macOS via AppleScript."""
        # Un-miniaturize and un-fullscreen
        script = (
            f'tell application "{app_name}" to set miniaturized of '
            f'front window to false'
        )
        return await self._run_osascript(script, app_name, "restore")

    async def _switch_macos(self, app_name: str) -> bool:
        """Switch focus to an application on macOS via AppleScript."""
        script = f'tell application "{app_name}" to activate'
        return await self._run_osascript(script, app_name, "switch")

    async def _run_osascript(self, script: str, app_name: str, op: str) -> bool:
        """Run an AppleScript and return True on success."""
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "osascript", "-e", script,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("osascript %s failed for %r: %s", op, app_name, exc)
            return False

    # ------------------------------------------------------------------
    # Linux implementations
    # ------------------------------------------------------------------

    async def _open_linux(self, app_name: str) -> bool:
        """Launch an application on Linux."""
        # Try direct executable first
        try:
            await asyncio.create_subprocess_exec(
                app_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            # Don't wait — detach the process
            return True
        except FileNotFoundError as e:
            pass
        except Exception as exc:
            logger.debug("Direct exec failed for %r: %s", app_name, exc)

        # Fallback: xdg-open
        try:
            await asyncio.create_subprocess_exec(  # nosec B603 B607
                "xdg-open", app_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            return True
        except Exception as exc:
            logger.debug("xdg-open failed for %r: %s", app_name, exc)
            return False

    async def _close_linux(self, app_name: str) -> bool:
        """Terminate an application on Linux via wmctrl or pkill."""
        # Try wmctrl graceful close
        if await self._wmctrl_available():
            try:
                proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                    "wmctrl", "-c", app_name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.wait(), timeout=5.0)
                if proc.returncode == 0:
                    return True
            except Exception as exc:
                logger.debug("wmctrl close failed for %r: %s", app_name, exc)

        # Fallback: pkill
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "pkill", "-f", app_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("pkill failed for %r: %s", app_name, exc)
            return False

    async def _minimize_linux(self, app_name: str) -> bool:
        """Minimize a window on Linux via wmctrl."""
        if not await self._wmctrl_available():
            logger.debug("wmctrl not available — cannot minimize on Linux")
            return False
        try:
            # wmctrl -r <name> -b add,hidden  (iconify)
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "wmctrl", "-r", app_name, "-b", "add,hidden",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("wmctrl minimize failed for %r: %s", app_name, exc)
            return False

    async def _maximize_linux(self, app_name: str) -> bool:
        """Maximize a window on Linux via wmctrl."""
        if not await self._wmctrl_available():
            logger.debug("wmctrl not available — cannot maximize on Linux")
            return False
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "wmctrl", "-r", app_name, "-b", "add,maximized_vert,maximized_horz",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("wmctrl maximize failed for %r: %s", app_name, exc)
            return False

    async def _restore_linux(self, app_name: str) -> bool:
        """Restore a window on Linux via wmctrl."""
        if not await self._wmctrl_available():
            return False
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "wmctrl", "-r", app_name, "-b",
                "remove,maximized_vert,maximized_horz,hidden",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("wmctrl restore failed for %r: %s", app_name, exc)
            return False

    async def _switch_linux(self, app_name: str) -> bool:
        """Switch focus to a window on Linux via wmctrl."""
        if not await self._wmctrl_available():
            return False
        try:
            proc = await asyncio.create_subprocess_exec(  # nosec B603 B607
                "wmctrl", "-a", app_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return proc.returncode == 0
        except Exception as exc:
            logger.debug("wmctrl switch failed for %r: %s", app_name, exc)
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    _wmctrl_cache: Optional[bool] = None

    async def _wmctrl_available(self) -> bool:
        """Return True if wmctrl is installed (cached)."""
        if DesktopApplicationController._wmctrl_cache is not None:
            return DesktopApplicationController._wmctrl_cache

        try:
            proc = await asyncio.create_subprocess_exec(
                "which", "wmctrl",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=2.0)
            result = proc.returncode == 0
        except Exception as e:
            result = False

        DesktopApplicationController._wmctrl_cache = result
        return result
