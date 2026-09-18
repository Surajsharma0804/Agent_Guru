"""
Tests for Hybrid LLM Router.

Tests routing logic, complexity scoring, fallback behavior, and metrics tracking.

Coverage Target: 80%+
"""

from unittest.mock import AsyncMock, Mock

import pytest

from Agent_Guru.reasoning.llm.models import LLMProvider, LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig
from Agent_Guru.reasoning.llm.router import (
    ComplexityScore,
    HybridLLMRouter,
    RoutingDecision,
    RoutingMetrics,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_local_provider():
    """Create mock local provider."""
    provider = Mock(spec=BaseLLMProvider)
    provider.config = ProviderConfig(api_key="test-local")
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            text="Local response",
            provider=LLMProvider.LOCAL,
            latency_ms=100.0,
            tokens_generated=10,
            finish_reason="stop",
        )
    )
    provider.get_provider_type = Mock(return_value=LLMProvider.LOCAL)
    return provider


@pytest.fixture
def mock_cloud_provider():
    """Create mock cloud provider."""
    provider = Mock(spec=BaseLLMProvider)
    provider.config = ProviderConfig(api_key="test-cloud")
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            text="Cloud response",
            provider=LLMProvider.OPENAI,
            latency_ms=200.0,
            tokens_generated=20,
            finish_reason="stop",
        )
    )
    provider.get_provider_type = Mock(return_value=LLMProvider.OPENAI)
    return provider


@pytest.fixture
def router(mock_local_provider, mock_cloud_provider):
    """Create router with both providers."""
    return HybridLLMRouter(
        local_provider=mock_local_provider,
        cloud_provider=mock_cloud_provider,
        complexity_threshold=0.5,
        enable_fallback=True,
    )


# ============================================================================
# Initialization Tests
# ============================================================================


class TestInitialization:
    """Tests for router initialization."""

    def test_init_with_both_providers(self, mock_local_provider, mock_cloud_provider):
        """Test initialization with both providers."""
        router = HybridLLMRouter(
            local_provider=mock_local_provider,
            cloud_provider=mock_cloud_provider,
        )

        assert router.local_provider == mock_local_provider  # nosec B101
        assert router.cloud_provider == mock_cloud_provider  # nosec B101
        assert router.complexity_threshold == 0.5  # nosec B101
        assert router.enable_fallback is True  # nosec B101

    def test_init_with_local_only(self, mock_local_provider):
        """Test initialization with local provider only."""
        router = HybridLLMRouter(local_provider=mock_local_provider)

        assert router.local_provider == mock_local_provider  # nosec B101
        assert router.cloud_provider is None  # nosec B101

    def test_init_with_cloud_only(self, mock_cloud_provider):
        """Test initialization with cloud provider only."""
        router = HybridLLMRouter(cloud_provider=mock_cloud_provider)

        assert router.local_provider is None  # nosec B101
        assert router.cloud_provider == mock_cloud_provider  # nosec B101

    def test_init_with_no_providers(self):
        """Test initialization with no providers fails."""
        with pytest.raises(ValueError, match="At least one provider"):
            HybridLLMRouter()

    def test_init_with_custom_threshold(self, mock_local_provider):
        """Test initialization with custom complexity threshold."""
        router = HybridLLMRouter(
            local_provider=mock_local_provider,
            complexity_threshold=0.7,
        )

        assert router.complexity_threshold == 0.7  # nosec B101


# ============================================================================
# Complexity Scoring Tests
# ============================================================================


