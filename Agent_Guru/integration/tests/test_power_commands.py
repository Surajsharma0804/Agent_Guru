"""Power commands are understood as power commands, and the starting policy refuses them.

"shut down the computer" used to match the close-app pattern first and arrive as close_app with
the app name "shut down the", an action the starting policy allows, so the assistant would have
tried to close an application by that name. Bare "shutdown", "restart", "reboot" and "log out"
matched nothing and went to the model as conversation. The controller here records every call.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies


class Controller:
    def __init__(self):
        self.calls = []

    def app_instances(self, name):
        return {1: True}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def call(*args, **kwargs):
            self.calls.append((name, args))
            return {"success": True}

        return call


def _orchestrator(ctrl=None, policy=None):
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=ctrl,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=policy, avatar=None,
        deployment=None, gpu_pool=None, reminder_store=Path(tempfile.mkdtemp()) / "r.json",
    )
    orch._APP_OPEN_VERIFY_S = 0.0
    return orch


POWER = [
    ("shut down the computer", "shutdown"), ("shutdown", "shutdown"), ("shut down", "shutdown"),
    ("shut down my pc", "shutdown"), ("turn off the pc", "shutdown"), ("power off", "shutdown"),
    ("can you shut down the laptop", "shutdown"),
    ("restart the computer", "restart"), ("restart", "restart"), ("reboot", "restart"),
    ("please restart the computer now", "restart"),
    ("log out", "logout"), ("log off", "logout"), ("sign out of windows", "logout"),
    ("sleep", "sleep"), ("put the computer to sleep", "sleep"), ("hibernate", "sleep"), ("hibernate the pc", "sleep"),
]


@pytest.mark.parametrize("said, action", POWER)
async def test_each_phrasing_is_its_power_intent(said, action):
    orch = _orchestrator()
    try:
        assert await orch._stage_intent(said) == f"system_control:{action}"  # nosec B101
    finally:
        orch.close_scheduler()


@pytest.mark.parametrize("said", ["I could not sleep last night", "turn off the lights", "how do I restart my router"])
async def test_a_sentence_that_mentions_power_is_not_a_power_command(said):
    orch = _orchestrator()
    try:
        intent = await orch._stage_intent(said)
        assert intent.split(":")[1:2] not in (["shutdown"], ["restart"], ["logout"], ["sleep"])  # nosec B101
    finally:
        orch.close_scheduler()


@pytest.mark.parametrize("said, action", POWER)
async def test_the_starting_policy_refuses_the_power_intent_itself(said, action):
    engine = PolicyEngine()
    install_default_policies(engine)
    ctrl = Controller()
    orch = _orchestrator(ctrl, engine)
    try:
        result = await orch.run_text_turn(said)
        # Refused as what it is, a power command: not as a close_app that happened to be refused.
        assert result.intent == f"system_control:{action}" and result.policy_allowed is False  # nosec B101
        assert ctrl.calls == []  # nosec B101
    finally:
        orch.close_scheduler()


@pytest.mark.parametrize("said, app", [
    ("close the shut down dialog", "shut down dialog"), ("close the restart prompt", "restart prompt"),
    ("shut down notepad", "notepad"),
])
async def test_closing_a_window_named_like_a_power_word_still_closes_it(said, app):
    engine = PolicyEngine()
    install_default_policies(engine)
    ctrl = Controller()
    orch = _orchestrator(ctrl, engine)
    try:
        result = await orch.run_text_turn(said)
        assert result.intent == f"system_control:close_app:{app}" and result.policy_allowed  # nosec B101
    finally:
        orch.close_scheduler()
