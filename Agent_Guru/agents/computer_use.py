"""Autonomous Agentic Task Execution with ReAct-style decomposition."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PERCEPTION_TIMEOUT_MS = 200
HALT_TIMEOUT_MS = 500
TASK_TIMEOUT_S = 120
MAX_RECOVERY_ATTEMPTS = 3

CONFIRMATION_REQUIRED_ACTIONS = {"financial", "communication", "persistent_data"}

try:
    from playwright.async_api import async_playwright  # type: ignore[import]
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
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class AgenticTask:
    """A high-level agentic task."""
    task_id: str
    description: str
    task_type: str = "general"
    actions: List[UIAction] = field(default_factory=list)
    status: str = "pending"
    result: Optional[str] = None
    created_at: float = field(default_factory=time.time)


# Task templates for common service categories
TASK_TEMPLATES: Dict[str, List[str]] = {
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
        self._audit_log: List[Dict[str, Any]] = []

    async def perceive(self, screenshot: Optional[bytes] = None) -> Dict[str, Any]:
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

    def decompose(self, task: AgenticTask) -> List[UIAction]:
        """Decompose task into UIAction sequence using ReAct-style prompting."""
        template = TASK_TEMPLATES.get(task.task_type, [])
        actions = []
        for step in template:
            category = "general"
            if task.task_type in ("food_ordering", "ride_booking"):
                category = "financial"
            elif task.task_type == "email_composition":
                category = "communication"
            actions.append(UIAction(
                action_type=ActionType.CLICK,
                target=step,
                requires_confirmation=category in CONFIRMATION_REQUIRED_ACTIONS,
                action_category=category,
            ))
        if not actions:
            actions.append(UIAction(
                action_type=ActionType.CLICK,
                target=task.description[:50],
            ))
        return actions

    async def execute(
        self,
        task: AgenticTask,
        confirm_callback: Optional[Any] = None,
    ) -> AgenticTask:
        """Execute task with confirmation gate and timeout."""
        self._cancelled = False
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

        except asyncio.TimeoutError:
            task.status = "timeout"
            logger.warning("Task %s timed out after %ds", task.task_id, TASK_TIMEOUT_S)
            return task

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
        """Halt execution within 500ms."""
        start = time.perf_counter()
        self._cancelled = True
        await asyncio.sleep(0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Halted in %.1fms", elapsed_ms)
        raise asyncio.CancelledError("Task halted by user")

    def _log_action(self, action: UIAction, result: ActionResult) -> None:
        self._audit_log.append({
            "action": action.action_type.value,
            "target": action.target,
            "success": result.success,
            "before": result.before_state,
            "after": result.after_state,
            "ts": time.time(),
        })

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit_log)
