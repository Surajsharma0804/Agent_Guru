"""Scheduling checks and actions from a conversation, through the tool loop.

Served in process through MCPToolbox like the research tools, as the
server "tasks". The scheduler itself is the reminder manager
(platform/features/reminders.py); these tools only create, list and cancel
its tasks.

Creating or cancelling a task changes the owner's records, so those tools
are not read-only and the tool loop asks the owner first, reading back
exactly what will run. That yes, on the owner's own next turn, is the
approval of a scheduled action: it is stored bound to the tool and the
arguments it was given (a fingerprint), with an expiry, and the scheduler
refuses to run the action if any of that no longer holds. A web page, an
email or a tool's output cannot give it: they can only ever reach the model,
and the model cannot answer the loop's question.

A task may only call a tool that could run right now (allowed, with a
checkable schema, permitted by the policy), with arguments that pass its
schema; a check may only call a read-only tool; and no task may call these
tools themselves.
"""

from __future__ import annotations

import datetime
import json
import logging
import time
from typing import Any

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule
from Agent_Guru.reasoning.tools.mcp_schema import validate

logger = logging.getLogger(__name__)

SERVER_NAME = "tasks"
#: How long an approval of a repeating action lasts before the owner is asked again.
REPEAT_APPROVAL_S = 7 * 86400

_TARGET = {"type": "string", "minLength": 3, "maxLength": 200}


def tasks_server() -> ServerConfig:
    """The ServerConfig for the task tools; local is set by the caller."""
    rules = {
        "list_tasks": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
        "schedule_check": ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE),
        "schedule_action": ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT),
        "cancel_task": ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE),
    }
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=20.0, tools=rules)


#: Checked before the owner is asked as well as when the check is made. It
#: was only checked when made, so the owner was asked "Should I check ...
#: every hour?", said yes, and then heard that the call had failed (1 of 10
#: live runs of an hourly rain watch).
_CONTAINS_NEEDS_TEXT = "notify_when contains needs contains_text, the words to look for"


def _contains_without_text(arguments: dict[str, Any]) -> bool:
    return arguments.get("notify_when") == "contains" and not str(arguments.get("contains_text") or "").strip()


