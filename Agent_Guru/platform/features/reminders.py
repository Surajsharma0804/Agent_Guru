"""Reminders, timers and scheduled tasks for Agent Guru.

Handles voice commands like:
  "remind me in 10 minutes to take my medicine"
  "set a timer for 5 minutes"
  "remind me at 3pm to call John"

Reminders fire by speaking the reminder text via TTS. Each one is an asyncio
task that sleeps and then speaks; given a store_path, the manager also keeps
the pending ones on disk. They used to live only in memory, so a reminder
was lost if the app stopped before it fired, without a word. A reminder that
came due while the app was off is said on the next start, with how late it
is: dropping it would lose it as silently as before.

The same manager runs two more kinds of scheduled task, kept in the same
store, so there is one scheduler and one file:

- check: calls a read-only tool (through the tool runner the orchestrator
  sets, MCPToolbox.call, so policy, schema and output checks apply) every
  every_s seconds, at least MIN_CHECK_INTERVAL_S apart, and says what it
  found: every time, when the result changed, or when it contains a text.
  What it finds is only spoken; it can never start an action.
- action: calls a tool that changes things, at a time or repeatedly. It
  runs only with an approval the owner gave for exactly that tool and those
  arguments (a fingerprint), from the owner's own turn, that has not
  expired; and the policy is asked again when it runs, so an approval does
  not outlive a change of policy.

Every run is written as running before it starts. A run the app stopped in
the middle of is found on the next start: a check simply runs at its next
time; an action is recorded as unverified and is not run again, since it
may have happened. Missed times never run in a burst: a check missed while
the app was off runs once, an action missed by more than ACTION_GRACE_S is
recorded as missed and not run late. A lock file next to the store keeps a
second copy of the assistant from running the same tasks.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import TYPE_CHECKING, Any

from Agent_Guru.utils.duration import DURATION_PATTERN, describe_duration, normalize_duration_words, parse_duration

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


SAY, CHECK, ACTION = "say", "check", "action"
#: Checks run no more often than this.
MIN_CHECK_INTERVAL_S = 300.0
#: Scheduled tasks kept at once, reminders included.
MAX_TASKS = 50
#: An action missed by more than this (the app was off) is not run late.
ACTION_GRACE_S = 600.0
#: Longest one run may take, the tool's own time limit included.
RUN_TIMEOUT_S = 90.0
#: Runs kept in a task's history.
RUNS_KEPT = 10


@dataclass
class Reminder:
    """A single reminder, or a scheduled check or action (see the module docstring)."""

    reminder_id: str
    message: str
    fire_at: float  # Unix timestamp
    created_at: float = field(default_factory=time.time)
    fired: bool = False
    kind: str = SAY
    #: Seconds between runs, for a task that repeats.
    every_s: float | None = None
    server: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    #: For a check: "always", "changed", or "contains:<text>".
    notify_when: str = "always"
    #: For an action: fingerprint, by, approved_at, expires_at.
    approval: dict[str, Any] | None = None
    enabled: bool = True
    #: The run in progress (run_id, started), written before it starts.
    running: dict[str, Any] | None = None
    runs: list[dict[str, Any]] = field(default_factory=list)
    #: Fingerprint of a check's last result, for notify_when="changed".
    last_result: str | None = None


def action_fingerprint(server: str | None, tool: str | None, arguments: dict[str, Any] | None) -> str:
    """What an approval is bound to: exactly this tool with exactly these arguments."""
    blob = json.dumps({"server": server, "tool": tool, "arguments": arguments or {}}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _pid_alive(pid: int) -> bool:
    try:
        import psutil

        return psutil.pid_exists(pid)
    except Exception:
        return False


class ReminderManager:
    """Manages voice-set reminders and timers.

    Usage:
        mgr = ReminderManager(speak_callback=speak_fn)
        await mgr.set_reminder("take medicine", minutes=10)
        await mgr.set_reminder("call John", at_time="3pm")
    """

    def __init__(self, speak_callback: Callable[[str], Any] | None = None, store_path: Path | None = None) -> None:
        self._reminders: dict[str, Reminder] = {}
        self._tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]
        self._speak = speak_callback
        self._store_path = store_path
        self._tool_runner: Callable[..., Any] | None = None
        self._audit: Callable[[str, str, dict[str, Any]], None] | None = None
        self._running: set[str] = set()
        #: Another copy of the assistant holds this store: run nothing.
        self.standby = False
        self._lock_path = store_path.with_suffix(".lock") if store_path is not None else None
        self._locked = False

    def set_tool_runner(self, runner: Callable[..., Any]) -> None:
        """How checks and actions call tools: async runner(server, tool, arguments) -> a ToolCallResult."""
        self._tool_runner = runner

    def set_audit(self, audit: Callable[[str, str, dict[str, Any]], None]) -> None:
        """Where each run is recorded: audit(task_id, status, details)."""
        self._audit = audit

    def _take_lock(self) -> bool:
        """Hold the store's lock file; False if a running copy of the assistant holds it."""
        if self._lock_path is None or self._locked:
            return True
        for _ in range(2):
            try:
                fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    holder = int(self._lock_path.read_text(encoding="utf-8").strip() or "0")
                except (OSError, ValueError):
                    holder = 0
                if holder and holder != os.getpid() and _pid_alive(holder):
                    return False
                # Left by a copy that has stopped: taken over.
                self._lock_path.unlink(missing_ok=True)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as lock:
                lock.write(str(os.getpid()))
            self._locked = True
            return True
        return False

    def close(self) -> None:
        """Stop every scheduled task and let go of the store's lock."""
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        if self._locked and self._lock_path is not None:
            self._lock_path.unlink(missing_ok=True)
            self._locked = False

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
        # Unique across runs: a counter restarted at reminder_1 every start
        # and would clash with the reminders kept from the last one.
        rid = f"reminder_{uuid.uuid4().hex[:12]}"

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

        if len(self._reminders) >= MAX_TASKS:
            return f"Sorry, I can only keep {MAX_TASKS} reminders and tasks at once."
        fire_at = time.time() + delay
        reminder = Reminder(reminder_id=rid, message=message, fire_at=fire_at)
        self._reminders[rid] = reminder

        # Schedule the asyncio task
        task = asyncio.create_task(self._fire_after(reminder, delay))
        self._tasks[rid] = task
        self._save()

        # Human-readable confirmation. A duration is said exactly ("1 minute
        # 30 seconds"); it used to be cut to whole minutes, so a 90-second
        # timer was confirmed as "1 minute".
        if at_time is None:
            time_str = describe_duration(delay)
        elif delay < 60:
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
        """Cancel a pending reminder or scheduled task, also one between runs or switched off."""
        task = self._tasks.pop(reminder_id, None)
        if task and not task.done():
            task.cancel()
        if self._reminders.pop(reminder_id, None) is None and task is None:
            return False
        self._save()
        self._record(reminder_id, "cancelled", {})
        return True

    def list_reminders(self) -> list[Reminder]:
        """Return all pending (not yet fired) reminders and scheduled tasks."""
        return [r for r in self._reminders.values() if not r.fired]

    def set_enabled(self, task_id: str, enabled: bool) -> bool:
        """Switch a scheduled task off (it keeps its place, nothing runs) or back on."""
        task = self._reminders.get(task_id)
        if task is None:
            return False
        task.enabled = enabled
        running = self._tasks.pop(task_id, None)
        if running is not None:
            running.cancel()
        if enabled:
            self._schedule(task, time.time())
        self._save()
        return True

    async def add_check(
        self, message: str, *, server: str, tool: str, arguments: dict[str, Any], every_s: float,
        notify_when: str = "always", first_in_s: float = 0.0,
    ) -> Reminder:
        """Schedule a check (see the module docstring); raises ValueError naming what is wrong."""
        if every_s < MIN_CHECK_INTERVAL_S:
            msg = f"a check runs at most every {int(MIN_CHECK_INTERVAL_S // 60)} minutes"
            raise ValueError(msg)
        if not (notify_when in {"always", "changed", "met"} or notify_when.startswith("contains:")):
            msg = "notify_when is always, changed, met, or contains:<text>"
            raise ValueError(msg)
        return self._add(Reminder(
            reminder_id=f"check_{uuid.uuid4().hex[:12]}", message=message, fire_at=time.time() + first_in_s,
            kind=CHECK, every_s=every_s, server=server, tool=tool, arguments=dict(arguments), notify_when=notify_when,
        ))

    async def add_action(
        self, message: str, *, server: str, tool: str, arguments: dict[str, Any], fire_at: float,
        approved_by: str, approval_expires_at: float, every_s: float | None = None,
    ) -> Reminder:
        """Schedule an action with the owner's approval of exactly it (see the module docstring)."""
        if approved_by != "owner":
            msg = "only the owner can approve a scheduled action"
            raise ValueError(msg)
        if every_s is not None and every_s < MIN_CHECK_INTERVAL_S:
            msg = f"an action repeats at most every {int(MIN_CHECK_INTERVAL_S // 60)} minutes"
            raise ValueError(msg)
        now = time.time()
        return self._add(Reminder(
            reminder_id=f"action_{uuid.uuid4().hex[:12]}", message=message, fire_at=fire_at, kind=ACTION,
            every_s=every_s, server=server, tool=tool, arguments=dict(arguments),
            approval={"fingerprint": action_fingerprint(server, tool, arguments), "by": approved_by,
                      "approved_at": now, "expires_at": approval_expires_at},
        ))

    def _add(self, task: Reminder) -> Reminder:
        if len(self._reminders) >= MAX_TASKS:
            msg = f"at most {MAX_TASKS} reminders and tasks are kept at once"
            raise ValueError(msg)
        self._reminders[task.reminder_id] = task
        self._schedule(task, time.time())
        self._save()
        return task

    def _schedule(self, task: Reminder, now: float) -> None:
        if not task.enabled or self.standby:
            return
        old = self._tasks.pop(task.reminder_id, None)
        if old is not None and not old.done() and old is not asyncio.current_task():
            old.cancel()
        self._tasks[task.reminder_id] = asyncio.create_task(self._fire_after(task, max(0.0, task.fire_at - now)))

    async def _fire_after(self, reminder: Reminder, delay: float) -> None:
        """Sleep then fire the reminder, or run the task."""
        try:
            await asyncio.sleep(delay)
            if reminder.kind != SAY:
                await self._run(reminder)
                self._next(reminder)
                return
            reminder.fired = True
            logger.info("Reminder firing: %s", reminder.message)
            await self._say(reminder.message)
            # Forgotten only once said: if the app stops while it speaks,
            # the next start says it again rather than never.
            self._reminders.pop(reminder.reminder_id, None)
            self._tasks.pop(reminder.reminder_id, None)
            self._save()
        except asyncio.CancelledError:
            logger.debug("Reminder cancelled: %s", reminder.reminder_id)

    def _next(self, task: Reminder) -> None:
        """Schedule a repeating task's next run, past now, or forget a one-off task."""
        if task.reminder_id not in self._reminders:
            return
        if task.every_s:
            now = time.time()
            while task.fire_at <= now:
                task.fire_at += task.every_s
            self._save()
            self._schedule(task, now)
        else:
            self._reminders.pop(task.reminder_id, None)
            self._tasks.pop(task.reminder_id, None)
            self._save()

    async def _run(self, task: Reminder) -> str:
        """One run of a check or an action: claimed on disk, bounded in time, recorded; returns its status."""
        if task.reminder_id in self._running:
            return "skipped"  # already running: never twice at once
        self._running.add(task.reminder_id)
        run = {"run_id": uuid.uuid4().hex[:12], "started": time.time()}
        task.running = dict(run)
        self._save()
        status, detail = "failed", ""
        try:
            status, detail = await asyncio.wait_for(self._execute(task), RUN_TIMEOUT_S)
        except TimeoutError:
            # An action may have happened before the time ran out.
            status = "unverified" if task.kind == ACTION else "failed"
            detail = f"no result within {RUN_TIMEOUT_S:g} s"
        except asyncio.CancelledError:
            status, detail = ("unverified" if task.kind == ACTION else "cancelled"), "cancelled while running"
            raise
        except Exception as exc:
            status, detail = ("unverified" if task.kind == ACTION else "failed"), f"{type(exc).__name__}: {exc}"[:200]
        finally:
            self._running.discard(task.reminder_id)
            task.running = None
            run.update(ended=time.time(), status=status, detail=detail[:300])
            task.runs = [*task.runs, run][-RUNS_KEPT:]
            self._save()
            self._record(task.reminder_id, status, {"kind": task.kind, "run_id": run["run_id"], "tool": task.tool,
                                                   "server": task.server, "detail": detail[:200]})
        return status

    async def _execute(self, task: Reminder) -> tuple[str, str]:
        if self._tool_runner is None:
            return "failed", "no tool runner"
        if task.kind == ACTION:
            problem = self._approval_problem(task)
            if problem:
                await self._say(f"I didn't run your scheduled task, {task.message}: {problem}.")
                return "denied", problem
        result = await self._tool_runner(task.server, task.tool, task.arguments or {})
        status = getattr(getattr(result, "status", None), "value", str(getattr(result, "status", "failed")))
        output = str(getattr(result, "output", "") or "")
        error = str(getattr(result, "error", "") or "")
        if task.kind == CHECK:
            if status != "success":
                await self._say(f"Your check, {task.message}, didn't work this time.")
                return status, error
            digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
            changed, task.last_result = digest != task.last_result, digest
            wanted = task.notify_when
            if wanted == "met":
                # A watch for a condition (rain, a temperature) speaks the tool's one sentence
                # when it holds and nothing otherwise. It used to be a "contains" match on the
                # whole report, which said "chance of rain" every day, and spoke the first 240
                # characters of it, source formatting included.
                from Agent_Guru.platform.features.weather import MET

                first = output.lstrip().split("\n", 1)[0]
                if first.startswith(MET):
                    await self._say(f"Your check, {task.message}: {first[len(MET):].strip()}")
                    return status, "notified"
                return status, "condition not met"
            if wanted == "always" or (wanted == "changed" and changed) or (
                wanted.startswith("contains:") and wanted.split(":", 1)[1].strip().lower() in output.lower()
            ):
                # Said, never acted on: a check only reads.
                await self._say(f"Your check, {task.message}: {output[:240]}")
                return status, "notified"
            return status, "nothing to report"
        reply = {
            "success": f"Your scheduled task, {task.message}, is done.",
            "unverified": f"Your scheduled task, {task.message}, ran, but I couldn't confirm it worked.",
            "denied": f"I wasn't allowed to run your scheduled task, {task.message}.",
        }.get(status, f"Your scheduled task, {task.message}, didn't work.")
        await self._say(reply)
        return status, error

    def _approval_problem(self, task: Reminder) -> str:
        """Why an action may not run on its approval, or "" if it may."""
        approval = task.approval or {}
        if approval.get("by") != "owner":
            return "it was never approved by you"
        if approval.get("fingerprint") != action_fingerprint(task.server, task.tool, task.arguments):
            return "it changed after you approved it"
        if time.time() > float(approval.get("expires_at", 0)):
            return "your approval has expired"
        return ""

    def _record(self, task_id: str, status: str, details: dict[str, Any]) -> None:
        if self._audit is not None:
            try:
                self._audit(task_id, status, details)
            except Exception:
                logger.exception("Scheduled task %s could not be audited", task_id)

    async def _say(self, text: str) -> None:
        """Speak *text*; a plain function runs in a worker thread.

        The speaker callback synthesizes and plays the whole sentence. Called
        on the event loop, it held up everything else, wake-word listening
        included, for as long as the reminder took to say.
        """
        if self._speak is None:
            return
        try:
            if asyncio.iscoroutinefunction(self._speak):
                await self._speak(text)
            else:
                result = await asyncio.to_thread(self._speak, text)
                if asyncio.iscoroutine(result):
                    await result
        except Exception:
            logger.exception("Reminder TTS failed")

    async def restore(self, now: float | None = None) -> list[str]:
        """Pick up the reminders and tasks kept by an earlier run; returns what was said for the missed ones.

        Reminders still ahead are scheduled for their remaining time. One
        that came due while the app was off is said now, with how late it is.
        Checks and actions are taken up as the module docstring describes.
        If another running copy of the assistant holds the store, nothing is
        scheduled here (standby).
        """
        if self._store_path is None:
            return []
        if not self._take_lock():
            self.standby = True
            logger.warning("Another copy of Agent Guru is running the scheduled tasks; this one runs none")
            return []
        if not self._store_path.exists():
            return []
        now = time.time() if now is None else now
        known = {f.name for f in fields(Reminder)}
        try:
            saved = json.loads(self._store_path.read_text(encoding="utf-8"))
            pending = [Reminder(**{k: v for k, v in item.items() if k in known and k != "fired"}) for item in saved]
        except (OSError, ValueError, TypeError, KeyError):
            # Unreadable: keep the file for inspection instead of overwriting it.
            broken = self._store_path.with_suffix(".unreadable.json")
            logger.exception("Kept reminders could not be read; moved to %s", broken)
            self._store_path.replace(broken)
            return []
        said = []
        for task in [t for t in pending if t.kind != SAY]:
            said.extend(await self._take_up(task, now))
        for reminder in sorted((t for t in pending if t.kind == SAY), key=lambda r: r.fire_at):
            if reminder.fire_at > now:
                self._reminders[reminder.reminder_id] = reminder
                self._tasks[reminder.reminder_id] = asyncio.create_task(
                    self._fire_after(reminder, reminder.fire_at - now),
                )
                continue
            late = _how_late(now - reminder.fire_at)
            text = f"You had a reminder {late} ago: {reminder.message}" if late else f"Reminder: {reminder.message}"
            logger.info("Missed reminder said on start: %s", text)
            await self._say(text)
            said.append(text)
        self._save()
        return said

    async def _take_up(self, task: Reminder, now: float) -> list[str]:
        """A kept check or action, after a restart (see the module docstring)."""
        said: list[str] = []
        self._reminders[task.reminder_id] = task
        if task.running is not None:
            # The app stopped during this run. An action may have happened:
            # recorded as unverified and not run again.
            status = "unverified" if task.kind == ACTION else "interrupted"
            run = {**task.running, "ended": now, "status": status, "detail": "the app stopped during this run"}
            task.runs = [*task.runs, run][-RUNS_KEPT:]
            task.running = None
            self._record(task.reminder_id, status, {"kind": task.kind, "run_id": run.get("run_id"), "detail": run["detail"]})
            if task.kind == ACTION:
                text = f"Your scheduled task, {task.message}, was running when I stopped; I can't tell if it finished."
                await self._say(text)
                said.append(text)
                self._advance_past(task, now)
        if task.fire_at <= now and task.kind == ACTION and now - task.fire_at > ACTION_GRACE_S:
            late = _how_late(now - task.fire_at) or "a while"
            run = {"run_id": uuid.uuid4().hex[:12], "started": now, "ended": now, "status": "missed",
                   "detail": f"due {late} ago while the app was off; not run late"}
            task.runs = [*task.runs, run][-RUNS_KEPT:]
            self._record(task.reminder_id, "missed", {"kind": task.kind, "detail": run["detail"]})
            text = f"Your scheduled task, {task.message}, was due {late} ago; I didn't run it late."
            await self._say(text)
            said.append(text)
            self._advance_past(task, now)
        elif task.fire_at <= now and task.kind == CHECK and task.every_s:
            # Missed checks run once now, not once per missed time.
            task.fire_at = now
        if task.reminder_id in self._reminders:
            self._schedule(task, now)
        return said

    def _advance_past(self, task: Reminder, now: float) -> None:
        if task.every_s:
            while task.fire_at <= now:
                task.fire_at += task.every_s
        else:
            self._reminders.pop(task.reminder_id, None)

    def _save(self) -> None:
        """Keep the pending reminders on disk, if a store was given; never raises."""
        if self._store_path is None:
            return
        from Agent_Guru.utils.secure_file import secure_write_bytes

        pending = [asdict(r) for r in self._reminders.values() if not r.fired]
        try:
            secure_write_bytes(self._store_path, json.dumps(pending, indent=1).encode("utf-8"))
        except OSError:
            logger.exception("Could not keep reminders on disk; they will not survive a restart")

    @staticmethod
    def _parse_time_to_delay(time_str: str) -> float | None:
        """Parse a time string like '3pm', '15:30', '3:30 pm' to seconds from now."""
        time_str = time_str.strip().lower()
        # The owner's clock, not UTC: "3pm" was read as 3 pm UTC, so in India
        # (UTC+5:30) "remind me at 11:59 pm" said at 22:32 was set for 05:29
        # the next morning.
        now = datetime.datetime.now().astimezone()

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


