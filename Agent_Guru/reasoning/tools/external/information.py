"""Information tools for news and stock prices.

Provides access to news APIs and financial data.
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
    tool_id="information.get_news",
    name="Get News",
    description="Get latest news articles",
    parameters=[
        ToolParameter(
            name="query",
            type=ToolParameterType.STRING,
            description="News search query or topic",
            required=False,
            default="",
        ),
        ToolParameter(
            name="category",
            type=ToolParameterType.STRING,
            description="News category (business, technology, sports, etc.)",
            required=False,
            default="general",
        ),
        ToolParameter(
            name="max_results",
            type=ToolParameterType.INTEGER,
            description="Maximum number of articles (default: 10)",
            required=False,
            default=10,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1500,
    capabilities=["news", "information", "current_events"],
    examples=[
        "Get latest news",
        "Show me technology news",
        "What's happening in sports",
    ],
)
class GetNewsTool(Tool):
    """Tool for getting news articles."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute news retrieval.

        Args:
            query: Search query
            category: News category
            max_results: Maximum results

        Returns:
            Execution result with news articles

        """
        # query is accepted and documented above but unread: there is no news
        # backend in this build to search with it (see the note below).
        category = kwargs.get("category", "general").lower()
        max_results = kwargs.get("max_results", 10)

        # Validate category
        valid_categories = [
            "general",
            "business",
            "technology",
            "sports",
            "entertainment",
            "health",
            "science",
        ]
        if category not in valid_categories:
            return {
                "success": False,
                "error": f"Invalid category. Must be one of: {', '.join(valid_categories)}",
            }

        # Validate max_results
        if max_results <= 0 or max_results > 100:
            return {
                "success": False,
                "error": "max_results must be between 1 and 100",
            }

        try:
            # BUG FIX (Round 21): this used to unconditionally return
            # "success": True with "article_count": 0 and "articles": [] --
            # indistinguishable from a real query that legitimately found no
            # matching news, when no query ever happened. A generic web
            # search (the real backend wired into web_search.py/
            # information.py's knowledge-tool siblings this same round)
            # isn't a safe substitute here: this tool's contract promises
            # structured article objects (titles, sources, dates), which a
            # search snippet can't reliably provide -- returning something
            # that looks structured but is really just chopped-up search
            # text would trade one kind of dishonesty for another. No news
            # API is configured in this codebase, so this now honestly
            # fails.
            return {
                "success": False,
                "error": "News retrieval is not available: no news API is configured in this build of Agent Guru.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get news: {e!s}",
            }


@tool(
    tool_id="information.get_stock_price",
    name="Get Stock Price",
    description="Get current stock price and information",
    parameters=[
        ToolParameter(
            name="symbol",
            type=ToolParameterType.STRING,
            description="Stock ticker symbol (e.g., AAPL, GOOGL)",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1000,
    capabilities=["stocks", "finance", "market_data", "information"],
    examples=[
        "Get Apple stock price",
        "What's TSLA trading at",
        "Show me Google stock",
    ],
)
class GetStockPriceTool(Tool):
    """Tool for getting stock prices."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute stock price retrieval.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Execution result with stock data

        """
        symbol = kwargs["symbol"].upper()

        # Validate symbol
        if not symbol or not symbol.strip():
            return {
                "success": False,
                "error": "Stock symbol cannot be empty",
            }

        # Basic symbol validation (alphanumeric only)
        if not symbol.replace(".", "").isalnum():
            return {
                "success": False,
                "error": "Invalid stock symbol format",
            }

        try:
            # BUG FIX (Round 21): this used to return the EXACT SAME
            # fabricated numbers ($150.00, +$2.50, +1.69%, 1M volume, $2.5T
            # market cap) for ANY ticker symbol whatsoever, with
            # "success": True and no indication it was invented. Of every
            # placeholder found in this audit, this is the one with the
            # clearest potential for direct real-world harm: a user asking
            # about a real position or a trade decision could act on a
            # completely fabricated price with total false confidence, and
            # -- per this system prompt's own guidance on financial
            # information -- Agent Guru must not present confident,
            # made-up financial data as fact. No financial-data API is
            # configured in this codebase, so this now honestly fails
            # rather than inventing a price.
            return {
                "success": False,
                "error": f"Stock price lookup is not available for {symbol}: no financial data API is configured in this build of Agent Guru.",
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get stock price: {e!s}",
            }