class TaskTools:
    """The task tools; bind() gives them the orchestrator whose scheduler and tools they use."""

    def __init__(self) -> None:
        self._orch: Any = None

    def bind(self, orchestrator: Any) -> None:
        self._orch = orchestrator

    def tool_list(self) -> list[dict[str, Any]]:
        return [
            {"name": "list_tasks", "description": "List the owner's reminders and scheduled checks and actions.",
             "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "additionalProperties": False}},
            # The example names the assistant's own weather tool (before it existed, web research). It
            # named eval__get_weather, which exists only in the evaluation server, so in the live app
            # gemma4 invented a weather tool to match ("weather__get_weather", 3 of 3 runs), the call
            # was refused, and "keep an eye on the weather in Delhi every hour" ended in "I hit a snag".
            # The error message for a check with nothing to repeat still named eval__get_weather.
            {"name": "schedule_check", "description": (
                "Repeat a read-only lookup every so often and tell the owner what it finds. Give tool (its name as "
                "you see it) and that tool's own arguments as further fields, for example "
                '{"tool": "guru__weather", "place": "Delhi", "every_minutes": 60}. '
                "notify_when: always, changed, or contains (with contains_text)."),
             "annotations": {"readOnlyHint": False}, "inputSchema": {
                 "type": "object", "additionalProperties": True,
                 "required": ["every_minutes"],
                 "properties": {
                     "description": {"type": "string", "minLength": 3, "maxLength": 120},
                     "tool": _TARGET, "arguments": {"type": "object"},
                     "every_minutes": {"type": "number", "minimum": 5, "maximum": 10080},
                     "notify_when": {"type": "string", "enum": ["always", "changed", "contains"]},
                     "contains_text": {"type": "string", "maxLength": 100}}}},
            {"name": "schedule_action", "description": (
                "Run a tool that changes something, later, once (in_minutes or at_time like 9pm) or repeatedly "
                "(every_minutes). Give tool and that tool's own arguments as further fields. The owner is asked "
                "to approve exactly this before it is scheduled."),
             "annotations": {"readOnlyHint": False}, "inputSchema": {
                 "type": "object", "additionalProperties": True,
                 "required": ["description", "tool"],
                 "properties": {
                     "description": {"type": "string", "minLength": 3, "maxLength": 120},
                     "tool": _TARGET, "arguments": {"type": "object"},
                     "in_minutes": {"type": "number", "minimum": 1, "maximum": 525600},
                     "at_time": {"type": "string", "maxLength": 12},
                     "every_minutes": {"type": "number", "minimum": 5, "maximum": 10080}}}},
            {"name": "cancel_task", "description": "Cancel a reminder or scheduled task by its id (from list_tasks).",
             "annotations": {"readOnlyHint": False}, "inputSchema": {
                 "type": "object", "additionalProperties": False, "required": ["task_id"],
                 "properties": {"task_id": {"type": "string", "minLength": 3, "maxLength": 40}}}},
        ]

    async def precheck(self, name: str, arguments: dict[str, Any]) -> list[str]:
        """What is wrong with a schedule_check or schedule_action call, without scheduling anything."""
        if name not in {"schedule_check", "schedule_action"} or self._orch is None:
            return []
        # Every problem at once. The first one found used to be the only one
        # reported, and the model gets one repair: "tell me every hour if it
        # rains in Delhi" came as guru__weather without its place and with
        # notify_when contains but no words; told only about the place, the
        # repaired call was refused for the words, and 6 of 10 live runs
        # ended unscheduled.
        problems = []
        try:
            tool, target_arguments = self._split(arguments)
            target = await self._target(tool, target_arguments)
        except ValueError as exc:
            problems.append(str(exc))
        else:
            if name == "schedule_check" and target.risk is not ToolRisk.READ_ONLY:
                problems.append(f"{tool} changes things; a check may only use a read-only tool")
        if name == "schedule_check" and _contains_without_text(arguments):
            problems.append(_CONTAINS_NEEDS_TEXT)
        return problems

    def missing_target(self, name: str, arguments: Any) -> str | None:
        """The tool a schedule call names when none of its own arguments came with it; else None."""
        if name not in {"schedule_check", "schedule_action"} or not isinstance(arguments, dict):
            return None
        tool = str(arguments.get("tool") or "")
        extra = arguments.get("arguments") or {k: v for k, v in arguments.items() if k not in self._OWN}
        return tool if tool and not extra else None

    _OWN = frozenset({"description", "tool", "arguments", "every_minutes", "notify_when", "contains_text",
                      "in_minutes", "at_time"})

    def describe(self, name: str, arguments: dict[str, Any]) -> str | None:
        """The owner's yes/no question for a scheduling call, from what _split says will run.

        Without it the tool loop read the raw call aloud: "Should I run
        schedule_check on tasks with {"arguments": {}, "contains_text":
        "Delhi", "every_minutes": 60, "notify_when": "always", "tool":
        "eval__get_weather", "city": "Delhi"}?". The words come from the same
        split the call will use, so they name what is approved and nothing else.
        """
        if not isinstance(arguments, dict):
            return None
        if name == "cancel_task":
            return f"cancel the task {str(arguments.get('task_id', ''))[:40]}"
        if name not in {"schedule_check", "schedule_action"}:
            return None
        try:
            tool, target_arguments = self._split(arguments)
        except ValueError:
            return None
        what = tool.split("__", 1)[-1].replace("_", " ")
        given = ", ".join(f"{k} {json.dumps(v, ensure_ascii=False).strip(chr(34))}" for k, v in target_arguments.items())
        lookup = f"{what} ({given[:120]})" if given else what

        def every(minutes: Any) -> str:
            try:
                value = float(minutes)
            except (TypeError, ValueError):
                return ""
            if value == 60:
                return "every hour"
            if value % 1440 == 0:
                return "every day" if value == 1440 else f"every {value / 1440:g} days"
            if value % 60 == 0:
                return f"every {value / 60:g} hours"
            return f"every {value:g} minutes"

        if name == "schedule_check":
            when = every(arguments.get("every_minutes"))
            notify = arguments.get("notify_when", "always")
            if notify == "contains" and arguments.get("contains_text"):
                tell = f"tell you when it mentions {str(arguments['contains_text'])[:60]}"
            elif notify == "changed":
                tell = "tell you when it changes"
            else:
                tell = "tell you what it finds each time"
            return f"check {lookup} {when} and {tell}".replace("  ", " ")
        if arguments.get("in_minutes") is not None:
            when = f"in {float(arguments['in_minutes']):g} minutes"
        elif arguments.get("at_time"):
            when = f"at {str(arguments['at_time'])[:12]}"
        else:
            when = every(arguments.get("every_minutes"))
        return f"run {lookup} {when}".strip()

    def _split(self, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """The target tool and its arguments: from tool and arguments, from extra fields, or the turn's last lookup."""
        tool = str(arguments.get("tool") or "")
        target_arguments = arguments.get("arguments") or {k: v for k, v in arguments.items() if k not in self._OWN}
        if tool and target_arguments:
            return tool, dict(target_arguments)
        # Repeat the read-only call this turn made. gemma4 could not fill
        # a nested arguments object: it sent {"arguments": {}, "contains_text":
        # "Delhi"} for the Delhi weather, but called get_weather({"city":
        # "Delhi"}) itself without trouble.
        from Agent_Guru.integration.tool_loop import CALLS_THIS_TURN

        made = [c for c in CALLS_THIS_TURN.get() or [] if c[0] != SERVER_NAME and c[3].value == "success"]
        if tool:
            made = [c for c in made if f"{c[0]}__{c[1]}" == tool]
        if not made:
            if tool:
                return tool, {}
            msg = ("name the tool to repeat and give its arguments as further fields, for example "
                   '{"tool": "guru__weather", "place": "Delhi", "every_minutes": 60}')
            raise ValueError(msg)
        server, name, made_arguments, _ = made[-1]
        return f"{server}__{name}", dict(made_arguments)

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[Any, ...]:
        if self._orch is None:
            return "scheduling is not available", True
        handler = {"list_tasks": self._list, "schedule_check": self._check,
                   "schedule_action": self._action, "cancel_task": self._cancel}.get(name)
        if handler is None:
            return f"no tool named {name}", True
        try:
            if name in {"schedule_check", "schedule_action"}:
                tool, target_arguments = self._split(arguments)
                own = {k: v for k, v in arguments.items() if k in self._OWN and k not in {"tool", "arguments"}}
                return await handler(tool=tool, arguments=target_arguments, **own)
            return await handler(**arguments)
        except ValueError as exc:
            return str(exc), True

    async def _target(self, name: str, arguments: dict[str, Any]) -> Any:
        """The callable tool *name* names, with *arguments* checked against its schema; raises ValueError."""
        toolbox = getattr(self._orch, "_toolbox", None)
        if toolbox is None:
            msg = "no tools are available to schedule"
            raise ValueError(msg)
        server, _, tool = name.partition("__")
        if server == SERVER_NAME:
            msg = "a task cannot schedule other tasks"
            raise ValueError(msg)
        found = next((t for t in await toolbox.available_now() if t.server == server and t.name == tool), None)
        if found is None:
            msg = f"{name} is not a tool that can run now"
            raise ValueError(msg)
        schema = {**found.input_schema, "additionalProperties": found.input_schema.get("additionalProperties", False)}
        problems = validate(arguments, schema)
        if problems:
            msg = "the arguments do not fit the tool: " + "; ".join(problems[:3])
            raise ValueError(msg)
        return found

    async def _list(self) -> tuple[Any, ...]:
        tasks = self._orch._reminders().list_reminders()
        if not tasks:
            return "There are no reminders or scheduled tasks.", False
        lines = []
        for t in sorted(tasks, key=lambda t: t.fire_at):
            when = datetime.datetime.fromtimestamp(t.fire_at).strftime("%a %d %b %H:%M")
            repeat = f", every {int(t.every_s // 60)} min" if t.every_s else ""
            last = t.runs[-1]["status"] if t.runs else "not run yet"
            state = "" if t.enabled else ", switched off"
            target = f" -> {t.server}__{t.tool} {json.dumps(t.arguments)}" if t.tool else ""
            lines.append(f"{t.reminder_id} ({t.kind}{repeat}{state}): {t.message}{target}; next {when}; last run {last}")
        return "\n".join(lines), False

    async def _check(self, *, every_minutes: float, tool: str, arguments: dict[str, Any], description: str = "",
                     notify_when: str = "always", contains_text: str = "") -> tuple[Any, ...]:
        target = await self._target(tool, arguments)
        description = description or f"{target.name} {json.dumps(arguments)}"
        if target.risk is not ToolRisk.READ_ONLY:
            msg = f"{tool} changes things; a check may only use a read-only tool"
            raise ValueError(msg)
        if notify_when == "contains":
            if _contains_without_text({"notify_when": notify_when, "contains_text": contains_text}):
                raise ValueError(_CONTAINS_NEEDS_TEXT)
            notify_when = f"contains:{contains_text.strip()}"
        task = await self._orch._reminders().add_check(
            description, server=target.server, tool=target.name, arguments=arguments, every_s=every_minutes * 60,
            notify_when=notify_when,
        )
        return f"Scheduled check {task.reminder_id}: {description}, every {every_minutes:g} minutes.", False, \
            self._stored(task.reminder_id)

    async def _action(self, *, description: str, tool: str, arguments: dict[str, Any], in_minutes: float | None = None,
                      at_time: str | None = None, every_minutes: float | None = None) -> tuple[Any, ...]:
        from Agent_Guru.platform.features.reminders import ACTION_GRACE_S, ReminderManager

        target = await self._target(tool, arguments)
        if in_minutes is not None:
            fire_at = time.time() + in_minutes * 60
        elif at_time:
            delay = ReminderManager._parse_time_to_delay(at_time)
            if delay is None:
                msg = f"could not read the time {at_time!r}"
                raise ValueError(msg)
            fire_at = time.time() + delay
        elif every_minutes is not None:
            fire_at = time.time() + every_minutes * 60
        else:
            msg = "say when: in_minutes, at_time or every_minutes"
            raise ValueError(msg)
        every_s = every_minutes * 60 if every_minutes else None
        expires = time.time() + REPEAT_APPROVAL_S if every_s else fire_at + ACTION_GRACE_S
        # Reached only after the tool loop asked the owner and they said yes
        # on their own turn (this tool is not read-only), so the approval is
        # theirs, of exactly these arguments.
        task = await self._orch._reminders().add_action(
            description, server=target.server, tool=target.name, arguments=arguments, fire_at=fire_at,
            approved_by="owner", approval_expires_at=expires, every_s=every_s,
        )
        when = datetime.datetime.fromtimestamp(fire_at).strftime("%a %d %b %H:%M")
        return f"Scheduled {task.reminder_id}: {description}, first at {when}. Approved by you until " + \
            datetime.datetime.fromtimestamp(expires).strftime("%d %b %H:%M") + ".", False, self._stored(task.reminder_id)

    async def _cancel(self, task_id: str) -> tuple[Any, ...]:
        if not self._orch._reminders().cancel_reminder(task_id.strip()):
            return f"There is no task {task_id}.", True
        return f"Cancelled {task_id}.", False, not self._stored(task_id.strip())

    def _stored(self, task_id: str) -> bool:
        """Whether the scheduler now holds *task_id*: the evidence a change was made."""
        return any(t.reminder_id == task_id for t in self._orch._reminders().list_reminders())
