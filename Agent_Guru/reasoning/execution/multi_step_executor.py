"""
Multi-step plan executor for Core Reasoning Engine.

Performance Requirements:
- Time Complexity: O(n) where n is number of steps
- Space Complexity: O(n) for step results storage
- Latency: <15s total for multi-step plans (max 5 steps)
- Per-step timeout: 5s default (configurable)

Design Decisions:
- Sequential execution with state passing between steps
- Fail-fast on step failure with partial results
- Parameter binding from previous step results
- Progress tracking through multi-step plans
- Support for step-level timeout and cancellation

Validates Requirements: 11.1, 11.2

Author: Kiro AI
Date: 2026-02-21
Version: 1.0.0
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Agent_Guru.reasoning.execution.executor import SyncExecutor
from Agent_Guru.reasoning.models.action import Action


@dataclass
class StepResult:
    """Result of a single step execution.

    Attributes:
        step_number: Step number (1-indexed)
        action_id: ID of executed action
        success: Whether step succeeded
        result_data: Result data if successful
        error: Error information if failed
        execution_time: Time taken to execute (seconds)
        timestamp: When step completed
    """

    step_number: int
    action_id: str
    success: bool
    result_data: Any | None = None
    error: dict[str, Any] | None = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_number": self.step_number,
            "action_id": self.action_id,
            "success": self.success,
            "result_data": self.result_data,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MultiStepResult:
    """Result of multi-step plan execution.

    Attributes:
        plan_id: Unique plan identifier
        success: Whether all steps succeeded
        completed_steps: Number of steps completed
        total_steps: Total number of steps in plan
        step_results: Results for each step
        total_execution_time: Total time taken (seconds)
        failed_at_step: Step number where failure occurred (None if success)
        error: Error information if plan failed
        timestamp: When plan execution completed
    """

    plan_id: str
    success: bool
    completed_steps: int
    total_steps: int
    step_results: list[StepResult]
    total_execution_time: float = 0.0
    failed_at_step: int | None = None
    error: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "success": self.success,
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "step_results": [step.to_dict() for step in self.step_results],
            "total_execution_time": self.total_execution_time,
            "failed_at_step": self.failed_at_step,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PlanStep:
    """Represents a single step in a multi-step plan.

    Attributes:
        step_number: Step number (1-indexed)
        action: Action to execute
        tool_function: Function to execute
        parameter_bindings: Parameter bindings from previous steps
        output_binding: Variable name to store result (optional)
        timeout: Step-specific timeout in seconds (optional)
    """

    step_number: int
    action: Action
    tool_function: Callable[[dict[str, Any]], Any]
    parameter_bindings: dict[str, str] = field(default_factory=dict)
    output_binding: str | None = None
    timeout: float | None = None


class MultiStepExecutor:
    """Multi-step plan executor with sequential execution and state passing.

    Time Complexity: O(n) where n is number of steps
    Space Complexity: O(n) for storing step results

    Example:
        >>> executor = MultiStepExecutor(max_steps=5, default_step_timeout=5.0)
        >>> steps = [
        ...     PlanStep(1, action1, tool_func1, output_binding="result1"),
        ...     PlanStep(2, action2, tool_func2, parameter_bindings={"input": "result1"}),
        ... ]
        >>> result = executor.execute_plan("plan_123", steps)
        >>> print(f"Success: {result.success}, Steps: {result.completed_steps}/{result.total_steps}")
    """

    def __init__(
        self,
        max_steps: int = 5,
        default_step_timeout: float = 5.0,
        total_timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize multi-step executor.

        Args:
            max_steps: Maximum number of steps allowed (default: 5)
            default_step_timeout: Default timeout per step in seconds (default: 5.0)
            total_timeout: Total timeout for entire plan in seconds (default: 15.0)
            max_retries: Maximum retry attempts per step (default: 3)

        Raises:
            ValueError: If parameters are invalid
        """
        if max_steps <= 0:
            raise ValueError(f"Invalid max_steps: {max_steps}")
        if default_step_timeout <= 0:
            raise ValueError(f"Invalid default_step_timeout: {default_step_timeout}")
        if total_timeout <= 0:
            raise ValueError(f"Invalid total_timeout: {total_timeout}")
        if max_retries < 0:
            raise ValueError(f"Invalid max_retries: {max_retries}")

        self.max_steps = max_steps
        self.default_step_timeout = default_step_timeout
        self.total_timeout = total_timeout

        # Create sync executor for step execution
        self.sync_executor = SyncExecutor(
            default_timeout=default_step_timeout,
            max_retries=max_retries,
        )

        # Track execution state
        self._execution_context: dict[str, Any] = {}
        self._cancelled = False
        self._current_step_future: Any | None = None  # Track current step for cancellation

    def execute_plan(
        self,
        plan_id: str,
        steps: list[PlanStep],
    ) -> MultiStepResult:
        """Execute multi-step plan sequentially with state passing.

        Time Complexity: O(n) where n is number of steps
        Space Complexity: O(n) for storing step results

        Args:
            plan_id: Unique plan identifier
            steps: List of steps to execute

        Returns:
            MultiStepResult with execution results

        Raises:
            Never raises - all errors captured in MultiStepResult
        """
        # Check cancellation before starting
        if self._cancelled:
            return MultiStepResult(
                plan_id=plan_id,
                success=False,
                completed_steps=0,
                total_steps=len(steps),
                step_results=[],
                error={
                    "error_code": "PLAN_CANCELLED",
                    "message": "Plan execution was cancelled before starting",
                    "details": {},
                    "recoverable": False,
                },
            )

        # Validate plan
        validation_error = self._validate_plan(steps)
        if validation_error:
            return MultiStepResult(
                plan_id=plan_id,
                success=False,
                completed_steps=0,
                total_steps=len(steps),
                step_results=[],
                error=validation_error,
            )

        # Initialize execution state
        start_time = time.perf_counter()
        step_results: list[StepResult] = []
        self._execution_context = {}
        # Note: Don't reset _cancelled here - it may have been set before execute_plan was called

        # Execute steps sequentially
        for step in steps:
            # Check total timeout
            elapsed = time.perf_counter() - start_time
            if elapsed >= self.total_timeout:
                return self._create_timeout_result(plan_id, steps, step_results, elapsed)

            # Check cancellation
            if self._cancelled:
                return self._create_cancelled_result(plan_id, steps, step_results, elapsed)

            # Execute step
            step_result = self._execute_step(step)
            step_results.append(step_result)

            # Check if step was cancelled
            if not step_result.success and step_result.error:
                if step_result.error.get("error_code") == "CANCELLED":
                    # Step was cancelled - return cancellation result
                    total_time = time.perf_counter() - start_time
                    return self._create_cancelled_result(plan_id, steps, step_results, total_time)

            # Check if step failed (fail-fast)
            if not step_result.success:
                total_time = time.perf_counter() - start_time
                return MultiStepResult(
                    plan_id=plan_id,
                    success=False,
                    completed_steps=len(step_results),
                    total_steps=len(steps),
                    step_results=step_results,
                    total_execution_time=total_time,
                    failed_at_step=step.step_number,
                    error={
                        "error_code": "STEP_FAILED",
                        "message": f"Step {step.step_number} failed",
                        "details": {
                            "step_number": step.step_number,
                            "step_error": step_result.error,
                        },
                        "recoverable": False,
                    },
                )

            # Store result in context if output binding specified
            if step.output_binding:
                self._execution_context[step.output_binding] = step_result.result_data

        # All steps completed successfully
        total_time = time.perf_counter() - start_time
        return MultiStepResult(
            plan_id=plan_id,
            success=True,
            completed_steps=len(step_results),
            total_steps=len(steps),
            step_results=step_results,
            total_execution_time=total_time,
        )

    def _execute_step(self, step: PlanStep) -> StepResult:
        """Execute a single step with parameter binding.

        Args:
            step: Step to execute

        Returns:
            StepResult with execution result
        """
        start_time = time.perf_counter()

        try:
            # Check cancellation before starting step
            if self._cancelled:
                execution_time = time.perf_counter() - start_time
                return StepResult(
                    step_number=step.step_number,
                    action_id=step.action.action_id,
                    success=False,
                    error={
                        "error_code": "CANCELLED",
                        "message": "Step execution was cancelled",
                        "details": {},
                        "recoverable": False,
                    },
                    execution_time=execution_time,
                )

            # Bind parameters from previous step results
            bound_parameters = self._bind_parameters(
                step.action.parameters,
                step.parameter_bindings,
            )

            # Create action with bound parameters
            bound_action = Action(
                action_id=step.action.action_id,
                tool_id=step.action.tool_id,
                parameters=bound_parameters,
                is_sensitive=step.action.is_sensitive,
                estimated_duration=step.action.estimated_duration,
            )

            # Create cancellation token that references our _cancelled flag
            # This allows the executor to check cancellation in real-time
            cancellation_token = {"cancelled": False, "check_fn": lambda: self._cancelled}

            # Execute action with cancellation support
            timeout = step.timeout or self.default_step_timeout
            exec_result = self.sync_executor.execute(
                bound_action,
                step.tool_function,
                timeout,
                cancellation_token=cancellation_token,
            )

            # Convert to StepResult
            execution_time = time.perf_counter() - start_time
            return StepResult(
                step_number=step.step_number,
                action_id=step.action.action_id,
                success=exec_result.success,
                result_data=exec_result.result_data,
                error=exec_result.error,
                execution_time=execution_time,
            )

        except Exception as e:
            # Unexpected error during step execution
            execution_time = time.perf_counter() - start_time
            return StepResult(
                step_number=step.step_number,
                action_id=step.action.action_id,
                success=False,
                error={
                    "error_code": "STEP_EXECUTION_ERROR",
                    "message": str(e),
                    "details": {"exception_type": type(e).__name__},
                    "recoverable": False,
                },
                execution_time=execution_time,
            )

    def _bind_parameters(
        self,
        parameters: dict[str, Any],
        bindings: dict[str, str],
    ) -> dict[str, Any]:
        """Bind parameters from previous step results.

        Args:
            parameters: Original parameters
            bindings: Parameter bindings (param_name -> context_key)

        Returns:
            Parameters with bound values
        """
        bound_params = parameters.copy()

        for param_name, context_key in bindings.items():
            if context_key in self._execution_context:
                bound_params[param_name] = self._execution_context[context_key]

        return bound_params

    def _validate_plan(self, steps: list[PlanStep]) -> dict[str, Any] | None:
        """Validate plan before execution.

        Args:
            steps: Steps to validate

        Returns:
            Error dict if invalid, None if valid
        """
        # Check step count
        if len(steps) == 0:
            return {
                "error_code": "EMPTY_PLAN",
                "message": "Plan has no steps",
                "details": {},
                "recoverable": False,
            }

        if len(steps) > self.max_steps:
            return {
                "error_code": "TOO_MANY_STEPS",
                "message": f"Plan has {len(steps)} steps, maximum is {self.max_steps}",
                "details": {"step_count": len(steps), "max_steps": self.max_steps},
                "recoverable": False,
            }

        # Check step numbers are sequential
        for i, step in enumerate(steps, start=1):
            if step.step_number != i:
                return {
                    "error_code": "INVALID_STEP_NUMBER",
                    "message": f"Step numbers must be sequential, expected {i}, got {step.step_number}",
                    "details": {"expected": i, "actual": step.step_number},
                    "recoverable": False,
                }

        # Check parameter bindings reference valid context keys
        for step in steps:
            for param_name, context_key in step.parameter_bindings.items():
                # Check if context key will be available
                # (must be output from previous step)
                found = False
                for prev_step in steps:
                    if prev_step.step_number >= step.step_number:
                        break
                    if prev_step.output_binding == context_key:
                        found = True
                        break

                if not found:
                    return {
                        "error_code": "INVALID_BINDING",
                        "message": f"Step {step.step_number} references undefined context key: {context_key}",
                        "details": {
                            "step_number": step.step_number,
                            "parameter": param_name,
                            "context_key": context_key,
                        },
                        "recoverable": False,
                    }

        return None

    def _create_timeout_result(
        self,
        plan_id: str,
        steps: list[PlanStep],
        step_results: list[StepResult],
        elapsed: float,
    ) -> MultiStepResult:
        """Create result for timeout scenario.

        Args:
            plan_id: Plan identifier
            steps: All steps in plan
            step_results: Results from completed steps
            elapsed: Elapsed time

        Returns:
            MultiStepResult for timeout
        """
        return MultiStepResult(
            plan_id=plan_id,
            success=False,
            completed_steps=len(step_results),
            total_steps=len(steps),
            step_results=step_results,
            total_execution_time=elapsed,
            error={
                "error_code": "PLAN_TIMEOUT",
                "message": f"Plan execution exceeded timeout of {self.total_timeout}s",
                "details": {
                    "timeout": self.total_timeout,
                    "elapsed": elapsed,
                    "completed_steps": len(step_results),
                },
                "recoverable": False,
            },
        )

    def _create_cancelled_result(
        self,
        plan_id: str,
        steps: list[PlanStep],
        step_results: list[StepResult],
        elapsed: float,
    ) -> MultiStepResult:
        """Create result for cancellation scenario.

        Args:
            plan_id: Plan identifier
            steps: All steps in plan
            step_results: Results from completed steps
            elapsed: Elapsed time

        Returns:
            MultiStepResult for cancellation
        """
        return MultiStepResult(
            plan_id=plan_id,
            success=False,
            completed_steps=len(step_results),
            total_steps=len(steps),
            step_results=step_results,
            total_execution_time=elapsed,
            error={
                "error_code": "PLAN_CANCELLED",
                "message": "Plan execution was cancelled",
                "details": {"completed_steps": len(step_results)},
                "recoverable": False,
            },
        )

    def cancel_execution(self) -> None:
        """Cancel ongoing plan execution with graceful shutdown.

        Sets cancellation flag that will be checked:
        1. Before starting each new step
        2. During current step execution (polled every 100ms)

        Current step will attempt graceful shutdown by:
        - Cancelling the underlying thread pool future
        - Returning a CANCELLED error result

        Subsequent steps will not execute after cancellation.

        Note: Cancellation is cooperative - the tool function must be
        interruptible for immediate cancellation. Long-running operations
        may take up to 100ms to detect cancellation.
        """
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if execution has been cancelled.

        Returns:
            True if cancellation has been requested, False otherwise
        """
        return self._cancelled

    def get_execution_context(self) -> dict[str, Any]:
        """Get current execution context.

        Returns:
            Dictionary of context variables
        """
        return self._execution_context.copy()

    def clear_execution_context(self) -> None:
        """Clear execution context."""
        self._execution_context.clear()
        self._cancelled = False
