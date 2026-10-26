"""Global test configuration and fixtures for Agent Guru reasoning tests.

This conftest.py is automatically loaded by pytest for ALL tests in this
directory and subdirectories. It provides:

1. Ollama mock - prevents any test from making real HTTP calls to Ollama.
   Set AGENT_GURU_LIVE_LLM=1 to opt-out and test with real Ollama.

2. Session-scoped intent engine - IntentDetectionEngine is expensive to
   initialize (NER/neural model loading). We initialize it once per session
   and share it across all tests via the `shared_intent_engine` fixture.

3. Fast engine factory - `make_engine` fixture creates a ReasoningEngine
   with LLM disabled and the shared intent engine injected.

4. Environment hardening - sets OLLAMA_TIMEOUT_SECONDS=2 so any test that
   accidentally bypasses the mock fails fast instead of hanging.

5. Tool registry isolation - each test function gets a clean tool registry
   snapshot to prevent cross-test pollution from double-registration.

Performance contract:
    - No test should take >30s (enforced by pytest-timeout in pytest.ini)
    - No test should make real network calls (enforced by this conftest)
    - Engine construction: <100ms (intent engine shared, not re-initialized)
    - First test in session: ~5s (one-time intent engine init)
"""

import asyncio
import logging
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding model warm-up
# ---------------------------------------------------------------------------


_EMBEDDING_MODEL_WARMED = False


def _warm_embedding_model_once() -> None:
    """Load the sentence-transformer embedding model, at most once."""
    global _EMBEDDING_MODEL_WARMED
    if _EMBEDDING_MODEL_WARMED:
        return
    from Agent_Guru.reasoning.memory.embedding import EmbeddingGenerator

    EmbeddingGenerator()
    _EMBEDDING_MODEL_WARMED = True


def pytest_collection_finish(session: pytest.Session) -> None:
    """Warm the embedding model after collection, before any test starts.

    TIMEOUT FIX: the warm-up used to live entirely in the session fixture
    below. pytest-timeout's budget covers the whole runtest protocol - setup
    included - so the fixture's 420 MB model load was still charged against
    the FIRST dependent test's 30 s allowance. It had merely moved the cost
    from "whichever test constructed a retriever first" to "whichever test
    runs first", which is the same failure with a more predictable victim: on
    a cold Hugging Face cache or a machine already busy running another suite,
    the load overran 30 s, the session fixture raised, and pytest replayed
    that cached exception as "ERROR at setup" for every single test in every
    opted-in module - 68 of them in one observed run.

    Collection hooks run outside any test's timeout window, so doing the load
    here removes it from the budget entirely. It stays opt-in: the model is
    only loaded when some collected test actually asked for the fixture, so
    suites that never touch memory pay nothing.

    A warm-up failure must degrade, never abort. An exception raised from a
    collection hook becomes an INTERNALERROR: pytest stops the whole session
    and never prints the collection-error summary, so one broken dependency
    hides every other problem in the run. The failure is logged and
    collection continues. The warm_embedding_model fixture below retries the
    load, so tests that genuinely need the model still fail on their own
    with the real exception, while everything else runs and reports.
    """
    if not any("warm_embedding_model" in item.fixturenames for item in session.items):
        return
    try:
        _warm_embedding_model_once()
    except Exception as exc:
        root = exc
        while root.__cause__ is not None:
            root = root.__cause__
        detail = f"{type(exc).__name__}: {exc}"
        if root is not exc:
            detail += f" (caused by {type(root).__name__}: {root})"
        message = (
            f"Embedding model warm-up failed during collection - {detail}. "
            "Tests using warm_embedding_model will retry the load and report "
            "the failure themselves; all other tests run normally."
        )
        logger.warning(message)
        # Captured log records are not shown for a collection hook, so also
        # write the warning to the terminal where it is visible in CI logs.
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(f"WARNING: {message}", yellow=True)


@pytest.fixture(scope="session")
def warm_embedding_model():
    """Ensure the sentence-transformer embedding model is loaded.

    The FIRST MemoryRetriever()/EmbeddingGenerator() in a process loads a
    420 MB sentence-transformer (~11 s warm, longer on a cold Hugging Face
    cache). Whichever test happened to construct one first was charged that
    cost inside its own 30 s budget and failed with
    "Timeout (>30.0s) from pytest-timeout" - a failure that had nothing to do
    with the code under test and that moved around as tests were reordered.

    Modules that build memory components opt in with

        pytestmark = pytest.mark.usefixtures("warm_embedding_model")

    pytest_collection_finish above normally does the load before any test
    starts. This fixture is the backstop for the cases that hook cannot cover
    - a test that requests the fixture dynamically, or a run where the hook
    did not fire - and is a no-op once the model is loaded.
    """
    _warm_embedding_model_once()


# ---------------------------------------------------------------------------
# Environment hardening - applied before any test module is imported
# ---------------------------------------------------------------------------

