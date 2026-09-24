"""
Tests for multi-step plan executor.

Coverage Target: >80% (enforced by CI/CD)

Validates Requirements: 11.1, 11.2, 11.5
"""

import time
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.execution.multi_step_executor import (
    MultiStepExecutor,
    MultiStepResult,
    PlanStep,
    StepResult,
)
from Agent_Guru.reasoning.models.action import Action

# Test fixtures


@pytest.fixture
def executor() -> MultiStepExecutor:
    """Create multi-step executor for testing."""
    return MultiStepExecutor(
        max_steps=5,
        default_step_timeout=5.0,
        total_timeout=15.0,
        max_retries=3,
    )


@pytest.fixture
def simple_action() -> Action:
    """Create simple action for testing."""
    return Action(
        action_id="action_1",
        tool_id="test_tool",
        parameters={"value": 10},
    )


def simple_tool_function(params: dict[str, Any]) -> Any:
    """Simple tool function that returns doubled value."""
    return params.get("value", 0) * 2


def slow_tool_function(params: dict[str, Any]) -> Any:
    """Slow tool function for timeout testing."""
    time.sleep(params.get("delay", 1.0))
    return "completed"


def failing_tool_function(params: dict[str, Any]) -> Any:
    """Tool function that always fails."""
    raise ValueError("Intentional failure")


def identity_tool_function(params: dict[str, Any]) -> Any:
    """Tool function that returns input value."""
    return params.get("input", None)


# Unit Tests


# ---------------------------------------------------------------------------
# WALL-CLOCK BUDGET FOR THE TIMEOUT PROPERTIES
#
# The four timeout properties below are exercised by really sleeping, so their
# runtime is max_examples x (time each example spends blocked). As originally
# written they cost roughly 50 x 0.9 s, 50 x 1.5 s, 30 x 1.5 s and 30 x 0.7 s
# - each far beyond the `--timeout=30` pytest.ini sets for every test - so all
# four hit pytest-timeout's SIGALRM on every run and Hypothesis reported them
# as "FlakyFailure ... produces unreliable results" rather than as passes or
# failures. None of their assertions had ever been evaluated.
#
# What each property asserts is a RELATION between a delay and a timeout
# (delay > step timeout, sum of delays > plan timeout), not any particular
# number of seconds. The constants below preserve every one of those relations
# while scaling the absolute durations down by ~5x, keeping every interval an
# order of magnitude above scheduler granularity, and bounding each property
# to a few seconds.
# ---------------------------------------------------------------------------
# Step timeout used by the step-timeout properties, and the delay of a step
# that must exceed it (SLOW) or comfortably fit inside it (FAST).
STEP_TIMEOUT = 0.2
SLOW_STEP_MIN = 0.35
SLOW_STEP_MAX = 0.5
FAST_STEP = 0.05
# Plan-level timeout used by the total-timeout property, and the per-step delay
# that makes 4-5 such steps overrun it.
PLAN_TIMEOUT = 0.5
PLAN_STEP_MIN = 0.18
PLAN_STEP_MAX = 0.25
TIMEOUT_EXAMPLES = 20


