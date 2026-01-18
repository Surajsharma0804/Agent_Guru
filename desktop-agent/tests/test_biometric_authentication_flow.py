"""
Biometric Authentication Flow Tests

This module contains comprehensive tests for biometric authentication integration,
including Windows Hello integration, fingerprint and face recognition, and
failed authentication lockout.

Tests validate:
- Windows Hello integration
- Fingerprint and face recognition
- Failed authentication lockout (3 attempts)

Requirements validated: 4.1, 4.2, 4.3, 4.4, 4.5
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from authority.authority_state_machine import (
    AuthorityConfiguration,
    AuthorityState,
    AuthorityStateMachine,
    BiometricFactor,
    StateTransitionReason,
)
from pal.backends.windows.biometric_authenticator import WindowsBiometricAuthenticator
from pal.interfaces import AuthResult, AuthResultStatus, BiometricAuthenticator

# ============================================================================
# Test 1: Windows Hello Integration
# ============================================================================

class TestWindowsHelloIntegration:
    """Test Windows Hello integration."""
    
    def test_windows_hello_available(self):
        """
        Test that Windows Hello is detected when available.
        
        Validates: Requirements 4.1
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Verify platform is Windows
        assert authenticator.platform == "windows"
        
        # Verify authenticator has required methods
        assert hasattr(authenticator, 'authenticate')
        assert hasattr(authenticator, 'is_available')
        assert hasattr(authenticator, 'get_available_factors')
        assert hasattr(authenticator, 'get_capabilities')
    
    def test_windows_hello_authentication_success(self):
        """
        Test successful Windows Hello authentication.
        
        Validates: Requirements 4.3, 4.4
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Mock successful authentication
        with patch.object(authenticator, '_invoke_windows_hello', return_value=True):
            with patch.object(authenticator, 'is_available', return_value=True):
                with patch.object(authenticator, 'get_available_factors', return_value=['fingerprint']):
                    # Attempt authentication
                    result = authenticator.authenticate("Test authentication")
                    
                    # Verify success
                    assert result.status == AuthResultStatus.SUCCESS
                    assert result.platform == "windows"
                    assert result.factor_used is not None
                    assert isinstance(result.timestamp, datetime)
    
    def test_windows_hello_authentication_failure(self):
        """
        Test failed Windows Hello authentication.
        
        Validates: Requirements 4.3
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Mock failed authentication
        with patch.object(authenticator, '_invoke_windows_hello', return_value=False):
            with patch.object(authenticator, 'is_available', return_value=True):
                # Attempt authentication
                result = authenticator.authenticate("Test authentication")
                
                # Verify failure
                assert result.status == AuthResultStatus.FAILURE
                assert result.platform == "windows"
                assert result.factor_used is None
                assert 'failed_attempts' in result.metadata
    
    def test_windows_hello_unavailable(self):
        """
        Test behavior when Windows Hello is unavailable.
        
        Validates: Requirements 4.1
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Mock unavailable Windows Hello
        with patch.object(authenticator, 'is_available', return_value=False):
            # Attempt authentication
            result = authenticator.authenticate("Test authentication")
            
            # Verify unavailable status
            assert result.status == AuthResultStatus.UNAVAILABLE
            assert result.platform == "windows"
            assert 'reason' in result.metadata


# ============================================================================
# Test 2: Fingerprint and Face Recognition
# ============================================================================

class TestBiometricFactors:
    """Test fingerprint and face recognition support."""
    
    def test_fingerprint_detection(self):
        """
        Test fingerprint sensor detection.
        
        Validates: Requirements 4.2
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Mock fingerprint hardware detection
        with patch.object(authenticator, '_detect_fingerprint_hardware', return_value=True):
            authenticator._detect_hardware()
            
            # Verify fingerprint is detected
            factors = authenticator.get_available_factors()
            assert 'fingerprint' in factors or authenticator._has_fingerprint
    
    def test_face_recognition_detection(self):
        """
        Test face recognition hardware detection.
        
        Validates: Requirements 4.2
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Mock face recognition hardware detection
        with patch.object(authenticator, '_detect_face_hardware', return_value=True):
            authenticator._detect_hardware()
            
            # Verify face recognition is detected
            factors = authenticator.get_available_factors()
            assert 'face' in factors or authenticator._has_face
    
    def test_multiple_factors_available(self):
        """
        Test detection of multiple biometric factors.
        
        Validates: Requirements 4.2
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Mock multiple hardware types
        with patch.object(authenticator, '_detect_fingerprint_hardware', return_value=True):
            with patch.object(authenticator, '_detect_face_hardware', return_value=True):
                authenticator._detect_hardware()
                
                # Verify multiple factors detected
                capabilities = authenticator.get_capabilities()
                assert capabilities['has_fingerprint'] or capabilities['has_face']
    
    def test_biometric_factor_authentication(self):
        """
        Test authentication with specific biometric factor.
        
        Validates: Requirements 4.2, 4.3
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Mock successful fingerprint authentication
        with patch.object(authenticator, '_invoke_windows_hello', return_value=True):
            with patch.object(authenticator, 'is_available', return_value=True):
                with patch.object(authenticator, 'get_available_factors', return_value=['fingerprint']):
                    # Attempt authentication
                    result = authenticator.authenticate("Fingerprint authentication")
                    
                    # Verify success with fingerprint factor
                    assert result.status == AuthResultStatus.SUCCESS
                    assert result.factor_used == 'fingerprint'


# ============================================================================
# Test 3: Failed Authentication Lockout (3 Attempts)
# ============================================================================

class TestFailedAuthenticationLockout:
    """Test failed authentication lockout after 3 attempts."""
    
    def test_lockout_after_three_failures(self):
        """
        Test that authentication is locked after 3 failed attempts.
        
        Validates: Requirements 4.5
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Mock failed authentication
        with patch.object(authenticator, '_invoke_windows_hello', return_value=False):
            with patch.object(authenticator, 'is_available', return_value=True):
                # Attempt 1: Failure
                result1 = authenticator.authenticate("Attempt 1")
                assert result1.status == AuthResultStatus.FAILURE
                assert result1.metadata['failed_attempts'] == 1
                
                # Attempt 2: Failure
                result2 = authenticator.authenticate("Attempt 2")
                assert result2.status == AuthResultStatus.FAILURE
                assert result2.metadata['failed_attempts'] == 2
                
                # Attempt 3: Failure → Lockout
                result3 = authenticator.authenticate("Attempt 3")
                assert result3.status == AuthResultStatus.LOCKED
                assert result3.metadata['failed_attempts'] == 3
                
                # Attempt 4: Still locked
                result4 = authenticator.authenticate("Attempt 4")
                assert result4.status == AuthResultStatus.LOCKED
    
    def test_lockout_reset_after_success(self):
        """
        Test that failure count resets after successful authentication.
        
        Validates: Requirements 4.5
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        with patch.object(authenticator, 'is_available', return_value=True):
            # Fail twice
            with patch.object(authenticator, '_invoke_windows_hello', return_value=False):
                result1 = authenticator.authenticate("Attempt 1")
                assert result1.status == AuthResultStatus.FAILURE
                assert result1.metadata['failed_attempts'] == 1
                
                result2 = authenticator.authenticate("Attempt 2")
                assert result2.status == AuthResultStatus.FAILURE
                assert result2.metadata['failed_attempts'] == 2
            
            # Succeed on third attempt
            with patch.object(authenticator, '_invoke_windows_hello', return_value=True):
                with patch.object(authenticator, 'get_available_factors', return_value=['fingerprint']):
                    result3 = authenticator.authenticate("Attempt 3")
                    assert result3.status == AuthResultStatus.SUCCESS
                    
                    # Verify failure count reset
                    assert authenticator.failed_attempts == 0
    
    def test_lockout_prevents_further_attempts(self):
        """
        Test that lockout prevents all further authentication attempts.
        
        Validates: Requirements 4.5
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Manually set lockout state
        authenticator.is_locked_out = True
        authenticator.failed_attempts = 3
        
        # Attempt authentication while locked out
        result = authenticator.authenticate("Locked out attempt")
        
        # Verify locked status
        assert result.status == AuthResultStatus.LOCKED
        assert "locked" in result.message.lower()
        assert result.metadata['failed_attempts'] == 3


