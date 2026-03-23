"""
Calendar tools for creating and retrieving calendar events.

Supports Google Calendar, Outlook Calendar, and other calendar services.
"""

from datetime import datetime
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
            description="Event start time (ISO format)",
            required=True,
        ),
        ToolParameter(
            name="end_time",
            type=ToolParameterType.STRING,
            description="Event end time (ISO format)",
            required=True,
        ),
        ToolParameter(
            name="description",
            type=ToolParameterType.STRING,
            description="Event description",
            required=False,
            default="",
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
    estimated_latency_ms=1500,
    capabilities=["calendar", "scheduling", "create_event", "time_management"],
    examples=[
        "Create a meeting at 2pm tomorrow",
        "Schedule a dentist appointment",
        "Add team standup to calendar",
    ],
)
class CreateCalendarEventTool(Tool):
    """Tool for creating calendar events."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute calendar event creation.

        Args:
            title: Event title
            start_time: Start time
            end_time: End time
            description: Event description
            location: Event location

        Returns:
            Execution result
        """
        title = kwargs["title"]
        start_time = kwargs["start_time"]
        end_time = kwargs["end_time"]
        description = kwargs.get("description", "")
        location = kwargs.get("location", "")

        # Validate title
        if not title or not title.strip():
            return {
                "success": False,
                "error": "Event title cannot be empty",
            }

        # Validate times
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            if end_dt <= start_dt:
                return {
                    "success": False,
                    "error": "End time must be after start time",
                }

        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid time format: {str(e)}",
            }

        try:
            # Note: In a real implementation, this would use Google Calendar API,
            # Microsoft Graph API, or other calendar service
            event_id = f"event_{hash(title + start_time)}"

            return {
                "success": True,
                "result": {
                    "event_id": event_id,
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time,
                    "description": description,
                    "location": location,
                    "message": f"Created event '{title}' from {start_time} to {end_time}",
                    "note": "This is a placeholder. Real implementation would use calendar API.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create calendar event: {str(e)}",
            }


@tool(
    tool_id="calendar.get_events",
    name="Get Calendar Events",
    description="Get calendar events for a date range",
    parameters=[
        ToolParameter(
            name="start_date",
            type=ToolParameterType.STRING,
            description="Start date (ISO format)",
            required=True,
        ),
        ToolParameter(
            name="end_date",
            type=ToolParameterType.STRING,
            description="End date (ISO format)",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type=ToolParameterType.INTEGER,
            description="Maximum number of events to return (default: 50)",
            required=False,
            default=50,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1000,
    capabilities=["calendar", "scheduling", "get_events", "time_management"],
    examples=[
        "What's on my calendar today",
        "Show me this week's meetings",
        "Get my calendar events for tomorrow",
    ],
)
class GetCalendarEventsTool(Tool):
    """Tool for retrieving calendar events."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute calendar event retrieval.

        Args:
            start_date: Start date
            end_date: End date
            max_results: Maximum results

        Returns:
            Execution result with events
        """
        start_date = kwargs["start_date"]
        end_date = kwargs["end_date"]
        max_results = kwargs.get("max_results", 50)

        # Validate dates
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

            if end_dt <= start_dt:
                return {
                    "success": False,
                    "error": "End date must be after start date",
                }

        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid date format: {str(e)}",
            }

        # Validate max_results
        if max_results <= 0 or max_results > 1000:
            return {
                "success": False,
                "error": "max_results must be between 1 and 1000",
            }

        try:
            # Note: In a real implementation, this would query calendar API
            return {
                "success": True,
                "result": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "event_count": 0,
                    "events": [],
                    "message": f"Retrieved events from {start_date} to {end_date}",
                    "note": "This is a placeholder. Real implementation would query calendar API.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get calendar events: {str(e)}",
            }
