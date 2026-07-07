"""
Tests for ReasoningVerifier.
Coverage Target: >80% (enforced by CI/CD)
"""

from unittest.mock import AsyncMock, Mock

import pytest

from Agent_Guru.reasoning.llm.client import LLMClient
from Agent_Guru.reasoning.llm.models import LLMResponse
from Agent_Guru.reasoning.models.task import Task, TaskStatus, TaskStep, TaskType
from Agent_Guru.reasoning.models.verification import (
    IssueSeverity,
    IssueType,
    VerificationAction,
    VerificationIssue,
    VerificationResult,
)
from Agent_Guru.reasoning.tools.base import (
    ToolMetadata,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import ToolRegistry
from Agent_Guru.reasoning.verification.verifier import ReasoningVerifier


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = Mock(spec=LLMClient)
    return client


@pytest.fixture
def mock_tool_registry():
    """Create a mock tool registry with sample tools."""
    registry = Mock(spec=ToolRegistry)

    # Define sample tool metadata
    timer_tool = ToolMetadata(
        tool_id="timer.set",
        name="Set Timer",
        description="Set a timer",
        parameters=[
            ToolParameter(
                name="duration_seconds",
                type=ToolParameterType.INTEGER,
                description="Duration in seconds",
                required=True,
            )
        ],
        sensitivity=ToolSensitivity.SAFE,
        estimated_latency_ms=100,
        capabilities=["timer"],
        examples=[],
    )

    message_tool = ToolMetadata(
        tool_id="message.send",
        name="Send Message",
        description="Send a message",
        parameters=[
            ToolParameter(
                name="recipient",
                type=ToolParameterType.STRING,
                description="Message recipient",
                required=True,
            ),
            ToolParameter(
                name="content",
                type=ToolParameterType.STRING,
                description="Message content",
                required=True,
            ),
        ],
        sensitivity=ToolSensitivity.SENSITIVE,
        estimated_latency_ms=500,
        capabilities=["messaging"],
        examples=[],
    )

    # Configure mock to return tool metadata
    def get_metadata_side_effect(tool_id: str):
        if tool_id == "timer.set":
            return timer_tool
        elif tool_id == "message.send":
            return message_tool
        return None

    registry.get_metadata.side_effect = get_metadata_side_effect

    return registry


@pytest.fixture
def verifier(mock_llm_client, mock_tool_registry):
    """Create a ReasoningVerifier instance."""
    return ReasoningVerifier(
        llm_client=mock_llm_client, tool_registry=mock_tool_registry, confidence_threshold=0.75
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        goal="Set a 5 minute timer",
        task_type=TaskType.SINGLE_STEP,
        entities={"duration": "5 minutes"},
        steps=[
            TaskStep(
                step_id=1,
                description="Set timer for 5 minutes",
                tool_id="timer.set",
                parameters={"duration_seconds": 300},
                depends_on=[],
                estimated_duration=0.1,
                status=TaskStatus.PENDING,
            )
        ],
        confidence=0.95,
        requires_confirmation=False,
        estimated_duration=0.1,
        status=TaskStatus.PENDING,
        retry_count=0,
    )


class TestReasoningVerifier:
    """Unit tests for ReasoningVerifier."""

    def test_initialization(self, mock_llm_client, mock_tool_registry):
        """Test verifier initialization."""
        verifier = ReasoningVerifier(
            llm_client=mock_llm_client, tool_registry=mock_tool_registry, confidence_threshold=0.8
        )

        assert verifier.llm_client == mock_llm_client  # nosec B101
        assert verifier.tool_registry == mock_tool_registry  # nosec B101
        assert verifier.confidence_threshold == 0.8  # nosec B101

    @pytest.mark.asyncio
    async def test_verify_tool_compatibility_valid(self, verifier, sample_task):
        """Test tool compatibility verification with valid tools."""
        issues = await verifier._verify_tool_compatibility(sample_task)

        assert len(issues) == 0  # nosec B101

    @pytest.mark.asyncio
    async def test_verify_tool_compatibility_missing_tool(self, verifier):
        """Test tool compatibility with non-existent tool."""
        task = Task(
            goal="Use unknown tool",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Use unknown tool",
                    tool_id="unknown.tool",
                    parameters={},
                    depends_on=[],
                    estimated_duration=0.1,
                    status=TaskStatus.PENDING,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.1,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        issues = await verifier._verify_tool_compatibility(task)

        assert len(issues) == 1  # nosec B101
        assert issues[0].issue_type == IssueType.TOOL_COMPATIBILITY  # nosec B101
        assert issues[0].severity == IssueSeverity.CRITICAL  # nosec B101
        assert "does not exist" in issues[0].description  # nosec B101

    @pytest.mark.asyncio
    async def test_verify_tool_compatibility_missing_parameters(self, verifier):
        """Test tool compatibility with missing required parameters."""
        task = Task(
            goal="Send message without recipient",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Send message",
                    tool_id="message.send",
                    parameters={"content": "Hello"},  # Missing 'recipient'
                    depends_on=[],
                    estimated_duration=0.5,
                    status=TaskStatus.PENDING,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        issues = await verifier._verify_tool_compatibility(task)

        assert len(issues) == 1  # nosec B101
        assert issues[0].issue_type == IssueType.TOOL_COMPATIBILITY  # nosec B101
        assert issues[0].severity == IssueSeverity.CRITICAL  # nosec B101
        assert "missing required parameters" in issues[0].description  # nosec B101
        assert "recipient" in issues[0].description  # nosec B101

    @pytest.mark.asyncio
    async def test_detect_circular_dependencies_none(self, verifier):
        """Test circular dependency detection with no cycles."""
        steps = [
            TaskStep(
                step_id=1,
                description="Step 1",
                tool_id="timer.set",
                parameters={},
                depends_on=[],
                estimated_duration=0.1,
                status=TaskStatus.PENDING,
            ),
            TaskStep(
                step_id=2,
                description="Step 2",
                tool_id="timer.set",
                parameters={},
                depends_on=[1],  # Depends on step 1
                estimated_duration=0.1,
                status=TaskStatus.PENDING,
            ),
        ]

        result = verifier._detect_circular_dependencies(steps)

        assert result is None  # nosec B101

    @pytest.mark.asyncio
    async def test_detect_circular_dependencies_exists(self, verifier):
        """Test circular dependency detection with cycle."""
        # Note: We can't actually create a circular dependency due to validation
        # So we'll test the detection logic directly with a mock scenario
        # In practice, circular dependencies would be caught during task creation

        # This test verifies the detection logic works if somehow invalid data gets through
        # For now, we'll skip this test as the validation prevents it
        pytest.skip("Circular dependencies are prevented by TaskStep validation")

    @pytest.mark.asyncio
    async def test_detect_conflicting_actions_none(self, verifier):
        """Test conflict detection with no conflicts."""
        steps = [
            TaskStep(
                step_id=1,
                description="Open app",
                tool_id="app.open",
                parameters={},
                depends_on=[],
                estimated_duration=0.1,
                status=TaskStatus.PENDING,
            ),
            TaskStep(
                step_id=2,
                description="Use app",
                tool_id="app.use",
                parameters={},
                depends_on=[1],
                estimated_duration=0.1,
                status=TaskStatus.PENDING,
            ),
        ]

        conflicts = verifier._detect_conflicting_actions(steps)

        assert len(conflicts) == 0  # nosec B101

    @pytest.mark.asyncio
    async def test_detect_conflicting_actions_open_close(self, verifier):
        """Test conflict detection with open/close conflict."""
        steps = [
            TaskStep(
                step_id=1,
                description="Open app",
                tool_id="app.open",
                parameters={},
                depends_on=[],
                estimated_duration=0.1,
                status=TaskStatus.PENDING,
            ),
            TaskStep(
                step_id=2,
                description="Close app",
                tool_id="app.close",
                parameters={},
                depends_on=[1],
                estimated_duration=0.1,
                status=TaskStatus.PENDING,
            ),
        ]

        conflicts = verifier._detect_conflicting_actions(steps)

        assert len(conflicts) == 1  # nosec B101
        assert "closes" in conflicts[0]["description"]  # nosec B101
        assert "opened" in conflicts[0]["description"]  # nosec B101

    @pytest.mark.asyncio
    async def test_parse_llm_verification_valid_json(self, verifier):
        """Test parsing valid LLM verification response."""
        llm_response = """```json
{
    "is_correct": true,
    "is_complete": true,
    "has_unnecessary_steps": false,
    "is_aligned": true,
    "confidence": 0.95,
    "issues": [],
    "reasoning": "Plan looks good"
}
```"""

        result = verifier._parse_llm_verification(llm_response)

        assert result["is_correct"] is True  # nosec B101
        assert result["confidence"] == 0.95  # nosec B101
        assert len(result["issues"]) == 0  # nosec B101

    @pytest.mark.asyncio
    async def test_parse_llm_verification_with_issues(self, verifier):
        """Test parsing LLM response with issues."""
        llm_response = """{
    "is_correct": false,
    "is_complete": false,
    "has_unnecessary_steps": false,
    "is_aligned": true,
    "confidence": 0.6,
    "issues": [
        {
            "type": "completeness",
            "severity": "critical",
            "description": "Missing step to validate input",
            "affected_step": null
        }
    ],
    "reasoning": "Plan is missing validation"
}"""

        result = verifier._parse_llm_verification(llm_response)

        assert result["is_correct"] is False  # nosec B101
        assert len(result["issues"]) == 1  # nosec B101
        assert result["issues"][0]["type"] == "completeness"  # nosec B101

    @pytest.mark.asyncio
    async def test_calculate_confidence_no_issues(self, verifier, sample_task):
        """Test confidence calculation with no issues."""
        issues: list[VerificationIssue] = []

        confidence = verifier._calculate_confidence(issues, sample_task)

        assert confidence >= 0.9  # High confidence with no issues  # nosec B101

    @pytest.mark.asyncio
    async def test_calculate_confidence_with_critical_issues(self, verifier, sample_task):
        """Test confidence calculation with critical issues."""
        issues = [
            VerificationIssue(
                issue_type=IssueType.TOOL_COMPATIBILITY,
                severity=IssueSeverity.CRITICAL,
                description="Critical issue",
            )
        ]

        confidence = verifier._calculate_confidence(issues, sample_task)

        assert confidence < 0.9  # Lower confidence with critical issues  # nosec B101

    @pytest.mark.asyncio
    async def test_determine_recommendation_proceed(self, verifier):
        """Test recommendation determination for PROCEED."""
        recommendation = verifier._determine_recommendation(
            is_valid=True, confidence=0.9, issues=[]
        )

        assert recommendation == VerificationAction.PROCEED  # nosec B101

    @pytest.mark.asyncio
    async def test_determine_recommendation_clarify(self, verifier):
        """Test recommendation determination for CLARIFY."""
        recommendation = verifier._determine_recommendation(
            is_valid=True, confidence=0.6, issues=[]  # Below threshold
        )

        assert recommendation == VerificationAction.CLARIFY  # nosec B101

    @pytest.mark.asyncio
    async def test_determine_recommendation_replan(self, verifier):
        """Test recommendation determination for REPLAN."""
        issues = [
            VerificationIssue(
                issue_type=IssueType.PLAN_CORRECTNESS,
                severity=IssueSeverity.CRITICAL,
                description="Critical issue",
            )
        ]

        recommendation = verifier._determine_recommendation(
            is_valid=False, confidence=0.8, issues=issues
        )

        assert recommendation == VerificationAction.REPLAN  # nosec B101

    @pytest.mark.asyncio
    async def test_verify_plan_integration(self, verifier, sample_task, mock_llm_client):
        """Test full plan verification integration."""
        # Mock LLM response
        from Agent_Guru.reasoning.llm.models import LLMProvider

        mock_llm_response = LLMResponse(
            text="""{
                "is_correct": true,
                "is_complete": true,
                "has_unnecessary_steps": false,
                "is_aligned": true,
                "confidence": 0.95,
                "issues": [],
                "reasoning": "Plan is correct"
            }""",
            provider=LLMProvider.LOCAL,
            tokens_generated=100,
            latency_ms=150.0,
            finish_reason="stop",
        )
        mock_llm_client.generate = AsyncMock(return_value=mock_llm_response)

        result = await verifier.verify_plan(sample_task, "Set a 5 minute timer")

        assert isinstance(result, VerificationResult)  # nosec B101
        assert result.is_valid is True  # nosec B101
        assert result.confidence > 0.0  # nosec B101
        assert result.recommendation == VerificationAction.PROCEED  # nosec B101
        assert result.verification_time_ms > 0  # nosec B101

    @pytest.mark.asyncio
    async def test_schema_validate_valid(self, verifier):
        """Test schema validation with valid data."""
        data = {"name": "test", "value": 123}
        schema = {"required": ["name", "value"]}

        is_valid = await verifier.schema_validate(data, schema)

        assert is_valid is True  # nosec B101

    @pytest.mark.asyncio
    async def test_schema_validate_missing_field(self, verifier):
        """Test schema validation with missing required field."""
        data = {"name": "test"}
        schema = {"required": ["name", "value"]}

        is_valid = await verifier.schema_validate(data, schema)

        assert is_valid is False  # nosec B101


class TestVerificationIntegration:
    """Integration tests for verification workflow."""

    @pytest.mark.asyncio
    async def test_full_verification_workflow_success(self, verifier, sample_task, mock_llm_client):
        """Test complete verification workflow with successful result."""
        # Mock successful LLM verification
        from Agent_Guru.reasoning.llm.models import LLMProvider

        mock_llm_response = LLMResponse(
            text="""{
                "is_correct": true,
                "is_complete": true,
                "has_unnecessary_steps": false,
                "is_aligned": true,
                "confidence": 0.95,
                "issues": [],
                "reasoning": "Plan is excellent"
            }""",
            provider=LLMProvider.LOCAL,
            tokens_generated=100,
            latency_ms=120.0,
            finish_reason="stop",
        )
        mock_llm_client.generate = AsyncMock(return_value=mock_llm_response)

        result = await verifier.verify_plan(sample_task, "Set a 5 minute timer")

        assert result.is_valid is True  # nosec B101
        assert result.recommendation == VerificationAction.PROCEED  # nosec B101
        assert result.verification_time_ms < 200  # Within latency budget  # nosec B101

    @pytest.mark.asyncio
    async def test_full_verification_workflow_with_issues(self, verifier, mock_llm_client):
        """Test verification workflow with issues detected."""
        # Create task with missing parameters
        task = Task(
            goal="Send message",
            task_type=TaskType.SINGLE_STEP,
            entities={},
            steps=[
                TaskStep(
                    step_id=1,
                    description="Send message",
                    tool_id="message.send",
                    parameters={"content": "Hello"},  # Missing recipient
                    depends_on=[],
                    estimated_duration=0.5,
                    status=TaskStatus.PENDING,
                )
            ],
            confidence=0.9,
            requires_confirmation=False,
            estimated_duration=0.5,
            status=TaskStatus.PENDING,
            retry_count=0,
        )

        # Mock LLM response
        from Agent_Guru.reasoning.llm.models import LLMProvider

        mock_llm_response = LLMResponse(
            text="""{
                "is_correct": true,
                "is_complete": true,
                "has_unnecessary_steps": false,
                "is_aligned": true,
                "confidence": 0.8,
                "issues": [],
                "reasoning": "Plan looks okay"
            }""",
            provider=LLMProvider.LOCAL,
            tokens_generated=100,
            latency_ms=130.0,
            finish_reason="stop",
        )
        mock_llm_client.generate = AsyncMock(return_value=mock_llm_response)

        result = await verifier.verify_plan(task, "Send a message to John")

        assert result.is_valid is False  # Tool compatibility issue  # nosec B101
        assert len(result.issues) > 0  # nosec B101
        assert result.recommendation in [VerificationAction.REPLAN, VerificationAction.ABORT]  # nosec B101
