"""Autonomous Agentic Task Execution with ReAct-style decomposition."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

PERCEPTION_TIMEOUT_MS = 200
HALT_TIMEOUT_MS = 500
TASK_TIMEOUT_S = 120
MAX_RECOVERY_ATTEMPTS = 3

CONFIRMATION_REQUIRED_ACTIONS = frozenset({"financial", "communication", "persistent_data"})

try:
    from playwright.async_api import async_playwright  # type: ignore[import]  # noqa: F401

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False


class ActionType(Enum):
    CLICK = "click"
    TYPE = "type"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    WAIT = "wait"


@dataclass
class UIAction:
    """A single UI action in a task sequence."""

    action_type: ActionType
    target: str
    value: str = ""
    requires_confirmation: bool = False
    action_category: str = "general"


@dataclass
class ActionResult:
    """Result of executing a UI action."""

    success: bool
    action: UIAction
    before_state: str | None = None
    after_state: str | None = None
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class AgenticTask:
    """A high-level agentic task."""

    task_id: str
    description: str
    task_type: str = "general"
    actions: list[UIAction] = field(default_factory=list)
    status: str = "pending"
    result: str | None = None
    created_at: float = field(default_factory=time.time)


# Task templates for common service categories
TASK_TEMPLATES: dict[str, list[str]] = {
    "ride_booking": ["open_app", "enter_destination", "select_ride", "confirm"],
    "food_ordering": ["open_app", "browse_menu", "add_to_cart", "checkout"],
    "restaurant_reservation": ["search_restaurant", "select_date", "enter_party_size", "confirm"],
    "calendar_scheduling": ["open_calendar", "create_event", "set_time", "invite_attendees"],
    "email_composition": ["open_email", "compose", "enter_recipient", "enter_subject", "send"],
    "form_filling": ["navigate_to_form", "fill_fields", "review", "submit"],
}


class ComputerUseAgent:
    """Autonomous agent for computer use tasks with ReAct-style decomposition."""

    def __init__(self) -> None:
        self._cancelled = False
        self._audit_log: list[dict[str, Any]] = []
        # BUG FIX: see _execute_action()/perceive()/recover() -- these
        # are stubs (no real UI perception or automation is wired in
        # yet), so _execute_action() always reports success regardless
        # of whether anything real happened. A caller that only checks
        # the returned AgenticTask.status has no way to know this.
        # This flag makes sure a WARNING is logged the first time this
        # agent actually runs, so 'completed' is never silently
        # mistaken for proof that real work happened.
        self._stub_mode_warned = False
        # BUG FIX: tracks the asyncio.Task running execute(), so halt()
        # (called from a DIFFERENT coroutine, e.g. a "stop" button
        # handler) can actually cancel it -- see halt()'s docstring for
        # the full explanation of why this is required.
        self._current_task: asyncio.Task[Any] | None = None

    async def perceive(self, screenshot: bytes | None = None) -> dict[str, Any]:
        """Identify UI elements from screenshot within 200ms."""
        start = time.perf_counter()
        # Stub: in production uses GPT-4V/Gemini Vision
        await asyncio.sleep(0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "elements": [],
            "page_title": "Unknown",
            "latency_ms": elapsed_ms,
        }

    def decompose(self, task: AgenticTask) -> list[UIAction]:
        """Decompose task into UIAction sequence using ReAct-style prompting."""
        template = TASK_TEMPLATES.get(task.task_type, [])
        actions = []
        for step in template:
            category = "general"
            if task.task_type in ("food_ordering", "ride_booking"):
                category = "financial"
            elif task.task_type == "email_composition":
                category = "communication"
            actions.append(
                UIAction(
                    action_type=ActionType.CLICK,
                    target=step,
                    requires_confirmation=category in CONFIRMATION_REQUIRED_ACTIONS,
                    action_category=category,
                ),
            )
        if not actions:
            actions.append(
                UIAction(
                    action_type=ActionType.CLICK,
                    target=task.description[:50],
                ),
            )
        return actions

    async def execute(
        self,
        task: AgenticTask,
        confirm_callback: Any | None = None,
    ) -> AgenticTask:
        """Execute task with confirmation gate and timeout."""
        if not self._stub_mode_warned:
            logger.warning(
                "ComputerUseAgent is running in STUB mode: perceive(), "
                "_execute_action(), and recover() do not perform any "
                "real UI perception or automation -- every action is "
                "simulated as successful. A 'completed' task status is "
                "NOT proof that any real-world action occurred.",
            )
            self._stub_mode_warned = True
        self._cancelled = False
        # BUG FIX: record the Task this coroutine is running as, so a
        # concurrent halt() call (from a different coroutine) has a real
        # asyncio.Task object to cancel -- see halt()'s docstring.
        self._current_task = asyncio.current_task()
        task.status = "running"
        actions = self.decompose(task)

        try:
            async with asyncio.timeout(TASK_TIMEOUT_S):
                for action in actions:
                    if self._cancelled:
                        task.status = "cancelled"
                        return task

                    # Confirmation gate
                    if action.requires_confirmation and confirm_callback:
                        confirmed = await confirm_callback(action)
                        if not confirmed:
                            task.status = "cancelled"
                            return task

                    result = await self._execute_action(action)
                    self._log_action(action, result)

                    if not result.success:
                        recovered = await self.recover(action)
                        if not recovered:
                            task.status = "failed"
                            return task
                        # BUG FIX: recover() returning True means the
                        # blocking condition was addressed, not that
                        # this action's own effect already happened --
                        # previously execution just moved on to the
                        # NEXT action, silently skipping this one's
                        # real-world effect forever while still
                        # letting the task finish as "completed". Retry
                        # the action once now that recovery reported
                        # success; only a real success lets execution
                        # continue.
                        result = await self._execute_action(action)
                        self._log_action(action, result)
                        if not result.success:
                            task.status = "failed"
                            return task

        except TimeoutError:
            task.status = "timeout"
            # BUG FIX: previously logged
            # `task.timeout_seconds if hasattr(task, "timeout_seconds")
            # else 0` -- AgenticTask has no timeout_seconds field at all,
            # so hasattr() was always False and this always logged 0,
            # never the real timeout. Logs the actual constant that was
            # passed to asyncio.timeout() above instead.
            logger.exception(
                "Task %s timed out after %ds",
                task.task_id,
                TASK_TIMEOUT_S,
            )
            return task
        except asyncio.CancelledError:
            # BUG FIX: this is the counterpart to halt()'s fix below --
            # halt() now cancels self._current_task (this coroutine's own
            # Task) directly, which is the only way asyncio actually
            # interrupts a coroutine mid-await (e.g. mid in-flight
            # action), not just between loop iterations like the
            # self._cancelled flag check above. Note this except clause
            # can ONLY fire for an externally-triggered cancellation
            # (i.e. halt()): asyncio.timeout()'s own deadline-triggered
            # cancellation is already converted to TimeoutError by the
            # `async with` block above before reaching here, so the two
            # except clauses are cleanly disjoint. Caught (not
            # re-raised) deliberately, mirroring how TimeoutError is
            # already absorbed into a returned status above -- this
            # method's whole contract is "always return an AgenticTask
            # describing the outcome", never raise for an expected
            # halt/timeout/cancel outcome.
            task.status = "cancelled"
            logger.info("Task %s halted mid-execution", task.task_id)
            return task
        finally:
            self._current_task = None

        task.status = "completed"
        task.result = f"Completed: {task.description}"
        return task

    async def _execute_action(self, action: UIAction) -> ActionResult:
        """Execute a single UI action."""
        start = time.perf_counter()
        await asyncio.sleep(0)  # Stub
        return ActionResult(
            success=True,
            action=action,
            before_state="before",
            after_state="after",
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    async def recover(self, failed_action: UIAction) -> bool:
        """Attempt recovery with up to 3 strategies."""
        for attempt in range(MAX_RECOVERY_ATTEMPTS):
            logger.info("Recovery attempt %d for action %s", attempt + 1, failed_action.target)
            await asyncio.sleep(0)
            # Stub: return True on first attempt
            return True
        return False

    async def halt(self) -> None:
        """Halt execution within 500ms.

        BUG FIX: previously this only (a) set self._cancelled, a flag
        that execute()'s loop checked only BETWEEN actions -- not during
        an in-flight action's await, so a slow or hung action was never
        actually interrupted -- and (b) raised asyncio.CancelledError in
        halt()'s OWN calling context, which has no effect whatsoever on
        the separate, still-running execute() coroutine: CancelledError
        only stops a task when the asyncio runtime delivers it INSIDE
        that task (via Task.cancel()), not when an unrelated caller
        raises it in its own frame. Net effect: halt() never actually
        halted anything faster than the current action's own natural
        completion -- directly contradicting this method's "within
        500ms" contract, and defeating the entire purpose of a safety
        kill-switch for an agent that can take real, confirmed,
        real-world actions (financial, communication, persistent-data).

        Fixed: execute() now records its own asyncio.Task (via
        asyncio.current_task()) when it starts, and halt() calls
        .cancel() on that exact task -- the correct, standard asyncio
        mechanism to interrupt a coroutine at its very next await point,
        including mid in-flight action, not just between loop
        iterations. halt() then waits, bounded by HALT_TIMEOUT_MS (the
        constant this method always declared but never actually used),
        for that cancellation to actually take effect before returning,
        so callers get a real, observable guarantee instead of a
        fire-and-forget signal.
        """
        start = time.perf_counter()
        self._cancelled = True
        target_task = self._current_task
        if target_task is not None and not target_task.done():
            target_task.cancel()
            try:
                await asyncio.wait_for(target_task, timeout=HALT_TIMEOUT_MS / 1000)
            except TimeoutError:
                logger.warning(
                    "halt(): target task did not stop within %dms", HALT_TIMEOUT_MS,
                )
            except asyncio.CancelledError:
                # halt() itself is being cancelled (e.g. caller torn
                # down) -- the target task's own .cancel() request
                # above still stands regardless, so this is safe to
                # ignore rather than letting it mask the halt outcome.
                pass
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Halted in %.1fms", elapsed_ms)

    def _log_action(self, action: UIAction, result: ActionResult) -> None:
        self._audit_log.append(
            {
                "action": action.action_type.value,
                "target": action.target,
                "success": result.success,
                "before": result.before_state,
                "after": result.after_state,
                "ts": time.time(),
            },
        )

    def get_audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)
