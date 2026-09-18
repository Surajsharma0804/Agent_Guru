"""Main benchmark runner script.

Runs benchmarks comparing Agent Guru to all competitor frameworks and generates reports.
"""

import argparse
import os
from datetime import UTC, datetime

from Agent_Guru.self_improvement.benchmarks.agent_guru_benchmark import create_agent_guru_benchmark
from Agent_Guru.self_improvement.benchmarks.autogen_benchmark import create_autogen_benchmark
from Agent_Guru.self_improvement.benchmarks.autogpt_benchmark import create_autogpt_benchmark
from Agent_Guru.self_improvement.benchmarks.base_benchmark import BenchmarkResult
from Agent_Guru.self_improvement.benchmarks.comprehensive_report import (
    generate_comprehensive_report,
)
from Agent_Guru.self_improvement.benchmarks.crewai_benchmark import create_crewai_benchmark
from Agent_Guru.self_improvement.benchmarks.langchain_benchmark import create_langchain_benchmark
from Agent_Guru.self_improvement.benchmarks.test_scenarios import (
    get_all_scenarios,
    get_complex_scenarios,
    get_error_recovery_scenarios,
    get_learning_scenarios,
    get_simple_scenarios,
    get_tool_usage_scenarios,
)


def run_all_benchmarks(
    output_dir: str = "Agent_Guru/self_improvement/benchmarks/results",
    scenario_type: str = "all",
    warmup_runs: int = 0,
) -> list[BenchmarkResult]:
    """Run benchmarks for all frameworks.

    Args:
        output_dir: Directory to save results
        scenario_type: Type of scenarios to run (all, simple, complex, etc.)
        warmup_runs: Number of warmup runs before measurement

    Returns:
        List of benchmark results

    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)  # noqa: PTH103

    # Get scenarios
    if scenario_type == "all":
        scenarios = get_all_scenarios()
    elif scenario_type == "simple":
        scenarios = get_simple_scenarios()
    elif scenario_type == "complex":
        scenarios = get_complex_scenarios()
    elif scenario_type == "tool":
        scenarios = get_tool_usage_scenarios()
    elif scenario_type == "error":
        scenarios = get_error_recovery_scenarios()
    elif scenario_type == "learning":
        scenarios = get_learning_scenarios()
    else:
        msg = f"Unknown scenario type: {scenario_type}"
        raise ValueError(msg)

    results = []
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")

    # Run Agent Guru benchmark
    agent_guru = create_agent_guru_benchmark()
    agent_guru_result = agent_guru.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(agent_guru_result)

    # Save Agent Guru results
    agent_guru_result.to_json(os.path.join(output_dir, f"agent_guru_{timestamp}.json"))
    if agent_guru_result.metrics.improvement_rate is not None:
        print(f"Agent Guru improvement rate: {agent_guru_result.metrics.improvement_rate:.1f}%")
    if agent_guru_result.metrics.recovery_rate is not None:
        print(f"Agent Guru recovery rate: {agent_guru_result.metrics.recovery_rate:.1f}%")

    # Run LangChain benchmark
    langchain = create_langchain_benchmark()
    langchain_result = langchain.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(langchain_result)

    # Save LangChain results
    langchain_result.to_json(os.path.join(output_dir, f"langchain_{timestamp}.json"))

    # Run CrewAI benchmark
    crewai = create_crewai_benchmark()
    crewai_result = crewai.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(crewai_result)

    # Save CrewAI results
    crewai_result.to_json(os.path.join(output_dir, f"crewai_{timestamp}.json"))

    # Run AutoGen benchmark
    autogen = create_autogen_benchmark()
    autogen_result = autogen.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(autogen_result)

    # Save AutoGen results
    autogen_result.to_json(os.path.join(output_dir, f"autogen_{timestamp}.json"))

    # Run AutoGPT benchmark
    autogpt = create_autogpt_benchmark()
    autogpt_result = autogpt.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(autogpt_result)

    # Save AutoGPT results
    autogpt_result.to_json(os.path.join(output_dir, f"autogpt_{timestamp}.json"))

    # Generate comparison report

    # Generate comprehensive report with all metrics
    analysis = generate_comprehensive_report(results, output_dir)

    # Also generate simple markdown report
    report_path = os.path.join(output_dir, f"comparison_{timestamp}.md")
    agent_guru.generate_markdown_report(results, report_path)

    # Print key findings
    print(f"\nBenchmark reports saved to {output_dir}")
    overall_winner = analysis["overall_winner"]["winner"]
    print(
        f"Overall winner: {overall_winner['framework']} "
        f"(score: {overall_winner['score']:.1f}/100)",
    )

    if analysis["improvement_analysis"].get("agent_guru_unique"):
        agent_guru_improvement = analysis["improvement_analysis"]["agent_guru_improvement"]
        print(
            "Agent Guru unique feature: self-improvement capability "
            f"({agent_guru_improvement:.1f}% improvement over time) -- "
            "no other framework demonstrated improvement over time",
        )

    return results


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Agent Guru vs Competitor Frameworks Benchmark",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="Agent_Guru/self_improvement/benchmarks/results",
        help="Directory to save results",
    )
    parser.add_argument(
        "--scenario-type",
        type=str,
        choices=["all", "simple", "complex", "tool", "error", "learning"],
        default="all",
        help="Type of scenarios to run",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=0,
        help="Number of warmup runs before measurement",
    )

    args = parser.parse_args()

    results = run_all_benchmarks(
        output_dir=args.output_dir,
        scenario_type=args.scenario_type,
        warmup_runs=args.warmup_runs,
    )

    for result in results:
        if result.metrics.improvement_rate is not None:
            print(
                f"{result.framework_name}: "
                f"{result.metrics.improvement_rate:.1f}% improvement over time",
            )


if __name__ == "__main__":
    main()
