"""Module: agent_guru.platform.window_identifiers
Purpose: Single source of truth for sanitizing window-identifier strings
before they are used in any OS-level scripting/shell context.

Why this module exists:
    A window identifier (a window title, or a substring of one) is
    fundamentally untrusted, attacker-influenceable text: it typically
    comes straight from a voice transcription or a text command ("snap
    Chrome to the left half"), and on top of that, a REAL window's title
    is itself attacker-influenceable in the ordinary course of using a
    computer -- a browser tab's title, for instance, is whatever the
    visited web page set it to. platform/controllers/window_management.py
    embeds this string into a scripting context that is NOT a simple
    string comparison -- macOS AppleScript via `osascript -e <script>`,
    where AppleScript has its own `do shell script` command capable of
    running arbitrary shell commands. An identifier containing a stray `"`
    can break out of an AppleScript string literal; from there, arbitrary
    AppleScript (and via `do shell script`, arbitrary shell commands) can
    be smuggled in.

    platform/controllers/application_control.py independently already has
    an equivalent `_sanitize_window_identifier` static method for the same
    underlying reason (it has its own macOS AppleScript window operations).
    It is not switched to import this module in this pass, specifically to
    avoid touching an already-audited, already-tested file for a change
    that isn't required to fix the vulnerability at hand -- but the two
    implementations are intentionally kept behaviorally equivalent, and
    consolidating application_control.py onto this shared module (removing
    its own copy) is flagged as a follow-up: two independently-maintained
    copies of the same safety-critical validation is exactly the kind of
    duplication that lets them drift apart over time.

Design:
    This takes the conservative, deny-list approach already established in
    application_control.py (reject a small set of characters that have
    special meaning in shells/AppleScript/most scripting contexts, rather
    than trying to context-specifically escape for each sink) -- simpler
    to reason about correctly, and matches the existing codebase
    convention.
"""

from __future__ import annotations

# Characters that have special meaning in a shell command line, an
# AppleScript string literal, or similar scripting contexts. Rejecting
# these outright (rather than trying to escape them per-sink) is
# deliberately conservative: a real window title essentially never
# legitimately needs a backtick, a pipe, or a null byte, but a malicious
# or malformed one absolutely might.
_DANGEROUS_CHARS: tuple[str, ...] = (
    "\n", "\r", ";", "&", "|", "`", "$", "(", ")", "<", ">", '"', "'", "\\",
)

_MAX_LENGTH = 256


def sanitize_window_identifier(window_identifier: str) -> str:
    """Validate and normalize a window identifier before any OS-level use.

    Args:
        window_identifier: Raw window identifier (title or substring),
            typically sourced from a voice/text command.

    Returns:
        The identifier with leading/trailing whitespace stripped.

    Raises:
        ValueError: If the identifier is empty, contains a null byte, a
            character considered dangerous in shell/scripting contexts, or
            exceeds the maximum allowed length.

    """
    if not window_identifier or not window_identifier.strip():
        msg = "Window identifier cannot be empty"
        raise ValueError(msg)

    if "\x00" in window_identifier:
        msg = "Window identifier contains null bytes"
        raise ValueError(msg)

    for char in _DANGEROUS_CHARS:
        if char in window_identifier:
            msg = f"Window identifier contains dangerous character: {char!r}"
            raise ValueError(msg)

    if len(window_identifier) > _MAX_LENGTH:
        msg = f"Window identifier too long (max {_MAX_LENGTH} characters)"
        raise ValueError(msg)

    return window_identifier.strip()
