"""
Tests for LocalLLMServer.

Tests server lifecycle, health checks, and inference.
"""

import subprocess
from unittest.mock import AsyncMock, Mock, patch

import pytest

from Agent_Guru.reasoning.llm.local_server import LocalLLMServer
from Agent_Guru.reasoning.llm.models import (
    GPUBackend,
    LLMRequest,
    LocalLLMConfig,
)


class TestLocalLLMServerInit:
    """Test LocalLLMServer initialization."""

    def test_init_with_valid_config(self, tmp_path):
        """Test initialization with valid config."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        assert server.config == config
        assert server.process is None
        assert server._is_running is False
        assert server._model_loaded is False
        assert server._base_url == "http://127.0.0.1:8080"

    def test_init_with_nonexistent_model(self):
        """Test that nonexistent model raises error."""
        config = LocalLLMConfig(model_path="nonexistent.gguf")

        with pytest.raises(FileNotFoundError, match="Model file not found"):
            LocalLLMServer(config)

    def test_init_with_custom_host_port(self, tmp_path):
        """Test initialization with custom host and port."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file), host="0.0.0.0", port=9000)
        server = LocalLLMServer(config)

        assert server._base_url == "http://0.0.0.0:9000"


class TestServerBinaryDetection:
    """Test server binary detection."""

    def test_detect_server_binary_in_path(self, tmp_path):
        """Test detecting server binary in PATH."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        with patch.object(server, "_is_command_available", return_value=True):
            binary = server._detect_server_binary()
            assert binary in ["llama-server", "server", "llama.cpp-server"]

    def test_detect_server_binary_not_found(self, tmp_path):
        """Test error when binary not found."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        with patch.object(server, "_is_command_available", return_value=False):
            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(FileNotFoundError, match="llama.cpp server binary not found"):
                    server._detect_server_binary()

    def test_is_command_available_success(self):
        """Test _is_command_available with available command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = None
            result = LocalLLMServer._is_command_available("test-command")
            assert result is True

    def test_is_command_available_failure(self):
        """Test _is_command_available with unavailable command."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = LocalLLMServer._is_command_available("nonexistent")
            assert result is False


class TestServerCommandBuilding:
    """Test server command building."""

    def test_build_server_command_cuda(self, tmp_path):
        """Test building command with CUDA backend."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(
            model_path=str(model_file),
            gpu_backend=GPUBackend.CUDA,
            n_gpu_layers=35,
            n_ctx=2048,
            n_threads=8,
            port=8080,
        )
        server = LocalLLMServer(config)

        with patch.object(server, "_detect_server_binary", return_value="llama-server"):
            cmd = server._build_server_command()

            assert "llama-server" in cmd
            assert "-m" in cmd
            assert str(model_file) in cmd
            assert "--host" in cmd
            assert "127.0.0.1" in cmd
            assert "--port" in cmd
            assert "8080" in cmd
            assert "-c" in cmd
            assert "2048" in cmd
            assert "-t" in cmd
            assert "8" in cmd
            assert "-ngl" in cmd
            assert "35" in cmd

    def test_build_server_command_metal(self, tmp_path):
        """Test building command with Metal backend."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(
            model_path=str(model_file),
            gpu_backend=GPUBackend.METAL,
            n_gpu_layers=35,
        )
        server = LocalLLMServer(config)

        with patch.object(server, "_detect_server_binary", return_value="llama-server"):
            cmd = server._build_server_command()

            assert "-ngl" in cmd
            assert "35" in cmd

    def test_build_server_command_cpu(self, tmp_path):
        """Test building command with CPU backend."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file), gpu_backend=GPUBackend.CPU)
        server = LocalLLMServer(config)

        with patch.object(server, "_detect_server_binary", return_value="llama-server"):
            cmd = server._build_server_command()

            # CPU mode should not have -ngl flag
            assert "-ngl" not in cmd


@pytest.mark.asyncio
class TestServerLifecycle:
    """Test server start/stop lifecycle."""

    async def test_start_server_success(self, tmp_path):
        """Test successful server start."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        mock_process = Mock()
        mock_process.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            with patch.object(
                server,
                "health_check",
                return_value=AsyncMock(is_healthy=True, model_loaded=True)(),
            ):
                await server.start(timeout=1.0)

                assert server._is_running is True
                assert server._model_loaded is True

    async def test_start_server_timeout(self, tmp_path):
        """Test server start timeout."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        mock_process = Mock()
        mock_process.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_process):
            with patch.object(
                server,
                "health_check",
                return_value=AsyncMock(is_healthy=False, model_loaded=False)(),
            ):
                with pytest.raises(TimeoutError, match="Server failed to start"):
                    await server.start(timeout=0.5)

                mock_process.kill.assert_called_once()

    async def test_start_already_running(self, tmp_path):
        """Test starting already running server."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)
        server._is_running = True

        await server.start()  # Should return immediately

        assert server._is_running is True

    async def test_stop_server(self, tmp_path):
        """Test stopping server."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        mock_process = Mock()
        mock_process.wait = Mock()
        server.process = mock_process
        server._is_running = True
        server._model_loaded = True

        await server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        assert server._is_running is False
        assert server._model_loaded is False

    async def test_stop_server_force_kill(self, tmp_path):
        """Test force killing server on timeout."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        mock_process = Mock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5.0)
        server.process = mock_process
        server._is_running = True

        await server.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()


