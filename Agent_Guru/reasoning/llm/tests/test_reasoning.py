"""
Tests for LLM reasoning core.

Coverage Target: >80% (enforced by CI/CD)
"""

import json
from unittest.mock import AsyncMock, Mock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMResponse
from Agent_Guru.reasoning.llm.prompts import ConversationContext
from Agent_Guru.reasoning.llm.reasoning import (
    ReasoningPlan,
    ReasoningPlanGenerator,
    ReasoningStep,
)


class TestReasoningStep:
    """Unit tests for ReasoningStep."""

    def test_valid_step_creation(self):
        """Test creating a valid reasoning step."""
        step = ReasoningStep(
            step_id=1,
            description="Set a timer",
            tool_id="timer_tool",
            parameters={"duration": 300},
            estimated_duration_seconds=1.0,
        )

        assert step.step_id == 1
        assert step.description == "Set a timer"
        assert step.tool_id == "timer_tool"
        assert step.parameters == {"duration": 300}
        assert step.estimated_duration_seconds == 1.0
        assert step.requires_confirmation is False
        assert step.depends_on == []

    def test_step_with_dependencies(self):
        """Test step with dependencies."""
        step = ReasoningStep(
            step_id=2,
            description="Send notification",
            tool_id="notification_tool",
            parameters={},
            estimated_duration_seconds=0.5,
            depends_on=[1],
        )

        assert step.depends_on == [1]

    def test_invalid_step_id(self):
        """Test that step_id must be >= 1."""
        with pytest.raises(ValueError, match="step_id must be >= 1"):
            ReasoningStep(
                step_id=0,
                description="Invalid",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )

    def test_empty_description(self):
        """Test that description cannot be empty."""
        with pytest.raises(ValueError, match="description cannot be empty"):
            ReasoningStep(
                step_id=1,
                description="",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )

    def test_empty_tool_id(self):
        """Test that tool_id cannot be empty."""
        with pytest.raises(ValueError, match="tool_id cannot be empty"):
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="",
                parameters={},
                estimated_duration_seconds=1.0,
            )

    def test_invalid_duration(self):
        """Test that duration must be positive."""
        with pytest.raises(ValueError, match="estimated_duration_seconds must be positive"):
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="tool",
                parameters={},
                estimated_duration_seconds=0.0,
            )

    def test_invalid_dependency(self):
        """Test that dependencies must reference earlier steps."""
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
    """Unit tests for ReasoningPlan."""

    def test_valid_plan_creation(self):
        """Test creating a valid reasoning plan."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Step 1",
                tool_id="tool1",
                parameters={},
                estimated_duration_seconds=1.0,
            )
        ]

        plan = ReasoningPlan(
            goal="Complete task",
            steps=steps,
            reasoning="This is the best approach",
            confidence=0.95,
        )

        assert plan.goal == "Complete task"
        assert len(plan.steps) == 1
        assert plan.reasoning == "This is the best approach"
        assert plan.confidence == 0.95
        assert plan.estimated_duration_seconds == 1.0
        assert plan.requires_confirmation is False

    def test_plan_with_confirmation(self):
        """Test plan with confirmation requirement."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Send message",
                tool_id="messaging_tool",
                parameters={},
                estimated_duration_seconds=1.0,
                requires_confirmation=True,
            )
        ]

        plan = ReasoningPlan(
            goal="Send message",
            steps=steps,
            reasoning="Messaging requires confirmation",
            confidence=0.95,
        )

        assert plan.requires_confirmation is True

    def test_plan_duration_calculation(self):
        """Test automatic duration calculation."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Step 1",
                tool_id="tool1",
                parameters={},
                estimated_duration_seconds=1.0,
            ),
            ReasoningStep(
                step_id=2,
                description="Step 2",
                tool_id="tool2",
                parameters={},
                estimated_duration_seconds=2.0,
            ),
        ]

        plan = ReasoningPlan(
            goal="Multi-step task",
            steps=steps,
            reasoning="Two steps needed",
            confidence=0.90,
        )

        assert plan.estimated_duration_seconds == 3.0

    def test_empty_goal(self):
        """Test that goal cannot be empty."""
        with pytest.raises(ValueError, match="goal cannot be empty"):
            ReasoningPlan(
                goal="",
                steps=[],
                reasoning="Test",
                confidence=0.9,
            )

    def test_empty_steps(self):
        """Test that steps cannot be empty."""
        with pytest.raises(ValueError, match="steps cannot be empty"):
            ReasoningPlan(
                goal="Test",
                steps=[],
                reasoning="Test",
                confidence=0.9,
            )

    def test_too_many_steps(self):
        """Test that maximum 5 steps are allowed."""
        steps = [
            ReasoningStep(
                step_id=i,
                description=f"Step {i}",
                tool_id=f"tool{i}",
                parameters={},
                estimated_duration_seconds=1.0,
            )
            for i in range(1, 7)  # 6 steps
        ]

        with pytest.raises(ValueError, match="Maximum 5 steps allowed"):
            ReasoningPlan(
                goal="Too many steps",
                steps=steps,
                reasoning="Test",
                confidence=0.9,
            )

    def test_invalid_confidence(self):
        """Test that confidence must be 0.0-1.0."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Step 1",
                tool_id="tool1",
                parameters={},
                estimated_duration_seconds=1.0,
            )
        ]

        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            ReasoningPlan(
                goal="Test",
                steps=steps,
                reasoning="Test",
                confidence=1.5,
            )

    def test_empty_reasoning(self):
        """Test that reasoning cannot be empty."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Step 1",
                tool_id="tool1",
                parameters={},
                estimated_duration_seconds=1.0,
            )
        ]

        with pytest.raises(ValueError, match="reasoning cannot be empty"):
            ReasoningPlan(
                goal="Test",
                steps=steps,
                reasoning="",
                confidence=0.9,
            )


class TestReasoningPlanGenerator:
    """Unit tests for ReasoningPlanGenerator."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = Mock()
        provider.generate = AsyncMock()
        return provider

    @pytest.fixture
    def generator(self, mock_llm_provider):
        """Create reasoning plan generator."""
        return ReasoningPlanGenerator(mock_llm_provider)

    @pytest.mark.asyncio
    async def test_generate_single_step_plan(self, generator, mock_llm_provider):
        """Test generating a single-step plan."""
        # Mock LLM response
        mock_response = LLMResponse(
            text=json.dumps(
                {
                    "goal": "Set a timer for 5 minutes",
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
                    "confidence": 0.98,
                }
            ),
            provider=LLMProvider.OPENAI,
            latency_ms=150.0,
            tokens_generated=100,
            finish_reason="stop",
        )
        mock_llm_provider.generate.return_value = mock_response

        # Generate plan
        plan = await generator.generate_plan(
            user_input="Set a timer for 5 minutes",
            intent_type="set_timer",
            entities={"duration": "5 minutes"},
            available_tools=["timer_tool"],
        )

        # Verify plan
        assert plan.goal == "Set a timer for 5 minutes"
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_id == "timer_tool"
        assert plan.confidence == 0.98

    @pytest.mark.asyncio
    async def test_generate_multi_step_plan(self, generator, mock_llm_provider):
        """Test generating a multi-step plan."""
        # Mock LLM response
        mock_response = LLMResponse(
            text=json.dumps(
                {
                    "goal": "Start workout session",
                    "steps": [
                        {
                            "step_id": 1,
                            "description": "Play workout playlist",
                            "tool_id": "music_tool",
                            "parameters": {"playlist": "workout"},
                            "estimated_duration_seconds": 2.0,
                            "requires_confirmation": False,
                        },
                        {
                            "step_id": 2,
                            "description": "Set 30-minute timer",
                            "tool_id": "timer_tool",
                            "parameters": {"duration_seconds": 1800},
                            "estimated_duration_seconds": 1.0,
                            "requires_confirmation": False,
                        },
                    ],
                    "reasoning": "Two independent actions",
                    "confidence": 0.96,
                }
            ),
            provider=LLMProvider.OPENAI,
            latency_ms=200.0,
            tokens_generated=150,
            finish_reason="stop",
        )
        mock_llm_provider.generate.return_value = mock_response

        # Generate plan
        plan = await generator.generate_plan(
            user_input="Play music and set a timer",
            intent_type="multi_step_task",
            entities={"playlist": "workout", "duration": "30 minutes"},
            available_tools=["music_tool", "timer_tool"],
        )

        # Verify plan
        assert plan.goal == "Start workout session"
        assert len(plan.steps) == 2
        assert plan.steps[0].tool_id == "music_tool"
        assert plan.steps[1].tool_id == "timer_tool"

    @pytest.mark.asyncio
    async def test_generate_plan_with_context(self, generator, mock_llm_provider):
        """Test generating plan with conversation context."""
        # Mock LLM response
        mock_response = LLMResponse(
            text=json.dumps(
                {
                    "goal": "Send message to John",
                    "steps": [
                        {
                            "step_id": 1,
                            "description": "Send message",
                            "tool_id": "messaging_tool",
                            "parameters": {"recipient": "John", "message": "Hello"},
                            "estimated_duration_seconds": 2.0,
                            "requires_confirmation": True,
                        }
                    ],
                    "reasoning": "Messaging requires confirmation",
                    "confidence": 0.95,
                }
            ),
            provider=LLMProvider.OPENAI,
            latency_ms=180.0,
            tokens_generated=120,
            finish_reason="stop",
        )
        mock_llm_provider.generate.return_value = mock_response

        # Create context
        context = ConversationContext(
            recent_turns=["User: I need to contact John"],
            tracked_entities={"person": "John"},
        )

        # Generate plan
        plan = await generator.generate_plan(
            user_input="Send him a message",
            intent_type="send_message",
            entities={"recipient": "John"},
            available_tools=["messaging_tool"],
            context=context,
        )

        # Verify plan
        assert plan.goal == "Send message to John"
        assert plan.requires_confirmation is True

    @pytest.mark.asyncio
    async def test_generate_plan_retry_on_invalid_json(self, generator, mock_llm_provider):
        """Test retry logic on invalid JSON."""
        # First attempt: invalid JSON
        invalid_response = LLMResponse(
            text="This is not JSON",
            provider=LLMProvider.OPENAI,
            latency_ms=150.0,
            tokens_generated=50,
            finish_reason="stop",
        )

        # Second attempt: valid JSON
        valid_response = LLMResponse(
            text=json.dumps(
                {
                    "goal": "Test",
                    "steps": [
                        {
                            "step_id": 1,
                            "description": "Test step",
                            "tool_id": "test_tool",
                            "parameters": {},
                            "estimated_duration_seconds": 1.0,
                        }
                    ],
                    "reasoning": "Test",
                    "confidence": 0.9,
                }
            ),
            provider=LLMProvider.OPENAI,
            latency_ms=150.0,
            tokens_generated=100,
            finish_reason="stop",
        )

        mock_llm_provider.generate.side_effect = [invalid_response, valid_response]

        # Generate plan (should succeed on second attempt)
        plan = await generator.generate_plan(
            user_input="Test",
            intent_type="test",
            entities={},
            available_tools=["test_tool"],
        )

        assert plan.goal == "Test"
        assert mock_llm_provider.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_plan_fails_after_max_retries(self, generator, mock_llm_provider):
        """Test that generation fails after max retries."""
        # Always return invalid JSON
        invalid_response = LLMResponse(
            text="Invalid JSON",
            provider=LLMProvider.OPENAI,
            latency_ms=150.0,
            tokens_generated=50,
            finish_reason="stop",
        )
        mock_llm_provider.generate.return_value = invalid_response

        # Should fail after 3 attempts
        with pytest.raises(ValueError, match="Failed to generate valid plan"):
            await generator.generate_plan(
                user_input="Test",
                intent_type="test",
                entities={},
                available_tools=["test_tool"],
            )

        assert mock_llm_provider.generate.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_plan_enforces_step_limit(self, generator, mock_llm_provider):
        """Test that step limit is enforced."""
        # Mock response with 6 steps (exceeds limit)
        mock_response = LLMResponse(
            text=json.dumps(
                {
                    "goal": "Too many steps",
                    "steps": [
                        {
                            "step_id": i,
                            "description": f"Step {i}",
                            "tool_id": f"tool{i}",
                            "parameters": {},
                            "estimated_duration_seconds": 1.0,
                        }
                        for i in range(1, 7)
                    ],
                    "reasoning": "Test",
                    "confidence": 0.9,
                }
            ),
            provider=LLMProvider.OPENAI,
            latency_ms=200.0,
            tokens_generated=200,
            finish_reason="stop",
        )
        mock_llm_provider.generate.return_value = mock_response

        # Should fail due to step limit
        with pytest.raises(ValueError, match="Maximum 5 steps allowed"):
            await generator.generate_plan(
                user_input="Test",
                intent_type="test",
                entities={},
                available_tools=["test_tool"],
            )

    @pytest.mark.asyncio
    async def test_extract_json_from_markdown(self, generator):
        """Test extracting JSON from markdown code blocks."""
        # JSON wrapped in markdown
        markdown_json = """```json
{
    "goal": "Test",
    "steps": [],
    "reasoning": "Test",
    "confidence": 0.9
}
```"""

        extracted = generator._extract_json(markdown_json)
        data = json.loads(extracted)
        assert data["goal"] == "Test"

    @pytest.mark.asyncio
    async def test_is_multi_step_task(self, generator):
        """Test multi-step task detection."""
        # Explicit multi-step intent
        assert generator._is_multi_step_task("multi_step_task", {}) is True

        # Multiple actions indicated by "and"
        assert (
            generator._is_multi_step_task("test", {"actions": "play music and set timer"}) is True
        )

        # Single action
        assert generator._is_multi_step_task("set_timer", {"duration": "5 minutes"}) is False


