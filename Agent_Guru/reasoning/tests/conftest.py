"""
Global test configuration and fixtures for Agent Guru reasoning tests.

This conftest.py is automatically loaded by pytest for ALL tests in this
directory and subdirectories. It provides:

1. Ollama mock — prevents any test from making real HTTP calls to Ollama.
   Set AGENT_GURU_REAL_OLLAMA=1 to opt-out and test with real Ollama.

2. Session-scoped intent engine — IntentDetectionEngine is expensive to
   initialize (NER/neural model loading). We initialize it once per session
   and share it across all tests via the `shared_intent_engine` fixture.

3. Fast engine factory — `make_engine` fixture creates a ReasoningEngine
   with LLM disabled and the shared intent engine injected.

4. Environment hardening — sets OLLAMA_TIMEOUT_SECONDS=2 so any test that
   accidentally bypasses the mock fails fast instead of hanging.

5. Tool registry isolation — each test function gets a clean tool registry
   snapshot to prevent cross-test pollution from double-registration.

Performance contract:
    - No test should take >30s (enforced by pytest-timeout in pytest.ini)
    - No test should make real network calls (enforced by this conftest)
    - Engine construction: <100ms (intent engine shared, not re-initialized)
    - First test in session: ~5s (one-time intent engine init)
"""

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Environment hardening — applied before any test module is imported
# ---------------------------------------------------------------------------

# Short Ollama timeout so any accidental real call fails in 2s, not 300s.
os.environ.setdefault("OLLAMA_TIMEOUT_SECONDS", "2")

# Signal to engine._initialize_llm_provider that we are in test mode.
# pytest also sets PYTEST_CURRENT_TEST automatically, but we set our own
# flag so the engine code can check it without importing pytest.
os.environ.setdefault("AGENT_GURU_TEST_MODE", "1")


# ---------------------------------------------------------------------------
# Ollama mock — applied globally via autouse session fixture
# ---------------------------------------------------------------------------

