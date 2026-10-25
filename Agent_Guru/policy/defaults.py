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


#: Device actions a spoken command may take without asking: each is undone by
#: another command, or changes nothing but what is on the screen or the
#: speaker. Only messaging used to be allowed, so "open notepad", "set volume
#: to 30", "set a timer for 1 minute" and "good morning" all reached the
#: action stage denied and were answered "it isn't allowed in my current
#: settings". close_app is here because closing asks the application's
#: windows to close and never forces it: an editor with unsaved work asks the
#: owner itself.
#:
#: Left out on purpose: type_text and dictate (keystrokes into whatever window
#: is in front), clipboard (reads it aloud), settings (turns Wi-Fi or
#: Bluetooth off, and reports success without a controller to do it),
#: shutdown, restart, power and uninstall_app.
DEVICE_ACTIONS = (
    "open_app", "close_app", "switch_app", "window",
    "volume", "brightness", "play_pause", "next_track", "previous_track", "stop_media",
    "open_url", "web_search", "screenshot", "screen_read",
    "reminder", "briefing", "system_status",
)


def device_control_policy() -> Policy:
    """Allow the reversible device actions in DEVICE_ACTIONS, and nothing else.

    The action string is "system_control:<action>[:<param>[:<level>]]". The
    match is whole (the "matches" operator is a fullmatch), so a longer
    action name that merely starts with an allowed one is not allowed, and
    "|" cannot appear: a multi-step intent is checked one step at a time.
    """
    now = datetime.now(tz=UTC)
    pattern = r"system_control:(?:" + "|".join(DEVICE_ACTIONS) + r")(?::[^|]*)?"
    return Policy(
        id="",
        version=1,
        name="allow-device-control",
        description="Allow the assistant to open and close apps, set volume and brightness, "
                    "control media, open pages, take screenshots, set reminders and give briefings.",
        effect=PolicyEffect.ALLOW,
        priority=10,
        principals=[PIPELINE_PRINCIPAL],
        resources=[PIPELINE_RESOURCE],
        actions=["*"],
        conditions={"attribute": "action", "operator": "matches", "value": "(?s)" + pattern},
        created_at=now,
        updated_at=now,
    )


def install_default_policies(engine: PolicyEngine) -> None:
    """Add the assistant's starting policies to *engine*."""
    engine.create_policy(messaging_policy())
    engine.create_policy(device_control_policy())
