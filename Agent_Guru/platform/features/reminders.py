"""Reminder and timer system for Agent Guru.

Handles voice commands like:
  "remind me in 10 minutes to take my medicine"
  "set a timer for 5 minutes"
  "remind me at 3pm to call John"

Reminders fire by speaking the reminder text via TTS. They're stored in
memory so they survive across sessions (if the app is running).

This is intentionally simple - no external calendar integration needed.
Just asyncio tasks that sleep and then speak.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass
class Reminder:
    """A single reminder."""

    reminder_id: str
    message: str
    fire_at: float  # Unix timestamp
    created_at: float = field(default_factory=time.time)
    fired: bool = False


class ReminderManager:
    """Manages voice-set reminders and timers.

    Usage:
        mgr = ReminderManager(speak_callback=speak_fn)
        await mgr.set_reminder("take medicine", minutes=10)
        await mgr.set_reminder("call John", at_time="3pm")
    """

    def __init__(self, speak_callback: Callable[[str], Any] | None = None) -> None:
        self._reminders: dict[str, Reminder] = {}
        self._tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]
        self._speak = speak_callback
        self._counter = 0

    def set_speak_callback(self, callback: Callable[[str], Any]) -> None:
        """Set the TTS callback used to speak reminders."""
        self._speak = callback

    async def set_reminder(
        self,
        message: str,
        minutes: float | None = None,
        seconds: float | None = None,
        at_time: str | None = None,
    ) -> str:
        """Set a reminder.

        Args:
            message: What to say when the reminder fires.
            minutes: Fire in this many minutes from now.
            seconds: Fire in this many seconds from now.
            at_time: Fire at a specific time string like "3pm", "15:30".

        Returns:
            Confirmation message for TTS.

        """
        self._counter += 1
        rid = f"reminder_{self._counter}"

        if seconds is not None:
            delay = seconds
        elif minutes is not None:
            delay = minutes * 60
        elif at_time is not None:
            delay = self._parse_time_to_delay(at_time)
            if delay is None:
                return f"Sorry, I couldn't understand the time '{at_time}'."
        else:
            return "Please specify when to remind you."

        fire_at = time.time() + delay
        reminder = Reminder(reminder_id=rid, message=message, fire_at=fire_at)
        self._reminders[rid] = reminder

        # Schedule the asyncio task
        task = asyncio.create_task(self._fire_after(reminder, delay))
        self._tasks[rid] = task

        # Human-readable confirmation
        if delay < 60:
            time_str = f"{int(delay)} seconds"
        elif delay < 3600:
            mins = int(delay / 60)
            time_str = f"{mins} minute{'s' if mins != 1 else ''}"
        else:
            hours = delay / 3600
            time_str = f"{hours:.1f} hours"

        logger.info("Reminder set: '%s' in %s (id=%s)", message, time_str, rid)
        return f"I'll remind you in {time_str}."

    async def set_timer(self, minutes: float) -> str:
        """Set a simple countdown timer."""
        return await self.set_reminder(
            f"Your {int(minutes)}-minute timer is done.",
            minutes=minutes,
        )

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a pending reminder."""
        task = self._tasks.get(reminder_id)
        if task and not task.done():
            task.cancel()
            del self._tasks[reminder_id]
            if reminder_id in self._reminders:
                del self._reminders[reminder_id]
            return True
        return False

    def list_reminders(self) -> list[Reminder]:
        """Return all pending (not yet fired) reminders."""
        return [r for r in self._reminders.values() if not r.fired]

    async def _fire_after(self, reminder: Reminder, delay: float) -> None:
        """Sleep then fire the reminder."""
        try:
            await asyncio.sleep(delay)
            reminder.fired = True
            logger.info("Reminder firing: %s", reminder.message)
            if self._speak is not None:
                try:
                    result = self._speak(reminder.message)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    logger.exception("Reminder TTS failed")
        except asyncio.CancelledError:
            logger.debug("Reminder cancelled: %s", reminder.reminder_id)

    @staticmethod
    def _parse_time_to_delay(time_str: str) -> float | None:
        """Parse a time string like '3pm', '15:30', '3:30 pm' to seconds from now."""
        time_str = time_str.strip().lower()
        now = datetime.datetime.now(tz=datetime.UTC)

        # Try "3pm", "3:30pm", "3:30 pm", "15:30"
        # fullmatch, not match+"$": Python's "$" also matches just before a
        # trailing newline, so "7:30 pm\n<anything-was-already-stripped>" and
        # similar near-misses parsed as valid times.
        patterns = [
            (r"(\d{1,2}):(\d{2})\s*(am|pm)", True),
            (r"(\d{1,2})\s*(am|pm)", False),
            (r"(\d{1,2}):(\d{2})", None),
        ]

        for pattern, has_minutes in patterns:
            m = re.fullmatch(pattern, time_str)
            if not m:
                continue
            groups = m.groups()
            if has_minutes is True:
                hour, minute, ampm = int(groups[0]), int(groups[1]), groups[2]
                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            elif has_minutes is False:
                hour, ampm = int(groups[0]), groups[1]
                minute = 0
                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            else:
                hour, minute = int(groups[0]), int(groups[1])

            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)  # next occurrence

            return (target - now).total_seconds()

        return None


