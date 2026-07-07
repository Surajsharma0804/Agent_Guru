"""
Tests for LLM-based response generator.

Coverage target: 80%+
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.router import HybridLLMRouter
from Agent_Guru.reasoning.models.conversation import (
    ConversationState,
    ConversationTurn,
    TrackedEntity,
)
from Agent_Guru.reasoning.models.intent import Entity, EntityType, Intent, IntentType
from Agent_Guru.reasoning.models.result import ExecutionResult, ResponseModality
from Agent_Guru.reasoning.response.llm_generator import LLMResponseGenerator
from Agent_Guru.reasoning.response.template_generator import TemplateGenerator


@pytest.fixture
def mock_llm_router():
    """Create mock LLM router."""
    router = Mock(spec=HybridLLMRouter)
    router.generate = AsyncMock()
    return router


@pytest.fixture
def template_generator():
    """Create real template generator for fallback."""
    return TemplateGenerator()


@pytest.fixture
def llm_generator(mock_llm_router, template_generator):
    """Create LLM response generator with mocks."""
    return LLMResponseGenerator(
        llm_router=mock_llm_router,
        template_generator=template_generator,
        enable_streaming=True,
        fallback_on_error=True,
        timeout_seconds=2.0,
    )


@pytest.fixture
def sample_intent():
    """Create sample intent."""
    return Intent(
        intent_type=IntentType.SET_TIMER,
        entities={
            "duration": Entity(
                entity_type=EntityType.DURATION,
                value="5 minutes",
                raw_text="5 minutes",
                confidence=0.95,
            )
        },
        confidence=0.95,
        requires_reasoning=False,
        original_input="Set a timer for 5 minutes",
    )


@pytest.fixture
def sample_result():
    """Create sample execution result."""
    return ExecutionResult(
        success=True,
        result_data={"timer": "5 minutes", "timer_id": "timer_123"},
        error=None,
        execution_time=1.2,
        action_id="action_123",
        tool_id="timer_tool",
    )


@pytest.fixture
def sample_conversation_state():
    """Create sample conversation state."""
    state = ConversationState(
        conversation_id="conv_123",
        user_id="user_123",
        turns=[
            ConversationTurn(
                turn_id="turn_1",
                user_input="What's the weather?",
                resolved_input="What's the weather?",
                intent=Intent(
                    intent_type=IntentType.QUERY_WEATHER,
                    entities={},
                    confidence=0.9,
                    requires_reasoning=False,
                    original_input="What's the weather?",
                ),
                response="It's sunny and 72°F",
            )
        ],
        entities={
            "location": TrackedEntity(
                entity_type=EntityType.LOCATION,
                value="San Francisco",
                first_mentioned=1,
                last_mentioned=1,
                mention_count=1,
            )
        },
    )
    return state


class TestLLMResponseGenerator:
    """Test LLM response generator."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_llm_router, template_generator):
        """Test generator initialization."""
        generator = LLMResponseGenerator(
            llm_router=mock_llm_router,
            template_generator=template_generator,
            enable_streaming=True,
            fallback_on_error=True,
            timeout_seconds=2.0,
        )

        assert generator.llm_router == mock_llm_router  # nosec B101
        assert generator.template_generator == template_generator  # nosec B101
        assert generator.enable_streaming is True  # nosec B101
        assert generator.fallback_on_error is True  # nosec B101
        assert generator.timeout_seconds == 2.0  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_success(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test successful LLM response generation."""
        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="I've set a timer for 5 minutes",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=50,
            completion_tokens=10,
        )

        # Generate response
        response = await llm_generator.generate(
            result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
        )

        # Verify response
        assert response.text == "I've set a timer for 5 minutes"  # nosec B101
        assert response.modality == ResponseModality.VOICE  # nosec B101
        assert response.metadata["generation_method"] == "llm"  # nosec B101
        assert response.metadata["llm_provider"] == "local"  # nosec B101
        assert "llm_latency_ms" in response.metadata  # nosec B101

        # Verify LLM was called
        mock_llm_router.generate.assert_called_once()
        call_args = mock_llm_router.generate.call_args[0][0]
        assert isinstance(call_args, LLMRequest)  # nosec B101
        assert "Set a timer for 5 minutes" in call_args.prompt  # nosec B101
        assert call_args.max_tokens == 200  # nosec B101
        assert call_args.temperature == 0.7  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_with_conversation_context(
        self,
        llm_generator,
        mock_llm_router,
        sample_intent,
        sample_result,
        sample_conversation_state,
    ):
        """Test response generation with conversation context."""
        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="Timer set for 5 minutes",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=100,
            completion_tokens=10,
        )

        # Generate response with context
        response = await llm_generator.generate(
            result=sample_result,
            intent=sample_intent,
            modality=ResponseModality.TEXT,
            conversation_state=sample_conversation_state,
        )

        # Verify response
        assert response.text == "Timer set for 5 minutes"  # nosec B101
        assert response.modality == ResponseModality.TEXT  # nosec B101

        # Verify context was included in prompt
        call_args = mock_llm_router.generate.call_args[0][0]
        assert "Recent conversation" in call_args.prompt or "context" in call_args.prompt.lower()  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_with_user_preferences(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test response generation with user preferences."""
        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="Timer set",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=50,
            completion_tokens=5,
        )

        # Generate response with preferences
        user_preferences = {"verbosity": "concise", "formality": "casual"}
        response = await llm_generator.generate(
            result=sample_result,
            intent=sample_intent,
            modality=ResponseModality.VOICE,
            user_preferences=user_preferences,
        )

        # Verify response
        assert response.text == "Timer set"  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_error_result(self, llm_generator, mock_llm_router, sample_intent):
        """Test response generation for error result."""
        # Create error result
        error_result = ExecutionResult(
            success=False,
            result_data=None,
            error="Timer service unavailable",
            execution_time=0.5,
            action_id="action_123",
            tool_id="timer_tool",
        )

        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="Sorry, I couldn't set the timer. The timer service is currently unavailable.",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=60,
            completion_tokens=15,
        )

        # Generate response
        response = await llm_generator.generate(
            result=error_result, intent=sample_intent, modality=ResponseModality.TEXT
        )

        # Verify error response
        assert "couldn't" in response.text.lower() or "unavailable" in response.text.lower()  # nosec B101
        assert response.metadata["generation_method"] == "llm"  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_fallback_on_llm_error(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test fallback to template generator on LLM error."""
        # Mock LLM to raise error
        mock_llm_router.generate.side_effect = RuntimeError("LLM unavailable")

        # Generate response (should fallback to template)
        response = await llm_generator.generate(
            result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
        )

        # Verify fallback response
        assert response.text  # Should have some text  # nosec B101
        assert response.metadata["generation_method"] == "template_fallback"  # nosec B101
        assert "llm_error" in response.metadata  # nosec B101
        assert "LLM unavailable" in response.metadata["llm_error"]  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_fallback_disabled(
        self, mock_llm_router, template_generator, sample_intent, sample_result
    ):
        """Test error when fallback is disabled."""
        # Create generator with fallback disabled
        generator = LLMResponseGenerator(
            llm_router=mock_llm_router,
            template_generator=template_generator,
            fallback_on_error=False,
        )

        # Mock LLM to raise error
        mock_llm_router.generate.side_effect = RuntimeError("LLM unavailable")

        # Should raise error (no fallback)
        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await generator.generate(
                result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
            )

    @pytest.mark.asyncio
    async def test_generate_timeout(
        self, mock_llm_router, template_generator, sample_intent, sample_result
    ):
        """Test timeout handling."""
        # Create generator with short timeout
        generator = LLMResponseGenerator(
            llm_router=mock_llm_router,
            template_generator=template_generator,
            timeout_seconds=0.1,
        )

        # Mock LLM to be slow
        async def slow_generate(request):
            await asyncio.sleep(1.0)
            return LLMResponse(text="Response", provider=LLMProvider.LOCAL, latency_ms=1000.0)

        mock_llm_router.generate.side_effect = slow_generate

        # Should timeout and fallback to template
        response = await generator.generate(
            result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
        )

        # Verify fallback response
        assert response.text  # nosec B101
        assert response.metadata["generation_method"] == "template_fallback"  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_voice_modality(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test voice modality generates concise responses."""
        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="Timer set for 5 minutes",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=50,
            completion_tokens=10,
        )

        # Generate voice response
        response = await llm_generator.generate(
            result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
        )

        # Verify prompt includes voice instructions
        call_args = mock_llm_router.generate.call_args[0][0]
        assert "voice" in call_args.prompt.lower()  # nosec B101
        assert "concise" in call_args.prompt.lower()  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_text_modality(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test text modality allows more detail."""
        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="I've successfully set a timer for 5 minutes. I'll notify you when it's done.",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=50,
            completion_tokens=20,
        )

        # Generate text response
        response = await llm_generator.generate(
            result=sample_result, intent=sample_intent, modality=ResponseModality.TEXT
        )

        # Verify prompt includes text instructions
        call_args = mock_llm_router.generate.call_args[0][0]
        assert "text" in call_args.prompt.lower()  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_includes_suggestions(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test response includes follow-up suggestions."""
        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="Timer set for 5 minutes",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=50,
            completion_tokens=10,
        )

        # Generate response
        response = await llm_generator.generate(
            result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
        )

        # Verify suggestions
        assert response.suggestions  # nosec B101
        assert len(response.suggestions) > 0  # nosec B101
        # Timer-related suggestions
        assert any("timer" in s.lower() for s in response.suggestions)  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_streaming_enabled(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test streaming response generation."""
        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="Timer set for 5 minutes",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=50,
            completion_tokens=10,
        )

        # Generate streaming response
        chunks = []
        async for chunk in llm_generator.generate_streaming(
            result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
        ):
            chunks.append(chunk)

        # Verify chunks
        assert len(chunks) > 0  # nosec B101
        full_text = "".join(chunks)
        assert "Timer" in full_text or "timer" in full_text  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_streaming_disabled(
        self, mock_llm_router, template_generator, sample_intent, sample_result
    ):
        """Test streaming when disabled."""
        # Create generator with streaming disabled
        generator = LLMResponseGenerator(
            llm_router=mock_llm_router,
            template_generator=template_generator,
            enable_streaming=False,
        )

        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="Timer set for 5 minutes",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            prompt_tokens=50,
            completion_tokens=10,
        )

        # Generate streaming response
        chunks = []
        async for chunk in generator.generate_streaming(
            result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
        ):
            chunks.append(chunk)

        # Should return full response in one chunk
        assert len(chunks) == 1  # nosec B101
        assert "Timer" in chunks[0] or "timer" in chunks[0]  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_streaming_fallback(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test streaming fallback on error."""
        # Mock LLM to raise error
        mock_llm_router.generate.side_effect = RuntimeError("LLM unavailable")

        # Generate streaming response (should fallback)
        chunks = []
        async for chunk in llm_generator.generate_streaming(
            result=sample_result, intent=sample_intent, modality=ResponseModality.VOICE
        ):
            chunks.append(chunk)

        # Verify fallback response
        assert len(chunks) > 0  # nosec B101
        full_text = "".join(chunks)
        assert full_text  # Should have some text from template  # nosec B101

    @pytest.mark.asyncio
    async def test_create_response_prompt(
        self, llm_generator, sample_intent, sample_result, sample_conversation_state
    ):
        """Test prompt creation."""
        prompt = llm_generator._create_response_prompt(
            result=sample_result,
            intent=sample_intent,
            modality=ResponseModality.VOICE,
            conversation_state=sample_conversation_state,
        )

        # Verify prompt contains key information
        assert "Set a timer for 5 minutes" in prompt  # nosec B101
        assert "set_timer" in prompt  # nosec B101
        assert "5 minutes" in prompt  # nosec B101
        assert "Success: True" in prompt  # nosec B101
        assert "voice" in prompt.lower()  # nosec B101

    @pytest.mark.asyncio
    async def test_extract_conversation_context(self, llm_generator, sample_conversation_state):
        """Test conversation context extraction."""
        context = llm_generator._extract_conversation_context(sample_conversation_state)

        # Verify context
        assert context is not None  # nosec B101
        assert len(context.recent_turns) > 0  # nosec B101
        assert "What's the weather?" in context.recent_turns[0]  # nosec B101
        assert "location" in context.tracked_entities  # nosec B101
        assert context.tracked_entities["location"] == "San Francisco"  # nosec B101

    @pytest.mark.asyncio
    async def test_extract_conversation_context_none(self, llm_generator):
        """Test context extraction with no state."""
        context = llm_generator._extract_conversation_context(None)
        assert context is None  # nosec B101

    @pytest.mark.asyncio
    async def test_extract_context_dict(self, llm_generator, sample_conversation_state):
        """Test context dictionary extraction."""
        context_dict = llm_generator._extract_context_dict(sample_conversation_state)

        # Verify context dict
        assert isinstance(context_dict, dict)  # nosec B101
        assert "location" in context_dict  # nosec B101
        assert context_dict["location"] == "San Francisco"  # nosec B101

    @pytest.mark.asyncio
    async def test_extract_context_dict_none(self, llm_generator):
        """Test context dict extraction with no state."""
        context_dict = llm_generator._extract_context_dict(None)
        assert context_dict == {}  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_suggestions(self, llm_generator, sample_intent, sample_result):
        """Test suggestion generation."""
        suggestions = llm_generator._generate_suggestions(sample_intent, sample_result)

        # Verify suggestions
        assert isinstance(suggestions, list)  # nosec B101
        assert len(suggestions) > 0  # nosec B101
        # Should have timer-related suggestions
        assert any("timer" in s.lower() for s in suggestions)  # nosec B101


class TestLLMResponseGeneratorIntegration:
    """Integration tests for LLM response generator."""

    @pytest.mark.asyncio
    async def test_end_to_end_success_flow(
        self, llm_generator, mock_llm_router, sample_intent, sample_result
    ):
        """Test complete success flow."""
        # Mock LLM response
        mock_llm_router.generate.return_value = LLMResponse(
            text="I've set a timer for 5 minutes. I'll let you know when it's done.",
            provider=LLMProvider.CLOUD,
            latency_ms=180.0,
            prompt_tokens=75,
            completion_tokens=15,
        )

        # Generate response
        response = await llm_generator.generate(
            result=sample_result, intent=sample_intent, modality=ResponseModality.TEXT
        )

        # Verify complete response
        assert response.text  # nosec B101
        assert response.modality == ResponseModality.TEXT  # nosec B101
        assert response.metadata["generation_method"] == "llm"  # nosec B101
        assert response.metadata["llm_provider"] == "cloud"  # nosec B101
        assert response.suggestions  # nosec B101
        assert len(response.suggestions) > 0  # nosec B101

    @pytest.mark.asyncio
    async def test_end_to_end_error_flow(self, llm_generator, mock_llm_router, sample_intent):
        """Test complete error flow with fallback."""
        # Create error result
        error_result = ExecutionResult(
            success=False,
            result_data=None,
            error="Network timeout",
            execution_time=3.0,
            action_id="action_123",
            tool_id="timer_tool",
        )

        # Mock LLM to fail
        mock_llm_router.generate.side_effect = RuntimeError("LLM timeout")

        # Generate response (should fallback)
        response = await llm_generator.generate(
            result=error_result, intent=sample_intent, modality=ResponseModality.VOICE
        )

        # Verify fallback response
        assert response.text  # nosec B101
        assert response.metadata["generation_method"] == "template_fallback"  # nosec B101
        assert "llm_error" in response.metadata  # nosec B101