@pytest.mark.asyncio
class TestHealthCheck:
    """Test health check functionality."""

    async def test_health_check_healthy(self, tmp_path):
        """Test health check with healthy server."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        mock_process = Mock()
        mock_process.poll.return_value = None
        server.process = mock_process

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model_loaded": True,
            "gpu": True,
        }

        with patch("requests.get", return_value=mock_response):
            health = await server.health_check()

            assert health.is_healthy is True
            assert health.model_loaded is True
            assert health.gpu_available is True
            assert health.gpu_backend == GPUBackend.CUDA
            assert health.latency_ms is not None
            assert health.latency_ms >= 0

    async def test_health_check_process_not_running(self, tmp_path):
        """Test health check when process not running."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        health = await server.health_check()

        assert health.is_healthy is False
        assert health.model_loaded is False
        assert health.error_message == "Server process not running"

    async def test_health_check_http_error(self, tmp_path):
        """Test health check with HTTP error."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        mock_process = Mock()
        mock_process.poll.return_value = None
        server.process = mock_process

        mock_response = Mock()
        mock_response.status_code = 500

        with patch("requests.get", return_value=mock_response):
            health = await server.health_check()

            assert health.is_healthy is False
            assert "Health check failed: 500" in health.error_message

    async def test_health_check_request_exception(self, tmp_path):
        """Test health check with request exception."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        mock_process = Mock()
        mock_process.poll.return_value = None
        server.process = mock_process

        with patch("requests.get", side_effect=Exception("Connection refused")):
            health = await server.health_check()

            assert health.is_healthy is False
            assert "Health check error" in health.error_message


@pytest.mark.asyncio
class TestInference:
    """Test inference functionality."""

    async def test_generate_success(self, tmp_path):
        """Test successful text generation."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)
        server._is_running = True

        request = LLMRequest(prompt="Hello, world!", max_tokens=100)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Generated response text",
            "tokens_predicted": 50,
            "stop_reason": "stop",
        }

        with patch("requests.post", return_value=mock_response):
            response = await server.generate(request)

            assert response.text == "Generated response text"
            assert response.provider.value == "local"
            assert response.tokens_generated == 50
            assert response.finish_reason == "stop"
            assert response.latency_ms >= 0
            assert "model" in response.metadata
            assert "gpu_backend" in response.metadata

    async def test_generate_server_not_running(self, tmp_path):
        """Test generation when server not running."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        request = LLMRequest(prompt="test")

        with pytest.raises(RuntimeError, match="Server not running"):
            await server.generate(request)

    async def test_generate_http_error(self, tmp_path):
        """Test generation with HTTP error."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)
        server._is_running = True

        request = LLMRequest(prompt="test")

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="Generation failed: 500"):
                await server.generate(request)

    async def test_generate_request_exception(self, tmp_path):
        """Test generation with request exception."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)
        server._is_running = True

        request = LLMRequest(prompt="test")

        with patch("requests.post", side_effect=Exception("Timeout")):
            with pytest.raises(RuntimeError, match="Generation error"):
                await server.generate(request)


class TestServerStatus:
    """Test server status methods."""

    def test_is_running(self, tmp_path):
        """Test is_running method."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        assert server.is_running() is False

        server._is_running = True
        assert server.is_running() is True

    def test_is_model_loaded(self, tmp_path):
        """Test is_model_loaded method."""
        model_file = tmp_path / "model.gguf"
        model_file.touch()

        config = LocalLLMConfig(model_path=str(model_file))
        server = LocalLLMServer(config)

        assert server.is_model_loaded() is False

        server._model_loaded = True
        assert server.is_model_loaded() is True
