"""
Tests for clarification rules and templates.
"""

import pytest

from Agent_Guru.reasoning.conversation.clarification import (
    ClarificationGenerator,
    ClarificationRules,
    ClarificationTrigger,
)
from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskStep, TaskType


class TestClarificationRules:
    """Test clarification rules."""

    def test_should_clarify_low_confidence(self):
        """Test clarification needed for low confidence."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(
                    entity_type="duration", value=300, raw_text="5 minutes", confidence=0.9
                )
            },
            confidence=0.6,
            original_input="Set a timer for 5 minutes",
        )
        task = Task(
            goal="Set a timer",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer for 5 minutes",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=1.0,
                )
            ],
            confidence=0.6,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        should_clarify, trigger = ClarificationRules.should_clarify(intent, task, 0.6)

        assert should_clarify is True
        assert trigger == ClarificationTrigger.LOW_CONFIDENCE

    def test_should_not_clarify_high_confidence(self):
        """Test no clarification for high confidence."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(
                    entity_type="duration", value=300, raw_text="5 minutes", confidence=0.9
                )
            },
            confidence=0.9,
            original_input="Set a timer for 5 minutes",
        )
        task = Task(
            goal="Set a timer",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer for 5 minutes",
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

        should_clarify, trigger = ClarificationRules.should_clarify(intent, task, 0.9)

        assert should_clarify is False
        assert trigger is None

    def test_should_clarify_missing_entities(self):
        """Test clarification needed for missing entities."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={},
            confidence=0.8,
            original_input="Set a timer",
        )
        task = Task(
            goal="Set a timer",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer",
                    tool_id="set_timer",
                    parameters={},
                    estimated_duration=1.0,
                )
            ],
            confidence=0.8,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        should_clarify, trigger = ClarificationRules.should_clarify(intent, task, 0.8)

        assert should_clarify is True
        assert trigger == ClarificationTrigger.MISSING_ENTITIES

    def test_should_offer_options_ambiguous(self):
        """Test offering options for ambiguous intent."""
        alternatives = [("set_timer", 0.6), ("set_alarm", 0.5)]

        should_offer = ClarificationRules.should_offer_options(
            ClarificationTrigger.AMBIGUOUS_INTENT, alternatives
        )

        assert should_offer is True

    def test_should_not_offer_options_no_alternatives(self):
        """Test not offering options without alternatives."""
        alternatives = []

        should_offer = ClarificationRules.should_offer_options(
            ClarificationTrigger.LOW_CONFIDENCE, alternatives
        )

        assert should_offer is False


class TestClarificationGenerator:
    """Test clarification generator."""

    def test_generate_clarification_low_confidence(self):
        """Test generating clarification for low confidence."""
        generator = ClarificationGenerator()

        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(
                    entity_type="duration", value=300, raw_text="5 minutes", confidence=0.9
                )
            },
            confidence=0.6,
            original_input="Set a timer for 5 minutes",
        )
        task = Task(
            goal="Set a timer",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer for 5 minutes",
                    tool_id="set_timer",
                    parameters={"duration": 300},
                    estimated_duration=1.0,
                )
            ],
            confidence=0.6,
            requires_confirmation=False,
            estimated_duration=1.0,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        clarification = generator.generate_clarification(intent, task, 0.6)

        assert clarification is not None
        assert clarification.trigger == ClarificationTrigger.LOW_CONFIDENCE
        assert len(clarification.question) > 0

    def test_generate_clarification_with_options(self):
        """Test generating clarification with multiple options."""
        generator = ClarificationGenerator()

        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={},
            confidence=0.5,
            original_input="Set something",
        )
        task = None
        alternatives = [("set_timer", 0.6), ("set_alarm", 0.5)]

        clarification = generator.generate_clarification(intent, task, 0.5, alternatives)

        assert clarification is not None
        assert len(clarification.options) > 0
        assert clarification.is_open_ended is False

    def test_no_clarification_high_confidence(self):
        """Test no clarification for high confidence."""
        generator = ClarificationGenerator()

        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            entities={
                "duration": Entity(
                    entity_type="duration", value=300, raw_text="5 minutes", confidence=0.9
                )
            },
            confidence=0.9,
            original_input="Set a timer for 5 minutes",
        )
        task = Task(
            goal="Set a timer",
            task_type=TaskType.SINGLE_STEP,
            entities={"duration": "5 minutes"},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Set timer for 5 minutes",
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

        clarification = generator.generate_clarification(intent, task, 0.9)

        assert clarification is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
