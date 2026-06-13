"""Semantic LLM Interpreter Prompt Templates.

This module provides prompt templates for the Semantic LLM Interpreter,
which is the PRIMARY BRAIN of Agent_Guru. It converts natural language
user requests directly into structured Task objects.

The Semantic LLM Interpreter:
- Converts natural language to Task objects (goal, task_type, entities, steps)
- Handles single-step, multi-step, and conversational tasks
- Injects conversation context, user preferences, and memories
- Provides few-shot examples for common task types
- Supports fast-path routing (80% of commands bypass full reasoning)

Performance Target: <400ms for LLM reasoning (95th percentile)
Accuracy Target: >95% task generation accuracy

Requirements: 16.1, 16.2, 16.3, 16.4
"""

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptContext:
    """Context information for prompt injection.

    Includes conversation history, tracked entities, user preferences,
    past actions, retrieved memories, and world state.
    """

    # Conversation context
    recent_turns: list[str] = field(default_factory=list)
    tracked_entities: dict[str, Any] = field(default_factory=dict)

    # User personalization
    user_preferences: dict[str, Any] = field(default_factory=dict)
    past_actions: list[str] = field(default_factory=list)

    # Memory retrieval (top 5 relevant memories)
    retrieved_memories: list[dict[str, Any]] = field(default_factory=list)

    # World state summary
    world_state_summary: str | None = None

    def format_for_prompt(self, max_turns: int = 5) -> str:
        """Format context for prompt injection.

        Args:
            max_turns: Maximum number of conversation turns to include

        Returns:
            Formatted context string

        """
        parts = []

        # Recent conversation
        if self.recent_turns:
            turns = (
                self.recent_turns[-max_turns:]
                if len(self.recent_turns) > max_turns
                else self.recent_turns
            )
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

        # Retrieved memories
        if self.retrieved_memories:
            parts.append("\nRelevant memories:")
            for memory in self.retrieved_memories[:5]:  # Top 5 memories
                memory_type = memory.get("memory_type", "unknown")
                content = memory.get("content", "")
                parts.append(f"  - [{memory_type}] {content}")

        # World state
        if self.world_state_summary:
            parts.append(f"\nWorld state:\n{self.world_state_summary}")

        return "\n".join(parts) if parts else "No context available."


class PromptTemplate:
    """Prompt template for semantic interpretation.

    Includes system prompt, user prompt template, and few-shot examples.
    """

    def __init__(
        self,
        system_prompt: str,
        user_prompt_template: str,
        few_shot_examples: list[dict[str, Any]],
    ) -> None:
        """Initialize prompt template.

        Args:
            system_prompt: System-level instructions for the LLM
            user_prompt_template: Template for user prompts with placeholders
            few_shot_examples: List of example input/output pairs

        """
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.few_shot_examples = few_shot_examples

    def format_user_prompt(
        self,
        user_input: str,
        context: PromptContext | None = None,
        available_tools: list[str] | None = None,
        include_examples: bool = True,
        max_examples: int = 3,
    ) -> str:
        """Format user prompt with context and examples.

        Args:
            user_input: User's natural language request
            context: Optional conversation context
            available_tools: Optional list of available tool names
            include_examples: Whether to include few-shot examples
            max_examples: Maximum number of examples to include

        Returns:
            Formatted user prompt

        """
        # Format context
        context_str = context.format_for_prompt() if context else "No context available."

        # Format available tools
        tools_str = ", ".join(available_tools) if available_tools else "All tools available"

        # Format few-shot examples
        examples_str = ""
        if include_examples and self.few_shot_examples:
            examples_str = "\n\n".join(
                [self._format_example(ex) for ex in self.few_shot_examples[:max_examples]],
            )
            examples_str = f"\n\nExamples:\n\n{examples_str}\n\n"

        # Format user prompt
        return self.user_prompt_template.format(
            user_input=user_input,
            context=context_str,
            available_tools=tools_str,
            examples=examples_str,
        )

    def _format_example(self, example: dict[str, Any]) -> str:
        """Format a single few-shot example."""
        input_text = example.get("input", "")
        output_task = example.get("output", {})

        return f"Input: {input_text}\n\nOutput:\n{json.dumps(output_task, indent=2)}"


