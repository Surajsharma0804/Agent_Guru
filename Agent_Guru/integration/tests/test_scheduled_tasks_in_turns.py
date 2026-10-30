"""Scheduling from a conversation goes through the owner's yes, and the policy decides again at run time.

The model, the scheduler's clock and the owner's words are scripted; the
tool loop, MCPToolbox, the policy engine and the MCP test server
(mcp_test_server.py) are real.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule, install_mcp_policies
from Agent_Guru.integration.orchestrator import ActionStatus, IntegrationOrchestrator
from Agent_Guru.integration.task_tools import TaskTools, tasks_server
from Agent_Guru.llm.models import ToolCall
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies

SERVER = str(Path(__file__).with_name("mcp_test_server.py"))


class Model:
    def __init__(self, *script):
        self.script, self.requests = list(script), []

    async def supports_tool_calling(self, model):
        return True

    async def complete(self, request):
        self.requests.append(request)
        text, calls = self.script.pop(0) if self.script else ("Okay.", [])
        return SimpleNamespace(content=text, tool_calls=calls, finish_reason="stop")


@pytest.fixture
async def setup(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("", encoding="utf-8")
    test_server = ServerConfig(
        name="test", command=sys.executable, args=[SERVER], env={"MCP_TEST_NOTES": str(notes)}, timeout=5.0,
        start_timeout=15.0, tools={"echo": ToolRule(allow=True, risk=ToolRisk.READ_ONLY),
                                   "write_note": ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE)},
    )
    task_tools = TaskTools()
    tasks = tasks_server()
    tasks.local = task_tools
    engine = PolicyEngine()
    install_default_policies(engine)
    install_mcp_policies(engine, [test_server, tasks])
    made = []

    async def build(*script):
        model = Model(*script)
        orch = IntegrationOrchestrator(
            speech_engine=None, vision_engine=None, llm_runtime=model, platform_controller=None,
            agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
            avatar=None, deployment=None, gpu_pool=None, mcp_servers=[test_server, tasks],
            reminder_store=tmp_path / "reminders.json",
        )

        async def no_web(*a, **k):
            return ""

        orch._fetch_web_context = no_web
        task_tools.bind(orch)
        orch._start_tools()
        await orch._tools_starting
        said = []
        orch._reminders().set_speak_callback(said.append)
        made.append(orch)
        return orch, model, said

    yield SimpleNamespace(build=build, notes=notes, engine=engine, store=tmp_path / "reminders.json")
    for orch in made:
        orch.close_scheduler()
        await orch.close_tools()


def _schedule(**arguments):
    return ToolCall(name="tasks__schedule_action", arguments={
        "description": "save the milk note", "tool": "test__write_note", "arguments": {"note": "buy milk"},
        "in_minutes": 60, **arguments})


async def test_scheduling_an_action_waits_for_the_owners_yes(setup):
    orch, _, _ = await setup.build(("", [_schedule()]), ("Scheduled it.", []))
    asked = await orch.run_text_turn("in an hour, note that I need milk")
    # The exact action is read back in words, from the arguments that will run.
    assert asked.awaiting_reply and "Should I run write note (note buy milk) in 60 minutes?" in asked.llm_response  # nosec B101
    assert orch._reminders().list_reminders() == []  # nosec B101  nothing scheduled yet
    done = await orch.run_text_turn("yes")
    (task,) = orch._reminders().list_reminders()
    assert task.kind == "action" and task.approval["by"] == "owner" and task.arguments == {"note": "buy milk"}  # nosec B101
    # The scheduler read back its own change, so it is not "unconfirmed".
    assert done.action_status is ActionStatus.SUCCESS  # nosec B101
    assert setup.notes.read_text(encoding="utf-8") == ""  # nosec B101  scheduled, not run


async def test_anything_but_yes_schedules_nothing(setup):
    orch, _, _ = await setup.build(("", [_schedule()]))
    await orch.run_text_turn("in an hour, note that I need milk")
    result = await orch.run_text_turn("no, wait")
    assert result.action_status is ActionStatus.CANCELLED and orch._reminders().list_reminders() == []  # nosec B101


async def test_a_scheduled_action_runs_through_the_toolbox_when_due(setup):
    orch, _, said = await setup.build(("", [_schedule()]), ("Scheduled.", []))
    await orch.run_text_turn("in an hour, note that I need milk")
    await orch.run_text_turn("yes")
    (task,) = orch._reminders().list_reminders()
    status = await orch._reminders()._run(task)
    assert setup.notes.read_text(encoding="utf-8") == "buy milk\n"  # nosec B101
    # The test server only says "saved": the change is not confirmed.
    assert status == "unverified" and "couldn't confirm it worked" in said[-1]  # nosec B101


async def test_a_policy_withdrawn_after_approval_stops_the_action(setup):
    orch, _, said = await setup.build(("", [_schedule()]), ("Scheduled.", []))
    await orch.run_text_turn("in an hour, note that I need milk")
    await orch.run_text_turn("yes")
    (task,) = orch._reminders().list_reminders()
    for policy in setup.engine.find_policies():
        if policy.name == "allow-mcp-test-write_note":
            setup.engine.delete_policy(policy.id)
    status = await orch._reminders()._run(task)
    assert status == "denied" and setup.notes.read_text(encoding="utf-8") == ""  # nosec B101
    assert said[-1] == "I wasn't allowed to run your scheduled task, save the milk note."  # nosec B101


async def test_a_check_may_only_use_a_read_only_tool(setup):
    call = ToolCall(name="tasks__schedule_check", arguments={
        "description": "keep writing", "tool": "test__write_note", "arguments": {"note": "x"}, "every_minutes": 5})
    orch, model, _ = await setup.build(("", [call]), ("Can't.", []))
    result = await orch.run_text_turn("could you keep an eye on this for me")
    # Refused before the owner is asked: no yes is wanted for a call that cannot run.
    assert not result.awaiting_reply and orch._reminders().list_reminders() == []  # nosec B101
    assert "a check may only use a read-only tool" in model.requests[1].messages[-1].content  # nosec B101


async def test_a_task_cannot_target_a_tool_that_cannot_run_or_bad_arguments(setup):
    # After each refusal the model gets one step to correct the call; here
    # it declines both times.
    orch, model, _ = await setup.build(("", [_schedule(tool="test__wipe")]), ("No.", []), ("I can't do that.", []),
                                       ("", [_schedule(arguments={"nope": 1})]), ("No.", []), ("I can't do that.", []))
    first = await orch.run_text_turn("in an hour, wipe everything")
    assert not first.awaiting_reply and "not a tool that can run now" in model.requests[1].messages[-1].content  # nosec B101
    second = await orch.run_text_turn("in an hour, note that I need milk")
    assert not second.awaiting_reply and any(  # nosec B101
        "do not fit the tool" in m.content for r in model.requests[3:] for m in r.messages)
    assert orch._reminders().list_reminders() == []  # nosec B101


async def test_a_call_with_bad_arguments_is_not_read_back_for_a_yes(setup):
    # gemma4 called schedule_check with only {"arguments": {}, "contains_text": ""};
    # the owner was asked to approve a call that could only fail.
    bad = ToolCall(name="tasks__schedule_check", arguments={"arguments": {}, "contains_text": ""})
    orch, model, _ = await setup.build(("", [bad]), ("Which city, and how often?", []))
    result = await orch.run_text_turn("could you keep an eye on this for me")
    assert not result.awaiting_reply and result.llm_response == "Which city, and how often?"  # nosec B101
    assert "every_minutes is required" in model.requests[1].messages[-1].content  # nosec B101


async def test_a_check_repeats_the_lookup_the_model_just_made(setup):
    # gemma4 could not fill a nested arguments object for the check, but
    # made the lookup itself without trouble.
    orch, _, _ = await setup.build(
        ("", [ToolCall(name="test__echo", arguments={"text": "31 C"})]),
        ("", [ToolCall(name="tasks__schedule_check", arguments={"every_minutes": 60, "notify_when": "changed"})]),
        ("Done, I'll keep checking.", []),
    )
    asked = await orch.run_text_turn("could you keep an eye on this for me")
    assert asked.awaiting_reply  # nosec B101
    await orch.run_text_turn("yes")
    (task,) = orch._reminders().list_reminders()
    assert (task.kind, task.tool, task.arguments, task.every_s, task.notify_when) == (  # nosec B101
        "check", "echo", {"text": "31 C"}, 3600, "changed")


async def test_a_named_tool_without_its_arguments_gets_them_from_one_focused_step(setup):
    # gemma4 named the tool to repeat but left out its arguments in 6 of 6
    # runs; offered only that tool, it filled them in.
    bad = ToolCall(name="tasks__schedule_check", arguments={"tool": "test__echo", "every_minutes": 60})
    orch, model, _ = await setup.build(("", [bad]), ("", [ToolCall(name="test__echo", arguments={"text": "hi"})]))
    asked = await orch.run_text_turn("could you keep an eye on this for me")
    assert asked.awaiting_reply and "check echo (text hi) every hour" in asked.llm_response  # nosec B101  read back with what was filled
    assert [f.name for f in model.requests[1].functions] == ["test__echo"]  # nosec B101  only the target offered
    await orch.run_text_turn("yes")
    assert [t.arguments for t in orch._reminders().list_reminders()] == [{"text": "hi"}]  # nosec B101
    assert setup.notes.read_text(encoding="utf-8") == ""  # nosec B101


async def test_a_refused_call_gets_one_chance_to_be_corrected(setup):
    too_often = ToolCall(name="tasks__schedule_check", arguments={"tool": "test__echo", "text": "hi", "every_minutes": 1})
    good = ToolCall(name="tasks__schedule_check", arguments={"tool": "test__echo", "text": "hi", "every_minutes": 60})
    orch, model, _ = await setup.build(("", [too_often]), ("Okay.", []), ("", [good]), ("Done.", []))
    asked = await orch.run_text_turn("could you keep an eye on this for me")
    assert asked.awaiting_reply and any(  # nosec B101
        m.role == "system" and "refused before it ran" in m.content for r in model.requests for m in r.messages)
    await orch.run_text_turn("yes")
    assert [t.every_s for t in orch._reminders().list_reminders()] == [3600]  # nosec B101


async def test_a_check_with_nothing_to_repeat_says_what_to_do(setup):
    call = ToolCall(name="tasks__schedule_check", arguments={"every_minutes": 60})
    orch, model, _ = await setup.build(("", [call]), ("Which city?", []))
    result = await orch.run_text_turn("could you keep an eye on this for me")
    assert not result.awaiting_reply and orch._reminders().list_reminders() == []  # nosec B101
    assert "name the tool to repeat" in model.requests[1].messages[-1].content  # nosec B101


async def test_a_check_can_name_the_tool_with_its_arguments_as_flat_fields(setup):
    call = ToolCall(name="tasks__schedule_check", arguments={"tool": "test__echo", "text": "31 C", "every_minutes": 60})
    orch, _, _ = await setup.build(("", [call]), ("Done.", []))
    asked = await orch.run_text_turn("could you keep an eye on this for me")
    assert asked.awaiting_reply  # nosec B101
    await orch.run_text_turn("yes")
    (task,) = orch._reminders().list_reminders()
    assert (task.tool, task.arguments) == ("echo", {"text": "31 C"})  # nosec B101


async def test_listing_tasks_needs_no_yes_and_cancelling_does(setup):
    orch, model, _ = await setup.build(
        ("", [_schedule()]), ("Scheduled.", []),
        ("", [ToolCall(name="tasks__list_tasks", arguments={})]), ("Here they are.", []),
    )
    await orch.run_text_turn("in an hour, note that I need milk")
    await orch.run_text_turn("yes")
    listed = await orch.run_text_turn("what tasks do I have")
    assert not listed.awaiting_reply and "test__write_note" in model.requests[-1].messages[-1].content  # nosec B101
    (task,) = orch._reminders().list_reminders()
    model.script = [("", [ToolCall(name="tasks__cancel_task", arguments={"task_id": task.reminder_id})]), ("Gone.", [])]
    await orch.run_text_turn("cancel that")
    assert orch._reminders().list_reminders() != []  # nosec B101  not until the owner says yes
    await orch.run_text_turn("yes")
    assert orch._reminders().list_reminders() == []  # nosec B101
    assert task.reminder_id not in json.loads(setup.store.read_text(encoding="utf-8"))  # nosec B101


@pytest.mark.parametrize("arguments, said", [
    # gemma4's own call for "keep an eye on the weather in Delhi every hour", measured live: an empty
    # arguments object, the city as a further field, and a contains_text the check will not use.
    ({"arguments": {}, "contains_text": "Delhi", "every_minutes": 60, "notify_when": "always",
      "tool": "eval__get_weather", "city": "Delhi"},
     "check get weather (city Delhi) every hour and tell you what it finds each time"),
    ({"tool": "eval__get_weather", "arguments": {"city": "Pune"}, "every_minutes": 120, "notify_when": "contains",
      "contains_text": "rain"}, "check get weather (city Pune) every 2 hours and tell you when it mentions rain"),
    ({"tool": "eval__get_weather", "city": "London", "every_minutes": 30, "notify_when": "changed"},
     "check get weather (city London) every 30 minutes and tell you when it changes"),
])
def test_a_scheduled_check_is_asked_about_in_words(arguments, said):
    """The question used to be the raw call: "Should I run schedule_check on tasks with {"arguments": {}, ...}?"."""
    assert TaskTools().describe("schedule_check", arguments) == said  # nosec B101


async def test_a_check_that_could_only_fail_is_refused_before_the_owner_is_asked(setup):
    # Live: "Should I check web research ... every hour?", the owner said yes,
    # and only then was the call refused for a contains rule with no words.
    bad = ToolCall(name="tasks__schedule_check", arguments={
        "tool": "test__echo", "text": "Delhi weather", "every_minutes": 60, "notify_when": "contains"})
    orch, model, _ = await setup.build(("", [bad]), ("Which words should I look for?", []))
    result = await orch.run_text_turn("tell me every hour if it rains in Delhi")
    assert not result.awaiting_reply and orch._reminders().list_reminders() == []  # nosec B101
    assert "contains needs contains_text" in model.requests[1].messages[-1].content  # nosec B101


async def test_every_problem_with_a_check_is_reported_at_once(setup):
    # Live: guru__weather without its place and notify_when contains without
    # words. Told only about the place, the one repair fixed that and was then
    # refused for the words, so the watch was never scheduled.
    bad = ToolCall(name="tasks__schedule_check", arguments={
        "tool": "test__echo", "text": 5, "every_minutes": 60, "notify_when": "contains"})
    orch, model, _ = await setup.build(("", [bad]), ("Which words should I look for?", []))
    await orch.run_text_turn("tell me every hour if it rains in Delhi")
    told = model.requests[1].messages[-1].content
    assert "do not fit the tool" in told and "contains needs contains_text" in told  # nosec B101