def _how_late(seconds: float) -> str | None:
    """How late a missed reminder is, in words fit to say; None if under a minute."""
    if seconds < 60:
        return None
    if seconds < 2 * 86400:
        return describe_duration(round(seconds / 60) * 60)
    days = round(seconds / 86400)
    return f"{days} days"


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

    # Spoken durations ("half an hour", "a minute") become number + unit,
    # through the project's one duration parser.
    t = normalize_duration_words(t)

    # Pattern 1: "remind me in X minutes to Y" or just "remind me in X minutes"
    m = re.search(
        rf"remind\s+me\s+in\s+({DURATION_PATTERN})(?:\s+(?:to\s+)?(.+))?",
        t,
        re.IGNORECASE,
    )
    if m:
        message = (m.group(2) or "reminder").strip().rstrip(".,!?")
        return {"message": message, "seconds": parse_duration(m.group(1))}

    # Pattern 2: "remind me to Y in X minutes" (reversed order)
    m = re.search(
        rf"remind\s+me\s+(?:to\s+)?(.+?)\s+in\s+({DURATION_PATTERN})",
        t,
        re.IGNORECASE,
    )
    if m:
        return {"message": m.group(1).strip().rstrip(".,!?"), "seconds": parse_duration(m.group(2))}

    # Pattern 3: "in X minutes remind me to Y" (time first)
    m = re.search(
        rf"in\s+({DURATION_PATTERN})\s+remind\s+me\s+(?:to\s+)?(.+)",
        t,
        re.IGNORECASE,
    )
    if m:
        return {"message": m.group(2).strip().rstrip(".,!?"), "seconds": parse_duration(m.group(1))}

    # Pattern 4: "set a timer for X minutes"
    m = re.search(
        rf"(?:set\s+a?\s*)?timer\s+(?:for\s+)?({DURATION_PATTERN})",
        t,
        re.IGNORECASE,
    )
    if m:
        seconds = parse_duration(m.group(1))
        return {"message": f"Your {_timer_label(seconds)} timer is done.", "seconds": seconds}

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
        rf"(?:don.t\s+let\s+me\s+forget|don.t\s+forget)\s+(?:to\s+)?(.+?)\s+in\s+({DURATION_PATTERN})",
        t,
        re.IGNORECASE,
    )
    if m:
        return {"message": m.group(1).strip().rstrip(".,!?"), "seconds": parse_duration(m.group(2))}

    return None


def _timer_label(seconds: int) -> str:
    """"5-minute", "1-hour", "90-second": the largest unit that divides exactly."""
    for name, size in (("hour", 3600), ("minute", 60)):
        if seconds >= size and seconds % size == 0:
            return f"{seconds // size}-{name}"
    return f"{seconds}-second"
