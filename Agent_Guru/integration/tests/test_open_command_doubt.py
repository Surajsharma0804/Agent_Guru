"""Overheard or garbled speech asks before opening anything; clean commands still open at once.

The rule engine routes any sentence with "open" in it to open_app or open_url, and the action
stage opened a guessed website for a name it did not know: "Guru, Open Note Packed" (a real turn,
2026-10-23) went to www.notepacked.com, "I opened the window in the morning" to www.window.com.
Turns run under the starting policy; the controller records calls and no browser starts.
"""

from __future__ import annotations

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies


class Controller:
    def __init__(self):
        self.calls = []

    def app_instances(self, name):
        return {}

    def open_application(self, name):
        self.calls.append(("app", name))
        return {"success": True}


@pytest.fixture
async def turn(tmp_path):
    engine = PolicyEngine()
    install_default_policies(engine)
    ctrl = Controller()
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=ctrl,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine, avatar=None,
        deployment=None, gpu_pool=None, reminder_store=tmp_path / "r.json",
    )
    orch._APP_OPEN_VERIFY_S = 0.0

    async def no_browser(c, param):
        ctrl.calls.append(("url", param))
        return f"Opening {param}"

    orch._action_open_url = no_browser

    async def say(text):
        return await orch.run_text_turn(text), ctrl.calls

    yield say
    orch.close_scheduler()


@pytest.mark.parametrize("said, opened", [
    ("open notepad", ("app", "notepad")), ("open youtube", ("url", "youtube")),
    ("launch vs code", ("app", "vscode")), ("open github.com", ("url", "github.com")),
    ("open file explorer", ("app", "file explorer")), ("Guru, open calculator", ("app", "calculator")),
])
async def test_a_clean_command_opens_without_a_question(turn, said, opened):
    result, calls = await turn(said)
    assert calls == [opened] and "?" not in (result.action_result or "")  # nosec B101


# Exactly as Whisper transcribed the synthesized speech (scratchpad conf_measure.py); each of
# these reached open_app or open_url and opened something before.
@pytest.mark.parametrize("said", [
    "I open the window in the morning.",
    "She said it was open season on everything.",
    "Open the door when the guests arrive.",
    "Ram Kalan, Thaisakritu Mous, Rusman, Arit Kumar, Pramini Singh, I'm going to start the",
])
async def test_overheard_speech_opens_nothing(turn, said):
    result, calls = await turn(said)
    assert calls == [] and result.action_result  # nosec B101  it says why instead


@pytest.mark.parametrize("said", ["Guru, Open Note Packed.", "open not pad", "open my files"])
async def test_a_website_it_does_not_know_is_never_guessed(turn, said):
    result, calls = await turn(said)
    assert calls == [] and "won't guess" in (result.action_result or "")  # nosec B101


def test_a_guess_is_refused_without_a_transcript():
    # A scheduled or replayed action carries no words to check, so only the website rule applies.
    from Agent_Guru.integration.orchestrator import _open_command_doubt

    assert _open_command_doubt("", "open_url", "Note Packed") is not None  # nosec B101
    assert _open_command_doubt("", "open_url", "youtube") is None  # nosec B101
    assert _open_command_doubt("", "open_app", "notepad") is None  # nosec B101
