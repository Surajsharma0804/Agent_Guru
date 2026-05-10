"""Conversation Context Injector.

This module implements context injection for LLM prompts, integrating with
the Conversation State Manager to provide rich context for reasoning.

The ContextInjector:
- Extracts relevant conversation turns (last 5 turns)
- Includes tracked entities from conversation state
- Adds user preferences and past actions
- Implements context compression for long conversations
- Integrates with PromptContext from prompt_templates.py

Performance Target: <50ms for context extraction and formatting
Requirements: 16.4, 16.7

Author: Agent_Guru Team
Date: 2024
"""

from dataclasses import dataclass
from typing import Any

from Agent_Guru.reasoning.llm.prompt_templates import PromptContext
from Agent_Guru.reasoning.models.conversation import ConversationState
from Agent_Guru.reasoning.state.conversation_manager import ConversationStateManager


@dataclass
class ContextExtractionConfig:
    """Configuration for context extraction.

    Attributes:
        max_turns: Maximum number of conversation turns to extract
        max_entities: Maximum number of entities to include
        max_preferences: Maximum number of preferences to include
        max_actions: Maximum number of past actions to include
        max_memories: Maximum number of memories to include
        max_tokens: Maximum token count for context (approximate)
        include_world_state: Whether to include world state summary

    """

    max_turns: int = 5
    max_entities: int = 10
    max_preferences: int = 5
    max_actions: int = 3
    max_memories: int = 5
    max_tokens: int = 1000
    include_world_state: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if self.max_turns < 1:
            msg = f"max_turns must be >= 1, got {self.max_turns}"
            raise ValueError(msg)
        if self.max_entities < 0:
            msg = f"max_entities must be >= 0, got {self.max_entities}"
            raise ValueError(msg)
        if self.max_preferences < 0:
            msg = f"max_preferences must be >= 0, got {self.max_preferences}"
            raise ValueError(msg)
        if self.max_actions < 0:
            msg = f"max_actions must be >= 0, got {self.max_actions}"
            raise ValueError(msg)
        if self.max_memories < 0:
            msg = f"max_memories must be >= 0, got {self.max_memories}"
            raise ValueError(msg)
        if self.max_tokens < 100:
            msg = f"max_tokens must be >= 100, got {self.max_tokens}"
            raise ValueError(msg)


