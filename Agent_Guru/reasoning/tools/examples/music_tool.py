"""
Music tool for playing music.
"""

from typing import Any, Dict

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


@tool(
    tool_id="music.play",
    name="Play Music",
    description="Play music by song, artist, album, or playlist",
    parameters=[
        ToolParameter(
            name="query",
            type=ToolParameterType.STRING,
            description="Song name, artist, album, or playlist to play",
            required=True,
        ),
        ToolParameter(
            name="shuffle",
            type=ToolParameterType.BOOLEAN,
            description="Whether to shuffle playback",
            required=False,
            default=False,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=800,
    capabilities=["music", "media", "entertainment"],
    examples=["Play some jazz music", "Play Bohemian Rhapsody by Queen"],
)
class MusicTool(Tool):
    """Tool for playing music."""

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute music playback.

        Args:
            query: Music query
            shuffle: Whether to shuffle

        Returns:
            Execution result
        """
        query = kwargs["query"]
        shuffle = kwargs.get("shuffle", False)

        # Validate query
        if not query or len(query.strip()) == 0:
            return {
                "success": False,
                "error": "Music query cannot be empty",
            }

        # Mock music playback (in production, would use music API)
        return {
            "success": True,
            "result": {
                "query": query,
                "shuffle": shuffle,
                "now_playing": {
                    "title": "Sample Song",
                    "artist": "Sample Artist",
                    "album": "Sample Album",
                    "duration_seconds": 240,
                },
                "message": f"Now playing: {query}" + (" (shuffled)" if shuffle else ""),
            },
        }
