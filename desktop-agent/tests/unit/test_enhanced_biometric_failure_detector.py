"""
Unit tests for enhanced biometric failure detector.

This module tests the sophisticated biometric verification failure detection,
pattern analysis, and integration capabilities of the enhanced failure detector.
"""

import pytest
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.intrusion.biometric_failure_detector import (
    EnhancedBiometricFailureDetector,
    BiometricFailureEvent,
    BiometricFailureType,
    BiometricFailureSeverity,
    BiometricFailureDetectionConfig,
    create_enhanced_biometric_failure_detector
)
from src.intrusion.detection import (
    IntrusionDetector,
    IntrusionDetectionConfig
)
from src.authority.state import BiometricFactor
from src.biometric.providers import (
    BiometricResult,
    BiometricProviderType
)


class TestBiometricFailureDetectionConfig:
    """Test biometric failure detection configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = BiometricFailureDetectionConfig()
        
        assert config.low_confidence_threshold == 0.5
        assert config.suspicious_failure_rate == 0.7
        assert config.malicious_failure_rate == 1.5
        assert config.enable_adaptive_thresholds is True
        assert config.enable_spoofing_detection is True
        assert config.integrate_with_intrusion_detector is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = BiometricFailureDetectionConfig(
            low_confidence_threshold=0.3,
            suspicious_failure_rate=1.0,
            enable_adaptive_thresholds=False,
            baseline_learning_period_hours=48
        )
        
        assert config.low_confidence_threshold == 0.3
        assert config.suspicious_failure_rate == 1.0
        assert config.enable_adaptive_thresholds is False
        assert config.baseline_learning_period_hours == 48


class TestEnhancedBiometricFailureDetector:
    """Test enhanced biometric failure detector functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BiometricFailureDetectionConfig(
            suspicious_failure_rate=0.5,  # Lower threshold for testing
            malicious_failure_rate=1.0,
            enable_adaptive_thresholds=True,
            enable_spoofing_detection=True
        )
    
    @pytest.fixture
    def intrusion_detector(self):
        """Create intrusion detector for integration testing."""
        return IntrusionDetector(IntrusionDetectionConfig())
    
    @pytest.fixture
    def failure_detector(self, config, intrusion_detector):
        """Create enhanced failure detector for testing."""
        return EnhancedBiometricFailureDetector(config, intrusion_detector)
    
    @pytest.fixture
    def sample_biometric_result(self):
        """Create sample biometric result for testing."""
        return BiometricResult(
            success=False,
            confidence_score=0.3,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow(),
            failure_reason="Low confidence score",
            session_id="test_session_123"
        )
    
    def test_detector_initialization(self, failure_detector):
        """Test detector initialization."""
        assert failure_detector.config.suspicious_failure_rate == 0.5
        assert failure_detector.intrusion_detector is not None
        assert failure_detector._monitoring_active is True
        assert len(failure_detector._failure_events) == 0
    
    def test_factory_function(self):
        """Test factory function."""
        detector = create_enhanced_biometric_failure_detector()
        assert isinstance(detector, EnhancedBiometricFailureDetector)
        assert detector.config.suspicious_failure_rate == 0.7  # Default value
    
    def test_analyze_biometric_failure_basic(self, failure_detector, sample_biometric_result):
        """Test basic biometric failure analysis."""
        failure_event = failure_detector.analyze_biometric_failure(sample_biometric_result)
        
        assert isinstance(failure_event, BiometricFailureEvent)
        assert failure_event.factor == BiometricFactor.FACE
        assert failure_event.failure_type == BiometricFailureType.LOW_CONFIDENCE
        assert failure_event.confidence_score == 0.3
        assert failure_event.provider_type == BiometricProviderType.WINDOWS_HELLO
        assert failure_event.session_id == "test_session_123"
    
    def test_failure_type_classification(self, failure_detector):
        """Test failure type classification."""
        # Test low confidence classification
        low_confidence_result = BiometricResult(
            success=False,
            confidence_score=0.2,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow(),
            failure_reason="Low confidence"
        )
        
        event = failure_detector.analyze_biometric_failure(low_confidence_result)
        assert event.failure_type == BiometricFailureType.LOW_CONFIDENCE
        
        # Test timeout classification
        timeout_result = BiometricResult(
            success=False,
            confidence_score=0.8,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow(),
            failure_reason="Verification timeout occurred"
        )
        
        event = failure_detector.analyze_biometric_failure(timeout_result)
        assert event.failure_type == BiometricFailureType.TIMEOUT
        
        # Test spoofing detection classification
        spoofing_result = BiometricResult(
            success=False,
            confidence_score=0.8,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow(),
            failure_reason="Spoofing attempt detected"
        )
        
        event = failure_detector.analyze_biometric_failure(spoofing_result)
        assert event.failure_type == BiometricFailureType.SPOOFING_DETECTED
    
    def test_failure_severity_assessment(self, failure_detector):
        """Test failure severity assessment."""
        # Test benign failure
        benign_result = BiometricResult(
            success=False,
            confidence_score=0.3,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow(),
            failure_reason="Low confidence"
        )
        
        event = failure_detector.analyze_biometric_failure(benign_result)
        assert event.failure_severity == BiometricFailureSeverity.BENIGN
        
        # Test critical failure (spoofing)
        critical_result = BiometricResult(
            success=False,
            confidence_score=0.8,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow(),
            failure_reason="Spoofing detected"
        )
        
        event = failure_detector.analyze_biometric_failure(critical_result)
        assert event.failure_severity == BiometricFailureSeverity.CRITICAL
    
    def test_rapid_failure_detection(self, failure_detector):
        """Test detection of rapid successive failures."""
        # Generate rapid failures to trigger malicious classification
        for i in range(5):
            result = BiometricResult(
                success=False,
                confidence_score=0.3,
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Rapid failure {i+1}",
                session_id=f"session_{i}"
            )
            
            event = failure_detector.analyze_biometric_failure(result)
        
        # Last event should be classified as malicious due to high failure rate
        assert event.failure_severity in [BiometricFailureSeverity.MALICIOUS, 
                                        BiometricFailureSeverity.CRITICAL]
    
    def test_successful_verification_analysis(self, failure_detector):
        """Test analysis of successful verification."""
        success_result = BiometricResult(
            success=True,
            confidence_score=0.95,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow(),
            session_id="success_session"
        )
        
        # Should not raise exception
        failure_detector.analyze_successful_verification(success_result)
        
        # Check that behavioral profile was updated
        profile = failure_detector._user_behavior_profile
        assert profile['preferred_factors'][BiometricFactor.FACE] == 1
        assert 'face' in profile['typical_confidence_ranges']
        assert 0.95 in profile['typical_confidence_ranges']['face']
    
    def test_failure_analysis_report(self, failure_detector, sample_biometric_result):
        """Test failure analysis report generation."""
        # Generate some failures
        for i in range(3):
            result = BiometricResult(
                success=False,
                confidence_score=0.3 + (i * 0.1),
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Test failure {i+1}",
                session_id=f"test_session_{i}"
            )
            failure_detector.analyze_biometric_failure(result)
        
        report = failure_detector.get_failure_analysis_report()
        
        assert 'total_failure_events' in report
        assert 'recent_failures' in report
        assert 'failure_type_distribution' in report
        assert 'severity_distribution' in report
        assert 'factor_analysis' in report
        assert 'provider_analysis' in report
        assert 'behavioral_analysis' in report
        assert 'current_threat_assessment' in report
        
        assert report['total_failure_events'] == 3
        assert 'face' in report['factor_analysis']
        assert report['factor_analysis']['face']['failure_count'] == 3
    
    def test_recent_failure_events(self, failure_detector, sample_biometric_result):
        """Test recent failure events retrieval."""
        # Initially no events
        events = failure_detector.get_recent_failure_events()
        assert len(events) == 0
        
        # Add some failures
        for i in range(5):
            result = BiometricResult(
                success=False,
                confidence_score=0.3,
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Test failure {i+1}",
                session_id=f"test_session_{i}"
            )
            failure_detector.analyze_biometric_failure(result)
        
        events = failure_detector.get_recent_failure_events(limit=3)
        assert len(events) == 3
        assert all(isinstance(event, BiometricFailureEvent) for event in events)
        
        # Should be in reverse chronological order (most recent first)
        assert events[0].failure_reason == "Test failure 5"
        assert events[1].failure_reason == "Test failure 4"
        assert events[2].failure_reason == "Test failure 3"
    
    def test_reset_failure_tracking(self, failure_detector, sample_biometric_result):
        """Test failure tracking reset."""
        # Add some failures
        for i in range(3):
            result = BiometricResult(
                success=False,
                confidence_score=0.3,
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Test failure {i+1}",
                session_id=f"test_session_{i}"
            )
            failure_detector.analyze_biometric_failure(result)
        
        assert len(failure_detector._failure_events) == 3
        
        # Reset specific factor
        failure_detector.reset_failure_tracking(BiometricFactor.FACE)
        
        # Reset all tracking
        failure_detector.reset_failure_tracking()
        assert len(failure_detector._failure_events) == 0
        assert len(failure_detector._failure_history) == 0
    
    def test_adaptive_thresholds(self, failure_detector):
        """Test adaptive threshold functionality."""
        if not failure_detector.config.enable_adaptive_thresholds:
            pytest.skip("Adaptive thresholds disabled")
        
        # Generate baseline data
        for i in range(15):  # Need enough samples for statistics
            result = BiometricResult(
                success=False,
                confidence_score=0.4 + (i * 0.01),  # Varying confidence scores
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Baseline failure {i+1}",
                session_id=f"baseline_session_{i}"
            )
            failure_detector.analyze_biometric_failure(result)
        
        # Check that adaptive thresholds were calculated
        report = failure_detector.get_failure_analysis_report()
        adaptive_status = report.get('adaptive_thresholds', {})
        
        assert 'learning_progress' in adaptive_status
        assert 'current_thresholds' in adaptive_status
        assert 'baseline_samples' in adaptive_status
    
    def test_intrusion_detector_integration(self, failure_detector):
        """Test integration with intrusion detector."""
        assert failure_detector.intrusion_detector is not None
        
        # Generate suspicious failures
        for i in range(3):
            result = BiometricResult(
                success=False,
                confidence_score=0.1,  # Very low confidence
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Suspicious failure {i+1}",
                session_id=f"suspicious_session_{i}"
            )
            failure_detector.analyze_biometric_failure(result)
        
        # Check that intrusion detector received the failures
        intrusion_stats = failure_detector.intrusion_detector.get_failure_statistics()
        assert intrusion_stats['total_failures'] >= 3
    
    def test_behavioral_profiling(self, failure_detector):
        """Test behavioral profiling functionality."""
        # Add successful verifications at different times
        for hour in [9, 14, 18]:  # Different hours of day
            success_result = BiometricResult(
                success=True,
                confidence_score=0.9,
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow().replace(hour=hour),
                session_id=f"behavioral_session_{hour}"
            )
            failure_detector.analyze_successful_verification(success_result)
        
        # Check behavioral profile
        profile = failure_detector._user_behavior_profile
        assert profile['preferred_factors'][BiometricFactor.FACE] == 3
        assert len(profile['time_of_day_patterns']) >= 1
        
        # Test behavioral anomaly detection
        unusual_time_result = BiometricResult(
            success=False,
            confidence_score=0.3,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow().replace(hour=3),  # Unusual hour
            failure_reason="Unusual time failure",
            session_id="unusual_time_session"
        )
        
        event = failure_detector.analyze_biometric_failure(unusual_time_result)
        # Should potentially be classified as suspicious due to unusual timing
        assert event.failure_severity in [BiometricFailureSeverity.BENIGN, 
                                        BiometricFailureSeverity.SUSPICIOUS]
    
    def test_cross_provider_analysis(self, failure_detector):
        """Test cross-provider failure analysis."""
        providers = [BiometricProviderType.WINDOWS_HELLO, BiometricProviderType.MOCK_PROVIDER]
        
        # Generate failures across different providers
        for i, provider in enumerate(providers * 2):  # 4 failures total
            result = BiometricResult(
                success=False,
                confidence_score=0.3,
                provider_type=provider,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Cross-provider failure {i+1}",
                session_id=f"cross_provider_session_{i}"
            )
            failure_detector.analyze_biometric_failure(result)
        
        # Check provider analysis in report
        report = failure_detector.get_failure_analysis_report()
        provider_analysis = report['provider_analysis']
        
        assert 'windows_hello' in provider_analysis
        assert 'mock_provider' in provider_analysis
        assert provider_analysis['windows_hello']['total_failures'] == 2
        assert provider_analysis['mock_provider']['total_failures'] == 2
    
    def test_confidence_trend_analysis(self, failure_detector):
        """Test confidence trend analysis."""
        # Generate failures with degrading confidence
        confidence_scores = [0.8, 0.6, 0.4, 0.2, 0.1]
        
        for i, confidence in enumerate(confidence_scores):
            result = BiometricResult(
                success=False,
                confidence_score=confidence,
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Degrading confidence {i+1}",
                session_id=f"degrading_session_{i}"
            )
            failure_detector.analyze_biometric_failure(result)
        
        # Check that confidence trends are tracked
        assert len(failure_detector._confidence_trends[BiometricFactor.FACE]) == 5
        
        # Last failure should potentially be classified as suspicious due to trend
        events = failure_detector.get_recent_failure_events(1)
        assert len(events) == 1
        # Severity depends on the specific trend analysis implementation


