"""
Tests for Reasoning Engine.

Coverage Target: >80% (enforced by CI/CD)

All tests use llm_reasoning=None (or a mock) — no real Ollama calls.
The global conftest.py also patches OllamaProvider for the entire session.

Performance contract:
    - First test in session: ~5s (one-time intent engine init via shared_intent_engine)
    - Subsequent tests: <200ms each (shared intent engine, no re-init)
    - Total suite: <15s
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from Agent_Guru.reasoning.engine import (
    ReasoningResult,
    get_reasoning_engine,
)
from Agent_Guru.reasoning.input.normalizer import InputSource, RawInput
from Agent_Guru.reasoning.models.intent import Intent, IntentType


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestReasoningEngine:
    """Unit tests for ReasoningEngine."""

    def test_initialization(self, make_engine_fast):
        """Test engine initializes all required components."""
        engine = make_engine_fast()

        assert engine.input_normalizer is not None
        assert engine.intent_engine is not None
        assert engine.tool_selector is not None
        assert engine.safety_gate is not None
        assert engine.response_generator is not None
        assert engine.latency_controller is not None
        assert engine.enable_fast_path is True
        assert engine.enable_tracing is True

    def test_initialization_with_custom_components(self, make_engine_fast):
        """Test engine accepts custom component injection."""
        from Agent_Guru.reasoning.input.normalizer import InputNormalizer
        from Agent_Guru.reasoning.latency.controller import LatencyController

        normalizer = InputNormalizer()
        controller = LatencyController()

        engine = make_engine_fast(
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
    async def test_process_basic(self, make_engine_fast, register_example_tools):
        """Fast-path timer command succeeds without LLM."""
        engine = make_engine_fast()

        raw = RawInput(
            content="set a timer for 5 minutes",
            source=InputSource.TEXT,
            user_id="user_123",
        )
        result = await engine.process(raw)

        assert isinstance(result, ReasoningResult)
        assert result.response is not None
        assert result.success is True
        assert result.total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_process_with_invalid_input(self, make_engine_fast):
        """Empty input returns a graceful error result."""
        engine = make_engine_fast()

        raw = RawInput(content="", source=InputSource.TEXT, user_id="user_123")
        result = await engine.process(raw)

        assert result.success is False
        assert result.error is not None
        assert "didn't understand" in result.response.lower()

    @pytest.mark.asyncio
    async def test_normalize_input(self, make_engine_fast):
        """Input normalizer strips whitespace."""
        engine = make_engine_fast()

        raw = RawInput(
            content="  hello world  ",
            source=InputSource.TEXT,
            user_id="user_123",
        )
        normalized = await engine._normalize_input(raw, None)

        assert normalized.text == "hello world"
        assert normalized.source == InputSource.TEXT
        assert normalized.user_id == "user_123"

    @pytest.mark.asyncio
    async def test_detect_intent(self, make_engine):
        """Intent detection returns a valid Intent object (uses real NLP engine)."""
        from Agent_Guru.reasoning.input.normalizer import NormalizedInput

        engine = make_engine()
        normalized = NormalizedInput(
            text="set a timer for 5 minutes",
            source=InputSource.TEXT,
            user_id="user_123",
            timestamp=datetime.now(tz=timezone.utc),
        )
        intent = await engine._detect_intent(normalized, None)

        assert isinstance(intent, Intent)
        assert intent.intent_type is not None
        assert 0.0 <= intent.confidence <= 1.0

    def test_is_fast_path_eligible_high_confidence(self, make_engine_fast):
        """High-confidence timer intent is fast-path eligible."""
        engine = make_engine_fast()
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.95,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes",
        )
        assert engine._is_fast_path_eligible(intent) is True

    def test_is_fast_path_eligible_low_confidence(self, make_engine_fast):
        """Low-confidence intent is NOT fast-path eligible."""
        engine = make_engine_fast()
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.7,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes",
        )
        assert engine._is_fast_path_eligible(intent) is False

    def test_is_fast_path_eligible_requires_reasoning(self, make_engine_fast):
        """Intent that requires reasoning is NOT fast-path eligible."""
        engine = make_engine_fast()
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.95,
            requires_reasoning=True,
            original_input="set a timer for 5 minutes",
        )
        assert engine._is_fast_path_eligible(intent) is False

    def test_is_fast_path_eligible_complex_intent(self, make_engine_fast):
        """SEND_MESSAGE is not in the fast-path set."""
        engine = make_engine_fast()
        intent = Intent(
            intent_type=IntentType.SEND_MESSAGE,
            confidence=0.95,
            requires_reasoning=False,
            original_input="send a message to John",
        )
        assert engine._is_fast_path_eligible(intent) is False

    @pytest.mark.asyncio
    async def test_process_fast_path(self, make_engine_fast):
        """Fast-path returns success with all expected stage latencies."""
        from Agent_Guru.reasoning.execution.executor import ExecutionResult
        from Agent_Guru.reasoning.input.normalizer import NormalizedInput
        from Agent_Guru.reasoning.tools.base import ToolMetadata, ToolSensitivity
        from Agent_Guru.reasoning.tools.selector import SelectedTool, ToolSelector

        mock_tool = Mock()
        mock_tool.metadata = ToolMetadata(
            tool_id="timer.set",
            name="Set Timer",
            description="Set a timer",
            parameters=[],
            sensitivity=ToolSensitivity.SAFE,
            estimated_latency_ms=100,
        )
        mock_tool.tool_id = "timer.set"
        mock_tool.name = "Set Timer"
        mock_tool.description = "Set a timer"
        mock_tool.category = "timer"
        mock_tool.parameters = []
        mock_tool.requires_permission = False
        mock_tool.permission_scope = None

        async def mock_execute(**kwargs):
            return ExecutionResult(
                success=True,
                result_data={"message": "Timer set for 5 minutes"},
                execution_time=0.1,
                action_id="test_action",
                retries=0,
            )

        mock_tool.execute = mock_execute

        mock_selector = Mock(spec=ToolSelector)
        mock_selector.select_tool = AsyncMock(
            return_value=SelectedTool(
                tool=mock_tool,
                confidence=0.95,
                parameters={"duration": "5 minutes"},
                tier=1,
                selection_time_ms=10,
            )
        )

        engine = make_engine_fast(tool_selector=mock_selector)
        # Clear the singleton response cache to avoid cross-test pollution
        engine._response_cache.clear()
        normalized = NormalizedInput(
            text="set a timer for 5 minutes",
            source=InputSource.TEXT,
            user_id="user_123",
            timestamp=datetime.now(tz=timezone.utc),
        )
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.95,
            requires_reasoning=False,
            original_input="set a timer for 5 minutes",
        )

        result = await engine._process_fast_path(normalized, intent, None)

        assert isinstance(result, ReasoningResult)
        assert result.response is not None
        assert result.success is True
        assert "tool_selection" in result.stage_latencies
        assert "safety_validation" in result.stage_latencies
        assert "response_generation" in result.stage_latencies

    @pytest.mark.asyncio
    async def test_process_full_pipeline(self, make_engine_fast, register_example_tools, mock_llm_reasoning):
        """Full pipeline with mocked LLM returns a valid result."""
        from Agent_Guru.reasoning.input.normalizer import NormalizedInput

        engine = make_engine_fast(llm_reasoning=mock_llm_reasoning)
        normalized = NormalizedInput(
            text="send a message to John",
            source=InputSource.TEXT,
            user_id="user_123",
            timestamp=datetime.now(tz=timezone.utc),
        )
        intent = Intent(
            intent_type=IntentType.SEND_MESSAGE,
            confidence=0.85,
            requires_reasoning=True,
            original_input="send a message to John",
        )

        result = await engine._process_full_pipeline(normalized, intent, None)

        assert isinstance(result, ReasoningResult)
        assert result.response is not None
        assert result.success is True

    def test_generate_error_response_value_error(self, make_engine_fast):
        """ValueError maps to 'didn't understand' message."""
        engine = make_engine_fast()
        assert "didn't understand" in engine._generate_error_response(ValueError("x")).lower()

    def test_generate_error_response_timeout(self, make_engine_fast):
        """TimeoutError maps to 'taking too long' message."""
        engine = make_engine_fast()
        assert "taking too long" in engine._generate_error_response(TimeoutError("x")).lower()

    def test_generate_error_response_generic(self, make_engine_fast):
        """Generic exception maps to 'encountered an error' message."""
        engine = make_engine_fast()
        assert "encountered an error" in engine._generate_error_response(RuntimeError("x")).lower()

    def test_get_statistics_initial(self, make_engine_fast):
        """Fresh engine has zero statistics."""
        engine = make_engine_fast()
        stats = engine.get_statistics()

        assert stats["total_requests"] == 0
        assert stats["fast_path_requests"] == 0
        assert stats["fast_path_rate"] == 0.0
        assert stats["failed_requests"] == 0
        assert stats["error_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_statistics_after_requests(self, make_engine_fast):
        """Statistics are updated after processing requests."""
        engine = make_engine_fast()

        for _ in range(3):
            await engine.process(
                RawInput(
                    content="set a timer for 5 minutes",
                    source=InputSource.TEXT,
                    user_id="user_123",
                )
            )

        stats = engine.get_statistics()
        assert stats["total_requests"] == 3
        assert stats["fast_path_requests"] >= 0
        assert 0.0 <= stats["fast_path_rate"] <= 1.0


# ---------------------------------------------------------------------------
# ReasoningResult tests
# ---------------------------------------------------------------------------

class TestReasoningResult:
    """Tests for ReasoningResult dataclass."""

    def test_reasoning_result_creation(self):
        """ReasoningResult stores all fields correctly."""
        result = ReasoningResult(
            response="Timer set for 5 minutes",
            confidence=0.95,
            success=True,
            fast_path=True,
            total_latency_ms=450.0,
        )
        assert result.response == "Timer set for 5 minutes"
        assert result.confidence == 0.95
        assert result.success is True
        assert result.fast_path is True
        assert result.total_latency_ms == 450.0

    def test_reasoning_result_to_dict(self):
        """to_dict() serialises all fields correctly."""
        intent = Intent(
            intent_type=IntentType.SET_TIMER,
            confidence=0.95,
            requires_reasoning=False,
            original_input="set a timer",
        )
        result = ReasoningResult(
            response="Timer set",
            confidence=0.95,
            intent=intent,
            success=True,
            fast_path=True,
            total_latency_ms=450.0,
            trace_id="abc123",
        )
        d = result.to_dict()

        assert d["response"] == "Timer set"
        assert d["confidence"] == 0.95
        assert d["intent"] == "set_timer"
        assert d["success"] is True
        assert d["fast_path"] is True
        assert d["total_latency_ms"] == 450.0
        assert d["trace_id"] == "abc123"


# ---------------------------------------------------------------------------
# Global engine singleton
# ---------------------------------------------------------------------------

class TestGlobalEngine:
    """Tests for the global engine singleton."""

    def test_get_reasoning_engine_returns_same_instance(self):
        """get_reasoning_engine() is a singleton."""
        assert get_reasoning_engine() is get_reasoning_engine()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestReasoningEngineIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_end_to_end_fast_path(self, make_engine_fast, register_example_tools):
        """Complete fast-path flow succeeds and updates statistics."""
        engine = make_engine_fast()

        result = await engine.process(
            RawInput(
                content="set a timer for 5 minutes",
                source=InputSource.TEXT,
                user_id="user_123",
            )
        )

        assert result.success is True
        assert result.response is not None
        assert result.total_latency_ms > 0
        assert result.intent is not None
        assert result.trace_id is not None
        assert engine.get_statistics()["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_end_to_end_error_handling(self, make_engine_fast):
        """Empty input produces a graceful error and increments failed_requests."""
        engine = make_engine_fast()

        result = await engine.process(
            RawInput(content="", source=InputSource.TEXT, user_id="user_123")
        )

        assert result.success is False
        assert result.error is not None
        assert result.response is not None
        stats = engine.get_statistics()
        assert stats["total_requests"] == 1
        assert stats["failed_requests"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, make_engine_fast, register_example_tools):
        """Five concurrent timer requests all succeed."""
        engine = make_engine_fast()

        results = await asyncio.gather(
            *[
                engine.process(
                    RawInput(
                        content=f"set a timer for {i} minutes",
                        source=InputSource.TEXT,
                        user_id=f"user_{i}",
                    )
                )
                for i in range(1, 6)
            ]
        )

        assert len(results) == 5
        assert all(r.success for r in results)
        assert engine.get_statistics()["total_requests"] == 5
