"""
Web search tool for searching the internet.

Supports multiple search engines: Google, Bing, DuckDuckGo.
"""

import urllib.parse
from typing import Any, Dict

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


@tool(
    tool_id="web.search",
    name="Web Search",
    description="Search the web for information",
    parameters=[
        ToolParameter(
            name="query",
            type=ToolParameterType.STRING,
            description="Search query",
            required=True,
        ),
        ToolParameter(
            name="engine",
            type=ToolParameterType.STRING,
            description="Search engine (google, bing, duckduckgo)",
            required=False,
            default="google",
        ),
        ToolParameter(
            name="max_results",
            type=ToolParameterType.INTEGER,
            description="Maximum number of results (default: 10)",
            required=False,
            default=10,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1000,
    capabilities=["web_search", "search", "internet_search", "knowledge_retrieval"],
    examples=[
        "Search for Python tutorials",
        "Find information about climate change",
        "Search the web for best restaurants nearby",
    ],
)
class WebSearchTool(Tool):
    """Tool for web searching."""

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute web search.

        Args:
            query: Search query
            engine: Search engine to use
            max_results: Maximum number of results

        Returns:
            Execution result with search results
        """
        query = kwargs["query"]
        engine = kwargs.get("engine", "google").lower()
        max_results = kwargs.get("max_results", 10)

        # Validate query
        if not query or not query.strip():
            return {
                "success": False,
                "error": "Search query cannot be empty",
            }

        # Validate engine
        valid_engines = ["google", "bing", "duckduckgo"]
        if engine not in valid_engines:
            return {
                "success": False,
                "error": f"Invalid search engine. Must be one of: {', '.join(valid_engines)}",
            }

        # Validate max_results
        if max_results <= 0 or max_results > 100:
            return {
                "success": False,
                "error": "max_results must be between 1 and 100",
            }

        try:
            # Build search URL
            encoded_query = urllib.parse.quote_plus(query)

            if engine == "google":
                search_url = f"https://www.google.com/search?q={encoded_query}"
            elif engine == "bing":
                search_url = f"https://www.bing.com/search?q={encoded_query}"
            elif engine == "duckduckgo":
                search_url = f"https://duckduckgo.com/?q={encoded_query}"

            # Note: In a real implementation, you would use an API or web scraping
            # For now, we return a mock response with the search URL
            return {
                "success": True,
                "result": {
                    "query": query,
                    "engine": engine,
                    "search_url": search_url,
                    "max_results": max_results,
                    "message": f"Search URL generated for '{query}' on {engine}",
                    "note": "This is a placeholder. Real implementation would use search API or web scraping.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to perform web search: {str(e)}",
            }
