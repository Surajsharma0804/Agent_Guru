"""
Example weather skill for Agent Guru.

This skill demonstrates how to create a simple skill that provides
weather information.
"""

from typing import Dict
from Agent_Guru.sdk import Skill, skill_capability


class WeatherSkill(Skill):
    """Weather information skill."""

    def __init__(self):
        """Initialize weather skill."""
        super().__init__()

    @skill_capability("get_weather", "Get current weather for a location")
    async def get_weather(self, location: str) -> Dict[str, any]:
        """Get current weather for a location.

        Args:
            location: Location name (city, state, country)

        Returns:
            Weather information dictionary
        """
        # In a real implementation, this would call a weather API
        # For demo purposes, return mock data
        return {
            "location": location,
            "temperature": 72,
            "temperature_unit": "F",
            "condition": "sunny",
            "humidity": 45,
            "wind_speed": 10,
            "wind_unit": "mph",
        }

    @skill_capability("get_forecast", "Get weather forecast for a location")
    async def get_forecast(
        self, location: str, days: int = 3
    ) -> Dict[str, any]:
        """Get weather forecast for a location.

        Args:
            location: Location name
            days: Number of days to forecast (1-7)

        Returns:
            Forecast information dictionary
        """
        # Mock forecast data
        forecast = []
        for day in range(min(days, 7)):
            forecast.append(
                {
                    "day": day + 1,
                    "temperature_high": 75 + day,
                    "temperature_low": 55 + day,
                    "condition": "partly cloudy" if day % 2 == 0 else "sunny",
                }
            )

        return {
            "location": location,
            "forecast": forecast,
        }


# Generate manifest when run as script
if __name__ == "__main__":
    from pathlib import Path
    from Agent_Guru.sdk import ManifestGenerator

    manifest = ManifestGenerator.generate_and_save(
        skill_class=WeatherSkill,
        output_path=Path("weather_skill_manifest.json"),
        skill_id="com.example.weather",
        version="1.0.0",
        name="Weather Skill",
        description="Provides weather information and forecasts",
        author="Example Developer",
        required_permissions=["network_access"],
        max_latency=3000,
        dependencies=["requests>=2.28.0"],
        metadata={
            "allowed_endpoints": [
                "api.openweathermap.org",
                "api.weatherapi.com",
            ]
        },
    )

    print("Manifest generated successfully!")
    print(f"Capabilities: {manifest['capabilities']}")
