"""
Example usage of Ollama server integration.

This script demonstrates how to use the Ollama server with existing models
for local LLM inference.

Requirements:
- Ollama installed and running (ollama serve)
- Models downloaded: qwen2.5:14b-instruct, mistral:7b-instruct

Usage:
    python -m Agent_Guru.reasoning.llm.example_ollama_usage
"""

import asyncio

from Agent_Guru.reasoning.llm.models import LLMRequest
from Agent_Guru.reasoning.llm.ollama_server import OllamaServer


async def main():
    """Demonstrate Ollama server usage."""

    print("=" * 60)
    print("Ollama Server Integration Example")
    print("=" * 60)

    # Initialize Ollama server
    print("\n1. Initializing Ollama server...")
    server = OllamaServer(
        host="127.0.0.1",
        port=11434,
        default_model="mistral:7b-instruct",
    )

    # Start server (check availability and list models)
    print("2. Checking Ollama availability...")
    try:
        await server.start(timeout=5.0)
        print("   ✓ Ollama server is running")
        print(f"   ✓ Available models: {server.get_available_models()}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("\nMake sure Ollama is running: ollama serve")
        return

    # Health check
    print("\n3. Performing health check...")
    health = await server.health_check()
    print(f"   - Healthy: {health.is_healthy}")
    print(f"   - Models loaded: {health.model_loaded}")
    print(f"   - GPU available: {health.gpu_available}")
    print(f"   - Latency: {health.latency_ms:.2f}ms")

    # Simple task with Mistral 7B (fast)
    print("\n4. Testing simple task with Mistral 7B...")
    simple_request = LLMRequest(
        prompt="What is 2+2? Answer in one sentence.",
        temperature=0.7,
        max_tokens=50,
    )

    try:
        response = await server.generate(simple_request, model="mistral:7b-instruct")
        print(f"   - Response: {response.text}")
        print(f"   - Latency: {response.latency_ms:.2f}ms")
        print(f"   - Tokens: {response.tokens_generated}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Complex task with Qwen 14B (powerful)
    print("\n5. Testing complex task with Qwen 14B...")
    complex_request = LLMRequest(
        prompt="Explain the concept of recursion in programming with a simple example.",
        temperature=0.7,
        max_tokens=200,
    )

    try:
        response = await server.generate(complex_request, model="qwen2.5:14b-instruct")
        print(f"   - Response: {response.text[:200]}...")
        print(f"   - Latency: {response.latency_ms:.2f}ms")
        print(f"   - Tokens: {response.tokens_generated}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Model selection based on complexity
    print("\n6. Testing intelligent model selection...")
    simple_model = server.select_model_for_task("simple")
    complex_model = server.select_model_for_task("complex")
    print(f"   - Simple tasks use: {simple_model}")
    print(f"   - Complex tasks use: {complex_model}")

    # Latency measurement
    print("\n7. Measuring latency for Mistral 7B...")
    try:
        stats = await server.measure_latency("mistral:7b-instruct", num_samples=5)
        print(f"   - Mean latency: {stats['mean']:.2f}ms")
        print(f"   - P50 latency: {stats['p50']:.2f}ms")
        print(f"   - P95 latency: {stats['p95']:.2f}ms")
        print(f"   - P99 latency: {stats['p99']:.2f}ms")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Stop server
    print("\n8. Stopping server...")
    await server.stop()
    print("   ✓ Server stopped")

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
