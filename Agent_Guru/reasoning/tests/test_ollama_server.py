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
from Agent_Guru.reasoning.llm.generation import DEFAULT_OLLAMA_MODEL
from Agent_Guru.reasoning.llm.ollama_server import (
    OLLAMA_MODELS,
    OLLAMA_USE_CASES,
    OllamaModelConfig,
    OllamaServer,
)

#: The model a bare OllamaServer() asks for. These tests used the literal
#: "gemma3:4b" for it, so changing the default model broke every test that
#: never cared which model it was.
DEFAULT_MODEL = DEFAULT_OLLAMA_MODEL


@pytest.fixture(autouse=True)
def _no_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """OllamaServer() reads OLLAMA_MODEL, so a developer's own setting must not leak in."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)


class TestOllamaModelConfig:
    """Test Ollama model configuration."""

    def test_predefined_models_exist(self):
        """Test that predefined models are configured."""
        assert OLLAMA_MODELS  # nosec B101
        assert "gemma3:4b" in OLLAMA_MODELS  # nosec B101
        # The default a bare OllamaServer() uses must be a model the registry
        # can describe, otherwise get_model_config() returns None for the very
        # model the server will actually call.
        assert OllamaServer().default_model in OLLAMA_MODELS  # nosec B101

    def test_gemma3_model_config(self):
        """Test the registered gemma3:4b configuration."""
        config = OLLAMA_MODELS["gemma3:4b"]
        assert config.name == "gemma3:4b"  # nosec B101
        assert config.size_gb == 3.3  # nosec B101
        assert config.parameters == "4B"  # nosec B101
        assert config.use_case == "general"  # nosec B101
        assert config.temperature == 0.7  # nosec B101
        assert config.top_p == 0.9  # nosec B101
        assert config.max_tokens == 512  # nosec B101

    def test_every_registered_model_is_self_consistent(self):
        """Every registry entry must satisfy the config invariants."""
        for key, config in OLLAMA_MODELS.items():
            # The dict key is what callers pass to get_model_config(); if it
            # disagreed with config.name the server would request a model that
            # does not match the sampling parameters it loaded.
            assert key == config.name, key  # nosec B101
            assert config.size_gb > 0, key  # nosec B101
            assert config.parameters, key  # nosec B101
            assert config.use_case in OLLAMA_USE_CASES, key  # nosec B101
            assert 0.0 <= config.temperature <= 2.0, key  # nosec B101
            assert 0.0 < config.top_p <= 1.0, key  # nosec B101
            assert config.max_tokens > 0, key  # nosec B101

    def test_model_config_rejects_invalid_values(self):
        """OllamaModelConfig validates its own fields on construction."""
        base = {
            "name": "gemma3:4b",
            "size_gb": 3.3,
            "parameters": "4B",
            "use_case": "general",
        }
        for field, bad in (
            ("name", ""),
            ("size_gb", 0.0),
            ("use_case", "medium"),
            ("temperature", 2.5),
            ("top_p", 0.0),
            ("max_tokens", 0),
        ):
            with pytest.raises(ValueError, match=field):
                OllamaModelConfig(**{**base, field: bad})


class TestOllamaServerInitialization:
    """Test Ollama server initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        server = OllamaServer()
        assert server.host == "127.0.0.1"  # nosec B101
        assert server.port == 11434  # nosec B101
        assert server.default_model == DEFAULT_MODEL  # nosec B101
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

    def test_init_accepts_models_outside_the_registry(self):
        """Any model name Ollama might serve is accepted.

        OLLAMA_MODELS is a table of models whose sampling parameters this
        project has tuned, NOT an allow-list. Ollama serves whatever the
        operator has pulled, and the OLLAMA_MODEL environment variable is
        honoured in five places, so rejecting unregistered names here would
        break every one of those overrides. This test pins that contract so a
        future "validation" change cannot silently reintroduce the restriction.
        """
        server = OllamaServer(default_model="llama3.2:1b")
        assert server.default_model == "llama3.2:1b"  # nosec B101
        # ...but an unregistered model has no tuned configuration.
        assert server.get_model_config("llama3.2:1b") is None  # nosec B101

    @pytest.mark.parametrize("bad_model", ["", "   ", "\t\n"])
    def test_init_with_blank_model(self, bad_model):
        """A blank model name can never be a model Ollama serves."""
        with pytest.raises(ValueError, match="Unknown model"):
            OllamaServer(default_model=bad_model)

    @pytest.mark.parametrize("bad_port", [0, -1, 65536, 100000])
    def test_init_with_invalid_port(self, bad_port):
        """A port outside the TCP range is a configuration mistake."""
        with pytest.raises(ValueError, match="port"):
            OllamaServer(port=bad_port)

    @pytest.mark.parametrize("bad_host", ["", "   "])
    def test_init_with_blank_host(self, bad_host):
        """A blank host would build the nonsense base URL 'http://:11434'."""
        with pytest.raises(ValueError, match="host"):
            OllamaServer(host=bad_host)

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
                {"name": DEFAULT_MODEL},
                {"name": "llama3.2:1b"},
            ]
        }

        with patch("requests.get", return_value=mock_list_response):
            await server.start()

        assert server.is_running()  # nosec B101
        assert DEFAULT_MODEL in server.get_available_models()  # nosec B101
        assert "llama3.2:1b" in server.get_available_models()  # nosec B101

    @pytest.mark.asyncio
    async def test_start_missing_models(self):
        """Test start fails when the configured model is missing."""
        server = OllamaServer()

        # Mock response with missing models
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "other-model"}]}

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(RuntimeError, match="Configured model not found"):
                await server.start()

    @pytest.mark.asyncio
    async def test_start_accepts_the_model_named_by_ollama_model(self, monkeypatch):
        """start() must require the model the server will actually use.

        DEFECT FIX: start() used to demand the literal "gemma3:4b" while
        select_model_for_task() honoured OLLAMA_MODEL. Anyone who pulled a
        smaller model to suit weaker hardware - the whole reason that
        environment variable exists - had the server refuse to start, naming
        a model they had deliberately not installed.
        """
        monkeypatch.setenv("OLLAMA_MODEL", "gemma3:1b")
        server = OllamaServer()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "gemma3:1b"}]}

        with patch("requests.get", return_value=mock_response):
            await server.start()

        assert server.is_running()  # nosec B101

    @pytest.mark.asyncio
    async def test_start_rejects_when_the_configured_model_is_absent(self, monkeypatch):
        """The error must name the configured model, not a hard-coded one."""
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:0.5b")
        server = OllamaServer()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "gemma3:4b"}]}

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(RuntimeError, match="qwen2.5:0.5b"):
                await server.start()

    @pytest.mark.asyncio
    async def test_start_timeout_defaults_to_the_policy(self, monkeypatch):
        """A cold server still loading a model must not be declared missing.

        The old default was a hard-coded 10 s, which assumed an already-warm
        server; the policy default allows for reading model weights off disk
        on a machine without a GPU.
        """
        from Agent_Guru.reasoning.llm.timeouts import start_timeout

        monkeypatch.setenv("OLLAMA_START_TIMEOUT_SECONDS", "0.3")
        assert start_timeout() == 0.3
        server = OllamaServer()
        with patch("requests.get", side_effect=requests.ConnectionError()):
            with pytest.raises(TimeoutError, match="not available"):
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
        server._available_models = [DEFAULT_MODEL]

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
        server._available_models = [DEFAULT_MODEL]

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
        server._available_models = [DEFAULT_MODEL]

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
        assert model == DEFAULT_MODEL  # nosec B101

    def test_select_model_complex_task(self):
        """Test model selection for complex tasks."""
        server = OllamaServer()
        model = server.select_model_for_task("complex")
        assert model == DEFAULT_MODEL  # nosec B101

    def test_get_model_config(self):
        """Test getting model configuration."""
        server = OllamaServer()

        config = server.get_model_config("gemma3:4b")
        assert config is not None  # nosec B101
        assert config.name == "gemma3:4b"  # nosec B101
        assert config.use_case == "general"  # nosec B101

        # Repeated lookups must return the same configuration object, not a
        # per-call copy callers could mutate independently.
        assert server.get_model_config("gemma3:4b") is config  # nosec B101

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
        server._available_models = [DEFAULT_MODEL]

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
        server._available_models = [DEFAULT_MODEL]

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
