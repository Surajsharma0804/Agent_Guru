"""Module: Agent_Guru.platform.macos.controller
Purpose: macOS OS Controller - App launching, keyboard/mouse, window management.

Uses subprocess 'open -a' for app launching, pyautogui for keyboard/mouse,
and pyobjc (AppKit/Quartz) for Accessibility API and CGEvent simulation.

Performance:
    - Time Complexity: O(1) for all operations
    - Space Complexity: O(1)
    - Latency: <200ms for app launch, <10ms for keyboard/mouse

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import logging
import subprocess  # nosec B404
import sys
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional macOS-only imports
# ---------------------------------------------------------------------------
_PYAUTOGUI_AVAILABLE = False
_APPKIT_AVAILABLE = False
_QUARTZ_AVAILABLE = False

try:
    import pyautogui  # type: ignore[import]

    pyautogui.FAILSAFE = False
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    logger.exception("pyautogui not available - keyboard/mouse simulation limited")
if sys.platform == "darwin":
    try:
        import AppKit  # type: ignore[import]
        import Foundation  # type: ignore[import]  # noqa: F401

        _APPKIT_AVAILABLE = True
    except ImportError:
        logger.exception("pyobjc-framework-AppKit not available")
    try:
        import Quartz  # type: ignore[import]

        _QUARTZ_AVAILABLE = True
    except ImportError:
        logger.exception("pyobjc-framework-Quartz not available")
# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MacOSControllerResult:
    """Result of a macOS controller operation."""

    success: bool
    operation: str
    message: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

# ---------------------------------------------------------------------------
# Known application aliases
# ---------------------------------------------------------------------------
_APP_ALIASES: dict[str, str] = {
    # Browsers
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "firefox": "Firefox",
    "safari": "Safari",
    "edge": "Microsoft Edge",
    "brave": "Brave Browser",
    # Productivity
    "word": "Microsoft Word",
    "microsoft word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "pages": "Pages",
    "numbers": "Numbers",
    "keynote": "Keynote",
    "notes": "Notes",
    "reminders": "Reminders",
    "calendar": "Calendar",
    # System tools
    "terminal": "Terminal",
    "finder": "Finder",
    "activity monitor": "Activity Monitor",
    "system preferences": "System Preferences",
    "system settings": "System Settings",
    "calculator": "Calculator",
    "textedit": "TextEdit",
    "text edit": "TextEdit",
    "preview": "Preview",
    # Media
    "vlc": "VLC",
    "spotify": "Spotify",
    "music": "Music",
    "quicktime": "QuickTime Player",
    # Communication
    "whatsapp": "WhatsApp",
    "teams": "Microsoft Teams",
    "slack": "Slack",
    "discord": "Discord",
    "zoom": "zoom.us",
    "facetime": "FaceTime",
    "messages": "Messages",
    "mail": "Mail",
    # Development
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "xcode": "Xcode",
    "pycharm": "PyCharm",
    "iterm": "iTerm",
    "iterm2": "iTerm2",
    # Web (open in default browser)
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
}

class MacOSController:
    """macOS OS Controller for voice-driven automation.

    Provides:
    - Application launching via 'open -a' subprocess
    - Keyboard simulation via pyautogui / CGEvent
    - Mouse simulation via pyautogui
    - Window management via AppKit NSWorkspace
    - Permission checking via Accessibility API

    Example:
        >>> ctrl = MacOSController()
        >>> ctrl.launch_app("safari")
        >>> ctrl.type_text("Hello from Guru!")
        >>> ctrl.press_key("return")

    """

    def __init__(self) -> None:
        """Initialize macOS controller."""
        self._validate_platform()
        logger.info("MacOSController initialized")

    # ------------------------------------------------------------------
    # Platform validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_platform() -> None:
        """Raise RuntimeError if not on macOS."""
        if sys.platform != "darwin":
            msg = f"MacOSController requires macOS, running on {sys.platform}"
            raise RuntimeError(msg)

    # ------------------------------------------------------------------
    # Application launching
    # ------------------------------------------------------------------

    def launch_app(
        self,
        app_name: str,
        args: list[str] | None = None,
    ) -> MacOSControllerResult:
        """Launch an application by name.

        Tries in order:
        1. Known alias → macOS app name
        2. URL alias → 'open' command
        3. 'open -a <app_name>' subprocess
        4. Direct subprocess fallback

        Time Complexity: O(1)

        Args:
            app_name: Application name, alias, or URL
            args: Optional arguments to pass to the application

        Returns:
            MacOSControllerResult with success status

        """
        start = time.perf_counter()
        args = args or []
        normalized = app_name.lower().strip()

        # Resolve alias
        resolved = _APP_ALIASES.get(normalized, app_name)

        try:
            # URL → open in default browser
            if resolved.startswith(("http://", "https://")):
                subprocess.Popen(  # nosec B603 B607  # noqa: S603
                    ["open", resolved],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                logger.info("Opened URL: %s", resolved)
                return MacOSControllerResult(
                    success=True,
                    operation="launch_app",
                    message=f"Opened URL: {resolved}",
                    latency_ms=latency_ms,
                    metadata={"url": resolved},
                )

            # 'open -a <AppName>' - standard macOS app launch
            cmd = ["open", "-a", resolved] + (["--args", *args] if args else [])
            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                latency_ms = (time.perf_counter() - start) * 1000
                logger.info("Launched app: %s", resolved)
                return MacOSControllerResult(
                    success=True,
                    operation="launch_app",
                    message=f"Launched {app_name}",
                    latency_ms=latency_ms,
                    metadata={"app": resolved},
                )
            # Fallback: try direct subprocess
            proc = subprocess.Popen(  # nosec B603 B607  # noqa: S603
                [resolved, *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            logger.info("Launched via direct exec: %s (PID: %s)", resolved, proc.pid)
            return MacOSControllerResult(
                success=True,
                operation="launch_app",
                message=f"Launched {app_name} (PID: {proc.pid})",
                latency_ms=latency_ms,
                metadata={"pid": proc.pid, "app": resolved},
            )

        except subprocess.TimeoutExpired:
            latency_ms = (time.perf_counter() - start) * 1000
            return MacOSControllerResult(
                success=False,
                operation="launch_app",
                message=f"Timeout launching {app_name}",
                error="Launch timed out after 10s",
                latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Keyboard simulation
    # ------------------------------------------------------------------

    def type_text(
        self,
        text: str,
        interval: float = 0.0,
    ) -> MacOSControllerResult:
        """Type text into the active window.

        Uses pyautogui if available, falls back to AppleScript.

        Time Complexity: O(n) where n = len(text)

        Args:
            text: Text to type
            interval: Delay between keystrokes in seconds

        Returns:
            MacOSControllerResult

        """
        start = time.perf_counter()

        if _PYAUTOGUI_AVAILABLE:
            try:
                pyautogui.typewrite(text, interval=interval)
                latency_ms = (time.perf_counter() - start) * 1000
                logger.info("Typed %s characters via pyautogui", len(text))
                return MacOSControllerResult(
                    success=True,
                    operation="type_text",
                    message=f"Typed {len(text)} characters",
                    latency_ms=latency_ms,
                    metadata={"length": len(text), "method": "pyautogui"},
                )
            except Exception:
                logger.exception("pyautogui type_text failed, trying AppleScript")
        # AppleScript fallback
        try:
            escaped = text.replace('"', '\\"').replace("\\", "\\\\")
            script = f'tell application "System Events" to keystroke "{escaped}"'
            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            if result.returncode == 0:
                logger.info("Typed %s characters via AppleScript", len(text))
                return MacOSControllerResult(
                    success=True,
                    operation="type_text",
                    message=f"Typed {len(text)} characters",
                    latency_ms=latency_ms,
                    metadata={"length": len(text), "method": "applescript"},
                )
            return MacOSControllerResult(
                success=False,
                operation="type_text",
                message="AppleScript type_text failed",
                error=result.stderr,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return MacOSControllerResult(
                success=False,
                operation="type_text",
                message="Failed to type text",
                error=str(e),
                latency_ms=latency_ms,
            )

    def press_key(self, key: str) -> MacOSControllerResult:
        """Press a single key or key combination.

        Args:
            key: Key name (e.g. 'return', 'cmd+c', 'ctrl+alt+t')

        Returns:
            MacOSControllerResult

        """
        start = time.perf_counter()

        if _PYAUTOGUI_AVAILABLE:
            try:
                if "+" in key:
                    parts = [p.strip() for p in key.split("+")]
                    pyautogui.hotkey(*parts)
                else:
                    pyautogui.press(key)
                latency_ms = (time.perf_counter() - start) * 1000
                return MacOSControllerResult(
                    success=True,
                    operation="press_key",
                    message=f"Pressed key: {key}",
                    latency_ms=latency_ms,
                    metadata={"key": key},
                )
            except Exception:
                logger.exception("pyautogui press_key failed")
        # AppleScript fallback for common keys
        _key_map = {
            "return": "return",
            "enter": "return",
            "escape": "escape",
            "tab": "tab",
            "space": "space",
            "delete": "delete",
            "backspace": "delete",
            "up": "up arrow",
            "down": "down arrow",
            "left": "left arrow",
            "right": "right arrow",
        }
        as_key = _key_map.get(key.lower(), key)
        try:
            script = f'tell application "System Events" to key code (key code of key "{as_key}")'
            # Simpler approach: use keystroke for printable, key code for special
            script = f'tell application "System Events" to keystroke (ASCII character {ord(key[0]) if len(key) == 1 else 13})'
            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            success = result.returncode == 0
            return MacOSControllerResult(
                success=success,
                operation="press_key",
                message=f"Pressed key: {key}",
                error=result.stderr if not success else None,
                latency_ms=latency_ms,
                metadata={"key": key},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return MacOSControllerResult(
                success=False,
                operation="press_key",
                message=f"Failed to press key: {key}",
                error=str(e),
                latency_ms=latency_ms,
            )

    def hotkey(self, *keys: str) -> MacOSControllerResult:
        """Press a hotkey combination simultaneously."""
        start = time.perf_counter()

        if _PYAUTOGUI_AVAILABLE:
            try:
                pyautogui.hotkey(*keys)
                latency_ms = (time.perf_counter() - start) * 1000
                combo = "+".join(keys)
                return MacOSControllerResult(
                    success=True,
                    operation="hotkey",
                    message=f"Hotkey pressed: {combo}",
                    latency_ms=latency_ms,
                    metadata={"keys": list(keys)},
                )
            except Exception as e:
                latency_ms = (time.perf_counter() - start) * 1000
                return MacOSControllerResult(
                    success=False,
                    operation="hotkey",
                    message="Failed to press hotkey",
                    error=str(e),
                    latency_ms=latency_ms,
                )
        return MacOSControllerResult(
            success=False,
            operation="hotkey",
            message="pyautogui not available",
            error="Install pyautogui: pip install pyautogui",
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
    ) -> MacOSControllerResult:
        """Click at screen coordinates."""
        start = time.perf_counter()

        if not _PYAUTOGUI_AVAILABLE:
            return MacOSControllerResult(
                success=False,
                operation="click",
                message="pyautogui not available",
                error="Install pyautogui: pip install pyautogui",
            )

        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            latency_ms = (time.perf_counter() - start) * 1000
            return MacOSControllerResult(
                success=True,
                operation="click",
                message=f"Clicked {button} at ({x}, {y})",
                latency_ms=latency_ms,
                metadata={"x": x, "y": y, "button": button, "clicks": clicks},
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return MacOSControllerResult(
                success=False,
                operation="click",
                message=f"Failed to click at ({x}, {y})",
                error=str(e),
                latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Window management via NSWorkspace / AppleScript
    # ------------------------------------------------------------------

    def get_running_apps(self) -> list[str]:
        """Return list of running application names."""
        if _APPKIT_AVAILABLE:
            try:
                workspace = AppKit.NSWorkspace.sharedWorkspace()
                apps = workspace.runningApplications()
                return [str(app.localizedName()) for app in apps if app.localizedName()]
            except Exception:
                logger.exception("NSWorkspace app listing failed")
        # AppleScript fallback
        try:
            script = 'tell application "System Events" to get name of every process whose background only is false'
            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return [a.strip() for a in result.stdout.split(",") if a.strip()]
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.debug("AppleScript app listing failed: %s", exc)
        return []

    def focus_app(self, app_name: str) -> MacOSControllerResult:
        """Bring an application to the foreground.

        Args:
            app_name: Application name (partial match)

        Returns:
            MacOSControllerResult

        """
        start = time.perf_counter()
        normalized = app_name.lower().strip()
        resolved = _APP_ALIASES.get(normalized, app_name)

        if _APPKIT_AVAILABLE:
            try:
                workspace = AppKit.NSWorkspace.sharedWorkspace()
                apps = workspace.runningApplications()
                for app in apps:
                    name = str(app.localizedName() or "")
                    if resolved.lower() in name.lower():
                        app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
                        latency_ms = (time.perf_counter() - start) * 1000
                        logger.info("Focused app: %s", name)
                        return MacOSControllerResult(
                            success=True,
                            operation="focus_app",
                            message=f"Focused {name}",
                            latency_ms=latency_ms,
                            metadata={"app": name},
                        )
            except Exception:
                logger.exception("AppKit focus failed")
        # AppleScript fallback
        try:
            script = f'tell application "{resolved}" to activate'
            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            success = result.returncode == 0
            return MacOSControllerResult(
                success=success,
                operation="focus_app",
                message=f"Focused {app_name}" if success else f"Failed to focus {app_name}",
                error=result.stderr if not success else None,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return MacOSControllerResult(
                success=False,
                operation="focus_app",
                message=f"Failed to focus {app_name}",
                error=str(e),
                latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Permission checking
    # ------------------------------------------------------------------

    def check_accessibility_permission(self) -> bool:
        """Check if Accessibility permission is granted.

        Required for keyboard/mouse simulation via Accessibility API.

        Returns:
            True if Accessibility permission is granted

        """
        if _QUARTZ_AVAILABLE:
            try:
                return bool(
                    Quartz.AXIsProcessTrustedWithOptions(
                        {Quartz.kAXTrustedCheckOptionPrompt: False},
                    ),
                )
            except Exception:
                logger.exception("Quartz accessibility check failed")
        # Fallback: try a benign AppleScript operation
        try:
            result = subprocess.run(  # nosec B603 B607
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get name of first process',
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.debug("AppleScript accessibility check failed: %s", exc)
            return False

    def check_permission(self, operation: str) -> bool:
        """Check if the current process has permission for an operation.

        Args:
            operation: Operation name

        Returns:
            True if permitted

        """
        accessibility_required = {
            "type_text",
            "press_key",
            "hotkey",
            "click",
            "move_mouse",
        }
        if operation in accessibility_required:
            return self.check_accessibility_permission()
        return True
