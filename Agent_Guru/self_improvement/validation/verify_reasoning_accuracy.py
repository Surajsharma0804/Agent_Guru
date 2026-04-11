"""
Verification Script: Task 24.4 - Verify Improvement in Reasoning Accuracy

This script verifies that reasoning quality improved from baseline to final window
in the 100-task learning cycle.

Requirements:
- Requirement 7.4: Demonstrate improvement in reasoning accuracy
- Design: Performance Tracker must measure reasoning quality improvements
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


def get_reasoning_quality_scores(conn: sqlite3.Connection) -> List[Tuple[int, float]]:
    """Get all reasoning quality scores ordered by task number."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT task_sequence_number, reasoning_quality
        FROM metrics
        ORDER BY task_sequence_number
    """)
    return cursor.fetchall()


def calculate_window_stats(
    quality_scores: List[Tuple[int, float]],
    start: int,
    end: int
) -> Dict[str, float]:
    """Calculate statistics for a window of tasks."""
    window_scores = [
        score for task_num, score in quality_scores
        if start <= task_num <= end
    ]
    
    if not window_scores:
        return {
            "mean": 0.0,
            "median": 0.0,
            "min": 0.0,
            "max": 0.0,
            "std_dev": 0.0,
            "count": 0
        }
    
    return {
        "mean": statistics.mean(window_scores),
        "median": statistics.median(window_scores),
        "min": min(window_scores),
        "max": max(window_scores),
        "std_dev": statistics.stdev(window_scores) if len(window_scores) > 1 else 0.0,
        "count": len(window_scores)
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
    
    absolute_change = final - baseline  # Positive means improvement (higher is better)
    relative_change = absolute_change / baseline
    percentage_change = relative_change * 100
    
    return {
        "absolute_change": absolute_change,
        "relative_change": relative_change,
        "percentage_change": percentage_change,
        "improved": absolute_change > 0  # Higher is better
    }


def verify_reasoning_accuracy_improvement(db_path: str) -> Dict[str, Any]:
    """
    Verify that reasoning accuracy improved from baseline to final window.
    
    Args:
        db_path: Path to validation database
        
    Returns:
        Verification results with pass/fail status
    """
    conn = load_database(db_path)
    
    # Get all reasoning quality scores
    quality_scores = get_reasoning_quality_scores(conn)
    
    if len(quality_scores) < 100:
        return {
            "status": "FAILED",
            "reason": f"Insufficient tasks: {len(quality_scores)} < 100",
            "baseline": {},
            "final": {},
            "improvement": {}
        }
    
    # Calculate baseline stats (tasks 1-10)
    baseline_stats = calculate_window_stats(quality_scores, 1, 10)
    
    # Calculate final stats (tasks 91-100)
    final_stats = calculate_window_stats(quality_scores, 91, 100)
    
    # Calculate improvement
    improvement = calculate_improvement(
        baseline_stats["mean"],
        final_stats["mean"]
    )
    
    # Determine pass/fail
    passed = improvement["improved"]
    
    # Get overall stats
    all_scores = [score for _, score in quality_scores]
    overall_stats = {
        "total_tasks": len(quality_scores),
        "mean": statistics.mean(all_scores),
        "median": statistics.median(all_scores),
        "min": min(all_scores),
        "max": max(all_scores)
    }
    
    conn.close()
    
    return {
        "status": "PASSED" if passed else "FAILED",
        "verification_date": datetime.now(tz=timezone.utc).isoformat(),
        "database": db_path,
        "baseline": {
            "window": "Tasks 1-10",
            "mean_score": round(baseline_stats["mean"], 4),
            "median_score": round(baseline_stats["median"], 4),
            "min_score": round(baseline_stats["min"], 4),
            "max_score": round(baseline_stats["max"], 4),
            "std_dev": round(baseline_stats["std_dev"], 4),
            "count": baseline_stats["count"]
        },
        "final": {
            "window": "Tasks 91-100",
            "mean_score": round(final_stats["mean"], 4),
            "median_score": round(final_stats["median"], 4),
            "min_score": round(final_stats["min"], 4),
            "max_score": round(final_stats["max"], 4),
            "std_dev": round(final_stats["std_dev"], 4),
            "count": final_stats["count"]
        },
        "improvement": {
            "absolute_change": round(improvement["absolute_change"], 4),
            "relative_change": round(improvement["relative_change"], 4),
            "percentage_change": round(improvement["percentage_change"], 2),
            "improved": improvement["improved"],
            "interpretation": "Better" if improvement["improved"] else "Worse"
        },
        "overall": overall_stats,
        "conclusion": (
            f"Reasoning accuracy {'IMPROVED' if passed else 'DID NOT IMPROVE'} "
            f"from baseline to final window. "
            f"Mean reasoning quality changed by {improvement['percentage_change']:.1f}%."
        )
    }


def generate_report(results: Dict[str, Any], output_path: str) -> None:
    """Generate markdown report."""
    report = f"""# Reasoning Accuracy Improvement Verification Report

