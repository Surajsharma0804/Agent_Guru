"""
LLM output parser for structured Task generation.

This module implements parsing and validation of LLM JSON outputs into
validated Task objects. It includes JSON schema validation, retry logic
for malformed responses, and confidence scoring based on output quality.

Performance Target: <100ms for parsing and validation
Accuracy Target: >95% successful parsing rate

Requirements: 16.2, 17.2, 17.3, 17.5
"""

import json
import re
import time
from typing import Any, Optional

from pydantic import ValidationError

from Agent_Guru.reasoning.config.logging import get_logger
from Agent_Guru.reasoning.config.metrics import (
    CONFIDENCE_SCORE_HISTOGRAM,
    PARSING_FAILURE_COUNTER,
    PARSING_LATENCY,
    PARSING_RETRY_COUNTER,
    PARSING_SUCCESS_COUNTER,
)
from Agent_Guru.reasoning.models.task import Task, TaskType

logger = get_logger(__name__)


class OutputParsingError(Exception):
    """Exception raised when LLM output parsing fails."""

    def __init__(self, message: str, raw_output: Optional[str] = None, retry_count: int = 0):
        """
        Initialize parsing error.

        Args:
            message: Error message
            raw_output: Raw LLM output that failed to parse
            retry_count: Number of retries attempted
        """
        super().__init__(message)
        self.raw_output = raw_output
        self.retry_count = retry_count


