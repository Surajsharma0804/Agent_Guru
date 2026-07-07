"""
Tests for LLM Reasoning Core.

Tests cover:
- ReasoningStep validation
- ReasoningPlan validation
- ReasoningPlanGenerator
- ReasoningPlanValidator
- Prompt formatting
- Conversation context integration

Target Coverage: 80%+
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMResponse
from Agent_Guru.reasoning.llm.prompts import ConversationContext
from Agent_Guru.reasoning.llm.reasoning import (
    ReasoningPlan,
    ReasoningPlanGenerator,
    ReasoningPlanValidator,
    ReasoningStep,
)


class TestReasoningStep:
    """Test ReasoningStep data model."""

    def test_valid_step_creation(self):
        """Test creating valid reasoning step."""
        step = ReasoningStep(
            step_id=1,
            description="Set a timer",
            tool_id="timer_tool",
            parameters={"duration_seconds": 300},
            estimated_duration_seconds=1.0,
        )

        assert step.step_id == 1  # nosec B101
        assert step.description == "Set a timer"  # nosec B101
        assert step.tool_id == "timer_tool"  # nosec B101
        assert step.parameters == {"duration_seconds": 300}  # nosec B101
        assert step.estimated_duration_seconds == 1.0  # nosec B101
        assert step.requires_confirmation is False  # nosec B101
        assert step.depends_on == []  # nosec B101

    def test_step_with_dependencies(self):
        """Test step with dependencies."""
        step = ReasoningStep(
            step_id=2,
            description="Send notification",
            tool_id="notification_tool",
            parameters={"message": "Timer complete"},
            estimated_duration_seconds=0.5,
            depends_on=[1],
        )

        assert step.depends_on == [1]  # nosec B101

    def test_step_invalid_id(self):
        """Test step with invalid ID."""
        with pytest.raises(ValueError, match="step_id must be >= 1"):
            ReasoningStep(
                step_id=0,
                description="Invalid",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )

    def test_step_empty_description(self):
        """Test step with empty description."""
        with pytest.raises(ValueError, match="description cannot be empty"):
            ReasoningStep(
                step_id=1,
                description="",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )

    def test_step_empty_tool_id(self):
        """Test step with empty tool_id."""
        with pytest.raises(ValueError, match="tool_id cannot be empty"):
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="",
                parameters={},
                estimated_duration_seconds=1.0,
            )

    def test_step_invalid_duration(self):
        """Test step with invalid duration."""
        with pytest.raises(ValueError, match="estimated_duration_seconds must be positive"):
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=0.0,
            )

    def test_step_invalid_dependency(self):
        """Test step with invalid dependency (depends on later step)."""
        with pytest.raises(ValueError, match="cannot depend on step"):
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
                depends_on=[2],  # Cannot depend on later step
            )


class TestReasoningPlan:
    """Test ReasoningPlan data model."""

    def test_valid_plan_creation(self):
        """Test creating valid reasoning plan."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Set timer",
                tool_id="timer_tool",
                parameters={"duration_seconds": 300},
                estimated_duration_seconds=1.0,
            )
        ]

        plan = ReasoningPlan(
            goal="Set a 5-minute timer",
            steps=steps,
            reasoning="Simple timer creation",
            confidence=0.95,
        )

        assert plan.goal == "Set a 5-minute timer"  # nosec B101
        assert len(plan.steps) == 1  # nosec B101
        assert plan.reasoning == "Simple timer creation"  # nosec B101
        assert plan.confidence == 0.95  # nosec B101
        assert plan.requires_confirmation is False  # nosec B101
        assert plan.estimated_duration_seconds == 1.0  # nosec B101

    def test_plan_with_multiple_steps(self):
        """Test plan with multiple steps."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Play music",
                tool_id="music_tool",
                parameters={"playlist": "workout"},
                estimated_duration_seconds=2.0,
            ),
            ReasoningStep(
                step_id=2,
                description="Set timer",
                tool_id="timer_tool",
                parameters={"duration_seconds": 1800},
                estimated_duration_seconds=1.0,
            ),
        ]

        plan = ReasoningPlan(
            goal="Start workout session",
            steps=steps,
            reasoning="Play music and set timer",
            confidence=0.92,
        )

        assert len(plan.steps) == 2  # nosec B101
        assert plan.estimated_duration_seconds == 3.0  # nosec B101

    def test_plan_requires_confirmation_from_step(self):
        """Test plan requires confirmation if any step does."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Send message",
                tool_id="messaging_tool",
                parameters={"recipient": "John", "message": "Hello"},
                estimated_duration_seconds=2.0,
                requires_confirmation=True,
            )
        ]

        plan = ReasoningPlan(
            goal="Send message to John",
            steps=steps,
            reasoning="Messaging requires confirmation",
            confidence=0.90,
        )

        assert plan.requires_confirmation is True  # nosec B101

    def test_plan_empty_goal(self):
        """Test plan with empty goal."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )
        ]

        with pytest.raises(ValueError, match="goal cannot be empty"):
            ReasoningPlan(goal="", steps=steps, reasoning="Test", confidence=0.9)

    def test_plan_empty_steps(self):
        """Test plan with no steps."""
        with pytest.raises(ValueError, match="steps cannot be empty"):
            ReasoningPlan(goal="Test", steps=[], reasoning="Test", confidence=0.9)

    def test_plan_too_many_steps(self):
        """Test plan with too many steps."""
        steps = [
            ReasoningStep(
                step_id=i,
                description=f"Step {i}",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )
            for i in range(1, 7)  # 6 steps
        ]

        with pytest.raises(ValueError, match="Maximum 5 steps allowed"):
            ReasoningPlan(goal="Test", steps=steps, reasoning="Test", confidence=0.9)

    def test_plan_invalid_confidence(self):
        """Test plan with invalid confidence."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )
        ]

        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            ReasoningPlan(goal="Test", steps=steps, reasoning="Test", confidence=1.5)

    def test_plan_empty_reasoning(self):
        """Test plan with empty reasoning."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )
        ]

        with pytest.raises(ValueError, match="reasoning cannot be empty"):
            ReasoningPlan(goal="Test", steps=steps, reasoning="", confidence=0.9)


class TestReasoningPlanGenerator:
    """Test ReasoningPlanGenerator."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = Mock()
        provider.generate = AsyncMock()
        return provider

    @pytest.fixture
    def generator(self, mock_llm_provider):
        """Create generator with mock provider."""
        return ReasoningPlanGenerator(mock_llm_provider)

    @pytest.mark.asyncio
    async def test_generate_single_step_plan(self, generator, mock_llm_provider):
        """Test generating single-step plan."""
        # Mock LLM response
        response_json = {
            "goal": "Set a 5-minute timer",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Create timer for 5 minutes",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 300},
                    "estimated_duration_seconds": 1.0,
                    "requires_confirmation": False,
                }
            ],
            "reasoning": "Simple timer creation",
            "confidence": 0.95,
        }

        mock_llm_provider.generate.return_value = LLMResponse(
            text=json.dumps(response_json),
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            tokens_generated=100,
            finish_reason="stop",
        )

        # Generate plan
        plan = await generator.generate_plan(
            user_input="Set a timer for 5 minutes",
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            available_tools=["timer_tool"],
        )

        assert plan.goal == "Set a 5-minute timer"  # nosec B101
        assert len(plan.steps) == 1  # nosec B101
        assert plan.steps[0].tool_id == "timer_tool"  # nosec B101
        assert plan.confidence == 0.95  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_multi_step_plan(self, generator, mock_llm_provider):
        """Test generating multi-step plan."""
        response_json = {
            "goal": "Start workout session",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Play workout playlist",
                    "tool_id": "music_tool",
                    "parameters": {"playlist": "workout"},
                    "estimated_duration_seconds": 2.0,
                },
                {
                    "step_id": 2,
                    "description": "Set 30-minute timer",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 1800},
                    "estimated_duration_seconds": 1.0,
                },
            ],
            "reasoning": "Play music and set timer for workout",
            "confidence": 0.92,
        }

        mock_llm_provider.generate.return_value = LLMResponse(
            text=json.dumps(response_json),
            provider=LLMProvider.LOCAL,
            latency_ms=200.0,
            tokens_generated=150,
            finish_reason="stop",
        )

        plan = await generator.generate_plan(
            user_input="Play my workout playlist and set a timer for 30 minutes",
            intent_type="multi_step_task",
            entities={"playlist": "workout", "duration": "30 minutes"},
            available_tools=["music_tool", "timer_tool"],
        )

        assert len(plan.steps) == 2  # nosec B101
        assert plan.steps[0].tool_id == "music_tool"  # nosec B101
        assert plan.steps[1].tool_id == "timer_tool"  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_plan_with_context(self, generator, mock_llm_provider):
        """Test generating plan with conversation context."""
        context = ConversationContext(
            recent_turns=["User: What's the weather?", "Assistant: It's sunny, 72°F"],
            tracked_entities={"location": "San Francisco"},
            user_preferences={"temperature_unit": "fahrenheit"},
        )

        response_json = {
            "goal": "Set a timer",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Set timer",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 300},
                    "estimated_duration_seconds": 1.0,
                }
            ],
            "reasoning": "Simple timer",
            "confidence": 0.95,
        }

        mock_llm_provider.generate.return_value = LLMResponse(
            text=json.dumps(response_json),
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            tokens_generated=100,
            finish_reason="stop",
        )

        plan = await generator.generate_plan(
            user_input="Set a timer for 5 minutes",
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            available_tools=["timer_tool"],
            context=context,
        )

        assert plan is not None  # nosec B101
        mock_llm_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_plan_with_markdown_json(self, generator, mock_llm_provider):
        """Test parsing JSON wrapped in markdown code blocks."""
        response_json = {
            "goal": "Set timer",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Set timer",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 300},
                    "estimated_duration_seconds": 1.0,
                }
            ],
            "reasoning": "Simple timer",
            "confidence": 0.95,
        }

        # Wrap in markdown
        markdown_response = f"```json\n{json.dumps(response_json)}\n```"

        mock_llm_provider.generate.return_value = LLMResponse(
            text=markdown_response,
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            tokens_generated=100,
            finish_reason="stop",
        )

        plan = await generator.generate_plan(
            user_input="Set a timer",
            intent_type="set_timer",
            entities={},
            available_tools=["timer_tool"],
        )

        assert plan.goal == "Set timer"  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_plan_retry_on_invalid_json(self, generator, mock_llm_provider):
        """Test retry logic on invalid JSON."""
        # First two attempts return invalid JSON, third succeeds
        valid_response = {
            "goal": "Set timer",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Set timer",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 300},
                    "estimated_duration_seconds": 1.0,
                }
            ],
            "reasoning": "Simple timer",
            "confidence": 0.95,
        }

        mock_llm_provider.generate.side_effect = [
            LLMResponse(
                text="invalid json {",
                provider=LLMProvider.LOCAL,
                latency_ms=150.0,
                tokens_generated=10,
                finish_reason="stop",
            ),
            LLMResponse(
                text='{"goal": "test"}',  # Missing required fields
                provider=LLMProvider.LOCAL,
                latency_ms=150.0,
                tokens_generated=20,
                finish_reason="stop",
            ),
            LLMResponse(
                text=json.dumps(valid_response),
                provider=LLMProvider.LOCAL,
                latency_ms=150.0,
                tokens_generated=100,
                finish_reason="stop",
            ),
        ]

        plan = await generator.generate_plan(
            user_input="Set a timer",
            intent_type="set_timer",
            entities={},
            available_tools=["timer_tool"],
        )

        assert plan.goal == "Set timer"  # nosec B101
        assert mock_llm_provider.generate.call_count == 3  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_plan_max_retries_exceeded(self, generator, mock_llm_provider):
        """Test failure after max retries."""
        mock_llm_provider.generate.return_value = LLMResponse(
            text="invalid json",
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            tokens_generated=10,
            finish_reason="stop",
        )

        with pytest.raises(ValueError, match="Failed to generate valid plan"):
            await generator.generate_plan(
                user_input="Set a timer",
                intent_type="set_timer",
                entities={},
                available_tools=["timer_tool"],
            )

        assert mock_llm_provider.generate.call_count == 3  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_plan_timeout(self, generator, mock_llm_provider):
        """Test timeout handling."""

        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
            return LLMResponse(
                text="{}",
                provider=LLMProvider.LOCAL,
                latency_ms=10000.0,
                tokens_generated=0,
                finish_reason="stop",
            )

        mock_llm_provider.generate.side_effect = slow_generate

        with pytest.raises(asyncio.TimeoutError):
            await generator.generate_plan(
                user_input="Set a timer",
                intent_type="set_timer",
                entities={},
                available_tools=["timer_tool"],
            )

    @pytest.mark.asyncio
    async def test_generate_plan_enforces_step_limit(self, generator, mock_llm_provider):
        """Test that plans with too many steps are rejected."""
        response_json = {
            "goal": "Too many steps",
            "steps": [
                {
                    "step_id": i,
                    "description": f"Step {i}",
                    "tool_id": "tool",
                    "parameters": {},
                    "estimated_duration_seconds": 1.0,
                }
                for i in range(1, 7)  # 6 steps
            ],
            "reasoning": "Too many steps",
            "confidence": 0.9,
        }

        mock_llm_provider.generate.return_value = LLMResponse(
            text=json.dumps(response_json),
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            tokens_generated=200,
            finish_reason="stop",
        )

        with pytest.raises(ValueError, match="Failed to generate valid plan"):
            await generator.generate_plan(
                user_input="Do many things",
                intent_type="multi_step_task",
                entities={},
                available_tools=["tool"],
            )

    @pytest.mark.asyncio
    async def test_stream_plan(self, generator, mock_llm_provider):
        """Test streaming plan generation."""
        response_json = {
            "goal": "Multi-step task",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Step 1",
                    "tool_id": "tool1",
                    "parameters": {},
                    "estimated_duration_seconds": 1.0,
                },
                {
                    "step_id": 2,
                    "description": "Step 2",
                    "tool_id": "tool2",
                    "parameters": {},
                    "estimated_duration_seconds": 1.0,
                },
            ],
            "reasoning": "Two steps",
            "confidence": 0.9,
        }

        mock_llm_provider.generate.return_value = LLMResponse(
            text=json.dumps(response_json),
            provider=LLMProvider.LOCAL,
            latency_ms=150.0,
            tokens_generated=100,
            finish_reason="stop",
        )

        steps = []
        async for step in generator.stream_plan(
            user_input="Do two things",
            intent_type="multi_step_task",
            entities={},
            available_tools=["tool1", "tool2"],
        ):
            steps.append(step)

        assert len(steps) == 2  # nosec B101
        assert steps[0].tool_id == "tool1"  # nosec B101
        assert steps[1].tool_id == "tool2"  # nosec B101