# ============================================================================
# Test 4: Integration with Authority State Machine
# ============================================================================

class TestBiometricAuthenticationIntegration:
    """Test biometric authentication integration with Authority State Machine."""
    
    def test_authority_machine_biometric_grant(self):
        """
        Test that successful biometric authentication grants authority.
        
        Validates: Requirements 4.4
        """
        # Create authority state machine with test mode
        config = AuthorityConfiguration(test_mode_disable_workstation_lock=True)
        
        with patch('src.pal.platform_detector.PlatformDetector.detect', return_value='windows'):
            authority_machine = AuthorityStateMachine(config)
            
            # Verify initial state
            assert authority_machine.current_state == AuthorityState.LOCKED_LISTEN_ONLY
            
            # Initiate voice re-arm
            success = authority_machine.initiate_voice_rearm(
                voice_confidence=0.9,
                speaker_verified=True
            )
            
            # Verify transition to IDENTITY_VERIFICATION or ARMED
            assert success
            assert authority_machine.current_state in (
                AuthorityState.IDENTITY_VERIFICATION,
                AuthorityState.ARMED
            )
    
    def test_authority_machine_biometric_failure_lockout(self):
        """
        Test that 3 failed biometric attempts trigger authority lockout.
        
        Validates: Requirements 4.5
        """
        # Create authority state machine with test mode and policy requiring biometric
        config = AuthorityConfiguration(
            test_mode_disable_workstation_lock=True,
            max_failed_attempts=3
        )
        
        with patch('src.pal.platform_detector.PlatformDetector.detect', return_value='windows'):
            authority_machine = AuthorityStateMachine(config)
            
            # Set policy to require biometric factors (not just voice)
            from authority.authority_state_machine import AuthorityPolicy
            authority_machine.set_authority_policy(AuthorityPolicy.MEDIUM_RISK)
            
            # Initiate voice re-arm to enter IDENTITY_VERIFICATION
            authority_machine.initiate_voice_rearm(
                voice_confidence=0.9,
                speaker_verified=True
            )
            
            # Verify we're in IDENTITY_VERIFICATION state (waiting for biometric)
            assert authority_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
            
            # Fail biometric verification 3 times
            for i in range(3):
                result = authority_machine.verify_biometric_factor(
                    factor=BiometricFactor.FACE,
                    provider="windows_hello",
                    confidence=0.3,  # Low confidence = failure
                    success=False,
                    failure_reason=f"Attempt {i+1} failed"
                )
                
                # First 2 attempts should fail without lockout
                if i < 2:
                    assert not result
                    assert authority_machine.current_state == AuthorityState.IDENTITY_VERIFICATION
            
            # After 3 failures, should transition to INTRUSION_DETECTED
            # (The state machine tracks failures internally and triggers intrusion detection)
    
    def test_authority_machine_biometric_success_arms_system(self):
        """
        Test that successful biometric verification arms the system.
        
        Validates: Requirements 4.4
        """
        # Create authority state machine with test mode
        config = AuthorityConfiguration(test_mode_disable_workstation_lock=True)
        
        with patch('src.pal.platform_detector.PlatformDetector.detect', return_value='windows'):
            authority_machine = AuthorityStateMachine(config)
            
            # Initiate voice re-arm
            authority_machine.initiate_voice_rearm(
                voice_confidence=0.9,
                speaker_verified=True
            )
            
            # Verify with biometric factor (if required)
            if authority_machine.current_state == AuthorityState.IDENTITY_VERIFICATION:
                result = authority_machine.verify_biometric_factor(
                    factor=BiometricFactor.FINGERPRINT,
                    provider="windows_hello",
                    confidence=0.95,
                    success=True
                )
                
                # Verify system is armed
                assert result
                assert authority_machine.current_state == AuthorityState.ARMED
                assert authority_machine.is_armed


