"""Which web addresses the owner or this turn's sources named, compared as parsed scheme, host and port.

A substring check is the usual way this goes wrong: a source that mentions "example.com" would
vouch for "example.com.evil.net", and "https://example.com@evil.net" visits evil.net.
"""

from __future__ import annotations

import pytest

from Agent_Guru.security.url_trust import untrusted

SOURCE = "[S1] Install guide <https://example.com/guide> (page read)\nPassage text."


@pytest.mark.parametrize("url", ["https://github.com/anthropics", "github.com", "https://www.github.com/"])
def test_an_address_the_owner_said_is_trusted(url):
    assert untrusted(url, "open github.com for me", []) is None  # nosec B101


@pytest.mark.parametrize("url", ["https://example.com/other/page", "https://EXAMPLE.com./guide"])
def test_an_address_a_source_returned_is_trusted(url):
    assert untrusted(url, "how do I install it", [SOURCE]) is None  # nosec B101


@pytest.mark.parametrize("url", [
    "https://example.com.evil.net/x",       # the trusted host as a prefix of another
    "https://evilexample.com/",             # as a suffix
    "https://evil.net/?next=example.com",   # in the query
    "https://evil.net/example.com",         # in the path
    "https://example.com@evil.net/",        # as user info: the request goes to evil.net
    "https://user:pw@example.com/",         # credentials in the URL, even on the trusted host
    "https://xn--exmple-cua.com/",          # a lookalike in punycode
    "https://example.com:8443/",            # another port
    "http://example.com/",                  # another scheme than the one named
    "javascript:alert(1)",
])
def test_a_lookalike_is_not_trusted(url):
    assert untrusted(url, "how do I install it", [SOURCE]) is not None  # nosec B101


def test_an_address_nobody_named_is_not_trusted():
    reason = untrusted("https://attacker.example/?q=7314", "what's my locker code", [])
    assert reason is not None and "attacker.example" in reason  # nosec B101


def test_a_longer_host_in_the_text_names_only_itself():
    # The text names a.example.com.evil.net; that is not example.com.
    assert untrusted("https://example.com/", "", ["see a.example.com.evil.net"]) is not None  # nosec B101
