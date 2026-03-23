"""
Calendar tool for managing calendar events.
"""

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
    tool_id="calendar.create_event",
    name="Create Calendar Event",
    description="Create a new calendar event",
    parameters=[
        ToolParameter(
            name="title",
            type=ToolParameterType.STRING,
            description="Event title",
            required=True,
        ),
        ToolParameter(
            name="start_time",
            type=ToolParameterType.STRING,
            description="Event start time (ISO 8601 format)",
            required=True,
        ),
        ToolParameter(
            name="duration_minutes",
            type=ToolParameterType.INTEGER,
            description="Event duration in minutes",
            required=False,
            default=60,
        ),
        ToolParameter(
            name="location",
            type=ToolParameterType.STRING,
            description="Event location",
            required=False,
            default="",
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=500,
    capabilities=["calendar", "scheduling", "time_management"],
    examples=["Schedule a meeting tomorrow at 2pm", "Add dentist appointment on Friday"],
)
class CalendarTool(Tool):
    """Tool for creating calendar events."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute calendar event creation.

        Args:
            title: Event title
            start_time: Event start time
            duration_minutes: Event duration
            location: Event location

        Returns:
            Execution result
        """
        title = kwargs["title"]
        start_time = kwargs["start_time"]
        duration_minutes = kwargs.get("duration_minutes", 60)
        location = kwargs.get("location", "")

        # Validate title
        if not title or len(title.strip()) == 0:
            return {
                "success": False,
                "error": "Event title cannot be empty",
            }

        # Validate duration
        if duration_minutes <= 0:
            return {
                "success": False,
                "error": "Duration must be positive",
            }

        if duration_minutes > 1440:  # 24 hours
            return {
                "success": False,
                "error": "Duration cannot exceed 24 hours",
            }

        # Generate event ID
        event_id = f"event_{int(time.time() * 1000)}"

        # Mock event creation (in production, would use calendar API)
        return {
            "success": True,
            "result": {
                "event_id": event_id,
                "title": title,
                "start_time": start_time,
                "duration_minutes": duration_minutes,
                "location": location,
                "message": f"Event '{title}' created for {start_time}",
            },
        }