**Generated:** {results['verification_date']}

**Database:** `{results['database']}`

## Verification Status

{'✅' if results['status'] == 'PASSED' else '❌'} **Verification {results['status']}**

{'✅' if results['status'] == 'PASSED' else '❌'} Reasoning accuracy improved from baseline to final window

## Executive Summary

The self-improvement engine was required to demonstrate improvement in reasoning accuracy (Requirement 7.4).

**Result:** {results['improvement']['percentage_change']:.1f}% {'improvement' if results['improvement']['improved'] else 'degradation'} {'✅' if results['status'] == 'PASSED' else '❌'}

## Reasoning Quality Comparison

### Baseline Window (Tasks 1-10)

| Metric | Value |
|--------|-------|
| **Mean Reasoning Quality** | {results['baseline']['mean_score']:.4f} |
| **Median Reasoning Quality** | {results['baseline']['median_score']:.4f} |
| **Min Reasoning Quality** | {results['baseline']['min_score']:.4f} |
| **Max Reasoning Quality** | {results['baseline']['max_score']:.4f} |
| **Std Deviation** | {results['baseline']['std_dev']:.4f} |
| **Sample Size** | {results['baseline']['count']} tasks |

### Final Window (Tasks 91-100)

| Metric | Value |
|--------|-------|
| **Mean Reasoning Quality** | {results['final']['mean_score']:.4f} |
| **Median Reasoning Quality** | {results['final']['median_score']:.4f} |
| **Min Reasoning Quality** | {results['final']['min_score']:.4f} |
| **Max Reasoning Quality** | {results['final']['max_score']:.4f} |
| **Std Deviation** | {results['final']['std_dev']:.4f} |
| **Sample Size** | {results['final']['count']} tasks |

## Improvement Analysis

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Absolute Change** | {results['improvement']['absolute_change']:.4f} | {'Better' if results['improvement']['improved'] else 'Worse'} |
| **Relative Change** | {results['improvement']['relative_change']:.4f} | {results['improvement']['percentage_change']:.2f}% |
| **Improvement Status** | {'✅ IMPROVED' if results['improvement']['improved'] else '❌ NO IMPROVEMENT'} | {results['improvement']['interpretation']} |

## Overall Performance

- **Total Tasks:** {results['overall']['total_tasks']}
- **Overall Mean:** {results['overall']['mean']:.4f}
- **Overall Median:** {results['overall']['median']:.4f}
- **Overall Min:** {results['overall']['min']:.4f}
- **Overall Max:** {results['overall']['max']:.4f}

## Reasoning Quality Scale

Reasoning quality is measured on a scale from 0.0 to 1.0:
- **0.0 - 0.3:** Poor reasoning (many errors)
- **0.3 - 0.5:** Fair reasoning (some errors)
- **0.5 - 0.7:** Good reasoning (few errors)
- **0.7 - 0.9:** Excellent reasoning (minimal errors)
- **0.9 - 1.0:** Perfect reasoning (no errors)

## Conclusion

{results['conclusion']}

{'✅ **SUCCESS:** The self-improvement engine demonstrated measurable improvement in reasoning accuracy.' if results['status'] == 'PASSED' else '❌ **FAILURE:** The self-improvement engine did not demonstrate improvement in reasoning accuracy.'}

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
    print("Task 24.4: Verify Improvement in Reasoning Accuracy")
    print("=" * 80)
    print()
    
    print(f"Loading database: {db_path}")
    
    # Run verification
    results = verify_reasoning_accuracy_improvement(db_path)
    
    # Save JSON results
    output_dir = Path("Agent_Guru/self_improvement/validation/results")
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"reasoning_accuracy_verification_{timestamp}.json"
    md_path = output_dir / f"reasoning_accuracy_verification_{timestamp}.md"
    
    with open(json_path, 'w') as f:
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
    print(f"Baseline Mean: {results['baseline']['mean_score']:.4f}")
    print(f"Final Mean: {results['final']['mean_score']:.4f}")
    print(f"Improvement: {results['improvement']['percentage_change']:.1f}%")
    print()
    print(results['conclusion'])
    print()
    
    if results['status'] == "PASSED":
        print("✅ Task 24.4 COMPLETE: Reasoning accuracy improvement verified")
    else:
        print("❌ Task 24.4 FAILED: No reasoning accuracy improvement detected")


if __name__ == "__main__":
    main()
