"""
Unit tests for Ollama server integration.

Tests cover:
- Server initialization and configuration
- Health checks
- Model listing and selection
- Text generation
- Latency measurement
- Error handling

Coverage target: 80%+
"""

from unittest.mock import Mock, patch

import pytest
import requests

from Agent_Guru.reasoning.llm.models import (
    GPUBackend,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)
from Agent_Guru.reasoning.llm.ollama_server import (
    OLLAMA_MODELS,
    OllamaServer,
)


class TestOllamaModelConfig:
    """Test Ollama model configuration."""

    def test_predefined_models_exist(self):
        """Test that predefined models are configured."""
        assert "gemma3:4b" in OLLAMA_MODELS  # nosec B101
        assert "gemma3:4b" in OLLAMA_MODELS  # nosec B101

    def test_qwen_model_config(self):
        """Test Qwen model configuration."""
        config = OLLAMA_MODELS["gemma3:4b"]
        assert config.name == "gemma3:4b"  # nosec B101
        assert config.size_gb == 3.3  # nosec B101
        assert config.parameters == "4B"  # nosec B101
        assert config.use_case == "complex"  # nosec B101
        assert config.temperature == 0.7  # nosec B101
        assert config.top_p == 0.9  # nosec B101
        assert config.max_tokens == 512  # nosec B101

    def test_mistral_model_config(self):
        """Test Mistral model configuration."""
        config = OLLAMA_MODELS["gemma3:4b"]
        assert config.name == "gemma3:4b"  # nosec B101
        assert config.size_gb == 3.3  # nosec B101
        assert config.parameters == "7B"  # nosec B101
        assert config.use_case == "simple"  # nosec B101
        assert config.temperature == 0.7  # nosec B101
        assert config.top_p == 0.9  # nosec B101
        assert config.max_tokens == 512  # nosec B101


