"""Shared path utilities for Agent Guru.

Provides safe path construction that prevents path traversal attacks (CWE-22)
by resolving and validating that any constructed path remains within a
designated base directory.

Performance Characteristics:
    - Time Complexity: O(1) - single Path.resolve() call
    - Space Complexity: O(1) - no caching or state

Security Guarantees:
    - Symlinks are fully resolved before the containment check
    - ``..`` sequences cannot escape the base directory
    - Raises ``ValueError`` on violation

Requirements: 2.2
"""

from __future__ import annotations

import os
from pathlib import Path


def app_data_dir(*parts: str, create: bool = True) -> Path:
    """Return Agent Guru's per-user data directory, optionally with children.

    ``%LOCALAPPDATA%\\agent_guru`` on Windows, ``$XDG_DATA_HOME/agent_guru``
    (falling back to ``~/.local/share/agent_guru``) on Linux and macOS.

    This logic was written out four separate times -- in
    core/error_handler.py, memory/conversation_memory.py,
    memory/memory_manager.py and platform/controllers/messaging_controller.py,
    the last of which carries a comment saying it "mirrors" another copy. A
    fifth place needed it (reasoning/memory/vector_db.py defaulted to a
    RELATIVE "./memory_db", so the vector store landed wherever the process
    happened to be started from -- a different directory meant a different,
    empty long-term memory). One definition instead.

    Args:
        *parts: Path components to append under the data directory.
        create: Create the directory (the parent of the final component when
            that component looks like a file, i.e. has a suffix).

    Returns:
        Absolute path inside the per-user data directory.

    """
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")

    target = base.joinpath("agent_guru", *parts)
    if create:
        directory = target.parent if target.suffix else target
        directory.mkdir(parents=True, exist_ok=True)
    return target


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
