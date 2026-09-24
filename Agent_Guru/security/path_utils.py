"""Safe path resolver for Agent Guru.

This module provides canonicalized path resolution that prevents path
traversal attacks (CWE-22) by asserting that any resolved path remains
within a designated base directory.

Performance Characteristics:
    - Time Complexity: O(1) - single ``Path.resolve()`` call
    - Space Complexity: O(1) - no caching or state

Security Guarantees:
    - Symlinks are fully resolved before the containment check
    - ``..`` sequences cannot escape the base directory
    - Raises ``PermissionError`` (not a silent fallback) on violation

Requirements: 2.8
"""

from __future__ import annotations

from pathlib import Path


def safe_path(user_input: str | Path, base_dir: Path) -> Path:
    """Resolve *user_input* and assert it stays within *base_dir*.

    Both *user_input* and *base_dir* are fully resolved (symlinks expanded,
    ``..`` collapsed) before the containment check so that no traversal
    sequence can escape the intended directory.

    Args:
        user_input: A path supplied by the user (string or ``Path``).
        base_dir: The directory that the resolved path must reside within.
                  Must be an absolute path or resolvable to one.

    Returns:
        The fully resolved ``Path`` object, guaranteed to be relative to
        (or equal to) *base_dir*.

    Raises:
        ValueError: When the resolved path escapes *base_dir*.

    Example::

        from pathlib import Path
        from Agent_Guru.security.path_utils import safe_path

        DATA_DIR = Path("/var/app/data").resolve()
        p = safe_path(user_filename, DATA_DIR)
        with open(p) as fh:
            ...

    """
    candidate = Path(user_input)
    # Relative paths are resolved within base_dir, not the CWD
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    resolved = candidate.resolve()
    resolved_base = base_dir.resolve()

    if not resolved.is_relative_to(resolved_base):
        msg = (
            f"Path traversal detected: {user_input!r} resolves to "
            f"{resolved!r} which is outside the permitted base "
            f"directory {resolved_base!r}."
        )
        raise ValueError(
            msg,
        )

    return resolved
