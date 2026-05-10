"""Weather tool for querying weather information."""

from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


@tool(
    tool_id="weather.query",
    name="Query Weather",
    description="Get current weather information for a location",
    parameters=[
        ToolParameter(
            name="location",
            type=ToolParameterType.STRING,
            description="Location to query weather for (city, zip code, etc.)",
            required=True,
        ),
        ToolParameter(
            name="units",
            type=ToolParameterType.STRING,
            description="Temperature units: 'celsius' or 'fahrenheit'",
            required=False,
            default="celsius",
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=500,
    capabilities=["weather", "information", "location_based"],
    examples=["What's the weather in New York?", "Check weather for 90210"],
)
class WeatherTool(Tool):
    """Tool for querying weather information."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute weather query.

        Args:
            location: Location to query
            units: Temperature units

        Returns:
            Execution result with weather data

        """
        location = kwargs["location"]
        units = kwargs.get("units", "celsius")

        # Validate units
        if units not in ["celsius", "fahrenheit"]:
            return {
                "success": False,
                "error": f"Invalid units: {units}. Must be 'celsius' or 'fahrenheit'",
            }

        # Validate location
        if not location or len(location.strip()) == 0:
            return {
                "success": False,
                "error": "Location cannot be empty",
            }

        # Mock weather data (in production, would call weather API)
        return {
            "success": True,
            "result": {
                "location": location,
                "temperature": 22 if units == "celsius" else 72,
                "units": units,
                "condition": "Partly Cloudy",
                "humidity": 65,
                "wind_speed": 10,
                "message": f"Weather in {location}: 22°C, Partly Cloudy",
            },
        }