@pytest.mark.asyncio
class TestReasoningPlanGeneratorIntegration:
    """Integration tests for ReasoningPlanGenerator."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider."""
        provider = Mock()
        provider.generate = AsyncMock()
        return provider

    @pytest.fixture
    def generator(self, mock_llm_provider):
        """Create reasoning plan generator."""
        return ReasoningPlanGenerator(mock_llm_provider)

    async def test_complete_workflow(self, generator, mock_llm_provider):
        """Test complete plan generation workflow."""
        # Mock LLM response
        mock_response = LLMResponse(
            text=json.dumps(
                {
                    "goal": "Complete workout session",
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
                    "reasoning": "Start workout with music and timer",
                    "confidence": 0.96,
                }
            ),
            provider=LLMProvider.OPENAI,
            latency_ms=250.0,
            tokens_generated=180,
            finish_reason="stop",
        )
        mock_llm_provider.generate.return_value = mock_response

        # Create context
        context = ConversationContext(
            recent_turns=["User: I'm starting my workout"],
            user_preferences={"workout_playlist": "Rock"},
        )

        # Generate plan
        plan = await generator.generate_plan(
            user_input="Start workout session with music and timer",
            intent_type="multi_step_task",
            entities={"playlist": "workout", "duration": "30 minutes"},
            available_tools=["music_tool", "timer_tool"],
            context=context,
        )

        # Verify complete plan
        assert plan.goal == "Complete workout session"
        assert len(plan.steps) == 2
        assert plan.steps[0].tool_id == "music_tool"
        assert plan.steps[0].parameters["playlist"] == "workout"
        assert plan.steps[1].tool_id == "timer_tool"
        assert plan.steps[1].parameters["duration_seconds"] == 1800
        assert plan.estimated_duration_seconds == 3.0
        assert plan.confidence == 0.96


