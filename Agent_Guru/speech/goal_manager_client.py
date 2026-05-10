"""Goal Manager Client for Speech Engine.

Enables voice-driven task creation by routing task-creation commands
to the Goal Manager system with verbal confirmation support.

Performance Requirements:
- Task creation: async, non-blocking (<100ms overhead)
- Graceful degradation when goal manager unavailable

Author: Speech Engine Team
Date: 2026-03-14
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TaskCreationResult:
    """Result of creating a task via voice command."""

    success: bool
    goal_id: str | None
    description: str
    confirmation_text: str
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class GoalManagerClient:
    """Client for creating goals/tasks via voice commands.

    Converts voice-driven task descriptions into Goal Manager goals,
    and generates verbal confirmation text for TTS synthesis.

    Gracefully degrades when the Goal Manager is unavailable.

    Time Complexity: O(1) per task creation
    Space Complexity: O(1)

    Example:
        >>> client = GoalManagerClient(goal_manager)
        >>> result = await client.create_task("Remind me to call John at 3pm")
        >>> print(result.confirmation_text)
        "Task created: Remind me to call John at 3pm"

    """

    def __init__(self, goal_manager: Any | None = None) -> None:
        """Initialize the client.

        Args:
            goal_manager: GoalManager instance (None = disabled)

        """
        self._manager = goal_manager
        logger.info(
            "GoalManagerClient initialized (manager=%s)",
            "connected" if goal_manager else "disabled",
        )

    async def create_task(
        self,
        description: str,
        priority: str = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> TaskCreationResult:
        """Create a task from a voice command description.

        Args:
            description: Natural language task description from voice command
            priority: Task priority ("critical", "high", "medium", "low")
            metadata: Optional additional context

        Returns:
            TaskCreationResult with goal_id and verbal confirmation text

        """
        if not description or not description.strip():
            return TaskCreationResult(
                success=False,
                goal_id=None,
                description=description,
                confirmation_text="Sorry, I couldn't understand the task description.",
                error="Empty description",
            )

        if self._manager is None:
            logger.debug("Goal manager unavailable — task creation skipped")
            return TaskCreationResult(
                success=True,
                goal_id=None,
                description=description,
                confirmation_text=f"Task noted: {description}",
            )

        try:
            priority_map = {
                "critical": "critical",
                "high": "high",
                "medium": "medium",
                "low": "low",
            }
            mapped_priority = priority_map.get(priority.lower(), "medium")

            goal = await self._manager.create_goal(
                description=description,
                priority=mapped_priority,
                metadata=metadata or {},
            )

            goal_id = str(goal.id) if hasattr(goal, "id") else str(goal)
            confirmation = f"Task created: {description}"

            logger.info("Voice task created: goal_id=%s description=%s", goal_id, description)

            return TaskCreationResult(
                success=True,
                goal_id=goal_id,
                description=description,
                confirmation_text=confirmation,
            )

        except Exception as exc:
            logger.exception("Failed to create task '%s': %s", description, exc)
            return TaskCreationResult(
                success=False,
                goal_id=None,
                description=description,
                confirmation_text=f"Sorry, I couldn't create the task: {description}",
                error=str(exc),
            )

    async def cancel_task(self, goal_id: str) -> bool:
        """Cancel a previously created task.

        Args:
            goal_id: Goal identifier to cancel

        Returns:
            True if cancelled successfully, False on error

        """
        if self._manager is None:
            return True

        try:
            await self._manager.cancel_goal(goal_id)
            logger.info("Voice task cancelled: goal_id=%s", goal_id)
            return True
        except Exception:
            logger.exception("Failed to cancel task %s: %s")
            return False

    def build_confirmation_text(self, description: str, success: bool) -> str:
        """Build verbal confirmation text for TTS synthesis.

        Args:
            description: Task description
            success: Whether task was created successfully

        Returns:
            Natural language confirmation for TTS

        """
        if success:
            return f"Task created: {description}"
        return "Sorry, I couldn't create the task. Please try again."
