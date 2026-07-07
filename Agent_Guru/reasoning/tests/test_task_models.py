"""
Unit tests for Task data models.

Tests Task and TaskStep models including validation, state transitions,
and helper methods.

Coverage target: 80%+
"""


import pytest
from pydantic import ValidationError

from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskStep, TaskType


class TestTaskStep:
    """Unit tests for TaskStep model."""

    def test_valid_task_step(self):
        """Test creating a valid TaskStep."""
        step = TaskStep(
            step_id=1,
            description="Test step",
            tool_id="test_tool",
            parameters={"param1": "value1"},
            estimated_duration=2.0,
        )

        assert step.step_id == 1  # nosec B101
        assert step.description == "Test step"  # nosec B101
        assert step.tool_id == "test_tool"  # nosec B101
        assert step.parameters == {"param1": "value1"}  # nosec B101
        assert step.estimated_duration == 2.0  # nosec B101
        assert step.status == TaskStatus.PENDING  # nosec B101
        assert step.depends_on == []  # nosec B101

    def test_step_with_dependencies(self):
        """Test TaskStep with dependencies."""
        step = TaskStep(
            step_id=2,
            description="Dependent step",
            tool_id="test_tool",
            parameters={},
            depends_on=[1],
        )

        assert step.depends_on == [1]  # nosec B101

    def test_invalid_step_id(self):
        """Test that step_id must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            TaskStep(step_id=0, description="Test", tool_id="test_tool", parameters={})

        assert "step_id" in str(exc_info.value).lower()  # nosec B101

    def test_invalid_dependency(self):
        """Test that dependencies must reference earlier steps."""
        with pytest.raises(ValidationError) as exc_info:
            TaskStep(
                step_id=2,
                description="Test",
                tool_id="test_tool",
                parameters={},
                depends_on=[2],  # Cannot depend on itself
            )

        assert "depend" in str(exc_info.value).lower()  # nosec B101

    def test_invalid_duration(self):
        """Test duration validation."""
        # Too short
        with pytest.raises(ValidationError):
            TaskStep(
                step_id=1,
                description="Test",
                tool_id="test_tool",
                parameters={},
                estimated_duration=0.05,  # < 0.1
            )

        # Too long
        with pytest.raises(ValidationError):
            TaskStep(
                step_id=1,
                description="Test",
                tool_id="test_tool",
                parameters={},
                estimated_duration=100.0,  # > 60
            )

    def test_empty_description(self):
        """Test that description cannot be empty."""
        with pytest.raises(ValidationError):
            TaskStep(step_id=1, description="", tool_id="test_tool", parameters={})

    def test_empty_tool_id(self):
        """Test that tool_id cannot be empty."""
        with pytest.raises(ValidationError):
            TaskStep(step_id=1, description="Test", tool_id="", parameters={})


class TestTask:
    """Unit tests for Task model."""

    def test_valid_single_step_task(self):
        """Test creating a valid single-step task."""
        task = Task(
            goal="Set a timer",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Create timer",
                    tool_id="timer_tool",
                    parameters={"duration_seconds": 300},
                    estimated_duration=1.0,
                )
            ],
            confidence=0.95,
            estimated_duration=1.0,
        )

        assert task.goal == "Set a timer"  # nosec B101
        assert task.task_type == TaskType.SINGLE_STEP  # nosec B101
        assert len(task.steps) == 1  # nosec B101
        assert task.confidence == 0.95  # nosec B101
        assert task.status == TaskStatus.PENDING  # nosec B101
        assert task.retry_count == 0  # nosec B101

    def test_valid_multi_step_task(self):
        """Test creating a valid multi-step task."""
        task = Task(
            goal="Play music and set timer",
            task_type=TaskType.MULTI_STEP,
            entities={"playlist": "workout", "duration": "30 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Play music",
                    tool_id="music_tool",
                    parameters={"playlist": "workout"},
                    estimated_duration=2.0,
                ),
                TaskStep(
                    step_id=2,
                    description="Set timer",
                    tool_id="timer_tool",
                    parameters={"duration_seconds": 1800},
                    estimated_duration=1.0,
                ),
            ],
            confidence=0.92,
            estimated_duration=3.0,
        )

        assert task.task_type == TaskType.MULTI_STEP  # nosec B101
        assert len(task.steps) == 2  # nosec B101

    def test_invalid_single_step_with_multiple_steps(self):
        """Test that single_step task must have exactly 1 step."""
        with pytest.raises(ValidationError) as exc_info:
            Task(
                goal="Test",
                task_type=TaskType.SINGLE_STEP,
                steps=[
                    TaskStep(step_id=1, description="Step 1", tool_id="tool1", parameters={}),
                    TaskStep(step_id=2, description="Step 2", tool_id="tool2", parameters={}),
                ],
                confidence=0.9,
                estimated_duration=2.0,
            )

        assert "single_step" in str(exc_info.value).lower()  # nosec B101

    def test_invalid_multi_step_with_one_step(self):
        """Test that multi_step task must have 2-5 steps."""
        with pytest.raises(ValidationError) as exc_info:
            Task(
                goal="Test",
                task_type=TaskType.MULTI_STEP,
                steps=[TaskStep(step_id=1, description="Step 1", tool_id="tool1", parameters={})],
                confidence=0.9,
                estimated_duration=1.0,
            )

        assert "multi_step" in str(exc_info.value).lower()  # nosec B101

    def test_too_many_steps(self):
        """Test that task cannot have more than 5 steps."""
        with pytest.raises(ValidationError):
            Task(
                goal="Test",
                task_type=TaskType.MULTI_STEP,
                steps=[
                    TaskStep(step_id=i, description=f"Step {i}", tool_id="tool", parameters={})
                    for i in range(1, 7)  # 6 steps
                ],
                confidence=0.9,
                estimated_duration=6.0,
            )

    def test_invalid_step_ids(self):
        """Test that step IDs must be sequential starting from 1."""
        with pytest.raises(ValidationError) as exc_info:
            Task(
                goal="Test",
                task_type=TaskType.MULTI_STEP,
                steps=[
                    TaskStep(step_id=1, description="Step 1", tool_id="tool1", parameters={}),
                    TaskStep(
                        step_id=3, description="Step 3", tool_id="tool3", parameters={}
                    ),  # Skip 2
                ],
                confidence=0.9,
                estimated_duration=2.0,
            )

        assert "sequential" in str(exc_info.value).lower()  # nosec B101

    def test_circular_dependency(self):
        """Test that circular dependencies are detected."""
        with pytest.raises(ValidationError):
            Task(
                goal="Test",
                task_type=TaskType.SINGLE_STEP,
                steps=[
                    TaskStep(
                        step_id=1,
                        description="Step 1",
                        tool_id="tool1",
                        parameters={},
                        depends_on=[1],  # Depends on itself
                    )
                ],
                confidence=0.9,
                estimated_duration=1.0,
            )

    def test_invalid_confidence(self):
        """Test confidence validation."""
        # Too low
        with pytest.raises(ValidationError):
            Task(
                goal="Test",
                task_type=TaskType.SINGLE_STEP,
                steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
                confidence=-0.1,
                estimated_duration=1.0,
            )

        # Too high
        with pytest.raises(ValidationError):
            Task(
                goal="Test",
                task_type=TaskType.SINGLE_STEP,
                steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
                confidence=1.5,
                estimated_duration=1.0,
            )

    def test_duration_mismatch(self):
        """Test that total duration should match sum of step durations."""
        with pytest.raises(ValidationError) as exc_info:
            Task(
                goal="Test",
                task_type=TaskType.MULTI_STEP,
                steps=[
                    TaskStep(
                        step_id=1,
                        description="Step 1",
                        tool_id="tool1",
                        parameters={},
                        estimated_duration=2.0,
                    ),
                    TaskStep(
                        step_id=2,
                        description="Step 2",
                        tool_id="tool2",
                        parameters={},
                        estimated_duration=3.0,
                    ),
                ],
                confidence=0.9,
                estimated_duration=10.0,  # Should be ~5.0
            )

        assert "duration" in str(exc_info.value).lower()  # nosec B101

    def test_increment_retry(self):
        """Test retry count increment."""
        task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
            confidence=0.9,
            estimated_duration=1.0,
        )

        assert task.retry_count == 0  # nosec B101
        task.increment_retry()
        assert task.retry_count == 1  # nosec B101
        task.increment_retry()
        assert task.retry_count == 2  # nosec B101
        task.increment_retry()
        assert task.retry_count == 3  # nosec B101

        # Cannot exceed 3
        with pytest.raises(ValueError):
            task.increment_retry()

    def test_mark_started(self):
        """Test marking task as started."""
        task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
            confidence=0.9,
            estimated_duration=1.0,
        )

        assert task.status == TaskStatus.PENDING  # nosec B101
        assert task.started_at is None  # nosec B101

        task.mark_started()

        assert task.status == TaskStatus.RUNNING  # nosec B101
        assert task.started_at is not None  # nosec B101

    def test_mark_completed(self):
        """Test marking task as completed."""
        task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
            confidence=0.9,
            estimated_duration=1.0,
        )

        task.mark_completed()

        assert task.status == TaskStatus.COMPLETED  # nosec B101
        assert task.completed_at is not None  # nosec B101

    def test_mark_failed(self):
        """Test marking task as failed."""
        task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
            confidence=0.9,
            estimated_duration=1.0,
        )

        task.mark_failed("Test error")

        assert task.status == TaskStatus.FAILED  # nosec B101
        assert task.error == "Test error"  # nosec B101
        assert task.completed_at is not None  # nosec B101

    def test_mark_cancelled(self):
        """Test marking task as cancelled."""
        task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
            confidence=0.9,
            estimated_duration=1.0,
        )

        task.mark_cancelled()

        assert task.status == TaskStatus.CANCELLED  # nosec B101
        assert task.completed_at is not None  # nosec B101

    def test_can_retry(self):
        """Test retry eligibility check."""
        task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
            confidence=0.9,
            estimated_duration=1.0,
        )

        # Pending task cannot retry
        assert not task.can_retry()  # nosec B101

        # Failed task can retry
        task.mark_failed("Error")
        assert task.can_retry()  # nosec B101

        # After 3 retries, cannot retry
        task.retry_count = 3
        assert not task.can_retry()  # nosec B101

    def test_is_complete(self):
        """Test completion check."""
        task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
            confidence=0.9,
            estimated_duration=1.0,
        )

        # Pending is not complete
        assert not task.is_complete()  # nosec B101

        # Running is not complete
        task.mark_started()
        assert not task.is_complete()  # nosec B101

        # Completed is complete
        task.mark_completed()
        assert task.is_complete()  # nosec B101

    def test_get_next_pending_step(self):
        """Test getting next pending step."""
        task = Task(
            goal="Test",
            task_type=TaskType.MULTI_STEP,
            steps=[
                TaskStep(
                    step_id=1,
                    description="Step 1",
                    tool_id="tool1",
                    parameters={},
                    estimated_duration=1.0,
                ),
                TaskStep(
                    step_id=2,
                    description="Step 2",
                    tool_id="tool2",
                    parameters={},
                    depends_on=[1],
                    estimated_duration=1.0,
                ),
            ],
            confidence=0.9,
            estimated_duration=2.0,
        )

        # First step is next
        next_step = task.get_next_pending_step()
        assert next_step is not None  # nosec B101
        assert next_step.step_id == 1  # nosec B101

        # Mark first step as completed
        task.steps[0].status = TaskStatus.COMPLETED

        # Second step is next
        next_step = task.get_next_pending_step()
        assert next_step is not None  # nosec B101
        assert next_step.step_id == 2  # nosec B101

        # Mark second step as completed
        task.steps[1].status = TaskStatus.COMPLETED

        # No more pending steps
        next_step = task.get_next_pending_step()
        assert next_step is None  # nosec B101

    def test_get_completed_steps(self):
        """Test getting completed steps."""
        task = Task(
            goal="Test",
            task_type=TaskType.MULTI_STEP,
            steps=[
                TaskStep(
                    step_id=1,
                    description="Step 1",
                    tool_id="tool1",
                    parameters={},
                    estimated_duration=1.0,
                ),
                TaskStep(
                    step_id=2,
                    description="Step 2",
                    tool_id="tool2",
                    parameters={},
                    estimated_duration=1.0,
                ),
            ],
            confidence=0.9,
            estimated_duration=2.0,
        )

        # No completed steps initially
        assert len(task.get_completed_steps()) == 0  # nosec B101

        # Mark first step as completed
        task.steps[0].status = TaskStatus.COMPLETED
        assert len(task.get_completed_steps()) == 1  # nosec B101

        # Mark second step as completed
        task.steps[1].status = TaskStatus.COMPLETED
        assert len(task.get_completed_steps()) == 2  # nosec B101

    def test_get_failed_steps(self):
        """Test getting failed steps."""
        task = Task(
            goal="Test",
            task_type=TaskType.MULTI_STEP,
            steps=[
                TaskStep(
                    step_id=1,
                    description="Step 1",
                    tool_id="tool1",
                    parameters={},
                    estimated_duration=1.0,
                ),
                TaskStep(
                    step_id=2,
                    description="Step 2",
                    tool_id="tool2",
                    parameters={},
                    estimated_duration=1.0,
                ),
            ],
            confidence=0.9,
            estimated_duration=2.0,
        )

        # No failed steps initially
        assert len(task.get_failed_steps()) == 0  # nosec B101

        # Mark first step as failed
        task.steps[0].status = TaskStatus.FAILED
        assert len(task.get_failed_steps()) == 1  # nosec B101

    def test_calculate_progress(self):
        """Test progress calculation."""
        task = Task(
            goal="Test",
            task_type=TaskType.MULTI_STEP,
            steps=[
                TaskStep(
                    step_id=1,
                    description="Step 1",
                    tool_id="tool1",
                    parameters={},
                    estimated_duration=1.0,
                ),
                TaskStep(
                    step_id=2,
                    description="Step 2",
                    tool_id="tool2",
                    parameters={},
                    estimated_duration=1.0,
                ),
            ],
            confidence=0.9,
            estimated_duration=2.0,
        )

        # 0% progress initially
        assert task.calculate_progress() == 0.0  # nosec B101

        # 50% after first step
        task.steps[0].status = TaskStatus.COMPLETED
        assert task.calculate_progress() == 0.5  # nosec B101

        # 100% after both steps
        task.steps[1].status = TaskStatus.COMPLETED
        assert task.calculate_progress() == 1.0  # nosec B101

    def test_json_serialization(self):
        """Test JSON serialization."""
        task = Task(
            goal="Test",
            task_type=TaskType.SINGLE_STEP,
            steps=[TaskStep(step_id=1, description="Test", tool_id="tool", parameters={})],
            confidence=0.9,
            estimated_duration=1.0,
        )

        # Should be able to serialize to JSON
        json_str = task.model_dump_json()
        assert isinstance(json_str, str)  # nosec B101
        assert "Test" in json_str  # nosec B101

        # Should be able to deserialize from JSON
        task2 = Task.model_validate_json(json_str)
        assert task2.goal == task.goal  # nosec B101
        assert task2.task_type == task.task_type  # nosec B101
