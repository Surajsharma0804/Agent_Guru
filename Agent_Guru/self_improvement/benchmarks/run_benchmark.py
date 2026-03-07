"""
Main benchmark runner script.

Runs benchmarks comparing Agent Guru to LangChain and generates reports.
"""

import argparse
import os
from datetime import datetime
from typing import List

from Agent_Guru.self_improvement.benchmarks.base_benchmark import BenchmarkResult
from Agent_Guru.self_improvement.benchmarks.agent_guru_benchmark import create_agent_guru_benchmark
from Agent_Guru.self_improvement.benchmarks.langchain_benchmark import create_langchain_benchmark
from Agent_Guru.self_improvement.benchmarks.test_scenarios import (
    get_all_scenarios,
    get_simple_scenarios,
    get_complex_scenarios,
    get_tool_usage_scenarios,
    get_error_recovery_scenarios,
    get_learning_scenarios,
)


def run_all_benchmarks(
    output_dir: str = "Agent_Guru/self_improvement/benchmarks/results",
    scenario_type: str = "all",
    warmup_runs: int = 0
) -> List[BenchmarkResult]:
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
    
    # Run Agent Guru benchmark
    print("=" * 60)
    print("Running Agent Guru Benchmark")
    print("=" * 60)
    agent_guru = create_agent_guru_benchmark()
    agent_guru_result = agent_guru.run_benchmark(scenarios, warmup_runs=warmup_runs)
    results.append(agent_guru_result)
    
    # Save Agent Guru results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    agent_guru_result.to_json(
        os.path.join(output_dir, f"agent_guru_{timestamp}.json")
    )
    print(f"\nAgent Guru Results:")
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
    print(f"\nLangChain Results:")
    print(f"  Success Rate: {langchain_result.metrics.success_rate:.1f}%")
    print(f"  Avg Time: {langchain_result.metrics.avg_execution_time_ms:.1f} ms")
    print(f"  API Calls: {langchain_result.metrics.total_api_calls}")
    print(f"  Tokens: {langchain_result.metrics.total_tokens}")
    
    # Generate comparison report
    print("\n" + "=" * 60)
    print("Generating Comparison Report")
    print("=" * 60)
    report_path = os.path.join(output_dir, f"comparison_{timestamp}.md")
    agent_guru.generate_markdown_report(results, report_path)
    print(f"Report saved to: {report_path}")
    
    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Agent Guru vs LangChain benchmark comparison"
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
    print("Agent Guru vs LangChain Benchmark Suite")
    print("=" * 60)
    print(f"Scenario Type: {args.scenario_type}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Warmup Runs: {args.warmup_runs}")
    
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
