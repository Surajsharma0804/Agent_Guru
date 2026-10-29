"""A typed answer prints even when the console cannot show every character in it.

Piped or redirected on Windows, stdout is cp1252, and `python -m Agent_Guru ask "yes"` died with
UnicodeEncodeError on a reply holding an emoji: the turn had run, the owner saw a traceback.
"""

from __future__ import annotations

import io
import sys

from Agent_Guru.utils import commands


def _cp1252_stdout(monkeypatch) -> io.BytesIO:
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252", errors="strict"))
    return raw


def test_a_reply_with_an_emoji_prints_on_a_cp1252_console(monkeypatch):
    raw = _cp1252_stdout(monkeypatch)
    commands._show({"reply": "Scheduled it \U0001f609 every hour.", "awaiting_reply": True})
    sys.stdout.flush()
    out = raw.getvalue().decode("cp1252")
    assert "Scheduled it ? every hour." in out
    assert "(It is waiting for your answer.)" in out


def test_sources_after_such_a_reply_still_print(monkeypatch):
    raw = _cp1252_stdout(monkeypatch)
    commands._show({"reply": "नमस्ते", "sources": [{"id": "S1", "title": "Delhi", "url": "https://example.com/d"}]})
    sys.stdout.flush()
    assert "[S1] Delhi https://example.com/d" in raw.getvalue().decode("cp1252")