class TestComplexityScoring:
    """Tests for complexity scoring."""

    def test_simple_task_low_complexity(self, router):
        """Test simple task has low complexity score."""
        request = LLMRequest(prompt="Hello")
        complexity = router.calculate_complexity(request)

        assert 0.0 <= complexity.score < 0.3  # nosec B101
        assert "prompt_length" in complexity.factors  # nosec B101
        assert "entity_count" in complexity.factors  # nosec B101
        assert "step_count" in complexity.factors  # nosec B101

    def test_complex_task_high_complexity(self, router):
        """Test complex task has high complexity score."""
        request = LLMRequest(prompt="A" * 300)  # Long prompt
        complexity = router.calculate_complexity(
            request,
            intent_type="multi_step_task",
            entity_count=5,
            step_count=4,
        )

        assert complexity.score >= 0.5  # nosec B101
        assert complexity.factors["prompt_length"] > 0  # nosec B101
        assert complexity.factors["entity_count"] > 0  # nosec B101
        assert complexity.factors["step_count"] > 0  # nosec B101
        assert complexity.factors["intent_type"] > 0  # nosec B101

    def test_medium_prompt_length(self, router):
        """Test medium prompt length scoring."""
        request = LLMRequest(prompt="A" * 100)
        complexity = router.calculate_complexity(request)

        assert 0.1 <= complexity.factors["prompt_length"] <= 0.2  # nosec B101

    def test_entity_count_scoring(self, router):
        """Test entity count affects complexity."""
        request = LLMRequest(prompt="Test")

        # No entities
        complexity_0 = router.calculate_complexity(request, entity_count=0)
        assert complexity_0.factors["entity_count"] == 0.0  # nosec B101

        # Few entities
        complexity_2 = router.calculate_complexity(request, entity_count=2)
        assert complexity_2.factors["entity_count"] == 0.1  # nosec B101

        # Many entities
        complexity_5 = router.calculate_complexity(request, entity_count=5)
        assert complexity_5.factors["entity_count"] == 0.2  # nosec B101

    def test_step_count_scoring(self, router):
        """Test step count affects complexity."""
        request = LLMRequest(prompt="Test")

        # Single step
        complexity_1 = router.calculate_complexity(request, step_count=1)
        assert complexity_1.factors["step_count"] == 0.0  # nosec B101

        # Few steps
        complexity_3 = router.calculate_complexity(request, step_count=3)
        assert complexity_3.factors["step_count"] == 0.15  # nosec B101

        # Many steps
        complexity_5 = router.calculate_complexity(request, step_count=5)
        assert complexity_5.factors["step_count"] == 0.3  # nosec B101

    def test_complex_intent_scoring(self, router):
        """Test complex intent types increase score."""
        request = LLMRequest(prompt="Test")

        # Simple intent
        complexity_simple = router.calculate_complexity(request, intent_type="simple_query")
        assert complexity_simple.factors["intent_type"] == 0.0  # nosec B101

        # Complex intent
        complexity_complex = router.calculate_complexity(request, intent_type="multi_step_task")
        assert complexity_complex.factors["intent_type"] == 0.2  # nosec B101


# ============================================================================
# Routing Decision Tests
# ============================================================================


class TestRoutingDecision:
    """Tests for routing decision logic."""

    def test_simple_task_routes_to_local(self, router):
        """Test simple task routes to local provider."""
        complexity = ComplexityScore(score=0.3, factors={}, reasoning="Simple")
        decision = router.make_routing_decision(complexity)

        assert decision == RoutingDecision.LOCAL  # nosec B101

    def test_complex_task_routes_to_cloud(self, router):
        """Test complex task routes to cloud provider."""
        complexity = ComplexityScore(score=0.7, factors={}, reasoning="Complex")
        decision = router.make_routing_decision(complexity)

        assert decision == RoutingDecision.CLOUD  # nosec B101

    def test_threshold_boundary(self, router):
        """Test routing at threshold boundary."""
        # Just below threshold → local
        complexity_below = ComplexityScore(score=0.49, factors={}, reasoning="Below")
        decision_below = router.make_routing_decision(complexity_below)
        assert decision_below == RoutingDecision.LOCAL  # nosec B101

        # At threshold → cloud
        complexity_at = ComplexityScore(score=0.5, factors={}, reasoning="At")
        decision_at = router.make_routing_decision(complexity_at)
        assert decision_at == RoutingDecision.CLOUD  # nosec B101

    def test_fallback_when_local_unavailable(self, router):
        """Test fallback to cloud when local unavailable."""
        complexity = ComplexityScore(score=0.3, factors={}, reasoning="Simple")
        decision = router.make_routing_decision(complexity, local_available=False)

        assert decision == RoutingDecision.FALLBACK  # nosec B101

    def test_fallback_when_cloud_unavailable(self, router):
        """Test fallback to local when cloud unavailable."""
        complexity = ComplexityScore(score=0.7, factors={}, reasoning="Complex")
        decision = router.make_routing_decision(complexity, cloud_available=False)

        assert decision == RoutingDecision.FALLBACK  # nosec B101

    def test_error_when_no_providers_available(self, router):
        """Test error when no providers available."""
        complexity = ComplexityScore(score=0.5, factors={}, reasoning="Test")

        with pytest.raises(RuntimeError, match="No LLM providers available"):
            router.make_routing_decision(complexity, local_available=False, cloud_available=False)


# ============================================================================
# Generation Tests
# ============================================================================


