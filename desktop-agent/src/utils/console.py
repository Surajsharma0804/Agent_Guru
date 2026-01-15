"""
Console Utilities

Production-grade console output handling with:
- Unicode fallback for Windows
- Cross-platform compatibility
- Consistent formatting
- Error handling
"""

import sys


def safe_print(text: str, end: str = "\n", flush: bool = False):
    """
    Print text with fallback for Unicode issues on Windows.

    On Windows, the console may not support UTF-8 encoding by default.
    This function handles Unicode characters gracefully by falling back
    to ASCII equivalents when encoding fails.

    Args:
        text: Text to print
        end: String appended after text (default: newline)
        flush: Whether to flush output buffer
    """
    try:
        print(text, end=end, flush=flush)
    except UnicodeEncodeError:
        # Replace Unicode characters with ASCII equivalents
        replacements = {
            "✓": "[OK]",
            "✗": "[X]",
            "⚠": "[!]",
            "→": "->",
            "←": "<-",
            "↓": "|",
            "↑": "^",
            "•": "*",
            "◆": "+",
            "▶": ">",
            "◀": "<",
            "★": "*",
            "☆": "*",
            "♦": "+",
            "♥": "<3",
            "♠": "^",
            "♣": "+",
            "─": "-",
            "│": "|",
            "┌": "+",
            "┐": "+",
            "└": "+",
            "┘": "+",
            "├": "+",
            "┤": "+",
            "┬": "+",
            "┴": "+",
            "┼": "+",
            "═": "=",
            "║": "|",
            "╔": "+",
            "╗": "+",
            "╚": "+",
            "╝": "+",
            "╠": "+",
            "╣": "+",
            "╦": "+",
            "╩": "+",
            "╬": "+",
        }

        for unicode_char, ascii_char in replacements.items():
            text = text.replace(unicode_char, ascii_char)

        print(text, end=end, flush=flush)


def init_console_encoding():
    """
    Initialize console encoding for Unicode support.

    On Windows, attempts to set UTF-8 encoding for stdout/stderr.
    Falls back gracefully if this fails.

    This should be called early in the application startup.
    """
    if sys.platform == "win32":
        try:
            # Skip if stdout/stderr are already wrapped
            if hasattr(sys.stdout, "buffer"):
                # Try to enable UTF-8 mode
                import codecs

                sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
                sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")
            return True
        except Exception as e:
            # Fallback: use safe_print for all output
            print(f"Warning: Could not set UTF-8 encoding: {e}")
            return False
    return True


# Export
__all__ = ["safe_print", "init_console_encoding"]
