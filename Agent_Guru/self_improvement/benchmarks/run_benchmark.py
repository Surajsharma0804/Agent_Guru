"""
Main benchmark runner script.

Runs benchmarks comparing Agent Guru to all competitor frameworks and generates reports.
"""

import argparse
import os
from datetime import datetime, timezone

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
    warmup_runs: int = 0
) -> list[BenchmarkResult]:
    """
    Run benchmarks for all frameworks.

    Args:
        output_dir: Directory to save results
        scenario_type: Type of scenarios to run (all, simple, complex, etc.)
        warmup_runs: Number of warmup runs before measurement

    Returns:
        List of benchmark results
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Get scenarios
    print(f"\nLoading {scenario_type} scenarios...")
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
        raise ValueError(f"Unknown scenario type: {scenario_type}")

    print(f"Loaded {len(scenarios)} scenarios\n")

    results = []
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Run Agent Guru benchmark
    print("=" * 60)
    print("Running Agent Guru Benchmark")
    print("=" * 60)
    agent_guru = create_agent_guru_benchmark()
    agent_guru_result = agent_guru.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(agent_guru_result)

    # Save Agent Guru results
    agent_guru_result.to_json(
        os.path.join(output_dir, f"agent_guru_{timestamp}.json")
    )
    print("\nAgent Guru Results:")
    print(f"  Success Rate: {agent_guru_result.metrics.success_rate:.1f}%")
    print(f"  Avg Time: {agent_guru_result.metrics.avg_execution_time_ms:.1f} ms")
    print(f"  API Calls: {agent_guru_result.metrics.total_api_calls}")
    print(f"  Tokens: {agent_guru_result.metrics.total_tokens}")
    if agent_guru_result.metrics.improvement_rate is not None:
        print(f"  Improvement Rate: {agent_guru_result.metrics.improvement_rate:.1f}%")
    if agent_guru_result.metrics.recovery_rate is not None:
        print(f"  Recovery Rate: {agent_guru_result.metrics.recovery_rate:.1f}%")

    # Run LangChain benchmark
    print("\n" + "=" * 60)
    print("Running LangChain Benchmark")
    print("=" * 60)
    langchain = create_langchain_benchmark()
    langchain_result = langchain.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(langchain_result)

    # Save LangChain results
    langchain_result.to_json(
        os.path.join(output_dir, f"langchain_{timestamp}.json")
    )
    print("\nLangChain Results:")
    print(f"  Success Rate: {langchain_result.metrics.success_rate:.1f}%")
    print(f"  Avg Time: {langchain_result.metrics.avg_execution_time_ms:.1f} ms")
    print(f"  API Calls: {langchain_result.metrics.total_api_calls}")
    print(f"  Tokens: {langchain_result.metrics.total_tokens}")

    # Run CrewAI benchmark
    print("\n" + "=" * 60)
    print("Running CrewAI Benchmark")
    print("=" * 60)
    crewai = create_crewai_benchmark()
    crewai_result = crewai.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(crewai_result)

    # Save CrewAI results
    crewai_result.to_json(
        os.path.join(output_dir, f"crewai_{timestamp}.json")
    )
    print("\nCrewAI Results:")
    print(f"  Success Rate: {crewai_result.metrics.success_rate:.1f}%")
    print(f"  Avg Time: {crewai_result.metrics.avg_execution_time_ms:.1f} ms")
    print(f"  API Calls: {crewai_result.metrics.total_api_calls}")
    print(f"  Tokens: {crewai_result.metrics.total_tokens}")

    # Run AutoGen benchmark
    print("\n" + "=" * 60)
    print("Running AutoGen Benchmark")
    print("=" * 60)
    autogen = create_autogen_benchmark()
    autogen_result = autogen.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(autogen_result)

    # Save AutoGen results
    autogen_result.to_json(
        os.path.join(output_dir, f"autogen_{timestamp}.json")
    )
    print("\nAutoGen Results:")
    print(f"  Success Rate: {autogen_result.metrics.success_rate:.1f}%")
    print(f"  Avg Time: {autogen_result.metrics.avg_execution_time_ms:.1f} ms")
    print(f"  API Calls: {autogen_result.metrics.total_api_calls}")
    print(f"  Tokens: {autogen_result.metrics.total_tokens}")

    # Run AutoGPT benchmark
    print("\n" + "=" * 60)
    print("Running AutoGPT Benchmark")
    print("=" * 60)
    autogpt = create_autogpt_benchmark()
    autogpt_result = autogpt.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(autogpt_result)

    # Save AutoGPT results
    autogpt_result.to_json(
        os.path.join(output_dir, f"autogpt_{timestamp}.json")
    )
    print("\nAutoGPT Results:")
    print(f"  Success Rate: {autogpt_result.metrics.success_rate:.1f}%")
    print(f"  Avg Time: {autogpt_result.metrics.avg_execution_time_ms:.1f} ms")
    print(f"  API Calls: {autogpt_result.metrics.total_api_calls}")
    print(f"  Tokens: {autogpt_result.metrics.total_tokens}")

    # Generate comparison report
    print("\n" + "=" * 60)
    print("Generating Comprehensive Comparison Report")
    print("=" * 60)

    # Generate comprehensive report with all metrics
    analysis = generate_comprehensive_report(results, output_dir)

    # Also generate simple markdown report
    report_path = os.path.join(output_dir, f"comparison_{timestamp}.md")
    agent_guru.generate_markdown_report(results, report_path)
    print(f"Simple report saved to: {report_path}")

    # Print key findings
    print("\n" + "=" * 60)
    print("Key Findings")
    print("=" * 60)
    print(f"\nOverall Winner: {analysis['overall_winner']['winner']['framework']}")
    print(f"Agent Guru Wins: {analysis['overall_winner']['agent_guru_wins']}")

    if analysis['improvement_analysis'].get('agent_guru_unique'):
        print("\n✅ Agent Guru has unique self-improvement capability")
        print(f"   Improvement Rate: {analysis['improvement_analysis']['agent_guru_improvement']:.1f}%")

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Agent Guru vs Competitor Frameworks Benchmark"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="Agent_Guru/self_improvement/benchmarks/results",
        help="Directory to save results"
    )
    parser.add_argument(
        "--scenario-type",
        type=str,
        choices=["all", "simple", "complex", "tool", "error", "learning"],
        default="all",
        help="Type of scenarios to run"
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=0,
        help="Number of warmup runs before measurement"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("Agent Guru vs Competitor Frameworks Benchmark Suite")
    print("=" * 60)
    print(f"Scenario Type: {args.scenario_type}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Warmup Runs: {args.warmup_runs}")
    print("\nFrameworks: Agent Guru, LangChain, CrewAI, AutoGen, AutoGPT")

    results = run_all_benchmarks(
        output_dir=args.output_dir,
        scenario_type=args.scenario_type,
        warmup_runs=args.warmup_runs
    )

    print("\n" + "=" * 60)
    print("Benchmark Complete!")
    print("=" * 60)
    print(f"\nResults saved to: {args.output_dir}")
    print("\nSummary:")
    for result in results:
        print(f"\n{result.framework_name}:")
        print(f"  Success Rate: {result.metrics.success_rate:.1f}%")
        print(f"  Avg Time: {result.metrics.avg_execution_time_ms:.1f} ms")
        print(f"  Total Tokens: {result.metrics.total_tokens}")
        if result.metrics.improvement_rate is not None:
            print(f"  Improvement: {result.metrics.improvement_rate:.1f}%")


if __name__ == "__main__":
    main()
