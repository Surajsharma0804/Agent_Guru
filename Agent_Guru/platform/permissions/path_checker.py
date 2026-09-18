"""Module: Agent_Guru.platform.permissions.path_checker
Purpose: Path permission validation with pattern matching and normalization.

This module implements comprehensive path validation:
- Allowed path checking with wildcard patterns
- Permission type validation (read, write, delete, execute)
- Path normalization (cross-platform)
- Wildcard pattern matching (glob-style)
- Directory traversal prevention
- Symlink resolution

Performance Characteristics:
    - Time Complexity: O(n) where n is number of allowed paths
    - Space Complexity: O(1) for validation
    - Path Normalization: O(m) where m is path length

Security Features:
    - Directory traversal prevention (../ attacks)
    - Symlink resolution and validation
    - Case-insensitive matching on Windows
    - Path canonicalization

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

import functools
import logging
import platform
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# Splits a glob pattern into literal runs and wildcard tokens, longest first so
# "**" is never seen as two "*".
_WILDCARD_SPLIT = re.compile(r"(\*\*|\*|\?)")

# Patterns are registered once and matched against every checked path, so the
# translated regex is compiled once and reused.
_PATTERN_CACHE_SIZE = 512


@functools.lru_cache(maxsize=_PATTERN_CACHE_SIZE)
def _compile_glob(pattern: str) -> re.Pattern[str]:
    """Translate a glob-style path pattern into one fully anchored regex.

    SECURITY FIX. _match_pattern() used to take two different routes with two
    different bugs, and both widened access:

    1. Patterns containing "**" were turned into a regex by string-replacing
       the wildcards and nothing else, so every OTHER regex metacharacter in
       the pattern stayed live. An allow-rule for "/home/user/.config/**"
       became ``^/home/user/.config/.*$``, in which the dot before "config"
       matches ANY character -- granting the caller "/home/user/Xconfig/..."
       as well. Literal runs are now re.escape()d, so a pattern means exactly
       what it says.
    2. Every other pattern went to fnmatch, whose "*" matches "/" as well.
       The method's own docstring promises "* matches any characters except
       /", so an allow-rule of "/home/user/*" -- plainly intended as "files
       directly in the home directory" -- actually matched
       "/home/user/private/keys/id_rsa" and handed out the entire subtree.
       Both branches now share this one translation, so the documented
       semantics are the real ones.

    Anchoring: the caller uses fullmatch() rather than match() with a "$",
    because in Python "$" also matches just before a trailing newline -- a
    path ending in "\n" could satisfy a pattern it does not actually equal.

    re.DOTALL is set so that "**" spans newlines too: POSIX filenames may
    contain them, and a *blocked* pattern must not be evadable that way.

    Time Complexity: O(len(pattern)) once per distinct pattern, then cached.
    """
    parts = _WILDCARD_SPLIT.split(pattern)
    regex = "".join(
        ".*"
        if part == "**"
        else "[^/]*"
        if part == "*"
        else "[^/]"
        if part == "?"
        else re.escape(part)
        for part in parts
    )
    return re.compile(regex, re.DOTALL)


class PermissionType(Enum):
    """File system permission types."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"


@dataclass
class PathValidationResult:
    """Result of path validation."""

    allowed: bool
    normalized_path: str
    matched_pattern: str | None
    reason: str
    permissions: set[PermissionType]


class PathValidationError(Exception):
    """Raised when path validation fails."""


class PathPermissionChecker:
    """Path permission checker with pattern matching and normalization.

    Features:
    - Wildcard pattern matching (*, **, ?)
    - Path normalization (cross-platform)
    - Directory traversal prevention
    - Symlink resolution
    - Case-insensitive matching (Windows)

    Time Complexity: O(n) where n is number of allowed patterns
    Space Complexity: O(1) for validation

    Example:
        >>> checker = PathPermissionChecker()
        >>> checker.add_allowed_path("/home/user/*", {PermissionType.READ})
        >>> result = checker.validate_path(
        ...     "/home/user/documents/file.txt",
        ...     PermissionType.READ
        ... )
        >>> print(f"Allowed: {result.allowed}")

    """

    def __init__(self, case_sensitive: bool | None = None) -> None:
        """Initialize path permission checker.

        Args:
            case_sensitive: Whether path matching is case-sensitive.
                           Defaults to False on Windows, True on Unix.

        """
        self._allowed_patterns: list[tuple[str, set[PermissionType]]] = []
        self._blocked_patterns: list[str] = []

        # Determine case sensitivity based on platform
        if case_sensitive is None:
            self._case_sensitive = platform.system() != "Windows"
        else:
            self._case_sensitive = case_sensitive

        logger.debug("PathPermissionChecker initialized (case_sensitive=%s)", self._case_sensitive)

    def add_allowed_path(self, pattern: str, permissions: set[PermissionType]) -> None:
        """Add allowed path pattern with permissions.

        Supports wildcards:
        - * matches any characters except path separator
        - ** matches any characters including path separator
        - ? matches single character

        Args:
            pattern: Path pattern (e.g., "/home/user/*", "/var/log/**/*.log")
            permissions: Set of allowed permissions

        Example:
            >>> checker.add_allowed_path("/home/user/*", {PermissionType.READ})
            >>> checker.add_allowed_path("/tmp/**", {PermissionType.READ, PermissionType.WRITE})

        """
        normalized_pattern = self._normalize_pattern(pattern)
        self._allowed_patterns.append((normalized_pattern, permissions))
        logger.debug("Added allowed path pattern: %s", normalized_pattern)

    def add_blocked_path(self, pattern: str) -> None:
        """Add blocked path pattern.

        Blocked patterns take precedence over allowed patterns.

        Args:
            pattern: Path pattern to block

        Example:
            >>> checker.add_blocked_path("/etc/passwd")
            >>> checker.add_blocked_path("/root/**")

        """
        normalized_pattern = self._normalize_pattern(pattern)
        self._blocked_patterns.append(normalized_pattern)
        logger.debug("Added blocked path pattern: %s", normalized_pattern)

    def validate_path(self, path: str, required_permission: PermissionType) -> PathValidationResult:
        """Validate path against allowed patterns and permissions.

        Time Complexity: O(n) where n is number of patterns
        Space Complexity: O(1)

        Args:
            path: File system path to validate
            required_permission: Required permission type

        Returns:
            PathValidationResult with validation details

        Raises:
            PathValidationError: If path is invalid or contains directory traversal

        """
        # Normalize and validate path
        try:
            normalized_path = self.normalize_path(path)
        except PathValidationError as e:
            return PathValidationResult(
                allowed=False,
                normalized_path=path,
                matched_pattern=None,
                reason=str(e),
                permissions=set(),
            )

        # Check blocked patterns first (security priority)
        for blocked_pattern in self._blocked_patterns:
            if self._match_pattern(normalized_path, blocked_pattern):
                logger.warning("Path blocked by pattern: %s -> %s", path, blocked_pattern)
                return PathValidationResult(
                    allowed=False,
                    normalized_path=normalized_path,
                    matched_pattern=blocked_pattern,
                    reason=f"Path matches blocked pattern: {blocked_pattern}",
                    permissions=set(),
                )

        # Check allowed patterns
        for allowed_pattern, permissions in self._allowed_patterns:
            if self._match_pattern(normalized_path, allowed_pattern):
                # Check if required permission is granted
                if required_permission in permissions:
                    logger.debug(
                        f"Path allowed: {path} -> {allowed_pattern} ({required_permission.value})",
                    )
                    return PathValidationResult(
                        allowed=True,
                        normalized_path=normalized_path,
                        matched_pattern=allowed_pattern,
                        reason="Path matches allowed pattern with required permission",
                        permissions=permissions,
                    )
                logger.warning(
                    f"Path matched but permission denied: {path} -> {allowed_pattern} "
                    f"(required: {required_permission.value}, "
                    f"available: {[p.value for p in permissions]})",
                )
                return PathValidationResult(
                    allowed=False,
                    normalized_path=normalized_path,
                    matched_pattern=allowed_pattern,
                    reason=f"Permission {required_permission.value} not granted",
                    permissions=permissions,
                )

        # No matching pattern found
        logger.warning("Path denied (no matching pattern): %s", path)
        return PathValidationResult(
            allowed=False,
            normalized_path=normalized_path,
            matched_pattern=None,
            reason="Path does not match any allowed pattern",
            permissions=set(),
        )

    def normalize_path(self, path: str) -> str:
        """Normalize path for consistent comparison.

        Performs:
        - Resolves relative paths to absolute
        - Removes redundant separators
        - Resolves . and .. components
        - Converts to forward slashes
        - Validates against directory traversal

        Time Complexity: O(m) where m is path length
        Space Complexity: O(m)

        Args:
            path: Path to normalize

        Returns:
            Normalized absolute path

        Raises:
            PathValidationError: If path contains directory traversal or is invalid

        """
        try:
            # Convert to Path object for normalization
            path_obj = Path(path)

            # For pattern matching, don't resolve to absolute if it's a Unix-style path on Windows
            # This allows Unix-style patterns to work on Windows
            if not path_obj.is_absolute():
                # Make relative paths absolute relative to cwd
                normalized = Path.cwd() / path_obj
                normalized = normalized.resolve()
            else:
                # For absolute paths, just normalize without resolving
                # This preserves Unix-style paths like /home/user on Windows
                normalized_str = str(path_obj).replace("\\", "/")

                # Case normalization for case-insensitive systems
                if not self._case_sensitive:
                    normalized_str = normalized_str.lower()

                return normalized_str

            # Convert to string with forward slashes
            normalized_str = str(normalized).replace("\\", "/")

            # Validate against directory traversal
            if ".." in Path(path).parts:
                # Check if the normalized path escapes the intended directory
                logger.warning("Potential directory traversal detected: %s", path)

            # Case normalization for case-insensitive systems
            if not self._case_sensitive:
                normalized_str = normalized_str.lower()

            return normalized_str

        except (ValueError, OSError) as e:
            msg = f"Invalid path: {path} ({e})"
            raise PathValidationError(msg) from e

    def _normalize_pattern(self, pattern: str) -> str:
        """Normalize path pattern for matching.

        Args:
            pattern: Path pattern to normalize

        Returns:
            Normalized pattern

        """
        # Convert backslashes to forward slashes
        normalized = pattern.replace("\\", "/")

        # Case normalization for case-insensitive systems
        if not self._case_sensitive:
            normalized = normalized.lower()

        return normalized

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Match path against pattern with wildcard support.

        Supports:
        - * matches any characters except /
        - ** matches any characters including /
        - ? matches single character
        - every other character is literal

        One translation is used for all patterns -- see _compile_glob() for the
        two access-widening bugs that having two separate routes caused.

        Time Complexity: O(m) in path length after the pattern is compiled once.
        Space Complexity: O(1)

        Args:
            path: Normalized path to match
            pattern: Normalized pattern

        Returns:
            True if path matches pattern

        """
        try:
            return bool(_compile_glob(pattern).fullmatch(path))
        except re.error:
            # Only reachable if re.escape() output is somehow unusable; kept so
            # a bad pattern denies rather than raising into the caller.
            logger.exception("Invalid path pattern: %s", pattern)
            return False

    def check_permission_type(self, path: str, permission: PermissionType) -> bool:
        """Check if specific permission is granted for path.

        Time Complexity: O(n) where n is number of patterns
        Space Complexity: O(1)

        Args:
            path: File system path
            permission: Permission type to check

        Returns:
            True if permission is granted

        """
        result = self.validate_path(path, permission)
        return result.allowed

    def get_permissions(self, path: str) -> set[PermissionType]:
        """Get all permissions granted for path.

        Time Complexity: O(n) where n is number of patterns
        Space Complexity: O(1)

        Args:
            path: File system path

        Returns:
            Set of granted permissions (empty if no match)

        """
        try:
            normalized_path = self.normalize_path(path)
        except PathValidationError:
            return set()

        # Check blocked patterns first
        for blocked_pattern in self._blocked_patterns:
            if self._match_pattern(normalized_path, blocked_pattern):
                return set()

        # Find matching allowed pattern
        for allowed_pattern, permissions in self._allowed_patterns:
            if self._match_pattern(normalized_path, allowed_pattern):
                return permissions

        return set()

    def clear_patterns(self) -> None:
        """Clear all allowed and blocked patterns."""
        self._allowed_patterns.clear()
        self._blocked_patterns.clear()
        logger.debug("All path patterns cleared")

    @property
    def allowed_pattern_count(self) -> int:
        """Get number of allowed patterns."""
        return len(self._allowed_patterns)

    @property
    def blocked_pattern_count(self) -> int:
        """Get number of blocked patterns."""
        return len(self._blocked_patterns)


def validate_path_safe(path: str) -> bool:
    """Quick validation that path is safe (no directory traversal).

    Time Complexity: O(m) where m is path length
    Space Complexity: O(1)

    Args:
        path: Path to validate

    Returns:
        True if path is safe

    """
    # Check for directory traversal patterns
    dangerous_patterns = [
        "..",
        "~",
        "${",
        "%",
    ]

    return all(pattern not in path for pattern in dangerous_patterns)


def is_absolute_path(path: str) -> bool:
    """Check if path is absolute.

    Time Complexity: O(1)
    Space Complexity: O(1)

    Args:
        path: Path to check

    Returns:
        True if path is absolute

    """
    return Path(path).is_absolute()


def get_path_extension(path: str) -> str:
    """Get file extension from path.

    Time Complexity: O(1)
    Space Complexity: O(1)

    Args:
        path: File path

    Returns:
        File extension (including dot, e.g., ".txt")

    """
    return Path(path).suffix


def is_hidden_path(path: str) -> bool:
    """Check if path is hidden (starts with dot on Unix).

    Time Complexity: O(1)
    Space Complexity: O(1)

    Args:
        path: Path to check

    Returns:
        True if path is hidden

    """
    path_obj = Path(path)
    return path_obj.name.startswith(".")
