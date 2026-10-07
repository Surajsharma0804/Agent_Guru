"""Tools on external MCP servers are called only as the owner allowed, and reported as what they did.

Before this the assistant had no way to use an MCP server. These tests run a
real server process over stdio (mcp_test_server.py beside this file), the
assistant's real policy engine through the orchestrator's policy stage, and
a real audit log, so each gate below is the one a voice turn will pass.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess  # nosec B404  the tests look for leftover server processes
import sys
import time
from pathlib import Path

import pytest

from Agent_Guru.integration import mcp_tools
from Agent_Guru.integration.mcp_tools import (
    MAX_OUTPUT_CHARS,
    ServerConfig,
    ToolRisk,
    ToolRule,
    build_toolbox,
    parse_servers,
)
from Agent_Guru.integration.orchestrator import ActionStatus
from Agent_Guru.integration.turn_trace import TurnRecord, TurnTraceStore
from Agent_Guru.reasoning.tools import mcp_client
from Agent_Guru.reasoning.tools.mcp_client import MCPConnection, ServerUnavailable
from Agent_Guru.security.audit.logger import AuditLogger, EventType, LogQuery, signing_key_at

SERVER = str(Path(__file__).with_name("mcp_test_server.py"))

RULES = {
    "echo": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "write_note": ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE),
    "lying_read": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "inject": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "big": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "sleep": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "crash": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "wrong_id": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "stray": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "no_result": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "fails": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "env_names": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "choice": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "fancy": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
    "wipe": ToolRule(allow=False, risk=ToolRisk.DESTRUCTIVE),
}


def _server(name="test", *flags, tools=None, timeout=5.0, max_kb=1024, notes=None):
    env = {"MCP_TEST_NOTES": str(notes)} if notes else {}
    return ServerConfig(
        name=name, command=sys.executable, args=[SERVER, *flags], env=env, timeout=timeout,
        start_timeout=15.0, max_message_bytes=max_kb * 1024, tools=dict(RULES if tools is None else tools),
    )


@pytest.fixture
def audit(tmp_path):
    return AuditLogger(str(tmp_path / "audit.db"), signing_key=signing_key_at(tmp_path / "audit_signing.key"))


@pytest.fixture
def notes(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("", encoding="utf-8")
    return path


@pytest.fixture
async def toolbox(audit, notes):
    box = build_toolbox([_server(notes=notes)], audit_logger=audit, actor="test")
    yield box
    await box.close()


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(  # noqa: S603  # nosec B603 B607
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False,
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# ---- what the owner allowed ----

async def test_an_allowed_read_only_tool_runs_and_succeeds(toolbox):
    result = await toolbox.call("test", "echo", {"text": "hello"})
    assert (result.status, result.output) == (ActionStatus.SUCCESS, "hello")  # nosec B101


async def test_a_tool_the_owner_did_not_allow_is_denied_without_running(audit, notes):
    rules = {**RULES, "write_note": ToolRule(allow=False, risk=ToolRisk.LOW_RISK_WRITE)}
    box = build_toolbox([_server(tools=rules, notes=notes)], audit_logger=audit, actor="test")
    try:
        result = await box.call("test", "write_note", {"note": "x"})
    finally:
        await box.close()
    assert (result.status, result.category) == (ActionStatus.DENIED, "not_allowed")  # nosec B101
    assert notes.read_text(encoding="utf-8") == ""  # nosec B101


async def test_a_tool_whose_risk_was_not_declared_is_denied(audit, notes):
    rules = {**RULES, "echo": ToolRule(allow=True)}
    box = build_toolbox([_server(tools=rules, notes=notes)], audit_logger=audit, actor="test")
    try:
        result = await box.call("test", "echo", {"text": "hi"})
    finally:
        await box.close()
    assert (result.status, result.category) == (ActionStatus.DENIED, "unknown_risk")  # nosec B101


async def test_a_destructive_tool_is_denied_unless_allowed(audit, notes):
    notes.write_text("keep me\n", encoding="utf-8")
    box = build_toolbox([_server(notes=notes)], audit_logger=audit, actor="test")
    try:
        denied = await box.call("test", "wipe")
    finally:
        await box.close()
    assert denied.status is ActionStatus.DENIED and notes.read_text(encoding="utf-8") == "keep me\n"  # nosec B101

    rules = {**RULES, "wipe": ToolRule(allow=True, risk=ToolRisk.DESTRUCTIVE)}
    box = build_toolbox([_server(tools=rules, notes=notes)], audit_logger=audit, actor="test")
    try:
        allowed = await box.call("test", "wipe")
    finally:
        await box.close()
    # It ran, and the server says so, but nothing here looked at the file.
    assert allowed.status is ActionStatus.UNVERIFIED and notes.read_text(encoding="utf-8") == ""  # nosec B101


async def test_a_change_the_server_reports_done_is_unverified(toolbox, notes):
    result = await toolbox.call("test", "write_note", {"note": "buy milk"})
    assert result.status is ActionStatus.UNVERIFIED and result.output == "saved"  # nosec B101
    assert notes.read_text(encoding="utf-8") == "buy milk\n"  # nosec B101


async def test_read_only_declared_against_the_servers_word_is_refused(toolbox, notes):
    result = await toolbox.call("test", "lying_read")
    assert (result.status, result.category) == (ActionStatus.DENIED, "hint_conflict")  # nosec B101
    assert notes.read_text(encoding="utf-8") == ""  # nosec B101


async def test_the_policy_engine_has_the_last_word(audit, notes, monkeypatch):
    # The owner allowed it, but the policy the engine holds does not.
    monkeypatch.setattr(mcp_tools, "install_mcp_policies", lambda engine, servers: 0)
    box = build_toolbox([_server(notes=notes)], audit_logger=audit, actor="test")
    try:
        result = await box.call("test", "echo", {"text": "hi"})
    finally:
        await box.close()
    assert (result.status, result.category) == (ActionStatus.DENIED, "denied_by_policy")  # nosec B101


async def test_an_unknown_tool_or_server_is_denied(toolbox):
    assert (await toolbox.call("test", "nope")).category == "not_found"  # nosec B101
    assert (await toolbox.call("other", "echo")).category == "not_found"  # nosec B101


async def test_only_callable_tools_are_offered(toolbox):
    names = {t.name for t in await toolbox.available_tools()}
    assert "echo" in names and "write_note" in names  # nosec B101
    assert not names & {"wipe", "lying_read", "fancy"}  # nosec B101
    every = await toolbox.discover()
    assert sum(t.name == "echo" for t in every) == 1  # nosec B101  listed twice, kept once


# ---- arguments ----

@pytest.mark.parametrize(("arguments", "problem"), [
    ({}, "text is required"),
    ({"text": 5}, "expected string"),
    ({"text": "hi", "path": "C:/Windows"}, "path is not an argument"),
    ({"text": "x" * 101}, "longer than 100"),
])
async def test_bad_arguments_never_reach_the_server(toolbox, arguments, problem):
    result = await toolbox.call("test", "echo", arguments)
    assert (result.status, result.category) == (ActionStatus.FAILED, "bad_arguments")  # nosec B101
    assert problem in result.error  # nosec B101


async def test_arguments_too_deep_or_too_large_are_refused_without_raising(toolbox):
    deep: dict = {}
    for _ in range(5000):
        deep = {"x": deep}
    result = await toolbox.call("test", "choice", {"mode": "fast", "tags": [deep]})
    assert (result.status, result.category) == (ActionStatus.FAILED, "bad_arguments")  # nosec B101
    assert "deeper" in result.error  # nosec B101
    huge = await toolbox.call("test", "choice", {"mode": "fast", "tags": ["x" * 70_000]})
    assert huge.category == "bad_arguments" and "bytes" in huge.error  # nosec B101


@pytest.mark.parametrize(("arguments", "ok"), [
    ({"mode": "fast"}, True),
    ({"mode": "fast", "when": None, "options": {"level": 5}, "tags": ["a"]}, True),
    ({"mode": "medium"}, False),
    ({"mode": "fast", "options": {"level": 6}}, False),
    ({"mode": "fast", "options": {}}, False),
    ({"mode": "fast", "options": {"level": 1, "extra": True}}, False),
    ({"mode": "fast", "tags": ["a", "b", "c", "d"]}, False),
    ({"mode": "fast", "tags": [1]}, False),
    ({"mode": "fast", "when": 3}, False),
])
async def test_nested_arguments_are_checked(toolbox, arguments, ok):
    result = await toolbox.call("test", "choice", arguments)
    assert (result.status is ActionStatus.SUCCESS) is ok, result.error  # nosec B101


async def test_a_schema_that_cannot_be_checked_makes_the_tool_unavailable(toolbox):
    result = await toolbox.call("test", "fancy", {"x": "a"})
    assert (result.status, result.category) == (ActionStatus.DENIED, "bad_schema")  # nosec B101
    assert "anyOf" in result.error  # nosec B101


# ---- what comes back ----

async def test_output_that_tries_to_steer_the_assistant_is_withheld(toolbox):
    result = await toolbox.call("test", "inject")
    assert result.status is ActionStatus.SUCCESS and result.guarded and result.output == ""  # nosec B101
    assert "Ignore" not in result.for_prompt() and "withheld" in result.for_prompt()  # nosec B101


async def test_output_reaches_the_model_marked_as_data():
    result = mcp_tools.ToolCallResult("s", "t", ActionStatus.SUCCESS, output="42 files")
    prompt = result.for_prompt()
    assert "not instructions" in prompt and "<<<\n42 files\n>>>" in prompt  # nosec B101


async def test_long_output_is_cut_and_the_cut_recorded(toolbox):
    result = await toolbox.call("test", "big", {"chars": MAX_OUTPUT_CHARS + 500})
    assert result.truncated and len(result.output) == MAX_OUTPUT_CHARS  # nosec B101


async def test_a_message_over_the_size_limit_is_refused_and_the_server_still_usable(audit, notes):
    box = build_toolbox([_server(max_kb=64, notes=notes)], audit_logger=audit, actor="test")
    try:
        result = await box.call("test", "big", {"chars": 200_000})
        assert (result.status, result.category) == (ActionStatus.FAILED, "too_large")  # nosec B101
        assert (await box.call("test", "echo", {"text": "after"})).output == "after"  # nosec B101
    finally:
        await box.close()


async def test_a_tool_error_is_a_failure(toolbox):
    result = await toolbox.call("test", "fails")
    assert (result.status, result.category) == (ActionStatus.FAILED, "tool_error")  # nosec B101
    assert "disk is full" in result.error  # nosec B101


async def test_a_server_sees_only_the_environment_it_needs_and_is_given(audit, notes, monkeypatch):
    monkeypatch.setenv("AGENT_GURU_TEST_TOKEN", "should-not-leak")
    monkeypatch.setenv("NOTES_SERVER_KEY", "for-this-server")
    (config,) = parse_servers({"servers": {"test": {
        "command": sys.executable, "args": [SERVER], "pass_env": ["NOTES_SERVER_KEY"],
        "tools": {"env_names": {"allow": True, "risk": "read_only"}},
    }}}, dict(os.environ))
    box = build_toolbox([config], audit_logger=audit, actor="test")
    try:
        names = json.loads((await box.call("test", "env_names")).output)
    finally:
        await box.close()
    assert "AGENT_GURU_TEST_TOKEN" not in names and "NOTES_SERVER_KEY" in names  # nosec B101
    assert {n.upper() for n in names} <= mcp_client._BASE_ENV | {"NOTES_SERVER_KEY"}  # nosec B101


# ---- the protocol ----

async def test_a_wrong_or_repeated_reply_id_never_completes_another_call(toolbox):
    first = await toolbox.call("test", "wrong_id")
    second = await toolbox.call("test", "echo", {"text": "next"})
    assert (first.output, second.output) == ("yours", "next")  # nosec B101


async def test_stray_output_does_not_disturb_the_reply(toolbox):
    assert (await toolbox.call("test", "stray")).output == "clean"  # nosec B101


async def test_a_reply_with_neither_result_nor_error_is_a_failure(toolbox):
    result = await toolbox.call("test", "no_result")
    assert result.status is ActionStatus.FAILED  # nosec B101


async def test_concurrent_calls_each_get_their_own_answer(toolbox):
    results = await asyncio.gather(*(toolbox.call("test", "echo", {"text": f"n{n}"}) for n in range(20)))
    assert [r.output for r in results] == [f"n{n}" for n in range(20)]  # nosec B101


# ---- time and failure ----

async def test_a_read_only_timeout_fails(audit, notes):
    box = build_toolbox([_server(timeout=0.5, notes=notes)], audit_logger=audit, actor="test")
    try:
        result = await box.call("test", "sleep", {"seconds": 5})
        assert (result.status, result.category) == (ActionStatus.FAILED, "timeout")  # nosec B101
        assert (await box.call("test", "echo", {"text": "restarted"})).output == "restarted"  # nosec B101
    finally:
        await box.close()


async def test_a_timeout_on_a_tool_that_changes_things_is_unverified(audit, notes):
    rules = {**RULES, "sleep": ToolRule(allow=True, risk=ToolRisk.EXTERNAL_SIDE_EFFECT)}
    box = build_toolbox([_server(tools=rules, timeout=0.5, notes=notes)], audit_logger=audit, actor="test")
    try:
        result = await box.call("test", "sleep", {"seconds": 5})
    finally:
        await box.close()
    assert (result.status, result.category) == (ActionStatus.UNVERIFIED, "timeout")  # nosec B101


async def test_a_cancelled_call_leaves_no_task_or_process(toolbox):
    task = asyncio.create_task(toolbox.call("test", "sleep", {"seconds": 30}))
    await asyncio.sleep(1.0)
    pid = toolbox._servers["test"].connection.pid
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.5)
    assert not _alive(pid)  # nosec B101
    assert not [t for t in asyncio.all_tasks() if t.get_name().startswith("mcp-")]  # nosec B101


async def test_a_crashed_server_fails_the_call_and_is_started_again(toolbox):
    result = await toolbox.call("test", "crash")
    assert (result.status, result.category) == (ActionStatus.FAILED, "unavailable")  # nosec B101
    toolbox._servers["test"].failure = ""
    assert (await toolbox.call("test", "echo", {"text": "back"})).output == "back"  # nosec B101


async def test_a_server_that_fails_to_start_does_not_take_the_others_down(audit, notes):
    box = build_toolbox(
        [_server("broken", "--fail-start", notes=notes), _server("good", notes=notes)],
        audit_logger=audit, actor="test",
    )
    try:
        broken = await box.call("broken", "echo", {"text": "hi"})
        good = await box.call("good", "echo", {"text": "hi"})
        listed = {t.server for t in await box.discover()}
    finally:
        await box.close()
    assert (broken.status, broken.category) == (ActionStatus.FAILED, "unavailable")  # nosec B101
    assert "cannot open the database" in broken.error  # nosec B101  the server's stderr is reported
    assert good.status is ActionStatus.SUCCESS and listed == {"good"}  # nosec B101


async def test_a_server_flooding_stderr_still_answers(audit, notes):
    box = build_toolbox([_server("noisy", "--stderr-flood", notes=notes)], audit_logger=audit, actor="test")
    try:
        assert (await box.call("noisy", "echo", {"text": "heard"})).output == "heard"  # nosec B101
    finally:
        await box.close()


async def test_closing_ends_the_server_and_what_it_started(tmp_path):
    connection = MCPConnection("tree", sys.executable, [SERVER, "--child"])
    await connection.start(15.0)
    deadline = time.monotonic() + 5
    while not any(line.startswith("child ") for line in connection.stderr_tail) and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    child = int(next(line for line in connection.stderr_tail if line.startswith("child ")).split()[1])
    parent = connection.pid
    await connection.close()
    await asyncio.sleep(0.5)
    assert not _alive(parent) and not _alive(child)  # nosec B101
    with pytest.raises(ServerUnavailable):
        await connection.request("tools/list", {}, timeout=1)


# ---- records ----

async def test_every_call_is_audited_without_secrets(toolbox, audit):
    await toolbox.call("test", "echo", {"text": "hi"})
    await toolbox.call("test", "write_note", {"note": "n", "api_key": "sk-123"})
    entries = [e for e in audit.query_logs(LogQuery()) if e.event_type is EventType.EXTERNAL_TOOL_CALL]
    by_tool = {e.details["tool"]: e for e in entries}
    assert by_tool["echo"].outcome == "success" and by_tool["echo"].target_id == "external:mcp:test:echo"  # nosec B101
    note = by_tool["write_note"]
    assert note.details["category"] == "bad_arguments"  # nosec B101  api_key is not a declared field
    assert "sk-123" not in json.dumps(note.details)  # nosec B101
    assert audit.verify_chain()[0]  # nosec B101


async def test_a_call_is_a_stage_of_the_turn_record(toolbox, tmp_path):
    stages: list = []
    await toolbox.call("test", "echo", {"text": "hi"}, stages=stages)
    (stage,) = stages
    assert stage.name == "mcp_call" and stage.detail["status"] == "success" and stage.seconds > 0  # nosec B101
    store = TurnTraceStore(tmp_path / "turns.db")
    store.record(TurnRecord(
        turn_id="t1", started_at=time.time(), seconds=1.0, personality="guru", heard="echo hi",
        said="hi", intent="", action_status="success", outcome=None, model="gemma4", stages=stages,
    ))
    assert store.get("t1").stages[0].detail["tool"] == "echo"  # nosec B101


# ---- configuration and the command ----

def test_settings_are_read_and_secrets_refused():
    servers = parse_servers({"servers": {"files": {
        "command": "npx", "args": ["-y", "x"], "timeout": 10, "pass_env": ["FILES_TOKEN"],
        "tools": {"read": {"allow": True, "risk": "read_only"}, "write": {"allow": True}},
    }}}, {"FILES_TOKEN": "abc"})
    (files,) = servers
    assert files.env == {"FILES_TOKEN": "abc"} and files.timeout == 10  # nosec B101
    assert files.tools["read"].risk is ToolRisk.READ_ONLY and files.tools["write"].risk is ToolRisk.UNKNOWN  # nosec B101
    with pytest.raises(ValueError, match="looks like a secret"):
        parse_servers({"servers": {"files": {"command": "x", "env": {"API_TOKEN": "abc"}}}}, {})
    with pytest.raises(ValueError, match="server name"):
        parse_servers({"servers": {"Bad:Name": {"command": "x"}}}, {})
    with pytest.raises(ValueError, match="risk must be one of"):
        parse_servers({"servers": {"s": {"command": "x", "tools": {"t": {"risk": "fine"}}}}}, {})


def test_the_mcp_table_is_not_mistaken_for_an_unknown_setting(tmp_path):
    from Agent_Guru.utils.settings import apply_settings_file

    path = tmp_path / "settings.toml"
    path.write_text('OLLAMA_MODEL = "gemma4"\n[mcp.servers.files]\ncommand = "npx"\n', encoding="utf-8")
    report = apply_settings_file(path, environ={})
    assert report.applied == {"OLLAMA_MODEL": "gemma4"} and report.refused == {}  # nosec B101
    assert [s.name for s in mcp_tools.load_servers(path, {})] == ["files"]  # nosec B101


def test_the_command_cannot_call_a_denied_tool(audit, notes, capsys):
    box = build_toolbox([_server(notes=notes)], audit_logger=audit, actor="test")
    assert mcp_tools.run(["call", "test", "wipe"], box) == 1  # nosec B101
    assert "denied" in capsys.readouterr().out and notes.read_text(encoding="utf-8") == ""  # nosec B101


def test_the_command_lists_tools_and_calls_one(audit, notes, capsys):
    box = build_toolbox([_server(notes=notes)], audit_logger=audit, actor="test")
    assert mcp_tools.run(["list"], box) == 0  # nosec B101
    out = capsys.readouterr().out
    assert "echo  risk=read_only  available" in out and "wipe  risk=destructive  not available" in out  # nosec B101
    box = build_toolbox([_server(notes=notes)], audit_logger=audit, actor="test")
    assert mcp_tools.run(["call", "test", "echo", '{"text": "hi there"}'], box) == 0  # nosec B101
    assert "success: test/echo" in capsys.readouterr().out  # nosec B101


def test_without_mcp_configured_nothing_is_started_or_loaded():
    # The assistant itself does not load the MCP code at all in this
    # batch; voice turns reach tools with the tool loop.
    probe = (
        "import sys, main; "
        "print('LOADED', sorted(m for m in sys.modules if 'mcp' in m))"
    )
    out = subprocess.run(  # noqa: S603  # nosec B603
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=120, check=False,
        cwd=str(Path(__file__).resolve().parents[3]),
    ).stdout
    assert "LOADED []" in out, out[-500:]  # nosec B101
