"""
Verification Script: Task 24.3 - Verify Improvement in Execution Time

This script verifies that execution time improved from baseline to final window
in the 100-task learning cycle.

Requirements:
- Requirement 7.4: Demonstrate improvement in task completion time
- Design: Performance Tracker must measure execution time improvements
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import statistics


def load_database(db_path: str) -> sqlite3.Connection:
    """Load the validation database."""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    return sqlite3.connect(db_path)


def get_execution_times(conn: sqlite3.Connection) -> List[Tuple[int, float]]:
    """Get all task execution times ordered by task number."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT task_sequence_number, execution_time_ms
        FROM metrics
        ORDER BY task_sequence_number
    """)
    return cursor.fetchall()


def calculate_window_stats(
    execution_times: List[Tuple[int, float]],
    start: int,
    end: int
) -> Dict[str, float]:
    """Calculate statistics for a window of tasks."""
    window_times = [
        time for task_num, time in execution_times
        if start <= task_num <= end
    ]
    
    if not window_times:
        return {
            "mean": 0.0,
            "median": 0.0,
            "min": 0.0,
            "max": 0.0,
            "std_dev": 0.0,
            "count": 0
        }
    
    return {
        "mean": statistics.mean(window_times),
        "median": statistics.median(window_times),
        "min": min(window_times),
        "max": max(window_times),
        "std_dev": statistics.stdev(window_times) if len(window_times) > 1 else 0.0,
        "count": len(window_times)
    }


def calculate_improvement(baseline: float, final: float) -> Dict[str, Any]:
    """Calculate improvement metrics."""
    if baseline == 0:
        return {
            "absolute_change": 0.0,
            "relative_change": 0.0,
            "percentage_change": 0.0,
            "improved": False
        }
    
    absolute_change = baseline - final  # Positive means improvement (faster)
    relative_change = absolute_change / baseline
    percentage_change = relative_change * 100
    
    return {
        "absolute_change": absolute_change,
        "relative_change": relative_change,
        "percentage_change": percentage_change,
        "improved": absolute_change > 0  # Faster is better
    }


def verify_execution_time_improvement(db_path: str) -> Dict[str, Any]:
    """
    Verify that execution time improved from baseline to final window.
    
    Args:
        db_path: Path to validation database
        
    Returns:
        Verification results with pass/fail status
    """
    conn = load_database(db_path)
    
    # Get all execution times
    execution_times = get_execution_times(conn)
    
    if len(execution_times) < 100:
        return {
            "status": "FAILED",
            "reason": f"Insufficient tasks: {len(execution_times)} < 100",
            "baseline": {},
            "final": {},
            "improvement": {}
        }
    
    # Calculate baseline stats (tasks 1-10)
    baseline_stats = calculate_window_stats(execution_times, 1, 10)
    
    # Calculate final stats (tasks 91-100)
    final_stats = calculate_window_stats(execution_times, 91, 100)
    
    # Calculate improvement
    improvement = calculate_improvement(
        baseline_stats["mean"],
        final_stats["mean"]
    )
    
    # Determine pass/fail
    passed = improvement["improved"]
    
    # Get overall stats
    all_times = [time for _, time in execution_times]
    overall_stats = {
        "total_tasks": len(execution_times),
        "mean": statistics.mean(all_times),
        "median": statistics.median(all_times),
        "min": min(all_times),
        "max": max(all_times)
    }
    
    conn.close()
    
    return {
        "status": "PASSED" if passed else "FAILED",
        "verification_date": datetime.now(tz=timezone.utc).isoformat(),
        "database": db_path,
        "baseline": {
            "window": "Tasks 1-10",
            "mean_ms": round(baseline_stats["mean"], 2),
            "median_ms": round(baseline_stats["median"], 2),
            "min_ms": round(baseline_stats["min"], 2),
            "max_ms": round(baseline_stats["max"], 2),
            "std_dev_ms": round(baseline_stats["std_dev"], 2),
            "count": baseline_stats["count"]
        },
        "final": {
            "window": "Tasks 91-100",
            "mean_ms": round(final_stats["mean"], 2),
            "median_ms": round(final_stats["median"], 2),
            "min_ms": round(final_stats["min"], 2),
            "max_ms": round(final_stats["max"], 2),
            "std_dev_ms": round(final_stats["std_dev"], 2),
            "count": final_stats["count"]
        },
        "improvement": {
            "absolute_change_ms": round(improvement["absolute_change"], 2),
            "relative_change": round(improvement["relative_change"], 4),
            "percentage_change": round(improvement["percentage_change"], 2),
            "improved": improvement["improved"],
            "interpretation": "Faster" if improvement["improved"] else "Slower"
        },
        "overall": overall_stats,
        "conclusion": (
            f"Execution time {'IMPROVED' if passed else 'DID NOT IMPROVE'} "
            f"from baseline to final window. "
            f"Mean execution time changed by {improvement['percentage_change']:.1f}%."
        )
    }


def generate_report(results: Dict[str, Any], output_path: str) -> None:
    """Generate markdown report."""
    report = f"""# Execution Time Improvement Verification Report

