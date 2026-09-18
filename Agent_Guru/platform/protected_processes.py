"""Module: agent_guru.platform.protected_processes
Purpose: Single source of truth for the set of process names AGENT_GURU must
never terminate, no matter which controller or code path is asking.

Why this module exists:
    Two independent controllers can end a process: ApplicationController
    (platform/controllers/application_control.py, used for voice/text
    commands like "close notepad") and ProcessManager
    (platform/process_manager.py, a lower-level process-management API).
    Both need the identical safety rule -- killing any of these processes
    doesn't close "an app", it takes down the OS shell or a core system
    service, and on some platforms can make the machine unusable until a
    reboot. Keeping that list as two independently-maintained copies is
    exactly the kind of duplication that lets them drift apart: a name
    added to one guard after an incident but not the other leaves a real
    gap. This module is the one place the set is defined; every controller
    that can terminate a process imports it from here instead of keeping
    its own copy.

Scope:
    This module intentionally has zero dependencies on either controller
    (or anything else in the codebase) so that both can import it without
    creating a layering problem or a circular import.
"""

from __future__ import annotations

# Process names that must never be terminated by any AGENT_GURU-controlled
# path (close_application, taskkill fallback, ProcessManager.terminate_process,
# or any future caller). Matched case-insensitively against the ACTUAL
# resolved process name -- not the caller's raw input -- right before any
# termination call; see application_control.py's close_application()/
# _taskkill_by_name() and process_manager.py's terminate_process() for why
# checking only the raw input string is not sufficient (a friendly name
# resolves to these exact executables via alias tables).
PROTECTED_PROCESS_NAMES: frozenset[str] = frozenset({
    # IDE / this application's own toolchain -- killing these can drop the
    # session that's controlling AGENT_GURU itself.
    "kiro",
    "code.exe",
    # Windows shell and core OS services.
    "explorer.exe",
    "winlogon.exe",
    "csrss.exe",
    "lsass.exe",
    "services.exe",
    "svchost.exe",
    "system",
    "smss.exe",
    "wininit.exe",
    # POSIX (macOS/Linux) init / PID-1 equivalents -- process_manager.py is
    # cross-platform (uses psutil, not taskkill), so it can actually be
    # asked to terminate these on macOS/Linux, unlike the Windows-only
    # taskkill fallback in application_control.py.
    "init",
    "systemd",
    "launchd",
})


def is_protected_process_name(name: str | None) -> bool:
    """Return True if *name* (a resolved process/executable name) is protected.

    Args:
        name: The actual resolved process name to check (case-insensitive,
            leading/trailing whitespace ignored). Pass the real name looked
            up from the OS/psutil, not the caller's raw input string --
            checking raw input alone lets a friendly name that resolves to
            a protected executable slip past this check entirely.

    Returns:
        True if the name (after trimming and lowercasing) is in the
        protected set; False for an empty/None name or any other name.

    """
    return bool(name) and name.strip().lower() in PROTECTED_PROCESS_NAMES
