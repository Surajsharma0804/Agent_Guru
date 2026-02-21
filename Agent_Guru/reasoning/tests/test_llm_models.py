"""
Tests for LLM data models.

Tests LLMRequest, LLMResponse, LocalLLMConfig, and ServerHealth models.
"""

import pytest
from datetime import datetime
from Agent_Guru.reasoning.llm.models import (
    LLMRequest,
    LLMResponse,
    LocalLLMConfig,
    ServerHealth,
    LLMProvider,
    GPUBackend,
)


class TestLLMRequest:
    """Test LLMRequest model."""

    def test_valid_request(self):
        """Test creating valid LLM request."""
        request = LLMRequest(
            prompt="Hello, world!",
            temperature=0.7,
            top_p=0.9,
            max_tokens=512,
        )

        assert request.prompt == "Hello, world!"
        assert request.temperature == 0.7
        assert request.top_p == 0.9
        assert request.max_tokens == 512
        assert request.stop_sequences == []
        assert request.stream is False
        assert request.metadata == {}

    def test_invalid_temperature(self):
        """Test that invalid temperature raises error."""
        with pytest.raises(ValueError, match="temperature must be 0.0-2.0"):
            LLMRequest(prompt="test", temperature=3.0)

        with pytest.raises(ValueError, match="temperature must be 0.0-2.0"):
            LLMRequest(prompt="test", temperature=-0.1)

    def test_invalid_top_p(self):
        """Test that invalid top_p raises error."""
        with pytest.raises(ValueError, match="top_p must be 0.0-1.0"):
            LLMRequest(prompt="test", top_p=1.5)

        with pytest.raises(ValueError, match="top_p must be 0.0-1.0"):
            LLMRequest(prompt="test", top_p=-0.1)

    def test_invalid_max_tokens(self):
        """Test that invalid max_tokens raises error."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            LLMRequest(prompt="test", max_tokens=0)

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            LLMRequest(prompt="test", max_tokens=-10)

    def test_with_stop_sequences(self):
        """Test request with stop sequences."""
        request = LLMRequest(
            prompt="test", stop_sequences=["\\n", "END"]
        )

        assert request.stop_sequences == ["\\n", "END"]

    def test_with_metadata(self):
        """Test request with metadata."""
        request = LLMRequest(
            prompt="test", metadata={"user_id": "123", "session": "abc"}
        )

        assert request.metadata["user_id"] == "123"
        assert request.metadata["session"] == "abc"



class TestLLMResponse:
    """Test LLMResponse model."""

    def test_valid_response(self):
        """Test creating valid LLM response."""
        response = LLMResponse(
            text="Generated text",
            provider=LLMProvider.LOCAL,
            latency_ms=150.5,
            tokens_generated=50,
            finish_reason="stop",
        )

        assert response.text == "Generated text"
        assert response.provider == LLMProvider.LOCAL
        assert response.latency_ms == 150.5
        assert response.tokens_generated == 50
        assert response.finish_reason == "stop"
        assert isinstance(response.timestamp, datetime)

    def test_invalid_latency(self):
        """Test that negative latency raises error."""
        with pytest.raises(ValueError, match="latency_ms must be non-negative"):
            LLMResponse(
                text="test",
                provider=LLMProvider.LOCAL,
                latency_ms=-10.0,
                tokens_generated=10,
                finish_reason="stop",
            )

    def test_invalid_tokens(self):
        """Test that negative tokens raises error."""
        with pytest.raises(ValueError, match="tokens_generated must be non-negative"):
            LLMResponse(
                text="test",
                provider=LLMProvider.LOCAL,
                latency_ms=100.0,
                tokens_generated=-5,
                finish_reason="stop",
            )

    def test_invalid_finish_reason(self):
        """Test that invalid finish_reason raises error."""
        with pytest.raises(ValueError, match="finish_reason must be"):
            LLMResponse(
                text="test",
                provider=LLMProvider.LOCAL,
                latency_ms=100.0,
                tokens_generated=10,
                finish_reason="invalid",
            )

    def test_finish_reasons(self):
        """Test all valid finish reasons."""
        for reason in ["stop", "length", "error"]:
            response = LLMResponse(
                text="test",
                provider=LLMProvider.LOCAL,
                latency_ms=100.0,
                tokens_generated=10,
                finish_reason=reason,
            )
            assert response.finish_reason == reason

    def test_with_metadata(self):
        """Test response with metadata."""
        response = LLMResponse(
            text="test",
            provider=LLMProvider.LOCAL,
            latency_ms=100.0,
            tokens_generated=10,
            finish_reason="stop",
            metadata={"model": "llama-3.2-8b", "gpu": "cuda"},
        )

        assert response.metadata["model"] == "llama-3.2-8b"
        assert response.metadata["gpu"] == "cuda"



class TestLocalLLMConfig:
    """Test LocalLLMConfig model."""

    def test_valid_config(self):
        """Test creating valid config."""
        config = LocalLLMConfig(
            model_path="models/llama-3.2-8b.gguf",
            gpu_backend=GPUBackend.CUDA,
            n_gpu_layers=35,
            n_ctx=2048,
            n_threads=8,
            host="127.0.0.1",
            port=8080,
        )

        assert config.model_path == "models/llama-3.2-8b.gguf"
        assert config.gpu_backend == GPUBackend.CUDA
        assert config.n_gpu_layers == 35
        assert config.n_ctx == 2048
        assert config.n_threads == 8
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.temperature == 0.7
        assert config.top_p == 0.9
        assert config.max_tokens == 512

    def test_invalid_gpu_layers(self):
        """Test that negative GPU layers raises error."""
        with pytest.raises(ValueError, match="n_gpu_layers must be non-negative"):
            LocalLLMConfig(model_path="test.gguf", n_gpu_layers=-1)

    def test_invalid_context_size(self):
        """Test that invalid context size raises error."""
        with pytest.raises(ValueError, match="n_ctx must be positive"):
            LocalLLMConfig(model_path="test.gguf", n_ctx=0)

        with pytest.raises(ValueError, match="n_ctx must be positive"):
            LocalLLMConfig(model_path="test.gguf", n_ctx=-100)

    def test_invalid_threads(self):
        """Test that invalid threads raises error."""
        with pytest.raises(ValueError, match="n_threads must be positive"):
            LocalLLMConfig(model_path="test.gguf", n_threads=0)

    def test_invalid_port(self):
        """Test that invalid port raises error."""
        with pytest.raises(ValueError, match="port must be 1024-65535"):
            LocalLLMConfig(model_path="test.gguf", port=80)

        with pytest.raises(ValueError, match="port must be 1024-65535"):
            LocalLLMConfig(model_path="test.gguf", port=70000)

    def test_invalid_temperature(self):
        """Test that invalid temperature raises error."""
        with pytest.raises(ValueError, match="temperature must be 0.0-2.0"):
            LocalLLMConfig(model_path="test.gguf", temperature=3.0)

    def test_invalid_top_p(self):
        """Test that invalid top_p raises error."""
        with pytest.raises(ValueError, match="top_p must be 0.0-1.0"):
            LocalLLMConfig(model_path="test.gguf", top_p=1.5)

    def test_invalid_max_tokens(self):
        """Test that invalid max_tokens raises error."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            LocalLLMConfig(model_path="test.gguf", max_tokens=0)

    def test_gpu_backends(self):
        """Test all GPU backend options."""
        for backend in [GPUBackend.CUDA, GPUBackend.METAL, GPUBackend.CPU]:
            config = LocalLLMConfig(
                model_path="test.gguf", gpu_backend=backend
            )
            assert config.gpu_backend == backend



