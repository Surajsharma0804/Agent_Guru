"""
Benchmark suite for comparing Agent Guru self-improvement engine to other frameworks.

This module provides comprehensive benchmarking capabilities to compare Agent Guru's
self-improvement engine against LangChain, CrewAI, AutoGen, and AutoGPT.

Metrics measured:
- Task success rate (%)
- Average execution time per task (ms)
- Cost per task (API calls, tokens)
- Improvement over time (unique to Agent Guru)
- Recovery from failures (%)
- Memory usage (MB)
- CPU usage (%)
"""

from Agent_Guru.self_improvement.benchmarks.base_benchmark import (
    BaseBenchmark,
    BenchmarkResult,
    BenchmarkMetrics,
    TestScenario,
)
from Agent_Guru.self_improvement.benchmarks.test_scenarios import (
    get_all_scenarios,
    get_simple_scenarios,
    get_complex_scenarios,
    get_tool_usage_scenarios,
    get_error_recovery_scenarios,
    get_learning_scenarios,
)

__all__ = [
    "BaseBenchmark",
    "BenchmarkResult",
    "BenchmarkMetrics",
    "TestScenario",
    "get_all_scenarios",
    "get_simple_scenarios",
    "get_complex_scenarios",
    "get_tool_usage_scenarios",
    "get_error_recovery_scenarios",
    "get_learning_scenarios",
]
