"""Mobile file operations controller for Agent Guru.

Provides async file operations on Android and iOS platforms via simulated
device tooling (adb shell for Android, xcrun simctl for iOS).

Platform support:
    - Android: Storage Access Framework via adb shell commands (simulated)
    - iOS:     Files app integration via xcrun simctl (simulated)

Design Decisions:
    - All public methods are async
    - Returns True on success, False on failure — never raises for normal failures
    - Safety checks block operations on system paths (OS-specific)
    - Path resolution: expand ~ and env vars
    - Raises RuntimeError only on desktop platforms (windows/macos/linux/unknown)
    - Since these are mobile-only and can't run on desktop test machines,
      all actual device operations are simulated — the real implementations
      log what would be done and return True

Performance Characteristics:
    - Time Complexity: O(1) for single-file ops; O(n) for directory listing
    - Space Complexity: O(1) per operation
    - Latency: <2 seconds per operation (target)

Author: Agent Guru Team
Date: 2026-03-20
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — blocked system path prefixes per platform
# ---------------------------------------------------------------------------

_BLOCKED_PATHS_ANDROID: tuple[str, ...] = (
    "/system",
    "/proc",
    "/sys",
    "/data/system",
)

_BLOCKED_PATHS_IOS: tuple[str, ...] = (
    "/System",
    "/private/var/db",
)

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
            import subprocess  # noqa: PLC0415

            out = subprocess.run(
                ["uname", "-o"],  # noqa: S607
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
# Path helpers
# ---------------------------------------------------------------------------


def _resolve_path(raw: str) -> Path:
    """Expand ``~`` and environment variables, then resolve to absolute path.

    Args:
        raw: Raw path string (may contain ``~`` or ``$VAR``).

    Returns:
        Absolute :class:`pathlib.Path`.

    """
    # Strip null bytes — they cause ValueError on Windows resolve()
    raw = raw.replace("\x00", "")
    expanded = os.path.expandvars(os.path.expanduser(raw))  # noqa: PTH111
    try:
        return Path(expanded).resolve()
    except (ValueError, OSError):
        # Fallback: return as absolute without resolving symlinks
        p = Path(expanded)
        if not p.is_absolute():
            p = Path.cwd() / p
        return p


def _is_blocked(path: Path, plat: str) -> bool:
    """Return True if *path* is a blocked system path for *plat*.

    Uses POSIX-style path strings for comparison so the check works
    correctly on all host platforms (including Windows test machines).

    Args:
        path: Path to check (may be a resolved Path or a raw string wrapped
              in Path).
        plat: Platform identifier (``"android"`` or ``"ios"``).

    Returns:
        ``True`` if the path is blocked, ``False`` otherwise.

    """
    # Use POSIX representation for cross-platform consistency
    path_str = path.as_posix()

    if plat == "android":
        for blocked in _BLOCKED_PATHS_ANDROID:
            if path_str == blocked or path_str.startswith(blocked + "/"):
                logger.warning("Blocked system path (Android): %s", path_str)
                return True
    elif plat == "ios":
        for blocked in _BLOCKED_PATHS_IOS:
            if path_str == blocked or path_str.startswith(blocked + "/"):
                logger.warning("Blocked system path (iOS): %s", path_str)
                return True

    return False


def _is_blocked_raw(raw: str, plat: str) -> bool:
    """Return True if the raw path string starts with a blocked prefix for *plat*.

    This check is applied to the raw (unexpanded) path string before OS
    resolution, so it works correctly for mobile device paths on any host OS.

    Args:
        raw: Raw path string (after ~ and env-var expansion, null bytes stripped).
        plat: Platform identifier (``"android"`` or ``"ios"``).

    Returns:
        ``True`` if the path is blocked, ``False`` otherwise.

    """
    # Normalise separators to forward slash for comparison
    normalised = raw.replace("\\", "/")

    if plat == "android":
        for blocked in _BLOCKED_PATHS_ANDROID:
            if normalised == blocked or normalised.startswith(blocked + "/"):
                logger.warning("Blocked system path (Android): %s", raw)
                return True
    elif plat == "ios":
        for blocked in _BLOCKED_PATHS_IOS:
            if normalised == blocked or normalised.startswith(blocked + "/"):
                logger.warning("Blocked system path (iOS): %s", raw)
                return True

    return False


# ---------------------------------------------------------------------------
# MobileFileController
# ---------------------------------------------------------------------------


class MobileFileController:
    """Async controller for mobile file operations on Android and iOS.

    Raises :class:`RuntimeError` when instantiated on desktop platforms
    (Windows, macOS, Linux, or unknown).

    Safety checks prevent operations on OS system paths.  Path arguments
    support ``~`` expansion and environment variable substitution.

    Since these are mobile-only and can't run on desktop test machines,
    all actual device operations are simulated — the real implementations
    log what would be done and return True.

    Example::

        ctrl = MobileFileController()
        await ctrl.initialize()

        ok = await ctrl.create_file("/sdcard/notes.txt", "Hello!")
        ok = await ctrl.copy_file("/sdcard/notes.txt", "/sdcard/backup.txt")
        ok = await ctrl.delete_file("/sdcard/notes.txt")
        entries = await ctrl.list_directory("/sdcard/")

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
            RuntimeError: If the detected platform is a desktop platform
                (``"windows"``, ``"macos"``, ``"linux"``, or ``"unknown"``).

        """
        self._platform: str = platform_override or _detect_platform()
        self._initialized: bool = False

        if _is_desktop(self._platform):
            msg = (
                f"MobileFileController is not supported on desktop "
                f"platform '{self._platform}'. Use DesktopFileController instead."
            )
            raise RuntimeError(
                msg,
            )

        logger.info("MobileFileController created — platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the controller.

        Idempotent — safe to call multiple times.
        """
        if self._initialized:
            logger.debug("MobileFileController already initialized")
            return

        self._initialized = True
        logger.info("MobileFileController initialized — platform=%s", self._platform)

    async def shutdown(self) -> None:
        """Shut down the controller and release resources."""
        self._initialized = False
        logger.info("MobileFileController shut down")

    # ------------------------------------------------------------------
    # Public API — file operations
    # ------------------------------------------------------------------

    async def create_file(self, path: str, content: str = "") -> bool:
        """Create a file at *path* with optional *content*.

        Android: Simulates Storage Access Framework file creation via adb.
        iOS: Simulates Files app integration via xcrun simctl.

        Args:
            path: Destination file path (supports ``~`` and env vars).
            content: Initial file content (default empty string).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.

        """
        # Strip null bytes before expansion
        expanded = os.path.expandvars(os.path.expanduser(path.replace("\x00", "")))  # noqa: PTH111
        if _is_blocked_raw(expanded, self._platform):
            return False

        resolved = _resolve_path(path)
        logger.info(
            "create_file: %s (platform=%s, content_len=%d)",
            resolved,
            self._platform,
            len(content),
        )
        try:
            if self._platform == "android":
                return await self._android_create_file(resolved, content)
            # ios
            return await self._ios_create_file(resolved, content)
        except Exception:
            logger.exception("create_file(%s) failed", resolved)
            return False

    async def delete_file(self, path: str) -> bool:
        """Delete the file at *path*.

        Args:
            path: File path to delete (supports ``~`` and env vars).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.

        """
        expanded = os.path.expandvars(os.path.expanduser(path.replace("\x00", "")))  # noqa: PTH111
        if _is_blocked_raw(expanded, self._platform):
            return False

        resolved = _resolve_path(path)
        logger.info("delete_file: %s (platform=%s)", resolved, self._platform)
        try:
            if self._platform == "android":
                return await self._android_delete_file(resolved)
            # ios
            return await self._ios_delete_file(resolved)
        except Exception:
            logger.exception("delete_file(%s) failed", resolved)
            return False

    async def move_file(self, src: str, dst: str) -> bool:
        """Move a file from *src* to *dst*.

        Args:
            src: Source file path (supports ``~`` and env vars).
            dst: Destination file path (supports ``~`` and env vars).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.

        """
        expanded_src = os.path.expandvars(os.path.expanduser(src.replace("\x00", "")))  # noqa: PTH111
        expanded_dst = os.path.expandvars(os.path.expanduser(dst.replace("\x00", "")))  # noqa: PTH111

        if _is_blocked_raw(expanded_src, self._platform) or _is_blocked_raw(
            expanded_dst,
            self._platform,
        ):
            return False

        resolved_src = _resolve_path(src)
        resolved_dst = _resolve_path(dst)
        logger.info("move_file: %s → %s (platform=%s)", resolved_src, resolved_dst, self._platform)
        try:
            if self._platform == "android":
                return await self._android_move_file(resolved_src, resolved_dst)
            # ios
            return await self._ios_move_file(resolved_src, resolved_dst)
        except Exception:
            logger.exception("move_file(%s → %s) failed", resolved_src, resolved_dst)
            return False

    async def copy_file(self, src: str, dst: str) -> bool:
        """Copy a file from *src* to *dst*.

        Args:
            src: Source file path (supports ``~`` and env vars).
            dst: Destination file path (supports ``~`` and env vars).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.

        """
        expanded_src = os.path.expandvars(os.path.expanduser(src.replace("\x00", "")))  # noqa: PTH111
        expanded_dst = os.path.expandvars(os.path.expanduser(dst.replace("\x00", "")))  # noqa: PTH111

        if _is_blocked_raw(expanded_src, self._platform) or _is_blocked_raw(
            expanded_dst,
            self._platform,
        ):
            return False

        resolved_src = _resolve_path(src)
        resolved_dst = _resolve_path(dst)
        logger.info("copy_file: %s → %s (platform=%s)", resolved_src, resolved_dst, self._platform)
        try:
            if self._platform == "android":
                return await self._android_copy_file(resolved_src, resolved_dst)
            # ios
            return await self._ios_copy_file(resolved_src, resolved_dst)
        except Exception:
            logger.exception("copy_file(%s → %s) failed", resolved_src, resolved_dst)
            return False

    async def list_directory(self, path: str) -> list[str]:
        """List the contents of a directory.

        Args:
            path: Directory path to list (supports ``~`` and env vars).

        Returns:
            List of filenames (not full paths) in the directory.
            Returns an empty list on error or blocked path.

        """
        expanded = os.path.expandvars(os.path.expanduser(path.replace("\x00", "")))  # noqa: PTH111
        if _is_blocked_raw(expanded, self._platform):
            return []

        resolved = _resolve_path(path)
        logger.info("list_directory: %s (platform=%s)", resolved, self._platform)
        try:
            if self._platform == "android":
                return await self._android_list_directory(resolved)
            # ios
            return await self._ios_list_directory(resolved)
        except Exception:
            logger.exception("list_directory(%s) failed: %s")
            return []

    async def request_permission(self, permission: str) -> bool:
        """Request a storage permission from the user.

        Simulates a permission request — always returns True in simulation.

        Android: Simulates requesting READ_EXTERNAL_STORAGE / WRITE_EXTERNAL_STORAGE.
        iOS: Simulates requesting NSPhotoLibraryUsageDescription / NSDocumentsFolderUsageDescription.

        Args:
            permission: Permission name to request.

        Returns:
            ``True`` — always granted in simulation.

        """
        logger.info(
            "request_permission: %r (platform=%s) — simulated, always True",
            permission,
            self._platform,
        )
        return True

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
    # Android simulated implementations
    # ------------------------------------------------------------------

    async def _android_create_file(self, path: Path, content: str) -> bool:
        """Simulate Android Storage Access Framework file creation via adb."""
        logger.debug(
            "[Android SAF simulation] Would run: adb shell 'echo %r > %s'",
            content[:50],
            path,
        )
        # Simulate async I/O delay
        await asyncio.sleep(0)
        return True

    async def _android_delete_file(self, path: Path) -> bool:
        """Simulate Android file deletion via adb shell rm."""
        logger.debug("[Android SAF simulation] Would run: adb shell rm %s", path)
        await asyncio.sleep(0)
        return True

    async def _android_move_file(self, src: Path, dst: Path) -> bool:
        """Simulate Android file move via adb shell mv."""
        logger.debug("[Android SAF simulation] Would run: adb shell mv %s %s", src, dst)
        await asyncio.sleep(0)
        return True

    async def _android_copy_file(self, src: Path, dst: Path) -> bool:
        """Simulate Android file copy via adb shell cp."""
        logger.debug("[Android SAF simulation] Would run: adb shell cp %s %s", src, dst)
        await asyncio.sleep(0)
        return True

    async def _android_list_directory(self, path: Path) -> list[str]:
        """Simulate Android directory listing via adb shell ls."""
        logger.debug("[Android SAF simulation] Would run: adb shell ls %s", path)
        await asyncio.sleep(0)
        return []

    # ------------------------------------------------------------------
    # iOS simulated implementations
    # ------------------------------------------------------------------

    async def _ios_create_file(self, path: Path, content: str) -> bool:
        """Simulate iOS Files app file creation via xcrun simctl."""
        logger.debug(
            "[iOS Files simulation] Would run: xcrun simctl spawn booted sh -c 'echo %r > %s'",
            content[:50],
            path,
        )
        await asyncio.sleep(0)
        return True

    async def _ios_delete_file(self, path: Path) -> bool:
        """Simulate iOS file deletion via xcrun simctl."""
        logger.debug("[iOS Files simulation] Would run: xcrun simctl spawn booted rm %s", path)
        await asyncio.sleep(0)
        return True

    async def _ios_move_file(self, src: Path, dst: Path) -> bool:
        """Simulate iOS file move via xcrun simctl."""
        logger.debug(
            "[iOS Files simulation] Would run: xcrun simctl spawn booted mv %s %s",
            src,
            dst,
        )
        await asyncio.sleep(0)
        return True

    async def _ios_copy_file(self, src: Path, dst: Path) -> bool:
        """Simulate iOS file copy via xcrun simctl."""
        logger.debug(
            "[iOS Files simulation] Would run: xcrun simctl spawn booted cp %s %s",
            src,
            dst,
        )
        await asyncio.sleep(0)
        return True

    async def _ios_list_directory(self, path: Path) -> list[str]:
        """Simulate iOS directory listing via xcrun simctl."""
        logger.debug("[iOS Files simulation] Would run: xcrun simctl spawn booted ls %s", path)
        await asyncio.sleep(0)
        return []
