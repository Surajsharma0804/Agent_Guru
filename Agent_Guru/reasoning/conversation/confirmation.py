"""Confirmation logic for sensitive actions.

This module implements:
- Sensitive action category definitions
- Confirmation requirement rules
- Confirmation message templates
- Batch confirmation for multi-step plans
- Confirmation parsing from user responses

Requirements: 19.2
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from Agent_Guru.reasoning.models.task import Task


class SensitiveActionCategory(Enum):
    """Categories of sensitive actions requiring confirmation."""

    MESSAGING = "messaging"  # Send messages, emails
    CALLING = "calling"  # Make phone calls
    SMART_HOME = "smart_home"  # Control smart home devices
    FILE_DELETION = "file_deletion"  # Delete files or data
    FINANCIAL = "financial"  # Financial transactions
    SYSTEM_MODIFICATION = "system_modification"  # System settings changes
    DATA_SHARING = "data_sharing"  # Share data externally
    CALENDAR = "calendar"  # Create/modify calendar events


@dataclass
class ConfirmationRequest:
    """A request for user confirmation."""

    action_description: str
    category: SensitiveActionCategory
    details: dict[str, Any]
    is_batch: bool
    batch_items: list[str]
    risk_level: str  # "low", "medium", "high"


@dataclass
class ConfirmationResponse:
    """Parsed confirmation response from user."""

    confirmed: bool
    confidence: float
    original_text: str


class ConfirmationRules:
    """Rules for determining when confirmation is required."""

    # Tool IDs that require confirmation
    SENSITIVE_TOOLS = {
        "send_message": SensitiveActionCategory.MESSAGING,
        "send_email": SensitiveActionCategory.MESSAGING,
        "make_call": SensitiveActionCategory.CALLING,
        "control_smart_home": SensitiveActionCategory.SMART_HOME,
        "delete_file": SensitiveActionCategory.FILE_DELETION,
        "modify_system_settings": SensitiveActionCategory.SYSTEM_MODIFICATION,
        "create_calendar_event": SensitiveActionCategory.CALENDAR,
        "share_data": SensitiveActionCategory.DATA_SHARING,
        "make_payment": SensitiveActionCategory.FINANCIAL,
    }

    # Keywords that indicate sensitive actions
    SENSITIVE_KEYWORDS = {
        "delete": SensitiveActionCategory.FILE_DELETION,
        "remove": SensitiveActionCategory.FILE_DELETION,
        "send": SensitiveActionCategory.MESSAGING,
        "call": SensitiveActionCategory.CALLING,
        "pay": SensitiveActionCategory.FINANCIAL,
        "transfer": SensitiveActionCategory.FINANCIAL,
        "share": SensitiveActionCategory.DATA_SHARING,
    }

    @staticmethod
    def requires_confirmation(
        task: Task,
        tool_id: str | None = None,
    ) -> tuple[bool, SensitiveActionCategory | None]:
        """Determine if a task requires confirmation.

        Args:
            task: The task to check
            tool_id: Optional specific tool ID to check

        Returns:
            Tuple of (requires_confirmation, category)

        """
        # Check task-level flag
        if task.requires_confirmation:
            # Try to determine category from task
            category = ConfirmationRules._infer_category_from_task(task)
            return True, category

        # Check tool-level sensitivity
        if tool_id and tool_id in ConfirmationRules.SENSITIVE_TOOLS:
            return True, ConfirmationRules.SENSITIVE_TOOLS[tool_id]

        # Check steps for sensitive tools
        for step in task.steps:
            if step.tool_id in ConfirmationRules.SENSITIVE_TOOLS:
                return True, ConfirmationRules.SENSITIVE_TOOLS[step.tool_id]

        # Check for sensitive keywords in goal
        for keyword, category in ConfirmationRules.SENSITIVE_KEYWORDS.items():
            if keyword in task.goal.lower():
                return True, category

        return False, None

    @staticmethod
    def _infer_category_from_task(task: Task) -> SensitiveActionCategory:
        """Infer sensitivity category from task.

        Args:
            task: The task

        Returns:
            Inferred category

        """
        # Check steps
        for step in task.steps:
            if step.tool_id in ConfirmationRules.SENSITIVE_TOOLS:
                return ConfirmationRules.SENSITIVE_TOOLS[step.tool_id]

        # Check keywords in goal
        for keyword, category in ConfirmationRules.SENSITIVE_KEYWORDS.items():
            if keyword in task.goal.lower():
                return category

        # Default to messaging (most common)
        return SensitiveActionCategory.MESSAGING

    @staticmethod
    def should_batch_confirm(task: Task) -> bool:
        """Determine if batch confirmation should be used.

        Args:
            task: The task

        Returns:
            True if batch confirmation should be used

        """
        # Use batch confirmation for multi-step tasks with multiple sensitive actions
        if len(task.steps) <= 1:
            return False

        # Count sensitive steps
        sensitive_count = sum(
            1 for step in task.steps if step.tool_id in ConfirmationRules.SENSITIVE_TOOLS
        )

        return sensitive_count >= 2  # noqa: PLR2004 - Small integer threshold


    @staticmethod
    def get_risk_level(category: SensitiveActionCategory, task: Task) -> str:
        """Determine risk level of the action.

        Args:
            category: Action category
            task: The task

        Returns:
            Risk level: "low", "medium", or "high"

        """
        # High risk categories
        if category in [
            SensitiveActionCategory.FINANCIAL,
            SensitiveActionCategory.FILE_DELETION,
            SensitiveActionCategory.SYSTEM_MODIFICATION,
        ]:
            return "high"

        # Medium risk categories
        if category in [
            SensitiveActionCategory.MESSAGING,
            SensitiveActionCategory.CALLING,
            SensitiveActionCategory.DATA_SHARING,
        ]:
            return "medium"

        # Low risk categories
        return "low"


class ConfirmationGenerator:
    """Generates confirmation requests."""

    # Templates by category
    TEMPLATES = {
        SensitiveActionCategory.MESSAGING: [
            'I\'ll send a message to {recipient} saying: "{message}". Should I proceed?',
            'Ready to send: "{message}" to {recipient}. Confirm?',
        ],
        SensitiveActionCategory.CALLING: [
            "I'll call {contact}. Should I proceed?",
            "Ready to call {contact}. Confirm?",
        ],
        SensitiveActionCategory.SMART_HOME: [
            "I'll {action} your {device}. Should I proceed?",
            "Ready to {action} {device}. Confirm?",
        ],
        SensitiveActionCategory.FILE_DELETION: [
            "I'll delete {file}. This cannot be undone. Should I proceed?",
            "Warning: This will permanently delete {file}. Confirm?",
        ],
        SensitiveActionCategory.FINANCIAL: [
            "I'll make a payment of {amount} to {recipient}. Should I proceed?",
            "Ready to transfer {amount} to {recipient}. Confirm?",
        ],
        SensitiveActionCategory.SYSTEM_MODIFICATION: [
            "I'll change {setting} to {value}. Should I proceed?",
            "Ready to modify {setting}. Confirm?",
        ],
        SensitiveActionCategory.DATA_SHARING: [
            "I'll share {data} with {recipient}. Should I proceed?",
            "Ready to share {data}. Confirm?",
        ],
        SensitiveActionCategory.CALENDAR: [
            "I'll create an event: {event} on {date}. Should I proceed?",
            "Ready to add {event} to your calendar. Confirm?",
        ],
    }

    # Batch confirmation template
    BATCH_TEMPLATE = "I'll perform these actions:\n{actions}\n\nShould I proceed with all of them?"

    def __init__(self) -> None:
        """Initialize confirmation generator."""
        self.rules = ConfirmationRules()

    def generate_confirmation(
        self,
        task: Task,
        tool_id: str | None = None,
    ) -> ConfirmationRequest | None:
        """Generate a confirmation request if needed.

        Args:
            task: The task to confirm
            tool_id: Optional specific tool ID

        Returns:
            ConfirmationRequest if confirmation needed, None otherwise

        """
        # Check if confirmation is required
        requires, category = self.rules.requires_confirmation(task, tool_id)

        if not requires or category is None:
            return None

        # Check if batch confirmation should be used
        is_batch = self.rules.should_batch_confirm(task)

        # Get risk level
        risk_level = self.rules.get_risk_level(category, task)

        # Generate confirmation message
        if is_batch:
            message, batch_items = self._generate_batch_confirmation(task)
        else:
            message = self._generate_single_confirmation(task, category)
            batch_items = []

        # Extract details
        details = self._extract_details(task, category)

        return ConfirmationRequest(
            action_description=message,
            category=category,
            details=details,
            is_batch=is_batch,
            batch_items=batch_items,
            risk_level=risk_level,
        )

    def _generate_single_confirmation(self, task: Task, category: SensitiveActionCategory) -> str:
        """Generate single action confirmation message.

        Args:
            task: The task
            category: Action category

        Returns:
            Confirmation message

        """
        # Get template for category
        templates = self.TEMPLATES.get(
            category,
            [
                "I'll {action}. Should I proceed?",
            ],
        )
        template = templates[0]

        # Extract parameters from task
        params = self._extract_parameters(task, category)

        # Format template
        try:
            return template.format(**params)
        except KeyError:
            # Fallback if parameters don't match
            return f"I'll {task.goal}. Should I proceed?"

    def _generate_batch_confirmation(self, task: Task) -> tuple[str, list[str]]:
        """Generate batch confirmation message.

        Args:
            task: The task with multiple steps

        Returns:
            Tuple of (message, list of action descriptions)

        """
        batch_items = []

        for i, step in enumerate(task.steps, 1):
            # Generate description for each step
            desc = f"{i}. {step.description}"
            batch_items.append(desc)

        # Format batch template
        actions_text = "\n".join(batch_items)
        message = self.BATCH_TEMPLATE.format(actions=actions_text)

        return message, batch_items

    def _extract_parameters(self, task: Task, category: SensitiveActionCategory) -> dict[str, Any]:
        """Extract parameters for template formatting.

        Args:
            task: The task
            category: Action category

        Returns:
            Dictionary of parameters

        """
        params = {}

        # Extract from task entities
        if category == SensitiveActionCategory.MESSAGING:
            params["recipient"] = task.entities.get("recipient", "unknown")
            params["message"] = task.entities.get("message", task.goal)

        elif category == SensitiveActionCategory.CALLING:
            params["contact"] = task.entities.get("contact", "unknown")

        elif category == SensitiveActionCategory.SMART_HOME:
            params["device"] = task.entities.get("device", "device")
            params["action"] = task.entities.get("action", "control")

        elif category == SensitiveActionCategory.FILE_DELETION:
            params["file"] = task.entities.get("file", "file")

        elif category == SensitiveActionCategory.FINANCIAL:
            params["amount"] = task.entities.get("amount", "unknown amount")
            params["recipient"] = task.entities.get("recipient", "unknown")

        elif category == SensitiveActionCategory.SYSTEM_MODIFICATION:
            params["setting"] = task.entities.get("setting", "setting")
            params["value"] = task.entities.get("value", "new value")

        elif category == SensitiveActionCategory.DATA_SHARING:
            params["data"] = task.entities.get("data", "data")
            params["recipient"] = task.entities.get("recipient", "unknown")

        elif category == SensitiveActionCategory.CALENDAR:
            params["event"] = task.entities.get("event", task.goal)
            params["date"] = task.entities.get("date", "unknown date")

        # Fallback
        params["action"] = task.goal

        return params

    def _extract_details(self, task: Task, category: SensitiveActionCategory) -> dict[str, Any]:
        """Extract detailed information about the action.

        Args:
            task: The task
            category: Action category

        Returns:
            Dictionary of details

        """
        return {
            "goal": task.goal,
            "category": category.value,
            "entities": task.entities,
            "step_count": len(task.steps),
        }


class ConfirmationParser:
    """Parses user confirmation responses."""

    # Positive confirmation patterns
    POSITIVE_PATTERNS = [
        "yes",
        "yeah",
        "yep",
        "sure",
        "ok",
        "okay",
        "confirm",
        "proceed",
        "go ahead",
        "do it",
        "affirmative",
        "correct",
        "right",
        "absolutely",
    ]

    # Negative confirmation patterns
    NEGATIVE_PATTERNS = [
        "no",
        "nope",
        "nah",
        "cancel",
        "stop",
        "don't",
        "negative",
        "abort",
        "never mind",
        "nevermind",
        "wait",
        "hold on",
    ]

    @staticmethod
    def parse_confirmation(user_response: str) -> ConfirmationResponse:
        """Parse user's confirmation response.

        Args:
            user_response: User's text response

        Returns:
            ConfirmationResponse with parsed result

        """
        # Normalize response
        normalized = user_response.lower().strip()

        # Check for positive confirmation
        for pattern in ConfirmationParser.POSITIVE_PATTERNS:
            if pattern in normalized:
                return ConfirmationResponse(
                    confirmed=True,
                    confidence=0.9,
                    original_text=user_response,
                )

        # Check for negative confirmation
        for pattern in ConfirmationParser.NEGATIVE_PATTERNS:
            if pattern in normalized:
                return ConfirmationResponse(
                    confirmed=False,
                    confidence=0.9,
                    original_text=user_response,
                )

        # Ambiguous response
        return ConfirmationResponse(confirmed=False, confidence=0.3, original_text=user_response)
