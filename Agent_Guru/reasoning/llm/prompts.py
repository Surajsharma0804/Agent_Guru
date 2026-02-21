"""
Reasoning Prompt Templates

Provides prompt templates for LLM reasoning with:
- System prompts for Agent_Guru reasoning engine
- Single-step reasoning templates
- Multi-step task decomposition templates
- Few-shot examples for common patterns
- Conversation context injection

Performance Target: <50ms prompt formatting overhead
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ConversationContext:
    """Conversation context for prompt injection."""

    recent_turns: list[str] = field(default_factory=list)
    tracked_entities: dict[str, Any] = field(default_factory=dict)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    past_actions: list[str] = field(default_factory=list)

    def format_for_prompt(self, max_turns: int = 5) -> str:
        """Format context for prompt injection."""
        parts = []

        # Recent conversation - respect max_turns limit
        if self.recent_turns:
            # Take only the last max_turns turns
            turns = self.recent_turns[-max_turns:] if len(self.recent_turns) > max_turns else self.recent_turns
            if turns:
                parts.append("Recent conversation:")
                for i, turn in enumerate(turns, 1):
                    parts.append(f"  {i}. {turn}")

        # Tracked entities
        if self.tracked_entities:
            parts.append("\nTracked entities:")
            for entity_type, entity_value in self.tracked_entities.items():
                parts.append(f"  - {entity_type}: {entity_value}")

        # User preferences
        if self.user_preferences:
            parts.append("\nUser preferences:")
            for pref_key, pref_value in self.user_preferences.items():
                parts.append(f"  - {pref_key}: {pref_value}")

        # Past actions
        if self.past_actions:
            parts.append("\nRecent actions:")
            for action in self.past_actions[-3:]:  # Last 3 actions
                parts.append(f"  - {action}")

        return "\n".join(parts) if parts else "No conversation context available."


class ReasoningPrompts:
    """
    Reasoning prompt templates for Agent_Guru.

    Provides system prompts, reasoning templates, and few-shot examples.
    """

    # System prompt for Agent_Guru reasoning engine
    SYSTEM_PROMPT = """You are the reasoning engine for Agent_Guru, an AI assistant that helps users control their devices and complete tasks through natural language.

Your role is to:
1. Understand user requests and break them down into actionable steps
2. Generate clear, executable plans with specific tools and parameters
3. Consider conversation context and user preferences
4. Ensure plans are safe, efficient, and aligned with user intent

Guidelines:
- Keep plans simple and focused (1-5 steps maximum)
- Use concrete, specific parameters (avoid vague references)
- Consider dependencies between steps
- Estimate realistic durations for each step
- Flag sensitive actions that require confirmation
- Provide clear reasoning for your decisions

Output Format:
Return a JSON object with this structure:
{
  "goal": "Clear description of what the plan achieves",
  "steps": [
    {
      "step_id": 1,
      "description": "What this step does",
      "tool_id": "tool_name",
      "parameters": {"param1": "value1"},
      "estimated_duration_seconds": 2.0,
      "requires_confirmation": false
    }
  ],
  "reasoning": "Why this plan achieves the goal",
  "confidence": 0.95
}"""

    # Single-step reasoning template
    SINGLE_STEP_TEMPLATE = """User request: {user_input}

Intent: {intent_type}
Entities: {entities}

{context}

Task: Generate a single-step plan to fulfill this request.

Available tools: {available_tools}

