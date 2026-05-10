"""Messaging tool for sending messages."""

from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


@tool(
    tool_id="messaging.send",
    name="Send Message",
    description="Send a text message to a contact",
    parameters=[
        ToolParameter(
            name="recipient",
            type=ToolParameterType.STRING,
            description="Recipient name or phone number",
            required=True,
        ),
        ToolParameter(
            name="message",
            type=ToolParameterType.STRING,
            description="Message content to send",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,  # Requires confirmation
    estimated_latency_ms=1000,
    capabilities=["messaging", "communication", "contacts"],
    examples=["Send a message to John", "Text Mom that I'll be late"],
)
class MessagingTool(Tool):
    """Tool for sending messages."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute message sending.

        Args:
            recipient: Message recipient
            message: Message content

        Returns:
            Execution result

        """
        recipient = kwargs["recipient"]
        message = kwargs["message"]

        # Validate recipient
        if not recipient or len(recipient.strip()) == 0:
            return {
                "success": False,
                "error": "Recipient cannot be empty",
            }

        # Validate message
        if not message or len(message.strip()) == 0:
            return {
                "success": False,
                "error": "Message cannot be empty",
            }

        if len(message) > 1000:
            return {
                "success": False,
                "error": "Message exceeds maximum length of 1000 characters",
            }

        # Mock message sending (in production, would use messaging API)
        return {
            "success": True,
            "result": {
                "recipient": recipient,
                "message": message,
                "message_id": f"msg_{hash(message) % 1000000}",
                "timestamp": "2024-01-01T12:00:00Z",
                "status": f"Message sent to {recipient}",
            },
        }
