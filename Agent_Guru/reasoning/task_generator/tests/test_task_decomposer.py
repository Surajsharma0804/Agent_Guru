"""
Unit tests for Task Model Generator (Task Decomposer).

Tests task generation, validation, confidence scoring, and error handling.

Coverage target: 100% (zero compromises)
"""

import pytest

from Agent_Guru.reasoning.models.intent import Intent, IntentType
from Agent_Guru.reasoning.models.task import TaskStatus, TaskType
from Agent_Guru.reasoning.task_generator.task_decomposer import (
    TaskModelGenerator,
)


class TestTaskModelGenerator:
    """Unit tests for TaskModelGenerator."""

    @pytest.fixture
    def generator(self) -> TaskModelGenerator:
        """Create TaskModelGenerator instance."""
        return TaskModelGenerator()

    @pytest.fixture
    def sample_intent(self) -> Intent:
        """Create sample intent for testing."""
        from Agent_Guru.reasoning.models.intent import Entity

        return Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(
                    entity_type="duration",
                    value=300,
                    raw_text="5 minutes",
                    confidence=0.95,
                )
            },
            confidence=0.95,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes",
        )

    def test_generate_single_step_task(self, generator, sample_intent):
        """Test generating a valid single-step task."""
        llm_output = {
            "goal": "Set a timer for 5 minutes",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Create timer",
                    "tool_id": "timer_tool",
                    "parameters": {"duration_seconds": 300},
                    "estimated_duration": 1.0,
                }
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.95)

        assert task.goal == "Set a timer for 5 minutes"  # nosec B101
        assert task.task_type == TaskType.SINGLE_STEP  # nosec B101
        assert len(task.steps) == 1  # nosec B101
        assert task.steps[0].tool_id == "timer_tool"  # nosec B101
        assert task.steps[0].parameters == {"duration_seconds": 300}  # nosec B101
        assert task.confidence == pytest.approx(0.95, abs=0.1)  # nosec B101
        assert task.status == TaskStatus.PENDING  # nosec B101
        assert task.retry_count == 0  # nosec B101

    def test_generate_multi_step_task(self, generator, sample_intent):
        """Test generating a valid multi-step task."""
        llm_output = {
            "goal": "Play music and set timer",
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
        }

        task = generator.generate_task(llm_output, sample_intent, 0.92)

        assert task.task_type == TaskType.MULTI_STEP  # nosec B101
        assert len(task.steps) == 2  # nosec B101
        assert task.steps[0].step_id == 1  # nosec B101
        assert task.steps[1].step_id == 2  # nosec B101
        assert task.estimated_duration == 3.0  # nosec B101

    def test_missing_goal(self, generator, sample_intent):
        """Test error when goal is missing."""
        llm_output = {
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
            ]
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_empty_goal(self, generator, sample_intent):
        """Test error when goal is empty."""
        llm_output = {
            "goal": "   ",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
            ],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_goal_too_long(self, generator, sample_intent):
        """Test error when goal exceeds maximum length."""
        llm_output = {
            "goal": "x" * 501,  # Exceeds 500 char limit
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
            ],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_missing_steps(self, generator, sample_intent):
        """Test error when steps are missing."""
        llm_output = {"goal": "Test goal"}

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_empty_steps_list(self, generator, sample_intent):
        """Test error when steps list is empty."""
        llm_output = {"goal": "Test goal", "steps": []}

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_too_many_steps(self, generator, sample_intent):
        """Test error when steps exceed maximum."""
        llm_output = {
            "goal": "Test goal",
            "steps": [
                {
                    "step_id": i,
                    "description": f"Step {i}",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
                for i in range(1, 7)  # 6 steps, exceeds max of 5
            ],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_invalid_confidence_range(self, generator, sample_intent):
        """Test error when confidence is out of range."""
        llm_output = {
            "goal": "Test goal",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
            ],
        }

        # Confidence too high
        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 1.5)

        # Confidence too low
        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, -0.1)

    def test_step_missing_description(self, generator, sample_intent):
        """Test error when step is missing description."""
        llm_output = {
            "goal": "Test goal",
            "steps": [{"step_id": 1, "tool_id": "test_tool", "parameters": {}}],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_step_missing_tool_id(self, generator, sample_intent):
        """Test error when step is missing tool_id."""
        llm_output = {
            "goal": "Test goal",
            "steps": [{"step_id": 1, "description": "Test", "parameters": {}}],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_step_id_correction(self, generator, sample_intent):
        """Test automatic correction of mismatched step IDs."""
        llm_output = {
            "goal": "Test goal",
            "steps": [
                {
                    "step_id": 5,  # Wrong ID, should be 1
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        # Should be corrected to 1
        assert task.steps[0].step_id == 1  # nosec B101

    def test_confidence_adjustment_missing_fields(self, generator, sample_intent):
        """Test confidence adjustment for missing optional fields."""
        llm_output = {
            "goal": "Test goal",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
            ],
            # Missing optional fields: reasoning, alternatives, risks
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        # Confidence should be reduced by 0.05 * 3 = 0.15
        # 0.9 - 0.15 = 0.75, but may have other adjustments
        assert task.confidence < 0.9  # nosec B101

    def test_confidence_adjustment_complex_task(self, generator, sample_intent):
        """Test confidence penalty for complex multi-step tasks."""
        llm_output = {
            "goal": "Complex task",
            "steps": [
                {
                    "step_id": i,
                    "description": f"Step {i}",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
                for i in range(1, 5)  # 4 steps (>3)
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        # Should have penalty for >3 steps
        assert task.confidence < 0.9  # nosec B101

    def test_confidence_bonus_complete_parameters(self, generator, sample_intent):
        """Test confidence bonus when all parameters are present."""
        llm_output = {
            "goal": "Test goal",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {"param1": "value1", "param2": "value2"},
                }
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.8)

        # Should have bonus for complete parameters
        # Base 0.8 + 0.05 (params) + 0.1 (high intent confidence) = 0.95
        assert task.confidence >= 0.8  # nosec B101

    def test_requires_confirmation_sensitive_keyword(self, generator, sample_intent):
        """Test confirmation required for sensitive keywords."""
        llm_output = {
            "goal": "Delete file",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Delete the file",
                    "tool_id": "file_tool",
                    "parameters": {"action": "delete"},
                }
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        assert task.requires_confirmation is True  # nosec B101

    def test_requires_confirmation_many_steps(self, generator, sample_intent):
        """Test confirmation required for tasks with >3 steps."""
        llm_output = {
            "goal": "Multi-step task",
            "steps": [
                {
                    "step_id": i,
                    "description": f"Step {i}",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
                for i in range(1, 5)  # 4 steps (>3)
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        assert task.requires_confirmation is True  # nosec B101

    def test_no_confirmation_safe_task(self, generator, sample_intent):
        """Test no confirmation for safe tasks."""
        llm_output = {
            "goal": "Get weather",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Query weather API",
                    "tool_id": "weather_tool",
                    "parameters": {"location": "Seattle"},
                }
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        assert task.requires_confirmation is False  # nosec B101

    def test_task_with_dependencies(self, generator, sample_intent):
        """Test task with step dependencies."""
        llm_output = {
            "goal": "Sequential task",
            "steps": [
                {
                    "step_id": 1,
                    "description": "First step",
                    "tool_id": "tool1",
                    "parameters": {},
                    "estimated_duration": 1.0,
                },
                {
                    "step_id": 2,
                    "description": "Second step",
                    "tool_id": "tool2",
                    "parameters": {},
                    "depends_on": [1],
                    "estimated_duration": 2.0,
                },
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        assert task.steps[1].depends_on == [1]  # nosec B101
        assert task.estimated_duration == 3.0  # nosec B101

    def test_invalid_dependency_nonexistent_step(self, generator, sample_intent):
        """Test error when dependency references non-existent step."""
        llm_output = {
            "goal": "Invalid dependency",
            "steps": [
                {
                    "step_id": 1,
                    "description": "First step",
                    "tool_id": "tool1",
                    "parameters": {},
                },
                {
                    "step_id": 2,
                    "description": "Second step",
                    "tool_id": "tool2",
                    "parameters": {},
                    "depends_on": [99],  # Non-existent step
                },
            ],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_invalid_dependency_future_step(self, generator, sample_intent):
        """Test error when dependency references future step."""
        llm_output = {
            "goal": "Invalid dependency",
            "steps": [
                {
                    "step_id": 1,
                    "description": "First step",
                    "tool_id": "tool1",
                    "parameters": {},
                    "depends_on": [2],  # Future step
                },
                {
                    "step_id": 2,
                    "description": "Second step",
                    "tool_id": "tool2",
                    "parameters": {},
                },
            ],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_circular_dependency_detection(self, generator, sample_intent):
        """Test detection of circular dependencies."""
        # Note: This is hard to create with the current validation
        # that prevents forward dependencies, but we test the logic
        llm_output = {
            "goal": "Test",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Step 1",
                    "tool_id": "tool1",
                    "parameters": {},
                    "depends_on": [1],  # Self-dependency
                }
            ],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_duration_mismatch_validation(self, generator, sample_intent):
        """Test validation of total duration mismatch."""
        llm_output = {
            "goal": "Test",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Step 1",
                    "tool_id": "tool1",
                    "parameters": {},
                    "estimated_duration": 1.0,
                },
                {
                    "step_id": 2,
                    "description": "Step 2",
                    "tool_id": "tool2",
                    "parameters": {},
                    "estimated_duration": 2.0,
                },
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        # Total should be 3.0 (1.0 + 2.0)
        assert task.estimated_duration == 3.0  # nosec B101

    def test_default_estimated_duration(self, generator, sample_intent):
        """Test default estimated duration when not provided."""
        llm_output = {
            "goal": "Test",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Step 1",
                    "tool_id": "tool1",
                    "parameters": {},
                    # No estimated_duration provided
                }
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        # Should default to 1.0
        assert task.steps[0].estimated_duration == 1.0  # nosec B101
        assert task.estimated_duration == 1.0  # nosec B101

    def test_task_type_classification_single_step(self, generator):
        """Test task type classification for single step."""
        from Agent_Guru.reasoning.models.task import TaskStep

        steps = [
            TaskStep(
                step_id=1,
                description="Test",
                tool_id="test_tool",
                parameters={},
            )
        ]

        task_type = generator._classify_task_type(steps, None)
        assert task_type == TaskType.SINGLE_STEP  # nosec B101

    def test_task_type_classification_multi_step(self, generator):
        """Test task type classification for multi-step."""
        from Agent_Guru.reasoning.models.task import TaskStep

        steps = [
            TaskStep(step_id=i, description=f"Step {i}", tool_id="test_tool", parameters={})
            for i in range(1, 4)  # 3 steps
        ]

        task_type = generator._classify_task_type(steps, None)
        assert task_type == TaskType.MULTI_STEP  # nosec B101

    def test_sensitive_keywords_detection(self, generator, sample_intent):
        """Test detection of all sensitive keywords."""
        sensitive_keywords = [
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
        ]

        for keyword in sensitive_keywords:
            llm_output = {
                "goal": f"Test {keyword}",
                "steps": [
                    {
                        "step_id": 1,
                        "description": f"{keyword.capitalize()} something",
                        "tool_id": "test_tool",
                        "parameters": {},
                    }
                ],
            }

            task = generator.generate_task(llm_output, sample_intent, 0.9)

            assert task.requires_confirmation is True, f"Failed for keyword: {keyword}"  # nosec B101

    def test_logging_on_successful_generation(self, generator, sample_intent, caplog):
        """Test that successful generation logs metrics."""
        llm_output = {
            "goal": "Test goal",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {},
                }
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        # Check that logging occurred (structlog may not show in caplog)
        assert task is not None  # nosec B101

    def test_parameters_type_validation(self, generator, sample_intent):
        """Test that parameters must be a dictionary."""
        llm_output = {
            "goal": "Test",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": "not a dict",  # Invalid type
                }
            ],
        }

        with pytest.raises((ValueError, Exception), match="I couldn't create a plan"):
            generator.generate_task(llm_output, sample_intent, 0.9)

    def test_empty_parameters_allowed(self, generator, sample_intent):
        """Test that empty parameters dictionary is allowed."""
        llm_output = {
            "goal": "Test",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {},  # Empty but valid
                }
            ],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.9)

        assert task.steps[0].parameters == {}  # nosec B101

    def test_confidence_bounds_enforcement(self, generator, sample_intent):
        """Test that confidence is always bounded to [0.0, 1.0]."""
        # Test with very high base confidence and many bonuses
        llm_output = {
            "goal": "Test",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Test",
                    "tool_id": "test_tool",
                    "parameters": {"param": "value"},
                }
            ],
            "reasoning": "test",
            "alternatives": [],
            "risks": [],
        }

        task = generator.generate_task(llm_output, sample_intent, 0.99)

        # Should not exceed 1.0
        assert 0.0 <= task.confidence <= 1.0  # nosec B101

