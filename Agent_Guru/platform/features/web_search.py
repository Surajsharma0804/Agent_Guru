"""Real-time web search for Agent Guru, with the sources every result came from.

When the user asks about current events, recent news, or who currently holds
a position, the LLM's training data is stale. This module finds results on
the web and keeps, for each one, where it came from: a title, the URL, the
text the provider returned, which provider, and when it was retrieved.

search_web() used to return one string of snippets and nothing else. Its
first tier read the "body" of each duckduckgo-search result and dropped the
"title" and "href" beside it, and that package was never a declared
dependency, so the tier always ended in ImportError. The second tier, the
DuckDuckGo instant answer API, returned only AbstractText and dropped the
AbstractURL, AbstractSource and Heading the same reply carries. So no answer
could say where its facts came from.

search_sources() now asks providers that answer through an API meant for
programs, and keeps what they return:

1. Wikipedia's search API (MediaWiki action=query&list=search): titles, page
   ids and the time each page was last edited. Measured 0.7 to 0.9 s.
2. The DuckDuckGo instant answer API: one abstract with its source URL, for
   topics it knows.

Scraping a search engine's result pages was tried and not taken:
html.duckduckgo.com answered 202 with a bot check, and the ddgs package found
nothing for 2 of 3 ordinary queries and took 5.7 s for the third.

search_web() keeps its signature for the prompt's web context, built from
these results. Its last tier, a Google search in the user's real browser, is
unchanged and is never used by research (integration/research.py).
"""

from __future__ import annotations

import asyncio
import logging
import posixpath
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Keywords that suggest the user wants current/live information.
# "who is the", "who are the" and "what is the" used to be in this list. They
# are how questions are phrased, not a sign that the answer changes over
# time, so "What is the capital of France?" went to the web like "Who is the
# Prime Minister?". An office-holder question is still caught by the office
# ("prime minister", "ceo", ...) below.
_CURRENT_EVENT_KEYWORDS = re.compile(
    r"\b(current|currently|now|today|latest|recent|right now|"
    r"president|prime minister|"
    r"chancellor|king|queen|ceo|leader|winner|champion|score|"
    r"price|stock|weather|news|headline|just happened|"
    r"2024|2025|2026)\b",
    re.IGNORECASE,
)

#: Sent with every request. Wikimedia's robot policy wants a way to reach the
#: client's maker: without the project URL, aiohttp's requests got HTTP 403
#: ("Please respect our robot policy").
USER_AGENT = "AgentGuru/1.0 (https://github.com/Surajsharma0804/Agent_Guru)"
_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_DDG_INSTANT_API = "https://api.duckduckgo.com/"
#: Seconds a provider may take before its results are given up on.
PROVIDER_TIMEOUT_S = 6.0

#: Query parameters that only track where a click came from; removed when
#: URLs are compared, never ones that change what the page shows.
_TRACKING_PARAMS = re.compile(r"^(utm_[a-z]+|gclid|fbclid|mc_cid|mc_eid|msclkid|ref_src|igshid)$", re.IGNORECASE)


def needs_web_search(query: str) -> bool:
    """Return True if the query likely needs live web data to answer correctly."""
    return bool(_CURRENT_EVENT_KEYWORDS.search(query))


@dataclass(slots=True)
class SearchResult:
    """One result as its provider gave it. Fields a provider did not supply stay None."""

    title: str
    url: str
    snippet: str
    provider: str
    retrieved_at: float
    #: The provider's own id for the page (Wikipedia's page id), when it has one.
    provider_id: str | None = None
    #: When the provider says the page last changed (Wikipedia: last edit).
    updated: str | None = None
    #: What is known of the page: only the provider's snippet so far.
    status: str = "snippet"


@dataclass(slots=True)
class SearchOutcome:
    """A search's results and how it went.

    status is "complete" (every provider answered), "partial" (some
    failed), "empty" (all answered, nothing found) or "failed" (none
    answered). errors names each provider that failed and why.
    """

    query: str
    results: list[SearchResult] = field(default_factory=list)
    status: str = "complete"
    errors: dict[str, str] = field(default_factory=dict)


