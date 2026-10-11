"""Reading a web page for research, without letting a URL reach anything it should not.

A URL that came from a search result or a model is untrusted. Reading it
naively would let it reach the owner's router admin page, a service on
localhost, or the cloud metadata address, and a public URL could redirect
there. So every hop, the first and each redirect, is checked:

- only http and https, no credentials in the URL;
- the host name is resolved, and every address it resolves to must be a
  public one (not private, loopback, link-local, multicast, reserved or
  unspecified, including IPv4 addresses hidden inside IPv6);
- the connection is then made to the address that was checked, with the
  host name kept for the Host header and for TLS (SNI and certificate
  checks), so a DNS answer that changes between the check and the
  connection (DNS rebinding) cannot redirect it;
- at most 5 redirects, none back to a URL already visited.

The response must be text (HTML, XHTML or plain text) and is read up to
MAX_BYTES; anything longer is cut and marked truncated. No script on the
page runs and nothing is downloaded or saved: the text is extracted with
the standard library's HTML parser, dropping scripts, styles, navigation,
headers, footers and forms.

Wikipedia pages are read through Wikipedia's API instead, which returns the
article's text without the page around it.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from Agent_Guru.platform.features.web_search import PROVIDER_TIMEOUT_S, USER_AGENT, normalize_url

logger = logging.getLogger(__name__)

#: Most bytes read from one page.
MAX_BYTES = 2 * 1024 * 1024
#: Most characters of extracted text kept from one page.
MAX_TEXT_CHARS = 20000
MAX_REDIRECTS = 5
#: Seconds for the whole of one page, every redirect included.
FETCH_TIMEOUT_S = 12.0
_TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_WIKIPEDIA_PAGE = re.compile(r"^https://en\.wikipedia\.org/wiki/([^?#]+)$")


@dataclass(slots=True)
class PageResult:
    """What reading one page found, and how far the reading got.

    status: "complete", "truncated" (cut at MAX_BYTES or MAX_TEXT_CHARS),
    "blocked" (the destination is not allowed), "unsupported" (not a text
    page), or "failed". final_url is where the text came from after any
    redirects; it is None unless the page was actually read.
    """

    requested_url: str
    status: str
    retrieved_at: float
    final_url: str | None = None
    title: str | None = None
    text: str = ""
    content_type: str | None = None
    error: str = ""
    provider: str = "web"


class BlockedDestination(ValueError):
    """The URL leads somewhere research may not go."""


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified or not ip.is_global
    )


async def resolve_public(host: str, port: int) -> str:
    """One public address *host* resolves to; raises BlockedDestination if any address is not public.

    Every address must be public, not just one: a name that resolves to a
    public and a private address could be connected to the private one.
    """
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=0)
        except OSError as exc:
            msg = f"{host} could not be resolved"
            raise BlockedDestination(msg) from exc
        addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        msg = f"{host} has no address"
        raise BlockedDestination(msg)
    private = [a for a in addresses if not _public(a)]
    if private:
        msg = f"{host} leads to a non-public address ({private[0]})"
        raise BlockedDestination(msg)
    return addresses[0]


class _TextExtractor(HTMLParser):
    _SKIP = frozenset({"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg",
                       "iframe", "template", "button", "select", "option"})
    _BLOCK = frozenset({"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section",
                        "article", "blockquote", "pre", "table", "ul", "ol", "dd", "dt"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title: str | None = None
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self._SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title = ((self.title or "") + data).strip() or None
        elif not self._skip:
            self.parts.append(data)


def extract_text(html: str) -> tuple[str | None, str]:
    """The page's title and readable text, without scripts, styles, navigation or forms."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        logger.debug("HTML could not be fully parsed", exc_info=True)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return parser.title, "\n".join(line for line in lines if line)