class TestOllamaServerInitialization:
    """Test Ollama server initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        server = OllamaServer()
        assert server.host == "127.0.0.1"  # nosec B101
        assert server.port == 11434  # nosec B101
        assert server.default_model == "gemma3:4b"  # nosec B101
        assert not server.is_running()  # nosec B101

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        server = OllamaServer(
            host="localhost",
            port=8080,
            default_model="gemma3:4b",
        )
        assert server.host == "localhost"  # nosec B101
        assert server.port == 8080  # nosec B101
        assert server.default_model == "gemma3:4b"  # nosec B101

    def test_init_with_invalid_model(self):
        """Test initialization with invalid model raises error."""
        with pytest.raises(ValueError, match="Unknown model"):
            OllamaServer(default_model="invalid-model")

    def test_base_url_construction(self):
        """Test base URL is constructed correctly."""
        server = OllamaServer(host="192.168.1.100", port=9999)
        assert server._base_url == "http://192.168.1.100:9999"  # nosec B101


class TestOllamaServerHealthCheck:
    """Test Ollama server health checks."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        server = OllamaServer()

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        with patch("requests.get", return_value=mock_response):
            health = await server.health_check()

        assert health.is_healthy  # nosec B101
        assert health.gpu_available  # nosec B101
        assert health.gpu_backend == GPUBackend.CUDA  # nosec B101
        assert health.latency_ms is not None  # nosec B101
        assert health.latency_ms >= 0  # nosec B101

    @pytest.mark.asyncio
    async def test_health_check_server_error(self):
        """Test health check with server error."""
        server = OllamaServer()

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500

        with patch("requests.get", return_value=mock_response):
            health = await server.health_check()

        assert not health.is_healthy  # nosec B101
        assert not health.model_loaded  # nosec B101
        assert not health.gpu_available  # nosec B101
        assert health.error_message is not None  # nosec B101

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """Test health check with connection error."""
        server = OllamaServer()

        # Mock connection error
        with patch("requests.get", side_effect=requests.ConnectionError("Connection refused")):
            health = await server.health_check()

        assert not health.is_healthy  # nosec B101
        assert not health.model_loaded  # nosec B101
        assert health.error_message is not None  # nosec B101
        assert "not available" in health.error_message  # nosec B101

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test health check with timeout."""
        server = OllamaServer()

        # Mock timeout
        with patch("requests.get", side_effect=requests.Timeout("Timeout")):
            health = await server.health_check()

        assert not health.is_healthy  # nosec B101
        assert health.latency_ms is None  # nosec B101


class TestOllamaServerStart:
    """Test Ollama server startup."""

    @pytest.mark.asyncio
    async def test_start_success(self):
        """Test successful server start."""
        server = OllamaServer()

        # Mock successful responses
        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {"models": []}

        mock_list_response = Mock()
        mock_list_response.status_code = 200
        mock_list_response.json.return_value = {
            "models": [
                {"name": "gemma3:4b"},
                {"name": "gemma3:4b"},
            ]
        }

        with patch("requests.get", return_value=mock_list_response):
            await server.start()

        assert server.is_running()  # nosec B101
        assert "gemma3:4b" in server.get_available_models()  # nosec B101
        assert "gemma3:4b" in server.get_available_models()  # nosec B101

    @pytest.mark.asyncio
    async def test_start_missing_models(self):
        """Test start fails when required models missing."""
        server = OllamaServer()

        # Mock response with missing models
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "other-model"}]}

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(RuntimeError, match="Required models not found"):
                await server.start()

    @pytest.mark.asyncio
    async def test_start_timeout(self):
        """Test start timeout when server not available."""
        server = OllamaServer()

        # Mock connection error
        with patch("requests.get", side_effect=requests.ConnectionError()):
            with pytest.raises(TimeoutError, match="not available"):
                await server.start(timeout=0.5)


class TestOllamaServerGeneration:
    """Test text generation with Ollama."""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful text generation."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        request = LLMRequest(
            prompt="Hello, world!",
            temperature=0.7,
            top_p=0.9,
            max_tokens=100,
        )

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello! How can I help you today?",
            "done": True,
            "done_reason": "stop",
            "eval_count": 8,
            "total_duration": 1500000000,  # 1.5s in nanoseconds
            "load_duration": 100000000,
            "prompt_eval_count": 3,
        }

        with patch("requests.post", return_value=mock_response):
            response = await server.generate(request)

        assert isinstance(response, LLMResponse)  # nosec B101
        assert response.text == "Hello! How can I help you today?"  # nosec B101
        assert response.provider == LLMProvider.LOCAL  # nosec B101
        assert response.latency_ms >= 0  # nosec B101
        assert response.tokens_generated == 8  # nosec B101
        assert response.finish_reason == "stop"  # nosec B101
        assert "model" in response.metadata  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_with_specific_model(self):
        """Test generation with specific model."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        request = LLMRequest(prompt="Test prompt")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Test response",
            "done": True,
            "eval_count": 2,
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            response = await server.generate(request, model="gemma3:4b")

        # Verify correct model was used
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "gemma3:4b"  # nosec B101
        assert response.metadata["model"] == "gemma3:4b"  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_server_not_running(self):
        """Test generation fails when server not running."""
        server = OllamaServer()
        request = LLMRequest(prompt="Test")

        with pytest.raises(RuntimeError, match="Server not running"):
            await server.generate(request)

    @pytest.mark.asyncio
    async def test_generate_model_not_available(self):
        """Test generation fails with unavailable model."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        request = LLMRequest(prompt="Test")

        with pytest.raises(RuntimeError, match="Model not available"):
            await server.generate(request, model="unknown-model")

    @pytest.mark.asyncio
    async def test_generate_api_error(self):
        """Test generation handles API errors."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        request = LLMRequest(prompt="Test")

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="Generation failed"):
                await server.generate(request)

    @pytest.mark.asyncio
    async def test_generate_with_stop_sequences(self):
        """Test generation with stop sequences."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        request = LLMRequest(
            prompt="Count to 5:",
            stop_sequences=["3", "4"],
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "1, 2, 3",
            "done": True,
            "eval_count": 5,
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            await server.generate(request)

        # Verify stop sequences were passed
        call_args = mock_post.call_args
        assert "stop" in call_args[1]["json"]["options"]  # nosec B101


class TestOllamaServerModelSelection:
    """Test model selection logic."""

    def test_select_model_simple_task(self):
        """Test model selection for simple tasks."""
        server = OllamaServer()
        model = server.select_model_for_task("simple")
        assert model == "gemma3:4b"  # nosec B101

    def test_select_model_complex_task(self):
        """Test model selection for complex tasks."""
        server = OllamaServer()
        model = server.select_model_for_task("complex")
        assert model == "gemma3:4b"  # nosec B101

    def test_get_model_config(self):
        """Test getting model configuration."""
        server = OllamaServer()

        config = server.get_model_config("gemma3:4b")
        assert config is not None  # nosec B101
        assert config.name == "gemma3:4b"  # nosec B101
        assert config.use_case == "simple"  # nosec B101

        config = server.get_model_config("gemma3:4b")
        assert config is not None  # nosec B101
        assert config.use_case == "complex"  # nosec B101

        config = server.get_model_config("unknown")
        assert config is None  # nosec B101


class TestOllamaServerLatencyMeasurement:
    """Test latency measurement."""

    @pytest.mark.asyncio
    async def test_measure_latency_success(self):
        """Test successful latency measurement."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        # Mock responses with varying latencies
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Test",
            "done": True,
            "eval_count": 1,
        }

        with patch("requests.post", return_value=mock_response):
            stats = await server.measure_latency("gemma3:4b", num_samples=5)

        assert "mean" in stats  # nosec B101
        assert "p50" in stats  # nosec B101
        assert "p95" in stats  # nosec B101
        assert "p99" in stats  # nosec B101
        assert stats["mean"] >= 0  # nosec B101
        assert stats["p50"] >= 0  # nosec B101
        assert stats["p95"] >= 0  # nosec B101
        assert stats["p99"] >= 0  # nosec B101

    @pytest.mark.asyncio
    async def test_measure_latency_all_failures(self):
        """Test latency measurement when all requests fail."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        # Mock failures
        with patch("requests.post", side_effect=requests.RequestException()):
            stats = await server.measure_latency("gemma3:4b", num_samples=3)

        # Should return zeros when all fail
        assert stats["mean"] == 0.0  # nosec B101
        assert stats["p50"] == 0.0  # nosec B101
        assert stats["p95"] == 0.0  # nosec B101
        assert stats["p99"] == 0.0  # nosec B101


class TestOllamaServerStop:
    """Test server stop."""

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping server client."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["model1", "model2"]

        await server.stop()

        assert not server.is_running()  # nosec B101
        assert len(server.get_available_models()) == 0  # nosec B101


class TestOllamaServerEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_generate_length_finish_reason(self):
        """Test generation with length finish reason."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        request = LLMRequest(prompt="Test", max_tokens=10)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "This is a very long response that exceeded the token limit",
            "done": True,
            "done_reason": "length",
            "eval_count": 10,
        }

        with patch("requests.post", return_value=mock_response):
            response = await server.generate(request)

        assert response.finish_reason == "length"  # nosec B101

    @pytest.mark.asyncio
    async def test_generate_incomplete_response(self):
        """Test generation with incomplete response."""
        server = OllamaServer()
        server._is_running = True
        server._available_models = ["gemma3:4b"]

        request = LLMRequest(prompt="Test")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Partial response",
            "done": False,  # Not done
            "eval_count": 2,
        }

        with patch("requests.post", return_value=mock_response):
            response = await server.generate(request)

        assert response.finish_reason == "error"  # nosec B101

    def test_get_available_models_returns_copy(self):
        """Test that get_available_models returns a copy."""
        server = OllamaServer()
        server._available_models = ["model1", "model2"]

        models = server.get_available_models()
        models.append("model3")

        # Original should not be modified
        assert len(server.get_available_models()) == 2  # nosec B101
