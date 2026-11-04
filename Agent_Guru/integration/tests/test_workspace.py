"""The everyday window: the orb follows real events, and a yes stays with the question that asked."""

from __future__ import annotations

import asyncio
import inspect
import threading
from types import SimpleNamespace

import pytest

from Agent_Guru.integration import workspace as ws
from Agent_Guru.integration.events import EventBus
from Agent_Guru.utils.settings import KNOWN_SETTINGS


def orb_after(*events, muted=False):
    orb = ws.Orb(muted)
    for topic, *data in events:
        orb.apply(topic, data[0] if data else {})
    return orb.state


def test_the_orb_moves_through_a_spoken_turn_on_events_alone():
    steps = [("listen.started", "listening"), ("listen.finished", "idle"), ("turn.started", "thinking"),
             ("speech.started", "speaking"), ("speech.finished", "thinking"), ("turn.ended", "idle")]
    seen = []
    orb = ws.Orb()
    for topic, want in steps:
        orb.apply(topic, {})
        seen.append(orb.state)
    assert seen == [want for _, want in steps]  # nosec B101


def test_muted_shows_when_nothing_is_running_and_a_running_turn_still_shows():
    assert orb_after(("mic", {"muted": True})) == "muted"  # nosec B101
    assert orb_after(("mic", {"muted": True}), ("turn.started",)) == "thinking"  # nosec B101
    assert orb_after(("mic", {"muted": True}), ("mic", {"muted": False})) == "idle"  # nosec B101


def test_the_orb_has_no_clock():
    source = inspect.getsource(ws.Orb)
    assert "time." not in source and "sleep" not in source and "Timer" not in source  # nosec B101


def test_every_studio_control_is_a_real_setting():
    assert [i["key"] for i in ws.STUDIO if i["key"] not in KNOWN_SETTINGS] == []  # nosec B101


class FakeOrch:
    def __init__(self):
        self.events = EventBus()
        self.microphone = None
        self.questions = []
        self.ran = []

    def pending_questions(self):
        return list(self.questions)

    async def run_text_turn(self, text, source="typed"):
        self.ran.append((text, source))


@pytest.fixture
def workspace():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    orch = FakeOrch()
    w = ws.Workspace(orch, loop)
    yield w
    loop.call_soon_threadsafe(loop.stop)
    thread.join(5)


def post(w, path, body):
    return w.routes()[("POST", path)](body)


def settle(w):
    asyncio.run_coroutine_threadsafe(asyncio.sleep(0), w.loop).result(5)


def test_a_typed_turn_runs_as_this_windows_source(workspace):
    status, _ = post(workspace, "/api/turn", {"text": "hello"})
    settle(workspace)
    assert status == 202 and workspace.orch.ran == [("hello", ws.SOURCE)]  # nosec B101
    assert post(workspace, "/api/turn", {"text": "   "})[0] == 400  # nosec B101
    assert post(workspace, "/api/turn", {"text": "x" * (ws.MAX_TEXT + 1)})[0] == 400  # nosec B101


def test_a_question_asked_by_voice_cannot_be_answered_from_the_window(workspace):
    workspace.orch.questions = [{"source": "voice", "turn": 7, "question": "Delete the file?"}]
    status, body = post(workspace, "/api/answer", {"source": "voice", "turn": 7, "yes": True})
    assert status == 409 and "by voice" in body["error"] and workspace.orch.ran == []  # nosec B101


def test_an_answer_needs_the_exact_turn_that_asked(workspace):
    workspace.orch.questions = [{"source": ws.SOURCE, "turn": 7, "question": "Delete the file?"}]
    assert post(workspace, "/api/answer", {"source": ws.SOURCE, "turn": 6, "yes": True})[0] == 409  # nosec B101
    assert workspace.orch.ran == []  # nosec B101
    assert post(workspace, "/api/answer", {"source": ws.SOURCE, "turn": 7, "yes": False})[0] == 202  # nosec B101
    settle(workspace)
    assert workspace.orch.ran == [("no", ws.SOURCE)]  # nosec B101


def test_the_window_sees_which_question_is_waiting(workspace):
    workspace.orch.questions = [{"source": "voice", "turn": 3, "question": "Send it?"}]
    assert workspace.state({})[1]["questions"] == workspace.orch.questions  # nosec B101


def test_turns_and_the_queue_come_from_events(workspace):
    on = workspace.on_event
    on(SimpleNamespace(topic="turn.started", data={"source": ws.SOURCE, "turn_id": 1}))
    on(SimpleNamespace(topic="turn.queued", data={"source": "voice", "waiting": 1}))
    state = workspace.state({})[1]
    assert state["orb"] == "thinking" and state["waiting"] == 1  # nosec B101
    on(SimpleNamespace(topic="turn.finished", data={"turn_id": 1, "heard": "hi", "said": "hello", "status": "ok",
                                                    "sources": ["https://example.test/a"]}))
    on(SimpleNamespace(topic="turn.ended", data={"turn_id": 1}))
    row = workspace.state({})[1]["turns"][0]
    assert (row["heard"], row["said"], row["sources"]) == ("hi", "hello", ["https://example.test/a"])  # nosec B101
    assert workspace.state({})[1]["orb"] == "idle"  # nosec B101