class TestMultiStepExecutor:
    """Unit tests for MultiStepExecutor."""

    def test_initialization(self):
        """Test executor initialization."""
        executor = MultiStepExecutor(
            max_steps=3,
            default_step_timeout=2.0,
            total_timeout=10.0,
            max_retries=2,
        )

        assert executor.max_steps == 3  # nosec B101
        assert executor.default_step_timeout == 2.0  # nosec B101
        assert executor.total_timeout == 10.0  # nosec B101
        assert executor.sync_executor.max_retries == 2  # nosec B101

    def test_invalid_initialization(self):
        """Test validation of invalid initialization parameters."""
        with pytest.raises(ValueError):
            MultiStepExecutor(max_steps=0)

        with pytest.raises(ValueError):
            MultiStepExecutor(default_step_timeout=-1.0)

        with pytest.raises(ValueError):
            MultiStepExecutor(total_timeout=0.0)

        with pytest.raises(ValueError):
            MultiStepExecutor(max_retries=-1)

    def test_single_step_execution(self, executor: MultiStepExecutor, simple_action: Action):
        """Test execution of single-step plan."""
        steps = [
            PlanStep(
                step_number=1,
                action=simple_action,
                tool_function=simple_tool_function,
            )
        ]

        result = executor.execute_plan("plan_1", steps)

        assert result.success is True  # nosec B101
        assert result.completed_steps == 1  # nosec B101
        assert result.total_steps == 1  # nosec B101
        assert len(result.step_results) == 1  # nosec B101
        assert result.step_results[0].success is True  # nosec B101
        assert result.step_results[0].result_data == 20  # 10 * 2  # nosec B101
        assert result.failed_at_step is None  # nosec B101
        assert result.error is None  # nosec B101

    def test_multi_step_execution(self, executor: MultiStepExecutor):
        """Test execution of multi-step plan."""
        action1 = Action(action_id="action_1", tool_id="tool_1", parameters={"value": 5})
        action2 = Action(action_id="action_2", tool_id="tool_2", parameters={"value": 3})
        action3 = Action(action_id="action_3", tool_id="tool_3", parameters={"value": 2})

        steps = [
            PlanStep(step_number=1, action=action1, tool_function=simple_tool_function),
            PlanStep(step_number=2, action=action2, tool_function=simple_tool_function),
            PlanStep(step_number=3, action=action3, tool_function=simple_tool_function),
        ]

        result = executor.execute_plan("plan_multi", steps)

        assert result.success is True  # nosec B101
        assert result.completed_steps == 3  # nosec B101
        assert result.total_steps == 3  # nosec B101
        assert len(result.step_results) == 3  # nosec B101
        assert result.step_results[0].result_data == 10  # 5 * 2  # nosec B101
        assert result.step_results[1].result_data == 6  # 3 * 2  # nosec B101
        assert result.step_results[2].result_data == 4  # 2 * 2  # nosec B101

    def test_parameter_binding(self, executor: MultiStepExecutor):
        """Test parameter binding from previous step results."""
        action1 = Action(action_id="action_1", tool_id="tool_1", parameters={"value": 5})
        action2 = Action(
            action_id="action_2",
            tool_id="tool_2",
            parameters={"input": None},  # Will be bound
        )

        steps = [
            PlanStep(
                step_number=1,
                action=action1,
                tool_function=simple_tool_function,
                output_binding="result1",
            ),
            PlanStep(
                step_number=2,
                action=action2,
                tool_function=identity_tool_function,
                parameter_bindings={"input": "result1"},
            ),
        ]

        result = executor.execute_plan("plan_binding", steps)

        assert result.success is True  # nosec B101
        assert result.completed_steps == 2  # nosec B101
        assert result.step_results[0].result_data == 10  # 5 * 2  # nosec B101
        assert result.step_results[1].result_data == 10  # Bound from step 1  # nosec B101

    def test_fail_fast_on_step_failure(self, executor: MultiStepExecutor):
        """Test that execution stops on first step failure."""
        action1 = Action(action_id="action_1", tool_id="tool_1", parameters={})
        action2 = Action(action_id="action_2", tool_id="tool_2", parameters={"value": 5})

        steps = [
            PlanStep(step_number=1, action=action1, tool_function=failing_tool_function),
            PlanStep(step_number=2, action=action2, tool_function=simple_tool_function),
        ]

        result = executor.execute_plan("plan_fail", steps)

        assert result.success is False  # nosec B101
        assert result.completed_steps == 1  # nosec B101
        assert result.total_steps == 2  # nosec B101
        assert result.failed_at_step == 1  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "STEP_FAILED"  # nosec B101
        assert result.step_results[0].success is False  # nosec B101

    def test_empty_plan_validation(self, executor: MultiStepExecutor):
        """Test validation of empty plan."""
        result = executor.execute_plan("plan_empty", [])

        assert result.success is False  # nosec B101
        assert result.completed_steps == 0  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "EMPTY_PLAN"  # nosec B101

    def test_too_many_steps_validation(self, executor: MultiStepExecutor):
        """Test validation of plan with too many steps."""
        # Create 6 steps (exceeds max of 5)
        steps = [
            PlanStep(
                step_number=i,
                action=Action(action_id=f"action_{i}", tool_id="tool", parameters={}),
                tool_function=simple_tool_function,
            )
            for i in range(1, 7)
        ]

        result = executor.execute_plan("plan_too_many", steps)

        assert result.success is False  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "TOO_MANY_STEPS"  # nosec B101

    def test_invalid_step_numbers(self, executor: MultiStepExecutor):
        """Test validation of non-sequential step numbers."""
        action1 = Action(action_id="action_1", tool_id="tool_1", parameters={})
        action2 = Action(action_id="action_2", tool_id="tool_2", parameters={})

        steps = [
            PlanStep(step_number=1, action=action1, tool_function=simple_tool_function),
            PlanStep(step_number=3, action=action2, tool_function=simple_tool_function),  # Skip 2
        ]

        result = executor.execute_plan("plan_invalid_nums", steps)

        assert result.success is False  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "INVALID_STEP_NUMBER"  # nosec B101

    def test_invalid_parameter_binding(self, executor: MultiStepExecutor):
        """Test validation of invalid parameter bindings."""
        action1 = Action(action_id="action_1", tool_id="tool_1", parameters={})

        steps = [
            PlanStep(
                step_number=1,
                action=action1,
                tool_function=simple_tool_function,
                parameter_bindings={"input": "nonexistent_key"},  # Invalid binding
            ),
        ]

        result = executor.execute_plan("plan_invalid_binding", steps)

        assert result.success is False  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "INVALID_BINDING"  # nosec B101

    def test_step_timeout(self, executor: MultiStepExecutor):
        """Test step-level timeout enforcement."""
        action = Action(action_id="action_1", tool_id="tool_1", parameters={"delay": 10.0})

        steps = [
            PlanStep(
                step_number=1,
                action=action,
                tool_function=slow_tool_function,
                timeout=0.5,  # Short timeout
            )
        ]

        result = executor.execute_plan("plan_step_timeout", steps)

        assert result.success is False  # nosec B101
        assert result.completed_steps == 1  # nosec B101
        assert result.step_results[0].success is False  # nosec B101
        assert result.step_results[0].error is not None  # nosec B101
        assert "TIMEOUT" in result.step_results[0].error["error_code"]  # nosec B101

    def test_total_timeout(self):
        """Test total plan timeout enforcement."""
        executor = MultiStepExecutor(
            max_steps=5,
            default_step_timeout=5.0,
            total_timeout=1.0,  # Short total timeout
        )

        # Create steps that will exceed total timeout
        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"delay": 0.5},
                ),
                tool_function=slow_tool_function,
            )
            for i in range(1, 4)
        ]

        result = executor.execute_plan("plan_total_timeout", steps)

        assert result.success is False  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "PLAN_TIMEOUT"  # nosec B101
        assert result.completed_steps < result.total_steps  # nosec B101

    def test_cancellation(self, executor: MultiStepExecutor):
        """Test plan cancellation."""

        def cancel_after_first_step(params: dict[str, Any]) -> Any:
            """Tool function that triggers cancellation."""
            if params.get("step") == 1:
                executor.cancel_execution()
            return params.get("value", 0)

        steps = [
            PlanStep(
                step_number=1,
                action=Action(
                    action_id="action_1",
                    tool_id="tool_1",
                    parameters={"step": 1, "value": 10},
                ),
                tool_function=cancel_after_first_step,
            ),
            PlanStep(
                step_number=2,
                action=Action(
                    action_id="action_2",
                    tool_id="tool_2",
                    parameters={"step": 2, "value": 20},
                ),
                tool_function=cancel_after_first_step,
            ),
        ]

        result = executor.execute_plan("plan_cancel", steps)

        assert result.success is False  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "PLAN_CANCELLED"  # nosec B101
        assert result.completed_steps == 1  # First step completed before cancellation  # nosec B101

    def test_cancellation_during_step_execution(self, executor: MultiStepExecutor):
        """Test cancellation during step execution with graceful shutdown."""
        import threading

        def long_running_tool(params: dict[str, Any]) -> Any:
            """Tool function that runs for a while."""
            time.sleep(params.get("delay", 2.0))
            return "completed"

        steps = [
            PlanStep(
                step_number=1,
                action=Action(
                    action_id="action_1",
                    tool_id="tool_1",
                    parameters={"delay": 2.0},
                ),
                tool_function=long_running_tool,
            ),
            PlanStep(
                step_number=2,
                action=Action(
                    action_id="action_2",
                    tool_id="tool_2",
                    parameters={"delay": 1.0},
                ),
                tool_function=long_running_tool,
            ),
        ]

        # Start execution in a thread
        result_container = []

        def execute_plan():
            result = executor.execute_plan("plan_cancel_during", steps)
            result_container.append(result)

        thread = threading.Thread(target=execute_plan)
        thread.start()

        # Cancel after 0.5 seconds (during first step)
        time.sleep(0.5)
        executor.cancel_execution()

        # Wait for execution to complete
        thread.join(timeout=5.0)

        # Check result
        assert len(result_container) == 1  # nosec B101
        result = result_container[0]

        # Should have been cancelled
        assert result.success is False  # nosec B101

        # Should have completed first step with cancellation error
        assert result.completed_steps == 1  # nosec B101
        assert result.step_results[0].success is False  # nosec B101
        assert result.step_results[0].error is not None  # nosec B101
        assert "CANCELLED" in result.step_results[0].error["error_code"]  # nosec B101

    def test_is_cancelled_method(self, executor: MultiStepExecutor):
        """Test is_cancelled method."""
        assert executor.is_cancelled() is False  # nosec B101

        executor.cancel_execution()
        assert executor.is_cancelled() is True  # nosec B101

        executor.clear_execution_context()
        assert executor.is_cancelled() is False  # nosec B101

    def test_cancellation_prevents_subsequent_steps(self, executor: MultiStepExecutor):
        """Test that cancellation prevents subsequent steps from executing."""
        executed_steps = []

        def tracking_tool(params: dict[str, Any]) -> Any:
            """Tool function that tracks execution."""
            step = params.get("step", 0)
            executed_steps.append(step)
            if step == 1:
                executor.cancel_execution()
            return step

        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"step": i},
                ),
                tool_function=tracking_tool,
            )
            for i in range(1, 4)
        ]

        result = executor.execute_plan("plan_prevent_subsequent", steps)

        # Only first step should have executed
        assert executed_steps == [1]  # nosec B101
        assert result.completed_steps == 1  # nosec B101
        assert result.success is False  # nosec B101
        assert result.error["error_code"] == "PLAN_CANCELLED"  # nosec B101

    def test_execution_context(self, executor: MultiStepExecutor):
        """Test execution context management."""
        action1 = Action(action_id="action_1", tool_id="tool_1", parameters={"value": 5})
        action2 = Action(action_id="action_2", tool_id="tool_2", parameters={"value": 10})

        steps = [
            PlanStep(
                step_number=1,
                action=action1,
                tool_function=simple_tool_function,
                output_binding="result1",
            ),
            PlanStep(
                step_number=2,
                action=action2,
                tool_function=simple_tool_function,
                output_binding="result2",
            ),
        ]

        result = executor.execute_plan("plan_context", steps)

        assert result.success is True  # nosec B101

        # Check execution context
        context = executor.get_execution_context()
        assert "result1" in context  # nosec B101
        assert "result2" in context  # nosec B101
        assert context["result1"] == 10  # 5 * 2  # nosec B101
        assert context["result2"] == 20  # 10 * 2  # nosec B101

    def test_clear_execution_context(self, executor: MultiStepExecutor):
        """Test clearing execution context."""
        action = Action(action_id="action_1", tool_id="tool_1", parameters={"value": 5})

        steps = [
            PlanStep(
                step_number=1,
                action=action,
                tool_function=simple_tool_function,
                output_binding="result1",
            )
        ]

        executor.execute_plan("plan_clear", steps)
        assert len(executor.get_execution_context()) > 0  # nosec B101

        executor.clear_execution_context()
        assert len(executor.get_execution_context()) == 0  # nosec B101

    def test_result_to_dict(self, executor: MultiStepExecutor, simple_action: Action):
        """Test conversion of results to dictionary."""
        steps = [PlanStep(step_number=1, action=simple_action, tool_function=simple_tool_function)]

        result = executor.execute_plan("plan_dict", steps)
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)  # nosec B101
        assert "plan_id" in result_dict  # nosec B101
        assert "success" in result_dict  # nosec B101
        assert "completed_steps" in result_dict  # nosec B101
        assert "total_steps" in result_dict  # nosec B101
        assert "step_results" in result_dict  # nosec B101
        assert isinstance(result_dict["step_results"], list)  # nosec B101

    def test_partial_results_on_failure(self, executor: MultiStepExecutor):
        """Test that partial results are returned on failure."""
        action1 = Action(action_id="action_1", tool_id="tool_1", parameters={"value": 5})
        action2 = Action(action_id="action_2", tool_id="tool_2", parameters={})
        action3 = Action(action_id="action_3", tool_id="tool_3", parameters={"value": 10})

        steps = [
            PlanStep(step_number=1, action=action1, tool_function=simple_tool_function),
            PlanStep(step_number=2, action=action2, tool_function=failing_tool_function),
            PlanStep(step_number=3, action=action3, tool_function=simple_tool_function),
        ]

        result = executor.execute_plan("plan_partial", steps)

        assert result.success is False  # nosec B101
        assert result.completed_steps == 2  # nosec B101
        assert result.total_steps == 3  # nosec B101
        assert len(result.step_results) == 2  # nosec B101
        assert result.step_results[0].success is True  # nosec B101
        assert result.step_results[1].success is False  # nosec B101
        assert result.failed_at_step == 2  # nosec B101


