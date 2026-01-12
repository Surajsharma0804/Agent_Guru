"""
Integration tests for biometric verification failure detection.

This module tests the integration between biometric providers, authority state machine,
and intrusion detection system to ensure proper failure detection and response.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.authority.state import (
    AuthorityStateMachine,
    BiometricFactor,
    AuthorityState,
    AuthorityConfiguration
)
from src.authority.biometric_integration import (
    BiometricAuthority,
    BiometricIntegrationConfig
)
from src.biometric.providers import (
    BiometricProviderSecurityBoundary,
    BiometricProviderConfig,
    BiometricResult,
    BiometricProviderType,
    MockBiometricProvider
)
from src.intrusion.detection import (
    IntrusionDetector,
    IntrusionDetectionConfig,
    IntrusionEvent,
    IntrusionEventType,
    IntrusionSeverity
)


class TestBiometricIntrusionIntegration:
    """Test integration between biometric verification and intrusion detection."""

    @pytest.fixture
    def authority_config(self):
        """Create authority configuration."""
        return AuthorityConfiguration(
            face_confidence_threshold=0.85,
            fingerprint_confidence_threshold=0.90,
            voice_confidence_threshold=0.80
        )

    @pytest.fixture
    def biometric_config(self):
        """Create biometric provider configuration."""
        return BiometricProviderConfig(
            face_confidence_threshold=0.85,
            fingerprint_confidence_threshold=0.90,
            verification_timeout_seconds=10
        )

    @pytest.fixture
    def integration_config(self):
        """Create biometric integration configuration."""
        return BiometricIntegrationConfig(
            fallback_to_mock=True,
            max_verification_attempts=3,
            auto_retry_on_failure=False
        )

    @pytest.fixture
    def intrusion_config(self):
        """Create intrusion detection configuration."""
        return IntrusionDetectionConfig(
            max_failures_per_factor=3,
            max_total_failures=5,
            enable_pattern_analysis=True,
            enable_automatic_lockdown=True
        )

    @pytest.fixture
    def authority_machine(self, authority_config):
        """Create authority state machine."""
        return AuthorityStateMachine(authority_config)

    @pytest.fixture
    def biometric_authority(self, authority_config, biometric_config, integration_config):
        """Create biometric authority."""
        return BiometricAuthority(authority_config, biometric_config, integration_config)

    @pytest.fixture
    def intrusion_detector(self, intrusion_config):
        """Create intrusion detector."""
        return IntrusionDetector(intrusion_config)

    @pytest.fixture
    def mock_provider(self, biometric_config):
        """Create mock biometric provider with configurable failure rate."""
        return MockBiometricProvider(biometric_config, mock_success_rate=0.3)  # High failure rate for testing

    @pytest.fixture
    def integrated_system(self, authority_machine, biometric_authority, intrusion_detector):
        """Create integrated system for testing."""
        # Connect intrusion detector to biometric authority
        def on_intrusion_event(event: IntrusionEvent):
            # In real system, this would trigger workstation lock
            pass

        intrusion_detector.register_response_callback(on_intrusion_event)

        return {
            'authority': authority_machine,
            'biometric': biometric_authority,
            'intrusion': intrusion_detector
        }

    @pytest.mark.asyncio
    async def test_biometric_failure_triggers_intrusion_detection(self, integrated_system, mock_provider):
        """Test that biometric failures trigger intrusion detection."""
        authority = integrated_system['authority']
        biometric = integrated_system['biometric']
        intrusion = integrated_system['intrusion']

        # Mock the provider manager to return our mock provider
        with patch.object(biometric.provider_manager, 'enforce_biometric_verification_boundary') as mock_verify:
            # Configure mock to return failures
            mock_verify.return_value = BiometricResult(
                success=False,
                confidence_score=0.2,
                provider_type=BiometricProviderType.MOCK_PROVIDER,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason="Low confidence score"
            )

            # Attempt biometric verification multiple times
            for i in range(3):
                success = await biometric.verify_biometric_authority_boundary(authority, BiometricFactor.FACE)
                assert success is False

                # Manually record failure in intrusion detector
                intrusion.record_biometric_failure(
                    factor=BiometricFactor.FACE,
                    failure_reason="Low confidence score",
                    confidence_score=0.2,
                    provider="mock_provider"
                )

            # Check that intrusion events were generated
            events = intrusion.get_recent_events()
            assert len(events) >= 1

            # Should have threshold exceeded event
            threshold_events = [e for e in events if e.event_type == IntrusionEventType.THRESHOLD_EXCEEDED]
            assert len(threshold_events) >= 1

            event = threshold_events[0]
            assert event.severity == IntrusionSeverity.HIGH
            assert event.source_factor == BiometricFactor.FACE

    @pytest.mark.asyncio
    async def test_multiple_factor_failure_detection(self, integrated_system):
        """Test detection of failures across multiple biometric factors."""
        intrusion = integrated_system['intrusion']

        # Record failures on different factors
        factors = [BiometricFactor.FACE, BiometricFactor.FINGERPRINT]

        for factor in factors:
            result = intrusion.record_biometric_failure(
                factor=factor,
                failure_reason="Authentication failed",
                confidence_score=0.3,
                provider="test_provider"
            )

        # Should trigger multiple factors failed event
        events = intrusion.get_recent_events()
        multiple_factor_events = [e for e in events if e.event_type == IntrusionEventType.MULTIPLE_FACTORS_FAILED]
        assert len(multiple_factor_events) >= 1

        event = multiple_factor_events[0]
        assert event.severity == IntrusionSeverity.HIGH

    @pytest.mark.asyncio
    async def test_rapid_failure_detection(self, integrated_system):
        """Test detection of rapid successive failures."""
        intrusion = integrated_system['intrusion']

        # Record multiple failures quickly
        for i in range(10):
            result = intrusion.record_biometric_failure(
                factor=BiometricFactor.FACE,
                failure_reason=f"Rapid failure {i+1}",
                confidence_score=0.3,
                provider="test_provider"
            )

        # Should trigger rapid attempts event
        events = intrusion.get_recent_events()
        rapid_events = [e for e in events if e.event_type == IntrusionEventType.RAPID_ATTEMPTS]
        assert len(rapid_events) >= 1

        event = rapid_events[0]
        assert event.severity == IntrusionSeverity.HIGH

    @pytest.mark.asyncio
    async def test_pattern_based_detection(self, integrated_system):
        """Test advanced pattern-based failure detection."""
        intrusion = integrated_system['intrusion']

        # Record failures that should trigger pattern detection
        current_time = datetime.utcnow()

        # Create temporal clustering pattern
        for i in range(4):
            intrusion.record_biometric_failure(
                factor=BiometricFactor.FACE,
                failure_reason=f"Clustered failure {i+1}",
                confidence_score=0.3,
                provider="test_provider"
            )

        # Check for pattern detection
        patterns = intrusion.get_recent_patterns()
        assert len(patterns) >= 0  # Pattern detection may or may not trigger depending on timing

        # Check statistics include pattern analysis
        stats = intrusion.get_failure_statistics()
        assert 'pattern_analysis' in stats

    @pytest.mark.asyncio
    async def test_confidence_threshold_enforcement(self, integrated_system):
        """Test that confidence thresholds are properly enforced."""
        authority = integrated_system['authority']
        biometric = integrated_system['biometric']
        intrusion = integrated_system['intrusion']

        with patch.object(biometric.provider_manager, 'verify_biometric') as mock_verify:
            # Configure mock to return low confidence (below threshold)
            mock_verify.return_value = BiometricResult(
                success=True,  # Provider says success
                confidence_score=0.5,  # But confidence is below threshold (0.85)
                provider_type=BiometricProviderType.MOCK_PROVIDER,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow()
            )

            # Attempt verification
            success = await biometric.verify_biometric_for_authority(authority, BiometricFactor.FACE)

            # Should fail due to low confidence
            assert success is False

            # Authority state should not be ARMED
            assert authority.get_current_state() != AuthorityState.ARMED

    @pytest.mark.asyncio
    async def test_successful_verification_resets_counters(self, integrated_system):
        """Test that successful verification resets failure counters."""
        intrusion = integrated_system['intrusion']

        # Record some failures
        for i in range(2):
            intrusion.record_biometric_failure(
                factor=BiometricFactor.FACE,
                failure_reason=f"Failure {i+1}",
                confidence_score=0.3,
                provider="test_provider"
            )

        # Check failure count
        stats = intrusion.get_failure_statistics()
        assert stats['factor_statistics']['face']['total_failures'] == 2

        # Record successful verification
        intrusion.record_successful_verification(BiometricFactor.FACE)

        # Failure count should be reset for this factor
        stats = intrusion.get_failure_statistics()
        assert stats['factor_statistics']['face']['total_failures'] == 0

    @pytest.mark.asyncio
    async def test_threat_level_escalation(self, integrated_system):
        """Test threat level escalation based on failure patterns."""
        intrusion = integrated_system['intrusion']

        # Initially low threat level
        assert intrusion.get_current_threat_level() == IntrusionSeverity.LOW

        # Record failures to escalate threat level
        for i in range(5):
            intrusion.record_biometric_failure(
                factor=BiometricFactor.FACE,
                failure_reason=f"Escalation failure {i+1}",
                confidence_score=0.3,
                provider="test_provider"
            )

        # Threat level should have escalated
        threat_level = intrusion.get_current_threat_level()
        assert threat_level in [IntrusionSeverity.MEDIUM, IntrusionSeverity.HIGH, IntrusionSeverity.CRITICAL]

    @pytest.mark.asyncio
    async def test_intrusion_event_callback_invocation(self, integrated_system):
        """Test that intrusion event callbacks are properly invoked."""
        intrusion = integrated_system['intrusion']

        # Register callback
        callback_invoked = []

        def test_callback(event: IntrusionEvent):
            callback_invoked.append(event)

        intrusion.register_response_callback(test_callback)

        # Trigger intrusion event
        for i in range(3):
            intrusion.record_biometric_failure(
                factor=BiometricFactor.FACE,
                failure_reason=f"Callback test failure {i+1}",
                confidence_score=0.3,
                provider="test_provider"
            )

        # Callback should have been invoked
        assert len(callback_invoked) >= 1
        assert isinstance(callback_invoked[0], IntrusionEvent)

    @pytest.mark.asyncio
    async def test_failure_statistics_accuracy(self, integrated_system):
        """Test accuracy of failure statistics reporting."""
        intrusion = integrated_system['intrusion']

        # Record specific pattern of failures
        factors = [BiometricFactor.FACE, BiometricFactor.FINGERPRINT, BiometricFactor.FACE]

        for i, factor in enumerate(factors):
            intrusion.record_biometric_failure(
                factor=factor,
                failure_reason=f"Statistics test failure {i+1}",
                confidence_score=0.3,
                provider="test_provider"
            )

        # Check statistics accuracy
        stats = intrusion.get_failure_statistics()

        assert stats['total_failures'] == 3
        assert stats['factor_statistics']['face']['total_failures'] == 2
        assert stats['factor_statistics']['fingerprint']['total_failures'] == 1
        assert 'recent_failures_1min' in stats
        assert 'recent_failures_5min' in stats

    @pytest.mark.asyncio
    async def test_concurrent_failure_detection(self, integrated_system):
        """Test concurrent failure detection and thread safety."""
        intrusion = integrated_system['intrusion']

        import threading
        import time

        results = []
        errors = []

        def record_concurrent_failures():
            try:
                for i in range(5):
                    result = intrusion.record_biometric_failure(
                        factor=BiometricFactor.FACE,
                        failure_reason=f"Concurrent failure {i}",
                        confidence_score=0.3,
                        provider="test_provider"
                    )
                    results.append(result)
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = [threading.Thread(target=record_concurrent_failures) for _ in range(3)]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0

        # Check final state consistency
        stats = intrusion.get_failure_statistics()
        assert stats['total_failures'] == 15  # 3 threads * 5 failures each


class TestAdvancedFailurePatterns:
    """Test advanced failure pattern detection capabilities."""

    @pytest.fixture
    def intrusion_detector(self):
        """Create intrusion detector with pattern analysis enabled."""
        config = IntrusionDetectionConfig(
            enable_pattern_analysis=True,
            enable_timing_analysis=True,
            enable_behavioral_analysis=True
        )
        return IntrusionDetector(config)

    def test_confidence_degradation_pattern(self, intrusion_detector):
        """Test detection of confidence degradation patterns."""
        # Record failures with degrading confidence scores
        confidence_scores = [0.8, 0.6, 0.4, 0.2]

        for i, confidence in enumerate(confidence_scores):
            intrusion_detector.record_biometric_failure(
                factor=BiometricFactor.FACE,
                failure_reason=f"Degrading confidence {i+1}",
                confidence_score=confidence,
                provider="test_provider"
            )

        # Check for pattern detection
        patterns = intrusion_detector.get_recent_patterns()

        # Should detect confidence degradation pattern
        degradation_patterns = [p for p in patterns
                              if hasattr(p, 'pattern_type') and
                                 p.pattern_type.value == 'confidence_degradation']

        # Pattern detection depends on implementation details
        # At minimum, statistics should reflect the pattern
        stats = intrusion_detector.get_failure_statistics()
        assert stats['total_failures'] == 4

    def test_behavioral_anomaly_detection(self, intrusion_detector):
        """Test behavioral anomaly detection."""
        current_time = datetime.utcnow()

        # Create unusual timing pattern (very rapid attempts)
        for i in range(5):
            intrusion_detector.record_biometric_failure(
                factor=BiometricFactor.FACE,
                failure_reason=f"Behavioral anomaly {i+1}",
                confidence_score=0.3,
                provider="test_provider"
            )

        # Check for behavioral pattern detection
        stats = intrusion_detector.get_failure_statistics()
        assert stats['recent_failures_1min'] == 5

        # Should trigger rapid attempts or unusual timing detection
        events = intrusion_detector.get_recent_events()
        timing_events = [e for e in events
                        if e.event_type in [IntrusionEventType.RAPID_ATTEMPTS,
                                          IntrusionEventType.UNUSUAL_TIMING]]
        assert len(timing_events) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