# Short Ollama timeout so any accidental real call fails in 2s, not 300s.
os.environ.setdefault("OLLAMA_TIMEOUT_SECONDS", "2")

# Signal to engine._initialize_llm_provider that we are in test mode.
# pytest also sets PYTEST_CURRENT_TEST automatically, but we set our own
# flag so the engine code can check it without importing pytest.
os.environ.setdefault("AGENT_GURU_TEST_MODE", "1")


# ---------------------------------------------------------------------------
# Ollama mock - applied globally via autouse session fixture
# ---------------------------------------------------------------------------


class _MockOllamaProvider:
    """Drop-in mock for OllamaProvider.

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
    """Session-scoped autouse fixture that replaces OllamaProvider with a mock
    for the entire test session.

    Set AGENT_GURU_LIVE_LLM=1 to opt-out (e.g. manual integration testing), the
    same switch the root conftest reads for every client.
    """
    if os.environ.get("AGENT_GURU_LIVE_LLM", "").strip().lower() in {"1", "true", "yes", "on"}:
        yield
        return

    from unittest.mock import patch

    with patch(
        "Agent_Guru.reasoning.llm.providers.ollama_provider.OllamaProvider",
        new=_MockOllamaProvider,
    ):
        yield


# ---------------------------------------------------------------------------
# Session-scoped intent engine - initialized ONCE per test session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def shared_intent_engine():
    """Session-scoped IntentDetectionEngine.

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
# Session-scoped tool pre-loader - loads all tools ONCE per session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _preload_tools():
    """Session-scoped autouse fixture that pre-loads all tools into the registry
    once per test session.

    Without this, ReasoningEngine.__init__ calls load_all_tools_sync() on
    every engine construction, which spawns a thread pool and re-instantiates
    all 35 tool classes (~1.5s overhead per test).

    By pre-loading here, subsequent load_all_tools_sync() calls are no-ops
    (all tools already registered → get_tool() check skips them).
    """
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
    """Factory fixture that creates a ReasoningEngine with:
    - LLM disabled by default (llm_reasoning=None)
    - Shared intent engine injected (no re-initialization cost).

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
# Mock intent engine fixture - for tests that don't need real NLP inference
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_intent_engine():
    """Mock IntentDetectionEngine that returns a pre-configured intent instantly.

    Use this in tests that exercise engine plumbing but don't need real
    NLP inference - saves ~0.5-1.5s per test call to detect_intent_async.

    The mock returns SET_TIMER with confidence=0.95 by default.
    Override mock_intent_engine.detect_intent_async.return_value to change.
    """
    from unittest.mock import AsyncMock, MagicMock

    from Agent_Guru.reasoning.models.intent import Entity, Intent, IntentType

    mock = MagicMock()
    mock._initialized = True

    # Default: high-confidence timer intent (fast-path eligible), with the
    # duration entity the real IntentDetectionEngine extracts from this
    # sentence. It had no entities, a detection that cannot happen, and the
    # tests using it passed only because the tool selector then picked
    # messaging.send_slack with no arguments and the engine called that a
    # success.
    _default_intent = Intent(
        intent_type=IntentType.SET_TIMER,
        confidence=0.95,
        requires_reasoning=False,
        original_input="set a timer for 5 minutes",
        entities={"duration": Entity(entity_type="duration", value=300, raw_text="5 minutes")},
    )

    class _DetectionResult:
        intent = _default_intent

    mock.detect_intent_async = AsyncMock(return_value=_DetectionResult())
    mock.initialize = MagicMock()
    return mock


@pytest.fixture
def make_engine_fast(mock_intent_engine):
    """Factory fixture like make_engine but uses a mock intent engine.

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
    """ReasoningPlanGenerator backed by a mock LLM provider.

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
# Tool registry isolation - prevents cross-test pollution
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_tool_registry(_preload_tools):
    """Function-scoped autouse fixture that snapshots the tool registry before
    each test and restores it after, preventing cross-test pollution from
    double-registration errors.

    Depends on _preload_tools so the snapshot always includes the full
    pre-loaded tool set - restoring to this baseline means subsequent
    load_all_tools_sync() calls in ReasoningEngine.__init__ are no-ops.
    """
    from Agent_Guru.reasoning.tools.registry import get_registry

    registry = get_registry()

    # Snapshot current state (shallow copy is sufficient - dicts of immutables)
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
    """Register example tools for tests that need them.

    Yields the registry. Tools are cleaned up automatically by
    _isolate_tool_registry after the test.
    """
    from Agent_Guru.reasoning.tools.examples import (
        CalendarTool,
        CancelTimerTool,
        MessagingTool,
        MusicTool,
        SetTimerTool,
        WeatherTool,
    )
    from Agent_Guru.reasoning.tools.registry import get_registry

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

    return registry