Generate a plan with exactly ONE step that accomplishes the user's goal."""

    # Multi-step reasoning template
    MULTI_STEP_TEMPLATE = """User request: {user_input}

Intent: {intent_type}
Entities: {entities}

{context}

Task: Generate a multi-step plan to fulfill this request.

Available tools: {available_tools}

Generate a plan with 2-5 steps that accomplishes the user's goal. Each step should:
- Have clear dependencies (if any)
- Use specific, concrete parameters
- Have realistic duration estimates
- Be executable with available tools

Consider the order of operations and any dependencies between steps."""

    # Few-shot examples for common patterns
    FEW_SHOT_EXAMPLES = {
        "set_timer": {
            "user_input": "Set a timer for 5 minutes",
            "intent_type": "set_timer",
            "entities": {"duration": "5 minutes"},
            "plan": {
                "goal": "Set a 5-minute timer",
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Create timer for 5 minutes",
                        "tool_id": "timer_tool",
                        "parameters": {"duration_seconds": 300, "label": "Timer"},
                        "estimated_duration_seconds": 1.0,
                        "requires_confirmation": False,
                    }
                ],
                "reasoning": "Simple timer creation with specified duration",
                "confidence": 0.98,
            },
        },
        "send_message": {
            "user_input": "Send a message to John saying I'll be late",
            "intent_type": "send_message",
            "entities": {"recipient": "John", "message": "I'll be late"},
            "plan": {
                "goal": "Send message to John",
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Send message to John",
                        "tool_id": "messaging_tool",
                        "parameters": {
                            "recipient": "John",
                            "message": "I'll be late",
                            "app": "default_messaging_app",
                        },
                        "estimated_duration_seconds": 2.0,
                        "requires_confirmation": True,
                    }
                ],
                "reasoning": "Messaging is sensitive, requires confirmation",
                "confidence": 0.95,
            },
        },
        "multi_step_task": {
            "user_input": "Play my workout playlist and set a timer for 30 minutes",
            "intent_type": "multi_step_task",
            "entities": {"playlist": "workout", "duration": "30 minutes"},
            "plan": {
                "goal": "Start workout session with music and timer",
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Play workout playlist",
                        "tool_id": "music_tool",
                        "parameters": {"playlist": "workout", "action": "play"},
                        "estimated_duration_seconds": 2.0,
                        "requires_confirmation": False,
                    },
                    {
                        "step_id": 2,
                        "description": "Set 30-minute timer",
                        "tool_id": "timer_tool",
                        "parameters": {"duration_seconds": 1800, "label": "Workout"},
                        "estimated_duration_seconds": 1.0,
                        "requires_confirmation": False,
                    },
                ],
                "reasoning": "Two independent actions that can be executed sequentially",
                "confidence": 0.96,
            },
        },
    }

    @staticmethod
    def format_single_step_prompt(
        user_input: str,
        intent_type: str,
        entities: dict[str, Any],
        available_tools: list[str],
        context: Optional[ConversationContext] = None,
    ) -> str:
        """
        Format single-step reasoning prompt.

        Args:
            user_input: User's request
            intent_type: Detected intent type
            entities: Extracted entities
            available_tools: List of available tool names
            context: Optional conversation context

        Returns:
            Formatted prompt string
        """
        context_str = context.format_for_prompt() if context else "No context available."

        return ReasoningPrompts.SINGLE_STEP_TEMPLATE.format(
            user_input=user_input,
            intent_type=intent_type,
            entities=entities,
            available_tools=", ".join(available_tools),
            context=context_str,
        )

    @staticmethod
    def format_multi_step_prompt(
        user_input: str,
        intent_type: str,
        entities: dict[str, Any],
        available_tools: list[str],
        context: Optional[ConversationContext] = None,
    ) -> str:
        """
        Format multi-step reasoning prompt.

        Args:
            user_input: User's request
            intent_type: Detected intent type
            entities: Extracted entities
            available_tools: List of available tool names
            context: Optional conversation context

        Returns:
            Formatted prompt string
        """
        context_str = context.format_for_prompt() if context else "No context available."

        return ReasoningPrompts.MULTI_STEP_TEMPLATE.format(
            user_input=user_input,
            intent_type=intent_type,
            entities=entities,
            available_tools=", ".join(available_tools),
            context=context_str,
        )

    @staticmethod
    def get_few_shot_examples(intent_type: str, count: int = 2) -> str:
        """
        Get few-shot examples for prompt.

        Args:
            intent_type: Intent type to get examples for
            count: Number of examples to include

        Returns:
            Formatted few-shot examples
        """
        examples = []

        # Get specific example if available
        if intent_type in ReasoningPrompts.FEW_SHOT_EXAMPLES:
            example = ReasoningPrompts.FEW_SHOT_EXAMPLES[intent_type]
            examples.append(
                f"Example:\nInput: {example['user_input']}\nIntent: {example['intent_type']}\nPlan: {example['plan']}"
            )

        # Add general examples
        for key, example in list(ReasoningPrompts.FEW_SHOT_EXAMPLES.items())[:count]:
            if key != intent_type:
                examples.append(
                    f"Example:\nInput: {example['user_input']}\nIntent: {example['intent_type']}\nPlan: {example['plan']}"
                )

        return "\n\n".join(examples[:count])

    @staticmethod
    def compress_context(context: ConversationContext, max_length: int = 500) -> ConversationContext:
        """
        Compress conversation context to fit within token limits.

        Args:
            context: Original context
            max_length: Maximum character length

        Returns:
            Compressed context
        """
        # Start with aggressive compression
        compressed = ConversationContext(
            recent_turns=context.recent_turns[-2:],  # Keep only last 2 turns
            tracked_entities=dict(list(context.tracked_entities.items())[:3]),  # Keep only 3 entities
            user_preferences=context.user_preferences,
            past_actions=[],  # Remove past actions first
        )

        # Check if it fits
        formatted = compressed.format_for_prompt()
        if len(formatted) <= max_length:
            return compressed

        # Further compress if still too long - reduce to 1 turn
        compressed.recent_turns = context.recent_turns[-1:] if context.recent_turns else []

        formatted = compressed.format_for_prompt()
        if len(formatted) <= max_length:
            return compressed

        # Even more aggressive - reduce entities to 2
        compressed.tracked_entities = dict(list(context.tracked_entities.items())[:2])

        formatted = compressed.format_for_prompt()
        if len(formatted) <= max_length:
            return compressed

        # Last resort - reduce entities to 1 and remove preferences
        compressed.tracked_entities = dict(list(context.tracked_entities.items())[:1])
        compressed.user_preferences = {}

        return compressed
