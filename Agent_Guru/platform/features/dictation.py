"""Voice dictation — type anywhere by speaking.

This lets the user say "dictate: hello world" or "type this: ..." and the
text gets typed into whatever app is currently focused. It's one of the
most useful features that Alexa/Siri/Cortana all support on desktop.

Also handles clipboard operations:
  "read my clipboard" → speaks the clipboard content
  "summarize my clipboard" → LLM summarizes clipboard text
  "fix my clipboard" → LLM fixes grammar/spelling in clipboard text
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def is_dictation_command(transcript: str) -> bool:
    """Return True if the transcript is a dictation command."""
    t = transcript.strip().lower()
    return bool(
        re.match(
            r"^(dictate|type this|type:|write this|input|say this|paste this)[:\s]",
            t,
            re.IGNORECASE,
        ),
    )


def extract_dictation_text(transcript: str) -> str | None:
    """Extract the text to type from a dictation command.

    Examples:
        "dictate: hello world" → "hello world"
        "type this: my name is John" → "my name is John"

    """
    m = re.match(
        r"^(?:dictate|type this|type|write this|input|say this|paste this)[:\s]+(.+)",
        transcript.strip(),
        re.IGNORECASE | re.DOTALL,
    )
    return m.group(1).strip() if m else None


def is_clipboard_command(transcript: str) -> bool:
    """Return True if the transcript is a clipboard command."""
    t = transcript.strip().lower()
    return bool(
        re.search(
            r"\b(clipboard|what.s in my clipboard|read my clipboard|"
            r"summarize my clipboard|fix my clipboard|correct my clipboard|"
            r"improve my clipboard)\b",
            t,
            re.IGNORECASE,
        ),
    )


def get_clipboard_text() -> str | None:
    """Read the current clipboard content."""
    try:
        import pyperclip  # type: ignore[import]

        text = pyperclip.paste()
        return text.strip() if text else None
    except Exception:
        logger.exception("Operation failed")

    # Windows fallback
    try:
        import win32clipboard  # type: ignore[import]

        win32clipboard.OpenClipboard()
        try:
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return text.strip() if text else None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        logger.exception("Operation failed")

    return None


def set_clipboard_text(text: str) -> bool:
    """Write text to the clipboard."""
    try:
        import pyperclip  # type: ignore[import]

        pyperclip.copy(text)
        return True
    except Exception:
        logger.exception("Operation failed")

    try:
        import win32clipboard  # type: ignore[import]

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            return True
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        logger.exception("Operation failed")

    return False


def get_clipboard_action(transcript: str) -> str:
    """Return the clipboard action: 'read', 'summarize', 'fix', or 'unknown'."""
    t = transcript.lower()
    if re.search(r"\b(read|what.s in|show)\b", t):
        return "read"
    if re.search(r"\b(summarize|summary|shorten)\b", t):
        return "summarize"
    if re.search(r"\b(fix|correct|improve|clean up|grammar|spelling)\b", t):
        return "fix"
    return "read"  # default