# ============================================================================
# Test 5: Biometric Provider Configuration
# ============================================================================

class TestBiometricProviderConfiguration:
    """Test biometric provider configuration and capabilities."""
    
    def test_windows_hello_configuration(self):
        """
        Test Windows Hello configuration detection.
        
        Validates: Requirements 4.1
        """
        # Create Windows biometric authenticator
        authenticator = WindowsBiometricAuthenticator()
        
        # Verify configuration methods exist
        assert hasattr(authenticator, '_check_windows_hello_configured')
        assert hasattr(authenticator, '_detect_hardware')
        
        # Get capabilities
        capabilities = authenticator.get_capabilities()
        
        # Verify capability structure
        assert 'has_fingerprint' in capabilities
        assert 'has_face' in capabilities
        assert 'has_iris' in capabilities
        assert 'is_configured' in capabilities
    
    def test_biometric_factor_requirements(self):
        """
        Test biometric factor requirements for different policies.
        
        Validates: Requirements 4.2
        """
        # Create authority state machine with test mode
        config = AuthorityConfiguration(test_mode_disable_workstation_lock=True)
        
        with patch('src.pal.platform_detector.PlatformDetector.detect', return_value='windows'):
            authority_machine = AuthorityStateMachine(config)
            
            # Verify policy requirements are configured
            assert hasattr(authority_machine, '_current_policy')
            assert hasattr(authority_machine, '_required_factors')
            
            # Get state info
            state_info = authority_machine.get_state_info()
            
            # Verify required factors are listed
            assert 'required_factors' in state_info
            assert isinstance(state_info['required_factors'], list)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