# System prompt for Agent_Guru Semantic LLM Interpreter
SEMANTIC_INTERPRETER_SYSTEM_PROMPT = """You are the Semantic LLM Interpreter for Agent_Guru, a world-class AI assistant.

Your role is to convert natural language user requests into structured Task objects that can be executed by the system.

CRITICAL RESPONSIBILITIES:
1. Understand user intent from natural language
2. Generate executable Task objects with clear goals and steps
3. Extract entities and parameters accurately
4. Consider conversation context and user preferences
5. Classify task types correctly (single_step, multi_step, conversational, memory_query)
6. Estimate realistic durations and identify sensitive actions
7. Provide confidence scores for your interpretations

TASK OBJECT STRUCTURE:
{
  "goal": "Clear, concise description of what the user wants to achieve",
  "task_type": "single_step | multi_step | conversational | memory_query",
  "entities": {
    "entity_name": "entity_value"
  },
  "steps": [
    {
      "step_id": 1,
      "description": "What this step does",
      "tool_id": "tool_name",
      "parameters": {
        "param1": "value1"
      },
      "estimated_duration": 2.0,
      "status": "pending"
    }
  ],
  "confidence": 0.95,
  "requires_confirmation": false,
  "estimated_duration": 3.0
}

TASK TYPES:
- single_step: One action to complete (e.g., "set timer", "play music")
- multi_step: 2-5 sequential actions (e.g., "check weather and remind me if raining")
- conversational: Requires dialogue, no immediate action (e.g., "tell me about yourself")
- memory_query: Retrieves information from memory (e.g., "when did I last call John?")

GUIDELINES:
1. Keep tasks simple and focused (1-5 steps maximum)
2. Use concrete, specific parameters (avoid vague references)
3. Extract all relevant entities from user input and context
4. Consider conversation history for pronoun resolution
5. Use user preferences to personalize task execution
6. Flag sensitive actions (messaging, calling, file operations) with requires_confirmation=true
7. Provide realistic duration estimates (in seconds)
8. Assign confidence scores based on clarity of intent (0.0-1.0)
9. For ambiguous requests, set confidence < 0.7 and include clarification in goal
10. Use retrieved memories to enhance understanding

PERFORMANCE TARGETS:
- Accuracy: >95% correct task generation
- Latency: <400ms for task generation
- Confidence: >0.8 for clear requests, <0.7 for ambiguous ones

OUTPUT FORMAT:
Always return a valid JSON object matching the Task structure above.
Do not include any text before or after the JSON object."""

# User prompt template for semantic interpretation
SEMANTIC_INTERPRETER_USER_TEMPLATE = """User request: {user_input}

Context:
{context}

Available tools: {available_tools}
{examples}
Now, convert the user request into a Task object. Consider the context and use appropriate tools.

Task object (JSON):"""

