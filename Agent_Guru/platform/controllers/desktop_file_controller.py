"""Desktop file operations controller for Agent Guru.

Provides async file and directory operations across Windows, macOS, and Linux
with safety checks to prevent modification of system paths.

Platform support:
    - Windows: pathlib + shutil (cross-platform stdlib)
    - macOS:   pathlib + shutil (cross-platform stdlib)
    - Linux:   pathlib + shutil (cross-platform stdlib)

Design Decisions:
    - All public methods are async (run_in_executor for blocking file I/O)
    - Returns True on success, False on failure — never raises for normal failures
    - Safety checks block operations on system paths (OS-specific)
    - Path resolution: expand ~ and env vars, resolve to absolute path
    - Raises RuntimeError only on mobile platforms (android/ios)

Performance Characteristics:
    - Time Complexity: O(1) for single-file ops; O(n) for recursive directory ops
    - Space Complexity: O(1) per operation (streaming where possible)
    - Latency: bounded by underlying filesystem I/O

Author: Agent Guru Team
Date: 2026-03-20
"""
from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — blocked system path prefixes per platform
# ---------------------------------------------------------------------------

_BLOCKED_PATHS_WINDOWS: tuple[str, ...] = (
    r"c:\windows",
    r"c:\system32",
    r"c:\program files",
    r"c:\program files (x86)",
)

_BLOCKED_PATHS_MACOS: tuple[str, ...] = (
    "/system",
    "/library",
    "/usr",
    "/bin",
    "/sbin",
    "/etc",
)

_BLOCKED_PATHS_LINUX: tuple[str, ...] = (
    "/etc",
    "/sys",
    "/proc",
    "/usr",
    "/bin",
    "/sbin",
    "/boot",
    "/dev",
)

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

_PLATFORM_CACHE: Optional[str] = None


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
                ["uname", "-o"], capture_output=True, text=True, timeout=1
            )
            if "android" in out.stdout.lower():
                result = "android"
            else:
                result = "linux"
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
    # Strip null bytes — they cause ValueError on Windows path resolution
    cleaned = raw.replace("\x00", "")
    expanded = os.path.expandvars(os.path.expanduser(cleaned))
    return Path(expanded).resolve()


def _is_blocked(path: Path, plat: str, raw: str = "") -> bool:
    """Return True if *path* is a blocked system path for *plat*.

    Also blocks the root directory itself (``/`` or ``C:\\``).
    Uses *raw* (the original unexpanded path string) as a fallback for
    Unix-style path checks when running on Windows, where ``Path.resolve()``
    may rewrite Unix paths relative to the current drive.

    Args:
        path: Resolved absolute path to check.
        plat: Platform identifier.
        raw: Optional original path string before resolution (for cross-OS tests).

    Returns:
        ``True`` if the path is blocked, ``False`` otherwise.
    """
    path_str = str(path)

    # Block root directory
    if path == path.parent:
        logger.warning("Blocked operation on root directory: %s", path_str)
        return True

    if plat == "windows":
        path_lower = path_str.lower()
        for blocked in _BLOCKED_PATHS_WINDOWS:
            if path_lower == blocked or path_lower.startswith(blocked + os.sep):
                logger.warning("Blocked system path (Windows): %s", path_str)
                return True
    elif plat == "macos":
        # macOS paths are case-insensitive — compare lowercased
        path_fwd = path_str.replace("\\", "/").lower()
        raw_clean = raw.replace("\x00", "")
        candidates = {path_fwd, raw_clean.replace("\\", "/").lower()}
        for blocked in _BLOCKED_PATHS_MACOS:
            blocked_lower = blocked.lower()
            for candidate in candidates:
                if candidate == blocked_lower or candidate.startswith(blocked_lower + "/"):
                    logger.warning("Blocked system path (macOS): %s", path_str)
                    return True
    else:  # linux / unknown — case-sensitive
        path_fwd = path_str.replace("\\", "/")
        raw_clean = raw.replace("\x00", "")
        candidates = {path_fwd, raw_clean.replace("\\", "/")}
        for blocked in _BLOCKED_PATHS_LINUX:
            for candidate in candidates:
                if candidate == blocked or candidate.startswith(blocked + "/"):
                    logger.warning("Blocked system path (Linux): %s", path_str)
                    return True

    return False


