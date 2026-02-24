"""
Task Model Generator - Converts LLM outputs into structured Task objects.

This module implements the Task Model Generator that parses LLM reasoning outputs
and converts them into validated, executable Task objects with proper lifecycle
management, confidence scoring, and validation.

Time Complexity: O(n) where n is the number of steps in the task
Space Complexity: O(n) for storing task steps

Performance Targets:
- Task generation: <50ms (95th percentile)
- Validation: <20ms (95th percentile)
- Total overhead: <70ms

Requirements: 16.1, 16.2, 16.3, 16.4, 17.1, 17.2, 17.3, 17.4, 17.5, 28.1-28.7
"""

from datetime import datetime
from typing import Any

import structlog
from pydantic import ValidationError

from Agent_Guru.reasoning.error.error_manager import (
    ErrorContext,
    ErrorType,
    get_error_manager,
)
from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskStep, TaskType

logger = structlog.get_logger(__name__)


class TaskModelGenerator:
    """
    Generates structured Task objects from LLM reasoning outputs.

    This class is responsible for:
    1. Parsing LLM JSON outputs into Task objects
    2. Validating task structure and dependencies
    3. Calculating confidence scores
    4. Classifying task types
    5. Ensuring all required fields are populated

    Time Complexity: O(n) where n is number of steps
    Space Complexity: O(n) for task storage

    Example:
        >>> generator = TaskModelGenerator()
        >>> llm_output = {
        ...     "goal": "Set a timer for 5 minutes",
        ...     "steps": [{
        ...         "step_id": 1,
        ...         "description": "Create timer",
        ...         "tool_id": "timer_tool",
        ...         "parameters": {"duration_seconds": 300}
        ...     }]
        ... }
        >>> task = generator.generate_task(llm_output, intent, confidence=0.95)
        >>> assert task.task_type == TaskType.SINGLE_STEP
        >>> assert len(task.steps) == 1
    """

    # Maximum allowed steps per task
    MAX_STEPS = 5

    # Minimum confidence threshold for task generation
    MIN_CONFIDENCE = 0.0

    # Sensitive action keywords that require confirmation
    SENSITIVE_KEYWORDS = {
        "delete",
        "remove",
        "send",
        "post",
        "publish",
        "transfer",
        "pay",
        "purchase",
        "buy",
        "call",
        "message",
        "email",
        "share",
        "upload",
    }

    def __init__(self) -> None:
        """Initialize the Task Model Generator."""
        self.logger = logger.bind(component="TaskModelGenerator")
        self.error_manager = get_error_manager()
    
    def _raise_generation_error(self, message: str, **context_data) -> None:
        """Helper to raise generation error with ErrorManager.
        
        Args:
            message: Error message
            **context_data: Additional context data
            
        Raises:
            ValueError: With user-friendly message
        """
        context = ErrorContext(additional_data=context_data)
        error = self.error_manager.create_error(
            error_type=ErrorType.PLAN_GENERATION_FAILED,
            message=message,
            context=context,
        )
        raise ValueError(error.user_message)
    
    def _raise_validation_error(self, message: str, **context_data) -> None:
        """Helper to raise validation error with ErrorManager.
        
        Args:
            message: Error message
            **context_data: Additional context data
            
        Raises:
            ValueError: With user-friendly message
        """
        context = ErrorContext(additional_data=context_data)
        error = self.error_manager.create_error(
            error_type=ErrorType.PLAN_VALIDATION_FAILED,
            message=message,
            context=context,
        )
        raise ValueError(error.user_message)

    def generate_task(
        self,
        llm_output: dict[str, Any],
        intent: Intent,
        confidence: float,
    ) -> Task:
        """
        Generate a validated Task object from LLM output.

        Time Complexity: O(n) where n is number of steps
        Space Complexity: O(n) for task storage

        Args:
            llm_output: Parsed JSON output from LLM containing task structure
            intent: Original intent that triggered task generation
            confidence: Base confidence score from LLM (0.0-1.0)

        Returns:
            Validated Task object ready for execution

        Raises:
            TaskGenerationError: If LLM output is malformed
            TaskValidationError: If generated task fails validation
            ValueError: If confidence is out of range

        Example:
            >>> generator = TaskModelGenerator()
            >>> llm_output = {
            ...     "goal": "Play music and set timer",
            ...     "steps": [
            ...         {
            ...             "step_id": 1,
            ...             "description": "Play music",
            ...             "tool_id": "music_tool",
            ...             "parameters": {"playlist": "workout"}
            ...         },
            ...         {
            ...             "step_id": 2,
            ...             "description": "Set timer",
            ...             "tool_id": "timer_tool",
            ...             "parameters": {"duration_seconds": 1800}
            ...         }
            ...     ]
            ... }
            >>> task = generator.generate_task(llm_output, intent, 0.92)
            >>> assert task.task_type == TaskType.MULTI_STEP
            >>> assert len(task.steps) == 2
        """
        start_time = datetime.now()

        try:
            # Validate confidence range
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(f"Confidence must be in [0.0, 1.0], got {confidence}")

            # Extract and validate required fields
            goal = self._extract_goal(llm_output)
            steps_data = self._extract_steps(llm_output)

            # Generate task steps
            steps = self._generate_steps(steps_data)

            # Classify task type
            task_type = self._classify_task_type(steps, intent)

            # Calculate adjusted confidence
            adjusted_confidence = self._calculate_confidence(confidence, llm_output, steps, intent)

            # Determine if confirmation is required
            requires_confirmation = self._requires_confirmation(steps, intent)

            # Calculate total estimated duration
            estimated_duration = self._calculate_total_duration(steps)

            # Create Task object
            task = Task(
                goal=goal,
                task_type=task_type,
                entities=intent.entities,
                steps=steps,
                confidence=adjusted_confidence,
                requires_confirmation=requires_confirmation,
                estimated_duration=estimated_duration,
                status=TaskStatus.PENDING,
                retry_count=0,
            )

            # Validate task structure
            self._validate_task(task)

            # Log successful generation
            generation_time = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.info(
                "task_generated",
                task_type=task_type.value,
                num_steps=len(steps),
                confidence=adjusted_confidence,
                requires_confirmation=requires_confirmation,
                generation_time_ms=generation_time,
            )

            return task

        except ValidationError as e:
            self.logger.error("task_validation_failed", error=str(e), llm_output=llm_output)
            error_manager = get_error_manager()
            error = error_manager.create_error(
                error_type=ErrorType.PLAN_VALIDATION_FAILED,
                message=f"Task validation failed: {e}",
            )
            raise ValueError(error.user_message) from e

        except Exception as e:
            self.logger.error("task_generation_failed", error=str(e), llm_output=llm_output)
            error_manager = get_error_manager()
            error = error_manager.create_error(
                error_type=ErrorType.PLAN_GENERATION_FAILED,
                message=f"Failed to generate task: {e}",
            )
            raise ValueError(error.user_message) from e

    def _extract_goal(self, llm_output: dict[str, Any]) -> str:
        """
        Extract and validate goal from LLM output.

        Args:
            llm_output: LLM output dictionary

        Returns:
            Validated goal string

        Raises:
            TaskGenerationError: If goal is missing or invalid
        """
        goal = llm_output.get("goal")

        if not goal:
            self._raise_generation_error("Missing required field: goal")

        if not isinstance(goal, str):
            self._raise_generation_error(f"Goal must be string, got {type(goal)}")

        goal_str = goal.strip() if goal else ""

        if not goal_str:
            self._raise_generation_error("Goal cannot be empty")

        if len(goal_str) > 500:
            self._raise_generation_error(f"Goal too long: {len(goal_str)} chars (max 500)")

        return goal_str

    def _extract_steps(self, llm_output: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract and validate steps from LLM output.

        Args:
            llm_output: LLM output dictionary

        Returns:
            List of step dictionaries

        Raises:
            TaskGenerationError: If steps are missing or invalid
        """
        steps = llm_output.get("steps")

        if steps is None:
            self._raise_generation_error("Missing required field: steps")

        if not isinstance(steps, list):
            self._raise_generation_error(f"Steps must be list, got {type(steps)}")

        if not steps or len(steps) == 0:
            self._raise_generation_error("Steps list cannot be empty")

        if steps and len(steps) > self.MAX_STEPS:
            self._raise_generation_error(f"Too many steps: {len(steps)} (max {self.MAX_STEPS})")

        return list(steps) if steps else []

    def _generate_steps(self, steps_data: list[dict[str, Any]]) -> list[TaskStep]:
        """
        Generate TaskStep objects from step data.

        Time Complexity: O(n) where n is number of steps
        Space Complexity: O(n) for storing steps

        Args:
            steps_data: List of step dictionaries from LLM

        Returns:
            List of validated TaskStep objects

        Raises:
            TaskGenerationError: If step data is invalid
        """
        steps: list[TaskStep] = []

        for i, step_data in enumerate(steps_data, start=1):
            try:
                # Validate step_id matches position
                step_id = step_data.get("step_id", i)
                if step_id != i:
                    self.logger.warning(
                        "step_id_mismatch",
                        expected=i,
                        actual=step_id,
                        correcting=True,
                    )
                    step_id = i

                # Extract required fields
                description = step_data.get("description", "").strip()
                if not description:
                    self._raise_generation_error(f"Step {i}: missing description")

                tool_id = step_data.get("tool_id", "").strip()
                if not tool_id:
                    self._raise_generation_error(f"Step {i}: missing tool_id")

                parameters = step_data.get("parameters", {})
                if not isinstance(parameters, dict):
                    self._raise_generation_error(
                        f"Step {i}: parameters must be dict, got {type(parameters)}"
                    )

                # Extract optional fields
                depends_on = step_data.get("depends_on", [])
                if not isinstance(depends_on, list):
                    depends_on = [depends_on] if depends_on else []

                estimated_duration = step_data.get("estimated_duration", 1.0)
                if not isinstance(estimated_duration, (int, float)):
                    estimated_duration = 1.0

                # Create TaskStep
                step = TaskStep(
                    step_id=step_id,
                    description=description,
                    tool_id=tool_id,
                    parameters=parameters,
                    depends_on=depends_on,
                    estimated_duration=float(estimated_duration),
                    status=TaskStatus.PENDING,
                )

                steps.append(step)

            except ValidationError as e:
                self._raise_generation_error(f"Step {i} validation failed: {e}")

        return list(steps) if steps else []

    def _classify_task_type(self, steps: list[TaskStep], intent: Intent) -> TaskType:
        """
        Classify task type based on steps and intent.

        Args:
            steps: List of task steps
            intent: Original intent

        Returns:
            Classified TaskType

        Example:
            >>> generator = TaskModelGenerator()
            >>> steps = [TaskStep(...)]  # Single step
            >>> task_type = generator._classify_task_type(steps, intent)
            >>> assert task_type == TaskType.SINGLE_STEP
        """
        num_steps = len(steps)

        # Single step tasks
        if num_steps == 1:
            return TaskType.SINGLE_STEP

        # Multi-step tasks (2-5 steps)
        if 2 <= num_steps <= self.MAX_STEPS:
            return TaskType.MULTI_STEP

        # Should never reach here due to validation
        self._raise_generation_error(f"Invalid number of steps: {num_steps}")

    def _calculate_confidence(
        self,
        base_confidence: float,
        llm_output: dict[str, Any],
        steps: list[TaskStep],
        intent: Intent,
    ) -> float:
        """
        Calculate adjusted confidence score based on multiple factors.

        Confidence adjustments:
        - Complete output: +0.0 (baseline)
        - Missing optional fields: -0.05 per field
        - Complex multi-step: -0.1
        - All parameters present: +0.05
        - High intent confidence: +0.1 if intent.confidence > 0.9

        Args:
            base_confidence: Base confidence from LLM
            llm_output: Full LLM output for completeness check
            steps: Generated task steps
            intent: Original intent

        Returns:
            Adjusted confidence score (0.0-1.0)

        Example:
            >>> generator = TaskModelGenerator()
            >>> confidence = generator._calculate_confidence(
            ...     0.85, llm_output, steps, intent
            ... )
            >>> assert 0.0 <= confidence <= 1.0
        """
        adjusted = base_confidence

        # Penalty for missing optional fields
        optional_fields = ["reasoning", "alternatives", "risks"]
        missing_fields = sum(1 for field in optional_fields if field not in llm_output)
        adjusted -= missing_fields * 0.05

        # Penalty for complex multi-step tasks
        if len(steps) > 3:
            adjusted -= 0.1

        # Bonus for complete parameters
        all_params_present = all(step.parameters for step in steps if step.parameters is not None)
        if all_params_present:
            adjusted += 0.05

        # Bonus for high intent confidence
        if intent.confidence > 0.9:
            adjusted += 0.1

        # Ensure bounds
        adjusted = max(0.0, min(1.0, adjusted))

        return round(adjusted, 3)

    def _requires_confirmation(self, steps: list[TaskStep], intent: Intent) -> bool:
        """
        Determine if task requires user confirmation before execution.

        Confirmation required if:
        - Any step contains sensitive keywords
        - Task has more than 3 steps
        - Intent is marked as requiring confirmation

        Args:
            steps: List of task steps
            intent: Original intent

        Returns:
            True if confirmation required, False otherwise

        Example:
            >>> generator = TaskModelGenerator()
            >>> steps = [TaskStep(tool_id="delete_file", ...)]
            >>> requires = generator._requires_confirmation(steps, intent)
            >>> assert requires is True  # "delete" is sensitive
        """
        # Check for sensitive keywords in descriptions or tool_ids
        for step in steps:
            text = f"{step.description} {step.tool_id}".lower()
            if any(keyword in text for keyword in self.SENSITIVE_KEYWORDS):
                return True

        # Multi-step tasks with >3 steps require confirmation
        if len(steps) > 3:
            return True

        # Check intent-level confirmation requirement
        # (This would be set by intent detection if needed)
        # For now, we don't have this field in Intent model

        return False

    def _calculate_total_duration(self, steps: list[TaskStep]) -> float:
        """
        Calculate total estimated duration for all steps.

        For sequential execution, this is the sum of all step durations.
        For parallel execution (future), this would be max of parallel branches.

        Args:
            steps: List of task steps

        Returns:
            Total estimated duration in seconds

        Example:
            >>> generator = TaskModelGenerator()
            >>> steps = [
            ...     TaskStep(estimated_duration=1.0, ...),
            ...     TaskStep(estimated_duration=2.0, ...)
            ... ]
            >>> duration = generator._calculate_total_duration(steps)
            >>> assert duration == 3.0
        """
        return sum(step.estimated_duration for step in steps)

    def _validate_task(self, task: Task) -> None:
        """
        Perform comprehensive validation on generated task.

        Validates:
        - Task type matches step count
        - Step IDs are sequential starting from 1
        - No circular dependencies
        - All dependencies reference valid steps
        - Total duration matches sum of step durations

        Args:
            task: Task to validate

        Raises:
            TaskValidationError: If validation fails

        Example:
            >>> generator = TaskModelGenerator()
            >>> task = Task(...)  # Valid task
            >>> generator._validate_task(task)  # No exception
        """
        # Validate task type matches step count
        num_steps = len(task.steps)

        if task.task_type == TaskType.SINGLE_STEP and num_steps != 1:
            self._raise_validation_error(f"SINGLE_STEP task must have exactly 1 step, got {num_steps}")

        if task.task_type == TaskType.MULTI_STEP and not (2 <= num_steps <= self.MAX_STEPS):
            self._raise_validation_error(
                f"MULTI_STEP task must have 2-{self.MAX_STEPS} steps, got {num_steps}"
            )

        # Validate step IDs are sequential
        expected_ids = list(range(1, num_steps + 1))
        actual_ids = [step.step_id for step in task.steps]

        if actual_ids != expected_ids:
            self._raise_validation_error(
                f"Step IDs must be sequential 1-{num_steps}, got {actual_ids}"
            )

        # Validate dependencies
        self._validate_dependencies(task.steps)

        # Validate total duration
        calculated_duration = sum(step.estimated_duration for step in task.steps)
        if abs(task.estimated_duration - calculated_duration) > 0.1:
            self._raise_validation_error(
                f"Total duration mismatch: task={task.estimated_duration}, "
                f"calculated={calculated_duration}"
            )

    def _validate_dependencies(self, steps: list[TaskStep]) -> None:
        """
        Validate step dependencies for correctness.

        Checks:
        - Dependencies reference valid step IDs
        - No circular dependencies
        - Dependencies only reference earlier steps

        Args:
            steps: List of task steps

        Raises:
            TaskValidationError: If dependencies are invalid

        Example:
            >>> generator = TaskModelGenerator()
            >>> steps = [
            ...     TaskStep(step_id=1, depends_on=[], ...),
            ...     TaskStep(step_id=2, depends_on=[1], ...)
            ... ]
            >>> generator._validate_dependencies(steps)  # Valid
        """
        step_ids = {step.step_id for step in steps}

        for step in steps:
            # Check all dependencies reference valid steps
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    self._raise_validation_error(
                        f"Step {step.step_id} depends on non-existent step {dep_id}"
                    )

                # Check dependencies only reference earlier steps
                if dep_id >= step.step_id:
                    self._raise_validation_error(
                        f"Step {step.step_id} cannot depend on step {dep_id} "
                        f"(must depend on earlier steps only)"
                    )

        # Check for circular dependencies using DFS
        self._check_circular_dependencies(steps)

    def _check_circular_dependencies(self, steps: list[TaskStep]) -> None:
        """
        Check for circular dependencies using depth-first search.

        Args:
            steps: List of task steps

        Raises:
            TaskValidationError: If circular dependency detected

        Example:
            >>> generator = TaskModelGenerator()
            >>> # Valid: 1 -> 2 -> 3
            >>> steps = [
            ...     TaskStep(step_id=1, depends_on=[], ...),
            ...     TaskStep(step_id=2, depends_on=[1], ...),
            ...     TaskStep(step_id=3, depends_on=[2], ...)
            ... ]
            >>> generator._check_circular_dependencies(steps)  # No exception
        """
        # Build adjacency list
        graph: dict[int, list[int]] = {step.step_id: step.depends_on for step in steps}

        # Track visited nodes and recursion stack
        visited: set[int] = set()
        rec_stack: set[int] = set()

        def has_cycle(node: int) -> bool:
            """DFS to detect cycle."""
            visited.add(node)
            rec_stack.add(node)

            # Check all dependencies
            for dep in graph.get(node, []):
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        # Check each node
        for step in steps:
            if step.step_id not in visited:
                if has_cycle(step.step_id):
                    self._raise_validation_error(
                        f"Circular dependency detected involving step {step.step_id}"
                    )
