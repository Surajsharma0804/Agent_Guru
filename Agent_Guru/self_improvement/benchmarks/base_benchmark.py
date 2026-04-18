"""
Base benchmark framework for comparing agent frameworks.

Provides common infrastructure for measuring and comparing performance
across different agent implementations.
"""

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import psutil

_logger = logging.getLogger(__name__)


class ScenarioType(Enum):
    """Types of test scenarios."""
    SIMPLE = "simple"
    COMPLEX = "complex"
    TOOL_USAGE = "tool_usage"
    ERROR_RECOVERY = "error_recovery"
    LEARNING = "learning"


@dataclass
class TestScenario:
    """A test scenario for benchmarking."""
    scenario_id: str
    name: str
    description: str
    scenario_type: ScenarioType
    input_data: dict[str, Any]
    expected_output: Optional[Any] = None
    success_criteria: Optional[Callable[[Any], bool]] = None
    difficulty: int = 1  # 1-5 scale


@dataclass
class BenchmarkMetrics:
    """Metrics collected during benchmark execution."""
    success_rate: float  # Percentage of successful tasks
    avg_execution_time_ms: float  # Average time per task
    total_api_calls: int  # Total API calls made
    total_tokens: int  # Total tokens used
    avg_memory_mb: float  # Average memory usage
    avg_cpu_percent: float  # Average CPU usage
    improvement_rate: Optional[float] = None  # Improvement over time (Agent Guru only)
    recovery_rate: Optional[float] = None  # Recovery from failures

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "success_rate": self.success_rate,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "total_api_calls": self.total_api_calls,
            "total_tokens": self.total_tokens,
            "avg_memory_mb": self.avg_memory_mb,
            "avg_cpu_percent": self.avg_cpu_percent,
            "improvement_rate": self.improvement_rate,
            "recovery_rate": self.recovery_rate,
        }


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    framework_name: str
    timestamp: datetime
    scenarios_run: int
    metrics: BenchmarkMetrics
    scenario_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "framework_name": self.framework_name,
            "timestamp": self.timestamp.isoformat(),
            "scenarios_run": self.scenarios_run,
            "metrics": self.metrics.to_dict(),
            "scenario_results": self.scenario_results,
            "errors": self.errors,
        }

    def to_json(self, filepath: str) -> None:
        """Save result to JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)


class BaseBenchmark:
    """
    Base class for agent framework benchmarks.

    Provides common infrastructure for measuring performance metrics
    across different agent implementations.
    """

    def __init__(self, framework_name: str):
        """
        Initialize benchmark.

        Args:
            framework_name: Name of the framework being benchmarked
        """
        self.framework_name = framework_name
        self.process = psutil.Process(os.getpid())
        self._reset_metrics()

    def _reset_metrics(self) -> None:
        """Reset metrics tracking."""
        self.successes = 0
        self.failures = 0
        self.execution_times: list[float] = []
        self.api_calls = 0
        self.tokens_used = 0
        self.memory_samples: list[float] = []
        self.cpu_samples: list[float] = []
        self.scenario_results: list[dict[str, Any]] = []
        self.errors: list[str] = []

    def run_benchmark(
        self,
        scenarios: list[TestScenario],
        warmup_runs: int = 0
    ) -> BenchmarkResult:
        """
        Run benchmark on provided scenarios.

        Args:
            scenarios: List of test scenarios to run
            warmup_runs: Number of warmup runs before measurement

        Returns:
            BenchmarkResult with collected metrics
        """
        self._reset_metrics()

        # Warmup runs (not measured)
        if warmup_runs > 0:
            print(f"Running {warmup_runs} warmup iterations...")
            for i in range(warmup_runs):
                scenario = scenarios[i % len(scenarios)]
                try:
                    self.execute_scenario(scenario)
                except Exception as exc:  # noqa: BLE001
                    _logger.debug("Warmup iteration %d skipped: %s", i, exc)  # Ignore warmup errors

        # Actual benchmark runs
        print(f"Running benchmark on {len(scenarios)} scenarios...")
        for i, scenario in enumerate(scenarios):
            print(f"  Scenario {i+1}/{len(scenarios)}: {scenario.name}")

            try:
                # Measure resources before
                mem_before = self.process.memory_info().rss / 1024 / 1024  # MB
                cpu_before = self.process.cpu_percent()

                # Execute scenario
                start_time = time.perf_counter()
                result = self.execute_scenario(scenario)
                end_time = time.perf_counter()

                # Measure resources after
                mem_after = self.process.memory_info().rss / 1024 / 1024  # MB
                cpu_after = self.process.cpu_percent()

                # Calculate metrics
                execution_time_ms = (end_time - start_time) * 1000
                self.execution_times.append(execution_time_ms)
                self.memory_samples.append((mem_before + mem_after) / 2)
                self.cpu_samples.append((cpu_before + cpu_after) / 2)

                # Check success
                success = self._check_success(scenario, result)
                if success:
                    self.successes += 1
                else:
                    self.failures += 1

                # Record scenario result
                self.scenario_results.append({
                    "scenario_id": scenario.scenario_id,
                    "name": scenario.name,
                    "success": success,
                    "execution_time_ms": execution_time_ms,
                    "result": str(result)[:200],  # Truncate long results
                })

            except Exception as e:
                self.failures += 1
                error_msg = f"Scenario {scenario.name} failed: {str(e)}"
                self.errors.append(error_msg)
                print(f"    ERROR: {error_msg}")

                self.scenario_results.append({
                    "scenario_id": scenario.scenario_id,
                    "name": scenario.name,
                    "success": False,
                    "error": str(e),
                })

        # Calculate final metrics
        total_tasks = self.successes + self.failures
        success_rate = (self.successes / total_tasks * 100) if total_tasks > 0 else 0.0
        avg_time = sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0.0
        avg_memory = sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0.0
        avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0

        metrics = BenchmarkMetrics(
            success_rate=success_rate,
            avg_execution_time_ms=avg_time,
            total_api_calls=self.api_calls,
            total_tokens=self.tokens_used,
            avg_memory_mb=avg_memory,
            avg_cpu_percent=avg_cpu,
        )

        return BenchmarkResult(
            framework_name=self.framework_name,
            timestamp=datetime.now(tz=timezone.utc),
            scenarios_run=len(scenarios),
            metrics=metrics,
            scenario_results=self.scenario_results,
            errors=self.errors,
        )

    def execute_scenario(self, scenario: TestScenario) -> Any:
        """
        Execute a single test scenario.

        Must be implemented by subclasses.

        Args:
            scenario: Test scenario to execute

        Returns:
            Result of scenario execution
        """
        raise NotImplementedError("Subclasses must implement execute_scenario")

    def _check_success(self, scenario: TestScenario, result: Any) -> bool:
        """
        Check if scenario execution was successful.

        Args:
            scenario: Test scenario
            result: Execution result

        Returns:
            True if successful, False otherwise
        """
        # Use custom success criteria if provided
        if scenario.success_criteria:
            try:
                return scenario.success_criteria(result)
            except Exception as e:
                return False

        # Use expected output if provided
        if scenario.expected_output is not None:
            return result == scenario.expected_output

        # Default: non-None result is success
        return result is not None

    def track_api_call(self, tokens: int = 0) -> None:
        """
        Track an API call.

        Args:
            tokens: Number of tokens used in the call
        """
        self.api_calls += 1
        self.tokens_used += tokens

    def generate_markdown_report(
        self,
        results: list[BenchmarkResult],
        output_path: str
    ) -> None:
        """
        Generate markdown comparison report.

        Args:
            results: List of benchmark results to compare
            output_path: Path to save markdown report
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Agent Framework Benchmark Results\n\n")
            f.write(f"Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Summary table
            f.write("## Summary\n\n")
            f.write("| Framework | Success Rate | Avg Time (ms) | API Calls | Tokens | Memory (MB) | CPU (%) |\n")
            f.write("|-----------|--------------|---------------|-----------|--------|-------------|----------|\n")

            for result in results:
                m = result.metrics
                f.write(f"| {result.framework_name} | {m.success_rate:.1f}% | {m.avg_execution_time_ms:.1f} | "
                       f"{m.total_api_calls} | {m.total_tokens} | {m.avg_memory_mb:.1f} | {m.avg_cpu_percent:.1f} |\n")

            f.write("\n")

            # Detailed results per framework
            f.write("## Detailed Results\n\n")
            for result in results:
                f.write(f"### {result.framework_name}\n\n")
                f.write(f"- **Scenarios Run**: {result.scenarios_run}\n")
                f.write(f"- **Success Rate**: {result.metrics.success_rate:.1f}%\n")
                f.write(f"- **Average Execution Time**: {result.metrics.avg_execution_time_ms:.1f} ms\n")
                f.write(f"- **Total API Calls**: {result.metrics.total_api_calls}\n")
                f.write(f"- **Total Tokens**: {result.metrics.total_tokens}\n")
                f.write(f"- **Average Memory**: {result.metrics.avg_memory_mb:.1f} MB\n")
                f.write(f"- **Average CPU**: {result.metrics.avg_cpu_percent:.1f}%\n")

                if result.metrics.improvement_rate is not None:
                    f.write(f"- **Improvement Rate**: {result.metrics.improvement_rate:.1f}%\n")
                if result.metrics.recovery_rate is not None:
                    f.write(f"- **Recovery Rate**: {result.metrics.recovery_rate:.1f}%\n")

                if result.errors:
                    f.write(f"\n**Errors**: {len(result.errors)}\n")
                    for error in result.errors[:5]:  # Show first 5 errors
                        f.write(f"- {error}\n")

                f.write("\n")

            # Winner analysis
            f.write("## Analysis\n\n")

            # Find best in each category
            best_success = max(results, key=lambda r: r.metrics.success_rate)
            best_speed = min(results, key=lambda r: r.metrics.avg_execution_time_ms)
            best_cost = min(results, key=lambda r: r.metrics.total_tokens)

            f.write(f"- **Best Success Rate**: {best_success.framework_name} ({best_success.metrics.success_rate:.1f}%)\n")
            f.write(f"- **Fastest**: {best_speed.framework_name} ({best_speed.metrics.avg_execution_time_ms:.1f} ms)\n")
            f.write(f"- **Most Cost-Effective**: {best_cost.framework_name} ({best_cost.metrics.total_tokens} tokens)\n")

            # Check for Agent Guru improvement
            agent_guru_result = next((r for r in results if "Agent Guru" in r.framework_name), None)
            if agent_guru_result and agent_guru_result.metrics.improvement_rate:
                f.write(f"\n**Agent Guru Unique Feature**: {agent_guru_result.metrics.improvement_rate:.1f}% improvement over time\n")
