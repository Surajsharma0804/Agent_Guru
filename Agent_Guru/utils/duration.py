"""The one place spoken durations become numbers: whole seconds, as an int.

Before this, three components each turned "5 minutes" into something
different. The fast router produced {'value': 5, 'unit': 'minutes'}, the NER
extractor and the LLM fallback produced seconds, and the live reminder parser
produced minutes or seconds. A consumer had to know which producer it was
talking to, and none of them understood compound durations: "1 hour 30
minutes" reached the timer as 30 minutes from one producer and was not
recognised by another, "1 minute 30 seconds" became 1 minute or 30 seconds,
and the live reminder parser did not understand hours at all.

The contract: a duration is an int number of seconds. parse_duration reads
it from text; to_seconds converts any representation a producer may still
hold. Nothing downstream interprets units.
"""

from __future__ import annotations

import re
from typing import Any

_UNIT_SECONDS = {
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
}
# "m" is left out on purpose: in speech it is as likely to be "metres" or the
# start of "am"/"pm" handling elsewhere as "minutes".
_UNIT = r"(?:hours?|hrs?|h|minutes?|mins?|seconds?|secs?|s)\b"
_PART = rf"\d+(?:\.\d+)?\s*{_UNIT}"
#: A whole duration phrase, possibly compound ("1 hour, 30 minutes and 10
#: seconds"), for embedding in other patterns. It has no capturing groups.
DURATION_PATTERN = rf"{_PART}(?:\s*(?:,\s*)?(?:and\s+)?{_PART})*"

_PART_RE = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNIT})", re.IGNORECASE)
_DURATION_RE = re.compile(DURATION_PATTERN, re.IGNORECASE)

# Spoken forms rewritten into number + unit before matching. Order matters:
# "an hour and a half" before "an hour", "half an hour" before "an hour".
_WORDS = [
    (re.compile(r"\b(?:an?|one)\s+hours?\s+and\s+a\s+half\b", re.IGNORECASE), "90 minutes"),
    (re.compile(r"\bhalf\s+an?\s+hour\b", re.IGNORECASE), "30 minutes"),
    (re.compile(r"\bquarter\s+of\s+an\s+hour\b", re.IGNORECASE), "15 minutes"),
    (re.compile(r"\ban?\s+hour\b", re.IGNORECASE), "1 hour"),
    (re.compile(r"\ba\s+few\s+minutes\b", re.IGNORECASE), "3 minutes"),
    (re.compile(r"\ba\s+couple\s+(?:of\s+)?minutes\b", re.IGNORECASE), "2 minutes"),
    (re.compile(r"\ba\s+minute\b", re.IGNORECASE), "1 minute"),
    (re.compile(r"\ba\s+second\b", re.IGNORECASE), "1 second"),
]


def normalize_duration_words(text: str) -> str:
    """Rewrite spoken durations ("half an hour", "a minute") as number and unit."""
    for pattern, replacement in _WORDS:
        text = pattern.sub(replacement, text)
    return text


def parse_duration(text: str) -> int | None:
    """Seconds in the first duration phrase in text, or None if there is none.

    Compound phrases are summed: "1 hour 30 minutes" is 5400.
    """
    if not text:
        return None
    m = _DURATION_RE.search(normalize_duration_words(text))
    if not m:
        return None
    total = sum(float(n) * _UNIT_SECONDS[u.lower()] for n, u in _PART_RE.findall(m.group(0)))
    return round(total)


def to_seconds(value: Any) -> int | None:
    """Canonical seconds from any representation a producer may hand over.

    Accepts seconds as a number, a duration phrase, a {'total_seconds': n}
    dict or a {'value': n, 'unit': u} dict. Anything else is None: an
    unreadable duration must not reach a timer as a guess.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(value)
    if isinstance(value, str):
        return parse_duration(value)
    if isinstance(value, dict):
        if isinstance(value.get("total_seconds"), (int, float)):
            return round(value["total_seconds"])
        unit = str(value.get("unit", "")).lower()
        if isinstance(value.get("value"), (int, float)) and unit in _UNIT_SECONDS:
            return round(value["value"] * _UNIT_SECONDS[unit])
    return None


def describe_duration(seconds: float) -> str:
    """Words for a duration, for confirmations: 5400 -> "1 hour 30 minutes"."""
    seconds = round(seconds)
    parts = []
    for name, size in (("hour", 3600), ("minute", 60), ("second", 1)):
        n, seconds = divmod(seconds, size)
        if n:
            parts.append(f"{n} {name}{'s' if n != 1 else ''}")
    return " ".join(parts) or "0 seconds"
