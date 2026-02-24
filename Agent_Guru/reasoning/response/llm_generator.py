"""
LLM-Based Response Generator

Generates natural language responses using LLM with:
- Prompt templates for response generation
- Execution result details in prompts
- Conversation context for coherent responses
- Streaming support for perceived responsiveness
- Fallback to templates on LLM failure

Performance Requirements:
- Time Complexity: O(n) where n = LLM generation time
- Space Complexity: O(1) - streaming responses
- Latency: <200ms target (with streaming for perceived responsiveness)

Design:
- Hybrid approach: LLM for natural responses, templates as fallback
- Streaming for long responses (perceived responsiveness)
- Context-aware generation using conversation history
- Automatic fallback to template generator on LLM failure
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

from Agent_Guru.reasoning.config.logging import get_logger
from Agent_Guru.reasoning.config.metrics import get_metrics_collector
from Agent_Guru.reasoning.llm.models import LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.prompts import ConversationContext
from Agent_Guru.reasoning.llm.router import HybridLLMRouter
from Agent_Guru.reasoning.models.conversation import ConversationState
from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.result import ExecutionResult, Response, ResponseModality
from Agent_Guru.reasoning.response.error_response_generator import ErrorResponseGenerator
from Agent_Guru.reasoning.response.rich_content_generator import (
    RichContentGenerator,
)
from Agent_Guru.reasoning.response.template_generator import TemplateGenerator

logger = get_logger(__name__)
metrics = get_metrics_collector()


class LLMResponseGenerator:
    """
    LLM-based response generator with streaming and fallback.

    Time Complexity: O(n) where n = LLM generation time
    Space Complexity: O(1) - streaming responses
    Latency Target: <200ms (with streaming for perceived responsiveness)

    Example:
        >>> generator = LLMResponseGenerator(llm_router, template_generator)
        >>> result = ExecutionResult(success=True, result_data={"timer": "5 minutes"})
        >>> intent = Intent(intent_type="set_timer", entities={"duration": "5 minutes"})
        >>> response = await generator.generate(result, intent, ResponseModality.VOICE)
        >>> print(response.text)
        "I've set a timer for 5 minutes"
    """

    # System prompt for response generation
    SYSTEM_PROMPT = """You are Agent_Guru's response generator. Your role is to convert execution results into natural, conversational responses.

Guidelines:
- Be concise and clear
- Match the user's communication style
- Include relevant details from the execution result
- For voice responses, be even more concise
- For errors, explain what went wrong in user-friendly terms
- Avoid technical jargon and error codes
- Provide actionable next steps when appropriate

Response Style:
- Casual and friendly (not robotic)
- Confident but not arrogant
- Helpful and proactive
- Natural and conversational"""

    # Response generation prompt template
    RESPONSE_TEMPLATE = """Generate a natural language response for this execution result.

User Request: {user_input}
Intent: {intent_type}
Entities: {entities}

Execution Result:
- Success: {success}
- Result Data: {result_data}
- Error: {error}
- Execution Time: {execution_time}s

{context}

Output Modality: {modality}
{modality_instructions}

Generate a natural, conversational response that:
1. Confirms what was done (if successful) or explains what went wrong (if failed)
2. Includes relevant details from the result
3. Is appropriate for {modality} output
4. Matches the conversation context and user's style