class ContextInjector:
    """Injects conversation context into LLM prompts.

    Integrates with ConversationStateManager to extract:
    - Recent conversation turns (last 5 by default)
    - Tracked entities from conversation
    - User preferences
    - Past actions
    - Retrieved memories (from Memory Retrieval Layer)
    - World state summary (optional)

    Implements context compression when approaching token limits.

    Time Complexity: O(n) where n is number of turns/entities
    Space Complexity: O(n) for extracted context

    Performance Target: <50ms for context extraction and formatting
    """

    def __init__(
        self,
        conversation_manager: ConversationStateManager,
        config: ContextExtractionConfig | None = None,
    ) -> None:
        """Initialize context injector.

        Args:
            conversation_manager: Conversation state manager instance
            config: Optional configuration for context extraction

        """
        self.conversation_manager = conversation_manager
        self.config = config or ContextExtractionConfig()

    async def extract_context(
        self,
        conversation_id: str,
        retrieved_memories: list[dict[str, Any]] | None = None,
        world_state_summary: str | None = None,
    ) -> PromptContext:
        """Extract conversation context for prompt injection.

        Time Complexity: O(n) where n is number of turns
        Space Complexity: O(n) for extracted context

        Args:
            conversation_id: Unique conversation identifier
            retrieved_memories: Optional list of retrieved memories from Memory Retrieval Layer
            world_state_summary: Optional world state summary

        Returns:
            PromptContext with extracted conversation context

        Example:
            >>> injector = ContextInjector(conversation_manager)
            >>> context = await injector.extract_context("conv_123")
            >>> print(context.format_for_prompt())

        """
        # Get conversation state
        state = await self.conversation_manager.get_state(conversation_id)

        if state is None:
            # Return empty context if conversation not found
            return PromptContext()

        # Extract recent turns
        recent_turns = await self._extract_recent_turns(state)

        # Extract tracked entities
        tracked_entities = await self._extract_tracked_entities(state)

        # Extract user preferences
        user_preferences = await self._extract_user_preferences(state)

        # Extract past actions
        past_actions = await self._extract_past_actions(state)

        # Create prompt context
        context = PromptContext(
            recent_turns=recent_turns,
            tracked_entities=tracked_entities,
            user_preferences=user_preferences,
            past_actions=past_actions,
            retrieved_memories=retrieved_memories or [],
            world_state_summary=world_state_summary if self.config.include_world_state else None,
        )

        # Compress if needed
        if self._needs_compression(context):
            context = self._compress_context(context)

        return context

    async def inject_context(
        self,
        conversation_id: str,
        retrieved_memories: list[dict[str, Any]] | None = None,
        world_state_summary: str | None = None,
    ) -> PromptContext:
        """Inject conversation context into prompt.

        This is an alias for extract_context for backward compatibility.

        Args:
            conversation_id: Unique conversation identifier
            retrieved_memories: Optional list of retrieved memories
            world_state_summary: Optional world state summary

        Returns:
            PromptContext with extracted conversation context

        """
        return await self.extract_context(conversation_id, retrieved_memories, world_state_summary)

    async def _extract_recent_turns(self, state: ConversationState) -> list[str]:
        """Extract recent conversation turns.

        Args:
            state: Conversation state

        Returns:
            List of formatted conversation turns (most recent last)

        """
        # Get last N turns
        recent_turns = state.turns[-self.config.max_turns :]

        # Format turns as "User: <input>" or "Agent: <response>"
        formatted_turns = []
        for turn in recent_turns:
            # Add user input
            formatted_turns.append(f"User: {turn.user_input}")

            # Add agent response if available
            if turn.response:
                formatted_turns.append(f"Agent: {turn.response}")

        return formatted_turns

    async def _extract_tracked_entities(self, state: ConversationState) -> dict[str, Any]:
        """Extract tracked entities from conversation.

        Args:
            state: Conversation state

        Returns:
            Dictionary of entity_type -> value pairs

        """
        # Get all tracked entities
        entities = state.entities

        if not entities:
            return {}

        # Sort by last mentioned (most recent first)
        sorted_entities = sorted(entities.values(), key=lambda e: e.last_mentioned, reverse=True)

        # Take top N entities
        top_entities = sorted_entities[: self.config.max_entities]

        # Convert to dictionary
        entity_dict = {}
        for entity in top_entities:
            entity_dict[entity.entity_type] = entity.value

        return entity_dict

    async def _extract_user_preferences(self, state: ConversationState) -> dict[str, Any]:
        """Extract user preferences from conversation state.

        Args:
            state: Conversation state

        Returns:
            Dictionary of preference_key -> preference_value pairs

        """
        # Get user preferences from state
        preferences = state.user_preferences

        if not preferences:
            return {}

        # Limit to max preferences
        if len(preferences) <= self.config.max_preferences:
            return preferences.copy()

        # Take first N preferences (could be improved with priority ranking)
        return dict(list(preferences.items())[: self.config.max_preferences])

    async def _extract_past_actions(self, state: ConversationState) -> list[str]:
        """Extract past actions from conversation turns.

        Args:
            state: Conversation state

        Returns:
            List of formatted past actions

        """
        # Extract actions from recent turns
        actions = []

        for turn in state.turns[-self.config.max_actions :]:
            if turn.action_taken:
                # Format action as "action_name(params)"
                action_str = self._format_action(turn.action_taken)
                actions.append(action_str)

        return actions

    def _format_action(self, action: Any) -> str:
        """Format action for display.

        Args:
            action: Action object

        Returns:
            Formatted action string

        """
        # Handle different action formats
        if hasattr(action, "tool_id") and hasattr(action, "parameters"):
            # Format as "tool_id(param1=value1, param2=value2)"
            params = ", ".join(f"{k}={v}" for k, v in action.parameters.items())
            return f"{action.tool_id}({params})"
        if isinstance(action, dict):
            # Format dictionary action
            tool_id = action.get("tool_id", "unknown")
            params = action.get("parameters", {})
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())
            return f"{tool_id}({params_str})"
        # Fallback to string representation
        return str(action)

    def _needs_compression(self, context: PromptContext) -> bool:
        """Check if context needs compression.

        Args:
            context: Prompt context

        Returns:
            True if context exceeds token limit

        """
        # Format context and estimate token count
        formatted = context.format_for_prompt()

        # Rough approximation: 4 characters per token
        estimated_tokens = len(formatted) / 4

        return estimated_tokens > self.config.max_tokens

    def _compress_context(self, context: PromptContext) -> PromptContext:
        """Compress context to fit within token limits.

        Compression strategy:
        1. Reduce turns to last 2
        2. Reduce entities to top 5
        3. Reduce preferences to top 3
        4. Remove past actions
        5. Reduce memories to top 3
        6. Truncate world state summary

        Args:
            context: Original context

        Returns:
            Compressed context

        """
        # Start with aggressive compression
        compressed = PromptContext(
            recent_turns=context.recent_turns[-2:],  # Last 2 turns
            tracked_entities=dict(list(context.tracked_entities.items())[:5]),  # Top 5 entities
            user_preferences=dict(list(context.user_preferences.items())[:3]),  # Top 3 preferences
            past_actions=[],  # Remove past actions
            retrieved_memories=context.retrieved_memories[:3],  # Top 3 memories
            world_state_summary=context.world_state_summary[:200]
            if context.world_state_summary
            else None,
        )

        # Check if it fits
        if not self._needs_compression(compressed):
            return compressed

        # Further compress - reduce to 1 turn
        compressed.recent_turns = context.recent_turns[-1:] if context.recent_turns else []

        if not self._needs_compression(compressed):
            return compressed

        # Even more aggressive - reduce entities to 3
        compressed.tracked_entities = dict(list(context.tracked_entities.items())[:3])

        if not self._needs_compression(compressed):
            return compressed

        # Last resort - reduce to 1 entity, 2 memories, remove preferences
        compressed.tracked_entities = dict(list(context.tracked_entities.items())[:1])
        compressed.retrieved_memories = context.retrieved_memories[:2]
        compressed.user_preferences = {}

        return compressed

    async def extract_context_for_multi_step(
        self,
        conversation_id: str,
        step_number: int,
        previous_step_results: list[dict[str, Any]],
        retrieved_memories: list[dict[str, Any]] | None = None,
        world_state_summary: str | None = None,
    ) -> PromptContext:
        """Extract context for multi-step reasoning.

        Includes results from previous steps in the context.

        Args:
            conversation_id: Unique conversation identifier
            step_number: Current step number (1-indexed)
            previous_step_results: Results from previous steps
            retrieved_memories: Optional list of retrieved memories
            world_state_summary: Optional world state summary

        Returns:
            PromptContext with multi-step context

        """
        # Get base context
        context = await self.extract_context(
            conversation_id,
            retrieved_memories,
            world_state_summary,
        )

        # Add previous step results to past actions
        for i, result in enumerate(previous_step_results, 1):
            action_str = f"Step {i}: {result.get('description', 'unknown')} -> {result.get('result', 'unknown')}"
            context.past_actions.append(action_str)

        return context

    async def update_context_with_feedback(
        self,
        conversation_id: str,
        feedback: str,
        feedback_type: str = "correction",
    ) -> None:
        """Update conversation context with user feedback.

        Args:
            conversation_id: Unique conversation identifier
            feedback: User feedback text
            feedback_type: Type of feedback (correction, confirmation, clarification)

        """
        # Get conversation state
        state = await self.conversation_manager.get_state(conversation_id)

        if state is None:
            return

        # Update last turn with feedback
        if state.turns:
            last_turn = state.turns[-1]
            last_turn.user_feedback = feedback

            # Update state
            await self.conversation_manager.set_state(conversation_id, state)

    def estimate_token_count(self, context: PromptContext) -> int:
        """Estimate token count for context.

        Uses rough approximation of 4 characters per token.

        Args:
            context: Prompt context

        Returns:
            Estimated token count

        """
        formatted = context.format_for_prompt()
        return len(formatted) // 4

    def get_compression_stats(
        self,
        original: PromptContext,
        compressed: PromptContext,
    ) -> dict[str, Any]:
        """Get compression statistics.

        Args:
            original: Original context
            compressed: Compressed context

        Returns:
            Dictionary with compression statistics

        """
        original_tokens = self.estimate_token_count(original)
        compressed_tokens = self.estimate_token_count(compressed)

        return {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "reduction_tokens": original_tokens - compressed_tokens,
            "reduction_percent": ((original_tokens - compressed_tokens) / original_tokens * 100)
            if original_tokens > 0
            else 0,
            "turns_removed": len(original.recent_turns) - len(compressed.recent_turns),
            "entities_removed": len(original.tracked_entities) - len(compressed.tracked_entities),
            "preferences_removed": len(original.user_preferences)
            - len(compressed.user_preferences),
            "actions_removed": len(original.past_actions) - len(compressed.past_actions),
            "memories_removed": len(original.retrieved_memories)
            - len(compressed.retrieved_memories),
        }
