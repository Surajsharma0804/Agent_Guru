"""Mobile text input controller for Agent Guru.

Provides async text input via adb (Android) and xcrun simctl (iOS) on mobile
platforms.

Platform support:
    - Android: adb shell input text for ASCII; clipboard+paste for unicode/emoji
    - iOS:     xcrun simctl pasteboard set + Cmd+V for all text (graceful fallback)

Design Decisions:
    - All public methods are async (asyncio.create_subprocess_exec for I/O)
    - Returns True on success, False on failure — never raises for normal failures
    - ASCII text typed via adb shell input text; unicode/emoji via clipboard+paste
    - Raises RuntimeError only on desktop platforms (windows/macos/linux/unknown)
    - Input sanitization: strip null bytes, limit to 10 000 chars
    - Graceful fallback when adb/xcrun unavailable

Performance Characteristics:
    - Time Complexity: O(n) where n = len(text)
    - Space Complexity: O(n) for clipboard buffer
    - Latency: <2 seconds per operation (target)

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import asyncio
import logging
import platform

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_TEXT_LENGTH: int = 10_000

_ASCII_PRINTABLE_MIN = 0x20
_ASCII_PRINTABLE_MAX = 0x7E

# Android keyevent keycodes
_ANDROID_KEYCODES: dict[str, int] = {
    "enter": 66,
    "return": 66,
    "backspace": 67,
    "del": 67,
    "delete": 67,
    "tab": 61,
    "escape": 111,
    "esc": 111,
    "space": 62,
    "up": 19,
    "down": 20,
    "left": 21,
    "right": 22,
    "home": 3,
    "end": 123,
    "pageup": 92,
    "pagedown": 93,
    "f1": 131,
    "f2": 132,
    "f3": 133,
    "f4": 134,
    "f5": 135,
    "f6": 136,
    "f7": 137,
    "f8": 138,
    "f9": 139,
    "f10": 140,
    "f11": 141,
    "f12": 142,
    # Ctrl+A = select all (KEYCODE_CTRL_A = 29 + modifier, use 277)
    "ctrl_a": 277,
    "select_all": 277,
}

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

_PLATFORM_CACHE: str | None = None


def _detect_platform() -> str:
    """Return a normalised platform identifier.

    Returns:
        One of ``"windows"``, ``"macos"``, ``"linux"``, ``"android"``,
        ``"ios"``, or ``"unknown"``.

    """
    global _PLATFORM_CACHE
    if _PLATFORM_CACHE is not None:
        return _PLATFORM_CACHE

    system = platform.system().lower()
    if system == "windows":
        result = "windows"
    elif system == "darwin":
        result = "macos"
    elif system == "linux":
        try:
            import subprocess

            out = subprocess.run(
                ["uname", "-o"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1,  # nosec B603 B607
            )
            result = "android" if "android" in out.stdout.lower() else "linux"
        except Exception:
            result = "linux"
    else:
        result = "unknown"

    _PLATFORM_CACHE = result
    return result


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
        Sanitized text safe for mobile input.

    """
    text = text.replace("\x00", "")
    if len(text) > _MAX_TEXT_LENGTH:
        logger.warning("Text truncated from %d to %d characters", len(text), _MAX_TEXT_LENGTH)
        text = text[:_MAX_TEXT_LENGTH]
    return text


def _is_ascii_typeable(text: str) -> bool:
    """Return True if every character in *text* is ASCII-printable (no whitespace).

    adb shell input text handles ASCII printable chars reliably.
    Unicode, emoji, and whitespace must go through the clipboard.
    """
    for ch in text:
        cp = ord(ch)
        if not (_ASCII_PRINTABLE_MIN <= cp <= _ASCII_PRINTABLE_MAX):
            return False
    return True


def _escape_for_adb(text: str) -> str:
    """Escape special shell characters for adb shell input text.

    adb shell input text requires escaping of spaces and special chars.

    Args:
        text: ASCII-printable text to escape.

    Returns:
        Shell-escaped text safe for adb input.

    """
    # Characters that need escaping in adb shell input text
    special = set(" \t\n\\'\"<>|&;(){}$`!#~")
    escaped = []
    for ch in text:
        if ch in special:
            escaped.append(f"\\{ch}")
        else:
            escaped.append(ch)
    return "".join(escaped)


# ---------------------------------------------------------------------------
# MobileTextController
# ---------------------------------------------------------------------------


