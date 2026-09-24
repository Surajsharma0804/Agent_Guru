"""Agent_Guru/platform/browser_manager.py.

Production-grade persistent browser manager for Agent Guru.

Architecture (how current leaders do it):
──────────────────────────────────────────
1. Launch ONE Chrome instance at startup with --remote-debugging-port=9222
2. Every command reconnects via CDP (connectOverCDP) - no new browser spawned
3. YouTube Data API v3 → get exact video ID → open watch?v=ID&autoplay=1
4. Fallback: Playwright search scrape if no API key
5. All playback controls (pause/resume/mute/volume) via JS evaluate on the
   persistent page - no media keys, no system-level hacks

Why this beats the old approach:
- No zombie Chrome processes
- Session/cookies persist (YouTube remembers login, preferences)
- Controls work on the ACTUAL open tab, not a new one
- CDP reconnect is <50ms - imperceptible to user
- YouTube API gives exact video ID - no fragile CSS selectors

Environment variables:
  YOUTUBE_API_KEY  - YouTube Data API v3 key (optional but recommended)
  AGENT_GURU_DEMO_BROWSER - "chromium" | "firefox" | "webkit" (default: chromium)

Author: Agent Guru Team
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess  # nosec B404
import time
import urllib.parse
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# CDP debug port - Chrome launched with this flag
_CDP_PORT = 9222
_CDP_STARTUP_TIMEOUT_S = 10.0
_CDP_POLL_INTERVAL_S = 0.25
_CDP_URL = f"http://localhost:{_CDP_PORT}"

# User data dir so Chrome keeps cookies/session between restarts
_USER_DATA_DIR = Path.home() / ".cache" / "agent_guru" / "chrome_profile"

# ─────────────────────────────────────────────────────────────────────────────
# Generic "any website" navigation (added 2026-09-13)
# ─────────────────────────────────────────────────────────────────────────────
# play_youtube() below is dedicated, API-first, YouTube-specific code. The
# methods in this section generalize the SAME underlying persistent-browser
# infrastructure (CDP reconnect, tab reuse, real Chrome/Edge/Brave/whatever
# is installed) to arbitrary sites: open_url()/open_website() navigate
# anywhere directly, and search_and_open() drives a real search engine when
# there's no dedicated API for the task at hand - the point being that
# Agent Guru doesn't need a per-site API key to act on a website; it can
# fall back to genuinely using the browser, the way a person would.
#
# This does NOT attempt full in-page task automation (filling out an
# arbitrary form, clicking through a checkout flow on an arbitrary site) -
# that is a much larger, open-ended capability and claiming it "works on
# every website" would not be honest. What IS covered, and works on
# effectively any site without per-site code: opening it, and searching it.
#
# CANONICAL REGISTRY (consolidated 2026-09-13): this used to be one of
# THREE separate, drifting site-name-to-URL tables - this one (~20
# entries), integration/orchestrator.py's IntegrationOrchestrator._URL_MAP
# (60+ entries), and platform/os_controller.py's OSController._resolve_url
# _shortcuts (15 entries) - a direct instance of the duplicate-
# implementation debt this project explicitly forbids. All three have been
# merged into this single table; orchestrator.py and os_controller.py now
# both import and delegate to _resolve_site_url() below instead of keeping
# their own copies. Where the old tables disagreed, the more useful entry
# won: "amazon" resolves to amazon.in (this product's primary market, a
# deliberate prior decision - not a default that should silently flip back
# to .com), "spotify" to open.spotify.com (the actual app, not the
# marketing homepage), and github/twitter/x to their canonical no-www
# domains.
_SITE_REGISTRY: dict[str, str] = {
    # Search / AI
    "google": "https://www.google.com",
    "bing": "https://www.bing.com",
    "wikipedia": "https://www.wikipedia.org",
    "quora": "https://www.quora.com",
    "chatgpt": "https://chatgpt.com",
    "gemini": "https://gemini.google.com",
    # Video / Music
    "youtube": "https://www.youtube.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://www.netflix.com",
    "hotstar": "https://www.hotstar.com",
    "primevideo": "https://www.primevideo.com",
    "jiocinema": "https://www.jiocinema.com",
    "zee5": "https://www.zee5.com",
    "sonyliv": "https://www.sonyliv.com",
    "twitch": "https://www.twitch.tv",
    "tiktok": "https://www.tiktok.com",
    # Social
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "reddit": "https://www.reddit.com",
    "pinterest": "https://www.pinterest.com",
    "tumblr": "https://www.tumblr.com",
    "medium": "https://www.medium.com",
    "hashnode": "https://hashnode.com",
    # Messaging
    "whatsapp": "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "discord": "https://discord.com",
    "slack": "https://slack.com",
    "zoom": "https://zoom.us",
    "teams": "https://teams.microsoft.com",
    "meet": "https://meet.google.com",
    # Dev / Coding
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "leetcode": "https://www.leetcode.com",
    "hackerrank": "https://www.hackerrank.com",
    "codechef": "https://www.codechef.com",
    "codeforces": "https://www.codeforces.com",
    "geeksforgeeks": "https://www.geeksforgeeks.org",
    "w3schools": "https://www.w3schools.com",
    "mdn": "https://developer.mozilla.org",
    "openai": "https://www.openai.com",
    "huggingface": "https://huggingface.co",
    "kaggle": "https://www.kaggle.com",
    "dev.to": "https://dev.to",
    # Learning
    "udemy": "https://www.udemy.com",
    "coursera": "https://www.coursera.org",
    "edx": "https://www.edx.org",
    "khanacademy": "https://www.khanacademy.org",
    "khan academy": "https://www.khanacademy.org",
    # Shopping / Finance
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "myntra": "https://www.myntra.com",
    "snapdeal": "https://www.snapdeal.com",
    "paytm": "https://www.paytm.com",
    "phonepe": "https://www.phonepe.com",
    "gpay": "https://pay.google.com",
    # Travel
    "irctc": "https://www.irctc.co.in",
    "makemytrip": "https://www.makemytrip.com",
    "goibibo": "https://www.goibibo.com",
    "booking": "https://www.booking.com",
    "airbnb": "https://www.airbnb.com",
    # Jobs
    "naukri": "https://www.naukri.com",
    "indeed": "https://www.indeed.com",
    "glassdoor": "https://www.glassdoor.com",
    # Google services
    "gmail": "https://mail.google.com",
    "google maps": "https://maps.google.com",
    "maps": "https://maps.google.com",
    "translate": "https://translate.google.com",
    "drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "slides": "https://slides.google.com",
    "calendar": "https://calendar.google.com",
    "keep": "https://keep.google.com",
}

_URL_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)


def _resolve_site_url(name_or_url: str) -> str:
    """Resolve a spoken site reference to a concrete URL, or "" if unknown.

    A small registry of common site names is recognized directly (no
    network round trip). Anything that already looks like a URL is
    returned as-is (a bare "www." prefix gets "https://" added). Anything
    else returns "" so the caller knows to treat it as a search query
    instead of guessing at a URL that doesn't exist.
    """
    value = (name_or_url or "").strip()
    if not value:
        return ""
    key = value.lower()
    if key in _SITE_REGISTRY:
        return _SITE_REGISTRY[key]
    if _URL_RE.match(value):
        return value if value.lower().startswith("http") else f"https://{value}"
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# YouTube API helper
# ─────────────────────────────────────────────────────────────────────────────


async def _yt_api_search(query: str) -> str | None:
    """Return the first YouTube video URL for *query* using the Data API v3.

    Requires YOUTUBE_API_KEY env var. Returns None if unavailable.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import aiohttp

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 1,
            "key": api_key,
        }
        url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                items = data.get("items", [])
                if items:
                    vid_id = items[0]["id"]["videoId"]
                    logger.info("YouTube API: found video %s for %r", vid_id, query)
                    return f"https://www.youtube.com/watch?v={vid_id}&autoplay=1"
    except Exception:
        logger.exception("YouTube API search failed")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# BrowserManager
