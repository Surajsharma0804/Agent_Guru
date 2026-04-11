"""Shared test fixtures for response generation tests."""

from datetime import datetime, timezone

import pytest

from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType
from Agent_Guru.reasoning.models.result import ExecutionResult
from Agent_Guru.reasoning.response.template_generator import TemplateGenerator


@pytest.fixture
def generator() -> TemplateGenerator:
    """Create template generator instance."""
    return TemplateGenerator()


@pytest.fixture
def success_result() -> ExecutionResult:
    """Create successful execution result."""
    return ExecutionResult(
        success=True,
        result_data={"duration": "5 minutes"},
        execution_time=0.1,
        action_id="test_action",
        tool_id="set_timer",
        timestamp=datetime.now(tz=timezone.utc),
    )


@pytest.fixture
def error_result() -> ExecutionResult:
    """Create error execution result."""
    return ExecutionResult(
        success=False,
        error="Operation timed out",
        execution_time=5.0,
        action_id="test_action",
        tool_id="set_timer",
        timestamp=datetime.now(tz=timezone.utc),
    )


@pytest.fixture
def timer_intent() -> Intent:
    """Create timer intent."""
    return Intent(
        intent_type=IntentType.SET_TIMER,
        entities={
            "duration": Entity(
                entity_type="duration", value="5 minutes", raw_text="5 minutes", confidence=0.95
            )
        },
        confidence=0.95,
        requires_reasoning=False,
        original_input="set timer for 5 minutes",
    )