class TestGeneration:
    """Tests for LLM generation with routing."""

    @pytest.mark.asyncio
    async def test_simple_task_uses_local(self, router, mock_local_provider):
        """Test simple task uses local provider."""
        request = LLMRequest(prompt="Hello")
        response = await router.generate(request)

        assert response.text == "Local response"  # nosec B101
        assert response.provider == LLMProvider.LOCAL  # nosec B101
        mock_local_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_complex_task_uses_cloud(self, router, mock_cloud_provider):
        """Test complex task uses cloud provider."""
        request = LLMRequest(prompt="A" * 300)
        response = await router.generate(
            request, intent_type="multi_step_task", entity_count=5, step_count=4
        )

        assert response.text == "Cloud response"  # nosec B101
        assert response.provider == LLMProvider.OPENAI  # nosec B101
        mock_cloud_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_local_error(self, router, mock_local_provider, mock_cloud_provider):
        """Test fallback to cloud when local fails."""
        # Make local provider fail
        mock_local_provider.generate.side_effect = RuntimeError("Local failed")

        request = LLMRequest(prompt="Hello")
        response = await router.generate(request)

        # Should fallback to cloud
        assert response.text == "Cloud response"  # nosec B101
        assert response.provider == LLMProvider.OPENAI  # nosec B101
        mock_cloud_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_cloud_error(self, router, mock_local_provider, mock_cloud_provider):
        """Test fallback to local when cloud fails."""
        # Make cloud provider fail
        mock_cloud_provider.generate.side_effect = RuntimeError("Cloud failed")

        request = LLMRequest(prompt="A" * 300)
        response = await router.generate(request, intent_type="multi_step_task", entity_count=5)

        # Should fallback to local
        assert response.text == "Local response"  # nosec B101
        assert response.provider == LLMProvider.LOCAL  # nosec B101
        mock_local_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_when_both_providers_fail(
        self, router, mock_local_provider, mock_cloud_provider
    ):
        """Test error when both providers fail."""
        # Make both providers fail
        mock_local_provider.generate.side_effect = RuntimeError("Local failed")
        mock_cloud_provider.generate.side_effect = RuntimeError("Cloud failed")

        request = LLMRequest(prompt="Hello")

        with pytest.raises(RuntimeError, match="Primary provider failed"):
            await router.generate(request)

    @pytest.mark.asyncio
    async def test_no_fallback_when_disabled(self, mock_local_provider, mock_cloud_provider):
        """Test no fallback when fallback disabled."""
        router = HybridLLMRouter(
            local_provider=mock_local_provider,
            cloud_provider=mock_cloud_provider,
            enable_fallback=False,
        )

        # Make local provider fail
        mock_local_provider.generate.side_effect = RuntimeError("Local failed")

        request = LLMRequest(prompt="Hello")

        with pytest.raises(RuntimeError, match="Local failed"):
            await router.generate(request)

        # Cloud should not be called
        mock_cloud_provider.generate.assert_not_called()


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Tests for routing metrics."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = RoutingMetrics()

        assert metrics.total_requests == 0  # nosec B101
        assert metrics.local_requests == 0  # nosec B101
        assert metrics.cloud_requests == 0  # nosec B101
        assert metrics.fallback_requests == 0  # nosec B101

    def test_record_local_request(self):
        """Test recording local request."""
        metrics = RoutingMetrics()
        metrics.record_request(RoutingDecision.LOCAL, 100.0, error=False)

        assert metrics.total_requests == 1  # nosec B101
        assert metrics.local_requests == 1  # nosec B101
        # Latency history is a bounded deque (see MAX_LATENCY_SAMPLES) so a
        # long-running session cannot grow it without limit; compare contents.
        assert list(metrics.local_latency_ms) == [100.0]  # nosec B101
        assert metrics.local_errors == 0  # nosec B101

    def test_record_cloud_request(self):
        """Test recording cloud request."""
        metrics = RoutingMetrics()
        metrics.record_request(RoutingDecision.CLOUD, 200.0, error=False)

        assert metrics.total_requests == 1  # nosec B101
        assert metrics.cloud_requests == 1  # nosec B101
        assert list(metrics.cloud_latency_ms) == [200.0]  # nosec B101
        assert metrics.cloud_errors == 0  # nosec B101

    def test_record_error(self):
        """Test recording error."""
        metrics = RoutingMetrics()
        metrics.record_request(RoutingDecision.LOCAL, 100.0, error=True)

        assert metrics.local_errors == 1  # nosec B101

    def test_get_stats(self):
        """Test getting statistics."""
        metrics = RoutingMetrics()
        metrics.record_request(RoutingDecision.LOCAL, 100.0)
        metrics.record_request(RoutingDecision.CLOUD, 200.0)

        stats = metrics.get_stats()

        assert stats["total_requests"] == 2  # nosec B101
        assert stats["local_requests"] == 1  # nosec B101
        assert stats["cloud_requests"] == 1  # nosec B101
        assert stats["local_percentage"] == 50.0  # nosec B101
        assert stats["cloud_percentage"] == 50.0  # nosec B101
        assert stats["local_avg_latency_ms"] == 100.0  # nosec B101
        assert stats["cloud_avg_latency_ms"] == 200.0  # nosec B101

    @pytest.mark.asyncio
    async def test_router_tracks_metrics(self, router):
        """Test router tracks metrics."""
        request = LLMRequest(prompt="Hello")
        await router.generate(request)

        metrics = router.get_metrics()
        assert metrics["total_requests"] == 1  # nosec B101
        assert metrics["local_requests"] == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_reset_metrics(self, router):
        """Test resetting metrics."""
        request = LLMRequest(prompt="Hello")
        await router.generate(request)

        router.reset_metrics()
        metrics = router.get_metrics()

        assert metrics["total_requests"] == 0  # nosec B101
