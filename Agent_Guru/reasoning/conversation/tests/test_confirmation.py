"""
Tests for confirmation logic.
"""

import pytest

from Agent_Guru.reasoning.conversation.confirmation import (
    ConfirmationGenerator,
    ConfirmationParser,
    ConfirmationRules,
    SensitiveActionCategory,
)
from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskStep, TaskType


class TestConfirmationRules:
    """Test confirmation rules."""

    def test_requires_confirmation_sensitive_tool(self):
        """Test confirmation required for sensitive tool."""
        task = Task(
            goal="Send a message",
            task_type=TaskType.SINGLE_STEP,
            entities={"recipient": "John", "message": "Hello"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Send message",
                    tool_id="send_message",
                    parameters={"recipient": "John", "message": "Hello"},
                    estimated_duration=1.0,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        requires, category = ConfirmationRules.requires_confirmation(task)

        assert requires is True  # nosec B101
        assert category == SensitiveActionCategory.MESSAGING  # nosec B101

    def test_no_confirmation_safe_tool(self):
        """Test no confirmation for safe tool."""
        task = Task(
            goal="Set a timer",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=1.0,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        requires, category = ConfirmationRules.requires_confirmation(task)

        assert requires is False  # nosec B101
        assert category is None  # nosec B101

    def test_batch_confirmation_multi_step(self):
        """Test batch confirmation for multi-step task."""
        task = Task(
            goal="Send messages",
            task_type=TaskType.MULTI_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Send message 1",
                    tool_id="send_message",
                    parameters={"recipient": "John", "message": "Hello"},
                    estimated_duration=1.0,
                ),
                TaskStep(
                    step_id=2,
                    description="Send message 2",
                    tool_id="send_message",
                    parameters={"recipient": "Jane", "message": "Hi"},
                    estimated_duration=1.0,
                ),
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=2.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        should_batch = ConfirmationRules.should_batch_confirm(task)

        assert should_batch is True  # nosec B101

    def test_risk_level_high(self):
        """Test high risk level for dangerous actions."""
        risk = ConfirmationRules.get_risk_level(
            SensitiveActionCategory.FILE_DELETION,
            Task(
                goal="Delete file",
                task_type=TaskType.SINGLE_STEP,
                entities={},
                steps=[
                    TaskStep(
                        step_id=1,
                        description="Delete file",
                        tool_id="delete_file",
                        parameters={"path": "/important/file.txt"},
                        estimated_duration=1.0,
                    )
                ],
                confidence=0.9,
                requires_confirmation=True,
                estimated_duration=1.0,
                status=TaskStatus.PENDING,
                retry_count=0,
            ),
        )

        assert risk == "high"  # nosec B101


class TestConfirmationGenerator:
    """Test confirmation generator."""

    def test_generate_confirmation_messaging(self):
        """Test generating confirmation for messaging."""
        generator = ConfirmationGenerator()

        task = Task(
            goal="Send a message",
            task_type=TaskType.SINGLE_STEP,
            entities={"recipient": "John", "message": "Hello"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Send message",
                    tool_id="send_message",
                    parameters={"recipient": "John", "message": "Hello"},
                    estimated_duration=1.0,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        confirmation = generator.generate_confirmation(task)

        assert confirmation is not None  # nosec B101
        assert confirmation.category == SensitiveActionCategory.MESSAGING  # nosec B101
        assert "John" in confirmation.action_description  # nosec B101
        assert confirmation.is_batch is False  # nosec B101

    def test_generate_batch_confirmation(self):
        """Test generating batch confirmation."""
        generator = ConfirmationGenerator()

        task = Task(
            goal="Send messages",
            task_type=TaskType.MULTI_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Send message to John",
                    tool_id="send_message",
                    parameters={"recipient": "John", "message": "Hello"},
                    estimated_duration=1.0,
                ),
                TaskStep(
                    step_id=2,
                    description="Send message to Jane",
                    tool_id="send_message",
                    parameters={"recipient": "Jane", "message": "Hi"},
                    estimated_duration=1.0,
                ),
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=2.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        confirmation = generator.generate_confirmation(task)

        assert confirmation is not None  # nosec B101
        assert confirmation.is_batch is True  # nosec B101
        assert len(confirmation.batch_items) == 2  # nosec B101


class TestConfirmationParser:
    """Test confirmation parser."""

    def test_parse_positive_confirmation(self):
        """Test parsing positive confirmation."""
        response = ConfirmationParser.parse_confirmation("yes")

        assert response.confirmed is True  # nosec B101
        assert response.confidence > 0.8  # nosec B101

    def test_parse_negative_confirmation(self):
        """Test parsing negative confirmation."""
        response = ConfirmationParser.parse_confirmation("no")

        assert response.confirmed is False  # nosec B101
        assert response.confidence > 0.8  # nosec B101

    def test_parse_ambiguous_response(self):
        """Test parsing ambiguous response."""
        response = ConfirmationParser.parse_confirmation("maybe later")

        assert response.confirmed is False  # nosec B101
        assert response.confidence < 0.5  # nosec B101


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
