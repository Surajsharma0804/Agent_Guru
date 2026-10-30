"""One turn at a time, and a question is answered only by the source that was asked.

Voice turns, typed turns (local API, ask, chat), A2A, the OpenAI endpoint and chat channels each
called run_pipeline on their own; only the API and the channels had a lock, each its own. In the
live run a false voice wake ran beside a typed turn and its words leaked into the typed answer, and
a pending "Should I ...?" took the next yes from anyone. These run the real orchestrator; the model
is scripted, the browser records its visits, and nothing is spoken.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from Agent_Guru.integration import browser_tools
from Agent_Guru.integration import orchestrator as orch_mod
from Agent_Guru.integration.browser_tools import BrowserTools, browser_server
from Agent_Guru.integration.mcp_tools import install_mcp_policies
from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.llm.models import ToolCall
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies

URL = "https://weather.example/delhi?q=7314"  # an address the owner never said


class RecordedBrowser(BrowserTools):
    def __init__(self) -> None:
        super().__init__()
        self.opened: list[str] = []

    async def _open(self, url):
        self.opened.append(url)
        return "Page: Weather\nSunny, 31 C.", False, False


class Model:
    """Asks to open URL whenever it is offered tools for a question; answers anything else plainly."""

    async def supports_tool_calling(self, model):
        return True

    async def complete(self, request):
        last = request.messages[-1]
        if getattr(last, "role", "") == "user" and "weather" in str(getattr(last, "content", "")):
            return SimpleNamespace(content="", tool_calls=[ToolCall(name="browser__browser_open",
                                                                   arguments={"url": URL})], finish_reason="stop")
        return SimpleNamespace(content="Okay.", tool_calls=[], finish_reason="stop")


@pytest.fixture
async def assistant(monkeypatch, tmp_path):
    monkeypatch.setenv(browser_tools.ENABLE_ENV, "1")
    browser = RecordedBrowser()
    server = browser_server()
    server.local = browser
    engine = PolicyEngine()
    install_default_policies(engine)
    install_mcp_policies(engine, [server])
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=Model(), platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
        avatar=None, deployment=None, gpu_pool=None, mcp_servers=[server], reminder_store=tmp_path / "r.json",
    )

    async def no_web(*a, **k):
        return ""

    async def silent(*a, **k):
        return None

    heard: dict[bytes, str] = {}

    async def stt(audio, personality):
        return heard[audio], "en"

    orch._fetch_web_context = no_web
    orch._stage_tts = silent
    orch._play_filler = silent
    orch._stage_stt = stt
    orch._start_tools()
    await orch._tools_starting

    def voice(words: str) -> WakeWordEvent:
        audio = words.encode()
        heard[audio] = words
        return WakeWordEvent(wake_word="Hey Guru", audio=audio)

    yield SimpleNamespace(orch=orch, browser=browser, voice=voice)
    orch.close_scheduler()
    await orch.close_tools()


async def test_a_typed_and_a_voice_turn_started_together_run_one_after_the_other(assistant, monkeypatch):
    orch = assistant.orch
    running, spans = 0, []
    real = orch._run_turn

    async def tracked(event, result, *rest):
        nonlocal running
        running += 1
        spans.append(("start", result.source, running))
        await asyncio.sleep(0.05)
        out = await real(event, result, *rest)
        spans.append(("end", result.source, running))
        running -= 1
        return out

    monkeypatch.setattr(orch, "_run_turn", tracked)
    await asyncio.gather(orch.run_text_turn("tell me a joke"), orch.run_pipeline(assistant.voice("good morning")))
    assert [s[2] for s in spans] == [1, 1, 1, 1], spans  # never two at once
    assert [s[:2] for s in spans] == [("start", "typed"), ("end", "typed"), ("start", "voice"), ("end", "voice")]


async def test_turns_past_the_queue_limit_are_turned_away_and_logged(assistant, monkeypatch, caplog):
    orch, release = assistant.orch, asyncio.Event()
    real = orch._run_turn

    async def held(event, result, *rest):
        await release.wait()
        return await real(event, result, *rest)

    monkeypatch.setattr(orch, "_run_turn", held)
    first = asyncio.create_task(orch.run_text_turn("one"))
    await asyncio.sleep(0.01)
    waiting = [asyncio.create_task(orch.run_text_turn(f"wait {i}")) for i in range(orch_mod.TURN_QUEUE_LIMIT)]
    await asyncio.sleep(0.01)
    turned_away = await asyncio.wait_for(orch.run_text_turn("one too many"), timeout=1)
    assert turned_away.error == "busy" and turned_away.llm_response == orch_mod.BUSY_REPLY
    assert "turned away" in caplog.text
    release.set()
    done = await asyncio.gather(first, *waiting)
    assert all(r.error != "busy" for r in done)


async def test_a_voice_yes_does_not_answer_a_typed_question(assistant):
    orch, browser = assistant.orch, assistant.browser
    asked = await orch.run_text_turn("what is the weather like today")
    assert asked.awaiting_reply and browser.opened == []
    heard = await orch.run_pipeline(assistant.voice("yes"))
    assert browser.opened == [] and not heard.awaiting_reply
    assert "typed" in orch._tool_pending  # still the typed question, still open
    await orch.run_text_turn("yes")
    assert browser.opened == [URL]


async def test_a_typed_yes_does_not_answer_a_spoken_question(assistant):
    orch, browser = assistant.orch, assistant.browser
    asked = await orch.run_pipeline(assistant.voice("what is the weather like today"))
    assert asked.awaiting_reply and browser.opened == []
    await orch.run_text_turn("yes")
    assert browser.opened == []
    await orch.run_pipeline(assistant.voice("yes"))
    assert browser.opened == [URL]


async def test_a_question_left_too_long_expires_and_says_so(assistant):
    orch, browser = assistant.orch, assistant.browser
    await orch.run_text_turn("what is the weather like today")
    orch._tool_pending["typed"]["expires"] = 0.0
    late = await orch.run_text_turn("yes")
    assert browser.opened == []
    assert "seconds for an answer" in (late.action_result or "") and not late.awaiting_reply


async def test_a_message_draft_is_finished_only_by_the_source_that_was_asked(assistant):
    orch = assistant.orch
    orch.platform_controller = SimpleNamespace(send_message=None)
    question = orch._start_message_draft  # asked inside a typed turn below
    token = orch_mod._TURN.set(("typed", 1))
    try:
        question("whatsapp", "John", "")
    finally:
        orch_mod._TURN.reset(token)
    token = orch_mod._TURN.set(("voice", 2))
    try:
        assert await orch._continue_message_draft("meet me at six") is None
    finally:
        orch_mod._TURN.reset(token)
    assert orch._message_draft["typed"]["message"] == ""


def test_the_local_api_says_its_turns_come_from_the_api(monkeypatch):
    # ask, chat and the dashboard type through the local API: their questions
    # must be answered from there, not by whatever the microphone hears next.
    import secrets

    from fastapi.testclient import TestClient

    from Agent_Guru.integration import local_api

    key, seen = secrets.token_urlsafe(24), []

    class Recording:
        events = SimpleNamespace(publish=lambda event, **d: None)

        async def run_text_turn(self, text, source="typed"):
            seen.append(source)
            return SimpleNamespace(llm_response="ok", action_result=None, action_status=None,
                                   awaiting_reply=False, sources=[], error=None)

    monkeypatch.setattr(local_api, "owner_key", lambda **k: key)
    TestClient(local_api.create_app(Recording())).post("/v1/turn", json={"text": "hi"}, headers={"X-API-Key": key})
    assert seen == ["api"]
