"""
Verification script for 15% improvement target (Task 24.2).

This script verifies that the 100-task learning cycle achieved at least 15%
improvement in success rate, as required by Requirement 7.3.

Performance Requirements:
- Time Complexity: O(n) where n is number of tasks
- Space Complexity: O(1) for metrics calculation
- Statistical rigor: t-test, confidence intervals

Author: Agent Guru Team
Date: 2026-03-07
Version: 1.0.0
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import numpy as np
from scipy import stats

# `with sqlite3.connect() as conn:` only ends the transaction and leaves the
# connection open until garbage collection, which on Windows keeps the database
# file locked. Connections here go through open_sqlite(), which also closes.
from Agent_Guru.utils.sqlite import open_sqlite


@dataclass
class ImprovementMetrics:
    """Metrics for improvement verification."""
    
    baseline_success_rate: float
    final_success_rate: float
    absolute_improvement: float
    relative_improvement: float
    improvement_percentage: float
    meets_target: bool
    target_threshold: float
    
    # Statistical significance
    t_statistic: float
    p_value: float
    is_significant: bool
    confidence_level: float
    confidence_interval: Tuple[float, float]
    
    # Additional context
    baseline_sample_size: int
    final_sample_size: int
    total_tasks: int
    baseline_window: str
    final_window: str


@dataclass
class VerificationReport:
    """Complete verification report."""
    
    timestamp: datetime
    database_path: str
    validation_passed: bool
    improvement_metrics: ImprovementMetrics
    
    # Task distribution
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    overall_success_rate: float
    
    # Detailed breakdown
    success_by_window: List[Dict[str, Any]]
    failure_analysis: Dict[str, int]
    
    # Recommendations
    recommendations: List[str]


class ImprovementVerifier:
    """
    Verifies 15% improvement target from validation data.
    
    Performs statistical analysis to confirm significance and generates
    comprehensive verification report.
    """
    
    def __init__(
        self,
        database_path: str,
        improvement_threshold: float = 0.15,
        confidence_level: float = 0.95,
        baseline_window: Tuple[int, int] = (1, 10),
        final_window: Tuple[int, int] = (91, 100)
    ):
        """
        Initialize improvement verifier.
        
        Args:
            database_path: Path to validation database
            improvement_threshold: Minimum relative improvement (15%)
            confidence_level: Statistical confidence level (95%)
            baseline_window: Task range for baseline (1-10)
            final_window: Task range for final measurement (91-100)
        """
        self.database_path = database_path
        self.improvement_threshold = improvement_threshold
        self.confidence_level = confidence_level
        self.baseline_window = baseline_window
        self.final_window = final_window
        
        if not Path(database_path).exists():
            raise FileNotFoundError(f"Database not found: {database_path}")
    
    def verify_improvement(self) -> VerificationReport:
        """
        Verify 15% improvement target.
        
        Time Complexity: O(n) where n is number of tasks
        Space Complexity: O(1) for metrics
        
        Returns:
            Complete verification report
        """
        # Load task data
        tasks = self._load_tasks()
        
        # Calculate baseline and final metrics
        baseline_tasks = self._filter_tasks_by_window(tasks, self.baseline_window)
        final_tasks = self._filter_tasks_by_window(tasks, self.final_window)
        
        baseline_success_rate = self._calculate_success_rate(baseline_tasks)
        final_success_rate = self._calculate_success_rate(final_tasks)
        
        # Calculate improvement
        absolute_improvement = final_success_rate - baseline_success_rate
        # BUG FIX: a zero baseline success rate makes relative
        # improvement mathematically undefined (division by zero), but
        # this used to silently fall back to 0.0 in that case --
        # misreporting even a 0% -> 100% improvement as a 0% relative
        # improvement, which then makes meets_target always False no
        # matter how dramatic the real improvement was. Any positive
        # final success rate after a zero baseline is treated as a full
        # (100%, i.e. 1.0 in this file's fraction convention)
        # improvement, consistent with the equivalent zero-baseline
        # handling already established in performance_tracker.py's
        # calculate_improvement().
        if baseline_success_rate > 0:
            relative_improvement = absolute_improvement / baseline_success_rate
        else:
            relative_improvement = 1.0 if final_success_rate > 0 else 0.0
        improvement_percentage = relative_improvement * 100
        
        # Check if target met
        meets_target = relative_improvement >= self.improvement_threshold
        
        # Statistical significance testing
        t_stat, p_value, is_significant, ci = self._test_significance(
            baseline_tasks, final_tasks
        )
        
        # Create improvement metrics
        improvement_metrics = ImprovementMetrics(
            baseline_success_rate=baseline_success_rate,
            final_success_rate=final_success_rate,
            absolute_improvement=absolute_improvement,
            relative_improvement=relative_improvement,
            improvement_percentage=improvement_percentage,
            meets_target=meets_target,
            target_threshold=self.improvement_threshold,
            t_statistic=t_stat,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=self.confidence_level,
            confidence_interval=ci,
            baseline_sample_size=len(baseline_tasks),
            final_sample_size=len(final_tasks),
            total_tasks=len(tasks),
            baseline_window=f"Tasks {self.baseline_window[0]}-{self.baseline_window[1]}",
            final_window=f"Tasks {self.final_window[0]}-{self.final_window[1]}"
        )
        
        # Calculate additional metrics
        total_tasks = len(tasks)
        successful_tasks = sum(1 for t in tasks if t["success"])
        failed_tasks = total_tasks - successful_tasks
        overall_success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0.0
        
        # Success by window
        success_by_window = self._calculate_success_by_window(tasks)
        
        # Failure analysis
        failure_analysis = self._analyze_failures(tasks)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(improvement_metrics)
        
        # Create verification report
        report = VerificationReport(
            timestamp=datetime.now(tz=timezone.utc),
            database_path=self.database_path,
            validation_passed=meets_target,
            improvement_metrics=improvement_metrics,
            total_tasks=total_tasks,
            successful_tasks=successful_tasks,
            failed_tasks=failed_tasks,
            overall_success_rate=overall_success_rate,
            success_by_window=success_by_window,
            failure_analysis=failure_analysis,
            recommendations=recommendations
        )
        
        return report
    
    def _load_tasks(self) -> List[Dict[str, Any]]:
        """Load tasks from database."""
        with open_sqlite(self.database_path) as conn:
            cursor = conn.cursor()

            # Load from metrics table
            cursor.execute("""
                SELECT task_id, task_sequence_number, task_type, strategy_id,
                       success, execution_time_ms, reasoning_quality, timestamp
                FROM metrics
                ORDER BY task_sequence_number
            """)

            tasks = []
            for row in cursor.fetchall():
                task_id = row[0]
                task_number = row[1]

                # Get failure type if task failed
                failure_type = None
                if not row[4]:  # if not success
                    cursor.execute("""
                        SELECT failure_type
                        FROM failures
                        WHERE task_id = ?
                        LIMIT 1
                    """, (task_id,))
                    failure_row = cursor.fetchone()
                    if failure_row:
                        failure_type = failure_row[0]

                tasks.append({
                    "task_id": task_id,
                    "task_number": task_number,
                    "task_type": row[2],
                    "strategy_id": row[3],
                    "success": bool(row[4]),
                    "execution_time_ms": row[5],
                    "reasoning_quality": row[6],
                    "failure_type": failure_type,
                    "timestamp": row[7]
                })

        return tasks
    
    def _filter_tasks_by_window(
        self,
        tasks: List[Dict[str, Any]],
        window: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        """Filter tasks by window range."""
        start, end = window
        return [
            t for t in tasks
            if start <= t["task_number"] <= end
        ]
    
    def _calculate_success_rate(self, tasks: List[Dict[str, Any]]) -> float:
        """Calculate success rate for tasks."""
        if not tasks:
            return 0.0
        
        successful = sum(1 for t in tasks if t["success"])
        return successful / len(tasks)
    
    def _test_significance(
        self,
        baseline_tasks: List[Dict[str, Any]],
        final_tasks: List[Dict[str, Any]]
    ) -> Tuple[float, float, bool, Tuple[float, float]]:
        """
        Test statistical significance of improvement.
        
        Uses independent samples t-test and confidence intervals.
        
        Returns:
            (t_statistic, p_value, is_significant, confidence_interval)
        """
        # Convert to binary arrays (1 = success, 0 = failure)
        baseline_results = np.array([1 if t["success"] else 0 for t in baseline_tasks])
        final_results = np.array([1 if t["success"] else 0 for t in final_tasks])

        # A t-test needs at least two tasks in each window: the variances
        # below use ddof=1 and the degrees of freedom are n1 + n2 - 2. On a
        # new install, where the database is empty, this used to raise
        # ZeroDivisionError from `1 / n1`, so every first run of
        # verify_improvement() crashed and only users who already had data
        # got a report. With too little data the answer is "not
        # significant", and the confidence interval is the whole possible
        # range of a difference in success rates, which states that nothing
        # is known instead of claiming a precise zero.
        if len(baseline_results) < 2 or len(final_results) < 2:
            return 0.0, 1.0, False, (-1.0, 1.0)

        # Perform t-test (scipy defaults to equal_var=True, a pooled-
        # variance / Student's t-test -- the confidence interval below
        # is computed to match that same model)
        t_stat, p_value_two_tailed = stats.ttest_ind(final_results, baseline_results)
        
        # BUG FIX: this used to compare the RAW two-tailed p-value from
        # scipy directly against alpha, despite the comment (and every
        # downstream report) describing this as a one-tailed test. A
        # one-tailed p-value for the hypothesis "final > baseline" is
        # half the two-tailed p-value when the observed effect is in that
        # direction (t_stat > 0), and 1 minus that half otherwise --
        # standard derivation for a one-tailed test from a two-tailed
        # t-test result. Concretely reproduced: baseline 30% / final 70%
        # over 10 tasks each (t_stat=1.8516, two-tailed p=0.0806) used to
        # report is_significant=False under the old two-tailed check,
        # while the correct one-tailed p-value (0.0403) is significant at
        # the stated 95% confidence level. p_value now reports this
        # one-tailed value consistently everywhere it surfaces (JSON
        # report, Markdown report, printed summary), matching the
        # one-tailed methodology already documented throughout.
        alpha = 1 - self.confidence_level
        p_value = (
            p_value_two_tailed / 2 if t_stat > 0 else 1 - p_value_two_tailed / 2
        )
        is_significant = p_value < alpha and t_stat > 0
        
        # Calculate confidence interval for difference in means
        baseline_mean = np.mean(baseline_results)
        final_mean = np.mean(final_results)
        baseline_var = np.var(baseline_results, ddof=1)
        final_var = np.var(final_results, ddof=1)
        
        n1 = len(baseline_results)
        n2 = len(final_results)
        
        # Critical value for confidence interval
        df = n1 + n2 - 2
        t_critical = stats.t.ppf((1 + self.confidence_level) / 2, df)
        
        # BUG FIX: pooled-variance standard error, matching scipy's
        # equal_var=True t-test above and the Student's df used here --
        # this used to be Welch's (unpooled-variance) SE paired with
        # Student's df, an inconsistent hybrid that is not a valid
        # procedure for either test. (For the equal window sizes this
        # class defaults to, n1 == n2 makes the two formulas coincide
        # numerically, so this was latent rather than currently
        # observable -- but baseline_window/final_window are caller-
        # configurable, so unequal sizes would have produced a
        # confidence interval whose true coverage did not match its
        # claimed confidence_level.)
        pooled_var = ((n1 - 1) * baseline_var + (n2 - 1) * final_var) / df
        se = np.sqrt(pooled_var * (1 / n1 + 1 / n2))
        
        # Confidence interval for difference
        diff = final_mean - baseline_mean
        margin = t_critical * se
        ci = (diff - margin, diff + margin)
        
        return t_stat, p_value, is_significant, ci
    
    def _calculate_success_by_window(
        self,
        tasks: List[Dict[str, Any]],
        window_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Calculate success rate by window."""
        windows = []
        
        for i in range(0, len(tasks), window_size):
            window_tasks = tasks[i:i + window_size]
            if not window_tasks:
                continue
            
            start_num = window_tasks[0]["task_number"]
            end_num = window_tasks[-1]["task_number"]
            success_rate = self._calculate_success_rate(window_tasks)
            
            windows.append({
                "window": f"Tasks {start_num}-{end_num}",
                "start": start_num,
                "end": end_num,
                "count": len(window_tasks),
                "success_rate": success_rate,
                "success_percentage": success_rate * 100
            })
        
        return windows
    
    def _analyze_failures(
        self,
        tasks: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Analyze failure types."""
        failures = [t for t in tasks if not t["success"]]
        
        failure_counts: Dict[str, int] = {}
        for task in failures:
            failure_type = task.get("failure_type") or "unknown"
            failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1
        
        return failure_counts
    
    def _generate_recommendations(
        self,
        metrics: ImprovementMetrics
    ) -> List[str]:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        if metrics.meets_target:
            recommendations.append(
                f"✅ SUCCESS: Achieved {metrics.improvement_percentage:.1f}% improvement, "
                f"exceeding the 15% target by {(metrics.improvement_percentage - 15):.1f}%"
            )
        else:
            recommendations.append(
                f"❌ FAILURE: Only achieved {metrics.improvement_percentage:.1f}% improvement, "
                f"falling short of 15% target by {(15 - metrics.improvement_percentage):.1f}%"
            )
        
        if metrics.is_significant:
            recommendations.append(
                f"✅ Improvement is statistically significant (p={metrics.p_value:.4f}, "
                f"confidence={metrics.confidence_level*100:.0f}%)"
            )
        else:
            recommendations.append(
                f"⚠️ Improvement is NOT statistically significant (p={metrics.p_value:.4f}). "
                "More data may be needed to confirm improvement."
            )
        
        if metrics.final_success_rate >= 0.8:
            recommendations.append(
                f"✅ Final success rate of {metrics.final_success_rate*100:.1f}% "
                "demonstrates strong performance"
            )
        elif metrics.final_success_rate >= 0.6:
            recommendations.append(
                f"⚠️ Final success rate of {metrics.final_success_rate*100:.1f}% "
                "is acceptable but could be improved"
            )
        else:
            recommendations.append(
                f"❌ Final success rate of {metrics.final_success_rate*100:.1f}% "
                "is below acceptable threshold"
            )
        
        return recommendations
    
    def generate_report_json(self, report: VerificationReport) -> str:
        """Generate JSON report."""
        
        def convert_numpy(obj):
            """Convert numpy types to Python types."""
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            return obj
        
        return json.dumps({
            "timestamp": report.timestamp.isoformat(),
            "database_path": report.database_path,
            "validation_passed": bool(report.validation_passed),
            "improvement_metrics": {
                "baseline_success_rate": float(report.improvement_metrics.baseline_success_rate),
                "final_success_rate": float(report.improvement_metrics.final_success_rate),
                "absolute_improvement": float(report.improvement_metrics.absolute_improvement),
                "relative_improvement": float(report.improvement_metrics.relative_improvement),
                "improvement_percentage": float(report.improvement_metrics.improvement_percentage),
                "meets_target": bool(report.improvement_metrics.meets_target),
                "target_threshold": float(report.improvement_metrics.target_threshold),
                "t_statistic": float(report.improvement_metrics.t_statistic),
                "p_value": float(report.improvement_metrics.p_value),
                "is_significant": bool(report.improvement_metrics.is_significant),
                "confidence_level": float(report.improvement_metrics.confidence_level),
                "confidence_interval": [float(x) for x in report.improvement_metrics.confidence_interval],
                "baseline_sample_size": int(report.improvement_metrics.baseline_sample_size),
                "final_sample_size": int(report.improvement_metrics.final_sample_size),
                "total_tasks": int(report.improvement_metrics.total_tasks),
                "baseline_window": report.improvement_metrics.baseline_window,
                "final_window": report.improvement_metrics.final_window
            },
            "summary": {
                "total_tasks": int(report.total_tasks),
                "successful_tasks": int(report.successful_tasks),
                "failed_tasks": int(report.failed_tasks),
                "overall_success_rate": float(report.overall_success_rate)
            },
            "success_by_window": report.success_by_window,
            "failure_analysis": report.failure_analysis,
            "recommendations": report.recommendations
        }, indent=2)
    
    def generate_report_markdown(self, report: VerificationReport) -> str:
        """Generate Markdown report."""
        m = report.improvement_metrics
        
        status_icon = "✅" if report.validation_passed else "❌"
        status_text = "PASSED" if report.validation_passed else "FAILED"
        
        md = f"""# 15% Improvement Verification Report

**Generated:** {report.timestamp.isoformat()}

**Database:** `{report.database_path}`

## Verification Status

{status_icon} **Verification {status_text}**

{"✅" if m.meets_target else "❌"} {"Meets" if m.meets_target else "Does NOT meet"} 15% improvement target

## Executive Summary

The self-improvement engine was required to demonstrate at least **15% relative improvement** in success rate after 100 tasks (Requirement 7.3).

**Result:** {m.improvement_percentage:.1f}% improvement {"✅ EXCEEDS" if m.meets_target else "❌ BELOW"} target

## Improvement Metrics

### Success Rate Comparison

| Metric | Baseline ({m.baseline_window}) | Final ({m.final_window}) | Change |
|--------|-------------------------------|--------------------------|--------|
| **Success Rate** | {m.baseline_success_rate*100:.1f}% | {m.final_success_rate*100:.1f}% | **{m.absolute_improvement*100:+.1f}%** |
| **Sample Size** | {m.baseline_sample_size} tasks | {m.final_sample_size} tasks | - |

### Improvement Analysis

- **Absolute Improvement:** {m.absolute_improvement*100:+.1f} percentage points
- **Relative Improvement:** {m.relative_improvement*100:+.1f}% ({m.improvement_percentage:.1f}%)
- **Target Threshold:** {m.target_threshold*100:.0f}% minimum
- **Target Achievement:** {(m.improvement_percentage / 15):.2f}x target {"✅" if m.meets_target else "❌"}

## Statistical Significance

### Hypothesis Testing

- **Test:** Independent samples t-test (one-tailed)
- **Null Hypothesis:** No improvement in success rate
- **Alternative Hypothesis:** Success rate improved

### Results

| Statistic | Value | Interpretation |
|-----------|-------|----------------|
| **t-statistic** | {m.t_statistic:.4f} | {"Positive" if m.t_statistic > 0 else "Negative"} change |
| **p-value** | {m.p_value:.4f} | {"Significant" if m.is_significant else "Not significant"} at {m.confidence_level*100:.0f}% confidence |
| **Significance** | {"✅ YES" if m.is_significant else "❌ NO"} | {"Improvement is statistically significant" if m.is_significant else "Improvement is NOT statistically significant"} |
| **Confidence Interval** | [{m.confidence_interval[0]:.4f}, {m.confidence_interval[1]:.4f}] | {m.confidence_level*100:.0f}% CI for difference in means |

## Overall Performance

- **Total Tasks:** {report.total_tasks}
- **Successful:** {report.successful_tasks} ({report.overall_success_rate*100:.1f}%)
- **Failed:** {report.failed_tasks} ({(1-report.overall_success_rate)*100:.1f}%)

## Success Rate Progression

| Window | Tasks | Success Rate |
|--------|-------|-------------|
"""
        
        for window in report.success_by_window:
            md += f"| {window['window']} | {window['count']} | {window['success_percentage']:.1f}% |\n"
        
        md += f"""
## Failure Analysis

Total Failures: {report.failed_tasks}

"""
        
        if report.failure_analysis:
            for failure_type, count in sorted(
                report.failure_analysis.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                percentage = (count / report.failed_tasks * 100) if report.failed_tasks > 0 else 0
                md += f"- **{failure_type}:** {count} failures ({percentage:.1f}%)\n"
        else:
            md += "No failures recorded.\n"
        
        md += "\n## Recommendations\n\n"
        
        for rec in report.recommendations:
            md += f"{rec}\n\n"
        
        md += """## Conclusion

"""
        
        if report.validation_passed:
            md += f"""✅ **The self-improvement engine successfully met the 15% improvement target.**

The system achieved a **{m.improvement_percentage:.1f}% improvement** in success rate, which is **{(m.improvement_percentage / 15):.2f}x the minimum requirement**. This validates Requirement 7.3: "THE Self_Improvement_Engine SHALL demonstrate statistically significant improvement in success rate (minimum 15% relative improvement)."

**Key Evidence:**
- Baseline success rate: {m.baseline_success_rate*100:.1f}% (tasks 1-10)
- Final success rate: {m.final_success_rate*100:.1f}% (tasks 91-100)
- Improvement: {m.improvement_percentage:.1f}% (target: 15%)
- Statistical significance: {"Confirmed" if m.is_significant else "Not confirmed"} (p={m.p_value:.4f})

This demonstrates that **the agent becomes measurably better over time**, fulfilling the core promise of the self-improvement engine.
"""
        else:
            md += f"""❌ **The self-improvement engine did NOT meet the 15% improvement target.**

The system achieved only a **{m.improvement_percentage:.1f}% improvement** in success rate, falling short of the **15% minimum requirement** by **{(15 - m.improvement_percentage):.1f}%**. This fails to validate Requirement 7.3.

**Analysis:**
- Baseline success rate: {m.baseline_success_rate*100:.1f}% (tasks 1-10)
- Final success rate: {m.final_success_rate*100:.1f}% (tasks 91-100)
- Improvement: {m.improvement_percentage:.1f}% (target: 15%)
- Shortfall: {(15 - m.improvement_percentage):.1f}%

**Recommended Actions:**
1. Investigate why improvement was insufficient
2. Review strategy optimization effectiveness
3. Analyze failure patterns for systemic issues
4. Consider adjusting learning parameters
5. Run additional validation cycles
"""
        
        md += f"""
---

**Verification Complete**  
**Status:** {status_icon} {status_text}  
**Date:** {report.timestamp.strftime("%Y-%m-%d")}  
**Version:** 1.0.0
"""
        
        return md


def main():
    """Main verification script."""
    # Find latest validation database
    results_dir = Path("Agent_Guru/self_improvement/validation/results")
    
    if not results_dir.exists():
        print("❌ Results directory not found")
        return
    
    # Find latest database
    db_files = list(results_dir.glob("validation_*.db"))
    if not db_files:
        print("❌ No validation databases found")
        return
    
    latest_db = max(db_files, key=lambda p: p.stat().st_mtime)
    print(f"📊 Using database: {latest_db}")
    
    # Create verifier
    verifier = ImprovementVerifier(str(latest_db))
    
    # Run verification
    print("🔍 Verifying 15% improvement target...")
    report = verifier.verify_improvement()
    
    # Generate reports
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    # JSON report
    json_path = results_dir / f"improvement_verification_{timestamp}.json"
    with open(json_path, "w", encoding='utf-8') as f:
        f.write(verifier.generate_report_json(report))
    print(f"✅ JSON report: {json_path}")
    
    # Markdown report
    md_path = results_dir / f"improvement_verification_{timestamp}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(verifier.generate_report_markdown(report))
    print(f"✅ Markdown report: {md_path}")
    
    # Print summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    m = report.improvement_metrics
    
    print(f"\n{'✅' if report.validation_passed else '❌'} Validation: {('PASSED' if report.validation_passed else 'FAILED')}")
    print(f"\nBaseline Success Rate: {m.baseline_success_rate*100:.1f}% ({m.baseline_window})")
    print(f"Final Success Rate: {m.final_success_rate*100:.1f}% ({m.final_window})")
    print(f"Improvement: {m.improvement_percentage:.1f}% (target: 15%)")
    print(f"Target Achievement: {(m.improvement_percentage / 15):.2f}x")
    print(f"\nStatistical Significance: {'✅ YES' if m.is_significant else '❌ NO'}")
    print(f"p-value: {m.p_value:.4f}")
    print(f"t-statistic: {m.t_statistic:.4f}")
    
    print("\n" + "="*70)
    
    if report.validation_passed:
        print("\n🎉 SUCCESS! The self-improvement engine met the 15% improvement target!")
    else:
        print("\n⚠️ FAILURE: The self-improvement engine did NOT meet the 15% target.")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
