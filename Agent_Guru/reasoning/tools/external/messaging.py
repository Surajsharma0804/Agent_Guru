"""Messaging tools for SMS, WhatsApp, Telegram, and Slack.

These tools are exposed to the LLM tool-calling agent (``agent_orchestrator``)
so that a "send a message to X saying Y" request can be executed directly by
the reasoning layer, with proper contact resolution and cross-platform
dispatch, instead of only being handled by the cruder rule-based fallback in
``integration/orchestrator.py``.

Real dispatch (fixed 2026-09-13):
    Every tool below used to be a pure placeholder: ``execute()`` did some
    input validation and then unconditionally returned
    ``{"success": True, ...}`` with a fabricated ``message_id`` built from
    ``hash(...)`` - no message was ever sent, opened, or delivered anywhere.
    Because the agent's tool-calling path is tried *before* the rule-based
    fallback (see ``IntegrationOrchestrator._execute_single_action``), this
    meant the single most common way these intents get handled told the user
    "WhatsApp sent to X" while doing nothing at all. That is exactly the kind
    of silent failure / fake completion this project explicitly forbids.

    All four tools now delegate to the already-correct, already-tested
    ``platform.controllers.messaging_controller.MessagingController`` (built
    in an earlier round to fix contact resolution), shared as a single
    lazily-started instance so its on-disk contacts cache and platform
    detection are not repeated per call. That controller:
      - resolves a spoken contact name against a local address book
        (falls through to the raw value when it already looks like a
        phone number / email / handle);
      - dispatches for real per platform: on Android/iOS via ``adb``/
        ``xcrun`` intents that open the target app with the message
        pre-filled; on desktop via the same URL-scheme pre-fill
        (``wa.me``/``t.me``/``mailto:``) opened in the real browser;
      - never auto-taps "send" on any platform - the message is prepared
        and the app is opened with it ready to go, and the user (or a
        vision-driven follow-up automation, if Agent Guru gains one) does
        the final confirmation tap. That is a deliberate safety choice
        (see messaging_controller.py's docstring) carried over here rather
        than re-litigated: it means "success" from these tools means
        "opened and ready", not "delivered", and the returned message says
        so explicitly rather than overclaiming.
      - SMS has no real desktop delivery path (no carrier gateway is
        wired up), so on desktop it honestly reports failure instead of
        pretending to send - matching MessagingController's own behavior.
      - Slack's URL scheme (``slack://open``) cannot target a specific
        channel or pre-fill text, so a Slack "send" only opens the app and
        says so - it does not claim the message reached the channel.
"""

from __future__ import annotations

import asyncio
from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool

# ---------------------------------------------------------------------------
# Shared MessagingController singleton
# ---------------------------------------------------------------------------
# Lazily started, reused across all four tools (and across calls) rather than
# constructed per-call: MessagingController reads a local contacts JSON file
# on each resolve_contact() call, and re-detecting the platform per call would
# be wasted work. Mirrors the _shared_browser_manager pattern already used in
# platform/features/web_search.py for the same reason.
_shared_messaging_controller: Any = None
_shared_messaging_controller_lock: asyncio.Lock | None = None


async def _get_shared_messaging_controller() -> Any:
    global _shared_messaging_controller, _shared_messaging_controller_lock
    if _shared_messaging_controller_lock is None:
        _shared_messaging_controller_lock = asyncio.Lock()
    async with _shared_messaging_controller_lock:
        if _shared_messaging_controller is None:
            from Agent_Guru.platform.controllers.messaging_controller import (
                MessagingController,
            )

            _shared_messaging_controller = MessagingController()
            await _shared_messaging_controller.initialize()
        return _shared_messaging_controller


async def _dispatch(app: str, contact: str, message: str, *, label: str) -> dict[str, Any]:
    """Shared execute() body for all four messaging tools.

    Args:
        app: MessagingController app name ("whatsapp", "telegram", "slack",
            "sms", "email").
        contact: Raw contact reference from the caller (name, phone, handle).
        message: Message text to send.
        label: Human-readable app name for the returned message ("WhatsApp",
            "Telegram", "Slack", "SMS").

    Returns:
        Tool-result dict with an honest, non-overclaiming status message.

    """
    if not contact or not contact.strip():
        return {"success": False, "error": "Contact cannot be empty"}
    if not message or not message.strip():
        return {"success": False, "error": "Message cannot be empty"}
    if len(message) > 2000:
        return {"success": False, "error": "Message too long (max 2000 characters)"}

    try:
        controller = await asyncio.wait_for(_get_shared_messaging_controller(), timeout=10.0)
        sent = await asyncio.wait_for(
            controller.send_message(app, contact, message),
            timeout=15.0,
        )
    except TimeoutError:
        return {
            "success": False,
            "error": f"{label} send timed out (contact resolution or app launch took too long)",
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"success": False, "error": f"{label} send failed: {exc}"}

    if not sent:
        return {
            "success": False,
            "error": (
                f"Could not send via {label}: the contact could not be resolved to a "
                f"known {label} identifier, {label} isn't reachable on this platform, "
                f"or the required automation tool (adb/xcrun) isn't available. "
                f"Save the contact first, or give a raw phone number/handle/email."
            ),
        }

    return {
        "success": True,
        "result": {
            "app": app,
            "message_length": len(message),
            "message": (
                f"{label} opened for {contact} with the message ready to send - "
                f"confirm the send in {label} to deliver it."
            ),
        },
    }


