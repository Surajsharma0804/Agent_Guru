"""What open_url opens: known sites and the addresses the owner said, and never a guessed one.

The browser is a recorder; nothing opens.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator


class Controller:
    def app_instances(self, name):
        return {}

    def open_application(self, name):
        return {"success": True}


@pytest.fixture
def opened():
    urls: list[str] = []

    class Browser:
        async def open_url(self, url):
            urls.append(url)

    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=Controller(),
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=None, avatar=None,
        deployment=None, gpu_pool=None, reminder_store=Path(tempfile.mkdtemp()) / "r.json",
    )

    async def browser():
        return Browser()

    orch._get_browser_mgr = browser
    yield orch, urls
    orch.close_scheduler()


@pytest.mark.parametrize("target, url", [
    ("youtube", "https://www.youtube.com"), ("github", "https://github.com"), ("example.com", "https://example.com"),
])
async def test_a_known_site_or_an_address_opens_as_before(opened, target, url):
    orch, urls = opened
    await orch._execute_single_action(f"system_control:open_url:{target}", "full", "")
    assert urls == [url]  # nosec B101


@pytest.mark.parametrize("target", [" example.com", "example.com "])
async def test_a_padded_address_is_not_turned_into_a_guess(opened, target):
    # The domain check saw the space and fell through to https://www.example.com.com.
    orch, urls = opened
    await orch._execute_single_action(f"system_control:open_url:{target}", "full", "")
    assert urls == ["https://example.com"]  # nosec B101


@pytest.mark.parametrize("target", ["Note Packed", "notpad", "my files"])
async def test_an_unknown_name_is_never_guessed_even_past_the_gate(opened, target):
    orch, urls = opened
    reply = await orch._action_open_url(Controller(), target)
    assert urls == [] and "won't guess" in reply  # nosec B101


@pytest.fixture
def turn(opened):
    from Agent_Guru.policy import PolicyEngine
    from Agent_Guru.policy.defaults import install_default_policies

    orch, urls = opened
    engine = PolicyEngine()
    install_default_policies(engine)
    orch.policy = engine

    async def say(text):
        await orch.run_text_turn(text)
        return urls

    return say


@pytest.mark.parametrize("said, url", [
    ("open example.com", "https://example.com"),                    # was cut to "example"
    ("open www.example.com", "https://www.example.com"),            # was cut to "www"
    ("go to https://github.com/python", "https://github.com/python"),  # was the site "https"
    ("open https://example.com/docs?a=1&b=2", "https://example.com/docs?a=1&b=2"),  # "&" became " and "
    ("visit http://localhost:8080/x", "http://localhost:8080/x"),   # the port's ":" split the intent
])
async def test_an_address_the_owner_says_opens_as_said(turn, said, url):
    assert await turn(said) == [url]  # nosec B101
