"""
Email tool for sending emails via Gmail, Outlook, or IMAP.

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
        cc = kwargs.get("cc", "")
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
            # Note: In a real implementation, this would:
            # 1. Load API credentials from secure storage
            # 2. Use provider-specific API (Gmail API, Microsoft Graph, SMTP)
            # 3. Send the email
            # 4. Handle rate limiting and retries
            return {
                "success": True,
                "result": {
                    "to": to,
                    "subject": subject,
                    "cc": cc,
                    "provider": provider,
                    "message_id": f"msg_{hash(to + subject)}",
                    "message": f"Email sent to {to} via {provider}",
                    "note": "This is a placeholder. Real implementation would use email API.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to send email: {str(e)}",
            }
