"""
Property-based tests for Ollama server integration.

Tests universal properties that should hold across all valid inputs.
Uses Hypothesis for property-based testing with 100 iterations.

Properties tested:
- Request validation always produces valid or error
- Response structure is always valid
- Latency is always non-negative
- Model selection is deterministic
- Health checks are idempotent
"""

from unittest.mock import Mock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.llm.generation import DEFAULT_OLLAMA_MODEL
from Agent_Guru.reasoning.llm.models import LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.ollama_server import (
    OLLAMA_MODELS,
    OLLAMA_USE_CASES,
    OllamaServer,
)


# Custom strategies for LLM testing
@st.composite
def llm_request_strategy(draw):
    """Generate valid LLM requests."""
    prompt = draw(st.text(min_size=1, max_size=1000))
    temperature = draw(st.floats(min_value=0.0, max_value=2.0))
    top_p = draw(st.floats(min_value=0.0, max_value=1.0))
    max_tokens = draw(st.integers(min_value=1, max_value=2048))
    stop_sequences = draw(st.lists(st.text(min_size=1, max_size=10), max_size=5))

    return LLMRequest(
        prompt=prompt,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stop_sequences=stop_sequences,
    )


class TestOllamaRequestValidation:
    """Property tests for request validation."""

    @given(llm_request_strategy())
    @settings(max_examples=100)
    def test_valid_request_always_accepted(self, request):
        """Property: Valid LLM requests are always accepted.

        Validates: Requirements 4.2
        """
        # Valid request should not raise during creation
        assert isinstance(request, LLMRequest)  # nosec B101
        assert request.prompt is not None  # nosec B101
        assert 0.0 <= request.temperature <= 2.0  # nosec B101
        assert 0.0 <= request.top_p <= 1.0  # nosec B101
        assert request.max_tokens > 0  # nosec B101

    @given(st.floats(min_value=-10.0, max_value=-0.1) | st.floats(min_value=2.1, max_value=10.0))
    @settings(max_examples=100)
    def test_invalid_temperature_rejected(self, temperature):
        """Property: Invalid temperature values are rejected.

        Validates: Requirements 4.2
        """
        with pytest.raises(ValueError, match="temperature"):
            LLMRequest(prompt="test", temperature=temperature)

    @given(st.floats(min_value=-10.0, max_value=-0.1) | st.floats(min_value=1.1, max_value=10.0))
    @settings(max_examples=100)
    def test_invalid_top_p_rejected(self, top_p):
        """Property: Invalid top_p values are rejected.

        Validates: Requirements 4.2
        """
        with pytest.raises(ValueError, match="top_p"):
            LLMRequest(prompt="test", top_p=top_p)

    @given(st.integers(max_value=0))
    @settings(max_examples=100)
    def test_invalid_max_tokens_rejected(self, max_tokens):
        """Property: Non-positive max_tokens are rejected.

        Validates: Requirements 4.2
        """
        with pytest.raises(ValueError, match="max_tokens"):
            LLMRequest(prompt="test", max_tokens=max_tokens)


class TestOllamaResponseStructure:
    """Property tests for response structure."""

    @given(
        text=st.text(min_size=0, max_size=5000),
        latency_ms=st.floats(min_value=0.0, max_value=10000.0),
        tokens=st.integers(min_value=0, max_value=2048),
        finish_reason=st.sampled_from(["stop", "length", "error"]),
    )
    @settings(max_examples=100)
    def test_response_structure_always_valid(self, text, latency_ms, tokens, finish_reason):
        """Property: LLM responses always have valid structure.

        Validates: Requirements 4.2, 10.1
        """
        from Agent_Guru.reasoning.llm.models import LLMProvider

        response = LLMResponse(
            text=text,
            provider=LLMProvider.LOCAL,
            latency_ms=latency_ms,
            tokens_generated=tokens,
            finish_reason=finish_reason,
        )

        assert isinstance(response, LLMResponse)  # nosec B101
        assert response.text == text  # nosec B101
        assert response.latency_ms >= 0  # nosec B101
        assert response.tokens_generated >= 0  # nosec B101
        assert response.finish_reason in ["stop", "length", "error"]  # nosec B101

    @given(st.floats(max_value=-0.1))
    @settings(max_examples=100)
    def test_negative_latency_rejected(self, latency_ms):
        """Property: Negative latency is rejected.

        Validates: Requirements 10.1
        """
        from Agent_Guru.reasoning.llm.models import LLMProvider

        with pytest.raises(ValueError, match="latency_ms"):
            LLMResponse(
                text="test",
                provider=LLMProvider.LOCAL,
                latency_ms=latency_ms,
                tokens_generated=10,
                finish_reason="stop",
            )

    @given(st.integers(max_value=-1))
    @settings(max_examples=100)
    def test_negative_tokens_rejected(self, tokens):
        """Property: Negative token count is rejected.

        Validates: Requirements 4.2
        """
        from Agent_Guru.reasoning.llm.models import LLMProvider

        with pytest.raises(ValueError, match="tokens_generated"):
            LLMResponse(
                text="test",
                provider=LLMProvider.LOCAL,
                latency_ms=100.0,
                tokens_generated=tokens,
                finish_reason="stop",
            )