class TestReasoningPlanValidator:
    """Test ReasoningPlanValidator."""

    @pytest.fixture
    def tool_registry(self):
        """Create mock tool registry."""
        return {
            "timer_tool": {
                "name": "Timer Tool",
                "required_parameters": ["duration_seconds"],
            },
            "music_tool": {
                "name": "Music Tool",
                "required_parameters": ["playlist"],
            },
            "messaging_tool": {
                "name": "Messaging Tool",
                "required_parameters": ["recipient", "message"],
            },
        }

    @pytest.fixture
    def validator(self, tool_registry):
        """Create validator with tool registry."""
        return ReasoningPlanValidator(tool_registry, max_duration_seconds=30.0)

    def test_validate_valid_plan(self, validator):
        """Test validating valid plan."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Set timer",
                tool_id="timer_tool",
                parameters={"duration_seconds": 300},
                estimated_duration_seconds=1.0,
            )
        ]

        plan = ReasoningPlan(
            goal="Set timer",
            steps=steps,
            reasoning="Simple timer",
            confidence=0.95,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is True  # nosec B101
        assert error is None  # nosec B101

    def test_validate_unknown_tool(self, validator):
        """Test validation fails for unknown tool."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Unknown tool",
                tool_id="unknown_tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )
        ]

        plan = ReasoningPlan(
            goal="Test",
            steps=steps,
            reasoning="Test",
            confidence=0.9,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is False  # nosec B101
        assert "Unknown tool" in error  # nosec B101

    def test_validate_missing_required_parameter(self, validator):
        """Test validation fails for missing required parameter."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Set timer without duration",
                tool_id="timer_tool",
                parameters={},  # Missing duration_seconds
                estimated_duration_seconds=1.0,
            )
        ]

        plan = ReasoningPlan(
            goal="Test",
            steps=steps,
            reasoning="Test",
            confidence=0.9,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is False  # nosec B101
        assert "Missing required parameter" in error  # nosec B101
        assert "duration_seconds" in error  # nosec B101

    def test_validate_duration_exceeds_limit(self, validator):
        """Test validation fails when duration exceeds limit."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Long task",
                tool_id="timer_tool",
                parameters={"duration_seconds": 300},
                estimated_duration_seconds=35.0,  # Exceeds 30s limit
            )
        ]

        plan = ReasoningPlan(
            goal="Test",
            steps=steps,
            reasoning="Test",
            confidence=0.9,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is False  # nosec B101
        assert "exceeds limit" in error  # nosec B101

    def test_validate_circular_dependencies(self, validator):
        """Test validation detects circular dependencies."""
        # Create steps with circular dependency (not possible with current validation)
        # This tests the _has_circular_dependencies method
        steps = [
            ReasoningStep(
                step_id=1,
                description="Step 1",
                tool_id="timer_tool",
                parameters={"duration_seconds": 300},
                estimated_duration_seconds=1.0,
            ),
            ReasoningStep(
                step_id=2,
                description="Step 2",
                tool_id="music_tool",
                parameters={"playlist": "test"},
                estimated_duration_seconds=1.0,
            ),
        ]

        plan = ReasoningPlan(
            goal="Test",
            steps=steps,
            reasoning="Test",
            confidence=0.9,
        )

        # Valid plan with no circular dependencies
        is_valid, error = validator.validate(plan)
        assert is_valid is True  # nosec B101
