"""Desktop text input controller for Agent Guru.

Provides async text input via keyboard simulation and clipboard across
Windows, macOS, and Linux.

Platform support:
    - Windows: pyautogui typewrite/hotkey + pyperclip clipboard
    - macOS:   pyautogui typewrite/hotkey + pbcopy/pbpaste clipboard
    - Linux:   pyautogui typewrite/hotkey + xclip/xdotool clipboard

Design Decisions:
    - All public methods are async (run_in_executor for blocking pyautogui calls)
    - Returns True on success, False on failure — never raises for normal failures
    - ASCII text typed via pyautogui.typewrite(); unicode/emoji via clipboard
    - Raises RuntimeError only on mobile platforms (android/ios)
    - Input sanitization: strip null bytes, limit to 10 000 chars

Performance Characteristics:
    - Time Complexity: O(n) where n = len(text)
    - Space Complexity: O(n) for clipboard buffer
    - Latency: configurable via interval parameter (default 0.05 s/char)

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import asyncio
import logging

from Agent_Guru.platform.platform_detector import PlatformDetector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_TEXT_LENGTH: int = 10_000

# Keys that must be sent via clipboard because pyautogui.typewrite cannot
# handle them reliably (non-ASCII, emoji, etc.)
_ASCII_PRINTABLE_MIN = 0x20
_ASCII_PRINTABLE_MAX = 0x7E

# Mapping of logical key names → pyautogui key strings
_SPECIAL_KEY_MAP: dict[str, str] = {
    "enter": "enter",
    "return": "enter",
    "tab": "tab",
    "escape": "escape",
    "esc": "escape",
    "backspace": "backspace",
    "delete": "delete",
    "del": "delete",
    "space": "space",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "f1": "f1",
    "f2": "f2",
    "f3": "f3",
    "f4": "f4",
    "f5": "f5",
    "f6": "f6",
    "f7": "f7",
    "f8": "f8",
    "f9": "f9",
    "f10": "f10",
    "f11": "f11",
    "f12": "f12",
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "win": "win",
    "command": "command",
    "cmd": "command",
    "capslock": "capslock",
    "insert": "insert",
    "printscreen": "printscreen",
    "scrolllock": "scrolllock",
    "pause": "pause",
    "numlock": "numlock",
}

# ---------------------------------------------------------------------------
# Platform detection (shared with desktop_app_controller pattern)
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
# Input sanitization helpers
# ---------------------------------------------------------------------------


def _sanitize_text(text: str) -> str:
    """Strip null bytes and truncate to _MAX_TEXT_LENGTH.

    Args:
        text: Raw input text.

    Returns:
        Sanitized text safe for keyboard simulation.

    """
    text = text.replace("\x00", "")
    if len(text) > _MAX_TEXT_LENGTH:
        logger.warning("Text truncated from %d to %d characters", len(text), _MAX_TEXT_LENGTH)
        text = text[:_MAX_TEXT_LENGTH]
    return text


def _is_ascii_typeable(text: str) -> bool:
    """Return True if every character in *text* is ASCII-printable or whitespace.

    pyautogui.typewrite() handles ASCII printable chars and common whitespace
    reliably; everything else must go through the clipboard.
    """
    for ch in text:
        cp = ord(ch)
        if not (_ASCII_PRINTABLE_MIN <= cp <= _ASCII_PRINTABLE_MAX or ch in "\t\n\r"):
            return False
    return True


# ---------------------------------------------------------------------------
# DesktopTextController
# ---------------------------------------------------------------------------


class DesktopTextController:
    """Async controller for desktop text input via keyboard simulation.

    Supports Windows, macOS, and Linux.  Raises :class:`RuntimeError` when
    instantiated on Android or iOS.

    Example::

        ctrl = DesktopTextController()
        await ctrl.initialize()

        ok = await ctrl.type_text("Hello, world!")
        ok = await ctrl.type_special_key("enter")
        ok = await ctrl.paste_text("Unicode: 🎉")
        ok = await ctrl.clear_field()

        await ctrl.shutdown()

    All action methods return ``True`` on success and ``False`` on failure.
    They never raise exceptions for normal operational failures.
    """

    def __init__(self, platform_override: str | None = None) -> None:
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
            msg = (
                f"DesktopTextController is not supported on mobile "
                f"platform '{self._platform}'. Use MobileTextController instead."
            )
            raise RuntimeError(
                msg,
            )

        logger.info("DesktopTextController created — platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the controller.

        Idempotent — safe to call multiple times.
        """
        if self._initialized:
            logger.debug("DesktopTextController already initialized")
            return

        self._initialized = True
        logger.info("DesktopTextController initialized — platform=%s", self._platform)

    async def shutdown(self) -> None:
        """Shut down the controller and release resources."""
        self._initialized = False
        logger.info("DesktopTextController shut down")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def type_text(self, text: str, interval: float = 0.05) -> bool:
        """Type *text* into the currently focused application.

        ASCII-printable text is typed character-by-character via
        ``pyautogui.typewrite()``.  Text containing unicode or emoji is
        automatically routed through the clipboard (``paste_text``).

        Args:
            text: Text to type.  Empty string is a no-op (returns ``True``).
            interval: Seconds between keystrokes (default 0.05).

        Returns:
            ``True`` on success, ``False`` on failure.

        """
        if not text:
            return True  # empty string is a no-op

        text = _sanitize_text(text)
        if not text:
            return True

        logger.info(
            "type_text: length=%d interval=%.3f platform=%s",
            len(text),
            interval,
            self._platform,
        )

        # Route unicode/emoji through clipboard
        if not _is_ascii_typeable(text):
            return await self.paste_text(text)

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._blocking_typewrite, text, interval)
            return True
        except Exception:
            logger.exception("type_text failed")
            return False
    async def type_special_key(self, key: str) -> bool:
        """Press a special key by logical name.

        Supported keys: enter, tab, escape, backspace, delete, space,
        arrow keys, function keys (f1–f12), home, end, pageup, pagedown,
        and modifier keys.

        Args:
            key: Logical key name (case-insensitive).

        Returns:
            ``True`` on success, ``False`` if the key is unknown or press fails.

        """
        if not key or not key.strip():
            logger.warning("type_special_key called with empty key")
            return False

        normalized = key.strip().lower()
        pyautogui_key = _SPECIAL_KEY_MAP.get(normalized)
        if pyautogui_key is None:
            logger.warning("Unknown special key: %r", key)
            return False

        logger.info("type_special_key: %r → %r", key, pyautogui_key)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._blocking_press, pyautogui_key)
            return True
        except Exception:
            logger.exception("type_special_key(%r) failed: %s")
            return False
    async def paste_text(self, text: str) -> bool:
        """Paste *text* into the focused application via the clipboard.

        Copies *text* to the system clipboard then sends Ctrl+V (or Cmd+V
        on macOS).  This is the preferred path for unicode and emoji.

        Args:
            text: Text to paste.  Empty string is a no-op (returns ``True``).

        Returns:
            ``True`` on success, ``False`` on failure.

        """
        if not text:
            return True

        text = _sanitize_text(text)
        if not text:
            return True

        logger.info("paste_text: length=%d platform=%s", len(text), self._platform)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._blocking_paste, text)
            return True
        except Exception:
            logger.exception("paste_text failed")
            return False
    async def clear_field(self) -> bool:
        """Clear the currently focused input field (Ctrl+A then Delete).

        Returns:
            ``True`` on success, ``False`` on failure.

        """
        logger.info("clear_field: platform=%s", self._platform)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._blocking_clear_field)
            return True
        except Exception:
            logger.exception("clear_field failed")
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
    # Blocking helpers (run inside executor)
    # ------------------------------------------------------------------

    def _blocking_typewrite(self, text: str, interval: float) -> None:
        """Blocking pyautogui.typewrite call — must run in executor."""
        try:
            import pyautogui  # type: ignore[import]
        except ImportError:
            logger.exception("pyautogui not available — cannot type text")
            raise
        pyautogui.typewrite(text, interval=interval)

    def _blocking_press(self, key: str) -> None:
        """Blocking pyautogui.press call — must run in executor."""
        try:
            import pyautogui  # type: ignore[import]
        except ImportError:
            logger.exception("pyautogui not available — cannot press key")
            raise
        pyautogui.press(key)

    def _blocking_paste(self, text: str) -> None:
        """Copy *text* to clipboard then send paste hotkey — blocking."""
        self._clipboard_copy(text)
        try:
            import pyautogui  # type: ignore[import]
        except ImportError:
            logger.exception("pyautogui not available — cannot send paste hotkey")
            raise
        if self._platform == "macos":
            pyautogui.hotkey("command", "v")
        else:
            pyautogui.hotkey("ctrl", "v")

    def _blocking_clear_field(self) -> None:
        """Select-all then delete — blocking."""
        try:
            import pyautogui  # type: ignore[import]
        except ImportError:
            logger.exception("pyautogui not available — cannot clear field")
            raise
        if self._platform == "macos":
            pyautogui.hotkey("command", "a")
        else:
            pyautogui.hotkey("ctrl", "a")

        pyautogui.press("delete")

    def _clipboard_copy(self, text: str) -> None:
        """Copy *text* to the system clipboard.

        Tries pyperclip first; falls back to platform-native commands.
        """
        # Try pyperclip (cross-platform)
        try:
            import pyperclip  # type: ignore[import]

            pyperclip.copy(text)
            return
        except ImportError as e:
            logger.debug("pyperclip not available — trying platform clipboard: %s", e)
            logger.debug("pyperclip.copy failed: %s — trying platform clipboard", e)
        # Platform-native fallback
        if self._platform == "macos":
            self._clipboard_copy_macos(text)
        elif self._platform == "windows":
            self._clipboard_copy_windows(text)
        else:
            self._clipboard_copy_linux(text)

    def _clipboard_copy_macos(self, text: str) -> None:
        """Copy to macOS clipboard via pbcopy."""
        import subprocess  # noqa: PLC0415

        proc = subprocess.run(
            ["pbcopy"],  # nosec B603 B607  # noqa: S607
            check=False,
            input=text.encode("utf-8"),
            timeout=5,
        )
        if proc.returncode != 0:
            msg = "pbcopy failed"
            raise RuntimeError(msg)

    def _clipboard_copy_windows(self, text: str) -> None:
        """Copy to Windows clipboard via ctypes."""
        try:
            import ctypes  # noqa: PLC0415
            import ctypes.wintypes  # noqa: PLC0415

            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]

            encoded = (text + "\x00").encode("utf-16-le")
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            ptr = kernel32.GlobalLock(h_mem)
            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(h_mem)

            user32.OpenClipboard(None)
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            user32.CloseClipboard()
        except Exception as exc:
            msg = f"Windows clipboard copy failed: {exc}"
            raise RuntimeError(msg) from exc
    def _clipboard_copy_linux(self, text: str) -> None:
        """Copy to Linux clipboard via xclip or xdotool."""
        import subprocess  # noqa: PLC0415

        for cmd in (["xclip", "-selection", "clipboard"], ["xdotool", "type", "--clearmodifiers"]):
            try:
                proc = subprocess.run(  # noqa: S603
                    cmd,  # nosec B603 B607
                    check=False,
                    input=text.encode("utf-8"),
                    timeout=5,
                    capture_output=True,
                )
                if proc.returncode == 0:
                    return
            except FileNotFoundError as exc:
                continue
                logger.debug("Clipboard command %r failed: %s", cmd[0], exc)
                continue
        msg = "No clipboard tool available on Linux (install xclip or pyperclip)"
        raise RuntimeError(msg)
