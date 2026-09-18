"""Real-time web search for Agent Guru.

When the user asks about current events, recent news, or who currently holds
a position, the LLM's training data is stale. This module fetches live web
results and injects them into the LLM prompt so the answer is accurate.

We use three approaches in priority order:
1. duckduckgo-search (ddgs) — real search results, no API key, best quality
2. DuckDuckGo instant answer API — fallback, shallower but always works
3. Real browser search (added 2026-09-13) — when NEITHER of the above finds
   anything (ddgs not installed, or both return nothing for an obscure/very
   current query), fall back to actually driving the persistent browser
   (platform/browser_manager.py::BrowserManager — the same real Chrome/Edge/
   whatever-is-installed instance used for YouTube playback) to run a real
   Google search and read the results page. This is the "no API key, no
   dedicated integration, just use the browser like a person would" tier —
   it works for effectively any query, at the cost of being slower and
   needing a real, running browser (so it's tried last, not first).

All three are free — no API key needed for any of them. Only the third
requires a browser environment (won't work in a headless-only server
deployment with no GUI browser available; degrades to returning None in
that case, same as the other two tiers do on failure).

Install: pip install duckduckgo-search
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from typing import Any

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


async def search_web(
    query: str,
    max_chars: int = 500,
    *,
    allow_browser_fallback: bool = True,
) -> str | None:
    """Search the web and return a short answer snippet.

    Tries duckduckgo-search (ddgs) first for real results, falls back to
    the DuckDuckGo instant answer API, and — only if both of those find
    nothing — falls back to a real browser-driven Google search (see the
    module docstring's tier 3). The browser fallback is the slowest tier
    (it has to launch/reconnect to a real browser and load a real page),
    so it's only attempted after the two fast, API-based tiers both come
    up empty.

    Args:
        query: The search query.
        max_chars: Maximum characters to return.
        allow_browser_fallback: Set False to skip tier 3 (e.g. a headless
            server deployment with no GUI browser available, or a caller
            that wants a fast "give up" instead of waiting on a browser
            launch).

    Returns:
        A short text snippet, or None if all attempted tiers failed.

    """
    # Try ddgs first — real search results, much better quality
    result = await _search_ddgs(query, max_chars)
    if result:
        return result

    # Fallback: DuckDuckGo instant answer API
    result = await _search_ddg_instant(query, max_chars)
    if result:
        return result

    # Last resort: an actual browser search, no API involved at all.
    if allow_browser_fallback:
        return await _search_browser_fallback(query, max_chars)
    return None


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
    except ImportError:
        logger.debug("duckduckgo-search not installed — run: pip install duckduckgo-search")
        return None
    except TimeoutError:
        logger.debug("ddgs search timed out")
        return None
    except Exception as exc:
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
    except TimeoutError:
        logger.debug("DDG instant answer timed out")
        return None
    except Exception as exc:
        logger.debug("DDG instant answer failed: %s", exc)
        return None


# Module-level singleton so this fallback reuses the SAME persistent browser
# instance (and its CDP connection, cookies, open tabs) that YouTube playback
# and any other browser-driven feature use — never spins up a second Chrome.
_shared_browser_manager: Any = None
_shared_browser_manager_lock: asyncio.Lock | None = None


async def _get_shared_browser_manager() -> Any:
    """Return the process-wide BrowserManager singleton, starting it if needed."""
    global _shared_browser_manager, _shared_browser_manager_lock
    if _shared_browser_manager_lock is None:
        _shared_browser_manager_lock = asyncio.Lock()

    async with _shared_browser_manager_lock:
        if _shared_browser_manager is None:
            from Agent_Guru.platform.browser_manager import BrowserManager

            _shared_browser_manager = BrowserManager()
            await _shared_browser_manager.start()
        return _shared_browser_manager


async def _search_browser_fallback(query: str, max_chars: int) -> str | None:
    """Last-resort tier: search Google via a real, persistent browser.

    No API key, no dedicated integration for the query's topic — this is
    the "just use the browser like a person would" fallback described in
    the module docstring. Only reached when both API-based tiers above
    have already returned nothing.

    Failure here (no GUI browser available, Playwright not installed,
    launch timeout, etc.) is expected and handled the same way the other
    two tiers handle failure: log at debug level and return None, letting
    the caller treat "no web context available" as a normal outcome
    rather than an error.
    """
    try:
        manager = await asyncio.wait_for(_get_shared_browser_manager(), timeout=15.0)
        await asyncio.wait_for(manager.search_and_open(query, engine="google"), timeout=15.0)
        text = await asyncio.wait_for(manager.get_page_text(max_chars=max_chars * 4), timeout=5.0)
    except TimeoutError:
        logger.debug("Browser search fallback timed out for %r", query)
        return None
    except Exception as exc:
        logger.debug("Browser search fallback unavailable/failed: %s", exc)
        return None

    if not text:
        return None

    # A raw Google results page's innerText is mostly UI chrome (nav links,
    # "Settings", "Tools", footer links) — crudely trim the obvious leading
    # boilerplate so what we return is closer to actual result content
    # rather than the search box and top nav. This is a heuristic, not a
    # real parser — good enough for "some real, current text about the
    # query" rather than a precise structured extraction.
    cleaned = text
    for marker in ("All\n", "About\n", "Search Results\n"):
        idx = cleaned.find(marker)
        if 0 <= idx < 200:
            cleaned = cleaned[idx + len(marker):]
            break

    cleaned = cleaned.strip()
    return cleaned[:max_chars] if cleaned else None
