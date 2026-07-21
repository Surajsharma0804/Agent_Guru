"""Local LLM Server using llama.cpp.

Manages llama.cpp server process with GPU acceleration for local inference.
Provides health checks, model loading, and inference endpoints.

Performance Targets:
- Inference latency: <400ms for 512 tokens (95th percentile)
- GPU utilization: >80% during inference
- Model loading: <30 seconds
- Health check: <50ms

Requirements: 4.2, 4.5
"""

import asyncio
import concurrent.futures
import subprocess  # nosec B404
import time
from pathlib import Path

import requests

from Agent_Guru.reasoning.llm.models import (
    GPUBackend,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LocalLLMConfig,
    ServerHealth,
)


class LocalLLMServer:
    """Local LLM server using llama.cpp with GPU acceleration.

    Time Complexity: O(1) for health checks, O(n) for inference (n = tokens)
    Space Complexity: O(model_size) for model loading

    Example:
        >>> config = LocalLLMConfig(
        ...     model_path="models/llama-3.2-8b-q4_k_m.gguf",
        ...     gpu_backend=GPUBackend.CUDA,
        ...     n_gpu_layers=35
        ... )
        >>> server = LocalLLMServer(config)
        >>> await server.start()
        >>> health = await server.health_check()
        >>> print(f"Server healthy: {health.is_healthy}")

    """

    def __init__(self, config: LocalLLMConfig) -> None:
        """Initialize local LLM server.

        Args:
            config: Server configuration

        Raises:
            ValueError: If configuration is invalid

        """
        self.config = config
        self.process: subprocess.Popen | None = None
        self._is_running = False
        self._model_loaded = False
        self._base_url = f"http://{config.host}:{config.port}"

        # FIX: previously every health_check()/generate() call created a
        # brand-new `ThreadPoolExecutor(max_workers=1)` via
        # `with concurrent.futures.ThreadPoolExecutor(...) as pool:` and
        # tore it down immediately after — real, avoidable thread-spawn
        # overhead on every single call, including every health-check poll
        # (this class's own `start()` polls health_check() in a loop every
        # 0.5s until the server is ready, potentially dozens of times).
        # One executor, built once, reused for the lifetime of this
        # instance — same fix already applied to the sibling OllamaServer
        # class for consistency.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    async def start(self, timeout: float = 60.0) -> None:
        """Start llama.cpp server process.

        Time Complexity: O(1) for process start, O(n) for model loading
        Space Complexity: O(model_size)

        Args:
            timeout: Maximum time to wait for server startup (seconds)

        Raises:
            RuntimeError: If server fails to start
            TimeoutError: If startup exceeds timeout

        """
        if self._is_running:
            return

        # FIX: _build_server_command() -> _detect_server_binary() ->
        # _is_command_available() runs up to 3 synchronous
        # `subprocess.run(..., timeout=1)` calls directly inside this
        # `async def`, unwrapped — blocking the event loop for up to ~3
        # seconds while probing for the llama.cpp binary (same bug class
        # as the subprocess.run-inside-async-def issue already found and
        # fixed elsewhere in reasoning/tools/system/*.py). Offloaded to a
        # worker thread so probing for the binary can't stall any other
        # concurrently-running asyncio task.
        cmd = await asyncio.to_thread(self._build_server_command)

        # Start server process
        self.process = subprocess.Popen(  # nosec B603  # noqa: S603
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # FIX: was `time.time()` — see OllamaServer.start() for why
        # `time.monotonic()` is the correct choice for measuring elapsed
        # durations against a timeout (immune to wall-clock adjustments).
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            health = await self.health_check()
            if health.is_healthy and health.model_loaded:
                self._is_running = True
                self._model_loaded = True
                return

            await asyncio.sleep(0.5)

        # Timeout - kill process
        if self.process:
            self.process.kill()
        msg = f"Server failed to start within {timeout}s"
        raise TimeoutError(msg)

    def _build_server_command(self) -> list:
        """Build llama.cpp server command with GPU acceleration.

        Returns:
            Command list for subprocess

        """
        # Detect llama.cpp server binary
        server_binary = self._detect_server_binary()

        cmd = [
            server_binary,
            "-m",
            self.config.model_path,
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
            "-c",
            str(self.config.n_ctx),
            "-t",
            str(self.config.n_threads),
        ]

        # Add GPU acceleration flags
        if self.config.gpu_backend in (GPUBackend.CUDA, GPUBackend.METAL):
            cmd.extend(["-ngl", str(self.config.n_gpu_layers)])

        return cmd

    def _detect_server_binary(self) -> str:
        """Detect llama.cpp server binary path.

        Returns:
            Path to server binary

        Raises:
            FileNotFoundError: If binary not found

        """
        # Common binary names
        binary_names = ["llama-server", "server", "llama.cpp-server"]

        # Check in PATH
        for name in binary_names:
            if self._is_command_available(name):
                return name

        # Check common installation paths
        common_paths = [
            "/usr/local/bin",
            "/usr/bin",
            str(Path.home() / ".local" / "bin"),
            str(Path.home() / "llama.cpp"),
        ]

        for path in common_paths:
            for name in binary_names:
                full_path = Path(path) / name
                if full_path.exists():
                    return str(full_path)

        msg = (
            "llama.cpp server binary not found. "
            "Please install llama.cpp and ensure server binary is in PATH."
        )
        raise FileNotFoundError(
            msg,
        )

    @staticmethod
    def _is_command_available(command: str) -> bool:
        """Check if command is available in PATH."""
        try:
            subprocess.run(  # nosec B603  # noqa: S603
                [command, "--version"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    async def health_check(self) -> ServerHealth:
        """Check server health and model availability.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Server health status

        Requirements: 4.2

        """
        # FIX: was time.time() — see start() above.
        start_time = time.monotonic()

        try:
            # Check if process is running
            if not self.process or self.process.poll() is not None:
                return ServerHealth(
                    is_healthy=False,
                    model_loaded=False,
                    gpu_available=False,
                    gpu_backend=None,
                    latency_ms=None,
                    error_message="Server process not running",
                )

            # Run blocking HTTP call in thread pool to avoid blocking event loop.
            # FIX: reuses self._executor (built once in __init__) instead of
            # creating and tearing down a new ThreadPoolExecutor on every call
            # — see __init__ FIX note.
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self._executor,
                lambda: requests.get(f"{self._base_url}/health", timeout=1.0),  # noqa: ASYNC210
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                return ServerHealth(
                    is_healthy=True,
                    model_loaded=data.get("model_loaded", False),
                    gpu_available=data.get("gpu", False),
                    gpu_backend=self.config.gpu_backend if data.get("gpu", False) else None,
                    latency_ms=latency_ms,
                )
            return ServerHealth(
                is_healthy=False,
                model_loaded=False,
                gpu_available=False,
                gpu_backend=None,
                latency_ms=latency_ms,
                error_message=f"Health check failed: {response.status_code}",
            )

        except requests.RequestException as e:
            return ServerHealth(
                is_healthy=False,
                model_loaded=False,
                gpu_available=False,
                gpu_backend=None,
                latency_ms=None,
                error_message=f"Health check error: {e!s}",
            )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text using local LLM.

        Time Complexity: O(n) where n = tokens generated
        Space Complexity: O(n)

        Args:
            request: LLM request with prompt and parameters

        Returns:
            LLM response with generated text

        Raises:
            RuntimeError: If server not running or generation fails

        Requirements: 4.2, 10.1

        """
        if not self._is_running:
            msg = "Server not running. Call start() first."
            raise RuntimeError(msg)

        # FIX: was time.time() — see start() above.
        start_time = time.monotonic()

        try:
            # Build request payload
            payload = {
                "prompt": request.prompt,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "n_predict": request.max_tokens,
                "stop": request.stop_sequences,
                "stream": request.stream,
            }

            # Run blocking HTTP call in thread pool to avoid blocking event loop.
            # FIX: reuses self._executor — see __init__ FIX note.
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self._executor,
                lambda: requests.post(  # noqa: ASYNC210
                    f"{self._base_url}/completion",
                    json=payload,
                    timeout=10.0,
                ),
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                return LLMResponse(
                    text=data.get("content", ""),
                    provider=LLMProvider.LOCAL,
                    latency_ms=latency_ms,
                    tokens_generated=data.get("tokens_predicted", 0),
                    finish_reason=data.get("stop_reason", "stop"),
                    metadata={
                        "model": self.config.model_path,
                        "gpu_backend": self.config.gpu_backend.value,
                    },
                )
            msg = f"Generation failed: {response.status_code} - {response.text}"
            raise RuntimeError(msg)

        except requests.RequestException as e:
            msg = f"Generation error: {e!s}"
            raise RuntimeError(msg) from e

    async def stop(self) -> None:
        """Stop llama.cpp server process.

        Time Complexity: O(1)
        Space Complexity: O(1)
        """
        if self.process:
            self.process.terminate()
            try:
                # FIX: `self.process.wait(timeout=5.0)` is a blocking
                # synchronous call — was executed directly inside this
                # `async def`, able to stall the event loop for up to 5
                # seconds waiting for the llama.cpp process to exit. Same
                # blocking-call-in-async-def bug class as the subprocess
                # fixes elsewhere in this codebase. Offloaded via
                # asyncio.to_thread so a slow-to-terminate process can't
                # freeze anything else running concurrently.
                await asyncio.to_thread(self.process.wait, timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()

        self._is_running = False
        self._model_loaded = False
        self._executor.shutdown(wait=False)

    def is_running(self) -> bool:
        """Check if server is running."""
        return self._is_running

    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model_loaded
