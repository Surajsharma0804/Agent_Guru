"""The code tool runs only behind the sandbox, only after the owner's yes, and says how the run ended.

The model and the owner's words are scripted; the tool loop, MCPToolbox
and the policy engine are real. The last test runs the real WSL sandbox
where it is set up.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Agent_Guru.integration import code_tools
from Agent_Guru.integration.code_tools import CodeTools, code_server
from Agent_Guru.integration.mcp_tools import install_mcp_policies
from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator
from Agent_Guru.llm.models import ToolCall
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies
from Agent_Guru.reasoning.tools.skills import wsl_sandbox
from Agent_Guru.reasoning.tools.skills.wsl_sandbox import SandboxRun

PROGRAM = "print(2 ** 200)"
ANSWER = str(2 ** 200)


class Model:
    def __init__(self, *script):
        self.script, self.requests = list(script), []

    async def supports_tool_calling(self, model):
        return True

    async def complete(self, request):
        self.requests.append(request)
        text, calls = self.script.pop(0) if self.script else ("Okay.", [])
        return SimpleNamespace(content=text, tool_calls=calls, finish_reason="stop")


def _call(code=PROGRAM):
    return ToolCall(name="code__run_python", arguments={"code": code})


@pytest.fixture
def boundary_ok(monkeypatch):
    monkeypatch.setenv(code_tools.ENABLE_ENV, "1")
    monkeypatch.setattr(wsl_sandbox, "check", lambda *a, **k: [])
    runs = []

    async def fake_run(code, *, seconds=10, memory_mb=256):
        runs.append(code)
        return SandboxRun("success", 0, ANSWER + "\n", "", 0.2)

    monkeypatch.setattr(wsl_sandbox, "run_python", fake_run)
    return runs


@pytest.fixture
async def build(tmp_path):
    made = []

    async def make(*script):
        server = code_server()
        server.local = CodeTools()
        engine = PolicyEngine()
        install_default_policies(engine)
        install_mcp_policies(engine, [server])
        model = Model(*script)
        orch = IntegrationOrchestrator(
            speech_engine=None, vision_engine=None, llm_runtime=model, platform_controller=None,
            agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
            avatar=None, deployment=None, gpu_pool=None, mcp_servers=[server],
            reminder_store=tmp_path / "reminders.json",
        )

        async def no_web(*a, **k):
            return ""

        orch._fetch_web_context = no_web
        orch._start_tools()
        await orch._tools_starting
        made.append(orch)
        return orch, model

    yield make
    for orch in made:
        orch.close_scheduler()
        await orch.close_tools()


def test_not_offered_unless_switched_on(monkeypatch):
    monkeypatch.delenv(code_tools.ENABLE_ENV, raising=False)
    monkeypatch.setattr(wsl_sandbox, "check", lambda *a, **k: (_ for _ in ()).throw(AssertionError("checked")))
    assert CodeTools().tool_list() == []  # nosec B101


def test_not_offered_when_the_sandbox_cannot_be_trusted(monkeypatch):
    monkeypatch.setenv(code_tools.ENABLE_ENV, "1")
    monkeypatch.setattr(wsl_sandbox, "check", lambda *a, **k: ["Windows interop is on"])
    tools = CodeTools()
    assert tools.tool_list() == []  # nosec B101


async def test_a_call_without_a_trusted_sandbox_runs_nothing(monkeypatch):
    monkeypatch.setattr(wsl_sandbox, "check", lambda *a, **k: ["no user agsandbox"])
    monkeypatch.setattr(wsl_sandbox, "run_python", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    text, is_error, verified = await CodeTools().call("run_python", {"code": PROGRAM})
    assert is_error and not verified and "no user agsandbox" in text  # nosec B101


async def test_the_owner_is_asked_before_the_program_runs(boundary_ok, build):
    orch, _ = await build(("", [_call()]), (f"It is {ANSWER}.", []))
    asked = await orch.run_text_turn("what is 2 to the power 200?")
    assert asked.awaiting_reply and "Python in the sandbox" in asked.llm_response  # nosec B101
    assert "2 ** 200" in asked.llm_response  # nosec B101  the program is read back
    assert boundary_ok == []  # nosec B101  nothing ran yet
    done = await orch.run_text_turn("yes")
    assert boundary_ok == [PROGRAM]  # nosec B101
    assert done.action_status is ActionStatus.SUCCESS  # nosec B101
    assert ANSWER in done.llm_response  # nosec B101


async def test_anything_but_yes_runs_nothing(boundary_ok, build):
    orch, _ = await build(("", [_call()]))
    await orch.run_text_turn("what is 2 to the power 200?")
    result = await orch.run_text_turn("no")
    assert boundary_ok == [] and result.action_status is ActionStatus.CANCELLED  # nosec B101


async def test_the_model_is_told_how_the_run_ended(boundary_ok, build, monkeypatch):
    async def stopped(code, *, seconds=10, memory_mb=256):
        return SandboxRun("timeout", None, "", "", 10.0)

    monkeypatch.setattr(wsl_sandbox, "run_python", stopped)
    orch, model = await build(("", [_call("while True: pass")]), ("It took too long.", []))
    await orch.run_text_turn("loop forever")
    done = await orch.run_text_turn("yes")
    shown = [m.content for m in model.requests[-1].messages if m.role == "tool"]
    assert any("stopped at its time limit" in s for s in shown)  # nosec B101
    assert done.action_status is ActionStatus.FAILED  # nosec B101


def test_long_output_keeps_its_start_and_end():
    text = code_tools._report(SandboxRun("success", 0, "a" * 5000 + "END", "", 0.1))
    assert "characters left out" in text and text.rstrip().endswith("END")  # nosec B101


async def test_the_real_sandbox_computes_the_answer(monkeypatch, build):
    problems = wsl_sandbox.check()
    if problems:
        pytest.skip("UNVERIFIED on this host: " + "; ".join(problems))
    monkeypatch.setenv(code_tools.ENABLE_ENV, "1")
    orch, model = await build(("", [_call()]), ("Done.", []))
    await orch.run_text_turn("what is 2 to the power 200?")
    done = await orch.run_text_turn("yes")
    shown = " ".join(m.content for m in model.requests[-1].messages if m.role == "tool")
    assert ANSWER in shown and done.action_status is ActionStatus.SUCCESS  # nosec B101
