"""
Agent Guru Skill SDK.

This SDK provides tools for developers to create third-party skills
for the Agent Guru reasoning engine.

Example:
    from agent_guru_sdk import Skill, skill_capability

    class WeatherSkill(Skill):
        @skill_capability("weather_query")
        async def get_weather(self, location: str) -> dict:
            # Implementation
            return {"temperature": 72, "condition": "sunny"}
"""

from Agent_Guru.sdk.skill import Skill, skill_capability, skill_parameter
from Agent_Guru.sdk.manifest import ManifestGenerator

__all__ = [
    "Skill",
    "skill_capability",
    "skill_parameter",
    "ManifestGenerator",
]

__version__ = "1.0.0"