# Property-Based Tests


class TestMultiStepExecutorProperties:
    """Property-based tests for MultiStepExecutor.

    Validates Requirements: 11.1, 11.2, 11.5
    """

    @given(
        max_steps=st.integers(min_value=1, max_value=10),
        default_step_timeout=st.floats(min_value=0.1, max_value=10.0),
        total_timeout=st.floats(min_value=1.0, max_value=30.0),
    )
    def test_valid_config_always_works(
        self,
        max_steps: int,
        default_step_timeout: float,
        total_timeout: float,
    ):
        """Property: Valid configuration always creates executor."""
        executor = MultiStepExecutor(
            max_steps=max_steps,
            default_step_timeout=default_step_timeout,
            total_timeout=total_timeout,
        )

        assert executor is not None  # nosec B101
        assert executor.max_steps == max_steps  # nosec B101
        assert executor.default_step_timeout == default_step_timeout  # nosec B101
        assert executor.total_timeout == total_timeout  # nosec B101

    @given(
        num_steps=st.integers(min_value=1, max_value=5),
        value=st.integers(min_value=1, max_value=100),
    )
    def test_successful_plan_completes_all_steps(self, num_steps: int, value: int):
        """Property: Successful plan completes all steps."""
        executor = MultiStepExecutor()

        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"value": value},
                ),
                tool_function=simple_tool_function,
            )
            for i in range(1, num_steps + 1)
        ]

        result = executor.execute_plan("plan_prop", steps)

        assert result.success is True  # nosec B101
        assert result.completed_steps == num_steps  # nosec B101
        assert result.total_steps == num_steps  # nosec B101
        assert len(result.step_results) == num_steps  # nosec B101

    @given(
        num_steps=st.integers(min_value=2, max_value=5),
        fail_at=st.integers(min_value=1, max_value=5),
    )
    def test_failure_stops_at_failed_step(self, num_steps: int, fail_at: int):
        """Property: Failure stops execution at failed step."""
        if fail_at > num_steps:
            fail_at = num_steps

        executor = MultiStepExecutor()

        steps = []
        for i in range(1, num_steps + 1):
            if i == fail_at:
                tool_func = failing_tool_function
            else:
                tool_func = simple_tool_function

            steps.append(
                PlanStep(
                    step_number=i,
                    action=Action(
                        action_id=f"action_{i}",
                        tool_id="tool",
                        parameters={"value": 10},
                    ),
                    tool_function=tool_func,
                )
            )

        result = executor.execute_plan("plan_fail_prop", steps)

        assert result.success is False  # nosec B101
        assert result.completed_steps == fail_at  # nosec B101
        assert result.failed_at_step == fail_at  # nosec B101
        assert len(result.step_results) == fail_at  # nosec B101

    @given(num_steps=st.integers(min_value=1, max_value=5))
    def test_result_has_correct_structure(self, num_steps: int):
        """Property: Result always has correct structure."""
        executor = MultiStepExecutor()

        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"value": 10},
                ),
                tool_function=simple_tool_function,
            )
            for i in range(1, num_steps + 1)
        ]

        result = executor.execute_plan("plan_struct", steps)

        # Check structure
        assert isinstance(result, MultiStepResult)  # nosec B101
        assert isinstance(result.plan_id, str)  # nosec B101
        assert isinstance(result.success, bool)  # nosec B101
        assert isinstance(result.completed_steps, int)  # nosec B101
        assert isinstance(result.total_steps, int)  # nosec B101
        assert isinstance(result.step_results, list)  # nosec B101
        assert isinstance(result.total_execution_time, float)  # nosec B101

        # Check step results structure
        for step_result in result.step_results:
            assert isinstance(step_result, StepResult)  # nosec B101
            assert isinstance(step_result.step_number, int)  # nosec B101
            assert isinstance(step_result.action_id, str)  # nosec B101
            assert isinstance(step_result.success, bool)  # nosec B101
            assert isinstance(step_result.execution_time, float)  # nosec B101

    @given(
        num_steps=st.integers(min_value=2, max_value=5),
        step_delay=st.floats(min_value=SLOW_STEP_MIN, max_value=SLOW_STEP_MAX),
    )
    @settings(deadline=None, max_examples=TIMEOUT_EXAMPLES)
    def test_step_timeout_returns_partial_results(self, num_steps: int, step_delay: float):
        """Property 29: Partial results are returned on step timeout.

        **Validates: Requirements 11.5**

        For any multi-step execution where a step times out, the system should
        return results from completed steps along with an indication that the
        plan was not fully executed.
        """
        # Create executor with short step timeout
        executor = MultiStepExecutor(
            max_steps=5,
            default_step_timeout=STEP_TIMEOUT,  # Short timeout
            total_timeout=15.0,
        )

        # Create steps where second step will timeout
        steps = []
        for i in range(1, num_steps + 1):
            if i == 2:  # Second step will timeout
                delay = step_delay  # Exceeds STEP_TIMEOUT by construction
            else:
                delay = FAST_STEP  # Fast steps

            steps.append(
                PlanStep(
                    step_number=i,
                    action=Action(
                        action_id=f"action_{i}",
                        tool_id="tool",
                        parameters={"delay": delay},
                    ),
                    tool_function=slow_tool_function,
                )
            )

        result = executor.execute_plan("plan_step_timeout_prop", steps)

        # Should fail due to step timeout
        assert result.success is False  # nosec B101

        # Should have completed at least the first step and the timeout step
        assert result.completed_steps >= 2  # nosec B101
        assert result.completed_steps <= num_steps  # nosec B101

        # Should have step results for completed steps
        assert len(result.step_results) == result.completed_steps  # nosec B101

        # Failed step (step 2) should have timeout error
        failed_step = result.step_results[1]  # Second step (index 1)
        assert failed_step.success is False  # nosec B101
        assert failed_step.error is not None  # nosec B101
        assert "TIMEOUT" in failed_step.error["error_code"]  # nosec B101

    @given(
        num_steps=st.integers(min_value=4, max_value=5),
        step_delay=st.floats(min_value=PLAN_STEP_MIN, max_value=PLAN_STEP_MAX),
    )
    @settings(deadline=None, max_examples=TIMEOUT_EXAMPLES)
    def test_plan_timeout_returns_partial_results(self, num_steps: int, step_delay: float):
        """Property 29: Partial results are returned on plan timeout.

        **Validates: Requirements 11.5**

        For any multi-step execution that exceeds the total plan timeout,
        the system should return results from completed steps along with
        an indication that the plan was not fully executed.
        """
        # Create executor with short total timeout
        executor = MultiStepExecutor(
            max_steps=5,
            default_step_timeout=5.0,  # Long step timeout
            total_timeout=PLAN_TIMEOUT,  # Short total timeout
        )

        # Create steps that will exceed total timeout: 4-5 steps of at least
        # PLAN_STEP_MIN each necessarily overrun PLAN_TIMEOUT.
        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"delay": step_delay},
                ),
                tool_function=slow_tool_function,
            )
            for i in range(1, num_steps + 1)
        ]

        result = executor.execute_plan("plan_total_timeout_prop", steps)

        # Should fail due to plan timeout
        assert result.success is False  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "PLAN_TIMEOUT"  # nosec B101

        # Should have completed some steps before timeout
        assert result.completed_steps >= 2  # nosec B101
        assert result.completed_steps < result.total_steps  # nosec B101

        # Should have step results for completed steps
        assert len(result.step_results) == result.completed_steps  # nosec B101

        # All completed steps should be successful
        for step_result in result.step_results:
            assert step_result.success is True  # nosec B101

        # Error should indicate timeout details
        assert "details" in result.error  # nosec B101
        assert "completed_steps" in result.error["details"]  # nosec B101
        assert result.error["details"]["completed_steps"] == result.completed_steps  # nosec B101

    @given(
        num_steps=st.integers(min_value=1, max_value=3),
        timeout_multiplier=st.floats(min_value=2.0, max_value=3.0),
    )
    @settings(deadline=None, max_examples=TIMEOUT_EXAMPLES)
    def test_timeout_enforcement_is_consistent(self, num_steps: int, timeout_multiplier: float):
        """Property: Timeout enforcement is consistent across executions.

        **Validates: Requirements 11.5**

        For any execution that should timeout, the timeout is consistently
        enforced and produces the same type of result.
        """
        step_timeout = STEP_TIMEOUT
        total_timeout = 2.0

        executor = MultiStepExecutor(
            max_steps=5,
            default_step_timeout=step_timeout,
            total_timeout=total_timeout,
        )

        # Create steps that will definitely timeout
        delay = step_timeout * timeout_multiplier
        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"delay": delay},
                ),
                tool_function=slow_tool_function,
            )
            for i in range(1, num_steps + 1)
        ]

        # Execute twice
        result1 = executor.execute_plan("plan_timeout_1", steps)
        executor.clear_execution_context()
        result2 = executor.execute_plan("plan_timeout_2", steps)

        # Both should fail
        assert result1.success is False  # nosec B101
        assert result2.success is False  # nosec B101

        # Both should have timeout-related errors
        assert result1.error is not None  # nosec B101
        assert result2.error is not None  # nosec B101
        assert (  # nosec B101
            "TIMEOUT" in result1.error["error_code"] or "STEP_FAILED" in result1.error["error_code"]
        )
        assert (  # nosec B101
            "TIMEOUT" in result2.error["error_code"] or "STEP_FAILED" in result2.error["error_code"]
        )

    @given(num_steps=st.integers(min_value=1, max_value=5))
    def test_completed_steps_never_exceeds_total(self, num_steps: int):
        """Property: Completed steps never exceeds total steps.

        **Validates: Requirements 11.1, 11.2**

        For any execution result, the number of completed steps should
        never exceed the total number of steps in the plan.
        """
        executor = MultiStepExecutor()

        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"value": 10},
                ),
                tool_function=simple_tool_function,
            )
            for i in range(1, num_steps + 1)
        ]

        result = executor.execute_plan("plan_bounds", steps)

        # Completed steps should never exceed total
        assert result.completed_steps <= result.total_steps  # nosec B101
        assert result.completed_steps >= 0  # nosec B101

        # Number of step results should match completed steps
        assert len(result.step_results) == result.completed_steps  # nosec B101

    @given(
        num_steps=st.integers(min_value=2, max_value=4),
        timeout_at_step=st.integers(min_value=1, max_value=4),
    )
    @settings(deadline=None, max_examples=TIMEOUT_EXAMPLES)
    def test_timeout_at_any_step_returns_partial_results(
        self, num_steps: int, timeout_at_step: int
    ):
        """Property: Timeout at any step returns partial results.

        **Validates: Requirements 11.5**

        For any step that times out, the system should return results
        from all steps completed before the timeout.
        """
        if timeout_at_step > num_steps:
            timeout_at_step = num_steps

        executor = MultiStepExecutor(
            max_steps=5,
            default_step_timeout=STEP_TIMEOUT,
            total_timeout=15.0,
        )

        # Create steps where one specific step will timeout
        steps = []
        for i in range(1, num_steps + 1):
            if i == timeout_at_step:
                delay = SLOW_STEP_MAX  # Will timeout
            else:
                delay = FAST_STEP  # Fast

            steps.append(
                PlanStep(
                    step_number=i,
                    action=Action(
                        action_id=f"action_{i}",
                        tool_id="tool",
                        parameters={"delay": delay},
                    ),
                    tool_function=slow_tool_function,
                )
            )

        result = executor.execute_plan("plan_timeout_at_step", steps)

        # Should fail
        assert result.success is False  # nosec B101

        # Should have completed steps up to and including the timeout step
        assert result.completed_steps == timeout_at_step  # nosec B101
        assert len(result.step_results) == timeout_at_step  # nosec B101

        # All steps before timeout should be successful
        for i in range(timeout_at_step - 1):
            assert result.step_results[i].success is True  # nosec B101

        # Timeout step should have failed
        assert result.step_results[timeout_at_step - 1].success is False  # nosec B101

    @given(
        num_steps=st.integers(min_value=2, max_value=5),
        cancel_at_step=st.integers(min_value=1, max_value=5),
    )
    @settings(deadline=None, max_examples=50)
    def test_cancellation_at_any_step_stops_execution(self, num_steps: int, cancel_at_step: int):
        """Property 28: Multi-step execution can be cancelled.

        **Validates: Requirements 11.5**

        For any multi-step execution in progress, calling cancel_execution
        should halt the current step and prevent subsequent steps from executing.
        """
        if cancel_at_step > num_steps:
            cancel_at_step = num_steps

        executor = MultiStepExecutor()
        executed_steps = []

        def tracking_tool(params: dict[str, Any]) -> Any:
            """Tool that tracks execution and cancels at specific step."""
            step = params.get("step", 0)
            executed_steps.append(step)
            if step == cancel_at_step:
                executor.cancel_execution()
            return step

        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"step": i},
                ),
                tool_function=tracking_tool,
            )
            for i in range(1, num_steps + 1)
        ]

        result = executor.execute_plan("plan_cancel_prop", steps)

        # Should have failed due to cancellation
        assert result.success is False  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "PLAN_CANCELLED"  # nosec B101

        # Should have executed only up to cancellation point
        assert len(executed_steps) == cancel_at_step  # nosec B101
        assert executed_steps == list(range(1, cancel_at_step + 1))  # nosec B101

        # Should have completed steps up to cancellation
        assert result.completed_steps == cancel_at_step  # nosec B101
        assert len(result.step_results) == cancel_at_step  # nosec B101

    @given(num_steps=st.integers(min_value=1, max_value=5))
    def test_cancellation_is_idempotent(self, num_steps: int):
        """Property: Calling cancel_execution multiple times is safe.

        **Validates: Requirements 11.5**

        For any execution, calling cancel_execution multiple times should
        have the same effect as calling it once.
        """
        executor = MultiStepExecutor()

        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"value": i},
                ),
                tool_function=simple_tool_function,
            )
            for i in range(1, num_steps + 1)
        ]

        # Cancel multiple times before execution
        executor.cancel_execution()
        executor.cancel_execution()
        executor.cancel_execution()

        result = executor.execute_plan("plan_idempotent", steps)

        # Should be cancelled
        assert result.success is False  # nosec B101
        assert result.error is not None  # nosec B101
        assert result.error["error_code"] == "PLAN_CANCELLED"  # nosec B101

        # Should not have executed any steps
        assert result.completed_steps == 0  # nosec B101
        assert len(result.step_results) == 0  # nosec B101

    @given(num_steps=st.integers(min_value=2, max_value=5))
    def test_clear_context_resets_cancellation(self, num_steps: int):
        """Property: Clearing context resets cancellation flag.

        **Validates: Requirements 11.5**

        For any executor, calling clear_execution_context should reset
        the cancellation flag, allowing new executions to proceed.
        """
        executor = MultiStepExecutor()

        # Cancel execution
        executor.cancel_execution()
        assert executor.is_cancelled() is True  # nosec B101

        # Clear context
        executor.clear_execution_context()
        assert executor.is_cancelled() is False  # nosec B101

        # Should be able to execute normally now
        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"value": i},
                ),
                tool_function=simple_tool_function,
            )
            for i in range(1, num_steps + 1)
        ]

        result = executor.execute_plan("plan_after_clear", steps)

        # Should succeed
        assert result.success is True  # nosec B101
        assert result.completed_steps == num_steps  # nosec B101
        assert len(result.step_results) == num_steps  # nosec B101

    @given(
        num_steps=st.integers(min_value=2, max_value=5),
        initial_value=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_multi_step_plans_execute_sequentially(self, num_steps: int, initial_value: int):
        """Property 27: Multi-step plans execute sequentially.

        **Validates: Requirements 11.1**

        For any multi-step reasoning plan, each step should complete before
        the next step begins, and the output of step N should be available
        as input to step N+1.

        This property verifies:
        1. Steps execute in sequential order (1, 2, 3, ...)
        2. Each step completes before the next begins
        3. Output from step N is available to step N+1 via parameter binding
        4. The execution context accumulates results from all previous steps
        """
        executor = MultiStepExecutor()

        # Track execution order
        execution_order = []

        def tracking_tool(params: dict[str, Any]) -> Any:
            """Tool that tracks execution order and transforms input."""
            step = params.get("step", 0)
            input_value = params.get("input", initial_value)

            # Record execution order
            execution_order.append(step)

            # Transform: multiply by step number
            result = input_value * step

            # Small delay to ensure sequential execution is observable
            time.sleep(0.01)

            return result

        # Create chain of steps where each depends on previous
        steps = []
        for i in range(1, num_steps + 1):
            if i == 1:
                # First step uses initial value
                action = Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"step": i, "input": initial_value},
                )
                steps.append(
                    PlanStep(
                        step_number=i,
                        action=action,
                        tool_function=tracking_tool,
                        output_binding=f"result_{i}",
                    )
                )
            else:
                # Subsequent steps depend on previous step output
                action = Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"step": i, "input": None},  # Will be bound
                )
                steps.append(
                    PlanStep(
                        step_number=i,
                        action=action,
                        tool_function=tracking_tool,
                        parameter_bindings={"input": f"result_{i-1}"},
                        output_binding=f"result_{i}",
                    )
                )

        result = executor.execute_plan("plan_sequential", steps)

        # Verify execution succeeded
        assert result.success is True  # nosec B101
        assert result.completed_steps == num_steps  # nosec B101
        assert len(result.step_results) == num_steps  # nosec B101

        # Property 1: Steps executed in sequential order
        assert execution_order == list(range(1, num_steps + 1)), (  # nosec B101
            f"Steps did not execute in sequential order. "
            f"Expected {list(range(1, num_steps + 1))}, got {execution_order}"
        )

        # Property 2: Each step completed before next began
        # (verified by execution_order being sequential)
        for i, step_num in enumerate(execution_order):
            assert step_num == i + 1, f"Step {step_num} executed out of order at position {i}"  # nosec B101

        # Property 3: Output from step N available to step N+1
        # Verify by checking the computed values form a chain
        expected_value = initial_value
        for i in range(num_steps):
            step_result = result.step_results[i]
            step_num = i + 1

            # Each step multiplies input by step number
            expected_value = expected_value * step_num

            assert step_result.result_data == expected_value, (  # nosec B101
                f"Step {step_num} result incorrect. "
                f"Expected {expected_value}, got {step_result.result_data}"
            )

        # Property 4: Execution context accumulates all results
        context = executor.get_execution_context()

        # Verify all output bindings are in context
        for i in range(1, num_steps + 1):
            binding_key = f"result_{i}"
            assert (  # nosec B101
                binding_key in context
            ), f"Output binding '{binding_key}' not found in execution context"

        # Verify context values match step results
        for i in range(num_steps):
            binding_key = f"result_{i+1}"
            step_result_value = result.step_results[i].result_data
            context_value = context[binding_key]

            assert context_value == step_result_value, (  # nosec B101
                f"Context value for '{binding_key}' does not match step result. "
                f"Context: {context_value}, Step result: {step_result_value}"
            )

        # Property 5: Step timestamps are monotonically increasing
        # (each step starts after previous completes)
        for i in range(1, num_steps):
            prev_step = result.step_results[i - 1]
            curr_step = result.step_results[i]

            # Current step timestamp should be after previous
            assert curr_step.timestamp >= prev_step.timestamp, (  # nosec B101
                f"Step {i+1} timestamp ({curr_step.timestamp}) is before "
                f"step {i} timestamp ({prev_step.timestamp})"
            )