class TestServerHealth:
    """Test ServerHealth model."""

    def test_healthy_server(self):
        """Test healthy server status."""
        health = ServerHealth(
            is_healthy=True,
            model_loaded=True,
            gpu_available=True,
            gpu_backend=GPUBackend.CUDA,
            latency_ms=25.5,
        )

        assert health.is_healthy is True
        assert health.model_loaded is True
        assert health.gpu_available is True
        assert health.gpu_backend == GPUBackend.CUDA
        assert health.latency_ms == 25.5
        assert health.error_message is None
        assert isinstance(health.timestamp, datetime)

    def test_unhealthy_server(self):
        """Test unhealthy server status."""
        health = ServerHealth(
            is_healthy=False,
            model_loaded=False,
            gpu_available=False,
            gpu_backend=None,
            latency_ms=None,
            error_message="Server not running",
        )

        assert health.is_healthy is False
        assert health.model_loaded is False
        assert health.gpu_available is False
        assert health.gpu_backend is None
        assert health.latency_ms is None
        assert health.error_message == "Server not running"

    def test_partial_health(self):
        """Test server with partial health (running but model not loaded)."""
        health = ServerHealth(
            is_healthy=True,
            model_loaded=False,
            gpu_available=True,
            gpu_backend=GPUBackend.CUDA,
            latency_ms=30.0,
        )

        assert health.is_healthy is True
        assert health.model_loaded is False
        assert health.gpu_available is True
