"""
Information tools for news and stock prices.

Provides access to news APIs and financial data.
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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute news retrieval.

        Args:
            query: Search query
            category: News category
            max_results: Maximum results

        Returns:
            Execution result with news articles
        """
        query = kwargs.get("query", "")
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
            # Note: In a real implementation, this would use NewsAPI,
            # Google News API, or similar service
            return {
                "success": True,
                "result": {
                    "query": query,
                    "category": category,
                    "article_count": 0,
                    "articles": [],
                    "message": f"Retrieved {category} news" + (f" for '{query}'" if query else ""),
                    "note": "This is a placeholder. Real implementation would use news API.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get news: {str(e)}",
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
        )
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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
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
            # Note: In a real implementation, this would use Alpha Vantage,
            # Yahoo Finance API, or similar service
            return {
                "success": True,
                "result": {
                    "symbol": symbol,
                    "price": 150.00,
                    "change": 2.50,
                    "change_percent": 1.69,
                    "volume": 1000000,
                    "market_cap": "2.5T",
                    "message": f"Stock data for {symbol}",
                    "note": "This is a placeholder. Real implementation would use financial API.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get stock price: {str(e)}",
            }
