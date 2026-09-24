"""Calendar tools for creating and retrieving calendar events.

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
        # description and location are accepted and documented above, but
        # nothing reads them: this tool has had no calendar backend to send
        # them to since it was changed to fail honestly. Left unread rather
        # than removed from the documented signature, so the day a backend
        # arrives the caller contract does not change.

        # Validate title
        if not title or not title.strip():
            return {
                "success": False,
                "error": "Event title cannot be empty",
            }

        # Validate times
        try:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)

            if end_dt <= start_dt:
                return {
                    "success": False,
                    "error": "End time must be after start time",
                }

        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid time format: {e!s}",
            }

        try:
            # BUG FIX (Round 21): this used to unconditionally claim
            # "success": True with a fabricated event_id and a message
            # reading "Created event '{title}'..." -- no calendar was ever
            # touched, and the user would have no way to know the event
            # doesn't actually exist until they check their real calendar
            # and find it missing. No calendar controller/API credentials
            # exist anywhere in this codebase to delegate to (unlike
            # messaging.py's fix in Round 4), so honestly failing is
            # correct here rather than fabricating an integration this
            # round didn't build or test.
            return {
                "success": False,
                "error": "Calendar integration is not available: no calendar provider is configured in this build of Agent Guru.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create calendar event: {e!s}",
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
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)

            if end_dt <= start_dt:
                return {
                    "success": False,
                    "error": "End date must be after start date",
                }

        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid date format: {e!s}",
            }

        # Validate max_results
        if max_results <= 0 or max_results > 1000:
            return {
                "success": False,
                "error": "max_results must be between 1 and 1000",
            }

        try:
            # BUG FIX (Round 21): this used to unconditionally claim
            # "success": True with "event_count": 0 and "events": [] and a
            # message reading "Retrieved events from..." -- no calendar
            # query ever happened. This is arguably worse than
            # CreateCalendarEventTool's old bug: a user asking "what's on my
            # calendar today" would be confidently told they have ZERO
            # events -- indistinguishable from a real, successful query
            # that legitimately found nothing -- when in truth no query was
            # ever attempted. No calendar provider is configured in this
            # codebase, so this honestly fails instead.
            return {
                "success": False,
                "error": "Calendar integration is not available: no calendar provider is configured in this build of Agent Guru.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get calendar events: {e!s}",
            }