# Integration Tests


@pytest.mark.integration
class TestMultiStepExecutorIntegration:
    """Integration tests for MultiStepExecutor."""

    def test_complex_multi_step_workflow(self):
        """Test complex multi-step workflow with parameter binding."""
        executor = MultiStepExecutor()

        # Step 1: Calculate initial value
        action1 = Action(
            action_id="calc_initial",
            tool_id="calculator",
            parameters={"value": 5},
        )

        # Step 2: Double the result from step 1
        action2 = Action(
            action_id="double_value",
            tool_id="calculator",
            parameters={"input": None},  # Will be bound
        )

        # Step 3: Add 10 to result from step 2
        def add_ten(params: dict[str, Any]) -> Any:
            return params.get("input", 0) + 10

        action3 = Action(
            action_id="add_ten",
            tool_id="calculator",
            parameters={"input": None},  # Will be bound
        )

        steps = [
            PlanStep(
                step_number=1,
                action=action1,
                tool_function=simple_tool_function,
                output_binding="initial",
            ),
            PlanStep(
                step_number=2,
                action=action2,
                tool_function=identity_tool_function,
                parameter_bindings={"input": "initial"},
                output_binding="doubled",
            ),
            PlanStep(
                step_number=3,
                action=action3,
                tool_function=add_ten,
                parameter_bindings={"input": "doubled"},
                output_binding="final",
            ),
        ]

        result = executor.execute_plan("complex_workflow", steps)

        assert result.success is True  # nosec B101
        assert result.completed_steps == 3  # nosec B101
        assert result.step_results[0].result_data == 10  # 5 * 2  # nosec B101
        assert result.step_results[1].result_data == 10  # Bound from step 1  # nosec B101
        assert result.step_results[2].result_data == 20  # 10 + 10  # nosec B101

        # Check final context
        context = executor.get_execution_context()
        assert context["initial"] == 10  # nosec B101
        assert context["doubled"] == 10  # nosec B101
        assert context["final"] == 20  # nosec B101

    def test_performance_within_budget(self):
        """Test that multi-step execution meets performance budget."""
        executor = MultiStepExecutor()

        # Create 5 fast steps
        steps = [
            PlanStep(
                step_number=i,
                action=Action(
                    action_id=f"action_{i}",
                    tool_id="tool",
                    parameters={"value": i},
                ),
                tool_function=simple_tool_function,
            )
            for i in range(1, 6)
        ]

        start_time = time.perf_counter()
        result = executor.execute_plan("perf_test", steps)
        elapsed = time.perf_counter() - start_time

        assert result.success is True  # nosec B101
        assert elapsed < 1.0  # Should complete in under 1 second  # nosec B101
        assert result.total_execution_time < 1.0  # nosec B101
