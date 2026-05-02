"""Real-time web search for Agent Guru.

When the user asks about current events, recent news, or who currently holds
a position, the LLM's training data is stale. This module fetches a live
web snippet and injects it into the LLM prompt so the answer is accurate.

We use DuckDuckGo's instant answer API — no API key needed, no rate limits
for reasonable usage, and it respects privacy (no tracking).

Usage:
    result = await search_web("who is the current president of America")
    # Returns a short snippet like "Donald Trump is the 47th president..."
"""
from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)

# Keywords that suggest the user wants current/live information
_CURRENT_EVENT_KEYWORDS = re.compile(
    r"\b(current|currently|now|today|latest|recent|right now|"
    r"who is the|who are the|what is the|president|prime minister|"
    r"chancellor|king|queen|ceo|leader|winner|champion|score|"
    r"price|stock|weather|news|headline|just happened|"
    r"2024|2025|2026)\b",
    re.I,
)


def needs_web_search(query: str) -> bool:
    """Return True if the query likely needs live web data to answer correctly."""
    return bool(_CURRENT_EVENT_KEYWORDS.search(query))


async def search_web(query: str, max_chars: int = 400) -> Optional[str]:
    """Search DuckDuckGo and return a short answer snippet.

    Uses DuckDuckGo's instant answer API (no key needed). Falls back to
    a regular search snippet if no instant answer is available.

    Args:
        query: The search query.
        max_chars: Maximum characters to return (keeps LLM prompt short).

    Returns:
        A short text snippet, or None if search failed.
    """
    try:
        import aiohttp
    except ImportError:
        logger.debug("aiohttp not available — web search disabled")
        return None

    # Try DuckDuckGo instant answer API first
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=4),
                headers={"User-Agent": "AgentGuru/1.0"},
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

        # Try abstract (Wikipedia-style answer)
        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            return abstract[:max_chars]

        # Try answer (direct factual answer)
        answer = (data.get("Answer") or "").strip()
        if answer:
            return answer[:max_chars]

        # Try related topics
        topics = data.get("RelatedTopics", [])
        for topic in topics[:3]:
            text = topic.get("Text", "").strip() if isinstance(topic, dict) else ""
            if text and len(text) > 30:
                return text[:max_chars]

        return None

    except asyncio.TimeoutError:
        logger.debug("Web search timed out for: %r", query)
        return None
    except Exception as exc:
        logger.debug("Web search failed: %s", exc)
        return None
