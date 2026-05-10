"""Agent_Guru/platform/browser_manager.py.

Production-grade persistent browser manager for Agent Guru.

Architecture (how current leaders do it):
──────────────────────────────────────────
1. Launch ONE Chrome instance at startup with --remote-debugging-port=9222
2. Every command reconnects via CDP (connectOverCDP) — no new browser spawned
3. YouTube Data API v3 → get exact video ID → open watch?v=ID&autoplay=1
4. Fallback: Playwright search scrape if no API key
5. All playback controls (pause/resume/mute/volume) via JS evaluate on the
   persistent page — no media keys, no system-level hacks

Why this beats the old approach:
- No zombie Chrome processes
- Session/cookies persist (YouTube remembers login, preferences)
- Controls work on the ACTUAL open tab, not a new one
- CDP reconnect is <50ms — imperceptible to user
- YouTube API gives exact video ID — no fragile CSS selectors

Environment variables:
  YOUTUBE_API_KEY  — YouTube Data API v3 key (optional but recommended)
  AGENT_GURU_DEMO_BROWSER — "chromium" | "firefox" | "webkit" (default: chromium)

Author: Agent Guru Team
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# CDP debug port — Chrome launched with this flag
_CDP_PORT = 9222
_CDP_URL = f"http://localhost:{_CDP_PORT}"

# User data dir so Chrome keeps cookies/session between restarts
_USER_DATA_DIR = Path.home() / ".cache" / "agent_guru" / "chrome_profile"


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
    """Persistent browser manager — one Chrome instance, reconnect via CDP.

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
            logger.info("BrowserManager started — CDP on port %d", _CDP_PORT)

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
            # Direct watch URL — fastest, most reliable
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

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _ensure_started(self) -> None:
        if not self._started:
            await self.start()

    async def _launch_chrome(self) -> None:
        """Launch Chrome with --remote-debugging-port if not already running."""
        # Check if Chrome is already listening on the CDP port
        if await self._cdp_alive():
            logger.info("Chrome already running on port %d — reusing", _CDP_PORT)
            await self._connect_cdp()
            return

        # Find Chrome executable
        chrome = self._find_chrome()
        if not chrome:
            logger.warning("Chrome not found — falling back to Playwright Chromium")
            await self._launch_playwright_chromium()
            return

        _USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
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
        self._proc = subprocess.Popen(  # nosec B603  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for CDP to become available (up to 10s)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if await self._cdp_alive():
                break
        else:
            msg = "Chrome did not start CDP in time"
            raise RuntimeError(msg)

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
                return r.status == 200  # noqa: PLR2004 - Percentage/large threshold

        except Exception:
            logger.exception("Operation failed")
        # Fallback: try httpx
        try:
            import httpx

            async with httpx.AsyncClient() as c:
                r = await c.get(f"{_CDP_URL}/json/version", timeout=1.0)
                return r.status_code == 200  # noqa: PLR2004 - Percentage/large threshold

        except Exception:
            return False
    async def _get_or_create_page(self) -> Any:
        """Get the current page or open a new tab."""
        if self._browser is None:
            await self._connect_cdp()

        # Try to reuse existing YouTube tab
        try:
            contexts = self._browser.contexts
            for ctx in contexts:
                for pg in ctx.pages:
                    if "youtube.com" in pg.url:
                        return pg
        except Exception:
            logger.exception("Operation failed")
        # Open new tab
        try:
            ctx = self._browser.contexts[0]
        except (IndexError, Exception):
            ctx = await self._browser.new_context(viewport={"width": 1440, "height": 900})
        return await ctx.new_page()

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
            logger.exception("YouTube: watch URL timeout — continuing")
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
                return  # No ad — done

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
                # Ad showing but not yet skippable — wait 1s and retry
                await page.wait_for_timeout(1000)

    async def _active_page(self) -> Any:
        """Return the current YouTube page, reconnecting via CDP if needed."""
        if self._page is not None:
            try:
                # Quick liveness check
                await self._page.evaluate("() => document.title")
                return self._page
            except Exception:
                logger.exception("YouTube page lost — reconnecting")
                self._page = None
        # Try to find an open YouTube tab
        if self._browser:
            try:
                for ctx in self._browser.contexts:
                    for pg in ctx.pages:
                        if "youtube.com/watch" in pg.url:
                            self._page = pg
                            return pg
            except Exception:
                logger.exception("Operation failed")
        # Reconnect via CDP and look again
        await self._connect_cdp()
        for ctx in self._browser.contexts:
            for pg in ctx.pages:
                if "youtube.com" in pg.url:
                    self._page = pg
                    return pg

        msg = "No YouTube page open. Say 'play <song> on YouTube' first."
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
            # Windows — Chrome
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            # Windows — Edge
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            # Windows — Brave
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            # Windows — Opera
            r"C:\Users\{user}\AppData\Local\Programs\Opera\opera.exe",
            r"C:\Program Files\Opera\opera.exe",
            # Windows — Vivaldi
            r"C:\Users\{user}\AppData\Local\Vivaldi\Application\vivaldi.exe",
            # macOS — Chrome
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

        import os as _os

        username = _os.environ.get("USERNAME") or _os.environ.get("USER") or ""
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
