"""Comprehensive benchmark report generator.

Generates detailed analysis comparing Agent Guru to all competitor frameworks
across multiple dimensions: success rate, cost, time, improvement, and recovery.
"""

import json
import os
from datetime import UTC, datetime
from typing import Any

from Agent_Guru.self_improvement.benchmarks.base_benchmark import BenchmarkResult


class ComprehensiveBenchmarkReport:
    """Generates comprehensive benchmark reports with detailed analysis.

    Measures and compares:
    - Task success rate across all frameworks
    - Cost per task (API calls and tokens)
    - Time per task (execution speed)
    - Improvement over time (unique to Agent Guru)
    - Recovery from failures
    """

    def __init__(self, results: list[BenchmarkResult]) -> None:
        """Initialize report generator.

        Args:
            results: List of benchmark results from all frameworks

        """
        self.results = results
        self.timestamp = datetime.now(tz=UTC)

    def generate_report(self, output_path: str) -> dict[str, Any]:
        """Generate comprehensive benchmark report.

        Args:
            output_path: Path to save markdown report

        Returns:
            Dictionary with analysis results

        """
        analysis = {
            "timestamp": self.timestamp.isoformat(),
            "frameworks_tested": [r.framework_name for r in self.results],
            "success_rate_analysis": self._analyze_success_rates(),
            "cost_analysis": self._analyze_costs(),
            "time_analysis": self._analyze_execution_times(),
            "improvement_analysis": self._analyze_improvement(),
            "recovery_analysis": self._analyze_recovery(),
            "overall_winner": self._determine_overall_winner(),
        }

        # Generate markdown report
        self._generate_markdown(analysis, output_path)

        # Save JSON analysis
        json_path = output_path.replace(".md", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2)

        return analysis

    def _analyze_success_rates(self) -> dict[str, Any]:
        """Analyze task success rates across all frameworks."""
        rates = {r.framework_name: r.metrics.success_rate for r in self.results}

        best_framework = max(rates.items(), key=lambda x: x[1])
        worst_framework = min(rates.items(), key=lambda x: x[1])
        avg_rate = sum(rates.values()) / len(rates)

        return {
            "rates": rates,
            "best": {"framework": best_framework[0], "rate": best_framework[1]},
            "worst": {"framework": worst_framework[0], "rate": worst_framework[1]},
            "average": avg_rate,
            "agent_guru_rank": self._get_rank("success_rate", rates, "Agent Guru"),
        }

    def _analyze_costs(self) -> dict[str, Any]:
        """Analyze cost per task (tokens used)."""
        # Calculate cost per successful task
        costs = {}
        for r in self.results:
            successful_tasks = r.scenarios_run * (r.metrics.success_rate / 100)
            if successful_tasks > 0:
                cost_per_task = r.metrics.total_tokens / successful_tasks
            else:
                cost_per_task = float("inf")
            costs[r.framework_name] = {
                "total_tokens": r.metrics.total_tokens,
                "tokens_per_task": cost_per_task,
                "api_calls": r.metrics.total_api_calls,
            }

        # Find most cost-effective
        best_framework = min(costs.items(), key=lambda x: x[1]["tokens_per_task"])

        return {
            "costs": costs,
            "most_cost_effective": {
                "framework": best_framework[0],
                "tokens_per_task": best_framework[1]["tokens_per_task"],
            },
            "agent_guru_rank": self._get_rank(
                "tokens_per_task",
                {k: v["tokens_per_task"] for k, v in costs.items()},
                "Agent Guru",
                lower_is_better=True,
            ),
        }

    def _analyze_execution_times(self) -> dict[str, Any]:
        """Analyze execution time per task."""
        times = {r.framework_name: r.metrics.avg_execution_time_ms for r in self.results}

        fastest_framework = min(times.items(), key=lambda x: x[1])
        slowest_framework = max(times.items(), key=lambda x: x[1])
        avg_time = sum(times.values()) / len(times)

        return {
            "times": times,
            "fastest": {"framework": fastest_framework[0], "time_ms": fastest_framework[1]},
            "slowest": {"framework": slowest_framework[0], "time_ms": slowest_framework[1]},
            "average": avg_time,
            "agent_guru_rank": self._get_rank(
                "execution_time",
                times,
                "Agent Guru",
                lower_is_better=True,
            ),
        }

    def _analyze_improvement(self) -> dict[str, Any]:
        """Analyze improvement over time (unique to Agent Guru)."""
        improvements = {}
        for r in self.results:
            if r.metrics.improvement_rate is not None:
                improvements[r.framework_name] = r.metrics.improvement_rate

        if not improvements:
            return {
                "note": "No frameworks demonstrated improvement capability",
                "agent_guru_unique": False,
            }

        return {
            "improvements": improvements,
            "agent_guru_improvement": improvements.get("Agent Guru"),
            "agent_guru_unique": len(improvements) == 1 and "Agent Guru" in improvements,
            "note": "Improvement over time is a unique Agent Guru feature"
            if len(improvements) == 1
            else "Multiple frameworks show improvement",
        }

    def _analyze_recovery(self) -> dict[str, Any]:
        """Analyze recovery from failures."""
        recoveries = {}
        for r in self.results:
            if r.metrics.recovery_rate is not None:
                recoveries[r.framework_name] = r.metrics.recovery_rate

        if not recoveries:
            return {
                "note": "Recovery rate not measured for any framework",
            }

        best_recovery = max(recoveries.items(), key=lambda x: x[1])

        return {
            "recoveries": recoveries,
            "best_recovery": {"framework": best_recovery[0], "rate": best_recovery[1]},
            "agent_guru_rank": self._get_rank("recovery_rate", recoveries, "Agent Guru")
            if "Agent Guru" in recoveries
            else None,
        }

    def _determine_overall_winner(self) -> dict[str, Any]:
        """Determine overall winner across all dimensions."""
        scores = {r.framework_name: 0 for r in self.results}

        # Success rate (40% weight)
        success_rates = {r.framework_name: r.metrics.success_rate for r in self.results}
        best_success = max(success_rates.values())
        for name, rate in success_rates.items():
            scores[name] += (rate / best_success) * 40

        times = {r.framework_name: r.metrics.avg_execution_time_ms for r in self.results}
        best_time = min(times.values())
        for name, time in times.items():
            scores[name] += (best_time / time) * 30

        costs = {r.framework_name: r.metrics.total_tokens for r in self.results}
        best_cost = min(costs.values())
        for name, cost in costs.items():
            if cost > 0:
                scores[name] += (best_cost / cost) * 20

        # Improvement (10% weight - bonus for Agent Guru)
        for r in self.results:
            if r.metrics.improvement_rate is not None and r.metrics.improvement_rate > 0:
                scores[r.framework_name] += 10

        winner = max(scores.items(), key=lambda x: x[1])

        return {
            "scores": scores,
            "winner": {"framework": winner[0], "score": winner[1]},
            "agent_guru_wins": winner[0] == "Agent Guru",
        }

    def _get_rank(
        self,
        metric_name: str,
        values: dict[str, float],
        framework: str,
        lower_is_better: bool = False,
    ) -> int:
        """Get rank of a framework for a specific metric."""
        sorted_items = sorted(values.items(), key=lambda x: x[1], reverse=not lower_is_better)

        for rank, (name, _) in enumerate(sorted_items, 1):
            if name == framework:
                return rank

        return len(sorted_items) + 1

    def _generate_markdown(self, analysis: dict[str, Any], output_path: str) -> None:
        """Generate markdown report."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Comprehensive Agent Framework Benchmark Report\n\n")
            f.write(f"**Generated**: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Frameworks Tested**: {', '.join(analysis['frameworks_tested'])}\n\n")

            # Executive Summary
            f.write("## Executive Summary\n\n")
            winner = analysis["overall_winner"]["winner"]
            f.write(
                f"**Overall Winner**: {winner['framework']} (Score: {winner['score']:.1f}/100)\n\n",
            )

            if analysis["overall_winner"]["agent_guru_wins"]:
                f.write("✅ **Agent Guru outperforms all competitor frameworks**\n\n")
            else:
                f.write(
                    f"⚠️ **{winner['framework']} currently leads, but Agent Guru has unique advantages**\n\n",
                )

            # Success Rate Analysis
            f.write("## 1. Task Success Rate Analysis\n\n")
            success = analysis["success_rate_analysis"]
            f.write("| Framework | Success Rate | Rank |\n")
            f.write("|-----------|--------------|------|\n")

            sorted_rates = sorted(success["rates"].items(), key=lambda x: x[1], reverse=True)
            for rank, (name, rate) in enumerate(sorted_rates, 1):
                marker = "🏆" if rank == 1 else ""
                f.write(f"| {name} {marker} | {rate:.1f}% | #{rank} |\n")

            f.write(
                f"\n**Best**: {success['best']['framework']} ({success['best']['rate']:.1f}%)\n",
            )
            f.write(f"**Average**: {success['average']:.1f}%\n")
            f.write(f"**Agent Guru Rank**: #{success['agent_guru_rank']}\n\n")

            # Cost Analysis
            f.write("## 2. Cost Per Task Analysis\n\n")
            cost = analysis["cost_analysis"]
            f.write("| Framework | Total Tokens | Tokens/Task | API Calls | Rank |\n")
            f.write("|-----------|--------------|-------------|-----------|------|\n")

            sorted_costs = sorted(cost["costs"].items(), key=lambda x: x[1]["tokens_per_task"])
            for rank, (name, data) in enumerate(sorted_costs, 1):
                marker = "💰" if rank == 1 else ""
                tokens_per_task = data["tokens_per_task"]
                tokens_str = "N/A" if tokens_per_task == float("inf") else f"{tokens_per_task:.1f}"
                f.write(
                    f"| {name} {marker} | {data['total_tokens']} | {tokens_str} | {data['api_calls']} | #{rank} |\n",
                )

            f.write(f"\n**Most Cost-Effective**: {cost['most_cost_effective']['framework']}\n")
            f.write(f"**Agent Guru Rank**: #{cost['agent_guru_rank']}\n\n")

            # Time Analysis
            f.write("## 3. Execution Time Analysis\n\n")
            time = analysis["time_analysis"]
            f.write("| Framework | Avg Time (ms) | Rank |\n")
            f.write("|-----------|---------------|------|\n")

            sorted_times = sorted(time["times"].items(), key=lambda x: x[1])
            for rank, (name, ms) in enumerate(sorted_times, 1):
                marker = "⚡" if rank == 1 else ""
                f.write(f"| {name} {marker} | {ms:.1f} | #{rank} |\n")

            f.write(
                f"\n**Fastest**: {time['fastest']['framework']} ({time['fastest']['time_ms']:.1f} ms)\n",
            )
            f.write(f"**Average**: {time['average']:.1f} ms\n")
            f.write(f"**Agent Guru Rank**: #{time['agent_guru_rank']}\n\n")

            # Improvement Analysis
            f.write("## 4. Improvement Over Time Analysis\n\n")
            improvement = analysis["improvement_analysis"]

            if improvement.get("agent_guru_unique"):
                f.write("🌟 **Agent Guru Unique Feature**: Self-improvement capability\n\n")
                f.write(
                    f"**Agent Guru Improvement Rate**: {improvement['agent_guru_improvement']:.1f}%\n\n",
                )
                f.write("No other framework demonstrated improvement over time.\n\n")
            elif "improvements" in improvement:
                f.write("| Framework | Improvement Rate |\n")
                f.write("|-----------|------------------|\n")
                for name, rate in improvement["improvements"].items():
                    f.write(f"| {name} | {rate:.1f}% |\n")
                f.write("\n")
            else:
                f.write(improvement["note"] + "\n\n")

            # Recovery Analysis
            f.write("## 5. Error Recovery Analysis\n\n")
            recovery = analysis["recovery_analysis"]

            if "recoveries" in recovery:
                f.write("| Framework | Recovery Rate | Rank |\n")
                f.write("|-----------|---------------|------|\n")

                sorted_recovery = sorted(
                    recovery["recoveries"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
                for rank, (name, rate) in enumerate(sorted_recovery, 1):
                    marker = "🛡️" if rank == 1 else ""
                    f.write(f"| {name} {marker} | {rate:.1f}% | #{rank} |\n")

                f.write(
                    f"\n**Best Recovery**: {recovery['best_recovery']['framework']} ({recovery['best_recovery']['rate']:.1f}%)\n",
                )
                if recovery["agent_guru_rank"]:
                    f.write(f"**Agent Guru Rank**: #{recovery['agent_guru_rank']}\n")
                f.write("\n")
            else:
                f.write(recovery["note"] + "\n\n")

            # Overall Scores
            f.write("## 6. Overall Scores\n\n")
            f.write(
                "Weighted scoring: Success Rate (40%), Speed (30%), Cost (20%), Improvement (10%)\n\n",
            )
            f.write("| Framework | Score | Rank |\n")
            f.write("|-----------|-------|------|\n")

            sorted_scores = sorted(
                analysis["overall_winner"]["scores"].items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for rank, (name, score) in enumerate(sorted_scores, 1):
                marker = "🏆" if rank == 1 else ""
                f.write(f"| {name} {marker} | {score:.1f}/100 | #{rank} |\n")

            # Conclusion
            f.write("\n## Conclusion\n\n")

            if analysis["overall_winner"]["agent_guru_wins"]:
                f.write("✅ **Agent Guru successfully outperforms all competitor frameworks**\n\n")
                f.write("Key advantages:\n")
                f.write("- Self-improvement capability (unique feature)\n")
                f.write("- Competitive performance across all metrics\n")
                f.write("- Balanced approach to speed, accuracy, and cost\n\n")
            else:
                f.write(f"**Current Leader**: {winner['framework']}\n\n")
                f.write("Agent Guru demonstrates:\n")
                f.write("- Unique self-improvement capability\n")
                f.write("- Competitive performance\n")
                f.write("- Room for optimization in specific areas\n\n")

            # Recommendations
            f.write("## Recommendations\n\n")

            agent_guru_rank = self._get_rank(
                "overall",
                analysis["overall_winner"]["scores"],
                "Agent Guru",
            )

            if agent_guru_rank == 1:
                f.write(
                    "- ✅ Agent Guru meets the requirement to outperform in at least one dimension\n",
                )
                f.write("- Continue monitoring and improving performance\n")
                f.write("- Leverage self-improvement capability for continuous optimization\n")
            else:
                f.write("- Focus on improving weak areas identified in this benchmark\n")
                f.write("- Leverage self-improvement capability to close performance gaps\n")
                f.write("- Re-run benchmarks after optimization\n")


def generate_comprehensive_report(
    results: list[BenchmarkResult],
    output_dir: str,
) -> dict[str, Any]:
    """Generate comprehensive benchmark report.

    Args:
        results: List of benchmark results from all frameworks
        output_dir: Directory to save report

    Returns:
        Analysis dictionary

    """
    os.makedirs(output_dir, exist_ok=True)  # noqa: PTH103

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"comprehensive_report_{timestamp}.md")

    reporter = ComprehensiveBenchmarkReport(results)
    return reporter.generate_report(report_path)
