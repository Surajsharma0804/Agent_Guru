"""The browser tools act on numbered elements, only after the owner's yes, and never reach private addresses.

Pages come from a small HTTP server on this machine; the browser is a
real Chrome or Edge through Playwright. Skipped as unverified where
Playwright or a browser is missing.
"""

from __future__ import annotations

import http.server
import threading
import urllib.parse
from types import SimpleNamespace

import pytest

pytest.importorskip("playwright.async_api", reason="UNVERIFIED on this host: Playwright is not installed")

from Agent_Guru.integration import browser_tools  # noqa: E402
from Agent_Guru.integration.browser_tools import BrowserTools, browser_server  # noqa: E402
from Agent_Guru.integration.mcp_tools import install_mcp_policies  # noqa: E402
from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator  # noqa: E402
from Agent_Guru.llm.models import ToolCall  # noqa: E402
from Agent_Guru.policy import PolicyEngine  # noqa: E402
from Agent_Guru.policy.defaults import install_default_policies  # noqa: E402

pytestmark = pytest.mark.timeout(90)

_FORM = """<html><head><title>Train search</title></head><body>
<h1>Find a train</h1>
<form action="/result" method="get">
  <label>From <input name="from" type="text"></label>
  <label>Secret <input name="pw" type="password"></label>
  <button type="submit">Search trains</button>
</form>
<a href="/about">About us</a>
</body></html>"""


class _Pages(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - the http.server API
        parts = urllib.parse.urlsplit(self.path)
        if parts.path == "/result":
            q = urllib.parse.parse_qs(parts.query).get("from", [""])[0]
            body = f"<html><head><title>Results</title></head><body>Trains from {q}: 08:15, 09:40</body></html>"
        elif parts.path == "/about":
            body = "<html><head><title>About</title></head><body>About this site</body></html>"
        else:
            body = _FORM
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Pages)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
async def tools(monkeypatch):
    monkeypatch.setenv(browser_tools.ENABLE_ENV, "1")
    made = BrowserTools(allow_private=True)
    yield made
    await made.close()


async def _open(tools, url):
    text, is_error, _ = await tools.call("browser_open", {"url": url})
    if is_error and "no browser could be started" in text:
        pytest.skip("UNVERIFIED on this host: " + text)
    assert not is_error, text  # nosec B101
    return text


def _number(text, name):
    for line in text.splitlines():
        if f"'{name}'" in line:
            return int(line.split("]")[0].lstrip("["))
    raise AssertionError(f"{name} not in\n{text}")


async def test_a_page_is_shown_with_numbered_elements(tools, site):
    text = await _open(tools, site)
    assert "Page: Train search" in text and "Find a train" in text  # nosec B101
    assert "button 'Search trains'" in text and "field (text) 'From'" in text  # nosec B101
    assert "link 'About us' ->" in text  # nosec B101


async def test_typing_is_read_back_and_submitting_moves_on(tools, site):
    text = await _open(tools, site)
    field = _number(text, "From")
    said, is_error, verified = await tools.call("browser_type", {"element": field, "text": "Delhi"})
    assert not is_error and verified and "Delhi" in said  # nosec B101
    said, is_error, verified = await tools.call("browser_type", {"element": field, "text": "Pune", "submit": True})
    assert not is_error and not verified  # nosec B101  what the site did cannot be confirmed
    assert "Trains from Pune" in said  # nosec B101


async def test_a_click_presses_exactly_the_numbered_element(tools, site):
    text = await _open(tools, site)
    said, is_error, verified = await tools.call("browser_click", {"element": _number(text, "About us")})
    assert not is_error and not verified and "Page: About" in said  # nosec B101


async def test_password_fields_are_never_typed_into(tools, site):
    text = await _open(tools, site)
    secret = _number(text, "Secret")
    assert await tools.precheck("browser_type", {"element": secret, "text": "x"}) == [  # nosec B101
        "password fields are never typed into"]
    _, is_error, _ = await tools.call("browser_type", {"element": secret, "text": "hunter2"})
    assert is_error  # nosec B101


async def test_an_element_from_no_page_is_refused(tools):
    assert await tools.precheck("browser_click", {"element": 3})  # nosec B101


async def test_private_addresses_are_blocked(monkeypatch, site):
    monkeypatch.setenv(browser_tools.ENABLE_ENV, "1")
    guarded = BrowserTools()
    try:
        text, is_error, _ = await guarded.call("browser_open", {"url": site})
        if "no browser could be started" in text:
            pytest.skip("UNVERIFIED on this host: " + text)
        assert is_error and "ERR_BLOCKED_BY_CLIENT" in text  # nosec B101
        _, is_error, _ = await guarded.call("browser_open", {"url": "file:///C:/Windows/win.ini"})
        assert is_error  # nosec B101
    finally:
        await guarded.close()


async def test_the_owner_hears_which_element_on_which_site(tools, site, tmp_path):
    text = await _open(tools, site)
    button = _number(text, "Search trains")
    server = browser_server()
    server.local = tools
    engine = PolicyEngine()
    install_default_policies(engine)
    install_mcp_policies(engine, [server])

    class Model:
        def __init__(self):
            self.script = [("", [ToolCall(name="browser__browser_click", arguments={"element": button})]),
                           ("Searched.", [])]

        async def supports_tool_calling(self, model):
            return True

        async def complete(self, request):
            text, calls = self.script.pop(0) if self.script else ("Okay.", [])
            return SimpleNamespace(content=text, tool_calls=calls, finish_reason="stop")

    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=Model(), platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
        avatar=None, deployment=None, gpu_pool=None, mcp_servers=[server], reminder_store=tmp_path / "r.json",
    )

    async def no_web(*a, **k):
        return ""

    orch._fetch_web_context = no_web
    orch._start_tools()
    await orch._tools_starting
    try:
        asked = await orch.run_text_turn("search the trains")
        assert asked.awaiting_reply  # nosec B101
        assert "press the button 'Search trains' on 127.0.0.1" in asked.llm_response  # nosec B101
        assert "Page: Train search" in await tools._snapshot()  # nosec B101  nothing pressed yet
        done = await orch.run_text_turn("yes")
        # Pressed, but what the site did is not confirmed by the assistant.
        assert done.action_status is ActionStatus.UNVERIFIED  # nosec B101
    finally:
        orch.close_scheduler()
        await orch.close_tools()


def test_not_offered_unless_switched_on(monkeypatch):
    monkeypatch.delenv(browser_tools.ENABLE_ENV, raising=False)
    assert BrowserTools().tool_list() == []  # nosec B101
