"""
Root Cause Investigator for Self-Improvement Engine.

Analyzes correlations between changes and performance degradation to identify
root causes. Provides diagnostic information to help prevent similar issues.

**Validates: Requirements 9.4 (Adversarial Robustness - Root Cause Investigation)**

Performance Requirements:
- Time Complexity: O(n log n) where n is number of changes to analyze
- Space Complexity: O(n) for correlation analysis
- Investigation Latency: <500ms (95th percentile)

Design:
- Correlates changes with performance metrics over time
- Identifies temporal relationships between changes and degradation
- Analyzes change patterns that precede performance drops
- Provides ranked list of likely root causes
- Generates diagnostic reports with actionable insights

Author: Agent Guru Team
Date: 2026-02-28
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.connection_pool import ConnectionPool
    from Agent_Guru.self_improvement.degradation_detector import DegradationAlert


class RootCauseConfidence(Enum):
    """Confidence level in root cause identification."""

    HIGH = "high"  # >80% confidence
    MEDIUM = "medium"  # 50-80% confidence
    LOW = "low"  # <50% confidence


@dataclass
class RootCause:
    """Identified root cause of performance degradation."""

    change_id: str
    component_id: str
    change_type: str
    change_timestamp: datetime
    confidence: RootCauseConfidence
    correlation_score: float  # -1.0 to 1.0
    time_to_degradation_hours: float
    performance_impact: dict[str, float]  # Metric -> impact
    evidence: list[str]  # Supporting evidence
    recommendation: str  # What to do about it


@dataclass
class RootCauseReport:
    """Complete root cause analysis report."""

    investigation_timestamp: datetime
    degradation_alert_id: str | None
    analysis_window_hours: int
    total_changes_analyzed: int
    likely_root_causes: list[RootCause]  # Ranked by confidence
    contributing_factors: list[str]
    diagnostic_summary: str
    prevention_recommendations: list[str]


class RootCauseInvestigator:
    """
    Investigates root causes of performance degradation.

    Analyzes correlations between changes and performance metrics to identify
    which changes likely caused degradation. Provides diagnostic information
    and recommendations.

    Time Complexity: O(n log n) where n is changes analyzed
    Space Complexity: O(n) for correlation data

    Example:
        >>> investigator = RootCauseInvestigator(pool)
        >>> # Investigate degradation
        >>> report = investigator.investigate_degradation(
        ...     degradation_alert=alert,
        ...     analysis_window_hours=48
        ... )
        >>> print(f"Found {len(report.likely_root_causes)} likely causes")
        >>> for cause in report.likely_root_causes:
        ...     print(f"  - {cause.component_id}: {cause.confidence.value}")
    """

    def __init__(
        self,
        pool: "ConnectionPool",
        min_correlation_threshold: float = 0.5,
        max_time_to_degradation_hours: int = 72,
    ) -> None:
        """
        Initialize root cause investigator.

        Args:
            pool: ConnectionPool for database access
            min_correlation_threshold: Minimum correlation to consider (default: 0.5)
            max_time_to_degradation_hours: Maximum time between change and degradation (default: 72)

        Raises:
            ValueError: If thresholds are invalid
        """
        if not 0.0 <= min_correlation_threshold <= 1.0:
            raise ValueError("min_correlation_threshold must be between 0 and 1")
        if max_time_to_degradation_hours <= 0:
            raise ValueError("max_time_to_degradation_hours must be positive")

        self.pool = pool
        self.min_correlation_threshold = min_correlation_threshold
        self.max_time_to_degradation_hours = max_time_to_degradation_hours

    def investigate_degradation(
        self,
        degradation_alert: "DegradationAlert",
        analysis_window_hours: int = 48,
    ) -> RootCauseReport:
        """
        Investigate root causes of performance degradation.

        Analyzes changes within the analysis window and correlates them with
        performance metrics to identify likely root causes.

        Time Complexity: O(n log n) where n is changes in window
        Performance Target: <500ms

        Args:
            degradation_alert: Alert from degradation detector
            analysis_window_hours: How far back to analyze (default: 48)

        Returns:
            RootCauseReport with identified causes and recommendations

        Example:
            >>> from Agent_Guru.self_improvement.degradation_detector import (
            ...     DegradationDetector
            ... )
            >>> detector = DegradationDetector(pool)
            >>> alert = detector.check_for_degradation()
            >>> if alert:
            ...     report = investigator.investigate_degradation(alert)
            ...     print(report.diagnostic_summary)
        """
        # Get changes within analysis window
        changes = self._get_changes_in_window(
            degradation_alert.detection_timestamp, analysis_window_hours
        )

        if not changes:
            return RootCauseReport(
                investigation_timestamp=datetime.now(),
                degradation_alert_id=None,
                analysis_window_hours=analysis_window_hours,
                total_changes_analyzed=0,
                likely_root_causes=[],
                contributing_factors=["No changes found in analysis window"],
                diagnostic_summary="No changes detected before degradation. Degradation may be due to external factors.",
                prevention_recommendations=[
                    "Monitor external dependencies",
                    "Check for data quality issues",
                    "Review system resource usage",
                ],
            )

        # Analyze each change for correlation with degradation
        root_causes = []
        for change in changes:
            correlation = self._calculate_correlation(change, degradation_alert)

            if abs(correlation) >= self.min_correlation_threshold:
                root_cause = self._create_root_cause(change, degradation_alert, correlation)
                root_causes.append(root_cause)

        # Rank by confidence and correlation
        root_causes.sort(key=lambda rc: (rc.confidence.value, abs(rc.correlation_score)), reverse=True)

        # Identify contributing factors
        contributing_factors = self._identify_contributing_factors(changes, degradation_alert)

        # Generate diagnostic summary
        diagnostic_summary = self._generate_diagnostic_summary(root_causes, contributing_factors)

        # Generate prevention recommendations
        prevention_recommendations = self._generate_prevention_recommendations(
            root_causes, contributing_factors
        )

        return RootCauseReport(
            investigation_timestamp=datetime.now(),
            degradation_alert_id=None,  # Could be added if alerts have IDs
            analysis_window_hours=analysis_window_hours,
            total_changes_analyzed=len(changes),
            likely_root_causes=root_causes,
            contributing_factors=contributing_factors,
            diagnostic_summary=diagnostic_summary,
            prevention_recommendations=prevention_recommendations,
        )

    def investigate_recent_changes(
        self,
        hours: int = 24,
        performance_metrics: dict[str, float] | None = None,
    ) -> RootCauseReport:
        """
        Investigate recent changes without a specific degradation alert.

        Useful for proactive analysis or when degradation is suspected but
        not yet confirmed by detector.

        Time Complexity: O(n log n) where n is changes in window

        Args:
            hours: How far back to analyze
            performance_metrics: Current performance metrics for comparison

        Returns:
            RootCauseReport with analysis of recent changes

        Example:
            >>> # Proactive investigation
            >>> report = investigator.investigate_recent_changes(
            ...     hours=24,
            ...     performance_metrics={"success_rate": 0.75}
            ... )
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        changes = self._get_changes_in_window(datetime.now(), hours)

        if not changes:
            return RootCauseReport(
                investigation_timestamp=datetime.now(),
                degradation_alert_id=None,
                analysis_window_hours=hours,
                total_changes_analyzed=0,
                likely_root_causes=[],
                contributing_factors=["No changes in analysis window"],
                diagnostic_summary="No recent changes detected.",
                prevention_recommendations=[],
            )

        # Analyze changes for potential issues
        suspicious_changes = []
        for change in changes:
            suspicion_score = self._calculate_suspicion_score(change, performance_metrics)

            if suspicion_score > 0.5:
                # Create root cause with suspicion-based confidence
                confidence = (
                    RootCauseConfidence.HIGH
                    if suspicion_score > 0.8
                    else RootCauseConfidence.MEDIUM if suspicion_score > 0.6 else RootCauseConfidence.LOW
                )

                root_cause = RootCause(
                    change_id=change["change_id"],
                    component_id=change["component_id"],
                    change_type=change["change_type"],
                    change_timestamp=datetime.fromisoformat(change["timestamp"]),
                    confidence=confidence,
                    correlation_score=suspicion_score,
                    time_to_degradation_hours=0.0,  # No specific degradation event
                    performance_impact={},
                    evidence=[f"Suspicion score: {suspicion_score:.2f}"],
                    recommendation="Monitor this change closely for performance impact",
                )
                suspicious_changes.append(root_cause)

        suspicious_changes.sort(key=lambda rc: rc.correlation_score, reverse=True)

        return RootCauseReport(
            investigation_timestamp=datetime.now(),
            degradation_alert_id=None,
            analysis_window_hours=hours,
            total_changes_analyzed=len(changes),
            likely_root_causes=suspicious_changes,
            contributing_factors=[],
            diagnostic_summary=f"Analyzed {len(changes)} recent changes. Found {len(suspicious_changes)} potentially risky changes.",
            prevention_recommendations=["Continue monitoring performance metrics", "Consider A/B testing for high-risk changes"],
        )

    def _get_changes_in_window(
        self,
        end_time: datetime,
        hours: int,
    ) -> list[dict[str, Any]]:
        """
        Get all changes within time window.

        Time Complexity: O(n) where n is changes in window

        Args:
            end_time: End of analysis window
            hours: Window size in hours

        Returns:
            List of change records
        """
        import json

        start_time = end_time - timedelta(hours=hours)
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT change_id, change_type, timestamp, component_id,
                       previous_state, new_state, performance_before,
                       performance_after, rolled_back
                FROM change_history
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            """,
                (start_iso, end_iso),
            )

            changes = []
            for row in cursor.fetchall():
                changes.append(
                    {
                        "change_id": row[0],
                        "change_type": row[1],
                        "timestamp": row[2],
                        "component_id": row[3],
                        "previous_state": json.loads(row[4]),
                        "new_state": json.loads(row[5]),
                        "performance_before": json.loads(row[6]),
                        "performance_after": json.loads(row[7]) if row[7] else None,
                        "rolled_back": bool(row[8]),
                    }
                )

            return changes

    def _calculate_correlation(
        self,
        change: dict[str, Any],
        degradation_alert: "DegradationAlert",
    ) -> float:
        """
        Calculate correlation between change and degradation.

        Uses temporal proximity and metric changes to estimate correlation.

        Time Complexity: O(1)

        Args:
            change: Change record
            degradation_alert: Degradation alert

        Returns:
            Correlation score (-1.0 to 1.0)
        """
        # Calculate temporal proximity score
        change_time = datetime.fromisoformat(change["timestamp"])
        time_diff_hours = (degradation_alert.detection_timestamp - change_time).total_seconds() / 3600

        if time_diff_hours < 0 or time_diff_hours > self.max_time_to_degradation_hours:
            return 0.0  # Change is too far from degradation

        # Temporal proximity: closer changes have higher correlation
        temporal_score = 1.0 - (time_diff_hours / self.max_time_to_degradation_hours)

        # Metric change correlation
        metric_correlation = 0.0
        if change["performance_after"]:
            # Compare performance change direction with degradation
            for metric, degradation_change in degradation_alert.metric_changes.items():
                if metric in change["performance_before"] and metric in change["performance_after"]:
                    change_delta = (
                        change["performance_after"][metric] - change["performance_before"][metric]
                    )

                    # If both are negative (degradation), positive correlation
                    # If opposite signs, negative correlation
                    if (change_delta < 0 and degradation_change < 0) or (
                        change_delta > 0 and degradation_change > 0
                    ):
                        metric_correlation += 1.0
                    else:
                        metric_correlation -= 0.5

        # Normalize metric correlation
        num_metrics = len(degradation_alert.metric_changes)
        if num_metrics > 0:
            metric_correlation /= num_metrics

        # Combined correlation (weighted average)
        correlation = 0.6 * temporal_score + 0.4 * metric_correlation

        return max(-1.0, min(1.0, correlation))

    def _create_root_cause(
        self,
        change: dict[str, Any],
        degradation_alert: "DegradationAlert",
        correlation: float,
    ) -> RootCause:
        """
        Create root cause record from change and correlation.

        Time Complexity: O(1)

        Args:
            change: Change record
            degradation_alert: Degradation alert
            correlation: Correlation score

        Returns:
            RootCause object
        """
        # Determine confidence based on correlation strength
        if abs(correlation) > 0.8:
            confidence = RootCauseConfidence.HIGH
        elif abs(correlation) > 0.6:
            confidence = RootCauseConfidence.MEDIUM
        else:
            confidence = RootCauseConfidence.LOW

        # Calculate time to degradation
        change_time = datetime.fromisoformat(change["timestamp"])
        time_to_degradation = (
            degradation_alert.detection_timestamp - change_time
        ).total_seconds() / 3600

        # Calculate performance impact
        performance_impact = {}
        if change["performance_after"]:
            for metric in degradation_alert.metric_changes.keys():
                if metric in change["performance_before"] and metric in change["performance_after"]:
                    impact = change["performance_after"][metric] - change["performance_before"][metric]
                    performance_impact[metric] = impact

        # Generate evidence
        evidence = []
        evidence.append(f"Temporal correlation: {correlation:.2f}")
        evidence.append(f"Time to degradation: {time_to_degradation:.1f} hours")

        if performance_impact:
            for metric, impact in performance_impact.items():
                evidence.append(f"{metric} changed by {impact:+.2%}")

        if change["rolled_back"]:
            evidence.append("This change has been rolled back")

        # Generate recommendation
        if confidence == RootCauseConfidence.HIGH:
            recommendation = f"High confidence this change caused degradation. Review {change['component_id']} implementation."
        elif confidence == RootCauseConfidence.MEDIUM:
            recommendation = f"Moderate confidence. Investigate {change['component_id']} for potential issues."
        else:
            recommendation = f"Low confidence. Monitor {change['component_id']} but may not be root cause."

        return RootCause(
            change_id=change["change_id"],
            component_id=change["component_id"],
            change_type=change["change_type"],
            change_timestamp=change_time,
            confidence=confidence,
            correlation_score=correlation,
            time_to_degradation_hours=time_to_degradation,
            performance_impact=performance_impact,
            evidence=evidence,
            recommendation=recommendation,
        )

    def _identify_contributing_factors(
        self,
        changes: list[dict[str, Any]],
        degradation_alert: "DegradationAlert",
    ) -> list[str]:
        """
        Identify contributing factors beyond individual changes.

        Time Complexity: O(n) where n is number of changes

        Args:
            changes: List of changes
            degradation_alert: Degradation alert

        Returns:
            List of contributing factor descriptions
        """
        factors = []

        # Check for rapid change rate
        if len(changes) > 10:
            factors.append(f"High change rate: {len(changes)} changes in analysis window")

        # Check for multiple changes to same component
        component_counts: dict[str, int] = {}
        for change in changes:
            component_id = change["component_id"]
            component_counts[component_id] = component_counts.get(component_id, 0) + 1

        for component_id, count in component_counts.items():
            if count > 3:
                factors.append(f"Multiple changes to {component_id}: {count} changes")

        # Check for changes without performance_after (untested changes)
        untested_count = sum(1 for c in changes if not c["performance_after"])
        if untested_count > 0:
            factors.append(f"{untested_count} changes deployed without performance validation")

        # Check for rolled back changes (indicates previous issues)
        rolled_back_count = sum(1 for c in changes if c["rolled_back"])
        if rolled_back_count > 0:
            factors.append(f"{rolled_back_count} changes were previously rolled back")

        return factors

    def _generate_diagnostic_summary(
        self,
        root_causes: list[RootCause],
        contributing_factors: list[str],
    ) -> str:
        """
        Generate human-readable diagnostic summary.

        Time Complexity: O(n) where n is root causes

        Args:
            root_causes: Identified root causes
            contributing_factors: Contributing factors

        Returns:
            Diagnostic summary text
        """
        if not root_causes:
            return "No clear root cause identified. Degradation may be due to external factors or data quality issues."

        high_confidence = [rc for rc in root_causes if rc.confidence == RootCauseConfidence.HIGH]
        medium_confidence = [rc for rc in root_causes if rc.confidence == RootCauseConfidence.MEDIUM]

        summary_parts = []

        if high_confidence:
            components = ", ".join(rc.component_id for rc in high_confidence[:3])
            summary_parts.append(
                f"High confidence root cause(s) identified: {components}. "
                f"These changes show strong correlation with performance degradation."
            )

        if medium_confidence:
            components = ", ".join(rc.component_id for rc in medium_confidence[:3])
            summary_parts.append(
                f"Moderate confidence causes: {components}. " f"These changes may have contributed to degradation."
            )

        if contributing_factors:
            summary_parts.append(f"Contributing factors: {'; '.join(contributing_factors[:3])}.")

        return " ".join(summary_parts)

    def _generate_prevention_recommendations(
        self,
        root_causes: list[RootCause],
        contributing_factors: list[str],
    ) -> list[str]:
        """
        Generate recommendations to prevent similar issues.

        Time Complexity: O(n) where n is root causes

        Args:
            root_causes: Identified root causes
            contributing_factors: Contributing factors

        Returns:
            List of prevention recommendations
        """
        recommendations = []

        # Recommendations based on root causes
        if root_causes:
            change_types = set(rc.change_type for rc in root_causes)

            if "strategy_update" in change_types:
                recommendations.append("Implement A/B testing for strategy changes before full deployment")
                recommendations.append("Increase validation window for strategy updates")

            if "prompt_update" in change_types:
                recommendations.append("Add automated prompt quality checks before deployment")
                recommendations.append("Maintain larger validation set for prompt testing")

        # Recommendations based on contributing factors
        for factor in contributing_factors:
            if "High change rate" in factor:
                recommendations.append("Implement rate limiting on changes to prevent rapid deployments")

            if "Multiple changes to" in factor:
                recommendations.append("Avoid multiple changes to same component in short time window")

            if "without performance validation" in factor:
                recommendations.append("Require performance validation before deploying changes")

            if "previously rolled back" in factor:
                recommendations.append("Implement stricter validation for components with rollback history")

        # General recommendations
        if not recommendations:
            recommendations.append("Continue monitoring performance metrics closely")
            recommendations.append("Consider implementing canary deployments for changes")

        return recommendations[:5]  # Limit to top 5 recommendations

    def _calculate_suspicion_score(
        self,
        change: dict[str, Any],
        performance_metrics: dict[str, float] | None,
    ) -> float:
        """
        Calculate suspicion score for a change without confirmed degradation.

        Time Complexity: O(1)

        Args:
            change: Change record
            performance_metrics: Current performance metrics

        Returns:
            Suspicion score (0.0 to 1.0)
        """
        score = 0.0

        # Check if change has performance_after
        if not change["performance_after"]:
            score += 0.3  # Untested changes are suspicious

        # Check if change was rolled back
        if change["rolled_back"]:
            score += 0.4  # Previously problematic

        # Check performance delta if available
        if change["performance_after"] and change["performance_before"]:
            for metric, before_value in change["performance_before"].items():
                if metric in change["performance_after"]:
                    after_value = change["performance_after"][metric]
                    delta = after_value - before_value

                    # Negative change is suspicious
                    if delta < 0:
                        score += min(0.3, abs(delta))

        # Check recency (more recent = more suspicious)
        change_time = datetime.fromisoformat(change["timestamp"])
        hours_ago = (datetime.now() - change_time).total_seconds() / 3600

        if hours_ago < 6:
            score += 0.2
        elif hours_ago < 12:
            score += 0.1

        return min(1.0, score)

    def get_investigation_history(
        self,
        hours: int = 168,  # 7 days
    ) -> list[dict[str, Any]]:
        """
        Get history of root cause investigations.

        This would be implemented if we store investigation results.
        For now, returns empty list as investigations are not persisted.

        Time Complexity: O(1)

        Args:
            hours: How far back to look

        Returns:
            List of investigation records
        """
        # TODO: Implement investigation history storage
        return []
