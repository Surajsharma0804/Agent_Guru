"""Web search tool for searching the internet.

Supports multiple search engines: Google, Bing, DuckDuckGo.
"""

import urllib.parse
from typing import Any

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

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
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

            # BUG FIX (Round 21): this tool used to fabricate a "success"
            # response containing nothing but the search URL, explicitly
            # labeled "This is a placeholder" -- meaning the LLM agent (and
            # therefore the user) received zero actual search content from
            # what is supposed to be the primary web-search capability.
            # A REAL implementation already exists and is already used
            # elsewhere in this codebase for exactly this purpose:
            # platform/features/web_search.py::search_web() -- a genuine
            # three-tier fetcher (duckduckgo-search library, then the
            # DuckDuckGo instant-answer API, then a real browser-driven
            # Google search as a last resort), no API key required. It was
            # simply never wired into this LLM-facing tool. Delegated to it
            # here (lazy import: reasoning/ -> platform/ is a layer
            # boundary this codebase keeps lazy, matching the existing
            # convention e.g. in reasoning/tools/system/app_control.py).
            from Agent_Guru.platform.features.web_search import search_web

            snippet = await search_web(query, max_chars=max_results * 200)

            if snippet:
                return {
                    "success": True,
                    "result": {
                        "query": query,
                        "engine": engine,
                        "search_url": search_url,
                        "max_results": max_results,
                        "results_text": snippet,
                        "message": f"Found web results for '{query}'",
                    },
                }

            # Genuinely no live result available (no ddgs installed, no
            # network reachable, and no browser available for the
            # last-resort fallback) -- honest about that rather than
            # claiming success with nothing behind it. The search URL is
            # still real and still useful, so it's included as a fallback
            # the agent can offer to open for the user.
            return {
                "success": False,
                "error": (
                    "Could not retrieve live web results (no search backend "
                    "available: duckduckgo-search is not installed, the "
                    "DuckDuckGo instant-answer API was unreachable, and no "
                    "browser fallback was available). You can still open "
                    f"{search_url} directly."
                ),
                "result": {
                    "query": query,
                    "engine": engine,
                    "search_url": search_url,
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to perform web search: {e!s}",
            }
