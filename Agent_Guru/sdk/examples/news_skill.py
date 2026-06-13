"""Example news skill for Agent Guru.

This skill demonstrates how to create a skill that fetches
news articles from external sources.
"""

from typing import Any

from Agent_Guru.sdk import Skill, skill_capability


class NewsSkill(Skill):
    """News aggregation skill."""

    def __init__(self) -> None:
        """Initialize news skill."""
        super().__init__()

    @skill_capability("get_headlines", "Get top news headlines")
    async def get_headlines(self, category: str = "general", count: int = 5) -> dict[str, Any]:
        """Get top news headlines.

        Args:
            category: News category (general, business, technology, sports, entertainment)
            count: Number of headlines to return (1-20)

        Returns:
            Headlines dictionary

        """
        # In a real implementation, this would call a news API
        # For demo purposes, return mock data
        headlines = []
        for i in range(min(count, 20)):
            headlines.append(
                {
                    "title": f"Sample {category} headline {i + 1}",
                    "source": "Example News",
                    "published_at": "2024-01-15T10:00:00Z",
                    "url": f"https://example.com/article-{i + 1}",
                },
            )

        return {
            "category": category,
            "count": len(headlines),
            "headlines": headlines,
        }

    @skill_capability("search_news", "Search for news articles")
    async def search_news(self, query: str, count: int = 10) -> dict[str, Any]:
        """Search for news articles by query.

        Args:
            query: Search query
            count: Number of results to return (1-50)

        Returns:
            Search results dictionary

        """
        # Mock search results
        results = []
        for i in range(min(count, 50)):
            results.append(
                {
                    "title": f"Article about {query} - {i + 1}",
                    "source": "Example News",
                    "published_at": "2024-01-15T10:00:00Z",
                    "url": f"https://example.com/search-{i + 1}",
                    "snippet": f"This article discusses {query} in detail...",
                },
            )

        return {
            "query": query,
            "count": len(results),
            "results": results,
        }

    @skill_capability("get_sources", "Get available news sources")
    async def get_sources(self, category: str = "all") -> dict[str, Any]:
        """Get list of available news sources.

        Args:
            category: Filter by category (all, business, technology, sports, entertainment)

        Returns:
            Sources dictionary

        """
        # Mock sources
        sources = [
            {
                "id": "example-news",
                "name": "Example News",
                "category": "general",
                "country": "us",
                "language": "en",
            },
            {
                "id": "tech-times",
                "name": "Tech Times",
                "category": "technology",
                "country": "us",
                "language": "en",
            },
            {
                "id": "business-daily",
                "name": "Business Daily",
                "category": "business",
                "country": "us",
                "language": "en",
            },
        ]

        # Filter by category if specified
        if category != "all":
            sources = [s for s in sources if s["category"] == category]

        return {
            "category": category,
            "count": len(sources),
            "sources": sources,
        }


# Generate manifest when run as script
if __name__ == "__main__":
    from pathlib import Path

    from Agent_Guru.sdk import ManifestGenerator

    manifest = ManifestGenerator.generate_and_save(
        skill_class=NewsSkill,
        output_path=Path("news_skill_manifest.json"),
        skill_id="com.example.news",
        version="1.0.0",
        name="News Skill",
        description="Fetches news headlines and articles from various sources",
        author="Example Developer",
        required_permissions=["network_access"],
        max_latency=5000,
        dependencies=["requests>=2.28.0"],
        metadata={
            "allowed_endpoints": [
                "newsapi.org",
                "api.nytimes.com",
                "api.theguardian.com",
            ],
        },
    )