class TestConcurrency:
    """Test concurrent access and thread safety."""
    
    @pytest.fixture
    def failure_detector(self):
        """Create failure detector for concurrency testing."""
        return EnhancedBiometricFailureDetector()
    
    def test_concurrent_failure_analysis(self, failure_detector):
        """Test concurrent failure analysis."""
        results = []
        errors = []
        
        def analyze_failures():
            try:
                for i in range(10):
                    result = BiometricResult(
                        success=False,
                        confidence_score=0.3,
                        provider_type=BiometricProviderType.WINDOWS_HELLO,
                        factor_type=BiometricFactor.FACE,
                        verification_time=datetime.utcnow(),
                        failure_reason=f"Concurrent failure {i}",
                        session_id=f"concurrent_session_{i}"
                    )
                    
                    event = failure_detector.analyze_biometric_failure(result)
                    results.append(event)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=analyze_failures) for _ in range(3)]
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have no errors
        assert len(errors) == 0
        assert len(results) == 30  # 3 threads * 10 failures each
        
        # Check final state consistency
        assert len(failure_detector._failure_events) == 30
    
    def test_concurrent_report_generation(self, failure_detector):
        """Test concurrent report generation."""
        # Add some baseline failures
        for i in range(5):
            result = BiometricResult(
                success=False,
                confidence_score=0.3,
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Setup failure {i}",
                session_id=f"setup_session_{i}"
            )
            failure_detector.analyze_biometric_failure(result)
        
        reports = []
        errors = []
        
        def generate_reports():
            try:
                for _ in range(10):
                    report = failure_detector.get_failure_analysis_report()
                    reports.append(report)
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=generate_reports) for _ in range(3)]
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have no errors
        assert len(errors) == 0
        assert len(reports) == 30  # 3 threads * 10 reports each
        
        # All reports should be consistent
        for report in reports:
            assert 'total_failure_events' in report
            assert report['total_failure_events'] >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])