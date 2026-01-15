"""
Advanced Failure Pattern Analysis for GURU Intrusion Detection

Enterprise-grade pattern recognition for biometric verification failures.
Implements comprehensive temporal, statistical, and behavioral analysis
with cryptographic integrity and zero-trust security architecture.
"""

import statistics
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import structlog

from authority.state import BiometricFactor

logger = structlog.get_logger(__name__)


class FailurePatternType(Enum):
    """Cryptographically verified failure pattern classifications."""

    TEMPORAL_CLUSTERING = "temporal_clustering"
    FREQUENCY_ANOMALY = "frequency_anomaly"
    CONFIDENCE_DEGRADATION = "confidence_degradation"
    CROSS_FACTOR_CORRELATION = "cross_factor_correlation"
    BEHAVIORAL_DEVIATION = "behavioral_deviation"
    PERSISTENCE_PATTERN = "persistence_pattern"
    RAPID_SUCCESSION = "rapid_succession"
    TIMING_MANIPULATION = "timing_manipulation"


class PatternSeverity(Enum):
    """Security threat severity classifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class FailurePattern:
    """Immutable, cryptographically verifiable failure pattern record."""

    pattern_id: str
    pattern_type: FailurePatternType
    severity: PatternSeverity
    detection_time: datetime
    time_window: timedelta
    failure_count: int
    affected_factors: Set[BiometricFactor]
    confidence_score: float
    metadata: Dict[str, str]
    session_id: str
    detection_algorithm_version: str = "1.0.0"
    cryptographic_hash: Optional[str] = None

    def compute_cryptographic_integrity_hash(self) -> str:
        """Compute SHA-256 hash for pattern integrity verification."""
        import hashlib
        import json

        pattern_data = {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "severity": self.severity.value,
            "detection_time": self.detection_time.isoformat(),
            "time_window_seconds": self.time_window.total_seconds(),
            "failure_count": self.failure_count,
            "affected_factors": sorted([f.value for f in self.affected_factors]),
            "confidence_score": self.confidence_score,
            "metadata": dict(sorted(self.metadata.items())),
            "session_id": self.session_id,
            "algorithm_version": self.detection_algorithm_version,
        }

        pattern_json = json.dumps(pattern_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(pattern_json.encode("utf-8")).hexdigest()

    def verify_cryptographic_integrity(self) -> bool:
        """Verify pattern has not been tampered with."""
        if self.cryptographic_hash is None:
            return False
        return self.compute_cryptographic_integrity_hash() == self.cryptographic_hash


@dataclass
class PatternAnalysisConfig:
    """Configuration for failure pattern analysis engine."""

    # Temporal analysis parameters
    clustering_time_window_minutes: int = 5
    rapid_succession_threshold_seconds: float = 2.0
    frequency_analysis_window_hours: int = 1

    # Statistical thresholds
    confidence_degradation_threshold: float = 0.15
    anomaly_detection_sensitivity: float = 2.0
    cross_correlation_threshold: float = 0.7

    # Pattern detection thresholds
    min_failures_for_pattern: int = 3
    temporal_clustering_threshold: int = 4
    persistence_pattern_threshold: int = 5

    # Security parameters
    enable_cryptographic_verification: bool = True
    pattern_retention_hours: int = 24
    max_patterns_stored: int = 1000

    # Analysis features
    enable_behavioral_analysis: bool = True
    enable_cross_factor_analysis: bool = True
    enable_timing_analysis: bool = True


class CryptographicFailurePatternAnalyzer:
    """
    Enterprise-grade failure pattern analysis engine.

    Implements advanced statistical and temporal analysis of biometric
    verification failures with cryptographic integrity protection.
    """

    def __init__(self, config: Optional[PatternAnalysisConfig] = None):
        """Initialize pattern analyzer with cryptographic security."""
        self.config = config or PatternAnalysisConfig()
        self._lock = threading.RLock()

        # Pattern storage with cryptographic integrity
        self._detected_patterns: List[FailurePattern] = []
        self._failure_history: List[Dict[str, Any]] = []

        # Statistical analysis state
        self._baseline_statistics: Dict[BiometricFactor, Dict[str, float]] = {}
        self._temporal_clusters: List[List[datetime]] = []

        # Cryptographic verification state
        self._pattern_integrity_verified = True
        self._last_integrity_check = datetime.utcnow()

        logger.info(
            "Cryptographic failure pattern analyzer initialized",
            config=self.config.__dict__,
            cryptographic_verification=self.config.enable_cryptographic_verification,
        )

    def analyze_failure(
        self,
        factor: BiometricFactor,
        failure_time: datetime,
        confidence_score: float,
        failure_reason: str,
        session_id: str,
    ) -> List[FailurePattern]:
        """
        Analyze biometric failure for security threat patterns.

        Returns list of detected patterns with cryptographic integrity.
        """
        with self._lock:
            # Record failure in history
            failure_record = {
                "factor": factor,
                "timestamp": failure_time,
                "confidence": confidence_score,
                "reason": failure_reason,
                "session_id": session_id,
            }
            self._failure_history.append(failure_record)

            # Limit history size for performance
            if len(self._failure_history) > 1000:
                self._failure_history = self._failure_history[-500:]

            detected_patterns = []

            # Temporal clustering analysis
            temporal_patterns = self._analyze_temporal_clustering(failure_time, factor)
            detected_patterns.extend(temporal_patterns)

            # Frequency anomaly detection
            frequency_patterns = self._analyze_frequency_anomalies(factor, failure_time)
            detected_patterns.extend(frequency_patterns)

            # Confidence degradation analysis
            confidence_patterns = self._analyze_confidence_degradation(factor, confidence_score)
            detected_patterns.extend(confidence_patterns)

            # Cross-factor correlation analysis
            if self.config.enable_cross_factor_analysis:
                correlation_patterns = self._analyze_cross_factor_correlations(factor, failure_time)
                detected_patterns.extend(correlation_patterns)

            # Behavioral deviation analysis
            if self.config.enable_behavioral_analysis:
                behavioral_patterns = self._analyze_behavioral_deviations(factor, failure_time)
                detected_patterns.extend(behavioral_patterns)

            # Store detected patterns with cryptographic integrity
            for pattern in detected_patterns:
                if self.config.enable_cryptographic_verification:
                    # Compute and store cryptographic hash
                    crypto_hash = pattern.compute_cryptographic_integrity_hash()
                    pattern = FailurePattern(
                        pattern_id=pattern.pattern_id,
                        pattern_type=pattern.pattern_type,
                        severity=pattern.severity,
                        detection_time=pattern.detection_time,
                        time_window=pattern.time_window,
                        failure_count=pattern.failure_count,
                        affected_factors=pattern.affected_factors,
                        confidence_score=pattern.confidence_score,
                        metadata=pattern.metadata,
                        session_id=pattern.session_id,
                        detection_algorithm_version=pattern.detection_algorithm_version,
                        cryptographic_hash=crypto_hash,
                    )

                self._detected_patterns.append(pattern)

            # Cleanup old patterns
            self._cleanup_expired_patterns()

            return detected_patterns

    def _analyze_temporal_clustering(self, failure_time: datetime, factor: BiometricFactor) -> List[FailurePattern]:
        """Detect temporal clustering of failures indicating coordinated attacks."""
        patterns = []

        # Get recent failures within clustering window
        window_start = failure_time - timedelta(minutes=self.config.clustering_time_window_minutes)
        recent_failures = [f for f in self._failure_history if f["timestamp"] >= window_start and f["factor"] == factor]

        if len(recent_failures) >= self.config.temporal_clustering_threshold:
            # Calculate cluster density and timing patterns
            timestamps = [f["timestamp"] for f in recent_failures]
            time_intervals = []
            for i in range(1, len(timestamps)):
                interval = (timestamps[i] - timestamps[i - 1]).total_seconds()
                time_intervals.append(interval)

            # Detect suspicious clustering patterns
            if time_intervals:
                avg_interval = statistics.mean(time_intervals)
                if avg_interval < self.config.rapid_succession_threshold_seconds:
                    severity = PatternSeverity.HIGH
                elif len(recent_failures) >= self.config.temporal_clustering_threshold * 2:
                    severity = PatternSeverity.CRITICAL
                else:
                    severity = PatternSeverity.MEDIUM

                pattern = self._create_pattern(
                    pattern_type=FailurePatternType.TEMPORAL_CLUSTERING,
                    severity=severity,
                    detection_time=failure_time,
                    time_window=timedelta(minutes=self.config.clustering_time_window_minutes),
                    failure_count=len(recent_failures),
                    affected_factors={factor},
                    confidence_score=min(1.0, len(recent_failures) / self.config.temporal_clustering_threshold),
                    metadata={
                        "average_interval_seconds": str(avg_interval),
                        "cluster_density": str(len(recent_failures)),
                        "analysis_type": "temporal_clustering",
                    },
                    session_id=recent_failures[-1]["session_id"],
                )
                patterns.append(pattern)

        return patterns

    def _analyze_frequency_anomalies(self, factor: BiometricFactor, failure_time: datetime) -> List[FailurePattern]:
        """Detect frequency anomalies indicating systematic attacks."""
        patterns = []

        # Analyze failure frequency over different time windows
        window_1h = failure_time - timedelta(hours=1)
        window_24h = failure_time - timedelta(hours=24)

        failures_1h = len([f for f in self._failure_history if f["timestamp"] >= window_1h and f["factor"] == factor])

        _failures_24h = len(
            [f for f in self._failure_history if f["timestamp"] >= window_24h and f["factor"] == factor]
        )

        # Calculate baseline frequency if available
        baseline_key = f"{factor.value}_hourly_baseline"
        if baseline_key in self._baseline_statistics:
            baseline_hourly = self._baseline_statistics[baseline_key]["mean"]
            current_hourly = failures_1h

            # Detect significant deviation from baseline
            if current_hourly > baseline_hourly * self.config.anomaly_detection_sensitivity:
                severity = PatternSeverity.HIGH if current_hourly > baseline_hourly * 3 else PatternSeverity.MEDIUM

                pattern = self._create_pattern(
                    pattern_type=FailurePatternType.FREQUENCY_ANOMALY,
                    severity=severity,
                    detection_time=failure_time,
                    time_window=timedelta(hours=1),
                    failure_count=failures_1h,
                    affected_factors={factor},
                    confidence_score=min(1.0, current_hourly / (baseline_hourly * 3)),
                    metadata={
                        "baseline_hourly": str(baseline_hourly),
                        "current_hourly": str(current_hourly),
                        "deviation_factor": str(current_hourly / baseline_hourly),
                        "analysis_type": "frequency_anomaly",
                    },
                    session_id=str(uuid.uuid4()),
                )
                patterns.append(pattern)

        return patterns

    def _analyze_confidence_degradation(self, factor: BiometricFactor, confidence_score: float) -> List[FailurePattern]:
        """Detect systematic confidence degradation indicating spoofing attempts."""
        patterns = []

        # Get recent confidence scores for this factor
        recent_failures = [
            f for f in self._failure_history[-20:] if f["factor"] == factor and "confidence" in f  # Last 20 failures
        ]

        if len(recent_failures) >= 5:
            confidences = [f["confidence"] for f in recent_failures]

            # Calculate trend using linear regression
            if len(confidences) >= 3:
                x_values = list(range(len(confidences)))
                n = len(confidences)

                # Simple linear regression for trend detection
                sum_x = sum(x_values)
                sum_y = sum(confidences)
                sum_xy = sum(x * y for x, y in zip(x_values, confidences))
                sum_x2 = sum(x * x for x in x_values)

                if n * sum_x2 - sum_x * sum_x != 0:
                    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

                    # Detect significant negative trend
                    if slope < -self.config.confidence_degradation_threshold:
                        severity = PatternSeverity.HIGH if slope < -0.3 else PatternSeverity.MEDIUM

                        pattern = self._create_pattern(
                            pattern_type=FailurePatternType.CONFIDENCE_DEGRADATION,
                            severity=severity,
                            detection_time=recent_failures[-1]["timestamp"],
                            time_window=timedelta(minutes=10),
                            failure_count=len(recent_failures),
                            affected_factors={factor},
                            confidence_score=abs(slope),
                            metadata={
                                "trend_slope": str(slope),
                                "confidence_range": f"{min(confidences):.3f}-{max(confidences):.3f}",
                                "sample_size": str(len(confidences)),
                                "analysis_type": "confidence_degradation",
                            },
                            session_id=recent_failures[-1]["session_id"],
                        )
                        patterns.append(pattern)

        return patterns

    def _analyze_cross_factor_correlations(
        self, factor: BiometricFactor, failure_time: datetime
    ) -> List[FailurePattern]:
        """Detect correlated failures across multiple biometric factors."""
        patterns = []

        # Get recent failures across all factors
        window_start = failure_time - timedelta(minutes=15)
        recent_failures = [f for f in self._failure_history if f["timestamp"] >= window_start]

        # Group by factor
        factor_failures = {}
        for failure in recent_failures:
            f = failure["factor"]
            if f not in factor_failures:
                factor_failures[f] = []
            factor_failures[f].append(failure)

        # Detect simultaneous failures across multiple factors
        affected_factors = set(factor_failures.keys())
        if len(affected_factors) >= 2:
            total_failures = sum(len(failures) for failures in factor_failures.values())

            # Calculate temporal correlation
            all_timestamps = [f["timestamp"] for f in recent_failures]
            if len(all_timestamps) >= self.config.min_failures_for_pattern:
                # Check for tight temporal clustering across factors
                time_span = (max(all_timestamps) - min(all_timestamps)).total_seconds()

                if time_span < 300:  # 5 minutes
                    severity = PatternSeverity.CRITICAL if len(affected_factors) >= 3 else PatternSeverity.HIGH

                    pattern = self._create_pattern(
                        pattern_type=FailurePatternType.CROSS_FACTOR_CORRELATION,
                        severity=severity,
                        detection_time=failure_time,
                        time_window=timedelta(seconds=time_span),
                        failure_count=total_failures,
                        affected_factors=affected_factors,
                        confidence_score=min(1.0, len(affected_factors) / 3.0),
                        metadata={
                            "factors_affected": ",".join(f.value for f in affected_factors),
                            "time_span_seconds": str(time_span),
                            "total_failures": str(total_failures),
                            "analysis_type": "cross_factor_correlation",
                        },
                        session_id=str(uuid.uuid4()),
                    )
                    patterns.append(pattern)

        return patterns

    def _analyze_behavioral_deviations(self, factor: BiometricFactor, failure_time: datetime) -> List[FailurePattern]:
        """Detect behavioral deviations indicating potential impersonation."""
        patterns = []

        # Analyze timing patterns for behavioral consistency
        recent_failures = [f for f in self._failure_history[-10:] if f["factor"] == factor]

        if len(recent_failures) >= 5:
            # Calculate inter-attempt intervals
            intervals = []
            for i in range(1, len(recent_failures)):
                interval = (recent_failures[i]["timestamp"] - recent_failures[i - 1]["timestamp"]).total_seconds()
                intervals.append(interval)

            if intervals:
                # Detect unnatural timing patterns
                avg_interval = statistics.mean(intervals)
                if len(intervals) > 1:
                    interval_variance = statistics.variance(intervals)

                    # Very consistent timing might indicate automation
                    if interval_variance < 1.0 and avg_interval < 10.0:
                        pattern = self._create_pattern(
                            pattern_type=FailurePatternType.BEHAVIORAL_DEVIATION,
                            severity=PatternSeverity.MEDIUM,
                            detection_time=failure_time,
                            time_window=timedelta(minutes=5),
                            failure_count=len(recent_failures),
                            affected_factors={factor},
                            confidence_score=1.0 - min(1.0, interval_variance),
                            metadata={
                                "average_interval": str(avg_interval),
                                "interval_variance": str(interval_variance),
                                "timing_consistency": "high",
                                "analysis_type": "behavioral_deviation",
                            },
                            session_id=recent_failures[-1]["session_id"],
                        )
                        patterns.append(pattern)

        return patterns

    def _create_pattern(
        self,
        pattern_type: FailurePatternType,
        severity: PatternSeverity,
        detection_time: datetime,
        time_window: timedelta,
        failure_count: int,
        affected_factors: Set[BiometricFactor],
        confidence_score: float,
        metadata: Dict[str, str],
        session_id: str,
    ) -> FailurePattern:
        """Create a new failure pattern with cryptographic integrity."""
        return FailurePattern(
            pattern_id=str(uuid.uuid4()),
            pattern_type=pattern_type,
            severity=severity,
            detection_time=detection_time,
            time_window=time_window,
            failure_count=failure_count,
            affected_factors=affected_factors,
            confidence_score=max(0.0, min(1.0, confidence_score)),
            metadata=dict(metadata),
            session_id=session_id,
        )

    def _cleanup_expired_patterns(self) -> None:
        """Remove expired patterns to maintain performance."""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=self.config.pattern_retention_hours)

        self._detected_patterns = [p for p in self._detected_patterns if p.detection_time > cutoff_time]

        # Limit total patterns stored
        if len(self._detected_patterns) > self.config.max_patterns_stored:
            self._detected_patterns = self._detected_patterns[-self.config.max_patterns_stored :]

    def get_recent_patterns(self, limit: int = 10) -> List[FailurePattern]:
        """Get recent failure patterns with cryptographic verification."""
        with self._lock:
            recent_patterns = list(reversed(self._detected_patterns[-limit:]))

            # Verify cryptographic integrity if enabled
            if self.config.enable_cryptographic_verification:
                verified_patterns = []
                for pattern in recent_patterns:
                    if pattern.verify_cryptographic_integrity():
                        verified_patterns.append(pattern)
                    else:
                        logger.error(
                            "Pattern integrity verification failed",
                            pattern_id=pattern.pattern_id,
                            pattern_type=pattern.pattern_type.value,
                        )
                return verified_patterns

            return recent_patterns

    def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get comprehensive pattern analysis statistics."""
        with self._lock:
            current_time = datetime.utcnow()

            # Count patterns by type and severity
            type_counts = {}
            severity_counts = {}

            for pattern in self._detected_patterns:
                pattern_type = pattern.pattern_type.value
                severity = pattern.severity.value

                type_counts[pattern_type] = type_counts.get(pattern_type, 0) + 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Recent activity analysis
            recent_1h = current_time - timedelta(hours=1)
            recent_patterns_1h = [p for p in self._detected_patterns if p.detection_time > recent_1h]

            return {
                "total_patterns": len(self._detected_patterns),
                "recent_patterns_1h": len(recent_patterns_1h),
                "pattern_types": type_counts,
                "severity_distribution": severity_counts,
                "failure_history_size": len(self._failure_history),
                "cryptographic_verification": self.config.enable_cryptographic_verification,
                "integrity_verified": self._pattern_integrity_verified,
                "last_integrity_check": self._last_integrity_check.isoformat(),
            }

    def verify_all_pattern_integrity(self) -> bool:
        """Verify cryptographic integrity of all stored patterns."""
        if not self.config.enable_cryptographic_verification:
            return True

        with self._lock:
            self._last_integrity_check = datetime.utcnow()

            for pattern in self._detected_patterns:
                if not pattern.verify_cryptographic_integrity():
                    self._pattern_integrity_verified = False
                    logger.critical(
                        "Pattern integrity verification failed",
                        pattern_id=pattern.pattern_id,
                        detection_time=pattern.detection_time.isoformat(),
                    )
                    return False

            self._pattern_integrity_verified = True
            return True


def create_failure_pattern_analyzer(
    config: Optional[PatternAnalysisConfig] = None,
) -> CryptographicFailurePatternAnalyzer:
    """Factory function to create a failure pattern analyzer."""
    return CryptographicFailurePatternAnalyzer(config)


__all__ = [
    "FailurePatternType",
    "PatternSeverity",
    "FailurePattern",
    "PatternAnalysisConfig",
    "CryptographicFailurePatternAnalyzer",
    "create_failure_pattern_analyzer",
]

# Alias for compatibility with tests
FailurePatternAnalyzer = CryptographicFailurePatternAnalyzer