**Generated:** {results['verification_date']}

**Database:** `{results['database']}`

## Verification Status

{'✅' if results['status'] == 'PASSED' else '❌'} **Verification {results['status']}**

{'✅' if results['status'] == 'PASSED' else '❌'} Execution time improved from baseline to final window

## Executive Summary

The self-improvement engine was required to demonstrate improvement in task completion time (Requirement 7.4).

**Result:** {results['improvement']['percentage_change']:.1f}% {'improvement' if results['improvement']['improved'] else 'degradation'} {'✅' if results['status'] == 'PASSED' else '❌'}

## Execution Time Comparison

### Baseline Window (Tasks 1-10)

| Metric | Value |
|--------|-------|
| **Mean Execution Time** | {results['baseline']['mean_ms']:.2f} ms |
| **Median Execution Time** | {results['baseline']['median_ms']:.2f} ms |
| **Min Execution Time** | {results['baseline']['min_ms']:.2f} ms |
| **Max Execution Time** | {results['baseline']['max_ms']:.2f} ms |
| **Std Deviation** | {results['baseline']['std_dev_ms']:.2f} ms |
| **Sample Size** | {results['baseline']['count']} tasks |

### Final Window (Tasks 91-100)

| Metric | Value |
|--------|-------|
| **Mean Execution Time** | {results['final']['mean_ms']:.2f} ms |
| **Median Execution Time** | {results['final']['median_ms']:.2f} ms |
| **Min Execution Time** | {results['final']['min_ms']:.2f} ms |
| **Max Execution Time** | {results['final']['max_ms']:.2f} ms |
| **Std Deviation** | {results['final']['std_dev_ms']:.2f} ms |
| **Sample Size** | {results['final']['count']} tasks |

## Improvement Analysis

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Absolute Change** | {results['improvement']['absolute_change_ms']:.2f} ms | {'Faster' if results['improvement']['improved'] else 'Slower'} |
| **Relative Change** | {results['improvement']['relative_change']:.4f} | {results['improvement']['percentage_change']:.2f}% |
| **Improvement Status** | {'✅ IMPROVED' if results['improvement']['improved'] else '❌ NO IMPROVEMENT'} | {results['improvement']['interpretation']} |

## Overall Performance

- **Total Tasks:** {results['overall']['total_tasks']}
- **Overall Mean:** {results['overall']['mean']:.2f} ms
- **Overall Median:** {results['overall']['median']:.2f} ms
- **Overall Min:** {results['overall']['min']:.2f} ms
- **Overall Max:** {results['overall']['max']:.2f} ms

## Conclusion

{results['conclusion']}

{'✅ **SUCCESS:** The self-improvement engine demonstrated measurable improvement in execution time.' if results['status'] == 'PASSED' else '❌ **FAILURE:** The self-improvement engine did not demonstrate improvement in execution time.'}

This {'validates' if results['status'] == 'PASSED' else 'does not validate'} Requirement 7.4: "THE Self_Improvement_Engine SHALL demonstrate improvement in at least two additional metrics: task completion time or reasoning accuracy."

---

**Verification Complete**  
**Status:** {'✅ PASSED' if results['status'] == 'PASSED' else '❌ FAILED'}  
**Date:** {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}  
**Version:** 1.0.0
"""
    
    Path(output_path).write_text(report, encoding='utf-8')


def main():
    """Main execution."""
    # Use the latest validation database
    db_path = "Agent_Guru/self_improvement/validation/results/validation_20260307_092801.db"
    
    print("=" * 80)
    print("Task 24.3: Verify Improvement in Execution Time")
    print("=" * 80)
    print()
    
    print(f"Loading database: {db_path}")
    
    # Run verification
    results = verify_execution_time_improvement(db_path)
    
    # Save JSON results
    output_dir = Path("Agent_Guru/self_improvement/validation/results")
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"execution_time_verification_{timestamp}.json"
    md_path = output_dir / f"execution_time_verification_{timestamp}.md"
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to: {json_path}")
    
    # Generate markdown report
    generate_report(results, str(md_path))
    print(f"✅ Report saved to: {md_path}")
    
    print()
    print("=" * 80)
    print("VERIFICATION RESULTS")
    print("=" * 80)
    print()
    print(f"Status: {results['status']}")
    print(f"Baseline Mean: {results['baseline']['mean_ms']:.2f} ms")
    print(f"Final Mean: {results['final']['mean_ms']:.2f} ms")
    print(f"Improvement: {results['improvement']['percentage_change']:.1f}%")
    print()
    print(results['conclusion'])
    print()
    
    if results['status'] == "PASSED":
        print("✅ Task 24.3 COMPLETE: Execution time improvement verified")
    else:
        print("❌ Task 24.3 FAILED: No execution time improvement detected")


if __name__ == "__main__":
    main()
