"""Safe subprocess wrapper for Agent Guru.

This module provides a hardened subprocess execution interface that
unconditionally disables shell interpretation, preventing OS command
injection (CWE-77/78/88).

Performance Characteristics:
    - Time Complexity: O(1) per call (excluding subprocess execution time)
    - Space Complexity: O(n) where n is the size of stdout/stderr output
    - No caching — each call spawns a fresh subprocess

Security Guarantees:
    - ``shell=False`` is enforced unconditionally; cannot be overridden by callers
    - String arguments are rejected at the boundary (TypeError raised)
    - Optional allowlist validation for user-supplied argument values

Requirements: 2.7
"""

from __future__ import annotations

import subprocess  # nosec B404
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def run_cmd(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an external command safely with ``shell=False`` enforced.

    Args:
        args: Command and arguments as a list of strings.  A bare string is
              rejected to prevent accidental shell-string usage.
        cwd: Working directory for the subprocess.  ``None`` inherits the
             current process directory.
        timeout: Maximum seconds to wait for the process.  Raises
                 ``subprocess.TimeoutExpired`` if exceeded.  Default: 30.
        check: If ``True`` (default), raise ``subprocess.CalledProcessError``
               when the process exits with a non-zero return code.

    Returns:
        ``subprocess.CompletedProcess`` with ``stdout`` and ``stderr`` as
        decoded strings.

    Raises:
        TypeError: If *args* is a string rather than a list.
        subprocess.CalledProcessError: If *check* is ``True`` and the process
            exits with a non-zero return code.
        subprocess.TimeoutExpired: If the process does not finish within
            *timeout* seconds.

    Example::

        result = run_cmd(["git", "status", "--short"], cwd=Path("/repo"))
        print(result.stdout)

    """
    if isinstance(args, str):
        msg = (
            "run_cmd() requires a list of strings, not a bare string. "
            "Passing a string would enable shell interpretation — use "
            "args=['cmd', 'arg1', 'arg2'] instead."
        )
        raise TypeError(
            msg,
        )

    return subprocess.run(  # noqa: S603
        args,
        shell=False,  # unconditional — never allow shell interpretation  # nosec B603
        cwd=cwd,
        timeout=timeout,
        check=check,
        capture_output=True,
        text=True,
    )


def validate_arg(value: str, allowlist: set[str] | None = None) -> str:
    """Validate a user-supplied argument value before passing to a subprocess.

    When *allowlist* is provided the value must be an exact member of that set.
    When *allowlist* is ``None`` the function simply returns *value* unchanged
    (useful as a pass-through placeholder that can be tightened later).

    Args:
        value: The user-supplied argument string to validate.
        allowlist: Optional set of permitted values.  If supplied and *value*
                   is not a member, ``ValueError`` is raised.

    Returns:
        The validated *value* string, unchanged.

    Raises:
        ValueError: If *allowlist* is provided and *value* is not in it.

    Example::

        action = validate_arg(user_action, allowlist={"start", "stop", "restart"})
        run_cmd(["systemctl", action, "myservice"])

    """
    if allowlist is not None and value not in allowlist:
        msg = (
            f"Argument {value!r} is not in the permitted allowlist. "
            f"Allowed values: {sorted(allowlist)}"
        )
        raise ValueError(
            msg,
        )
    return value
