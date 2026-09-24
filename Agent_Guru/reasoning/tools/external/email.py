"""Email tool for sending emails via Gmail, Outlook, or IMAP.

Supports multiple email providers with API key management.
"""

from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


@tool(
    tool_id="email.send",
    name="Send Email",
    description="Send an email via Gmail, Outlook, or IMAP",
    parameters=[
        ToolParameter(
            name="to",
            type=ToolParameterType.STRING,
            description="Recipient email address",
            required=True,
        ),
        ToolParameter(
            name="subject",
            type=ToolParameterType.STRING,
            description="Email subject",
            required=True,
        ),
        ToolParameter(
            name="body",
            type=ToolParameterType.STRING,
            description="Email body",
            required=True,
        ),
        ToolParameter(
            name="cc",
            type=ToolParameterType.STRING,
            description="CC recipients (comma-separated)",
            required=False,
            default="",
        ),
        ToolParameter(
            name="provider",
            type=ToolParameterType.STRING,
            description="Email provider (gmail, outlook, imap)",
            required=False,
            default="gmail",
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=2000,
    capabilities=["email", "messaging", "communication", "send_email"],
    examples=[
        "Send an email to john@example.com",
        "Email the report to my manager",
        "Send meeting notes to the team",
    ],
)
class SendEmailTool(Tool):
    """Tool for sending emails."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute email sending.

        Args:
            to: Recipient email
            subject: Email subject
            body: Email body
            cc: CC recipients
            provider: Email provider

        Returns:
            Execution result

        """
        to = kwargs["to"]
        subject = kwargs["subject"]
        body = kwargs["body"]
        # cc is accepted and documented above but unread: there is no email
        # backend in this build to pass it to (see the note below).
        provider = kwargs.get("provider", "gmail").lower()

        # Validate email
        if not to or "@" not in to:
            return {
                "success": False,
                "error": "Invalid recipient email address",
            }

        # Validate subject
        if not subject or not subject.strip():
            return {
                "success": False,
                "error": "Email subject cannot be empty",
            }

        # Validate body
        if not body or not body.strip():
            return {
                "success": False,
                "error": "Email body cannot be empty",
            }

        # Validate provider
        valid_providers = ["gmail", "outlook", "imap"]
        if provider not in valid_providers:
            return {
                "success": False,
                "error": f"Invalid provider. Must be one of: {', '.join(valid_providers)}",
            }

        try:
            # BUG FIX (Round 21): this used to unconditionally claim
            # "success": True with a fabricated message_id (built from
            # hash(to + subject)) and a message reading "Email sent to
            # {to}" -- no email was ever sent. This is the exact same class
            # of bug Round 4 found and fixed in the sibling file
            # reasoning/tools/external/messaging.py (SendSMSTool etc.):
            # a tool on the LLM agent's direct tool-calling path silently
            # lying about having completed a real-world action, which is
            # strictly worse than an error, since neither the agent nor the
            # user has any way to know the email never left the building.
            # Unlike messaging.py, there is no existing, already-built
            # controller anywhere in this codebase to delegate to here
            # (platform/controllers/ has a messaging_controller.py but no
            # email equivalent, and no SMTP/OAuth credential storage
            # exists) -- so honestly failing is the correct fix, not
            # fabricating a fake integration this round didn't build or
            # test.
            return {
                "success": False,
                "error": (
                    f"Email sending is not available: no email provider "
                    f"({provider}) is configured in this build of Agent Guru."
                ),
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to send email: {e!s}",
            }