class TaskOutputParser:
    """
    Parser for LLM outputs into structured Task objects.

    Implements JSON schema validation, retry logic, and confidence scoring
    to ensure high-quality Task generation from LLM outputs.

    Features:
    - JSON extraction from LLM responses (handles markdown code blocks)
    - Schema validation with descriptive error messages
    - Retry logic with exponential backoff (max 3 retries)
    - Confidence scoring based on completeness and consistency
    - Detailed error logging and metrics tracking

    Performance:
    - Target latency: <100ms for parsing and validation
    - Success rate: >95% for well-formed LLM outputs
    """

    def __init__(self, max_retries: int = 3):
        """
        Initialize output parser.

        Args:
            max_retries: Maximum number of retry attempts (default 3)
        """
        self.max_retries = max_retries
        self.logger = get_logger(__name__)

    def parse(self, llm_output: str, retry_count: int = 0) -> tuple[Task, float]:
        """
        Parse LLM output into validated Task object.

        This is the main entry point for parsing LLM outputs. It handles
        JSON extraction, validation, and confidence scoring.

        Args:
            llm_output: Raw LLM output string (may contain JSON in markdown)
            retry_count: Current retry attempt (0-indexed)

        Returns:
            Tuple of (Task object, confidence score)

        Raises:
            OutputParsingError: If parsing fails after all retries

        Example:
            >>> parser = TaskOutputParser()
            >>> llm_output = '{"goal": "Set timer", "task_type": "single_step", ...}'
            >>> task, confidence = parser.parse(llm_output)
            >>> print(f"Task: {task.goal}, Confidence: {confidence}")
        """
        start_time = time.time()

        try:
            # Extract JSON from LLM output
            json_str = self._extract_json(llm_output)

            # Parse JSON
            task_dict = json.loads(json_str)

            # Validate and create Task object
            task = Task(**task_dict)

            # Calculate confidence score
            confidence = self._calculate_confidence(task, task_dict)

            # Track metrics
            latency_ms = (time.time() - start_time) * 1000
            PARSING_LATENCY.observe(latency_ms)
            PARSING_SUCCESS_COUNTER.inc()
            CONFIDENCE_SCORE_HISTOGRAM.observe(confidence)

            self.logger.info(
                "Successfully parsed Task",
                extra={
                    "goal": task.goal,
                    "task_type": task.task_type,
                    "steps": len(task.steps),
                    "confidence": confidence,
                    "latency_ms": latency_ms,
                    "retry_count": retry_count,
                },
            )

            return task, confidence

        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            # Track failure
            PARSING_FAILURE_COUNTER.inc()

            error_msg = f"Failed to parse LLM output: {str(e)}"
            self.logger.error(
                error_msg,
                extra={
                    "error_type": type(e).__name__,
                    "retry_count": retry_count,
                    "raw_output": llm_output[:500],  # First 500 chars
                },
            )

            raise OutputParsingError(error_msg, raw_output=llm_output, retry_count=retry_count)

    def parse_with_retry(self, llm_output_generator, initial_prompt: str) -> tuple[Task, float]:
        """
        Parse LLM output with automatic retry on failure.

        If parsing fails, this method will retry up to max_retries times
        with exponential backoff. Each retry generates a new LLM output
        with an error-correcting prompt.

        Args:
            llm_output_generator: Callable that generates LLM output
                                 Takes (prompt: str, retry_count: int) -> str
            initial_prompt: Initial prompt for LLM

        Returns:
            Tuple of (Task object, confidence score)

        Raises:
            OutputParsingError: If parsing fails after all retries

        Example:
            >>> def generate_output(prompt, retry_count):
            ...     return llm_client.generate(prompt)
            >>> parser = TaskOutputParser(max_retries=3)
            >>> task, confidence = parser.parse_with_retry(generate_output, prompt)
        """
        last_error = None

        for retry_count in range(self.max_retries + 1):
            try:
                # Generate LLM output
                if retry_count == 0:
                    prompt = initial_prompt
                else:
                    # Add error correction to prompt
                    prompt = self._create_retry_prompt(initial_prompt, last_error)
                    PARSING_RETRY_COUNTER.inc()

                    # Exponential backoff
                    backoff_ms = 100 * (2 ** (retry_count - 1))  # 100ms, 200ms, 400ms
                    time.sleep(backoff_ms / 1000)

                llm_output = llm_output_generator(prompt, retry_count)

                # Try to parse
                return self.parse(llm_output, retry_count)

            except OutputParsingError as e:
                last_error = e

                if retry_count < self.max_retries:
                    self.logger.warning(
                        f"Parsing failed, retrying ({retry_count + 1}/{self.max_retries})",
                        extra={"error": str(e)},
                    )
                else:
                    self.logger.error(
                        f"Parsing failed after {self.max_retries} retries", extra={"error": str(e)}
                    )
                    raise

        # Should never reach here, but just in case
        raise last_error or OutputParsingError("Unknown parsing error")

    def _extract_json(self, llm_output: str) -> str:
        """
        Extract JSON from LLM output.

        Handles various formats:
        - Plain JSON
        - JSON in markdown code blocks (```json ... ```)
        - JSON with surrounding text

        Args:
            llm_output: Raw LLM output

        Returns:
            Extracted JSON string

        Raises:
            ValueError: If no valid JSON found
        """
        # Remove leading/trailing whitespace
        output = llm_output.strip()

        # Try to extract from markdown code block
        code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        match = re.search(code_block_pattern, output, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find JSON object boundaries
        # Look for outermost { ... }
        start_idx = output.find("{")
        if start_idx == -1:
            raise ValueError("No JSON object found in output")

        # Find matching closing brace
        brace_count = 0
        for i in range(start_idx, len(output)):
            if output[i] == "{":
                brace_count += 1
            elif output[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    return output[start_idx : i + 1]

        raise ValueError("No complete JSON object found in output")

    def _calculate_confidence(self, task: Task, task_dict: dict[str, Any]) -> float:
        """
        Calculate confidence score based on Task quality.

        Confidence is based on:
        - LLM-provided confidence (if present)
        - Completeness of fields
        - Consistency of data
        - Quality of descriptions

        Args:
            task: Validated Task object
            task_dict: Raw task dictionary from JSON

        Returns:
            Confidence score (0.0-1.0)
        """
        # Start with LLM-provided confidence if present
        base_confidence = task.confidence

        # Adjust based on completeness
        completeness_score = self._score_completeness(task, task_dict)

        # Adjust based on consistency
        consistency_score = self._score_consistency(task)

        # Adjust based on description quality
        quality_score = self._score_quality(task)

        # Weighted average
        final_confidence = (
            base_confidence * 0.5
            + completeness_score * 0.2
            + consistency_score * 0.2
            + quality_score * 0.1
        )

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, final_confidence))

    def _score_completeness(self, task: Task, task_dict: dict[str, Any]) -> float:
        """
        Score based on completeness of fields.

        Checks:
        - All required fields present
        - Entities extracted
        - Step parameters populated
        - Descriptions provided

        Returns:
            Completeness score (0.0-1.0)
        """
        score = 1.0

        # Check if entities are extracted
        if not task.entities:
            score -= 0.2

        # Check if all steps have parameters
        for step in task.steps:
            if not step.parameters:
                score -= 0.1

        # Check if descriptions are meaningful (>10 chars)
        if len(task.goal) < 10:
            score -= 0.1

        for step in task.steps:
            if len(step.description) < 10:
                score -= 0.05

        return max(0.0, score)

    def _score_consistency(self, task: Task) -> float:
        """
        Score based on internal consistency.

        Checks:
        - Task type matches step count
        - Estimated durations are reasonable
        - Dependencies are valid
        - Tool IDs are consistent

        Returns:
            Consistency score (0.0-1.0)
        """
        score = 1.0

        # Check task type consistency (already validated, but double-check)
        if task.task_type == TaskType.SINGLE_STEP and len(task.steps) != 1:
            score -= 0.3
        elif task.task_type == TaskType.MULTI_STEP and not 2 <= len(task.steps) <= 5:
            score -= 0.3

        # Check duration consistency
        step_total = sum(step.estimated_duration for step in task.steps)
        if abs(task.estimated_duration - step_total) > step_total * 0.2:
            score -= 0.2

        # Check for reasonable durations (0.1s to 60s per step)
        for step in task.steps:
            if not 0.1 <= step.estimated_duration <= 60.0:
                score -= 0.1

        # Check dependencies are valid
        for step in task.steps:
            for dep_id in step.depends_on:
                if dep_id >= step.step_id:
                    score -= 0.2

        return max(0.0, score)

    def _score_quality(self, task: Task) -> float:
        """
        Score based on description quality.

        Checks:
        - Descriptions are clear and specific
        - No placeholder text
        - Proper capitalization
        - Reasonable length

        Returns:
            Quality score (0.0-1.0)
        """
        score = 1.0

        # Check for placeholder text
        placeholders = ["TODO", "TBD", "...", "placeholder", "example"]
        for placeholder in placeholders:
            if placeholder.lower() in task.goal.lower():
                score -= 0.3
            for step in task.steps:
                if placeholder.lower() in step.description.lower():
                    score -= 0.1

        # Check for proper capitalization (first letter uppercase)
        if task.goal and not task.goal[0].isupper():
            score -= 0.1

        # Check for reasonable length (not too short, not too long)
        if len(task.goal) < 5 or len(task.goal) > 200:
            score -= 0.1

        for step in task.steps:
            if len(step.description) < 5 or len(step.description) > 200:
                score -= 0.05

        return max(0.0, score)

    def _create_retry_prompt(self, original_prompt: str, error: OutputParsingError) -> str:
        """
        Create retry prompt with error correction guidance.

        Args:
            original_prompt: Original prompt that failed
            error: Parsing error from previous attempt

        Returns:
            Enhanced prompt with error correction
        """
        error_msg = str(error)

        retry_guidance = f"""
IMPORTANT: The previous response had a parsing error. Please fix the following issue:

Error: {error_msg}

Make sure to:
1. Return ONLY valid JSON (no extra text before or after)
2. Include all required fields: goal, task_type, entities, steps, confidence, requires_confirmation, estimated_duration
3. Ensure step_id values are sequential starting from 1
4. Ensure estimated_duration matches sum of step durations
5. Ensure task_type matches step count (single_step=1, multi_step=2-5)
6. Use valid enum values for task_type and status

Original request:
{original_prompt}

Please generate a corrected Task object:
"""

        return retry_guidance

    def validate_schema(self, task_dict: dict[str, Any]) -> list[str]:
        """
        Validate task dictionary against schema.

        Performs detailed schema validation and returns list of issues.
        This is useful for debugging and providing detailed error messages.

        Args:
            task_dict: Task dictionary to validate

        Returns:
            List of validation error messages (empty if valid)

        Example:
            >>> parser = TaskOutputParser()
            >>> task_dict = {"goal": "Test", "task_type": "invalid"}
            >>> errors = parser.validate_schema(task_dict)
            >>> print(errors)
            ['task_type must be one of: single_step, multi_step, conversational, memory_query']
        """
        errors = []

        # Check required fields
        required_fields = [
            "goal",
            "task_type",
            "steps",
            "confidence",
            "requires_confirmation",
            "estimated_duration",
        ]
        for field in required_fields:
            if field not in task_dict:
                errors.append(f"Missing required field: {field}")

        # Validate task_type
        if "task_type" in task_dict:
            valid_types = [t.value for t in TaskType]
            if task_dict["task_type"] not in valid_types:
                errors.append(
                    f"task_type must be one of: {', '.join(valid_types)}, "
                    f"got {task_dict['task_type']}"
                )

        # Validate steps
        if "steps" in task_dict:
            steps = task_dict["steps"]
            if not isinstance(steps, list):
                errors.append("steps must be a list")
            elif len(steps) == 0:
                errors.append("steps must contain at least one step")
            elif len(steps) > 5:
                errors.append(f"steps cannot contain more than 5 steps, got {len(steps)}")
            else:
                # Validate each step
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        errors.append(f"Step {i+1} must be a dictionary")
                        continue

                    # Check required step fields
                    step_required = ["step_id", "description", "tool_id", "parameters"]
                    for field in step_required:
                        if field not in step:
                            errors.append(f"Step {i+1} missing required field: {field}")

                    # Validate step_id
                    if "step_id" in step and step["step_id"] != i + 1:
                        errors.append(
                            f"Step {i+1} has incorrect step_id: {step['step_id']} "
                            f"(expected {i+1})"
                        )

        # Validate confidence
        if "confidence" in task_dict:
            conf = task_dict["confidence"]
            if not isinstance(conf, (int, float)):
                errors.append("confidence must be a number")
            elif not 0.0 <= conf <= 1.0:
                errors.append(f"confidence must be 0.0-1.0, got {conf}")

        # Validate estimated_duration
        if "estimated_duration" in task_dict:
            duration = task_dict["estimated_duration"]
            if not isinstance(duration, (int, float)):
                errors.append("estimated_duration must be a number")
            elif duration <= 0:
                errors.append(f"estimated_duration must be positive, got {duration}")

        return errors


# Convenience function for quick parsing
def parse_task_from_llm(llm_output: str, max_retries: int = 3) -> tuple[Task, float]:
    """
    Convenience function to parse Task from LLM output.

    Args:
        llm_output: Raw LLM output string
        max_retries: Maximum retry attempts (default 3)

    Returns:
        Tuple of (Task object, confidence score)

    Raises:
        OutputParsingError: If parsing fails

    Example:
        >>> llm_output = '{"goal": "Set timer", ...}'
        >>> task, confidence = parse_task_from_llm(llm_output)
    """
    parser = TaskOutputParser(max_retries=max_retries)
    return parser.parse(llm_output)