Response:"""

    def __init__(
        self,
        llm_router: HybridLLMRouter,
        template_generator: TemplateGenerator,
        enable_streaming: bool = True,
        fallback_on_error: bool = True,
        timeout_seconds: float = 2.0,
    ) -> None:
        """
        Initialize LLM response generator.

        Args:
            llm_router: Hybrid LLM router for generation
            template_generator: Template generator for fallback
            enable_streaming: Enable streaming responses
            fallback_on_error: Fallback to templates on LLM error
            timeout_seconds: Timeout for LLM generation
        """
        self.llm_router = llm_router
        self.template_generator = template_generator
        self.error_response_generator = ErrorResponseGenerator()
        self.rich_content_generator = RichContentGenerator()
        self.enable_streaming = enable_streaming
        self.fallback_on_error = fallback_on_error
        self.timeout_seconds = timeout_seconds
        self._proactive_generator = None  # Will be set via set_proactive_generator

        logger.info(
            "LLMResponseGenerator initialized",
            extra={
                "streaming_enabled": enable_streaming,
                "fallback_enabled": fallback_on_error,
                "timeout_seconds": timeout_seconds,
            },
        )

    async def generate(
        self,
        result: ExecutionResult,
        intent: Intent,
        modality: ResponseModality,
        conversation_state: Optional[ConversationState] = None,
        user_preferences: Optional[dict[str, Any]] = None,
        client_capabilities: Optional[set] = None,
    ) -> Response:
        """
        Generate response using LLM with fallback to templates.

        Time Complexity: O(n) where n = LLM generation time
        Space Complexity: O(1) - streaming responses

        Args:
            result: Execution result to generate response for
            intent: Original user intent
            modality: Response modality (VOICE, TEXT, BOTH)
            conversation_state: Optional conversation state for context
            user_preferences: Optional user preferences for personalization
            client_capabilities: Optional set of client capabilities for rich content

        Returns:
            Response object with generated text and metadata

        Raises:
            RuntimeError: If both LLM and template generation fail
        """
        start_time = time.perf_counter()

        try:
            # Try LLM generation first
            response = await self._generate_with_llm(
                result, intent, modality, conversation_state, user_preferences
            )

            # Add rich content if client supports it
            if client_capabilities:
                rich_content = self.rich_content_generator.generate(
                    result, intent, client_capabilities
                )
                if rich_content:
                    response.rich_content = rich_content
                    logger.debug(
                        "Rich content added to response",
                        extra={
                            "content_type": rich_content.get("type"),
                            "intent_type": intent.intent_type,
                        },
                    )

            # Track metrics
            latency_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_stage_latency("response_generation_llm", latency_ms / 1000)
            metrics.increment_requests("llm_response_success")

            logger.info(
                "LLM response generated",
                extra={
                    "modality": modality.value,
                    "latency_ms": latency_ms,
                    "intent_type": intent.intent_type,
                    "generation_method": "llm",
                    "has_rich_content": response.has_rich_content(),
                },
            )

            return response

        except Exception as llm_error:
            # Log LLM failure
            logger.warning(
                "LLM response generation failed, falling back to templates",
                extra={
                    "error": str(llm_error),
                    "intent_type": intent.intent_type,
                    "fallback_enabled": self.fallback_on_error,
                },
            )
            metrics.increment_errors("llm_response_generation")

            # Fallback to template generation if enabled
            if self.fallback_on_error:
                try:
                    response = self.template_generator.generate(
                        result,
                        intent,
                        modality,
                        context=self._extract_context_dict(conversation_state),
                        user_preferences=user_preferences,
                    )

                    # Update metadata to indicate fallback
                    response.metadata["generation_method"] = "template_fallback"
                    response.metadata["llm_error"] = str(llm_error)

                    # Add rich content if client supports it
                    if client_capabilities:
                        rich_content = self.rich_content_generator.generate(
                            result, intent, client_capabilities
                        )
                        if rich_content:
                            response.rich_content = rich_content

                    # Track metrics
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    metrics.record_stage_latency("response_generation_fallback", latency_ms / 1000)
                    metrics.increment_requests("template_fallback_success")

                    logger.info(
                        "Template fallback response generated",
                        extra={
                            "modality": modality.value,
                            "latency_ms": latency_ms,
                            "intent_type": intent.intent_type,
                            "has_rich_content": response.has_rich_content(),
                        },
                    )

                    return response

                except Exception as template_error:
                    # Both LLM and template failed
                    logger.error(
                        "Both LLM and template generation failed",
                        extra={
                            "llm_error": str(llm_error),
                            "template_error": str(template_error),
                            "intent_type": intent.intent_type,
                        },
                    )
                    metrics.increment_errors("response_generation_total_failure")
                    raise RuntimeError(
                        f"Response generation failed: LLM error: {llm_error}, "
                        f"Template error: {template_error}"
                    ) from template_error
            else:
                # No fallback, raise original error
                raise

    async def generate_streaming(
        self,
        result: ExecutionResult,
        intent: Intent,
        modality: ResponseModality,
        conversation_state: Optional[ConversationState] = None,
        user_preferences: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """
        Generate response with streaming for perceived responsiveness.

        Yields response text chunks as they are generated.

        Args:
            result: Execution result
            intent: User intent
            modality: Response modality
            conversation_state: Optional conversation state
            user_preferences: Optional user preferences

        Yields:
            Response text chunks

        Raises:
            RuntimeError: If generation fails
        """
        if not self.enable_streaming:
            # Streaming disabled, generate full response
            response = await self.generate(
                result, intent, modality, conversation_state, user_preferences
            )
            yield response.text
            return

        try:
            # Create prompt
            prompt = self._create_response_prompt(
                result, intent, modality, conversation_state, user_preferences
            )

            # Create LLM request
            llm_request = LLMRequest(
                prompt=prompt,
                max_tokens=200,  # Concise responses
                temperature=0.7,  # Balanced creativity
                stream=True,  # Enable streaming
            )

            # Generate with streaming (simulated for now)
            # In production, this would use actual LLM streaming API
            response = await asyncio.wait_for(
                self.llm_router.generate(llm_request), timeout=self.timeout_seconds
            )

            # Yield response text in chunks
            chunk_size = 10
            for i in range(0, len(response.text), chunk_size):
                chunk = response.text[i : i + chunk_size]
                yield chunk
                await asyncio.sleep(0.01)  # Simulate streaming delay

        except Exception as e:
            logger.error(
                "Streaming response generation failed",
                extra={"error": str(e), "intent_type": intent.intent_type},
            )
            # Fallback to template
            if self.fallback_on_error:
                response = self.template_generator.generate(
                    result,
                    intent,
                    modality,
                    context=self._extract_context_dict(conversation_state),
                    user_preferences=user_preferences,
                )
                yield response.text
            else:
                raise

    async def _generate_with_llm(
        self,
        result: ExecutionResult,
        intent: Intent,
        modality: ResponseModality,
        conversation_state: Optional[ConversationState] = None,
        user_preferences: Optional[dict[str, Any]] = None,
    ) -> Response:
        """
        Generate response using LLM.

        Args:
            result: Execution result
            intent: User intent
            modality: Response modality
            conversation_state: Optional conversation state
            user_preferences: Optional user preferences

        Returns:
            Response object

        Raises:
            RuntimeError: If LLM generation fails
        """
        # Create prompt
        prompt = self._create_response_prompt(
            result, intent, modality, conversation_state, user_preferences
        )

        # Create LLM request
        llm_request = LLMRequest(
            prompt=prompt,
            max_tokens=200,  # Concise responses
            temperature=0.7,  # Balanced creativity
            stream=False,
        )

        # Generate with timeout
        try:
            llm_response: LLMResponse = await asyncio.wait_for(
                self.llm_router.generate(llm_request), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"LLM generation timed out after {self.timeout_seconds}s")

        # Parse response text
        response_text = llm_response.text.strip()

        # Create Response object
        response = Response(
            text=response_text,
            modality=modality,
            metadata={
                "generation_method": "llm",
                "llm_provider": llm_response.provider.value if llm_response.provider else "unknown",
                "llm_latency_ms": llm_response.latency_ms,
            },
            suggestions=self._generate_suggestions(
                intent, result, conversation_state, user_preferences
            ),
        )

        return response

    def _create_response_prompt(
        self,
        result: ExecutionResult,
        intent: Intent,
        modality: ResponseModality,
        conversation_state: Optional[ConversationState] = None,
        user_preferences: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Create prompt for response generation.

        Args:
            result: Execution result
            intent: User intent
            modality: Response modality
            conversation_state: Optional conversation state
            user_preferences: Optional user preferences

        Returns:
            Formatted prompt string
        """
        # Extract conversation context
        context = self._extract_conversation_context(conversation_state)

        # Format modality instructions
        if modality == ResponseModality.VOICE:
            modality_instructions = (
                "Voice output: Be very concise (1-2 sentences max). "
                "Avoid lists, bullet points, or long explanations."
            )
        else:
            modality_instructions = (
                "Text output: Can be slightly more detailed. " "Use clear formatting if helpful."
            )

        # Format entities
        entities_str = json.dumps(
            {k: (v.value if hasattr(v, "value") else v) for k, v in intent.entities.items()},
            indent=2,
        )

        # Format result data
        result_data_str = json.dumps(result.result_data, indent=2) if result.result_data else "None"

        # Create prompt
        prompt = self.RESPONSE_TEMPLATE.format(
            user_input=intent.original_input if hasattr(intent, "original_input") else "N/A",
            intent_type=intent.intent_type,
            entities=entities_str,
            success=result.success,
            result_data=result_data_str,
            error=result.error if result.error else "None",
            execution_time=result.execution_time if hasattr(result, "execution_time") else 0.0,
            context=context.format_for_prompt() if context else "No context available.",
            modality=modality.value,
            modality_instructions=modality_instructions,
        )

        return prompt

    def _extract_conversation_context(
        self, conversation_state: Optional[ConversationState]
    ) -> Optional[ConversationContext]:
        """
        Extract conversation context from state.

        Args:
            conversation_state: Conversation state

        Returns:
            ConversationContext or None
        """
        if not conversation_state:
            return None

        # Extract recent turns (last 5)
        recent_turns = []
        for turn in list(conversation_state.turns)[-5:]:
            turn_text = f"User: {turn.user_input} | Response: {turn.response}"
            recent_turns.append(turn_text)

        # Extract tracked entities
        tracked_entities = {
            entity.entity_type: entity.value for entity in conversation_state.entities.values()
        }

        # Extract user preferences (if available)
        user_preferences = (
            conversation_state.user_preferences
            if hasattr(conversation_state, "user_preferences")
            else {}
        )

        # Extract past actions
        past_actions = []
        for turn in list(conversation_state.turns)[-3:]:
            if turn.action_taken:
                past_actions.append(f"{turn.action_taken.tool_id}: {turn.action_taken.parameters}")

        return ConversationContext(
            recent_turns=recent_turns,
            tracked_entities=tracked_entities,
            user_preferences=user_preferences,
            past_actions=past_actions,
        )

    def _extract_context_dict(
        self, conversation_state: Optional[ConversationState]
    ) -> dict[str, Any]:
        """
        Extract context as dictionary for template generator.

        Args:
            conversation_state: Conversation state

        Returns:
            Context dictionary
        """
        if not conversation_state:
            return {}

        context = {}

        # Add recent entities
        for entity in conversation_state.entities.values():
            context[entity.entity_type] = entity.value

        return context

    def _generate_suggestions(
        self,
        intent: Intent,
        result: ExecutionResult,
        conversation_state: Optional[Any] = None,
        user_preferences: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        """
        Generate follow-up suggestions using proactive suggestion generator.

        Args:
            intent: User intent
            result: Execution result
            conversation_state: Optional conversation state
            user_preferences: Optional user preferences

        Returns:
            List of suggestion strings
        """
        # Use proactive suggestion generator if available
        if self._proactive_generator:
            return self._proactive_generator.generate_suggestions(
                intent, result, conversation_state, user_preferences
            )

        # Fallback to template generator's suggestion logic
        return self.template_generator._get_intent_suggestions(intent.intent_type)

    def set_proactive_generator(self, generator: Any) -> None:
        """
        Set proactive suggestion generator.

        Args:
            generator: ProactiveSuggestionGenerator instance
        """
        self._proactive_generator = generator
        logger.info("Proactive suggestion generator set for LLM generator")