class _MockOllamaProvider:
    """
    Drop-in mock for OllamaProvider.

    Returns a valid LLMResponse instantly without any network call.
    Used by the global autouse fixture to patch all Ollama usage.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def generate(self, request: Any) -> Any:
        from Agent_Guru.reasoning.llm.models import LLMProvider, LLMResponse

        return LLMResponse(
            text=(
                '{"goal":"mock goal",'
                '"steps":[{"step_id":1,"description":"mock step",'
                '"tool_id":"timer.set","parameters":{},'
                '"estimated_duration_seconds":1.0,'
                '"requires_confirmation":false,"depends_on":[]}],'
                '"reasoning":"mock reasoning","confidence":0.9}'
            ),
            provider=LLMProvider.LOCAL,
            tokens_generated=20,
            latency_ms=1.0,
            finish_reason="stop",
        )

    async def health_check(self) -> bool:
        return False

    def get_provider_type(self) -> Any:
        from Agent_Guru.reasoning.llm.models import LLMProvider
        return LLMProvider.LOCAL

    def get_health(self) -> dict:
        return {
            "provider": "local",
            "circuit_state": "closed",
            "failure_count": 0,
            "last_failure": None,
            "last_success": None,
            "requests_this_minute": 0,
            "tokens_this_minute": 0,
        }


@pytest.fixture(autouse=True, scope="session")
def _patch_ollama_globally() -> Any:
    """
    Session-scoped autouse fixture that replaces OllamaProvider with a mock
    for the entire test session.

    Set AGENT_GURU_REAL_OLLAMA=1 to opt-out (e.g. manual integration testing).
    """
    if os.environ.get("AGENT_GURU_REAL_OLLAMA") == "1":
        yield
        return

    from unittest.mock import patch
    with patch(
        "Agent_Guru.reasoning.llm.providers.ollama_provider.OllamaProvider",
        new=_MockOllamaProvider,
    ):
        yield


# ---------------------------------------------------------------------------
# Session-scoped intent engine — initialized ONCE per test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def shared_intent_engine():
    """
    Session-scoped IntentDetectionEngine.

    Initializing the intent engine is expensive (~3-5s) because it loads
    NER and neural classifier models. By sharing one instance across all
    tests we pay that cost only once per pytest session.

    All tests that create a ReasoningEngine should inject this fixture
    via make_engine() to avoid re-initialization overhead.
    """
    from Agent_Guru.reasoning.intent.engine import IntentDetectionEngine
    engine = IntentDetectionEngine()
    engine.initialize()
    return engine


# ---------------------------------------------------------------------------
# Session-scoped tool pre-loader — loads all tools ONCE per session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _preload_tools():
    """
    Session-scoped autouse fixture that pre-loads all tools into the registry
    once per test session.

    Without this, ReasoningEngine.__init__ calls load_all_tools_sync() on
    every engine construction, which spawns a thread pool and re-instantiates
    all 35 tool classes (~1.5s overhead per test).

    By pre-loading here, subsequent load_all_tools_sync() calls are no-ops
    (all tools already registered → get_tool() check skips them).
    """
    import asyncio
    from Agent_Guru.reasoning.tools.loader import load_all_tools
    from Agent_Guru.reasoning.tools.registry import get_registry

    registry = get_registry()
    asyncio.run(load_all_tools(registry))
    return registry


# ---------------------------------------------------------------------------
# Engine factory fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def make_engine(shared_intent_engine):
    """
    Factory fixture that creates a ReasoningEngine with:
    - LLM disabled by default (llm_reasoning=None)
    - Shared intent engine injected (no re-initialization cost)

    Usage:
        def test_something(make_engine):
            engine = make_engine()              # default: no LLM
            engine2 = make_engine(llm=mock_llm) # with custom mock LLM

    Accepts optional keyword args forwarded to ReasoningEngine.__init__.
    """
    def _factory(llm_reasoning=None, **kwargs):
        from Agent_Guru.reasoning.engine import ReasoningEngine
        return ReasoningEngine(
            llm_reasoning=llm_reasoning,
            intent_engine=shared_intent_engine,
            **kwargs,
        )

    return _factory


# ---------------------------------------------------------------------------
# Mock intent engine fixture — for tests that don't need real NLP inference
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_intent_engine():
    """
    Mock IntentDetectionEngine that returns a pre-configured intent instantly.

    Use this in tests that exercise engine plumbing but don't need real
    NLP inference — saves ~0.5-1.5s per test call to detect_intent_async.

    The mock returns SET_TIMER with confidence=0.95 by default.
    Override mock_intent_engine.detect_intent_async.return_value to change.
    """
    from unittest.mock import AsyncMock, MagicMock
    from Agent_Guru.reasoning.models.intent import Intent, IntentType

    mock = MagicMock()
    mock._initialized = True

    # Default: high-confidence timer intent (fast-path eligible)
    _default_intent = Intent(
        intent_type=IntentType.SET_TIMER,
        confidence=0.95,
        requires_reasoning=False,
        original_input="set a timer for 5 minutes",
    )

    class _DetectionResult:
        intent = _default_intent

    mock.detect_intent_async = AsyncMock(return_value=_DetectionResult())
    mock.initialize = MagicMock()
    return mock


@pytest.fixture
def make_engine_fast(mock_intent_engine):
    """
    Factory fixture like make_engine but uses a mock intent engine.

    Use for tests that need fast execution and don't care about real
    NLP inference (e.g. testing pipeline plumbing, error handling, stats).
    """
    def _factory(llm_reasoning=None, **kwargs):
        from Agent_Guru.reasoning.engine import ReasoningEngine
        return ReasoningEngine(
            llm_reasoning=llm_reasoning,
            intent_engine=mock_intent_engine,
            **kwargs,
        )

    return _factory


# ---------------------------------------------------------------------------
# Mock LLM reasoning fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_reasoning():
    """
    ReasoningPlanGenerator backed by a mock LLM provider.

    Returns a valid single-step reasoning plan JSON instantly.
    Use when a test needs to exercise the LLM reasoning path without
    a real Ollama server.

    Usage:
        async def test_full_pipeline(mock_llm_reasoning):
            engine = ReasoningEngine(llm_reasoning=mock_llm_reasoning)
            ...
    """
    from Agent_Guru.reasoning.llm.models import LLMProvider, LLMResponse
    from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanGenerator

    mock_response = LLMResponse(
        text=(
            '{"goal":"execute request",'
            '"steps":[{"step_id":1,"description":"Execute the request",'
            '"tool_id":"messaging.send","parameters":{"recipient":"John","message":"Hello"},'
            '"estimated_duration_seconds":1.0,'
            '"requires_confirmation":false,"depends_on":[]}],'
            '"reasoning":"User wants to perform an action","confidence":0.9}'
        ),
        provider=LLMProvider.LOCAL,
        tokens_generated=50,
        latency_ms=1.0,
        finish_reason="stop",
    )

    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(return_value=mock_response)

    return ReasoningPlanGenerator(llm_provider=mock_provider)


# ---------------------------------------------------------------------------
# Tool registry isolation — prevents cross-test pollution
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_tool_registry(_preload_tools):
    """
    Function-scoped autouse fixture that snapshots the tool registry before
    each test and restores it after, preventing cross-test pollution from
    double-registration errors.

    Depends on _preload_tools so the snapshot always includes the full
    pre-loaded tool set — restoring to this baseline means subsequent
    load_all_tools_sync() calls in ReasoningEngine.__init__ are no-ops.
    """
    from Agent_Guru.reasoning.tools.registry import get_registry

    registry = get_registry()

    # Snapshot current state (shallow copy is sufficient — dicts of immutables)
    snapshot_tools = dict(registry._tools)
    snapshot_metadata = dict(registry._metadata)
    snapshot_capabilities = {k: set(v) for k, v in registry._capability_index.items()}

    yield

    # Restore state after test
    registry._tools = snapshot_tools
    registry._metadata = snapshot_metadata
    registry._capability_index = snapshot_capabilities


# ---------------------------------------------------------------------------
# Example tools fixture (shared across test files)
# ---------------------------------------------------------------------------

@pytest.fixture
async def register_example_tools(shared_intent_engine):
    """
    Register example tools for tests that need them.

    Yields the registry. Tools are cleaned up automatically by
    _isolate_tool_registry after the test.
    """
    from Agent_Guru.reasoning.tools.registry import get_registry
    from Agent_Guru.reasoning.tools.examples import (
        CalendarTool,
        CancelTimerTool,
        MessagingTool,
        MusicTool,
        SetTimerTool,
        WeatherTool,
    )

    registry = get_registry()

    tools = [
        SetTimerTool(),
        CancelTimerTool(),
        WeatherTool(),
        MessagingTool(),
        MusicTool(),
        CalendarTool(),
    ]

    for tool in tools:
        if registry.get_tool(tool.metadata.tool_id) is None:
            await registry.register(tool, tool.metadata)

    yield registry