# ─────────────────────────────────────────────────────────────────────────────


class BrowserManager:
    """Persistent browser manager - one Chrome instance, reconnect via CDP.

    Usage::

        mgr = BrowserManager()
        await mgr.start()                          # launch Chrome once

        await mgr.play_youtube("chak de india")    # open & play
        await mgr.pause()                          # pause
        await mgr.resume()                         # resume
        await mgr.mute()                           # mute
        await mgr.unmute()                         # unmute
        await mgr.volume_up()                      # +20%
        await mgr.volume_down()                    # -20%
        await mgr.set_volume(80)                   # set to 80%

        await mgr.stop()                           # close Chrome
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None  # type: ignore[type-arg]
        self._playwright: Any = None
        self._browser: Any = None  # CDP-connected browser
        self._page: Any = None  # current YouTube page
        self._lock = asyncio.Lock()
        self._started = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch Chrome with remote debugging. Safe to call multiple times."""
        async with self._lock:
            if self._started:
                return
            await self._launch_chrome()
            self._started = True
            logger.info("BrowserManager started - CDP on port %d", _CDP_PORT)

    async def stop(self) -> None:
        """Close the browser and kill the Chrome process."""
        async with self._lock:
            await self._close_playwright()
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=3)
                except Exception:
                    self._proc.kill()
            self._proc = None
            self._started = False
            logger.info("BrowserManager stopped")

    # ── YouTube control ───────────────────────────────────────────────────────

    async def play_youtube(self, query: str) -> str:
        """Search YouTube for *query* and start playing the first result.

        Flow:
          1. Try YouTube Data API v3 → exact video URL (no scraping)
          2. Fallback: Playwright search → click first result
          3. Skip any ad
          4. Start playback
        """
        await self._ensure_started()

        # Step 1: get video URL
        video_url = await _yt_api_search(query)

        if video_url:
            # Direct watch URL - fastest, most reliable
            page = await self._get_or_create_page()
            logger.info("YouTube: navigating to %s", video_url)
            await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        else:
            # Fallback: search and click first result
            page = await self._search_and_click(query)

        # Wait for player to initialise
        await page.wait_for_timeout(2500)

        # Skip ad if present
        await self._skip_ad(page)

        # Start playback
        await self._js(page, "async v => { v.muted = false; v.volume = 0.8; await v.play(); }")
        self._page = page
        logger.info("YouTube: playing %r", query)
        return f"Playing {query} on YouTube"

    async def pause(self) -> str:
        page = await self._active_page()
        await self._js(page, "v => v.pause()")
        logger.info("YouTube: paused")
        return "Video paused"

    async def resume(self) -> str:
        page = await self._active_page()
        await self._js(page, "async v => { await v.play(); }")
        logger.info("YouTube: resumed")
        return "Video playing"

    async def mute(self) -> str:
        page = await self._active_page()
        await self._js(page, "v => { v.muted = true; }")
        logger.info("YouTube: muted")
        return "Video muted"

    async def unmute(self) -> str:
        page = await self._active_page()
        await self._js(page, "v => { v.muted = false; }")
        logger.info("YouTube: unmuted")
        return "Video unmuted"

    async def volume_up(self, amount: float = 0.2) -> str:
        page = await self._active_page()
        await self._js(page, f"v => {{ v.volume = Math.min(1.0, v.volume + {amount}); }}")
        logger.info("YouTube: volume up +%.0f%%", amount * 100)
        return "Volume increased"

    async def volume_down(self, amount: float = 0.2) -> str:
        page = await self._active_page()
        await self._js(page, f"v => {{ v.volume = Math.max(0.0, v.volume - {amount}); }}")
        logger.info("YouTube: volume down -%.0f%%", amount * 100)
        return "Volume decreased"

    async def set_volume(self, percent: int) -> str:
        page = await self._active_page()
        vol = max(0, min(100, percent)) / 100.0
        await self._js(page, f"v => {{ v.volume = {vol:.2f}; }}")
        logger.info("YouTube: volume set to %d%%", percent)
        return f"Volume set to {percent}%"

    async def skip_forward(self, seconds: int = 10) -> str:
        page = await self._active_page()
        await self._js(
            page,
            f"v => {{ v.currentTime = Math.min(v.duration || v.currentTime + {seconds},"
            f" v.currentTime + {seconds}); }}",
        )
        return f"Skipped forward {seconds} seconds"

    # ── Generic navigation (any website - no API key required) ───────────────

    async def open_url(self, url: str) -> str:
        """Navigate the persistent browser directly to *url* - any website.

        Reuses an existing tab already open on the same domain (same
        strategy play_youtube() uses for YouTube, generalized here to any
        site) instead of always opening a new tab.
        """
        await self._ensure_started()
        if not url.lower().startswith(("http://", "https://")):
            url = f"https://{url}"
        page = await self._get_or_create_page_for(url)
        logger.info("BrowserManager: navigating to %s", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self._page = page
        return f"Opened {url}"

    async def open_website(self, name_or_url: str) -> str:
        """Open a website by common name ("spotify", "gmail") or raw URL.

        Falls back to search_and_open() when *name_or_url* is neither a
        recognized site name nor something that looks like a URL, so a
        vague reference ("open that recipe site") still does something
        useful instead of failing outright.
        """
        resolved = _resolve_site_url(name_or_url)
        if resolved:
            return await self.open_url(resolved)
        logger.info(
            "open_website: %r isn't a known site or URL - searching instead",
            name_or_url,
        )
        return await self.search_and_open(name_or_url)

    async def search_and_open(self, query: str, engine: str = "google") -> str:
        """Search *query* on a real search engine via the persistent browser.

        This is the no-API-needed fallback: whenever a task needs
        information (or a site) there's no dedicated API/tool for, driving
        the actual installed browser to search works for effectively any
        site, the way a person would do it themselves - instead of the
        agent being limited to only the handful of capabilities that
        happen to have a dedicated API integration.

        Deliberately does NOT auto-click a specific result (unlike
        play_youtube()'s YouTube-specific first-result click): for a
        generic query, which result is "right" depends entirely on user
        intent, so this surfaces the real results page rather than
        guessing. get_page_text() can then read back what's actually on
        the page (see platform/features/web_search.py's browser-fallback
        tier for that use).
        """
        await self._ensure_started()
        engines = {
            "google": "https://www.google.com/search?q=",
            "bing": "https://www.bing.com/search?q=",
        }
        base = engines.get(engine.lower(), engines["google"])
        search_url = base + urllib.parse.quote_plus(query)
        page = await self._get_or_create_page_for(search_url)
        logger.info("BrowserManager: searching %r via %s", query, engine)
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        self._page = page
        return f"Searched for {query!r} on {engine.title()}"

    async def get_page_text(self, max_chars: int = 3000) -> str:
        """Return the visible text of the currently active tab (best-effort).

        Used by platform/features/web_search.py's browser-driven fallback
        tier to pull a real answer out of a real search when the
        API-based search methods are unavailable or return nothing.
        """
        page = await self._active_page_any()
        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        return " ".join((text or "").split())[:max_chars]

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _ensure_started(self) -> None:
        if not self._started:
            await self.start()

    async def _launch_chrome(self) -> None:
        """Launch Chrome with --remote-debugging-port if not already running."""
        # Check if Chrome is already listening on the CDP port
        if await self._cdp_alive():
            logger.info("Chrome already running on port %d - reusing", _CDP_PORT)
            await self._connect_cdp()
            return

        # Find Chrome executable.
        # _find_chrome() stats up to ~20 candidate paths and may fall back to
        # a PATH search - blocking filesystem work, so it runs in a thread
        # rather than stalling the event loop while every other coroutine
        # (speech, reasoning, timers) waits on it.
        chrome = await asyncio.to_thread(self._find_chrome)
        if not chrome:
            logger.warning("Chrome not found - falling back to Playwright Chromium")
            await self._launch_playwright_chromium()
            return

        await asyncio.to_thread(_USER_DATA_DIR.mkdir, parents=True, exist_ok=True)
        cmd = [
            chrome,
            f"--remote-debugging-port={_CDP_PORT}",
            f"--user-data-dir={_USER_DATA_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
        ]
        logger.info("Launching Chrome: %s", chrome)
        # subprocess.Popen forks and execs synchronously; on a process with a
        # large address space that stalls the event loop for tens of
        # milliseconds. Off-loaded to a thread. It stays a Popen (not
        # asyncio.create_subprocess_exec) because the rest of this class
        # drives it as one - see stop(), which calls self._proc.wait(timeout=3).
        self._proc = await asyncio.to_thread(
            subprocess.Popen,  # nosec B603  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for CDP to become available (up to ~10s).
        #
        # The loop used to sleep BEFORE its first check, so a Chrome that was
        # ready in 50 ms still cost the caller a full 500 ms. Checking first
        # and sleeping only between attempts removes that fixed penalty from
        # every browser launch.
        deadline = time.monotonic() + _CDP_STARTUP_TIMEOUT_S
        while True:
            if await self._cdp_alive():
                break
            if time.monotonic() >= deadline:
                msg = (
                    f"Chrome did not start CDP on port {_CDP_PORT} within "
                    f"{_CDP_STARTUP_TIMEOUT_S}s"
                )
                raise RuntimeError(msg)
            await asyncio.sleep(_CDP_POLL_INTERVAL_S)

        await self._connect_cdp()

    async def _launch_playwright_chromium(self) -> None:
        """Fallback: launch real Chrome/Edge via Playwright channel, or bundled Chromium."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        # Try real Chrome first, then Edge, then bundled Chromium
        for channel in ("chrome", "msedge"):
            try:
                self._browser = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(_USER_DATA_DIR),
                    headless=False,
                    channel=channel,
                    args=["--disable-background-timer-throttling"],
                )
                logger.info("Playwright launched real %s with persistent context", channel)
                return
            except Exception as _e:
                logger.exception("Channel '%s' unavailable: %s", channel, _e)
        # Final fallback: bundled Chromium
        self._browser = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(_USER_DATA_DIR),
            headless=False,
            args=[
                f"--remote-debugging-port={_CDP_PORT}",
                "--no-first-run",
                "--disable-background-timer-throttling",
            ],
        )
        logger.info("Playwright bundled Chromium launched (install Chrome for best experience)")

    async def _connect_cdp(self) -> None:
        """Connect Playwright to the running Chrome via CDP."""
        from playwright.async_api import async_playwright

        if self._playwright is None:
            self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(_CDP_URL)
        logger.info("Connected to Chrome via CDP at %s", _CDP_URL)

    async def _close_playwright(self) -> None:
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            logger.exception("Operation failed")
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            logger.exception("Operation failed")
        self._browser = None
        self._playwright = None
        self._page = None

    async def _cdp_alive(self) -> bool:
        """Return True if Chrome is already listening on the CDP port."""
        try:
            import aiohttp

            async with (
                aiohttp.ClientSession() as s,
                s.get(
                    f"{_CDP_URL}/json/version",
                    timeout=aiohttp.ClientTimeout(total=1),
                ) as r,
            ):
                return r.status == 200

        except Exception:
            logger.exception("Operation failed")
        # Fallback: try httpx
        try:
            import httpx

            async with httpx.AsyncClient() as c:
                r = await c.get(f"{_CDP_URL}/json/version", timeout=1.0)
                return r.status_code == 200

        except Exception:
            return False

    async def _get_or_create_page(self) -> Any:
        """Get the current YouTube tab or open a new one.

        Thin YouTube-specific wrapper over _get_or_create_page_for() - see
        that method for the generalized (any-site) tab-reuse logic this
        delegates to, so the two don't drift into duplicate implementations
        of the same tab-matching logic.
        """
        return await self._get_or_create_page_for("https://www.youtube.com")

    def _all_pages(self) -> list[Any]:
        """Return every open page/tab across self._browser, whatever shape it is.

        BUG FIX (found by real testing, 2026-09-13): self._browser is a real
        Playwright ``Browser`` (has ``.contexts`` -> list of ``BrowserContext``,
        each with ``.pages``) when connected via CDP - the path taken whenever
        a real Chrome/Edge/etc. binary is found (_find_chrome()) or Chrome is
        already running. But _launch_playwright_chromium()'s fallback (no
        matching browser binary found on the system at all) sets
        self._browser to the return of ``launch_persistent_context()``,
        which is a ``BrowserContext`` directly - it has ``.pages`` but NO
        ``.contexts`` and NO ``.new_context()``. Every page-lookup method
        here used to assume the Browser shape unconditionally, so on that
        fallback path the very first play_youtube()/open_url()/etc. call
        after start() crashed with AttributeError. This normalizes both
        shapes so the fallback path actually works instead of only
        appearing to (it launches successfully; it just couldn't do
        anything afterward).
        """
        if self._browser is None:
            return []
        if hasattr(self._browser, "contexts"):  # real Browser (CDP-connected)
            pages: list[Any] = []
            for ctx in self._browser.contexts:
                pages.extend(ctx.pages)
            return pages
        return list(self._browser.pages)  # BrowserContext (persistent-context fallback)

    async def _new_page(self) -> Any:
        """Open a new page/tab, handling both self._browser shapes (see _all_pages())."""
        if hasattr(self._browser, "contexts"):  # real Browser
            try:
                ctx = self._browser.contexts[0]
            except IndexError:
                ctx = await self._browser.new_context(viewport={"width": 1440, "height": 900})
            return await ctx.new_page()
        # BrowserContext - it IS the context already; open a page directly in it.
        return await self._browser.new_page()

    async def _get_or_create_page_for(self, url: str) -> Any:
        """Get a tab already open on *url*'s domain, or open a new one.

        Domain match is exact (www.-insensitive), not substring - a
        substring check like ``"youtube.com" in page.url`` would also
        (incorrectly) match a page at ``notyoutube.com``. Generalizes the
        tab-reuse strategy play_youtube() already relied on to any site.
        """
        if self._browser is None:
            await self._connect_cdp()

        try:
            target_domain = urllib.parse.urlparse(url).netloc.removeprefix("www.").lower()
        except Exception:
            target_domain = ""

        if target_domain:
            try:
                for pg in self._all_pages():
                    page_domain = urllib.parse.urlparse(pg.url).netloc.removeprefix("www.").lower()
                    if page_domain == target_domain:
                        return pg
            except Exception:
                logger.exception("Operation failed")

        # No matching tab - open a new one.
        return await self._new_page()

    async def _search_and_click(self, query: str) -> Any:
        """Playwright fallback: search YouTube and click first result."""
        from playwright.async_api import TimeoutError as _PWTimeout

        search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(
            query,
        )
        page = await self._get_or_create_page()
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

        # Dismiss consent dialogs
        for sel in (
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "button:has-text('Reject all')",
        ):
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    break
            except Exception:
                logger.exception("Operation failed")
        # Click first video
        first = page.locator("ytd-video-renderer a#video-title").first
        await first.wait_for(state="visible", timeout=45000)
        await first.click(timeout=20000)
        logger.info("YouTube: clicked first result for %r", query)

        try:
            await page.wait_for_url("**/watch**", timeout=30000)
        except _PWTimeout:
            logger.exception("YouTube: watch URL timeout - continuing")
        return page

    async def _skip_ad(self, page: Any) -> None:
        """Poll for skippable ads and click skip when available (up to 60s).

        Handles:
        - Single skippable ads (5s countdown then skip button appears)
        - Multiple consecutive ads
        - Non-skippable bumper ads (wait them out, max 6s each)
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 60  # extended to 60s for multiple ads
        ads_skipped = 0

        while loop.time() < deadline:
            try:
                # Check if ad is showing
                ad_info = await page.evaluate(
                    "() => {"
                    "  const p = document.querySelector('#movie_player');"
                    "  if (!p) return {ad: false, skippable: false};"
                    "  const ad = p.classList.contains('ad-showing');"
                    "  const skipBtn = document.querySelector('.ytp-skip-ad-button, .ytp-ad-skip-button, [class*=\"skip-ad\"]');"
                    "  const skippable = skipBtn ? skipBtn.offsetParent !== null : false;"
                    "  return {ad, skippable};"
                    "}",
                )
            except Exception:
                return
            if not ad_info.get("ad", False):
                if ads_skipped > 0:
                    logger.info("YouTube: all ads handled (%d skipped)", ads_skipped)
                return  # No ad - done

            # Try to click skip button
            skipped = False
            for sel in (
                ".ytp-skip-ad-button",
                ".ytp-ad-skip-button",
                "button.ytp-skip-ad-button",
                "button.ytp-ad-skip-button",
                "[class*='skip-ad']",
                "[class*='skip_ad']",
            ):
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=500):
                        await btn.click()
                        logger.info("YouTube: ad skipped (%s)", sel)
                        await page.wait_for_timeout(1000)
                        ads_skipped += 1
                        skipped = True
                        break
                except Exception:
                    logger.exception("Operation failed")
            if not skipped:
                # Ad showing but not yet skippable - wait 1s and retry
                await page.wait_for_timeout(1000)

    async def _active_page(self) -> Any:
        """Return the current YouTube page, reconnecting via CDP if needed."""
        if self._page is not None:
            try:
                # Quick liveness check
                await self._page.evaluate("() => document.title")
                return self._page
            except Exception:
                logger.exception("YouTube page lost - reconnecting")
                self._page = None
        # Try to find an open YouTube tab (via _all_pages() - handles both
        # the Browser and BrowserContext shapes self._browser can be; see
        # _all_pages()'s docstring for why that distinction matters)
        if self._browser:
            try:
                for pg in self._all_pages():
                    if "youtube.com/watch" in pg.url:
                        self._page = pg
                        return pg
            except Exception:
                logger.exception("Operation failed")
        # Reconnect via CDP and look again
        await self._connect_cdp()
        for pg in self._all_pages():
            if "youtube.com" in pg.url:
                self._page = pg
                return pg

        msg = "No YouTube page open. Say 'play <song> on YouTube' first."
        raise RuntimeError(msg)

    async def _active_page_any(self) -> Any:
        """Return the current tab (any site), reconnecting via CDP if needed.

        Generic sibling of _active_page(): that method specifically
        requires a YouTube tab (for playback controls); this one returns
        whatever tab is actually open, for the generic open_url()/
        search_and_open()/get_page_text() methods that don't care which
        site the active tab is on.
        """
        if self._page is not None:
            try:
                await self._page.evaluate("() => document.title")
                return self._page
            except Exception:
                logger.exception("Active page lost - reconnecting")
                self._page = None

        if self._browser:
            try:
                pages = self._all_pages()
                if pages:
                    return pages[-1]
            except Exception:
                logger.exception("Operation failed")

        await self._connect_cdp()
        pages = self._all_pages()
        if pages:
            return pages[-1]

        msg = "No browser page open. Call open_url()/open_website()/search_and_open() first."
        raise RuntimeError(msg)

    @staticmethod
    async def _js(page: Any, fn_body: str) -> Any:
        """Evaluate *fn_body* as a function on the first <video> element."""
        return await page.evaluate(
            f"async () => {{ const v = document.querySelector('video'); "
            f"if (v) {{ const fn = {fn_body}; await fn(v); }} }}",
        )

    @staticmethod
    def _find_chrome() -> str | None:
        """Find any Chromium-based browser executable on the system.

        Priority: Chrome → Edge → Brave → Opera → Vivaldi → Chromium
        Falls back to PATH search for any of these.
        """
        candidates = [
            # Windows - Chrome
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            # Windows - Edge
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            # Windows - Brave
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            # Windows - Opera
            r"C:\Users\{user}\AppData\Local\Programs\Opera\opera.exe",
            r"C:\Program Files\Opera\opera.exe",
            # Windows - Vivaldi
            r"C:\Users\{user}\AppData\Local\Vivaldi\Application\vivaldi.exe",
            # macOS - Chrome
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Opera.app/Contents/MacOS/Opera",
            "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
            # Linux
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/microsoft-edge",
            "/usr/bin/brave-browser",
            "/usr/bin/opera",
            "/snap/bin/chromium",
        ]


        username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        for c in candidates:
            c = c.replace("{user}", username)
            if Path(c).exists():
                return c

        # Try PATH for any Chromium-based browser
        import shutil

        for name in (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "msedge",
            "microsoft-edge",
            "brave",
            "brave-browser",
            "opera",
            "vivaldi",
        ):
            found = shutil.which(name)
            if found:
                return found

        return None
