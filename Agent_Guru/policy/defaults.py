"""The policies the assistant starts with.

The PolicyEngine starts empty and denies anything no policy allows, which is
the right default. But main.py created it and added nothing, so every voice
command reached the action stage denied: "send a message to John" and "set a
timer for 1 minute" both did nothing and the assistant said "Done.".

Each policy here allows one kind of action and nothing else. Anything not
listed stays denied.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from Agent_Guru.policy.models import Policy, PolicyEffect

if TYPE_CHECKING:
    from Agent_Guru.policy.engine import PolicyEngine

#: The principal and resource the integration orchestrator evaluates actions as.
PIPELINE_PRINCIPAL = "guru_pipeline"
PIPELINE_RESOURCE = "action"


def messaging_policy() -> Policy:
    """Allow sending a message or a reply, and nothing else.

    The action string is "communication:send_message:<contact>:<app>:<text>"
    (or ":reply:"), so the condition matches its prefix.
    """
    now = datetime.now(tz=UTC)
    return Policy(
        id="",
        version=1,
        name="allow-messaging",
        description="Allow the assistant to send a message or reply the user dictates.",
        effect=PolicyEffect.ALLOW,
        priority=10,
        principals=[PIPELINE_PRINCIPAL],
        resources=[PIPELINE_RESOURCE],
        actions=["*"],
        conditions={
            "operator": "OR",
            "conditions": [
                {"attribute": "action", "operator": "starts_with", "value": "communication:send_message:"},
                {"attribute": "action", "operator": "starts_with", "value": "communication:reply:"},
            ],
        },
        created_at=now,
        updated_at=now,
    )


def install_default_policies(engine: PolicyEngine) -> None:
    """Add the assistant's starting policies to *engine*."""
    engine.create_policy(messaging_policy())
