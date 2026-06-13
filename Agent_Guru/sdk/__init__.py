"""Agent Guru Skill SDK.

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

from Agent_Guru.sdk.client import AgentGuruClient
from Agent_Guru.sdk.exceptions import (
    InvalidParameterError,
    ProviderUnavailableError,
    RateLimitError,
)
from Agent_Guru.sdk.manifest import ManifestGenerator
from Agent_Guru.sdk.mock_server import MockServer
from Agent_Guru.sdk.skill import Skill, skill_capability, skill_parameter

__all__ = [
    "AgentGuruClient",
    "InvalidParameterError",
    "ManifestGenerator",
    "MockServer",
    "ProviderUnavailableError",
    "RateLimitError",
    "Skill",
    "skill_capability",
    "skill_parameter",
]

__version__ = "1.0.0"
