"""Maps and location tools for weather, directions, and place search.

Integrates with weather APIs, mapping services, and location databases.
"""

from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


@tool(
    tool_id="maps.get_weather",
    name="Get Weather",
    description="Get weather information for a location",
    parameters=[
        ToolParameter(
            name="location",
            type=ToolParameterType.STRING,
            description="Location (city name, zip code, or coordinates)",
            required=True,
        ),
        ToolParameter(
            name="units",
            type=ToolParameterType.STRING,
            description="Temperature units (metric, imperial)",
            required=False,
            default="metric",
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1000,
    capabilities=["weather", "location", "maps", "information"],
    examples=[
        "What's the weather in New York",
        "Get weather for San Francisco",
        "How's the weather today",
    ],
)
class GetWeatherTool(Tool):
    """Tool for getting weather information."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute weather retrieval.

        Args:
            location: Location
            units: Temperature units

        Returns:
            Execution result with weather data

        """
        location = kwargs["location"]
        units = kwargs.get("units", "metric").lower()

        # Validate location
        if not location or not location.strip():
            return {
                "success": False,
                "error": "Location cannot be empty",
            }

        # Validate units
        valid_units = ["metric", "imperial"]
        if units not in valid_units:
            return {
                "success": False,
                "error": f"Invalid units. Must be one of: {', '.join(valid_units)}",
            }

        try:
            # BUG FIX (Round 21): this used to unconditionally return the
            # exact same fabricated reading -- 20C/68F, "Partly Cloudy", 65%
            # humidity, wind 10 -- for EVERY location on Earth, with
            # "success": True and no indication whatsoever that it was
            # invented. This is the single most dangerous placeholder found
            # in this round: unlike a calendar or email placeholder (whose
            # falseness the user discovers the moment they check the real
            # thing), fabricated weather data can directly shape a user's
            # real-world decisions (whether to bring an umbrella, dress for
            # cold, delay travel) with total false confidence and no way
            # for the user to sanity-check it in the moment. No weather API
            # is configured in this codebase, so this now honestly fails.
            return {
                "success": False,
                "error": "Weather lookup is not available: no weather API is configured in this build of Agent Guru.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get weather: {e!s}",
            }


@tool(
    tool_id="maps.get_directions",
    name="Get Directions",
    description="Get directions between two locations",
    parameters=[
        ToolParameter(
            name="origin",
            type=ToolParameterType.STRING,
            description="Starting location",
            required=True,
        ),
        ToolParameter(
            name="destination",
            type=ToolParameterType.STRING,
            description="Destination location",
            required=True,
        ),
        ToolParameter(
            name="mode",
            type=ToolParameterType.STRING,
            description="Travel mode (driving, walking, transit, bicycling)",
            required=False,
            default="driving",
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1500,
    capabilities=["directions", "navigation", "maps", "location"],
    examples=[
        "Get directions to the airport",
        "How do I get to downtown",
        "Navigate to the nearest coffee shop",
    ],
)
class GetDirectionsTool(Tool):
    """Tool for getting directions."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute directions retrieval.

        Args:
            origin: Starting location
            destination: Destination
            mode: Travel mode

        Returns:
            Execution result with directions

        """
        origin = kwargs["origin"]
        destination = kwargs["destination"]
        mode = kwargs.get("mode", "driving").lower()

        # Validate locations
        if not origin or not origin.strip():
            return {
                "success": False,
                "error": "Origin cannot be empty",
            }

        if not destination or not destination.strip():
            return {
                "success": False,
                "error": "Destination cannot be empty",
            }

        # Validate mode
        valid_modes = ["driving", "walking", "transit", "bicycling"]
        if mode not in valid_modes:
            return {
                "success": False,
                "error": f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
            }

        try:
            # BUG FIX (Round 21): this used to return identical fabricated
            # directions ("10 km", "15 minutes", "Head north on Main St...")
            # for ANY origin/destination pair -- including pairs on
            # different continents -- with "success": True. No maps API is
            # configured in this codebase, so this now honestly fails
            # instead of inventing a route.
            return {
                "success": False,
                "error": "Directions are not available: no maps/directions API is configured in this build of Agent Guru.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get directions: {e!s}",
            }


@tool(
    tool_id="maps.search_places",
    name="Search Places",
    description="Search for places near a location",
    parameters=[
        ToolParameter(
            name="query",
            type=ToolParameterType.STRING,
            description="Search query (e.g., 'coffee shops', 'restaurants')",
            required=True,
        ),
        ToolParameter(
            name="location",
            type=ToolParameterType.STRING,
            description="Location to search near",
            required=True,
        ),
        ToolParameter(
            name="radius",
            type=ToolParameterType.INTEGER,
            description="Search radius in meters (default: 5000)",
            required=False,
            default=5000,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1500,
    capabilities=["places", "search", "maps", "location", "poi"],
    examples=[
        "Find coffee shops nearby",
        "Search for restaurants near me",
        "Where's the nearest gas station",
    ],
)
class SearchPlacesTool(Tool):
    """Tool for searching places."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute place search.

        Args:
            query: Search query
            location: Location
            radius: Search radius

        Returns:
            Execution result with places

        """
        query = kwargs["query"]
        location = kwargs["location"]
        radius = kwargs.get("radius", 5000)

        # Validate query
        if not query or not query.strip():
            return {
                "success": False,
                "error": "Search query cannot be empty",
            }

        # Validate location
        if not location or not location.strip():
            return {
                "success": False,
                "error": "Location cannot be empty",
            }

        # Validate radius
        if radius <= 0 or radius > 50000:
            return {
                "success": False,
                "error": "Radius must be between 1 and 50000 meters",
            }

        try:
            # BUG FIX (Round 21): this used to unconditionally return
            # "success": True with "place_count": 0 and "places": [] -- an
            # empty-but-successful result indistinguishable from a real
            # search that legitimately found nothing nearby, when in truth
            # no search ever happened. No places API is configured in this
            # codebase, so this now honestly fails.
            return {
                "success": False,
                "error": "Place search is not available: no places API is configured in this build of Agent Guru.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to search places: {e!s}",
            }
