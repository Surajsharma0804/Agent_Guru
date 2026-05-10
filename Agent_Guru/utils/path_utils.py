"""Shared path utilities for Agent Guru.

Provides safe path construction that prevents path traversal attacks (CWE-22)
by resolving and validating that any constructed path remains within a
designated base directory.

Performance Characteristics:
    - Time Complexity: O(1) — single Path.resolve() call
    - Space Complexity: O(1) — no caching or state

Security Guarantees:
    - Symlinks are fully resolved before the containment check
    - ``..`` sequences cannot escape the base directory
    - Raises ``ValueError`` on violation

Requirements: 2.2
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def safe_path(base: Path, untrusted: str) -> Path:
    """Safely construct a path within a base directory.

    Resolves the path and validates it stays within the base directory.
    Raises ``ValueError`` if the path would escape the base directory.

    Both ``base`` and the constructed path are fully resolved (symlinks
    expanded, ``..`` collapsed) before the containment check, so no
    traversal sequence can escape the intended directory.

    Args:
        base: The allowed base directory (must be absolute or will be resolved).
        untrusted: The untrusted path component from external input.

    Returns:
        Resolved ``Path`` that is guaranteed to be within ``base``.

    Raises:
        ValueError: If the resolved path escapes the base directory.

    Example::

        >>> from pathlib import Path
        >>> from Agent_Guru.utils.path_utils import safe_path
        >>> safe_path(Path("/data"), "user/file.txt")
        PosixPath('/data/user/file.txt')
        >>> safe_path(Path("/data"), "../../etc/passwd")  # raises ValueError

    """
    base_resolved = base.resolve()
    resolved = (base / untrusted).resolve()

    if not resolved.is_relative_to(base_resolved):
        msg = (
            f"Path traversal detected: '{untrusted}' resolves to '{resolved}' "
            f"which is outside base directory '{base_resolved}'"
        )
        raise ValueError(
            msg,
        )

    return resolved