class MobileTextController:
    """Async controller for mobile text input via adb (Android) and xcrun (iOS).

    Supports Android and iOS.  Raises :class:`RuntimeError` when instantiated
    on Windows, macOS, or Linux desktop platforms.

    Example::

        ctrl = MobileTextController()
        await ctrl.initialize()

        ok = await ctrl.type_text("Hello, world!")
        ok = await ctrl.type_text("Unicode: 🎉")
        ok = await ctrl.type_special_key("enter")
        ok = await ctrl.paste_text("Clipboard text")
        ok = await ctrl.clear_field()

        await ctrl.shutdown()

    All action methods return ``True`` on success and ``False`` on failure.
    They never raise exceptions for normal operational failures.

    Android implementation:
        ASCII text: ``adb shell input text "<escaped_text>"``
        Unicode/emoji: copy to clipboard via adb, then paste (Ctrl+V)
        Special keys: ``adb shell input keyevent <keycode>``
        Clear field: KEYCODE_CTRL_A (select all) + KEYCODE_DEL

    iOS implementation:
        Text input: ``xcrun simctl pasteboard set`` + Cmd+V via xcrun simctl
        Special keys: limited support via xcrun simctl io booted sendkey
        Graceful fallback with helpful warning message when xcrun unavailable
    """

    def __init__(self, platform_override: str | None = None) -> None:
        """Create the controller.

        Args:
            platform_override: Force a specific platform string (for testing).
                When ``None`` the platform is auto-detected.

        Raises:
            RuntimeError: If the detected platform is a desktop platform
                (``"windows"``, ``"macos"``, ``"linux"``, or ``"unknown"``).

        """
        self._platform: str = platform_override or _detect_platform()
        self._initialized: bool = False

        if _is_desktop(self._platform):
            msg = (
                f"MobileTextController is not supported on desktop "
                f"platform '{self._platform}'. Use DesktopTextController instead."
            )
            raise RuntimeError(
                msg,
            )

        logger.info("MobileTextController created — platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the controller.

        Idempotent — safe to call multiple times.
        """
        if self._initialized:
            logger.debug("MobileTextController already initialized")
            return

        self._initialized = True
        logger.info("MobileTextController initialized — platform=%s", self._platform)

    async def shutdown(self) -> None:
        """Shut down the controller and release resources."""
        self._initialized = False
        logger.info("MobileTextController shut down")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def type_text(self, text: str) -> bool:
        """Type *text* into the currently focused application.

        Android: ASCII text is typed via ``adb shell input text``; unicode
        and emoji are routed through the clipboard (``paste_text``).

        iOS: All text is routed through the clipboard via xcrun simctl.

        Args:
            text: Text to type.  Empty string is a no-op (returns ``True``).

        Returns:
            ``True`` on success, ``False`` on failure.

        """
        if not text:
            return True

        text = _sanitize_text(text)
        if not text:
            return True

        logger.info("type_text: length=%d platform=%s", len(text), self._platform)

        try:
            if self._platform == "android":
                return await self._type_text_android(text)
            # ios
            return await self._type_text_ios(text)
        except Exception:
            logger.exception("type_text failed")
            return False

    async def paste_text(self, text: str) -> bool:
        """Paste *text* into the focused application via the clipboard.

        Android: Copies text to clipboard via adb, then sends Ctrl+V.
        iOS: Uses xcrun simctl pasteboard set, then sends Cmd+V.

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
            if self._platform == "android":
                return await self._paste_android(text)
            # ios
            return await self._paste_ios(text)
        except Exception:
            logger.exception("paste_text failed")
            return False

    async def type_special_key(self, key: str) -> bool:
        """Press a special key by logical name.

        Android: Uses ``adb shell input keyevent <keycode>``.
        iOS: Limited support via xcrun simctl io booted sendkey.

        Supported keys: enter, backspace, delete, tab, escape, space,
        arrow keys, function keys (f1–f12), home, end, pageup, pagedown.

        Args:
            key: Logical key name (case-insensitive).

        Returns:
            ``True`` on success, ``False`` if the key is unknown or press fails.

        """
        if not key or not key.strip():
            logger.warning("type_special_key called with empty key")
            return False

        normalized = key.strip().lower()

        logger.info("type_special_key: %r platform=%s", key, self._platform)

        try:
            if self._platform == "android":
                return await self._special_key_android(normalized)
            # ios
            return await self._special_key_ios(normalized)
        except Exception:
            logger.exception("type_special_key failed")
            return False

    async def clear_field(self) -> bool:
        """Clear the currently focused input field.

        Android: Sends KEYCODE_CTRL_A (select all) then KEYCODE_DEL.
        iOS: Sends select-all then delete via xcrun simctl.

        Returns:
            ``True`` on success, ``False`` on failure.

        """
        logger.info("clear_field: platform=%s", self._platform)

        try:
            if self._platform == "android":
                return await self._clear_field_android()
            # ios
            return await self._clear_field_ios()
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
    # Android implementations
    # ------------------------------------------------------------------

    async def _type_text_android(self, text: str) -> bool:
        """Type text on Android via adb.

        ASCII text uses ``adb shell input text``; unicode/emoji uses clipboard.
        """
        if not await self._adb_available():
            logger.warning(
                "adb not available — cannot type text on Android. "
                "Ensure adb is installed and the device is connected.",
            )
            return False

        if _is_ascii_typeable(text):
            return await self._adb_input_text(text)
        # Unicode/emoji: use clipboard
        return await self._paste_android(text)

    async def _adb_input_text(self, text: str) -> bool:
        """Send ASCII text via ``adb shell input text``."""
        escaped = _escape_for_adb(text)
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb",
                "shell",
                "input",
                "text",
                escaped,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Typed ASCII text via adb input text (len=%d)", len(text))
            else:
                logger.warning("adb input text returned non-zero for text (len=%d)", len(text))
            return success
        except Exception as exc:
            logger.debug("adb input text failed: %s", exc)
            return False

    async def _paste_android(self, text: str) -> bool:
        """Copy text to Android clipboard via adb, then paste with Ctrl+V."""
        if not await self._adb_available():
            logger.warning(
                "adb not available — cannot paste text on Android. "
                "Ensure adb is installed and the device is connected.",
            )
            return False

        # Set clipboard content via adb shell am broadcast
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb",
                "shell",
                "am",
                "broadcast",
                "-a",
                "clipper.set",
                "-e",
                "text",
                text,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
        except Exception as exc:
            logger.debug("adb clipboard set failed: %s — trying alternative", exc)
            # Fallback: use input text with escaped content if ASCII
            if _is_ascii_typeable(text):
                return await self._adb_input_text(text)
            logger.exception("Cannot paste unicode text on Android without clipboard tool")
            return False

        # Send Ctrl+V (keyevent 279 = KEYCODE_PASTE)
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb",
                "shell",
                "input",
                "keyevent",
                "279",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Pasted text via adb clipboard (len=%d)", len(text))
            else:
                logger.warning("adb paste keyevent returned non-zero")
            return success
        except Exception as exc:
            logger.debug("adb paste keyevent failed: %s", exc)
            return False

    async def _special_key_android(self, key: str) -> bool:
        """Send a special key on Android via ``adb shell input keyevent``."""
        if not await self._adb_available():
            logger.warning("adb not available — cannot send key %r on Android.", key)
            return False

        keycode = _ANDROID_KEYCODES.get(key)
        if keycode is None:
            logger.warning("Unknown special key for Android: %r", key)
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "adb",
                "shell",
                "input",
                "keyevent",
                str(keycode),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Sent keyevent %d for key %r", keycode, key)
            else:
                logger.warning("adb keyevent %d returned non-zero for key %r", keycode, key)
            return success
        except Exception as exc:
            logger.debug("adb keyevent failed for key %r: %s", key, exc)
            return False

    async def _clear_field_android(self) -> bool:
        """Clear field on Android: KEYCODE_CTRL_A then KEYCODE_DEL."""
        if not await self._adb_available():
            logger.warning("adb not available — cannot clear field on Android.")
            return False

        # Select all: KEYCODE_CTRL_A = 277
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb",
                "shell",
                "input",
                "keyevent",
                "277",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            if proc.returncode != 0:
                logger.warning("adb KEYCODE_CTRL_A returned non-zero")
                return False
        except Exception as exc:
            logger.debug("adb KEYCODE_CTRL_A failed: %s", exc)
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "adb",
                "shell",
                "input",
                "keyevent",
                "67",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Cleared field via adb CTRL_A + DEL")
            else:
                logger.warning("adb KEYCODE_DEL returned non-zero")
            return success
        except Exception as exc:
            logger.debug("adb KEYCODE_DEL failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # iOS implementations
    # ------------------------------------------------------------------

    async def _type_text_ios(self, text: str) -> bool:
        """Type text on iOS via xcrun simctl pasteboard + paste."""
        if not await self._xcrun_available():
            logger.warning(
                "xcrun not available — cannot type text on iOS. "
                "To type text on a physical iOS device, use the Shortcuts app "
                "or an MDM solution. For simulators, install Xcode.",
            )
            return False

        return await self._paste_ios(text)

    async def _paste_ios(self, text: str) -> bool:
        """Paste text on iOS via xcrun simctl pasteboard set + Cmd+V."""
        if not await self._xcrun_available():
            logger.warning(
                "xcrun not available — cannot paste text on iOS. "
                "To paste text on a physical iOS device, use the Shortcuts app "
                "or an MDM solution. For simulators, install Xcode.",
            )
            return False

        # Set pasteboard content
        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun",
                "simctl",
                "pasteboard",
                "set",
                "booted",
                text,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            if proc.returncode != 0:
                logger.warning("xcrun simctl pasteboard set returned non-zero")
                return False
        except Exception as exc:
            logger.debug("xcrun simctl pasteboard set failed: %s", exc)
            return False

        # Send Cmd+V via xcrun simctl io booted sendkey
        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun",
                "simctl",
                "io",
                "booted",
                "sendkey",
                "--key",
                "v",
                "--modifier",
                "command",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Pasted text via xcrun simctl pasteboard (len=%d)", len(text))
            else:
                logger.warning("xcrun simctl io sendkey returned non-zero")
            return success
        except Exception as exc:
            logger.debug("xcrun simctl io sendkey failed: %s", exc)
            return False

    async def _special_key_ios(self, key: str) -> bool:
        """Send a special key on iOS via xcrun simctl io booted sendkey."""
        if not await self._xcrun_available():
            logger.warning(
                "xcrun not available — cannot send key %r on iOS. For simulators, install Xcode.",
                key,
            )
            return False

        # Map logical key names to xcrun simctl key names
        _IOS_KEY_MAP: dict[str, str] = {
            "enter": "return",
            "return": "return",
            "backspace": "delete",
            "del": "delete",
            "delete": "delete",
            "tab": "tab",
            "escape": "escape",
            "esc": "escape",
            "space": "space",
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
            "home": "home",
            "end": "end",
            "pageup": "pageup",
            "pagedown": "pagedown",
        }

        ios_key = _IOS_KEY_MAP.get(key)
        if ios_key is None:
            logger.warning("Unknown or unsupported special key for iOS: %r", key)
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun",
                "simctl",
                "io",
                "booted",
                "sendkey",
                "--key",
                ios_key,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Sent key %r via xcrun simctl io sendkey", key)
            else:
                logger.warning("xcrun simctl io sendkey returned non-zero for key %r", key)
            return success
        except Exception as exc:
            logger.debug("xcrun simctl io sendkey failed for key %r: %s", key, exc)
            return False

    async def _clear_field_ios(self) -> bool:
        """Clear field on iOS: Cmd+A then Delete."""
        if not await self._xcrun_available():
            logger.warning("xcrun not available — cannot clear field on iOS.")
            return False

        # Select all: Cmd+A
        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun",
                "simctl",
                "io",
                "booted",
                "sendkey",
                "--key",
                "a",
                "--modifier",
                "command",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            if proc.returncode != 0:
                logger.warning("xcrun simctl Cmd+A returned non-zero")
                return False
        except Exception as exc:
            logger.debug("xcrun simctl Cmd+A failed: %s", exc)
            return False

        # Delete
        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun",
                "simctl",
                "io",
                "booted",
                "sendkey",
                "--key",
                "delete",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            success = proc.returncode == 0
            if success:
                logger.info("Cleared field via xcrun simctl Cmd+A + Delete")
            else:
                logger.warning("xcrun simctl delete returned non-zero")
            return success
        except Exception as exc:
            logger.debug("xcrun simctl delete failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Availability checks (cached per instance)
    # ------------------------------------------------------------------

    _adb_cache: bool | None = None
    _xcrun_cache: bool | None = None

    async def _adb_available(self) -> bool:
        """Return True if adb is installed and reachable (cached)."""
        if MobileTextController._adb_cache is not None:
            return MobileTextController._adb_cache

        try:
            proc = await asyncio.create_subprocess_exec(
                "adb",
                "version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=3.0)
            result = proc.returncode == 0
        except Exception:
            result = False

        MobileTextController._adb_cache = result
        return result

    async def _xcrun_available(self) -> bool:
        """Return True if xcrun is installed and reachable (cached)."""
        if MobileTextController._xcrun_cache is not None:
            return MobileTextController._xcrun_cache

        try:
            proc = await asyncio.create_subprocess_exec(
                "xcrun",
                "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )  # nosec B603 B607
            await asyncio.wait_for(proc.wait(), timeout=3.0)
            result = proc.returncode == 0
        except Exception:
            result = False

        MobileTextController._xcrun_cache = result
        return result