def normalize_url(url: Any) -> str | None:
    """*url* as an http(s) URL in one canonical spelling, or None if it is not one.

    Lower-cases the scheme and host, drops the default port, the fragment
    and tracking parameters (utm_*, gclid, ...), and resolves "." and ".."
    in the path. Every other query parameter is kept in its order, since it
    may change what the page shows. A title, a javascript: link or a bare
    word is not a URL and gives None.
    """
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or any(c.isspace() for c in url) or len(url) > 2048:
        return None
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if scheme not in {"http", "https"} or not host or parts.username or parts.password:
        return None
    if not re.fullmatch(r"[a-z0-9.\-\[\]:]+", host) or ".." in host:
        return None
    netloc = f"[{host}]" if ":" in host and not host.startswith("[") else host
    if port and port != {"http": 80, "https": 443}[scheme]:
        netloc = f"{netloc}:{port}"
    path = parts.path or "/"
    trailing = path.endswith("/")
    path = posixpath.normpath(path)
    if trailing and not path.endswith("/"):
        path += "/"
    query = "&".join(
        f"{k}={v}" if v or "=" in pair else k
        for pair in parts.query.split("&")
        if pair
        for k, _, v in [pair.partition("=")]
        if not _TRACKING_PARAMS.match(urllib.parse.unquote_plus(k))
    )
    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def _clean_html(text: str) -> str:
    # Wikipedia's search snippets mark the matched words with <span> tags.
    text = re.sub(r"<[^>]+>", "", text)
    import html

    return " ".join(html.unescape(text).split())


async def _get_json(url: str, params: dict[str, Any]) -> Any:
    import aiohttp

    async with (
        aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session,
        session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=PROVIDER_TIMEOUT_S)) as resp,
    ):
        if resp.status == 429:
            msg = "rate limited (HTTP 429)"
            raise RuntimeError(msg)
        if resp.status != 200:
            msg = f"HTTP {resp.status}"
            raise RuntimeError(msg)
        return await resp.json(content_type=None)


#: Words that make a question a question but say nothing about its subject.
_QUESTION_WORDS = frozenset({
    "who", "what", "when", "where", "which", "why", "how", "is", "are", "was", "were", "the", "a", "an", "current",
    "currently", "latest", "tell", "me", "please", "do", "does", "did", "can", "you", "about", "right", "now",
    "today", "find", "out", "search", "look", "up", "know", "i", "want", "to", "my",
})


def search_terms(query: str) -> str:
    """*query* without the words that only make it a question.

    Wikipedia's search ranks by the words given, all of them: for "Who is
    the current prime minister of India?" it put the Prime Minister's
    Office and two other ministers above the Prime Minister of India
    article, which "prime minister of india" puts first.
    """
    words = re.findall(r"[\w'-]+", query)
    kept = [w for w in words if w.lower() not in _QUESTION_WORDS]
    return " ".join(kept) or query


async def _wikipedia_results(query: str, limit: int) -> list[SearchResult]:
    data = await _get_json(_WIKIPEDIA_API, {
        "action": "query", "list": "search", "srsearch": search_terms(query), "srlimit": limit,
        "format": "json", "formatversion": 2,
    })
    hits = data.get("query", {}).get("search") if isinstance(data, dict) else None
    if not isinstance(hits, list):
        msg = "unexpected reply"
        raise RuntimeError(msg)
    now = time.time()
    out = []
    for hit in hits:
        if not isinstance(hit, dict) or not isinstance(hit.get("title"), str) or not isinstance(hit.get("pageid"), int):
            continue
        title = hit["title"]
        url = normalize_url("https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")))
        if url is None:
            continue
        out.append(SearchResult(
            title=title, url=url, snippet=_clean_html(str(hit.get("snippet", ""))), provider="wikipedia",
            retrieved_at=now, provider_id=str(hit["pageid"]),
            updated=hit.get("timestamp") if isinstance(hit.get("timestamp"), str) else None,
        ))
    return out


async def _ddg_instant_results(query: str) -> list[SearchResult]:
    data = await _get_json(_DDG_INSTANT_API, {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
    if not isinstance(data, dict):
        msg = "unexpected reply"
        raise RuntimeError(msg)
    url = normalize_url(data.get("AbstractURL"))
    text = str(data.get("AbstractText") or "").strip()
    if not url or not text:
        return []
    return [SearchResult(
        title=str(data.get("Heading") or data.get("AbstractSource") or url).strip(), url=url, snippet=text,
        provider="duckduckgo_instant", retrieved_at=time.time(),
    )]


_NEWS_RSS = "https://www.bing.com/news/search"
#: Words that make a question about what is happening now, which an
#: encyclopedia cannot answer: research said "not found" to "who won
#: yesterday's match" because Wikipedia and DuckDuckGo were its only sources.
_CURRENT = re.compile(
    r"\b(news|latest|today|tonight|yesterday|this (week|month|morning|evening)|current(ly)?|recent(ly)?|now|"
    r"breaking|live|score|scores|won|wins|result|results|election|price|prices|stock|stocks|update|updates|"
    r"20[2-3]\d)\b",
    re.IGNORECASE,
)


def is_current(query: str) -> bool:
    """Whether *query* asks about something happening now, so news is searched and put first."""
    return bool(_CURRENT.search(query))


async def _get_text(url: str, params: dict[str, Any]) -> str:
    import aiohttp

    async with (
        aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session,
        session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=PROVIDER_TIMEOUT_S)) as resp,
    ):
        if resp.status != 200:
            msg = f"HTTP {resp.status}"
            raise RuntimeError(msg)
        return await resp.text()