@tool(
    tool_id="messaging.send_sms",
    name="Send SMS",
    description="Send an SMS message",
    parameters=[
        ToolParameter(
            name="phone_number",
            type=ToolParameterType.STRING,
            description="Recipient phone number (with country code)",
            required=True,
        ),
        ToolParameter(
            name="message",
            type=ToolParameterType.STRING,
            description="Message text",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=1500,
    capabilities=["messaging", "sms", "communication", "send_message"],
    examples=[
        "Send SMS to +1234567890",
        "Text my friend",
        "Send a message to my phone",
    ],
)
class SendSMSTool(Tool):
    """Tool for sending SMS messages.

    Real delivery only on Android (via an adb SENDTO intent to the default
    SMS app, pre-filled and ready to send) - there is no carrier gateway
    wired up for desktop, so a desktop call honestly returns failure instead
    of a fabricated success, matching MessagingController's own behavior.
    """

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        phone_number = kwargs.get("phone_number", "")
        message = kwargs.get("message", "")
        return await _dispatch("sms", phone_number, message, label="SMS")


@tool(
    tool_id="messaging.send_whatsapp",
    name="Send WhatsApp",
    description="Send a WhatsApp message",
    parameters=[
        ToolParameter(
            name="phone_number",
            type=ToolParameterType.STRING,
            description="Recipient phone number (with country code)",
            required=True,
        ),
        ToolParameter(
            name="message",
            type=ToolParameterType.STRING,
            description="Message text",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=1500,
    capabilities=["messaging", "whatsapp", "communication", "send_message"],
    examples=[
        "Send WhatsApp to +1234567890",
        "WhatsApp my friend",
        "Send a WhatsApp message",
    ],
)
class SendWhatsAppTool(Tool):
    """Tool for sending WhatsApp messages (real dispatch via MessagingController)."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        phone_number = kwargs.get("phone_number", "")
        message = kwargs.get("message", "")
        return await _dispatch("whatsapp", phone_number, message, label="WhatsApp")


@tool(
    tool_id="messaging.send_telegram",
    name="Send Telegram",
    description="Send a Telegram message",
    parameters=[
        ToolParameter(
            name="chat_id",
            type=ToolParameterType.STRING,
            description="Telegram chat ID or username",
            required=True,
        ),
        ToolParameter(
            name="message",
            type=ToolParameterType.STRING,
            description="Message text",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=1000,
    capabilities=["messaging", "telegram", "communication", "send_message"],
    examples=[
        "Send Telegram to @username",
        "Message on Telegram",
        "Send a Telegram message",
    ],
)
class SendTelegramTool(Tool):
    """Tool for sending Telegram messages (real dispatch via MessagingController)."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        chat_id = kwargs.get("chat_id", "")
        message = kwargs.get("message", "")
        return await _dispatch("telegram", chat_id, message, label="Telegram")


@tool(
    tool_id="messaging.send_slack",
    name="Send Slack",
    description="Send a Slack message",
    parameters=[
        ToolParameter(
            name="channel",
            type=ToolParameterType.STRING,
            description="Slack channel name or ID",
            required=True,
        ),
        ToolParameter(
            name="message",
            type=ToolParameterType.STRING,
            description="Message text",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=1000,
    capabilities=["messaging", "slack", "communication", "send_message", "team_chat"],
    examples=[
        "Send Slack message to #general",
        "Post to Slack channel",
        "Message the team on Slack",
    ],
)
class SendSlackTool(Tool):
    """Tool for opening Slack toward a channel (real dispatch via MessagingController).

    Slack's URL scheme (``slack://open``) cannot target a specific channel or
    pre-fill message text, unlike the other three apps - so unlike them, this
    genuinely cannot prepare the message for the user. The result message
    says exactly that instead of claiming the text is ready to send.
    """

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        channel = kwargs.get("channel", "")
        message = kwargs.get("message", "")
        result = await _dispatch("slack", channel, message, label="Slack")
        if result.get("success"):
            result["result"]["message"] = (
                f"Slack opened - it can't be pre-addressed to {channel} or pre-filled "
                f"with your message (Slack's desktop URL scheme doesn't support that), "
                f"so navigate to {channel} and send it yourself."
            )
        return result