class TestReasoningPlanValidator:
    """Unit tests for ReasoningPlanValidator."""

    @pytest.fixture
    def tool_registry(self):
        """Create mock tool registry."""
        return {
            "timer_tool": {
                "required_parameters": ["duration_seconds"],
            },
            "music_tool": {
                "required_parameters": ["playlist"],
            },
            "messaging_tool": {
                "required_parameters": ["recipient", "message"],
            },
            "weather_tool": {
                "required_parameters": [],
            },
        }

    @pytest.fixture
    def validator(self, tool_registry):
        """Create plan validator."""
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanValidator

        return ReasoningPlanValidator(tool_registry, max_duration_seconds=30.0)

    def test_validate_valid_plan(self, validator):
        """Test validating a valid plan."""
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
            goal="Set a timer",
            steps=steps,
            reasoning="Simple timer",
            confidence=0.95,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is True
        assert error is None

    def test_validate_unknown_tool(self, validator):
        """Test validation fails for unknown tool."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Unknown action",
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
        assert is_valid is False
        assert "Unknown tool" in error

    def test_validate_missing_required_parameter(self, validator):
        """Test validation fails for missing required parameter."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Set timer",
                tool_id="timer_tool",
                parameters={},  # Missing duration_seconds
                estimated_duration_seconds=1.0,
            )
        ]

        plan = ReasoningPlan(
            goal="Set timer",
            steps=steps,
            reasoning="Test",
            confidence=0.9,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is False
        assert "Missing required parameter" in error
        assert "duration_seconds" in error

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
            goal="Long task",
            steps=steps,
            reasoning="Test",
            confidence=0.9,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is False
        assert "exceeds limit" in error

    def test_validate_circular_dependencies(self, validator):
        """Test validation fails for circular dependencies."""

        # Create steps that form a cycle: 1 -> 2 -> 3 -> 1
        # We'll bypass the validation by creating steps first, then modifying depends_on
        step1 = ReasoningStep(
            step_id=1,
            description="Step 1",
            tool_id="timer_tool",
            parameters={"duration_seconds": 300},
            estimated_duration_seconds=1.0,
        )

        step2 = ReasoningStep(
            step_id=2,
            description="Step 2",
            tool_id="music_tool",
            parameters={"playlist": "workout"},
            estimated_duration_seconds=1.0,
            depends_on=[1],  # Valid: depends on earlier step
        )

        step3 = ReasoningStep(
            step_id=3,
            description="Step 3",
            tool_id="weather_tool",
            parameters={},
            estimated_duration_seconds=1.0,
            depends_on=[2],  # Valid: depends on earlier step
        )

        # Now manually create a cycle by modifying step1's depends_on
        # This simulates a malformed plan that bypassed validation
        step1.depends_on = [3]  # Creates cycle: 1 -> 3 -> 2 -> 1

        # Test circular dependency detection
        has_cycle = validator._has_circular_dependencies([step1, step2, step3])
        assert has_cycle is True

    def test_validate_valid_dependencies(self, validator):
        """Test validation passes for valid dependencies."""
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
                depends_on=[1],  # Depends on step 1 - valid
            ),
        ]

        plan = ReasoningPlan(
            goal="Workout session",
            steps=steps,
            reasoning="Music then timer",
            confidence=0.95,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is True
        assert error is None

    def test_validate_multiple_steps(self, validator):
        """Test validating multi-step plan."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Check weather",
                tool_id="weather_tool",
                parameters={},
                estimated_duration_seconds=1.0,
            ),
            ReasoningStep(
                step_id=2,
                description="Play music",
                tool_id="music_tool",
                parameters={"playlist": "chill"},
                estimated_duration_seconds=2.0,
            ),
            ReasoningStep(
                step_id=3,
                description="Set timer",
                tool_id="timer_tool",
                parameters={"duration_seconds": 600},
                estimated_duration_seconds=1.0,
            ),
        ]

        plan = ReasoningPlan(
            goal="Morning routine",
            steps=steps,
            reasoning="Check weather, play music, set timer",
            confidence=0.92,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is True
        assert error is None


@pytest.mark.integration
class TestReasoningPlanValidatorIntegration:
    """Integration tests for ReasoningPlanValidator."""

    def test_complete_validation_workflow(self):
        """Test complete plan validation workflow."""
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanValidator

        # Create tool registry
        tool_registry = {
            "timer_tool": {"required_parameters": ["duration_seconds"]},
            "music_tool": {"required_parameters": ["playlist"]},
        }

        # Create validator
        validator = ReasoningPlanValidator(tool_registry, max_duration_seconds=10.0)

        # Create valid plan
        valid_steps = [
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

        valid_plan = ReasoningPlan(
            goal="Start workout",
            steps=valid_steps,
            reasoning="Music and timer for workout",
            confidence=0.95,
        )

        # Validate
        is_valid, error = validator.validate(valid_plan)
        assert is_valid is True
        assert error is None

        # Create invalid plan (missing parameter)
        invalid_steps = [
            ReasoningStep(
                step_id=1,
                description="Set timer",
                tool_id="timer_tool",
                parameters={},  # Missing duration_seconds
                estimated_duration_seconds=1.0,
            )
        ]

        invalid_plan = ReasoningPlan(
            goal="Set timer",
            steps=invalid_steps,
            reasoning="Timer without duration",
            confidence=0.8,
        )

        # Validate
        is_valid, error = validator.validate(invalid_plan)
        assert is_valid is False
        assert "Missing required parameter" in error


class TestReasoningProperties:
    """Property-based tests for reasoning."""

    @given(
        num_steps=st.integers(min_value=1, max_value=5),
        confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_reasoning_plans_respect_step_limits(self, num_steps: int, confidence: float):
        """Property 9: Reasoning plans respect step limits (max 5 steps)."""
        steps = [
            ReasoningStep(
                step_id=i,
                description=f"Step {i}",
                tool_id=f"tool_{i}",
                parameters={},
                estimated_duration_seconds=1.0,
            )
            for i in range(1, num_steps + 1)
        ]

        plan = ReasoningPlan(
            goal="Test goal",
            steps=steps,
            reasoning="Test reasoning",
            confidence=confidence,
        )

        # Property: Number of steps must be <= 5
        assert len(plan.steps) <= 5
        assert len(plan.steps) == num_steps

    @given(
        num_steps=st.integers(min_value=6, max_value=10),
    )
    def test_too_many_steps_rejected(self, num_steps: int):
        """Property: Plans with >5 steps are rejected."""
        steps = [
            ReasoningStep(
                step_id=i,
                description=f"Step {i}",
                tool_id=f"tool_{i}",
                parameters={},
                estimated_duration_seconds=1.0,
            )
            for i in range(1, num_steps + 1)
        ]

        # Should raise ValueError
        with pytest.raises(ValueError, match="Maximum 5 steps allowed"):
            ReasoningPlan(
                goal="Test goal",
                steps=steps,
                reasoning="Test reasoning",
                confidence=0.9,
            )

    @given(
        step_id=st.integers(min_value=1, max_value=100),
        duration=st.floats(min_value=0.1, max_value=100.0),
    )
    def test_reasoning_steps_always_valid(self, step_id: int, duration: float):
        """Property: Valid reasoning steps can always be created."""
        step = ReasoningStep(
            step_id=step_id,
            description="Test step",
            tool_id="test_tool",
            parameters={"param": "value"},
            estimated_duration_seconds=duration,
        )

        assert step.step_id == step_id
        assert step.estimated_duration_seconds == duration
        assert step.tool_id == "test_tool"

    @given(
        num_steps=st.integers(min_value=1, max_value=5),
    )
    def test_plan_duration_is_sum_of_steps(self, num_steps: int):
        """Property: Plan duration equals sum of step durations."""
        step_durations = [float(i) for i in range(1, num_steps + 1)]

        steps = [
            ReasoningStep(
                step_id=i,
                description=f"Step {i}",
                tool_id=f"tool_{i}",
                parameters={},
                estimated_duration_seconds=step_durations[i - 1],
            )
            for i in range(1, num_steps + 1)
        ]

        plan = ReasoningPlan(
            goal="Test goal",
            steps=steps,
            reasoning="Test reasoning",
            confidence=0.9,
        )

        # Property: Total duration = sum of step durations
        expected_duration = sum(step_durations)
        assert abs(plan.estimated_duration_seconds - expected_duration) < 0.01

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_plan_confidence_always_valid(self, confidence: float):
        """Property: Plan confidence is always 0.0-1.0."""
        steps = [
            ReasoningStep(
                step_id=1,
                description="Test",
                tool_id="test_tool",
                parameters={},
                estimated_duration_seconds=1.0,
            )
        ]

        plan = ReasoningPlan(
            goal="Test",
            steps=steps,
            reasoning="Test",
            confidence=confidence,
        )

        assert 0.0 <= plan.confidence <= 1.0
        assert plan.confidence == confidence


class TestReasoningPlanValidationProperties:
    """Property-based tests for reasoning plan validation."""

    @given(
        num_steps=st.integers(min_value=1, max_value=5),
    )
    def test_plans_with_valid_tools_pass_validation(self, num_steps: int):
        """Property 11: Plans with valid tools always pass validation."""
        # Create tool registry and validator inside test (no fixtures with @given)
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanValidator

        tool_registry = {f"tool_{i}": {"required_parameters": []} for i in range(10)}
        validator = ReasoningPlanValidator(tool_registry, max_duration_seconds=100.0)

        steps = [
            ReasoningStep(
                step_id=i,
                description=f"Step {i}",
                tool_id=f"tool_{i % 10}",  # Use tools from registry
                parameters={},
                estimated_duration_seconds=1.0,
            )
            for i in range(1, num_steps + 1)
        ]

        plan = ReasoningPlan(
            goal="Test goal",
            steps=steps,
            reasoning="Test reasoning",
            confidence=0.9,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is True
        assert error is None

    @given(
        num_steps=st.integers(min_value=1, max_value=5),
    )
    def test_plans_with_invalid_tools_fail_validation(self, num_steps: int):
        """Property: Plans with invalid tools always fail validation."""
        # Create tool registry and validator inside test (no fixtures with @given)
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanValidator

        tool_registry = {f"tool_{i}": {"required_parameters": []} for i in range(10)}
        validator = ReasoningPlanValidator(tool_registry, max_duration_seconds=100.0)

        steps = [
            ReasoningStep(
                step_id=i,
                description=f"Step {i}",
                tool_id=f"invalid_tool_{i}",  # Not in registry
                parameters={},
                estimated_duration_seconds=1.0,
            )
            for i in range(1, num_steps + 1)
        ]

        plan = ReasoningPlan(
            goal="Test goal",
            steps=steps,
            reasoning="Test reasoning",
            confidence=0.9,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is False
        assert error is not None
        assert "Unknown tool" in error

    @given(
        duration=st.floats(min_value=101.0, max_value=1000.0),
    )
    def test_plans_exceeding_duration_fail_validation(self, duration: float):
        """Property: Plans exceeding max duration always fail validation."""
        # Create tool registry and validator inside test (no fixtures with @given)
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanValidator

        tool_registry = {f"tool_{i}": {"required_parameters": []} for i in range(10)}
        validator = ReasoningPlanValidator(tool_registry, max_duration_seconds=100.0)

        steps = [
            ReasoningStep(
                step_id=1,
                description="Long step",
                tool_id="tool_0",
                parameters={},
                estimated_duration_seconds=duration,
            )
        ]

        plan = ReasoningPlan(
            goal="Test goal",
            steps=steps,
            reasoning="Test reasoning",
            confidence=0.9,
        )

        is_valid, error = validator.validate(plan)
        assert is_valid is False
        assert error is not None
        assert "exceeds limit" in error

    @given(
        num_steps=st.integers(min_value=1, max_value=5),
        step_duration=st.floats(min_value=0.1, max_value=10.0),
    )
    def test_valid_plans_always_pass(self, num_steps: int, step_duration: float):
        """Property: Valid plans always pass validation."""
        # Create tool registry and validator inside test (no fixtures with @given)
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanValidator

        tool_registry = {f"tool_{i}": {"required_parameters": []} for i in range(10)}
        validator = ReasoningPlanValidator(tool_registry, max_duration_seconds=100.0)

        steps = [
            ReasoningStep(
                step_id=i,
                description=f"Step {i}",
                tool_id=f"tool_{i % 10}",
                parameters={},
                estimated_duration_seconds=step_duration,
            )
            for i in range(1, num_steps + 1)
        ]

        plan = ReasoningPlan(
            goal="Test goal",
            steps=steps,
            reasoning="Test reasoning",
            confidence=0.9,
        )

        # Only validate if total duration is within limit
        if plan.estimated_duration_seconds <= 100.0:
            is_valid, error = validator.validate(plan)
            assert is_valid is True
            assert error is None