# ---------------------------------------------------------------------------
# DesktopFileController
# ---------------------------------------------------------------------------


class DesktopFileController:
    """Async controller for desktop file and directory operations.

    Supports Windows, macOS, and Linux.  Raises :class:`RuntimeError` when
    instantiated on Android or iOS.

    Safety checks prevent operations on OS system paths.  Path arguments
    support ``~`` expansion and environment variable substitution.

    Example::

        ctrl = DesktopFileController()
        await ctrl.initialize()

        ok = await ctrl.create_file("~/notes.txt", "Hello!")
        ok = await ctrl.copy_file("~/notes.txt", "~/notes_backup.txt")
        ok = await ctrl.delete_file("~/notes.txt")

        await ctrl.shutdown()

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
                f"DesktopFileController is not supported on mobile "
                f"platform '{self._platform}'. Use MobileFileController instead."
            )

        logger.info("DesktopFileController created — platform=%s", self._platform)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the controller.

        Idempotent — safe to call multiple times.
        """
        if self._initialized:
            logger.debug("DesktopFileController already initialized")
            return

        self._initialized = True
        logger.info("DesktopFileController initialized — platform=%s", self._platform)

    async def shutdown(self) -> None:
        """Shut down the controller and release resources."""
        self._initialized = False
        logger.info("DesktopFileController shut down")

    # ------------------------------------------------------------------
    # Public API — file operations
    # ------------------------------------------------------------------

    async def create_file(self, path: str, content: str = "") -> bool:
        """Create a file at *path* with optional *content*.

        Creates parent directories if they do not exist.

        Args:
            path: Destination file path (supports ``~`` and env vars).
            content: Initial file content (default empty string).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.
        """
        resolved = _resolve_path(path)
        if _is_blocked(resolved, self._platform, raw=path):
            return False

        logger.info("create_file: %s", resolved)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._blocking_create_file, resolved, content)
            return True
        except Exception as exc:
            logger.error("create_file(%s) failed: %s", resolved, exc)
            return False

    async def delete_file(self, path: str) -> bool:
        """Delete the file at *path*.

        Args:
            path: File path to delete (supports ``~`` and env vars).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.
        """
        resolved = _resolve_path(path)
        if _is_blocked(resolved, self._platform, raw=path):
            return False

        logger.info("delete_file: %s", resolved)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._blocking_delete_file, resolved)
            return True
        except Exception as exc:
            logger.error("delete_file(%s) failed: %s", resolved, exc)
            return False

    async def move_file(self, src: str, dst: str) -> bool:
        """Move a file from *src* to *dst*.

        Args:
            src: Source file path (supports ``~`` and env vars).
            dst: Destination file path (supports ``~`` and env vars).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.
        """
        resolved_src = _resolve_path(src)
        resolved_dst = _resolve_path(dst)

        if _is_blocked(resolved_src, self._platform, raw=src) or _is_blocked(resolved_dst, self._platform, raw=dst):
            return False

        logger.info("move_file: %s → %s", resolved_src, resolved_dst)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._blocking_move_file, resolved_src, resolved_dst
            )
            return True
        except Exception as exc:
            logger.error("move_file(%s → %s) failed: %s", resolved_src, resolved_dst, exc)
            return False

    async def copy_file(self, src: str, dst: str) -> bool:
        """Copy a file from *src* to *dst*.

        Args:
            src: Source file path (supports ``~`` and env vars).
            dst: Destination file path (supports ``~`` and env vars).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.
        """
        resolved_src = _resolve_path(src)
        resolved_dst = _resolve_path(dst)

        if _is_blocked(resolved_src, self._platform, raw=src) or _is_blocked(resolved_dst, self._platform, raw=dst):
            return False

        logger.info("copy_file: %s → %s", resolved_src, resolved_dst)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._blocking_copy_file, resolved_src, resolved_dst
            )
            return True
        except Exception as exc:
            logger.error("copy_file(%s → %s) failed: %s", resolved_src, resolved_dst, exc)
            return False

    async def rename_file(self, path: str, new_name: str) -> bool:
        """Rename a file to *new_name* within the same directory.

        Args:
            path: Existing file path (supports ``~`` and env vars).
            new_name: New filename (basename only, no directory component).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.
        """
        resolved = _resolve_path(path)
        if _is_blocked(resolved, self._platform, raw=path):
            return False

        new_path = resolved.parent / new_name
        if _is_blocked(new_path, self._platform):
            return False

        logger.info("rename_file: %s → %s", resolved, new_path)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._blocking_rename_file, resolved, new_path
            )
            return True
        except Exception as exc:
            logger.error("rename_file(%s → %s) failed: %s", resolved, new_path, exc)
            return False

    # ------------------------------------------------------------------
    # Public API — directory operations
    # ------------------------------------------------------------------

    async def create_directory(self, path: str) -> bool:
        """Create a directory at *path* (including parents).

        Args:
            path: Directory path to create (supports ``~`` and env vars).

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.
        """
        resolved = _resolve_path(path)
        if _is_blocked(resolved, self._platform, raw=path):
            return False

        logger.info("create_directory: %s", resolved)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._blocking_create_directory, resolved)
            return True
        except Exception as exc:
            logger.error("create_directory(%s) failed: %s", resolved, exc)
            return False

    async def delete_directory(self, path: str, recursive: bool = False) -> bool:
        """Delete a directory at *path*.

        Args:
            path: Directory path to delete (supports ``~`` and env vars).
            recursive: If ``True``, delete directory and all contents.
                If ``False``, only delete empty directories.

        Returns:
            ``True`` on success, ``False`` on failure or blocked path.
        """
        resolved = _resolve_path(path)
        if _is_blocked(resolved, self._platform, raw=path):
            return False

        logger.info("delete_directory: %s (recursive=%s)", resolved, recursive)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._blocking_delete_directory, resolved, recursive
            )
            return True
        except Exception as exc:
            logger.error("delete_directory(%s) failed: %s", resolved, exc)
            return False

    async def list_directory(self, path: str) -> list[str]:
        """List the contents of a directory.

        Args:
            path: Directory path to list (supports ``~`` and env vars).

        Returns:
            List of filenames (not full paths) in the directory.
            Returns an empty list on error or blocked path.
        """
        resolved = _resolve_path(path)
        if _is_blocked(resolved, self._platform, raw=path):
            return []

        logger.info("list_directory: %s", resolved)
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._blocking_list_directory, resolved)
        except Exception as exc:
            logger.error("list_directory(%s) failed: %s", resolved, exc)
            return []

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

    def _blocking_create_file(self, path: Path, content: str) -> None:
        """Create a file with content — blocking."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _blocking_delete_file(self, path: Path) -> None:
        """Delete a file — blocking."""
        path.unlink()

    def _blocking_move_file(self, src: Path, dst: Path) -> None:
        """Move a file — blocking."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    def _blocking_copy_file(self, src: Path, dst: Path) -> None:
        """Copy a file — blocking."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))

    def _blocking_rename_file(self, src: Path, dst: Path) -> None:
        """Rename a file — blocking."""
        src.rename(dst)

    def _blocking_create_directory(self, path: Path) -> None:
        """Create a directory (with parents) — blocking."""
        path.mkdir(parents=True, exist_ok=True)

    def _blocking_delete_directory(self, path: Path, recursive: bool) -> None:
        """Delete a directory — blocking."""
        if recursive:
            shutil.rmtree(str(path))
        else:
            path.rmdir()

    def _blocking_list_directory(self, path: Path) -> list[str]:
        """List directory contents — blocking."""
        return [entry.name for entry in path.iterdir()]
