"""
Analytics Engine - Advanced Analytics and Trend Analysis

Production-grade analytics system with trend analysis, quality metrics over time,
and comprehensive data processing. Designed for 20+ year operational lifetime with
zero tolerance for data inaccuracies or calculation errors.

MAXIMUM ENGINEERING MANDATE:
- Complete analytics with historical trend analysis
- Quality metrics tracking over time
- Statistical analysis with confidence intervals
- Predictive analytics for quality trends
- Performance requirement: ≤30 seconds for trend analysis
"""

import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats


class TrendDirection(Enum):
    """Trend direction enumeration"""
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"


class MetricCategory(Enum):
    """Metric category enumeration"""
    QUALITY = "QUALITY"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
    COMPLIANCE = "COMPLIANCE"


@dataclass
class MetricDataPoint:
    """Single metric data point"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendAnalysisResult:
    """Trend analysis result"""
    metric_name: str
    category: MetricCategory
    current_value: float
    trend_direction: TrendDirection
    trend_strength: float  # 0.0 to 1.0
    confidence_interval: Tuple[float, float]
    statistical_significance: float  # p-value
    prediction_next_period: float
    historical_average: float
    historical_std_dev: float
    data_points_analyzed: int
    analysis_timestamp: datetime


@dataclass
class QualityMetricsTimeSeries:
    """Quality metrics time series data"""
    compiler_warnings: List[MetricDataPoint] = field(default_factory=list)
    runtime_errors: List[MetricDataPoint] = field(default_factory=list)
    test_pass_rate: List[MetricDataPoint] = field(default_factory=list)
    code_coverage: List[MetricDataPoint] = field(default_factory=list)
    security_vulnerabilities: List[MetricDataPoint] = field(default_factory=list)


@dataclass
class PerformanceMetricsTimeSeries:
    """Performance metrics time series data"""
    phase_transition_latency: List[MetricDataPoint] = field(default_factory=list)
    memory_usage: List[MetricDataPoint] = field(default_factory=list)
    cpu_utilization: List[MetricDataPoint] = field(default_factory=list)
    execution_duration: List[MetricDataPoint] = field(default_factory=list)


@dataclass
class AnalyticsReport:
    """Comprehensive analytics report"""
    report_id: str
    generated_at: datetime
    analysis_period_start: datetime
    analysis_period_end: datetime
    quality_trends: List[TrendAnalysisResult]
    performance_trends: List[TrendAnalysisResult]
    security_trends: List[TrendAnalysisResult]
    compliance_trends: List[TrendAnalysisResult]
    key_insights: List[str]
    recommendations: List[str]
    statistical_summary: Dict[str, Any]


class AnalyticsEngine:
    """
    Analytics Engine - Main Class
    
    Provides comprehensive analytics and trend analysis for audit system metrics.
    """

    def __init__(self, data_directory: Path):
        """
        Initialize analytics engine
        
        Args:
            data_directory: Directory containing historical audit data
        """
        self.data_directory = data_directory
        self.quality_metrics: QualityMetricsTimeSeries = QualityMetricsTimeSeries()
        self.performance_metrics: PerformanceMetricsTimeSeries = PerformanceMetricsTimeSeries()

    def load_historical_data(self, days: int = 90) -> None:
        """
        Load historical audit data for analysis
        
        Args:
            days: Number of days of historical data to load
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Load audit result files from data directory
        for audit_file in self.data_directory.glob("audit-*.json"):
            try:
                with open(audit_file, 'r', encoding='utf-8') as f:
                    audit_data = json.load(f)
                    timestamp = datetime.fromisoformat(audit_data.get('timestamp', datetime.now().isoformat()))
                    
                    if timestamp >= cutoff_date:
                        self._extract_metrics(audit_data, timestamp)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading audit file {audit_file}: {e}")

    def _extract_metrics(self, audit_data: Dict[str, Any], timestamp: datetime) -> None:
        """Extract metrics from audit data"""
        quality_metrics = audit_data.get('qualityMetrics', {})
        performance_metrics = audit_data.get('performanceMetrics', {})
        
        # Extract quality metrics
        if 'compilerWarnings' in quality_metrics:
            self.quality_metrics.compiler_warnings.append(
                MetricDataPoint(timestamp, float(quality_metrics['compilerWarnings']))
            )
        
        if 'runtimeErrors' in quality_metrics:
            self.quality_metrics.runtime_errors.append(
                MetricDataPoint(timestamp, float(quality_metrics['runtimeErrors']))
            )
        
        if 'testPassRate' in quality_metrics:
            self.quality_metrics.test_pass_rate.append(
                MetricDataPoint(timestamp, float(quality_metrics['testPassRate']))
            )
        
        if 'codeCoverage' in quality_metrics:
            self.quality_metrics.code_coverage.append(
                MetricDataPoint(timestamp, float(quality_metrics['codeCoverage']))
            )
        
        if 'securityVulnerabilities' in quality_metrics:
            self.quality_metrics.security_vulnerabilities.append(
                MetricDataPoint(timestamp, float(quality_metrics['securityVulnerabilities']))
            )
        
        # Extract performance metrics
        if 'executionDuration' in performance_metrics:
            self.performance_metrics.execution_duration.append(
                MetricDataPoint(timestamp, float(performance_metrics['executionDuration']))
            )

    def analyze_trends(self) -> AnalyticsReport:
        """
        Perform comprehensive trend analysis
        
        Returns:
            Comprehensive analytics report with trend analysis
        """
        start_time = datetime.now()
        
        # Analyze quality trends
        quality_trends = [
            self._analyze_metric_trend(
                "Compiler Warnings",
                MetricCategory.QUALITY,
                self.quality_metrics.compiler_warnings,
                lower_is_better=True
            ),
            self._analyze_metric_trend(
                "Runtime Errors",
                MetricCategory.QUALITY,
                self.quality_metrics.runtime_errors,
                lower_is_better=True
            ),
            self._analyze_metric_trend(
                "Test Pass Rate",
                MetricCategory.QUALITY,
                self.quality_metrics.test_pass_rate,
                lower_is_better=False
            ),
            self._analyze_metric_trend(
                "Code Coverage",
                MetricCategory.QUALITY,
                self.quality_metrics.code_coverage,
                lower_is_better=False
            ),
            self._analyze_metric_trend(
                "Security Vulnerabilities",
                MetricCategory.SECURITY,
                self.quality_metrics.security_vulnerabilities,
                lower_is_better=True
            ),
        ]
        
        # Analyze performance trends
        performance_trends = [
            self._analyze_metric_trend(
                "Execution Duration",
                MetricCategory.PERFORMANCE,
                self.performance_metrics.execution_duration,
                lower_is_better=True
            ),
        ]
        
        # Generate key insights
        key_insights = self._generate_key_insights(quality_trends, performance_trends)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(quality_trends, performance_trends)
        
        # Generate statistical summary
        statistical_summary = self._generate_statistical_summary(quality_trends, performance_trends)
        
        # Create analytics report
        report = AnalyticsReport(
            report_id=self._generate_report_id(),
            generated_at=datetime.now(),
            analysis_period_start=self._get_earliest_timestamp(),
            analysis_period_end=datetime.now(),
            quality_trends=[t for t in quality_trends if t is not None],
            performance_trends=[t for t in performance_trends if t is not None],
            security_trends=[],
            compliance_trends=[],
            key_insights=key_insights,
            recommendations=recommendations,
            statistical_summary=statistical_summary
        )
        
        # Check performance requirement
        duration = (datetime.now() - start_time).total_seconds()
        if duration > 30:
            print(f"Warning: Trend analysis exceeded performance requirement: {duration}s > 30s")
        
        return report

    def _analyze_metric_trend(
        self,
        metric_name: str,
        category: MetricCategory,
        data_points: List[MetricDataPoint],
        lower_is_better: bool = True
    ) -> Optional[TrendAnalysisResult]:
        """
        Analyze trend for a single metric
        
        Args:
            metric_name: Name of the metric
            category: Metric category
            data_points: Historical data points
            lower_is_better: Whether lower values are better
            
        Returns:
            Trend analysis result or None if insufficient data
        """
        if len(data_points) < 2:
            return None
        
        # Sort data points by timestamp
        sorted_points = sorted(data_points, key=lambda p: p.timestamp)
        values = np.array([p.value for p in sorted_points])
        
        # Calculate basic statistics
        current_value = values[-1]
        historical_average = float(np.mean(values))
        historical_std_dev = float(np.std(values))
        
        # Perform linear regression for trend analysis
        x = np.arange(len(values))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
        
        # Determine trend direction
        if abs(slope) < 0.01 * historical_average:  # Less than 1% change
            trend_direction = TrendDirection.STABLE
        elif (slope < 0 and lower_is_better) or (slope > 0 and not lower_is_better):
            trend_direction = TrendDirection.IMPROVING
        else:
            trend_direction = TrendDirection.DECLINING
        
        # Calculate trend strength (0.0 to 1.0)
        trend_strength = min(1.0, abs(r_value))
        
        # Calculate confidence interval (95%)
        confidence_level = 0.95
        degrees_of_freedom = len(values) - 2
        t_value = stats.t.ppf((1 + confidence_level) / 2, degrees_of_freedom)
        margin_of_error = t_value * std_err * np.sqrt(1 + 1/len(values))
        
        prediction_next_period = slope * len(values) + intercept
        confidence_interval = (
            prediction_next_period - margin_of_error,
            prediction_next_period + margin_of_error
        )
        
        return TrendAnalysisResult(
            metric_name=metric_name,
            category=category,
            current_value=current_value,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            confidence_interval=confidence_interval,
            statistical_significance=p_value,
            prediction_next_period=prediction_next_period,
            historical_average=historical_average,
            historical_std_dev=historical_std_dev,
            data_points_analyzed=len(values),
            analysis_timestamp=datetime.now()
        )

    def _generate_key_insights(
        self,
        quality_trends: List[Optional[TrendAnalysisResult]],
        performance_trends: List[Optional[TrendAnalysisResult]]
    ) -> List[str]:
        """Generate key insights from trend analysis"""
        insights = []
        
        # Analyze quality trends
        improving_quality = sum(
            1 for t in quality_trends
            if t and t.trend_direction == TrendDirection.IMPROVING
        )
        declining_quality = sum(
            1 for t in quality_trends
            if t and t.trend_direction == TrendDirection.DECLINING
        )
        
        if improving_quality > declining_quality:
            insights.append(f"Overall quality metrics are improving ({improving_quality} improving vs {declining_quality} declining)")
        elif declining_quality > improving_quality:
            insights.append(f"Overall quality metrics are declining ({declining_quality} declining vs {improving_quality} improving)")
        else:
            insights.append("Overall quality metrics are stable")
        
        # Identify metrics with strong trends
        for trend in quality_trends + performance_trends:
            if trend and trend.trend_strength > 0.8:
                insights.append(
                    f"{trend.metric_name} shows strong {trend.trend_direction.value.lower()} trend "
                    f"(strength: {trend.trend_strength:.2f})"
                )
        
        return insights

    def _generate_recommendations(
        self,
        quality_trends: List[Optional[TrendAnalysisResult]],
        performance_trends: List[Optional[TrendAnalysisResult]]
    ) -> List[str]:
        """Generate recommendations based on trend analysis"""
        recommendations = []
        
        # Check for declining trends
        for trend in quality_trends + performance_trends:
            if trend and trend.trend_direction == TrendDirection.DECLINING:
                recommendations.append(
                    f"Address declining trend in {trend.metric_name} "
                    f"(current: {trend.current_value:.2f}, predicted: {trend.prediction_next_period:.2f})"
                )
        
        # Check for high variability
        for trend in quality_trends + performance_trends:
            if trend and trend.historical_std_dev > 0.2 * trend.historical_average:
                recommendations.append(
                    f"Reduce variability in {trend.metric_name} "
                    f"(std dev: {trend.historical_std_dev:.2f})"
                )
        
        return recommendations

    def _generate_statistical_summary(
        self,
        quality_trends: List[Optional[TrendAnalysisResult]],
        performance_trends: List[Optional[TrendAnalysisResult]]
    ) -> Dict[str, Any]:
        """Generate statistical summary"""
        all_trends = [t for t in quality_trends + performance_trends if t is not None]
        
        return {
            'total_metrics_analyzed': len(all_trends),
            'improving_metrics': sum(1 for t in all_trends if t.trend_direction == TrendDirection.IMPROVING),
            'stable_metrics': sum(1 for t in all_trends if t.trend_direction == TrendDirection.STABLE),
            'declining_metrics': sum(1 for t in all_trends if t.trend_direction == TrendDirection.DECLINING),
            'average_trend_strength': statistics.mean([t.trend_strength for t in all_trends]) if all_trends else 0.0,
            'statistically_significant_trends': sum(1 for t in all_trends if t.statistical_significance < 0.05),
        }

    def _generate_report_id(self) -> str:
        """Generate unique report ID"""
        import uuid
        return str(uuid.uuid4())

    def _get_earliest_timestamp(self) -> datetime:
        """Get earliest timestamp from all metrics"""
        all_timestamps = []
        
        for metric_list in [
            self.quality_metrics.compiler_warnings,
            self.quality_metrics.runtime_errors,
            self.quality_metrics.test_pass_rate,
            self.quality_metrics.code_coverage,
            self.quality_metrics.security_vulnerabilities,
            self.performance_metrics.execution_duration,
        ]:
            if metric_list:
                all_timestamps.extend([p.timestamp for p in metric_list])
        
        return min(all_timestamps) if all_timestamps else datetime.now()

    def export_report(self, report: AnalyticsReport, output_path: Path) -> None:
        """
        Export analytics report to JSON file
        
        Args:
            report: Analytics report to export
            output_path: Output file path
        """
        report_dict = {
            'report_id': report.report_id,
            'generated_at': report.generated_at.isoformat(),
            'analysis_period_start': report.analysis_period_start.isoformat(),
            'analysis_period_end': report.analysis_period_end.isoformat(),
            'quality_trends': [self._trend_to_dict(t) for t in report.quality_trends],
            'performance_trends': [self._trend_to_dict(t) for t in report.performance_trends],
            'security_trends': [self._trend_to_dict(t) for t in report.security_trends],
            'compliance_trends': [self._trend_to_dict(t) for t in report.compliance_trends],
            'key_insights': report.key_insights,
            'recommendations': report.recommendations,
            'statistical_summary': report.statistical_summary,
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2)

    def _trend_to_dict(self, trend: TrendAnalysisResult) -> Dict[str, Any]:
        """Convert trend analysis result to dictionary"""
        return {
            'metric_name': trend.metric_name,
            'category': trend.category.value,
            'current_value': trend.current_value,
            'trend_direction': trend.trend_direction.value,
            'trend_strength': trend.trend_strength,
            'confidence_interval': list(trend.confidence_interval),
            'statistical_significance': trend.statistical_significance,
            'prediction_next_period': trend.prediction_next_period,
            'historical_average': trend.historical_average,
            'historical_std_dev': trend.historical_std_dev,
            'data_points_analyzed': trend.data_points_analyzed,
            'analysis_timestamp': trend.analysis_timestamp.isoformat(),
        }


def main():
    """Main entry point for analytics engine"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python analytics_engine.py <data_directory>")
        sys.exit(1)
    
    data_directory = Path(sys.argv[1])
    if not data_directory.exists():
        print(f"Error: Data directory does not exist: {data_directory}")
        sys.exit(1)
    
    # Initialize analytics engine
    engine = AnalyticsEngine(data_directory)
    
    # Load historical data
    print("Loading historical data...")
    engine.load_historical_data(days=90)
    
    # Perform trend analysis
    print("Analyzing trends...")
    report = engine.analyze_trends()
    
    # Export report
    output_path = data_directory / f"analytics-report-{report.report_id}.json"
    engine.export_report(report, output_path)
    
    print(f"Analytics report generated: {output_path}")
    print(f"Key insights: {len(report.key_insights)}")
    print(f"Recommendations: {len(report.recommendations)}")


if __name__ == '__main__':
    main()