@pytest.mark.parametrize("item", ws.STUDIO, ids=lambda i: i["key"])
def test_each_studio_control_round_trips_through_settings_toml(workspace, tmp_path, monkeypatch, item):
    from Agent_Guru.utils import commands

    monkeypatch.setattr(commands, "_settings_file", lambda: tmp_path / "settings.toml")
    monkeypatch.delenv(item["key"], raising=False)
    value = {"flag": True, "number": 4096, "choice": "cpu"}.get(item["control"], "gemma4:latest")
    status, _ = post(workspace, "/api/setting", {"key": item["key"], "value": value})
    assert status == 200  # nosec B101
    control = next(c for c in workspace.settings({})[1]["controls"] if c["key"] == item["key"])
    assert control["value"] == value  # nosec B101


def test_a_setting_off_the_screen_is_refused(workspace):
    assert post(workspace, "/api/setting", {"key": "AGENT_GURU_MAX_RESTARTS", "value": "1"})[0] == 400  # nosec B101
    assert post(workspace, "/api/setting", {"key": "OLLAMA_MODEL", "value": "x", "path": "y"})[0] == 400  # nosec B101


def test_a_provider_key_goes_in_and_is_never_shown_back(workspace, monkeypatch):
    from Agent_Guru.security import vault

    stored = {}
    monkeypatch.setattr(vault, "put", stored.__setitem__)
    monkeypatch.setattr(vault, "names", lambda: sorted(stored))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    status, body = post(workspace, "/api/credential", {"name": "OPENAI_API_KEY", "value": "sk-private"})
    assert status == 200 and stored == {"OPENAI_API_KEY": "sk-private"} and "sk-private" not in str(body)  # nosec B101
    view = workspace.settings({})[1]
    assert view["credentials"]["OPENAI_API_KEY"] == "set" and "sk-private" not in str(view)  # nosec B101
    assert post(workspace, "/api/credential", {"name": "PATH", "value": "x"})[0] == 400  # nosec B101


def test_a_spoken_yes_does_not_confirm_a_typed_question():
    """On the real orchestrator: the pending call stays with the source that asked."""
    from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
    from Agent_Guru.integration.tool_loop import PendingCall
    from Agent_Guru.policy import PolicyEngine
    from Agent_Guru.policy.defaults import install_default_policies

    class Model:
        async def complete(self, request):
            return SimpleNamespace(content="All right.", finish_reason="stop", tool_calls=[])

    async def main():
        engine = PolicyEngine()
        install_default_policies(engine)
        orch = IntegrationOrchestrator(speech_engine=None, vision_engine=None, llm_runtime=Model(), platform_controller=None,
                                       agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
                                       avatar=None, deployment=None, gpu_pool=None)

        async def no_web(*a, **k):
            return ""

        orch._fetch_web_context = no_web
        called = []
        loop = SimpleNamespace(resume=lambda *a, **k: called.append(a))
        pending = PendingCall(name="files.delete", server="files", tool="delete", arguments={}, question="Delete notes.txt?")
        orch._tool_pending[ws.SOURCE] = {"pending": pending, "loop": loop, "messages": [], "request": None,
                                         "expires": 1e12, "turn": 1}
        assert orch.pending_questions() == [{"source": ws.SOURCE, "turn": 1, "question": "Delete notes.txt?"}]  # nosec B101
        await orch.run_text_turn("yes", source="voice")
        orch.close_scheduler()
        return orch, called

    orch, called = asyncio.run(main())
    assert ws.SOURCE in orch._tool_pending and called == []  # nosec B101


def test_the_pipeline_publishes_each_turns_start_and_end():
    from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
    from Agent_Guru.policy import PolicyEngine
    from Agent_Guru.policy.defaults import install_default_policies

    class Model:
        async def complete(self, request):
            return SimpleNamespace(content="Fine.", finish_reason="stop", tool_calls=[])

    async def main():
        engine = PolicyEngine()
        install_default_policies(engine)
        orch = IntegrationOrchestrator(speech_engine=None, vision_engine=None, llm_runtime=Model(), platform_controller=None,
                                       agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
                                       avatar=None, deployment=None, gpu_pool=None)

        async def no_web(*a, **k):
            return ""

        orch._fetch_web_context = no_web
        seen = []
        orch.events.subscribe("*", lambda e: seen.append((e.topic, e.data.get("source"))))
        with orch._speaking(), orch._speaking():
            pass
        await asyncio.gather(orch.run_text_turn("first", source="a"), orch.run_text_turn("second", source="b"))
        await asyncio.sleep(0.05)
        orch.close_scheduler()
        return seen

    seen = asyncio.run(main())
    topics = [t for t, _ in seen]
    assert topics[:2] == ["speech.started", "speech.finished"]  # nosec B101  once, however deep
    assert ("turn.queued", "b") in seen and topics.count("turn.started") == 2 and topics.count("turn.ended") == 2  # nosec B101