# Few-shot examples for common task types
SEMANTIC_INTERPRETER_EXAMPLES = [
    {
        "input": "Set a timer for 5 minutes",
        "output": {
            "goal": "Set a 5-minute timer",
            "task_type": "single_step",
            "entities": {"duration": "5 minutes", "duration_seconds": 300},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Create timer for 5 minutes",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 300, "label": "Timer"},
                    "estimated_duration": 1.0,
                    "status": "pending",
                },
            ],
            "confidence": 0.98,
            "requires_confirmation": False,
            "estimated_duration": 1.0,
        },
    },
    {
        "input": "Send a message to John saying I'll be late",
        "output": {
            "goal": "Send message to John: 'I'll be late'",
            "task_type": "single_step",
            "entities": {"recipient": "John", "message": "I'll be late", "action": "send_message"},
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
                    "estimated_duration": 2.0,
                    "status": "pending",
                },
            ],
            "confidence": 0.95,
            "requires_confirmation": True,
            "estimated_duration": 2.0,
        },
    },
    {
        "input": "Play my workout playlist and set a timer for 30 minutes",
        "output": {
            "goal": "Start workout session with music and timer",
            "task_type": "multi_step",
            "entities": {"playlist": "workout", "duration": "30 minutes", "duration_seconds": 1800},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Play workout playlist",
                    "tool_id": "music_tool",
                    "parameters": {"playlist": "workout", "action": "play"},
                    "estimated_duration": 2.0,
                    "status": "pending",
                },
                {
                    "step_id": 2,
                    "description": "Set 30-minute timer",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 1800, "label": "Workout"},
                    "estimated_duration": 1.0,
                    "status": "pending",
                },
            ],
            "confidence": 0.96,
            "requires_confirmation": False,
            "estimated_duration": 3.0,
        },
    },
    {
        "input": "What's the weather like?",
        "output": {
            "goal": "Get current weather information",
            "task_type": "single_step",
            "entities": {"query_type": "weather", "time": "current"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Query current weather",
                    "tool_id": "weather_tool",
                    "parameters": {"location": "current_location", "time": "now"},
                    "estimated_duration": 1.5,
                    "status": "pending",
                },
            ],
            "confidence": 0.92,
            "requires_confirmation": False,
            "estimated_duration": 1.5,
        },
    },
    {
        "input": "Check the weather and if it's raining, remind me to bring an umbrella",
        "output": {
            "goal": "Check weather and conditionally set umbrella reminder",
            "task_type": "multi_step",
            "entities": {
                "query_type": "weather",
                "condition": "raining",
                "reminder": "bring umbrella",
            },
            "steps": [
                {
                    "step_id": 1,
                    "description": "Check current weather",
                    "tool_id": "weather_tool",
                    "parameters": {"location": "current_location", "time": "now"},
                    "estimated_duration": 1.5,
                    "status": "pending",
                },
                {
                    "step_id": 2,
                    "description": "Create reminder if raining",
                    "tool_id": "reminder_tool",
                    "parameters": {
                        "message": "Bring an umbrella",
                        "condition": "if_raining",
                        "depends_on_step": 1,
                    },
                    "estimated_duration": 1.0,
                    "status": "pending",
                },
            ],
            "confidence": 0.88,
            "requires_confirmation": False,
            "estimated_duration": 2.5,
        },
    },
    {
        "input": "Tell me about yourself",
        "output": {
            "goal": "Provide information about Agent_Guru",
            "task_type": "conversational",
            "entities": {"query_type": "about_agent"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Generate conversational response about Agent_Guru",
                    "tool_id": "conversation_tool",
                    "parameters": {"topic": "about_agent", "response_type": "informational"},
                    "estimated_duration": 0.5,
                    "status": "pending",
                },
            ],
            "confidence": 0.99,
            "requires_confirmation": False,
            "estimated_duration": 0.5,
        },
    },
    {
        "input": "When did I last call Mom?",
        "output": {
            "goal": "Retrieve last call time with Mom from memory",
            "task_type": "memory_query",
            "entities": {"query_type": "temporal", "action": "call", "person": "Mom"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Query memory for last call with Mom",
                    "tool_id": "memory_query_tool",
                    "parameters": {"query_type": "temporal", "action": "call", "person": "Mom"},
                    "estimated_duration": 1.0,
                    "status": "pending",
                },
            ],
            "confidence": 0.94,
            "requires_confirmation": False,
            "estimated_duration": 1.0,
        },
    },
    {
        "input": "Open Spotify and play my Chill playlist",
        "output": {
            "goal": "Open Spotify and play Chill playlist",
            "task_type": "multi_step",
            "entities": {"app": "Spotify", "playlist": "Chill", "action": "play"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Open Spotify app",
                    "tool_id": "app_control_tool",
                    "parameters": {"app_name": "Spotify", "action": "open"},
                    "estimated_duration": 2.0,
                    "status": "pending",
                },
                {
                    "step_id": 2,
                    "description": "Play Chill playlist",
                    "tool_id": "music_tool",
                    "parameters": {"app": "Spotify", "playlist": "Chill", "action": "play"},
                    "estimated_duration": 1.5,
                    "status": "pending",
                },
            ],
            "confidence": 0.97,
            "requires_confirmation": False,
            "estimated_duration": 3.5,
        },
    },
    {
        "input": "Remind me to call Sarah tomorrow at 2pm",
        "output": {
            "goal": "Set reminder to call Sarah tomorrow at 2pm",
            "task_type": "single_step",
            "entities": {"action": "call", "person": "Sarah", "time": "tomorrow at 2pm"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Create reminder for tomorrow at 2pm",
                    "tool_id": "reminder_tool",
                    "parameters": {
                        "message": "Call Sarah",
                        "time": "tomorrow 14:00",
                        "action": "call",
                        "person": "Sarah",
                    },
                    "estimated_duration": 1.0,
                    "status": "pending",
                },
            ],
            "confidence": 0.96,
            "requires_confirmation": False,
            "estimated_duration": 1.0,
        },
    },
    {
        "input": "What apps do I use most often?",
        "output": {
            "goal": "Retrieve most frequently used apps from memory",
            "task_type": "memory_query",
            "entities": {"query_type": "aggregation", "subject": "apps", "metric": "frequency"},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Query memory for app usage statistics",
                    "tool_id": "memory_query_tool",
                    "parameters": {
                        "query_type": "aggregation",
                        "subject": "apps",
                        "metric": "frequency",
                        "limit": 10,
                    },
                    "estimated_duration": 1.5,
                    "status": "pending",
                },
            ],
            "confidence": 0.93,
            "requires_confirmation": False,
            "estimated_duration": 1.5,
        },
    },
]

# Create default semantic interpreter prompt template
SEMANTIC_INTERPRETER_TEMPLATE = PromptTemplate(
    system_prompt=SEMANTIC_INTERPRETER_SYSTEM_PROMPT,
    user_prompt_template=SEMANTIC_INTERPRETER_USER_TEMPLATE,
    few_shot_examples=SEMANTIC_INTERPRETER_EXAMPLES,
)


