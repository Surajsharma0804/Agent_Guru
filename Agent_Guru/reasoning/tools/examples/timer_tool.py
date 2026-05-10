"""Timer tool for setting and canceling timers."""

import time
from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


@tool(
    tool_id="timer.set",
    name="Set Timer",
    description="Set a timer for a specified duration",
    parameters=[
        ToolParameter(
            name="duration_seconds",
            type=ToolParameterType.INTEGER,
            description="Timer duration in seconds",
            required=True,
        ),
        ToolParameter(
            name="label",
            type=ToolParameterType.STRING,
            description="Optional label for the timer",
            required=False,
            default="Timer",
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=50,
    capabilities=["timer", "time_management", "reminders"],
    examples=["Set a timer for 5 minutes", "Set a 30 second timer for cooking"],
)
class SetTimerTool(Tool):
    """Tool for setting timers."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute timer setting.

        Args:
            duration_seconds: Timer duration in seconds
            label: Optional timer label

        Returns:
            Execution result with timer ID and expiration time

        """
        duration_seconds = kwargs["duration_seconds"]
        label = kwargs.get("label", "Timer")

        # Validate duration
        if duration_seconds <= 0:
            return {
                "success": False,
                "error": "Duration must be positive",
            }

        if duration_seconds > 86400:  # 24 hours
            return {
                "success": False,
                "error": "Duration cannot exceed 24 hours",
            }

        # Generate timer ID
        timer_id = f"timer_{int(time.time() * 1000)}"
        expiration_time = time.time() + duration_seconds

        return {
            "success": True,
            "result": {
                "timer_id": timer_id,
                "label": label,
                "duration_seconds": duration_seconds,
                "expiration_time": expiration_time,
                "message": f"Timer '{label}' set for {duration_seconds} seconds",
            },
        }


@tool(
    tool_id="timer.cancel",
    name="Cancel Timer",
    description="Cancel an active timer",
    parameters=[
        ToolParameter(
            name="timer_id",
            type=ToolParameterType.STRING,
            description="ID of the timer to cancel",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=50,
    capabilities=["timer", "time_management"],
    examples=["Cancel the timer", "Stop the cooking timer"],
)
class CancelTimerTool(Tool):
    """Tool for canceling timers."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute timer cancellation.

        Args:
            timer_id: Timer ID to cancel

        Returns:
            Execution result

        """
        timer_id = kwargs["timer_id"]

        # Validate timer ID format
        if not timer_id.startswith("timer_"):
            return {
                "success": False,
                "error": f"Invalid timer ID: {timer_id}",
            }

        return {
            "success": True,
            "result": {
                "timer_id": timer_id,
                "message": f"Timer {timer_id} cancelled",
            },
        }
