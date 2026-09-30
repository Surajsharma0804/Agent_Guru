"""Example usage of Ollama server integration.

This script demonstrates how to use the Ollama server with existing models
for local LLM inference.

Requirements:
- Ollama installed and running (ollama serve)
- The model named by OLLAMA_MODEL pulled (default:
  generation.DEFAULT_OLLAMA_MODEL)

Usage:
    python -m Agent_Guru.reasoning.llm.example_ollama_usage
"""

import asyncio
import contextlib

from Agent_Guru.reasoning.llm.models import LLMRequest
from Agent_Guru.reasoning.llm.ollama_server import OllamaServer


async def main() -> None:
    """Demonstrate Ollama server usage."""
    # Initialize Ollama server
    server = OllamaServer(host="127.0.0.1", port=11434)

    # Start server (check availability and list models)
    try:
        await server.start(timeout=5.0)
    except Exception:
        return

    # Health check
    await server.health_check()

    # Simple task with Mistral 7B (fast)
    simple_request = LLMRequest(
        prompt="What is 2+2? Answer in one sentence.",
        temperature=0.7,
        max_tokens=50,
    )

    with contextlib.suppress(Exception):
        await server.generate(simple_request)

    # Complex task with Qwen 14B (powerful)
    complex_request = LLMRequest(
        prompt="Explain the concept of recursion in programming with a simple example.",
        temperature=0.7,
        max_tokens=200,
    )

    with contextlib.suppress(Exception):
        await server.generate(complex_request)

    # Model selection based on complexity
    server.select_model_for_task("simple")
    server.select_model_for_task("complex")

    # Latency measurement
    with contextlib.suppress(Exception):
        await server.measure_latency(server.default_model, num_samples=5)

    # Stop server
    await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
