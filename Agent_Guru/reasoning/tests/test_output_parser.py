"""
Unit tests for LLM output parser.

Tests JSON extraction, validation, retry logic, and confidence scoring.

Coverage target: 80%+
"""

import json

import pytest

from Agent_Guru.reasoning.llm.output_parser import (
    TaskOutputParser,
    parse_task_from_llm,
)
from Agent_Guru.reasoning.models.task import Task, TaskType


class TestTaskOutputParser:
    """Unit tests for TaskOutputParser."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON output."""
        parser = TaskOutputParser()

        llm_output = json.dumps(
            {
                "goal": "Set a timer",
                "task_type": "single_step",
                "entities": {"duration": "5 minutes"},
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Create timer",
                        "tool_id": "timer_tool",
                        "parameters": {"duration_seconds": 300},
                        "estimated_duration": 1.0,
                    }
                ],
                "confidence": 0.95,
                "requires_confirmation": False,
                "estimated_duration": 1.0,
            }
        )

        task, confidence = parser.parse(llm_output)

        assert isinstance(task, Task)  # nosec B101
        assert task.goal == "Set a timer"  # nosec B101
        assert task.task_type == TaskType.SINGLE_STEP  # nosec B101
        assert len(task.steps) == 1  # nosec B101
        assert 0.0 <= confidence <= 1.0  # nosec B101

    def test_parse_json_in_markdown(self):
        """Test extracting JSON from markdown code block."""
        parser = TaskOutputParser()

        task_dict = {
            "goal": "Test task",
            "task_type": "single_step",
            "entities": {},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test step",
                    "tool_id": "test_tool",
                    "parameters": {},
                    "estimated_duration": 1.0,
                }
            ],
            "confidence": 0.9,
            "requires_confirmation": False,
            "estimated_duration": 1.0,
        }

        llm_output = f"Here's the task:\n\n```json\n{json.dumps(task_dict)}\n```\n\nDone!"

        task, confidence = parser.parse(llm_output)

        assert isinstance(task, Task)  # nosec B101
        assert task.goal == "Test task"  # nosec B101

    def test_parse_json_with_surrounding_text(self):
        """Test extracting JSON with surrounding text."""
        parser = TaskOutputParser()

        task_dict = {
            "goal": "Test task",
            "task_type": "single_step",
            "entities": {},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test step",
                    "tool_id": "test_tool",
                    "parameters": {},
                    "estimated_duration": 1.0,
                }
            ],
            "confidence": 0.9,
            "requires_confirmation": False,
            "estimated_duration": 1.0,
        }

        llm_output = f"Sure, here's the task object:\n\n{json.dumps(task_dict)}\n\nLet me know if you need anything else!"

        task, confidence = parser.parse(llm_output)

        assert isinstance(task, Task)  # nosec B101
        assert task.goal == "Test task"  # nosec B101

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON raises error."""
        parser = TaskOutputParser()

        llm_output = "This is not JSON at all!"

        with pytest.raises((ValueError, Exception)) as exc_info:
            parser.parse(llm_output)

        # Error message should indicate parsing issue (either technical or user-friendly)
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["parse", "json", "confusing", "response"])  # nosec B101

    def test_parse_malformed_json(self):
        """Test parsing malformed JSON raises error."""
        parser = TaskOutputParser()

        llm_output = '{"goal": "Test", "task_type": "single_step"'  # Missing closing brace

        with pytest.raises((ValueError, Exception)):
            parser.parse(llm_output)

    def test_parse_missing_required_fields(self):
        """Test parsing JSON with missing required fields."""
        parser = TaskOutputParser()

        llm_output = json.dumps(
            {
                "goal": "Test task",
                # Missing task_type, steps, confidence, estimated_duration
            }
        )

        with pytest.raises((ValueError, Exception)):
            parser.parse(llm_output)

    def test_parse_invalid_task_type(self):
        """Test parsing with invalid task_type."""
        parser = TaskOutputParser()

        llm_output = json.dumps(
            {
                "goal": "Test task",
                "task_type": "invalid_type",
                "entities": {},
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Test",
                        "tool_id": "tool",
                        "parameters": {},
                        "estimated_duration": 1.0,
                    }
                ],
                "confidence": 0.9,
                "requires_confirmation": False,
                "estimated_duration": 1.0,
            }
        )

        with pytest.raises((ValueError, Exception)):
            parser.parse(llm_output)

    def test_parse_multi_step_task(self):
        """Test parsing multi-step task."""
        parser = TaskOutputParser()

        llm_output = json.dumps(
            {
                "goal": "Play music and set timer",
                "task_type": "multi_step",
                "entities": {"playlist": "workout", "duration": "30 minutes"},
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Play music",
                        "tool_id": "music_tool",
                        "parameters": {"playlist": "workout"},
                        "estimated_duration": 2.0,
                    },
                    {
                        "step_id": 2,
                        "description": "Set timer",
                        "tool_id": "timer_tool",
                        "parameters": {"duration_seconds": 1800},
                        "estimated_duration": 1.0,
                    },
                ],
                "confidence": 0.92,
                "requires_confirmation": False,
                "estimated_duration": 3.0,
            }
        )

        task, confidence = parser.parse(llm_output)

        assert task.task_type == TaskType.MULTI_STEP  # nosec B101
        assert len(task.steps) == 2  # nosec B101
        assert task.steps[0].step_id == 1  # nosec B101
        assert task.steps[1].step_id == 2  # nosec B101

    def test_confidence_scoring(self):
        """Test confidence scoring adjustments."""
        parser = TaskOutputParser()

        # High quality task
        high_quality = json.dumps(
            {
                "goal": "Set a timer for 5 minutes",
                "task_type": "single_step",
                "entities": {"duration": "5 minutes", "duration_seconds": 300},
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Create a 5-minute timer",
                        "tool_id": "timer_tool",
                        "parameters": {"duration_seconds": 300, "label": "Timer"},
                        "estimated_duration": 1.0,
                    }
                ],
                "confidence": 0.95,
                "requires_confirmation": False,
                "estimated_duration": 1.0,
            }
        )

        task1, conf1 = parser.parse(high_quality)

        # Low quality task (minimal entities, short descriptions)
        low_quality = json.dumps(
            {
                "goal": "Test",
                "task_type": "single_step",
                "entities": {},
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Do it",
                        "tool_id": "tool",
                        "parameters": {},
                        "estimated_duration": 1.0,
                    }
                ],
                "confidence": 0.95,
                "requires_confirmation": False,
                "estimated_duration": 1.0,
            }
        )

        task2, conf2 = parser.parse(low_quality)

        # High quality should have higher confidence
        assert conf1 > conf2  # nosec B101

    def test_validate_schema(self):
        """Test schema validation."""
        parser = TaskOutputParser()

        # Valid task
        valid_task = {
            "goal": "Test",
            "task_type": "single_step",
            "entities": {},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "tool",
                    "parameters": {},
                    "estimated_duration": 1.0,
                }
            ],
            "confidence": 0.9,
            "requires_confirmation": False,
            "estimated_duration": 1.0,
        }

        errors = parser.validate_schema(valid_task)
        assert len(errors) == 0  # nosec B101

        # Invalid task (missing required fields)
        invalid_task = {
            "goal": "Test"
            # Missing everything else
        }

        errors = parser.validate_schema(invalid_task)
        assert len(errors) > 0  # nosec B101
        assert any("task_type" in err for err in errors)  # nosec B101
        assert any("steps" in err for err in errors)  # nosec B101

    def test_validate_schema_invalid_step_ids(self):
        """Test schema validation catches invalid step IDs."""
        parser = TaskOutputParser()

        task_dict = {
            "goal": "Test",
            "task_type": "multi_step",
            "entities": {},
            "steps": [
                {
                    "step_id": 1,
                    "description": "Step 1",
                    "tool_id": "tool1",
                    "parameters": {},
                    "estimated_duration": 1.0,
                },
                {
                    "step_id": 3,  # Should be 2
                    "description": "Step 3",
                    "tool_id": "tool3",
                    "parameters": {},
                    "estimated_duration": 1.0,
                },
            ],
            "confidence": 0.9,
            "requires_confirmation": False,
            "estimated_duration": 2.0,
        }

        errors = parser.validate_schema(task_dict)
        assert len(errors) > 0  # nosec B101
        assert any("step_id" in err for err in errors)  # nosec B101

    def test_parse_with_retry_success_first_attempt(self):
        """Test parse_with_retry succeeds on first attempt."""
        parser = TaskOutputParser(max_retries=3)

        valid_output = json.dumps(
            {
                "goal": "Test",
                "task_type": "single_step",
                "entities": {},
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Test",
                        "tool_id": "tool",
                        "parameters": {},
                        "estimated_duration": 1.0,
                    }
                ],
                "confidence": 0.9,
                "requires_confirmation": False,
                "estimated_duration": 1.0,
            }
        )

        def generator(prompt, retry_count):
            return valid_output

        task, confidence = parser.parse_with_retry(generator, "test prompt")

        assert isinstance(task, Task)  # nosec B101
        assert task.goal == "Test"  # nosec B101

    def test_parse_with_retry_success_after_retry(self):
        """Test parse_with_retry succeeds after retry."""
        parser = TaskOutputParser(max_retries=3)

        valid_output = json.dumps(
            {
                "goal": "Test",
                "task_type": "single_step",
                "entities": {},
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Test",
                        "tool_id": "tool",
                        "parameters": {},
                        "estimated_duration": 1.0,
                    }
                ],
                "confidence": 0.9,
                "requires_confirmation": False,
                "estimated_duration": 1.0,
            }
        )

        call_count = 0

        def generator(prompt, retry_count):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "Invalid JSON"
            return valid_output

        task, confidence = parser.parse_with_retry(generator, "test prompt")

        assert isinstance(task, Task)  # nosec B101
        assert call_count == 2  # Failed once, succeeded on retry  # nosec B101

    def test_parse_with_retry_max_retries_exceeded(self):
        """Test parse_with_retry fails after max retries."""
        parser = TaskOutputParser(max_retries=2)

        def generator(prompt, retry_count):
            return "Invalid JSON"

        with pytest.raises((ValueError, Exception)):
            parser.parse_with_retry(generator, "test prompt")

    def test_create_retry_prompt(self):
        """Test retry prompt creation."""
        parser = TaskOutputParser()

        error = ValueError("Missing required field: task_type")
        original_prompt = "Create a task for setting a timer"

        retry_prompt = parser._create_retry_prompt(original_prompt, error)

        assert "error" in retry_prompt.lower()  # nosec B101
        assert "task_type" in retry_prompt  # nosec B101
        assert original_prompt in retry_prompt  # nosec B101

    def test_extract_json_plain(self):
        """Test extracting plain JSON."""
        parser = TaskOutputParser()

        json_str = '{"key": "value"}'
        extracted = parser._extract_json(json_str)

        assert extracted == json_str  # nosec B101

    def test_extract_json_markdown(self):
        """Test extracting JSON from markdown."""
        parser = TaskOutputParser()

        json_str = '{"key": "value"}'
        markdown = f"```json\n{json_str}\n```"
        extracted = parser._extract_json(markdown)

        assert extracted == json_str  # nosec B101

    def test_extract_json_with_text(self):
        """Test extracting JSON with surrounding text."""
        parser = TaskOutputParser()

        json_str = '{"key": "value"}'
        text = f"Here is the JSON: {json_str} Done!"
        extracted = parser._extract_json(text)

        assert extracted == json_str  # nosec B101

    def test_extract_json_no_json(self):
        """Test extracting JSON when none present."""
        parser = TaskOutputParser()

        text = "This is just plain text with no JSON"

        with pytest.raises(ValueError):
            parser._extract_json(text)

    def test_parse_task_from_llm_convenience(self):
        """Test convenience function."""
        llm_output = json.dumps(
            {
                "goal": "Test",
                "task_type": "single_step",
                "entities": {},
                "steps": [
                    {
                        "step_id": 1,
                        "description": "Test",
                        "tool_id": "tool",
                        "parameters": {},
                        "estimated_duration": 1.0,
                    }
                ],
                "confidence": 0.9,
                "requires_confirmation": False,
                "estimated_duration": 1.0,
            }
        )

        task, confidence = parse_task_from_llm(llm_output)

        assert isinstance(task, Task)  # nosec B101
        assert task.goal == "Test"  # nosec B101

    def test_score_completeness(self):
        """Test completeness scoring."""
        parser = TaskOutputParser()

        # Complete task
        complete_task = Task(
            goal="Set a timer for 5 minutes",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                {
                    "step_id": 1,
                    "description": "Create timer",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 300},
                }
            ],
            confidence=0.9,
            estimated_duration=1.0,
        )

        score = parser._score_completeness(complete_task, complete_task.model_dump())
        assert score > 0.8  # nosec B101

        # Incomplete task
        incomplete_task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[{"step_id": 1, "description": "Do", "tool_id": "tool", "parameters": {}}],
            confidence=0.9,
            estimated_duration=1.0,
        )

        score = parser._score_completeness(incomplete_task, incomplete_task.model_dump())
        assert score < 0.8  # nosec B101

    def test_score_consistency(self):
        """Test consistency scoring."""
        parser = TaskOutputParser()

        # Consistent task
        consistent_task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "tool",
                    "parameters": {},
                    "estimated_duration": 1.0,
                }
            ],
            confidence=0.9,
            estimated_duration=1.0,
        )

        score = parser._score_consistency(consistent_task)
        assert score > 0.8  # nosec B101

    def test_score_quality(self):
        """Test quality scoring."""
        parser = TaskOutputParser()

        # High quality task
        quality_task = Task(
            goal="Set a timer for 5 minutes",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                {
                    "step_id": 1,
                    "description": "Create a 5-minute timer",
                    "tool_id": "timer_tool",
                    "parameters": {},
                }
            ],
            confidence=0.9,
            estimated_duration=1.0,
        )

        score = parser._score_quality(quality_task)
        assert score > 0.8  # nosec B101

        # Low quality task (placeholder text)
        low_quality_task = Task(
            goal="TODO: add goal",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[{"step_id": 1, "description": "TODO", "tool_id": "tool", "parameters": {}}],
            confidence=0.9,
            estimated_duration=1.0,
        )

        score = parser._score_quality(low_quality_task)
        assert score < 0.8  # nosec B101
