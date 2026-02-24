"""
Tests for Reasoning Engine.

Coverage Target: >80% (enforced by CI/CD)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from Agent_Guru.reasoning.engine import (
    ReasoningEngine,
    ReasoningResult,
    get_reasoning_engine,
)
from Agent_Guru.reasoning.input.normalizer import (
    InputSource,
    RawInput,
)
from Agent_Guru.reasoning.models.intent import Intent, IntentType


@pytest.fixture(scope="function")
async def register_example_tools():
    """Register example tools for testing."""
    from Agent_Guru.reasoning.tools.registry import get_registry
    from Agent_Guru.reasoning.tools.examples import (
        SetTimerTool,
        CancelTimerTool,
        WeatherTool,
        MessagingTool,
        MusicTool,
        CalendarTool,
    )
    
    registry = get_registry()
    
    # Instantiate and register tools
    tools = [
        SetTimerTool(),
        CancelTimerTool(),
        WeatherTool(),
        MessagingTool(),
        MusicTool(),
        CalendarTool(),
    ]
    
    for tool in tools:
        await tool.ensure_registered()
    
    yield registry
    
    # Cleanup: unregister tools after test
    for tool in tools:
        await registry.unregister(tool.metadata.tool_id)


class TestReasoningEngine:
    """Unit tests for ReasoningEngine."""
    
    def test_initialization(self):
        """Test engine initialization."""
        engine = ReasoningEngine()
        
        assert engine.input_normalizer is not None
        assert engine.intent_engine is not None
        assert engine.tool_selector is not None
        assert engine.safety_gate is not None
        assert engine.response_generator is not None
        assert engine.latency_controller is not None
        assert engine.enable_fast_path is True
        assert engine.enable_tracing is True
    
    def test_initialization_with_custom_components(self):
        """Test engine initialization with custom components."""
        from Agent_Guru.reasoning.input.normalizer import InputNormalizer
        from Agent_Guru.reasoning.latency.controller import LatencyController
        
        normalizer = InputNormalizer()
        controller = LatencyController()
        
        engine = ReasoningEngine(
            input_normalizer=normalizer,
            latency_controller=controller,
            enable_fast_path=False,
            enable_tracing=False,
        )
        
        assert engine.input_normalizer is normalizer
        assert engine.latency_controller is controller
        assert engine.enable_fast_path is False
        assert engine.enable_tracing is False
    
    @pytest.mark.asyncio
    async def test_process_basic(self, register_example_tools):
        """Test basic request processing."""
        engine = ReasoningEngine()
        
        raw = RawInput(
            content="set a timer for 5 minutes",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        result = await engine.process(raw)
        
        assert isinstance(result, ReasoningResult)
        assert result.response is not None
        assert result.success is True
        assert result.total_latency_ms > 0
    
    @pytest.mark.asyncio
    async def test_process_with_invalid_input(self):
        """Test processing with invalid input."""
        engine = ReasoningEngine()
        
        raw = RawInput(
            content="",  # Empty input
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        result = await engine.process(raw)
        
        # Should return error result
        assert result.success is False
        assert result.error is not None
        assert "didn't understand" in result.response.lower()
    
    @pytest.mark.asyncio
    async def test_normalize_input(self):
        """Test input normalization stage."""
        engine = ReasoningEngine()
        
        raw = RawInput(
            content="  hello world  ",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        normalized = await engine._normalize_input(raw, None)
        
        assert normalized.text == "hello world"
        assert normalized.source == InputSource.TEXT
        assert normalized.user_id == "user_123"
    
    @pytest.mark.asyncio
    async def test_detect_intent(self):
        """Test intent detection stage."""
        engine = ReasoningEngine()
        
        from Agent_Guru.reasoning.input.normalizer import NormalizedInput
        
        normalized = NormalizedInput(
            text="set a timer for 5 minutes",
            source=InputSource.TEXT,
            user_id="user_123",
            timestamp=datetime.utcnow()
        )
        
        intent = await engine._detect_intent(normalized, None)
        
        assert isinstance(intent, Intent)
        assert intent.intent_type is not None
        assert 0.0 <= intent.confidence <= 1.0
    
    def test_is_fast_path_eligible_high_confidence(self):
        """Test fast-path eligibility with high confidence."""
        engine = ReasoningEngine()
        
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.95,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes"
        )
        
        assert engine._is_fast_path_eligible(intent) is True
    
    def test_is_fast_path_eligible_low_confidence(self):
        """Test fast-path eligibility with low confidence."""
        engine = ReasoningEngine()
        
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.7,  # Below threshold
            requires_reasoning=False,
            original_input="set a timer for 5 minutes"
        )
        
        assert engine._is_fast_path_eligible(intent) is False
    
    def test_is_fast_path_eligible_requires_reasoning(self):
        """Test fast-path eligibility when reasoning required."""
        engine = ReasoningEngine()
        
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.95,
            requires_reasoning=True,  # Requires reasoning
            original_input="set a timer for 5 minutes"
        )
        
        assert engine._is_fast_path_eligible(intent) is False
    
    def test_is_fast_path_eligible_complex_intent(self):
        """Test fast-path eligibility with complex intent."""
        engine = ReasoningEngine()
        
        intent = Intent(
            intent_type=IntentType.SEND_MESSAGE,  # Not in fast-path list
            confidence=0.95,
            requires_reasoning=False,
            original_input="send a message to John"
        )
        
        assert engine._is_fast_path_eligible(intent) is False
    
    @pytest.mark.asyncio
    async def test_process_fast_path(self):
        """Test fast-path processing."""
        from Agent_Guru.reasoning.tools.base import ToolMetadata
        from Agent_Guru.reasoning.tools.selector import ToolSelector, SelectedTool
        from Agent_Guru.reasoning.tools.registry import ToolRegistry
        from Agent_Guru.reasoning.execution.executor import ExecutionResult
        from Agent_Guru.reasoning.tools.base import ToolMetadata, ToolSensitivity
        
        # Create mock tool with proper metadata
        mock_tool = Mock()
        mock_tool.metadata = ToolMetadata(
            tool_id="timer.set",
            name="Set Timer",
            description="Set a timer",
            parameters=[],
            sensitivity=ToolSensitivity.SAFE,
            estimated_latency_ms=100
        )
        mock_tool.tool_id = "timer.set"
        mock_tool.name = "Set Timer"
        mock_tool.description = "Set a timer"
        mock_tool.category = "timer"
        mock_tool.parameters = []
        mock_tool.requires_permission = False
        mock_tool.permission_scope = None
        
        # Mock execute method to return proper ExecutionResult
        async def mock_execute(**kwargs):
            return ExecutionResult(
                success=True,
                result_data={"message": "Timer set for 5 minutes"},
                execution_time=0.1,
                action_id="test_action",
                retries=0
            )
        mock_tool.execute = mock_execute
        
        # Create mock tool selector that returns a tool
        mock_selector = Mock(spec=ToolSelector)
        mock_selector.select_tool = AsyncMock(return_value=SelectedTool(
            tool=mock_tool,
            confidence=0.95,
            parameters={"duration": "5 minutes"},
            tier=1,
            selection_time_ms=10
        ))
        
        # Create engine with mocked selector
        engine = ReasoningEngine(tool_selector=mock_selector)
        
        from Agent_Guru.reasoning.input.normalizer import NormalizedInput
        
        normalized = NormalizedInput(
            text="set a timer for 5 minutes",
            source=InputSource.TEXT,
            user_id="user_123",
            timestamp=datetime.utcnow()
        )
        
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.95,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes"
        )
        
        result = await engine._process_fast_path(normalized, intent, None)
        
        assert isinstance(result, ReasoningResult)
        assert result.response is not None
        assert result.success is True
        assert "tool_selection" in result.stage_latencies
        assert "safety_validation" in result.stage_latencies
        assert "response_generation" in result.stage_latencies
    
    @pytest.mark.asyncio
    async def test_process_full_pipeline(self, register_example_tools):
        """Test full pipeline processing."""
        engine = ReasoningEngine()
        
        from Agent_Guru.reasoning.input.normalizer import NormalizedInput
        
        normalized = NormalizedInput(
            text="send a message to John",
            source=InputSource.TEXT,
            user_id="user_123",
            timestamp=datetime.utcnow()
        )
        
        intent = Intent(
            intent_type=IntentType.SEND_MESSAGE,
            confidence=0.85,
            requires_reasoning=True,
            original_input="send a message to John"
        )
        
        result = await engine._process_full_pipeline(normalized, intent, None)
        
        assert isinstance(result, ReasoningResult)
        assert result.response is not None
        assert result.success is True
    
    def test_generate_error_response_value_error(self):
        """Test error response generation for ValueError."""
        engine = ReasoningEngine()
        
        error = ValueError("Invalid input")
        response = engine._generate_error_response(error)
        
        assert "didn't understand" in response.lower()
    
    def test_generate_error_response_timeout(self):
        """Test error response generation for TimeoutError."""
        engine = ReasoningEngine()
        
        error = TimeoutError("Request timed out")
        response = engine._generate_error_response(error)
        
        assert "taking too long" in response.lower()
    
    def test_generate_error_response_generic(self):
        """Test error response generation for generic error."""
        engine = ReasoningEngine()
        
        error = RuntimeError("Something went wrong")
        response = engine._generate_error_response(error)
        
        assert "encountered an error" in response.lower()
    
    def test_get_statistics_initial(self):
        """Test getting statistics initially."""
        engine = ReasoningEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 0
        assert stats["fast_path_requests"] == 0
        assert stats["fast_path_rate"] == 0.0
        assert stats["failed_requests"] == 0
        assert stats["error_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_get_statistics_after_requests(self):
        """Test getting statistics after processing requests."""
        engine = ReasoningEngine()
        
        # Process a few requests
        for _ in range(3):
            raw = RawInput(
                content="set a timer for 5 minutes",
                source=InputSource.TEXT,
                user_id="user_123"
            )
            await engine.process(raw)
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 3
        assert stats["fast_path_requests"] >= 0
        assert 0.0 <= stats["fast_path_rate"] <= 1.0


class TestReasoningResult:
    """Tests for ReasoningResult."""
    
    def test_reasoning_result_creation(self):
        """Test ReasoningResult creation."""
        result = ReasoningResult(
            response="Timer set for 5 minutes",
            confidence=0.95,
            success=True,
            fast_path=True,
            total_latency_ms=450.0
        )
        
        assert result.response == "Timer set for 5 minutes"
        assert result.confidence == 0.95
        assert result.success is True
        assert result.fast_path is True
        assert result.total_latency_ms == 450.0
    
    def test_reasoning_result_to_dict(self):
        """Test ReasoningResult to_dict conversion."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.95,
            requires_reasoning=False,
            original_input="set a timer"
        )
        
        result = ReasoningResult(
            response="Timer set",
            confidence=0.95,
            intent=intent,
            success=True,
            fast_path=True,
            total_latency_ms=450.0,
            trace_id="abc123"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["response"] == "Timer set"
        assert result_dict["confidence"] == 0.95
        assert result_dict["intent"] == "set_timer"
        assert result_dict["success"] is True
        assert result_dict["fast_path"] is True
        assert result_dict["total_latency_ms"] == 450.0
        assert result_dict["trace_id"] == "abc123"


class TestGlobalEngine:
    """Tests for global engine instance."""
    
    def test_get_reasoning_engine(self):
        """Test getting global engine."""
        engine1 = get_reasoning_engine()
        engine2 = get_reasoning_engine()
        
        # Should return same instance
        assert engine1 is engine2


@pytest.mark.integration
class TestReasoningEngineIntegration:
    """Integration tests for ReasoningEngine."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_fast_path(self, register_example_tools):
        """Test complete fast-path flow."""
        engine = ReasoningEngine()
        
        raw = RawInput(
            content="set a timer for 5 minutes",
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        result = await engine.process(raw)
        
        # Verify result
        assert result.success is True
        assert result.response is not None
        assert result.total_latency_ms > 0
        assert result.intent is not None
        assert result.trace_id is not None
        
        # Verify statistics updated
        stats = engine.get_statistics()
        assert stats["total_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_end_to_end_error_handling(self):
        """Test complete error handling flow."""
        engine = ReasoningEngine()
        
        raw = RawInput(
            content="",  # Invalid input
            source=InputSource.TEXT,
            user_id="user_123"
        )
        
        result = await engine.process(raw)
        
        # Verify error handling
        assert result.success is False
        assert result.error is not None
        assert result.response is not None
        
        # Verify statistics updated
        stats = engine.get_statistics()
        assert stats["total_requests"] == 1
        assert stats["failed_requests"] == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, register_example_tools):
        """Test handling concurrent requests."""
        engine = ReasoningEngine()
        
        # Create multiple requests
        requests = [
            RawInput(
                content=f"set a timer for {i} minutes",
                source=InputSource.TEXT,
                user_id=f"user_{i}"
            )
            for i in range(5)
        ]
        
        # Process concurrently
        results = await asyncio.gather(*[
            engine.process(req) for req in requests
        ])
        
        # Verify all succeeded
        assert len(results) == 5
        assert all(r.success for r in results)
        
        # Verify statistics
        stats = engine.get_statistics()
        assert stats["total_requests"] == 5
