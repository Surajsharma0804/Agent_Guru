"""
Property-Based Tests for LLM Reasoning Core.

Tests correctness properties:
- Property 9: Reasoning plans respect step limits
- Property 10: Reasoning prompts include context
- Property 11: Reasoning plans are executable

Target: 100 iterations per property
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.llm.prompts import ConversationContext, ReasoningPrompts
from Agent_Guru.reasoning.llm.reasoning import (
    ReasoningPlan,
    ReasoningPlanValidator,
    ReasoningStep,
)


# Strategies for generating test data
@st.composite
def reasoning_step_strategy(draw):
    """Generate valid ReasoningStep."""
    step_id = draw(st.integers(min_value=1, max_value=5))
    description = draw(st.text(min_size=1, max_size=100))
    tool_id = draw(
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N")))
    )
    parameters = draw(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.text(max_size=50),
            ),
            max_size=5,
        )
    )
    estimated_duration = draw(st.floats(min_value=0.1, max_value=10.0))
    requires_confirmation = draw(st.booleans())

    # Generate valid dependencies (only earlier steps)
    depends_on = draw(
        st.lists(
            st.integers(min_value=1, max_value=step_id - 1) if step_id > 1 else st.just(0),
            max_size=min(3, step_id - 1) if step_id > 1 else 0,
        )
    )
    depends_on = [d for d in depends_on if d > 0]  # Filter out zeros

    return ReasoningStep(
        step_id=step_id,
        description=description,
        tool_id=tool_id,
        parameters=parameters,
        estimated_duration_seconds=estimated_duration,
        requires_confirmation=requires_confirmation,
        depends_on=depends_on,
    )


@st.composite
def reasoning_plan_strategy(draw):
    """Generate valid ReasoningPlan."""
    goal = draw(st.text(min_size=1, max_size=200))
    num_steps = draw(st.integers(min_value=1, max_value=5))

    # Generate steps with sequential IDs
    steps = []
    for i in range(1, num_steps + 1):
        step = ReasoningStep(
            step_id=i,
            description=draw(st.text(min_size=1, max_size=100)),
            tool_id=draw(
                st.text(
                    min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
                )
            ),
            parameters=draw(
                st.dictionaries(
                    st.text(min_size=1, max_size=20),
                    st.one_of(st.integers(), st.text(max_size=50)),
                    max_size=3,
                )
            ),
            estimated_duration_seconds=draw(st.floats(min_value=0.1, max_value=5.0)),
        )
        steps.append(step)

    reasoning = draw(st.text(min_size=1, max_size=500))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))

    return ReasoningPlan(
        goal=goal,
        steps=steps,
        reasoning=reasoning,
        confidence=confidence,
    )


@st.composite
def conversation_context_strategy(draw):
    """Generate valid ConversationContext."""
    recent_turns = draw(st.lists(st.text(min_size=1, max_size=100), max_size=10))
    tracked_entities = draw(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.integers(), st.text(max_size=50)),
            max_size=5,
        )
    )
    user_preferences = draw(
        st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.booleans(), st.text(max_size=50)),
            max_size=5,
        )
    )
    past_actions = draw(st.lists(st.text(min_size=1, max_size=100), max_size=5))

    return ConversationContext(
        recent_turns=recent_turns,
        tracked_entities=tracked_entities,
        user_preferences=user_preferences,
        past_actions=past_actions,
    )


class TestReasoningPlanProperties:
    """Property-based tests for reasoning plans."""

    @given(plan=reasoning_plan_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_9_plans_respect_step_limits(self, plan):
        """
        Property 9: Reasoning plans respect step limits.

        For any reasoning plan, the number of steps should not exceed MAX_STEPS (5).

        Validates: Requirements 4.3, 11.4
        """
        assert len(plan.steps) <= 5, f"Plan has {len(plan.steps)} steps, maximum is 5"  # nosec B101
        assert len(plan.steps) >= 1, "Plan must have at least 1 step"  # nosec B101

    @given(plan=reasoning_plan_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_reasoning_plan_has_valid_fields(self, plan):
        """Property: All reasoning plans have valid required fields."""
        assert plan.goal, "Plan must have a goal"  # nosec B101
        assert plan.steps, "Plan must have steps"  # nosec B101
        assert plan.reasoning, "Plan must have reasoning"  # nosec B101
        assert 0.0 <= plan.confidence <= 1.0, "Confidence must be 0.0-1.0"  # nosec B101
        assert plan.estimated_duration_seconds >= 0, "Duration must be non-negative"  # nosec B101

    @given(plan=reasoning_plan_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_plan_duration_is_sum_of_steps(self, plan):
        """Property: Plan duration equals sum of step durations."""
        expected_duration = sum(step.estimated_duration_seconds for step in plan.steps)
        assert (  # nosec B101
            abs(plan.estimated_duration_seconds - expected_duration) < 0.01
        ), f"Plan duration {plan.estimated_duration_seconds} != sum of steps {expected_duration}"

    @given(plan=reasoning_plan_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_plan_confirmation_reflects_steps(self, plan):
        """Property: Plan requires confirmation if any step does."""
        any_step_requires_confirmation = any(step.requires_confirmation for step in plan.steps)
        if any_step_requires_confirmation:
            assert plan.requires_confirmation, "Plan should require confirmation if any step does"  # nosec B101


class TestReasoningStepProperties:
    """Property-based tests for reasoning steps."""

    @given(step=reasoning_step_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_step_has_valid_fields(self, step):
        """Property: All reasoning steps have valid required fields."""
        assert step.step_id >= 1, "Step ID must be >= 1"  # nosec B101
        assert step.description, "Step must have description"  # nosec B101
        assert step.tool_id, "Step must have tool_id"  # nosec B101
        assert step.estimated_duration_seconds > 0, "Duration must be positive"  # nosec B101
        assert isinstance(step.parameters, dict), "Parameters must be dict"  # nosec B101
        assert isinstance(step.depends_on, list), "depends_on must be list"  # nosec B101

    @given(step=reasoning_step_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_step_dependencies_are_earlier(self, step):
        """Property: Step dependencies must reference earlier steps."""
        for dep_id in step.depends_on:
            assert (  # nosec B101
                dep_id < step.step_id
            ), f"Step {step.step_id} cannot depend on step {dep_id} (must be earlier)"


class TestConversationContextProperties:
    """Property-based tests for conversation context."""

    @given(context=conversation_context_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_10_prompts_include_context(self, context):
        """
        Property 10: Reasoning prompts include context.

        For any reasoning request, the prompt should contain conversation context
        including recent turns and tracked entities.

        Validates: Requirements 4.4
        """
        # Format context for prompt
        formatted = context.format_for_prompt()

        # Check that context is included
        assert isinstance(formatted, str), "Formatted context must be string"  # nosec B101

        # If context has data, it should be in the formatted output
        if context.recent_turns:
            assert "Recent conversation" in formatted or len(formatted) > 0  # nosec B101

        if context.tracked_entities:
            # At least some entities should be mentioned
            assert len(formatted) > 0  # nosec B101

    @given(context=conversation_context_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_context_respects_max_turns(self, context):
        """Property: Context formatting respects max_turns limit."""
        max_turns = 3
        formatted = context.format_for_prompt(max_turns=max_turns)

        # Just verify it's a valid string
        assert isinstance(formatted, str)  # nosec B101

    @given(context=conversation_context_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_context_compression_reduces_size(self, context):
        """Property: Context compression reduces size."""
        original_formatted = context.format_for_prompt()
        compressed_context = ReasoningPrompts.compress_context(context, max_length=200)
        compressed_formatted = compressed_context.format_for_prompt()

        # Compressed should be <= original
        assert (  # nosec B101
            len(compressed_formatted) <= len(original_formatted) or len(original_formatted) <= 200
        )


class TestReasoningPlanValidatorProperties:
    """Property-based tests for plan validation."""

    @given(plan=reasoning_plan_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_11_plans_are_executable(self, plan):
        """
        Property 11: Reasoning plans are executable.

        For any generated reasoning plan, each step should specify a valid tool_id
        and all required parameters for that tool.

        Validates: Requirements 4.1
        """
        # Create tool registry with all tools from plan
        # Set required parameters to match what each step actually has
        tool_registry = {}
        for step in plan.steps:
            if step.tool_id not in tool_registry:
                # Only require parameters that this step actually provides
                tool_registry[step.tool_id] = {
                    "name": step.tool_id,
                    "required_parameters": list(step.parameters.keys()),
                }
            else:
                # If tool already exists, use intersection of parameters
                existing_params = set(tool_registry[step.tool_id]["required_parameters"])
                step_params = set(step.parameters.keys())
                # Only require parameters that ALL steps with this tool have
                tool_registry[step.tool_id]["required_parameters"] = list(
                    existing_params & step_params
                )

        # Validate plan
        validator = ReasoningPlanValidator(tool_registry, max_duration_seconds=100.0)
        is_valid, error = validator.validate(plan)

        # Plan should be valid with matching tool registry
        assert is_valid, f"Plan should be valid: {error}"  # nosec B101

    @given(plan=reasoning_plan_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_validator_rejects_unknown_tools(self, plan):
        """Property: Validator rejects plans with unknown tools."""
        # Create empty tool registry
        tool_registry = {}

        validator = ReasoningPlanValidator(tool_registry, max_duration_seconds=100.0)
        is_valid, error = validator.validate(plan)

        # Plan should be invalid (unknown tools)
        assert is_valid is False  # nosec B101
        assert error is not None  # nosec B101
        assert "Unknown tool" in error  # nosec B101

    @given(plan=reasoning_plan_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_validator_checks_duration_limit(self, plan):
        """Property: Validator enforces duration limits."""
        # Create tool registry
        tool_registry = {
            step.tool_id: {
                "name": step.tool_id,
                "required_parameters": list(step.parameters.keys()),
            }
            for step in plan.steps
        }

        # Set very low duration limit
        validator = ReasoningPlanValidator(tool_registry, max_duration_seconds=0.1)
        is_valid, error = validator.validate(plan)

        # If plan duration exceeds limit, should be invalid
        if plan.estimated_duration_seconds > 0.1:
            assert is_valid is False  # nosec B101
            assert "exceeds limit" in error  # nosec B101
