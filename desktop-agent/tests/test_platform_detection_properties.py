"""
Property-Based Tests for Platform Detection and Backend Factory

Feature: guru-complete-system
Task: 1.7 Write property tests for platform detection

Properties tested:
- Property 113: Automatic Platform Detection
- Property 114: Unsupported Platform Error
- Property 115: Backend Factory Creation

Validates: Requirements 43.1, 43.2, 43.3, 43.4
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import patch
import platform
import sys
import os

# Import PAL modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pal.platform_detector import PlatformDetector
from pal.backend_factory import PlatformBackendFactory
from pal.interfaces import (
    ApplicationController,
    InputAutomation,
    SpeechOutput,
    SpeechInput,
    BiometricAuthenticator,
    SecurityEnforcer,
    PlatformNotSupportedError
)


# Property 113: Automatic Platform Detection
@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_113_platform_detection_returns_correct_identifier(platform_name):
    """
    Property 113: Automatic Platform Detection
    
    For all supported platforms, detect() returns the expected platform identifier.
    
    Validates: Requirements 43.1, 43.2
    """
    SUPPORTED_PLATFORMS = {
        'windows': 'Windows',
        'macos': 'Darwin',
        'android': 'Linux',
        'ios': 'Darwin'
    }
    
    system_name = SUPPORTED_PLATFORMS[platform_name]
    
    with patch('platform.system', return_value=system_name):
        if platform_name == 'android':
            with patch.object(sys, 'getandroidapilevel', return_value=30, create=True):
                result = PlatformDetector.detect()
                assert result == 'android'
        elif platform_name == 'ios':
            with patch.object(sys, 'platform', 'ios', create=True):
                result = PlatformDetector.detect()
                assert result == 'ios'
        else:
            result = PlatformDetector.detect()
            assert result == platform_name


@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_113_platform_detection_is_deterministic(platform_name):
    """
    Property 113: Platform detection is deterministic.
    
    For all platforms, detect() is idempotent.
    
    Validates: Requirements 43.1, 43.2
    """
    SUPPORTED_PLATFORMS = {
        'windows': 'Windows',
        'macos': 'Darwin',
        'android': 'Linux',
        'ios': 'Darwin'
    }
    
    system_name = SUPPORTED_PLATFORMS[platform_name]
    
    with patch('platform.system', return_value=system_name):
        if platform_name == 'android':
            with patch.object(sys, 'getandroidapilevel', return_value=30, create=True):
                result1 = PlatformDetector.detect()
                result2 = PlatformDetector.detect()
                result3 = PlatformDetector.detect()
        elif platform_name == 'ios':
            with patch.object(sys, 'platform', 'ios', create=True):
                result1 = PlatformDetector.detect()
                result2 = PlatformDetector.detect()
                result3 = PlatformDetector.detect()
        else:
            result1 = PlatformDetector.detect()
            result2 = PlatformDetector.detect()
            result3 = PlatformDetector.detect()
        
        assert result1 == result2 == result3 == platform_name



@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_113_platform_info_contains_detected_platform(platform_name):
    """
    Property 113: Platform info matches detected platform.
    
    For all platforms, get_platform_info()['platform'] matches detect().
    
    Validates: Requirements 43.1, 43.2
    """
    SUPPORTED_PLATFORMS = {
        'windows': 'Windows',
        'macos': 'Darwin',
        'android': 'Linux',
        'ios': 'Darwin'
    }
    
    system_name = SUPPORTED_PLATFORMS[platform_name]
    
    with patch('platform.system', return_value=system_name):
        if platform_name == 'android':
            with patch.object(sys, 'getandroidapilevel', return_value=30, create=True):
                info = PlatformDetector.get_platform_info()
                detected = PlatformDetector.detect()
        elif platform_name == 'ios':
            with patch.object(sys, 'platform', 'ios', create=True):
                info = PlatformDetector.get_platform_info()
                detected = PlatformDetector.detect()
        else:
            info = PlatformDetector.get_platform_info()
            detected = PlatformDetector.detect()
        
        assert 'platform' in info
        assert info['platform'] == detected == platform_name


@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_113_platform_helper_methods_consistent(platform_name):
    """
    Property 113: Helper methods are consistent with detect().
    
    For all platforms, exactly one is_*() method returns True.
    
    Validates: Requirements 43.1, 43.2
    """
    SUPPORTED_PLATFORMS = {
        'windows': 'Windows',
        'macos': 'Darwin',
        'android': 'Linux',
        'ios': 'Darwin'
    }
    
    system_name = SUPPORTED_PLATFORMS[platform_name]
    
    with patch('platform.system', return_value=system_name):
        if platform_name == 'android':
            with patch.object(sys, 'getandroidapilevel', return_value=30, create=True):
                is_windows = PlatformDetector.is_windows()
                is_macos = PlatformDetector.is_macos()
                is_android = PlatformDetector.is_android()
                is_ios = PlatformDetector.is_ios()
        elif platform_name == 'ios':
            with patch.object(sys, 'platform', 'ios', create=True):
                is_windows = PlatformDetector.is_windows()
                is_macos = PlatformDetector.is_macos()
                is_android = PlatformDetector.is_android()
                is_ios = PlatformDetector.is_ios()
        else:
            is_windows = PlatformDetector.is_windows()
            is_macos = PlatformDetector.is_macos()
            is_android = PlatformDetector.is_android()
            is_ios = PlatformDetector.is_ios()
        
        # Exactly one should be True
        true_count = sum([is_windows, is_macos, is_android, is_ios])
        assert true_count == 1
        
        # The True one should match detected platform
        if platform_name == 'windows':
            assert is_windows
        elif platform_name == 'macos':
            assert is_macos
        elif platform_name == 'android':
            assert is_android
        elif platform_name == 'ios':
            assert is_ios


# Property 114: Unsupported Platform Error
UNSUPPORTED_PLATFORMS = ['Linux', 'FreeBSD', 'OpenBSD', 'NetBSD', 'SunOS', 'AIX']


@pytest.mark.properties
@settings(max_examples=100)
@given(unsupported_system=st.sampled_from(UNSUPPORTED_PLATFORMS))
def test_property_114_unsupported_platform_raises_error(unsupported_system):
    """
    Property 114: Unsupported Platform Error
    
    For all unsupported platforms, detect() raises PlatformNotSupportedError.
    
    Validates: Requirements 43.3
    """
    with patch('platform.system', return_value=unsupported_system):
        if unsupported_system == 'Linux':
            if hasattr(sys, 'getandroidapilevel'):
                delattr(sys, 'getandroidapilevel')
        
        with pytest.raises(PlatformNotSupportedError) as exc_info:
            PlatformDetector.detect()
        
        error_message = str(exc_info.value)
        assert 'not supported' in error_message.lower()


@pytest.mark.properties
@settings(max_examples=100)
@given(unsupported_system=st.sampled_from(UNSUPPORTED_PLATFORMS))
def test_property_114_unsupported_platform_error_message_is_actionable(unsupported_system):
    """
    Property 114: Error messages are actionable.
    
    For all unsupported platforms, error message lists supported platforms.
    
    Validates: Requirements 43.3
    """
    with patch('platform.system', return_value=unsupported_system):
        if unsupported_system == 'Linux':
            if hasattr(sys, 'getandroidapilevel'):
                delattr(sys, 'getandroidapilevel')
        
        with pytest.raises(PlatformNotSupportedError) as exc_info:
            PlatformDetector.detect()
        
        error_message = str(exc_info.value).lower()
        assert 'windows' in error_message or 'macos' in error_message


@pytest.mark.properties
@settings(max_examples=100)
@given(unsupported_system=st.sampled_from(UNSUPPORTED_PLATFORMS))
def test_property_114_unsupported_platform_helper_methods_return_false(unsupported_system):
    """
    Property 114: Helper methods return False for unsupported platforms.
    
    For all unsupported platforms, all is_*() methods return False.
    
    Validates: Requirements 43.3
    """
    with patch('platform.system', return_value=unsupported_system):
        if unsupported_system == 'Linux':
            if hasattr(sys, 'getandroidapilevel'):
                delattr(sys, 'getandroidapilevel')
        
        assert not PlatformDetector.is_windows()
        assert not PlatformDetector.is_macos()
        assert not PlatformDetector.is_android()
        assert not PlatformDetector.is_ios()
        assert not PlatformDetector.is_desktop()
        assert not PlatformDetector.is_mobile()



# Property 115: Backend Factory Creation
@pytest.mark.properties
@settings(max_examples=100, deadline=None)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_115_factory_creates_all_backends(platform_name):
    """
    Property 115: Backend Factory Creation
    
    For all supported platforms, create_all_backends() returns all 6 backends.
    
    Validates: Requirements 43.4
    """
    factory = PlatformBackendFactory(platform_name)
    backends = factory.create_all_backends()
    
    expected_keys = {
        'application_controller',
        'input_automation',
        'speech_output',
        'speech_input',
        'biometric_authenticator',
        'security_enforcer',
    }
    
    assert set(backends.keys()) == expected_keys
    
    for key, backend in backends.items():
        assert backend is not None, f"Backend '{key}' is None"


@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_115_factory_backends_implement_correct_interfaces(platform_name):
    """
    Property 115: Backends implement correct interfaces.
    
    For all supported platforms, each backend is an instance of its interface.
    
    Validates: Requirements 43.4
    """
    factory = PlatformBackendFactory(platform_name)
    backends = factory.create_all_backends()
    
    assert isinstance(backends['application_controller'], ApplicationController)
    assert isinstance(backends['input_automation'], InputAutomation)
    assert isinstance(backends['speech_output'], SpeechOutput)
    assert isinstance(backends['speech_input'], SpeechInput)
    assert isinstance(backends['biometric_authenticator'], BiometricAuthenticator)
    assert isinstance(backends['security_enforcer'], SecurityEnforcer)


@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_115_factory_individual_backend_creation(platform_name):
    """
    Property 115: Individual backend creation works.
    
    For all supported platforms, each create_*() method returns valid backend.
    
    Validates: Requirements 43.4
    """
    factory = PlatformBackendFactory(platform_name)
    
    app_controller = factory.create_application_controller()
    assert app_controller is not None
    assert isinstance(app_controller, ApplicationController)
    
    input_automation = factory.create_input_automation()
    assert input_automation is not None
    assert isinstance(input_automation, InputAutomation)
    
    speech_output = factory.create_speech_output()
    assert speech_output is not None
    assert isinstance(speech_output, SpeechOutput)
    
    speech_input = factory.create_speech_input()
    assert speech_input is not None
    assert isinstance(speech_input, SpeechInput)
    
    biometric_auth = factory.create_biometric_authenticator()
    assert biometric_auth is not None
    assert isinstance(biometric_auth, BiometricAuthenticator)
    
    security_enforcer = factory.create_security_enforcer()
    assert security_enforcer is not None
    assert isinstance(security_enforcer, SecurityEnforcer)


@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_115_factory_creation_is_deterministic(platform_name):
    """
    Property 115: Factory creation is deterministic.
    
    For all supported platforms, creating same backend multiple times
    produces instances of the same class.
    
    Validates: Requirements 43.4
    """
    factory = PlatformBackendFactory(platform_name)
    
    backend1 = factory.create_application_controller()
    backend2 = factory.create_application_controller()
    backend3 = factory.create_application_controller()
    
    assert type(backend1) == type(backend2) == type(backend3)
    assert backend1 is not backend2
    assert backend2 is not backend3


@pytest.mark.properties
@settings(max_examples=100)
@given(invalid_platform=st.text(min_size=1, max_size=20).filter(
    lambda x: x not in ['windows', 'macos', 'android', 'ios']
))
def test_property_115_factory_rejects_invalid_platforms(invalid_platform):
    """
    Property 115: Factory rejects invalid platforms.
    
    For all invalid platform identifiers, factory raises error.
    
    Validates: Requirements 43.4
    """
    with pytest.raises(PlatformNotSupportedError) as exc_info:
        PlatformBackendFactory(invalid_platform)
    
    error_message = str(exc_info.value)
    assert 'not supported' in error_message.lower()


@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_property_115_factory_platform_attribute_matches_input(platform_name):
    """
    Property 115: Factory platform attribute matches input.
    
    For all supported platforms, factory.platform equals input platform.
    
    Validates: Requirements 43.4
    """
    factory = PlatformBackendFactory(platform_name)
    assert factory.platform == platform_name


# Integration Property: End-to-End
@pytest.mark.properties
@settings(max_examples=100)
@given(platform_name=st.sampled_from(['windows', 'macos', 'android', 'ios']))
def test_integration_detect_then_create_backends(platform_name):
    """
    Integration: Complete flow from detection to backend creation.
    
    For all supported platforms, detecting platform and creating backends
    produces valid implementations.
    
    Validates: Requirements 43.1, 43.2, 43.4
    """
    SUPPORTED_PLATFORMS = {
        'windows': 'Windows',
        'macos': 'Darwin',
        'android': 'Linux',
        'ios': 'Darwin'
    }
    
    system_name = SUPPORTED_PLATFORMS[platform_name]
    
    with patch('platform.system', return_value=system_name):
        if platform_name == 'android':
            with patch.object(sys, 'getandroidapilevel', return_value=30, create=True):
                detected_platform = PlatformDetector.detect()
        elif platform_name == 'ios':
            with patch.object(sys, 'platform', 'ios', create=True):
                detected_platform = PlatformDetector.detect()
        else:
            detected_platform = PlatformDetector.detect()
        
        assert detected_platform == platform_name
        
        factory = PlatformBackendFactory(detected_platform)
        backends = factory.create_all_backends()
        
        assert len(backends) == 6
        assert isinstance(backends['application_controller'], ApplicationController)
        assert isinstance(backends['input_automation'], InputAutomation)
        assert isinstance(backends['speech_output'], SpeechOutput)
        assert isinstance(backends['speech_input'], SpeechInput)
        assert isinstance(backends['biometric_authenticator'], BiometricAuthenticator)
        assert isinstance(backends['security_enforcer'], SecurityEnforcer)
