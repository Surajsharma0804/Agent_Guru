"""Clarification rules and templates for conversation strategy.

This module implements:
- Rules for when to ask clarifications
- Clarification question templates
- Option generation for multiple interpretations
- Open-ended question templates

Requirements: 19.1, 19.6
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.task import Task


class ClarificationTrigger(Enum):
    """Reasons for requesting clarification."""

    LOW_CONFIDENCE = "low_confidence"  # Confidence < 0.7
    MISSING_ENTITIES = "missing_entities"  # Required entities not extracted
    AMBIGUOUS_INTENT = "ambiguous_intent"  # Multiple possible interpretations
    INCOMPLETE_REQUEST = "incomplete_request"  # Request lacks necessary details
    CONFLICTING_INFO = "conflicting_info"  # Contradictory information


@dataclass
class ClarificationOption:
    """A possible interpretation for clarification."""

    description: str
    intent_type: str
    entities: dict[str, Any]
    confidence: float


@dataclass
class ClarificationRequest:
    """A request for user clarification."""

    trigger: ClarificationTrigger
    question: str
    options: list[ClarificationOption]
    is_open_ended: bool
    context: dict[str, Any]


class ClarificationRules:
    """Rules for determining when to ask for clarification."""

    # Confidence threshold below which clarification is needed
    CONFIDENCE_THRESHOLD = 0.7

    # Minimum number of required entities
    MIN_REQUIRED_ENTITIES = 1

    @staticmethod
    def should_clarify(
        intent: Intent | None,
        task: Task | None,
        confidence: float,
    ) -> tuple[bool, ClarificationTrigger | None]:
        """Determine if clarification is needed.

        Args:
            intent: Detected intent (may be None)
            task: Generated task (may be None)
            confidence: Overall confidence score

        Returns:
            Tuple of (should_clarify, trigger_reason)

        """
        # Low confidence
        if confidence < ClarificationRules.CONFIDENCE_THRESHOLD:
            return True, ClarificationTrigger.LOW_CONFIDENCE

        # No intent detected
        if intent is None:
            return True, ClarificationTrigger.AMBIGUOUS_INTENT

        # Missing required entities
        if intent and not intent.entities:
            return True, ClarificationTrigger.MISSING_ENTITIES

        # Task has low confidence
        if task and task.confidence < ClarificationRules.CONFIDENCE_THRESHOLD:
            return True, ClarificationTrigger.LOW_CONFIDENCE

        # Task requires confirmation (might need clarification first)
        if task and task.requires_confirmation and confidence < 0.85:  # noqa: PLR2004 - Threshold value

            return True, ClarificationTrigger.INCOMPLETE_REQUEST

        return False, None

    @staticmethod
    def should_offer_options(
        trigger: ClarificationTrigger,
        alternative_intents: list[tuple[str, float]],
    ) -> bool:
        """Determine if we should offer multiple choice options.

        Args:
            trigger: The clarification trigger
            alternative_intents: List of (intent_type, confidence) alternatives

        Returns:
            True if options should be offered

        """
        # Offer options for ambiguous intents with clear alternatives
        if trigger == ClarificationTrigger.AMBIGUOUS_INTENT:
            return len(alternative_intents) >= 2  # noqa: PLR2004 - Small integer threshold


        # Offer options for low confidence with alternatives
        if trigger == ClarificationTrigger.LOW_CONFIDENCE:
            return len(alternative_intents) >= 2 and alternative_intents[0][1] > 0.5  # noqa: PLR2004 - Small integer threshold


        return False


class ClarificationTemplate:
    """Templates for clarification questions."""

    # Templates for low confidence
    LOW_CONFIDENCE_TEMPLATES = [
        "I'm not sure I understood correctly. {question}",
        "Could you clarify what you mean? {question}",
        "I want to make sure I understand. {question}",
    ]

    # Templates for missing entities
    MISSING_ENTITIES_TEMPLATES = [
        "I need a bit more information. {question}",
        "Could you tell me {missing_entity}?",
        "What {missing_entity} would you like?",
    ]

    # Templates for ambiguous intent
    AMBIGUOUS_INTENT_TEMPLATES = [
        "Did you want to {option1} or {option2}?",
        "I can help you {option1}, {option2}, or {option3}. Which would you like?",
        "Are you asking me to {option1}?",
    ]

    # Templates for incomplete requests
    INCOMPLETE_REQUEST_TEMPLATES = [
        "I can help with that, but I need to know {missing_info}.",
        "To do that, I'll need {missing_info}. Can you provide that?",
        "Could you specify {missing_info}?",
    ]

    # Open-ended templates
    OPEN_ENDED_TEMPLATES = [
        "Could you rephrase that?",
        "I didn't quite catch that. Could you say it differently?",
        "I'm not sure what you mean. Could you explain more?",
    ]

    @staticmethod
    def get_template(trigger: ClarificationTrigger, has_options: bool) -> str:
        """Get appropriate template for the trigger.

        Args:
            trigger: The clarification trigger
            has_options: Whether multiple choice options are available

        Returns:
            Template string

        """
        if trigger == ClarificationTrigger.LOW_CONFIDENCE:
            return ClarificationTemplate.LOW_CONFIDENCE_TEMPLATES[0]
        if trigger == ClarificationTrigger.MISSING_ENTITIES:
            return ClarificationTemplate.MISSING_ENTITIES_TEMPLATES[0]
        if trigger == ClarificationTrigger.AMBIGUOUS_INTENT and has_options:
            return ClarificationTemplate.AMBIGUOUS_INTENT_TEMPLATES[0]
        if trigger == ClarificationTrigger.INCOMPLETE_REQUEST:
            return ClarificationTemplate.INCOMPLETE_REQUEST_TEMPLATES[0]
        return ClarificationTemplate.OPEN_ENDED_TEMPLATES[0]


class ClarificationGenerator:
    """Generates clarification requests."""

    def __init__(self) -> None:
        """Initialize clarification generator."""
        self.rules = ClarificationRules()
        self.templates = ClarificationTemplate()

    def generate_clarification(
        self,
        intent: Intent | None,
        task: Task | None,
        confidence: float,
        alternative_intents: list[tuple[str, float]] | None = None,
    ) -> ClarificationRequest | None:
        """Generate a clarification request if needed.

        Args:
            intent: Detected intent
            task: Generated task
            confidence: Overall confidence score
            alternative_intents: Alternative intent interpretations

        Returns:
            ClarificationRequest if clarification needed, None otherwise

        """
        # Check if clarification is needed
        should_clarify, trigger = self.rules.should_clarify(intent, task, confidence)

        if not should_clarify or trigger is None:
            return None

        # Prepare alternatives
        alternatives = alternative_intents or []

        # Determine if we should offer options
        has_options = self.rules.should_offer_options(trigger, alternatives)

        # Generate options if applicable
        options = []
        if has_options:
            options = self._generate_options(alternatives, intent)

        # Generate question
        question = self._generate_question(trigger, intent, task, options)

        # Create clarification request
        return ClarificationRequest(
            trigger=trigger,
            question=question,
            options=options,
            is_open_ended=not has_options,
            context={
                "original_intent": intent.intent_type if intent else None,
                "confidence": confidence,
                "alternatives_count": len(alternatives),
            },
        )

    def _generate_options(
        self,
        alternatives: list[tuple[str, float]],
        original_intent: Intent | None,
    ) -> list[ClarificationOption]:
        """Generate clarification options from alternatives.

        Args:
            alternatives: List of (intent_type, confidence) tuples
            original_intent: Original detected intent

        Returns:
            List of clarification options

        """
        options = []

        # Take top 3 alternatives
        for intent_type, conf in alternatives[:3]:
            # Generate human-readable description
            description = self._intent_to_description(intent_type)

            # Extract entities from original intent if available
            entities = original_intent.entities if original_intent else {}

            options.append(
                ClarificationOption(
                    description=description,
                    intent_type=intent_type,
                    entities=entities,
                    confidence=conf,
                ),
            )

        return options

    def _generate_question(
        self,
        trigger: ClarificationTrigger,
        intent: Intent | None,
        task: Task | None,
        options: list[ClarificationOption],
    ) -> str:
        """Generate the clarification question.

        Args:
            trigger: Clarification trigger
            intent: Detected intent
            task: Generated task
            options: Clarification options

        Returns:
            Clarification question string

        """
        # Get base template
        template = self.templates.get_template(trigger, len(options) > 0)

        # Fill in template based on trigger
        if trigger == ClarificationTrigger.AMBIGUOUS_INTENT and options:
            if len(options) == 2:  # noqa: PLR2004 - Small integer threshold

                return template.format(
                    option1=options[0].description,
                    option2=options[1].description,
                )
            if len(options) >= 3:  # noqa: PLR2004 - Small integer threshold

                return template.format(
                    option1=options[0].description,
                    option2=options[1].description,
                    option3=options[2].description,
                )

        elif trigger == ClarificationTrigger.MISSING_ENTITIES:
            missing = self._identify_missing_entities(intent, task)
            return template.format(missing_entity=missing)

        elif trigger == ClarificationTrigger.INCOMPLETE_REQUEST:
            missing_info = self._identify_missing_info(intent, task)
            return template.format(missing_info=missing_info)

        elif trigger == ClarificationTrigger.LOW_CONFIDENCE:
            if intent:
                question = (
                    f"Are you asking me to {self._intent_to_description(intent.intent_type)}?"
                )
            else:
                question = "What would you like me to do?"
            return template.format(question=question)

        # Default open-ended
        return template

    def _intent_to_description(self, intent_type: str) -> str:
        """Convert intent type to human-readable description.

        Args:
            intent_type: Intent type string

        Returns:
            Human-readable description

        """
        # Simple conversion: replace underscores with spaces
        return intent_type.replace("_", " ")

    def _identify_missing_entities(self, intent: Intent | None, task: Task | None) -> str:
        """Identify what entities are missing.

        Args:
            intent: Detected intent
            task: Generated task

        Returns:
            Description of missing entities

        """
        # Common missing entities by intent type
        if intent and intent.intent_type == "set_timer":
            return "the duration"
        if intent and intent.intent_type == "send_message":
            return "who to send it to"
        if intent and intent.intent_type == "play_music":
            return "what to play"
        if intent and intent.intent_type == "query_weather":
            return "the location"

        return "more details"

    def _identify_missing_info(self, intent: Intent | None, task: Task | None) -> str:
        """Identify what information is missing.

        Args:
            intent: Detected intent
            task: Generated task

        Returns:
            Description of missing information

        """
        if task and task.requires_confirmation:
            return "confirmation to proceed"

        return "more information"