def create_semantic_interpreter_prompt(
    user_input: str,
    context: PromptContext | None = None,
    available_tools: list[str] | None = None,
    include_examples: bool = True,
    max_examples: int = 3,
) -> tuple[str, str]:
    """Create system and user prompts for semantic interpretation.

    This is the main entry point for generating prompts for the
    Semantic LLM Interpreter.

    Args:
        user_input: User's natural language request
        context: Optional conversation context
        available_tools: Optional list of available tool names
        include_examples: Whether to include few-shot examples
        max_examples: Maximum number of examples to include

    Returns:
        Tuple of (system_prompt, user_prompt)

    Example:
        >>> context = PromptContext(
        ...     recent_turns=["User: What's the weather?", "Agent: It's sunny, 72°F"],
        ...     tracked_entities={"location": "Seattle"}
        ... )
        >>> system_prompt, user_prompt = create_semantic_interpreter_prompt(
        ...     "What about tomorrow?",
        ...     context=context
        ... )

    """
    system_prompt = SEMANTIC_INTERPRETER_TEMPLATE.system_prompt
    user_prompt = SEMANTIC_INTERPRETER_TEMPLATE.format_user_prompt(
        user_input=user_input,
        context=context,
        available_tools=available_tools,
        include_examples=include_examples,
        max_examples=max_examples,
    )

    return system_prompt, user_prompt


def inject_conversation_context(
    recent_turns: list[str],
    tracked_entities: dict[str, Any],
    user_preferences: dict[str, Any],
    past_actions: list[str],
    retrieved_memories: list[dict[str, Any]] | None = None,
    world_state_summary: str | None = None,
) -> PromptContext:
    """Create PromptContext from conversation components.

    This helper function assembles all context components into a
    PromptContext object for prompt injection.

    Args:
        recent_turns: List of recent conversation turns
        tracked_entities: Dictionary of tracked entities
        user_preferences: Dictionary of user preferences
        past_actions: List of recent actions
        retrieved_memories: Optional list of retrieved memories
        world_state_summary: Optional world state summary

    Returns:
        PromptContext object

    Example:
        >>> context = inject_conversation_context(
        ...     recent_turns=["User: Set timer", "Agent: Timer set for 5 minutes"],
        ...     tracked_entities={"duration": "5 minutes"},
        ...     user_preferences={"default_timer_sound": "bell"},
        ...     past_actions=["set_timer(300)"]
        ... )

    """
    return PromptContext(
        recent_turns=recent_turns,
        tracked_entities=tracked_entities,
        user_preferences=user_preferences,
        past_actions=past_actions,
        retrieved_memories=retrieved_memories or [],
        world_state_summary=world_state_summary,
    )


def compress_context_for_token_limit(
    context: PromptContext,
    max_tokens: int = 1000,
) -> PromptContext:
    """Compress context to fit within token limits.

    Applies aggressive compression strategies to reduce context size
    while preserving the most important information.

    Args:
        context: Original context
        max_tokens: Maximum token count (approximate, using 4 chars per token)

    Returns:
        Compressed context

    Strategy:
        1. Reduce recent turns to last 2
        2. Keep only top 3 entities
        3. Remove past actions
        4. Keep only top 3 memories
        5. Truncate world state summary

    """
    max_chars = max_tokens * 4  # Rough approximation

    # Start with aggressive compression
    compressed = PromptContext(
        recent_turns=context.recent_turns[-2:],  # Last 2 turns
        tracked_entities=dict(list(context.tracked_entities.items())[:3]),  # Top 3 entities
        user_preferences=context.user_preferences,
        past_actions=[],  # Remove past actions first
        retrieved_memories=context.retrieved_memories[:3],  # Top 3 memories
        world_state_summary=context.world_state_summary[:200]
        if context.world_state_summary
        else None,  # Truncate
    )

    # Check if it fits
    formatted = compressed.format_for_prompt()
    if len(formatted) <= max_chars:
        return compressed

    # Further compress - reduce to 1 turn
    compressed.recent_turns = context.recent_turns[-1:] if context.recent_turns else []

    formatted = compressed.format_for_prompt()
    if len(formatted) <= max_chars:
        return compressed

    # Even more aggressive - reduce entities to 2
    compressed.tracked_entities = dict(list(context.tracked_entities.items())[:2])

    formatted = compressed.format_for_prompt()
    if len(formatted) <= max_chars:
        return compressed

    # Last resort - reduce to 1 entity, 2 memories, remove preferences
    compressed.tracked_entities = dict(list(context.tracked_entities.items())[:1])
    compressed.retrieved_memories = context.retrieved_memories[:2]
    compressed.user_preferences = {}

    return compressed
