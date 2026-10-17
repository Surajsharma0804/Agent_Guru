"""Two tools in a row: the loop finishes a chain the model leaves half done, and leaves other turns alone.

"When does my Goa flight leave?" needs find_booking, then flight_status
with the flight number it gives. gemma4 never chained them in
scripts/tool_loop_eval.py: it called flight_status with "Goa" and gave
up, or found the booking and stopped. The model here is scripted; the
tool loop, the toolbox and the policy engine are real.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule, install_mcp_policies
from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
from Agent_Guru.llm.models import ToolCall
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies


class Travel:
    """find_booking gives the flight number; flight_status needs one."""

    def __init__(self):
        self.calls = []

    def tool_list(self):
        def tool(name, description, prop):
            return {"name": name, "description": description, "annotations": {"readOnlyHint": True},
                    "inputSchema": {"type": "object", "properties": {prop: {"type": "string"}}, "required": [prop],
                                    "additionalProperties": False}}

        return [tool("find_booking", "Find the owner's travel booking for a destination; gives the booking "
                     "reference and flight number.", "destination"),
                tool("flight_status", "Departure time and status of a flight, by flight number such as 6E 523.", "flight"),
                tool("get_weather", "Current weather for a city.", "city")]

    async def call(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if name == "find_booking":
            return "Booking ABC123: flight 6E 523 from Pune to Goa on 14 November.", False
        if name == "flight_status":
            ok = arguments.get("flight") == "6E 523"
            return ("6E 523 departs Pune at 7:40, on time." if ok else f"No flight {arguments.get('flight')}."), not ok
        return "Delhi: 31 C, haze.", False


class Model:
    def __init__(self, *script):
        self.script, self.requests = list(script), []

    async def supports_tool_calling(self, model):
        return True

    async def complete(self, request):
        self.requests.append(request)
        text, calls = self.script.pop(0) if self.script else ("Okay.", [])
        return SimpleNamespace(content=text, tool_calls=calls, finish_reason="stop")


def _call(name, **arguments):
    return ToolCall(name=f"travel__{name}", arguments=arguments)


def _said(model, index):
    return [m.content for m in model.requests[index].messages if m.role in ("tool", "system")]


@pytest.fixture
async def turn(tmp_path):
    made = []

    async def run(*script):
        travel = Travel()
        server = ServerConfig(name="travel", command="(in process)", timeout=10.0, local=travel,
                              tools={n: ToolRule(allow=True, risk=ToolRisk.READ_ONLY)
                                     for n in ("find_booking", "flight_status", "get_weather")})
        engine = PolicyEngine()
        install_default_policies(engine)
        install_mcp_policies(engine, [server])
        model = Model(*script)
        orch = IntegrationOrchestrator(
            speech_engine=None, vision_engine=None, llm_runtime=model, platform_controller=None,
            agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine, avatar=None,
            deployment=None, gpu_pool=None, mcp_servers=[server], reminder_store=tmp_path / "r.json",
        )

        async def no_web(*a, **k):
            return ""

        orch._fetch_web_context = no_web
        orch._start_tools()
        await orch._tools_starting
        made.append(orch)
        result = await orch.run_text_turn("When does my Goa flight leave?")
        return result, model, travel

    yield run
    for orch in made:
        orch.close_scheduler()
        await orch.close_tools()


async def test_a_failed_call_is_finished_through_the_tool_that_gives_its_input(turn):
    result, model, travel = await turn(
        ("", [_call("flight_status", flight="Goa")]),
        ("I couldn't find a flight called Goa.", []),
        ("", [_call("find_booking", destination="Goa")]),
        ("Your booking is flight 6E 523.", []),
        ("", [_call("flight_status", flight="6E 523")]),
        ("Your flight 6E 523 leaves Pune at 7:40.", []),
    )
    assert [c[0] for c in travel.calls] == ["flight_status", "find_booking", "flight_status"]  # nosec B101
    assert "7:40" in result.llm_response  # nosec B101
    assert any("travel__find_booking gives it" in s for s in _said(model, 1))  # nosec B101  the failure names the producer
    assert any("Call travel__find_booking now" in s for s in _said(model, 2))  # nosec B101
    assert any("Call travel__flight_status now" in s for s in _said(model, 4))  # nosec B101


async def test_an_offer_to_go_on_after_the_first_tool_is_turned_into_the_call(turn):
    result, model, travel = await turn(
        ("", [_call("find_booking", destination="Goa")]),
        ("Your booking is flight 6E 523. Wanna know the departure time?", []),
        ("", [_call("flight_status", flight="6E 523")]),
        ("It leaves at 7:40.", []),
    )
    assert [c[0] for c in travel.calls] == ["find_booking", "flight_status"] and "7:40" in result.llm_response  # nosec B101


async def test_a_turn_with_nothing_left_to_chain_is_answered_as_written(turn):
    result, model, travel = await turn(
        ("", [_call("get_weather", city="Delhi")]),
        ("It's 31 C in Delhi.", []),
    )
    assert len(model.requests) == 2 and result.llm_response.startswith("It's 31 C")  # nosec B101


async def test_the_loop_nudges_at_most_twice(turn):
    result, model, travel = await turn(
        ("", [_call("flight_status", flight="Goa")]),
        ("Sorry.", []),
        ("Still sorry.", []),
        ("Really, I can't.", []),
    )
    # The failure, two nudges, then the reply stands.
    assert len(model.requests) == 4 and result.llm_response.startswith("Really, I can't.")  # nosec B101