async def _news_results(query: str, limit: int) -> list[SearchResult]:
    """Recent news articles from Bing News's RSS feed (no key), each with its publisher's own address.

    The feed's links go through bing.com/news/apiclick.aspx with the
    article's address in its url parameter; that address is kept, so
    reading the page reads the publisher, through the same guard as any page.
    """
    from email.utils import parsedate_to_datetime

    from Agent_Guru.security.xml_utils import safe_xml_parse

    root = safe_xml_parse(await _get_text(_NEWS_RSS, {"q": search_terms(query), "format": "rss"}))
    now = time.time()
    out = []
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        target = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).get("url", [link])[0]
        url = normalize_url(target)
        title = _clean_html(item.findtext("title") or "")
        if url is None or not title:
            continue
        try:
            updated = parsedate_to_datetime(item.findtext("pubDate") or "").isoformat()
        except (TypeError, ValueError):
            updated = None
        out.append(SearchResult(title=title, url=url, snippet=_clean_html(item.findtext("description") or ""),
                                provider="bing_news", retrieved_at=now, updated=updated))
    # Newest first: the feed ranks by relevance, and for "who won yesterday"
    # it put an article from June among October's.
    out.sort(key=lambda r: r.updated or "", reverse=True)
    return out[:limit]


async def search_sources(query: str, limit: int = 5) -> SearchOutcome:
    """Search every provider at once and return their results with sources, duplicates merged.

    Never raises: a provider that fails is named in errors, and the outcome
    says whether the results are complete, partial, empty or failed.
    """
    outcome = SearchOutcome(query=query)
    if not query.strip():
        outcome.status = "empty"
        return outcome
    providers: dict[str, Any] = {}
    if is_current(query):
        # First, so the articles lead the results for a question about now.
        providers["bing_news"] = _news_results(query, limit)
    providers["wikipedia"] = _wikipedia_results(query, limit)
    providers["duckduckgo_instant"] = _ddg_instant_results(query)
    answers = await asyncio.gather(
        *(asyncio.wait_for(p, PROVIDER_TIMEOUT_S + 1) for p in providers.values()), return_exceptions=True,
    )
    seen: set[str] = set()
    for name, answer in zip(providers, answers, strict=True):
        if isinstance(answer, BaseException):
            if isinstance(answer, asyncio.CancelledError):
                raise answer
            outcome.errors[name] = "timed out" if isinstance(answer, TimeoutError) else (str(answer)[:200] or type(answer).__name__)
            continue
        for result in answer:
            if result.url not in seen:
                seen.add(result.url)
                outcome.results.append(result)
    if len(outcome.errors) == len(providers):
        outcome.status = "failed"
    elif outcome.errors:
        outcome.status = "partial"
    elif not outcome.results:
        outcome.status = "empty"
    outcome.results = outcome.results[:limit]
    return outcome


async def search_web(
    query: str,
    max_chars: int = 500,
    *,
    allow_browser_fallback: bool = True,
) -> str | None:
    """Search the web and return a short text for the prompt, each part named by its source.

    Built from search_sources(). Only if that finds nothing does it fall back
    to a Google search in the user's real browser (see the module
    docstring), which is slower and has no source per result.

    Args:
        query: The search query.
        max_chars: Maximum characters to return.
        allow_browser_fallback: Set False to skip the browser tier.

    Returns:
        A short text, or None if nothing was found.

    """
    outcome = await search_sources(query, limit=3)
    parts = [f"{r.snippet} (source: {r.title}, {r.url})" for r in outcome.results if r.snippet]
    if parts:
        return " ".join(parts)[:max_chars]
    if allow_browser_fallback:
        return await _search_browser_fallback(query, max_chars)
    return None


# Module-level singleton so this fallback reuses the SAME persistent browser
# instance (and its CDP connection, cookies, open tabs) that YouTube playback
# and any other browser-driven feature use - never spins up a second Chrome.
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

    No API key, no dedicated integration for the query's topic - this is
    the "just use the browser like a person would" fallback described in
    the module docstring. Only reached when the API-based providers above
    have already returned nothing.

    Failure here (no GUI browser available, Playwright not installed,
    launch timeout, etc.) is expected and handled the same way the other
    tiers handle failure: log at debug level and return None, letting
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
    # "Settings", "Tools", footer links) - crudely trim the obvious leading
    # boilerplate so what we return is closer to actual result content
    # rather than the search box and top nav. This is a heuristic, not a
    # real parser - good enough for "some real, current text about the
    # query" rather than a precise structured extraction.
    cleaned = text
    for marker in ("All\n", "About\n", "Search Results\n"):
        idx = cleaned.find(marker)
        if 0 <= idx < 200:
            cleaned = cleaned[idx + len(marker):]
            break

    cleaned = cleaned.strip()
    return cleaned[:max_chars] if cleaned else None