async def _wikipedia_page(url: str, title: str) -> PageResult:
    from Agent_Guru.platform.features.web_search import _get_json

    now = time.time()
    data = await _get_json("https://en.wikipedia.org/w/api.php", {
        "action": "query", "prop": "extracts|info", "titles": urllib.parse.unquote(title).replace("_", " "),
        "explaintext": 1, "inprop": "url", "redirects": 1, "format": "json", "formatversion": 2,
    })
    pages = data.get("query", {}).get("pages") if isinstance(data, dict) else None
    page = pages[0] if isinstance(pages, list) and pages else {}
    if not isinstance(page, dict) or page.get("missing") or not isinstance(page.get("extract"), str):
        return PageResult(url, "failed", now, error="no such Wikipedia page", provider="wikipedia")
    text = page["extract"].strip()
    status = "truncated" if len(text) > MAX_TEXT_CHARS else "complete"
    return PageResult(
        requested_url=url, status=status, retrieved_at=now, final_url=normalize_url(page.get("fullurl")) or url,
        title=page.get("title"), text=text[:MAX_TEXT_CHARS], content_type="text/plain", provider="wikipedia",
    )


async def fetch_page(url: str) -> PageResult:
    """Read the page at *url* as the module docstring describes; never raises except CancelledError."""
    started = time.time()
    clean = normalize_url(url)
    if clean is None:
        return PageResult(str(url)[:300], "blocked", started, error="not an http or https URL")
    wiki = _WIKIPEDIA_PAGE.match(clean)
    try:
        if wiki:
            return await asyncio.wait_for(_wikipedia_page(clean, wiki.group(1)), FETCH_TIMEOUT_S)
        return await asyncio.wait_for(_fetch(clean, started), FETCH_TIMEOUT_S)
    except TimeoutError:
        return PageResult(clean, "failed", started, error=f"no complete answer within {FETCH_TIMEOUT_S:g} s")
    except BlockedDestination as exc:
        return PageResult(clean, "blocked", started, error=str(exc))
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return PageResult(clean, "failed", started, error=f"{type(exc).__name__}: {str(exc)[:200]}")


async def _fetch(url: str, started: float) -> PageResult:
    import httpx

    visited: set[str] = set()
    current = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=PROVIDER_TIMEOUT_S, trust_env=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            if current in visited:
                return PageResult(url, "failed", started, error="redirect loop")
            visited.add(current)
            parts = urllib.parse.urlsplit(current)
            host = parts.hostname or ""
            port = parts.port or (443 if parts.scheme == "https" else 80)
            address = await resolve_public(host, port)
            # Connect to the address just checked; keep the name for Host and TLS.
            pinned_host = f"[{address}]" if ":" in address else address
            pinned = urllib.parse.urlunsplit((parts.scheme, f"{pinned_host}:{port}", parts.path, parts.query, ""))
            request = client.build_request(
                "GET", pinned, headers={"Host": parts.netloc, "User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.9"},
                extensions={"sni_hostname": host} if parts.scheme == "https" else {},
            )
            response = await client.send(request, stream=True)
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    target = normalize_url(urllib.parse.urljoin(current, response.headers.get("location", "")))
                    if target is None:
                        return PageResult(url, "blocked", started, error="redirect to a URL that is not http or https")
                    current = target
                    continue
                if response.status_code != 200:
                    return PageResult(url, "failed", started, error=f"HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in _TEXT_TYPES:
                    return PageResult(url, "unsupported", started, content_type=content_type or None,
                                      error=f"not a text page ({content_type or 'no type'})")
                body = bytearray()
                truncated = False
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        del body[MAX_BYTES:]
                        truncated = True
                        break
                charset = response.charset_encoding or "utf-8"
            finally:
                await response.aclose()
            raw = body.decode(charset, errors="replace")
            title, text = extract_text(raw) if content_type != "text/plain" else (None, raw.strip())
            if len(text) > MAX_TEXT_CHARS:
                text, truncated = text[:MAX_TEXT_CHARS], True
            return PageResult(
                requested_url=url, status="truncated" if truncated else "complete", retrieved_at=started,
                final_url=current, title=title, text=text, content_type=content_type,
            )
    return PageResult(url, "failed", started, error=f"more than {MAX_REDIRECTS} redirects")
