"""Real-time web search for Agent Guru.

When the user asks about current events, recent news, or who currently holds
a position, the LLM's training data is stale. This module fetches live web
results and injects them into the LLM prompt so the answer is accurate.

We use two approaches in priority order:
1. duckduckgo-search (ddgs) — real search results, no API key, best quality
2. DuckDuckGo instant answer API — fallback, shallower but always works

Both are free, no API key needed, privacy-respecting.

Install: pip install duckduckgo-search
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse

logger = logging.getLogger(__name__)

# Keywords that suggest the user wants current/live information
_CURRENT_EVENT_KEYWORDS = re.compile(
    r"\b(current|currently|now|today|latest|recent|right now|"
    r"who is the|who are the|what is the|president|prime minister|"
    r"chancellor|king|queen|ceo|leader|winner|champion|score|"
    r"price|stock|weather|news|headline|just happened|"
    r"2024|2025|2026)\b",
    re.IGNORECASE,
)


def needs_web_search(query: str) -> bool:
    """Return True if the query likely needs live web data to answer correctly."""
    return bool(_CURRENT_EVENT_KEYWORDS.search(query))


async def search_web(query: str, max_chars: int = 500) -> str | None:
    """Search the web and return a short answer snippet.

    Tries duckduckgo-search (ddgs) first for real results, falls back to
    DuckDuckGo instant answer API.

    Args:
        query: The search query.
        max_chars: Maximum characters to return.

    Returns:
        A short text snippet, or None if search failed.

    """
    # Try ddgs first — real search results, much better quality
    result = await _search_ddgs(query, max_chars)
    if result:
        return result

    # Fallback: DuckDuckGo instant answer API
    return await _search_ddg_instant(query, max_chars)


async def _search_ddgs(query: str, max_chars: int) -> str | None:
    """Search using duckduckgo-search library (real results, no API key)."""
    try:
        from duckduckgo_search import DDGS  # type: ignore[import]

        def _sync_search() -> str | None:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            if not results:
                return None
            # Combine top 3 snippets
            parts = []
            for r in results[:3]:
                body = r.get("body", "").strip()
                if body and len(body) > 20:
                    parts.append(body)
            combined = " ".join(parts)
            return combined[:max_chars] if combined else None

        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, _sync_search),
            timeout=5.0,
        )
    except ImportError as exc:
        logger.debug("duckduckgo-search not installed — run: pip install duckduckgo-search")
        return None
        logger.debug("ddgs search timed out")
        return None
        logger.debug("ddgs search failed: %s", exc)
        return None


async def _search_ddg_instant(query: str, max_chars: int) -> str | None:
    """Fallback: DuckDuckGo instant answer API (shallow but always works)."""
    try:
        import aiohttp

        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=4),
                headers={"User-Agent": "AgentGuru/1.0"},
            ) as resp,
        ):
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)

        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            return abstract[:max_chars]

        answer = (data.get("Answer") or "").strip()
        if answer:
            return answer[:max_chars]

        topics = data.get("RelatedTopics", [])
        for topic in topics[:3]:
            text = topic.get("Text", "").strip() if isinstance(topic, dict) else ""
            if text and len(text) > 30:
                return text[:max_chars]

        return None
    except TimeoutError as exc:
        logger.debug("DDG instant answer timed out")
        return None
        logger.debug("DDG instant answer failed: %s", exc)
        return None