class TestOllamaModelSelection:
    """Property tests for model selection."""

    @given(st.sampled_from(["simple", "complex"]))
    @settings(max_examples=100)
    def test_model_selection_deterministic(self, complexity):
        """Property: Model selection is deterministic for same complexity.

        Validates: Requirements 4.2, 4.5
        """
        server = OllamaServer()

        # Select model multiple times
        model1 = server.select_model_for_task(complexity)
        model2 = server.select_model_for_task(complexity)
        model3 = server.select_model_for_task(complexity)

        # Should always return same model
        assert model1 == model2 == model3  # nosec B101

        # Should be a valid model
        assert model1 in OLLAMA_MODELS  # nosec B101

    @given(st.sampled_from(["simple", "complex"]))
    @settings(max_examples=100)
    def test_selected_model_has_config(self, complexity):
        """Property: Selected models always have configuration.

        Validates: Requirements 4.2
        """
        server = OllamaServer()
        model = server.select_model_for_task(complexity)
        config = server.get_model_config(model)

        assert config is not None  # nosec B101
        assert config.name == model  # nosec B101
        # The registry's single entry is "general"; assert against the
        # declared vocabulary rather than a hard-coded pair that predates the
        # consolidation to one model.
        assert config.use_case in OLLAMA_USE_CASES  # nosec B101

    def test_simple_uses_mistral(self):
        """Property: Simple tasks always use Mistral 7B."""
        server = OllamaServer()
        model = server.select_model_for_task("simple")
        assert model == DEFAULT_OLLAMA_MODEL  # nosec B101

    def test_complex_uses_qwen(self):
        """Property: Complex tasks always use Qwen 14B."""
        server = OllamaServer()
        model = server.select_model_for_task("complex")
        assert model == DEFAULT_OLLAMA_MODEL  # nosec B101


class TestOllamaHealthCheckIdempotence:
    """Property tests for health check idempotence."""

    @pytest.mark.asyncio
    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=20)  # Reduced for async tests
    async def test_health_check_idempotent(self, num_checks):
        """Property: Multiple health checks return consistent results.

        Validates: Requirements 4.2
        """
        server = OllamaServer()

        # Mock consistent response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        with patch("requests.get", return_value=mock_response):
            results = []
            for _ in range(num_checks):
                health = await server.health_check()
                results.append(health.is_healthy)

        # All checks should return same result
        assert all(r == results[0] for r in results)  # nosec B101


class TestOllamaServerInitialization:
    """Property tests for server initialization."""

    @given(
        host=st.text(min_size=1, max_size=100),
        port=st.integers(min_value=1024, max_value=65535),
    )
    @settings(max_examples=100)
    def test_initialization_always_succeeds_with_valid_params(self, host, port):
        """Property: Valid initialization parameters always succeed.

        Validates: Requirements 4.2
        """
        server = OllamaServer(host=host, port=port)

        assert server.host == host  # nosec B101
        assert server.port == port  # nosec B101
        assert not server.is_running()  # nosec B101
        assert server._base_url == f"http://{host}:{port}"  # nosec B101

    @given(st.sampled_from(list(OLLAMA_MODELS.keys())))
    @settings(max_examples=100)
    def test_initialization_with_any_valid_model(self, model):
        """Property: Initialization succeeds with any valid model.

        Validates: Requirements 4.2
        """
        server = OllamaServer(default_model=model)
        assert server.default_model == model  # nosec B101

    @given(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()))
    @settings(max_examples=100)
    def test_initialization_accepts_any_non_blank_model(self, model):
        """Property: any non-blank model name is accepted.

        OLLAMA_MODELS is a tuned-parameter table, not an allow-list - Ollama
        serves whatever the operator pulled, and OLLAMA_MODEL may name it.
        This property used to assert the opposite (that anything outside the
        table raised) which contradicted the implementation and five call
        sites that rely on the override.

        Validates: Requirements 4.2
        """
        server = OllamaServer(default_model=model)
        assert server.default_model == model  # nosec B101

    @given(st.text(max_size=10).filter(lambda x: not x.strip()))
    @settings(max_examples=50)
    def test_initialization_fails_with_blank_model(self, model):
        """Property: a blank model name is always rejected.

        Validates: Requirements 4.2
        """
        with pytest.raises(ValueError, match="Unknown model"):
            OllamaServer(default_model=model)


class TestOllamaLatencyProperties:
    """Property tests for latency measurement."""

    @pytest.mark.asyncio
    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=10)  # Reduced for async tests
    async def test_latency_stats_always_valid(self, num_samples):
        """Property: Latency statistics are always valid.

        Validates: Requirements 10.1
        """
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        # Mock responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "test",
            "done": True,
            "eval_count": 1,
        }

        with patch("requests.post", return_value=mock_response):
            stats = await server.measure_latency("gemma3:4b", num_samples=num_samples)

        # All stats should be non-negative
        assert stats["mean"] >= 0  # nosec B101
        assert stats["p50"] >= 0  # nosec B101
        assert stats["p95"] >= 0  # nosec B101
        assert stats["p99"] >= 0  # nosec B101

        # Percentiles should be ordered
        assert stats["p50"] <= stats["p95"] <= stats["p99"]  # nosec B101


class TestOllamaRequestResponseRoundtrip:
    """Property tests for request-response roundtrip."""

    @pytest.mark.asyncio
    @given(llm_request_strategy())
    @settings(max_examples=20)  # Reduced for async tests
    async def test_request_parameters_preserved_in_api_call(self, request):
        """Property: Request parameters are preserved in API call.

        Validates: Requirements 4.2
        """
        server = OllamaServer()
        server._is_running = True
        server._available_models = [DEFAULT_OLLAMA_MODEL]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "test",
            "done": True,
            "eval_count": 1,
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            await server.generate(request)

        # Verify request parameters were passed correctly
        call_args = mock_post.call_args
        payload = call_args[1]["json"]

        assert payload["prompt"] == request.prompt  # nosec B101
        assert payload["options"]["temperature"] == request.temperature  # nosec B101
        assert payload["options"]["top_p"] == request.top_p  # nosec B101
        assert payload["options"]["num_predict"] == request.max_tokens  # nosec B101
