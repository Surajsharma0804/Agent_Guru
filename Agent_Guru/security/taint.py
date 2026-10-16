"""Which parts of a tool call came from outside text rather than from the owner.

Every call that changes something already waits for the owner's yes, but
the question read back the arguments as if the owner had chosen them. A
web page, a mail or another tool's output can carry an address, a link or
a command ("send the report to x@example.net"); if the model copies it
into a call, the owner heard an ordinary "Should I run send_email with
..." and had no way to know the address was the page's, not theirs.

TaintTracker remembers the text each tool returned this turn. find()
looks for argument values that overlap that text and are not in what the
owner said: long shared runs of characters, and short tokens that are
worth stealing on their own (an email address, a URL, a long number, a
path). The tool loop names the source and the copied part in the
confirmation question. It is a label for the owner's decision, not a
filter: the call still runs if the owner says yes.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

#: Shared runs at least this long count as copied text.
MIN_RUN = 24
#: How much of each tool output is kept to compare against.
MAX_KEPT = 20_000

_TOKEN = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"          # email address
    r"|https?://[^\s\"'<>]+"                 # URL
    r"|(?<!\w)\+?\d[\d \-]{5,}\d(?!\w)"       # phone or account number
    r"|[A-Za-z]:[\\/][^\s\"'<>|]+"           # Windows path
)


@dataclass(frozen=True, slots=True)
class Taint:
    """A part of a call's arguments that matches outside text."""

    source: str
    excerpt: str


def _normal(text: str) -> str:
    return " ".join(text.lower().split())


def _strings(value: Any, depth: int = 0) -> Iterator[str]:
    if depth > 8:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v, depth + 1)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v, depth + 1)


def _shared_run(needle: str, haystack: str, minimum: int) -> str:
    """The first run of at least *minimum* characters of *needle* found in *haystack*, or ""."""
    if len(needle) < minimum:
        return ""
    step = max(1, minimum // 2)
    for start in range(0, len(needle) - minimum + 1, step):
        piece = needle[start:start + minimum]
        if piece.strip() and piece in haystack:
            end = start + minimum
            while end < len(needle) and needle[start:end + 1] in haystack:
                end += 1
            return needle[start:end]
    return ""


class TaintTracker:
    """Outside text seen this turn, by source; one per tool loop."""

    def __init__(self) -> None:
        self._seen: list[tuple[str, str]] = []

    def record(self, source: str, text: str) -> None:
        if text and text.strip():
            self._seen.append((source, _normal(text)[:MAX_KEPT]))

    def find(self, arguments: Any, owner_text: str = "") -> list[Taint]:
        """Parts of *arguments* that match recorded outside text and do not appear in *owner_text*."""
        owner = _normal(owner_text)
        found: list[Taint] = []
        for value in _strings(arguments):
            text = _normal(value)
            if not text or text in owner:
                continue
            for source, seen in self._seen:
                excerpt = ""
                for token in _TOKEN.findall(value):
                    t = _normal(token)
                    if t in seen and t not in owner:
                        excerpt = token
                        break
                if not excerpt:
                    run = _shared_run(text, seen, MIN_RUN)
                    if run and run not in owner:
                        excerpt = run
                if excerpt and all(f.excerpt != excerpt for f in found):
                    found.append(Taint(source=source, excerpt=excerpt[:80]))
        return found
