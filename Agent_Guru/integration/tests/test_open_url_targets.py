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