def parse_reminder_from_transcript(transcript: str) -> dict | None:
    """Extract reminder parameters from a voice transcript.

    Handles many natural speech variations:
        "remind me in 10 minutes to take my medicine"
        "remind me to take medicine in 10 minutes"  ← reversed order
        "in 10 minutes remind me to call John"       ← time first
        "set a timer for 5 minutes"
        "remind me at 3pm to call John"
        "remind me in half an hour"
        "remind me in an hour"
        "don't let me forget to call John in 30 minutes"

    Returns:
        Dict with keys: message, minutes/seconds/at_time, or None if no match.

    """
    t = transcript.strip()

    # Normalize natural time expressions FIRST before pattern matching
    t = re.sub(r"\bhalf\s+an?\s+hour\b", "30 minutes", t, flags=re.IGNORECASE)
    t = re.sub(r"\ban?\s+hour\b", "60 minutes", t, flags=re.IGNORECASE)
    t = re.sub(r"\ba\s+minute\b", "1 minute", t, flags=re.IGNORECASE)
    t = re.sub(r"\ba\s+second\b", "1 second", t, flags=re.IGNORECASE)
    t = re.sub(r"\ba\s+few\s+minutes\b", "3 minutes", t, flags=re.IGNORECASE)
    t = re.sub(r"\ba\s+couple\s+(?:of\s+)?minutes\b", "2 minutes", t, flags=re.IGNORECASE)

    # Pattern 1: "remind me in X minutes to Y" or just "remind me in X minutes"
    m = re.search(
        r"remind\s+me\s+in\s+(\d+(?:\.\d+)?)\s*(minute|min|second|sec)s?(?:\s+(?:to\s+)?(.+))?",
        t,
        re.IGNORECASE,
    )
    if m:
        amount = float(m.group(1))
        unit = m.group(2).lower()
        message = (m.group(3) or "reminder").strip().rstrip(".,!?")
        key = "seconds" if "sec" in unit else "minutes"
        return {"message": message, key: amount}

    # Pattern 2: "remind me to Y in X minutes" (reversed order)
    m = re.search(
        r"remind\s+me\s+(?:to\s+)?(.+?)\s+in\s+(\d+(?:\.\d+)?)\s*(minute|min|second|sec)s?",
        t,
        re.IGNORECASE,
    )
    if m:
        message, amount, unit = (
            m.group(1).strip().rstrip(".,!?"),
            float(m.group(2)),
            m.group(3).lower(),
        )
        return {"message": message, "seconds" if "sec" in unit else "minutes": amount}

    # Pattern 3: "in X minutes remind me to Y" (time first)
    m = re.search(
        r"in\s+(\d+(?:\.\d+)?)\s*(minute|min|second|sec)s?\s+remind\s+me\s+(?:to\s+)?(.+)",
        t,
        re.IGNORECASE,
    )
    if m:
        amount, unit, message = (
            float(m.group(1)),
            m.group(2).lower(),
            m.group(3).strip().rstrip(".,!?"),
        )
        return {"message": message, "seconds" if "sec" in unit else "minutes": amount}

    # Pattern 4: "set a timer for X minutes"
    m = re.search(
        r"(?:set\s+a?\s*)?timer\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*(minute|min|second|sec)s?",
        t,
        re.IGNORECASE,
    )
    if m:
        amount, unit = float(m.group(1)), m.group(2).lower()
        if "sec" in unit:
            return {"message": f"Your {int(amount)}-second timer is done.", "seconds": amount}
        return {"message": f"Your {int(amount)}-minute timer is done.", "minutes": amount}

    # Pattern 5: "remind me at 3pm to Y"
    m = re.search(
        r"remind\s+me\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:to\s+)?(.+)",
        t,
        re.IGNORECASE,
    )
    if m:
        at_time, message = m.group(1).strip(), m.group(2).strip().rstrip(".,!?")
        return {"message": message, "at_time": at_time}

    # Pattern 6: "don't let me forget to Y in X minutes"
    m = re.search(
        r"(?:don.t\s+let\s+me\s+forget|don.t\s+forget)\s+(?:to\s+)?(.+?)\s+in\s+(\d+(?:\.\d+)?)\s*(minute|min|second|sec)s?",
        t,
        re.IGNORECASE,
    )
    if m:
        message, amount, unit = (
            m.group(1).strip().rstrip(".,!?"),
            float(m.group(2)),
            m.group(3).lower(),
        )
        return {"message": message, "seconds" if "sec" in unit else "minutes": amount}

    return None
