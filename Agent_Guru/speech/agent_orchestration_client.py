"""
Agent Orchestration Client for Speech Engine.

Routes voice commands to the Agent Orchestration system for execution.
Provides status update notifications back to the speech engine.

Performance Requirements:
- Command routing: <100ms overhead
- Status updates: async, non-blocking
- Fallback: graceful degradation when orchestration unavailable

Author: Speech Engine Team
Date: 2026-03-14
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .models import CommandResult

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """Result of routing a command to agent orchestration."""

    success: bool
    task_id: Optional[str]
    output: Any
    error: Optional[str] = None
    routed_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


class AgentOrchestrationClient:
    """
    Client for routing voice commands to the Agent Orchestration system.

    Wraps the OrchestrationSystem with a speech-engine-friendly interface:
    - Converts CommandResult → Task and routes to orchestration
    - Delivers status updates via optional callback
    - Gracefully degrades when orchestration is unavailable

    Time Complexity: O(1) per routing call (async, non-blocking)
    Space Complexity: O(n) for pending task tracking

    Example:
        >>> client = AgentOrchestrationClient(orchestration_system)
        >>> result = await client.route_command(command_result, user_id="user_1")
        >>> print(result.success)
    """

    def __init__(
        self,
        orchestration_system: Optional[Any] = None,
        status_callback: Optional[Callable[[str, str, Any], None]] = None,
    ) -> None:
        """
        Initialize the client.

        Args:
            orchestration_system: OrchestrationSystem instance (None = disabled)
            status_callback: Optional callback(task_id, status, output) for updates
        """
        self._system = orchestration_system
        self._status_callback = status_callback
        self._pending: dict[str, RoutingResult] = {}
        logger.info(
            "AgentOrchestrationClient initialized (system=%s)",
            "connected" if orchestration_system else "disabled",
        )

    async def route_command(
        self,
        command: CommandResult,
        user_id: str = "default_user",
    ) -> RoutingResult:
        """
        Route a parsed voice command to the orchestration system.

        Args:
            command: Parsed command from CommandParser
            user_id: User identifier for task attribution

        Returns:
            RoutingResult with success status and task output
        """
        if not command.is_command or command.action_id is None:
            return RoutingResult(
                success=False,
                task_id=None,
                output=None,
                error="Not a valid command",
            )

        if self._system is None:
            logger.debug("Orchestration unavailable — command %s skipped", command.action_id)
            return RoutingResult(
                success=True,
                task_id=None,
                output=None,
                error=None,
            )

        try:
            task = self._build_task(command, user_id)
            task_result = await self._system.receive_task(task)

            result = RoutingResult(
                success=task_result.success,
                task_id=task_result.task_id,
                output=task_result.output,
                error=task_result.error,
            )

            self._pending[task_result.task_id] = result
            self._notify_status(task_result.task_id, "completed", task_result.output)
            return result

        except Exception as exc:
            logger.error("Command routing failed for %s: %s", command.action_id, exc)
            return RoutingResult(
                success=False,
                task_id=None,
                output=None,
                error=str(exc),
            )

    def _build_task(self, command: CommandResult, user_id: str) -> Any:
        """
        Build an orchestration Task from a CommandResult.

        Uses duck-typing so we don't hard-import the agents module.
        Falls back to a simple namespace object when Task is unavailable.
        """
        try:
            from Agent_Guru.agents.task_decomposer import Task

            return Task(
                id=f"speech_{command.action_id}_{id(command)}",
                description=f"Voice command: {command.action_id}",
                task_type=command.action_id or "UNKNOWN",
                parameters={
                    "action_id": command.action_id,
                    "parameters": command.parameters,
                    "raw_text": command.raw_text,
                    "user_id": user_id,
                },
            )
        except Exception as e:
            # Fallback: simple namespace
            import types

            task = types.SimpleNamespace()
            task.id = f"speech_{command.action_id}_{id(command)}"
            task.description = f"Voice command: {command.action_id}"
            task.task_type = command.action_id or "UNKNOWN"
            task.parameters = {
                "action_id": command.action_id,
                "parameters": command.parameters,
                "raw_text": command.raw_text,
                "user_id": user_id,
            }
            task.dependencies = []
            return task

    def _notify_status(self, task_id: str, status: str, output: Any) -> None:
        """Fire status callback if registered."""
        if self._status_callback:
            try:
                self._status_callback(task_id, status, output)
            except Exception as exc:
                logger.warning("Status callback failed: %s", exc)

    def get_pending_tasks(self) -> dict[str, RoutingResult]:
        """Return snapshot of pending/completed task results."""
        return dict(self._pending)

    def clear_completed(self) -> None:
        """Clear completed task records to free memory."""
        self._pending.clear()
