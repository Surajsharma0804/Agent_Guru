"""
Property-based tests for Agent_Guru.platform.platform_detector
Uses Hypothesis for property-based testing with 100+ iterations per property

Properties tested:
- Property 1: Platform Detection Correctness
- OS name validation
- Architecture validation
- Version string validation
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import patch

from Agent_Guru.platform.platform_detector import (
    PlatformDetector,
    PlatformInfo,
    UnsupportedPlatformError
)


# Custom strategies for generating valid test data
valid_os_names = st.sampled_from(["Windows", "Darwin", "Linux"])
valid_architectures = st.sampled_from(["x86_64", "AMD64", "amd64", "i386", "i686", "x86", "arm64", "aarch64", "armv7l", "armv8"])
valid_versions = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Nd", "Pc")))
valid_python_versions = st.text(min_size=5, max_size=10, alphabet=st.characters(whitelist_categories=("Nd", "Pc")))
valid_python_implementations = st.sampled_from(["CPython", "PyPy", "Jython", "IronPython"])


class TestPlatformDetectionProperties:
    """Property-based tests for platform detection correctness."""
    
    def setup_method(self):
        """Reset cached platform info before each test."""
        PlatformDetector._cached_platform_info = None
    
    @given(
        os_name=valid_os_names,
        os_version=valid_versions,
        architecture=valid_architectures,
        python_version=valid_python_versions,
        python_implementation=valid_python_implementations
    )
    @settings(max_examples=100)
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_property_1_platform_detection_correctness(
        self,
        mock_is_android,
        os_name,
        os_version,
        architecture,
        python_version,
        python_implementation
    ):
        """
        Feature: guru-platform-integration, Property 1: Platform Detection Correctness
        
        For any mocked platform.system() return value that is "Windows", "Darwin", or "Linux",
        the Platform_Detector should correctly identify the OS and return a PlatformInfo object
        with matching os_name ("Windows", "macOS", or "Linux" respectively).
        
        **Validates: Requirements 1.1, 1.2**
        """
        mock_is_android.return_value = False
        
        with patch('platform.system', return_value=os_name), \
             patch('platform.release', return_value=os_version), \
             patch('platform.machine', return_value=architecture), \
             patch('platform.python_version', return_value=python_version), \
             patch('platform.python_implementation', return_value=python_implementation):
            
            # Reset cache for each iteration
            PlatformDetector._cached_platform_info = None
            
            # Detect platform
            info = PlatformDetector.detect()
            
            # Property: Result should be a PlatformInfo object
            assert isinstance(info, PlatformInfo)
            
            # Property: OS name should be correctly mapped
            if os_name == "Windows":
                assert info.os_name == "Windows"
            elif os_name == "Darwin":
                assert info.os_name == "macOS"
            elif os_name == "Linux":
                assert info.os_name == "Linux"
            
            # Property: OS version should match input
            assert info.os_version == os_version
            
            # Property: Architecture should be normalized
            assert info.architecture in ["x64", "x86", "ARM64", "ARM", architecture.lower()]
            
            # Property: Python version should match input
            assert info.python_version == python_version
            
            # Property: Python implementation should match input
            assert info.python_implementation == python_implementation
    
    @given(os_name=st.sampled_from(["Windows", "Darwin", "Linux"]))
    @settings(max_examples=100)
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_property_os_name_always_valid(
        self,
        mock_is_android,
        mock_impl,
        mock_py_ver,
        mock_machine,
        mock_release,
        os_name
    ):
        """
        Property: OS name is always one of the valid values.
        
        For any supported platform, the detected os_name should be one of:
        "Windows", "macOS", "Linux", "Android", "iOS"
        """
        mock_is_android.return_value = False
        mock_release.return_value = "1.0.0"
        mock_machine.return_value = "x86_64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        with patch('platform.system', return_value=os_name):
            # Reset cache
            PlatformDetector._cached_platform_info = None
            
            info = PlatformDetector.detect()
            
            # Property: OS name must be one of the valid values
            assert info.os_name in ["Windows", "macOS", "Linux", "Android", "iOS"]
    
    @given(architecture=valid_architectures)
    @settings(max_examples=100)
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_property_architecture_normalization(
        self,
        mock_is_android,
        mock_impl,
        mock_py_ver,
        mock_release,
        mock_system,
        architecture
    ):
        """
        Property: Architecture is always normalized to standard values.
        
        For any machine architecture, the detected architecture should be normalized
        to one of: "x64", "x86", "ARM64", "ARM", or the raw value if unknown.
        """
        mock_is_android.return_value = False
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.15.0"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        with patch('platform.machine', return_value=architecture):
            # Reset cache
            PlatformDetector._cached_platform_info = None
            
            info = PlatformDetector.detect()
            
            # Property: Architecture should be normalized or raw value
            arch_lower = architecture.lower()
            if arch_lower in ("x86_64", "amd64"):
                assert info.architecture == "x64"
            elif arch_lower in ("i386", "i686", "x86"):
                assert info.architecture == "x86"
            elif arch_lower in ("arm64", "aarch64"):
                assert info.architecture == "ARM64"
            elif arch_lower.startswith("arm"):
                assert info.architecture == "ARM"
            else:
                assert info.architecture == arch_lower
    
    @given(unsupported_os=st.text(min_size=1, max_size=20).filter(
        lambda x: x not in ["Windows", "Darwin", "Linux", "Java"]
    ))
    @settings(max_examples=100)
    @patch('Agent_Guru.platform.platform_detector._is_ios')
    def test_property_unsupported_platform_raises_error(self, mock_is_ios, unsupported_os):
        """
        Property: Unsupported platforms always raise UnsupportedPlatformError.
        
        For any platform that is not Windows, Darwin, or Linux, the detector
        should raise UnsupportedPlatformError with a descriptive message.
        """
        mock_is_ios.return_value = False
        
        with patch('platform.system', return_value=unsupported_os):
            # Reset cache
            PlatformDetector._cached_platform_info = None
            
            # Property: Should raise UnsupportedPlatformError
            with pytest.raises(UnsupportedPlatformError) as exc_info:
                PlatformDetector.detect()
            
            # Property: Error message should contain platform name
            assert unsupported_os in str(exc_info.value) or "Unsupported platform" in str(exc_info.value)
    
    @given(os_name=st.sampled_from(["Windows", "Darwin", "Linux"]))
    @settings(max_examples=100)
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_property_caching_returns_same_object(
        self,
        mock_is_android,
        mock_impl,
        mock_py_ver,
        mock_machine,
        mock_release,
        os_name
    ):
        """
        Property: Caching always returns the same object.
        
        For any platform, calling detect() multiple times should return
        the exact same object (identity check, not just equality).
        """
        mock_is_android.return_value = False
        mock_release.return_value = "1.0.0"
        mock_machine.return_value = "x86_64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        with patch('platform.system', return_value=os_name):
            # Reset cache
            PlatformDetector._cached_platform_info = None
            
            # First call
            info1 = PlatformDetector.detect()
            
            # Second call
            info2 = PlatformDetector.detect()
            
            # Property: Should be the same object (cached)
            assert info1 is info2
    
    @given(os_name=st.sampled_from(["Windows", "Darwin", "Linux"]))
    @settings(max_examples=100)
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_property_is_methods_consistency(
        self,
        mock_is_android,
        mock_impl,
        mock_py_ver,
        mock_machine,
        mock_release,
        os_name
    ):
        """
        Property: is_* methods are consistent with detect().
        
        For any platform, the is_windows(), is_macos(), is_linux() methods
        should be consistent with the os_name returned by detect().
        """
        mock_is_android.return_value = False
        mock_release.return_value = "1.0.0"
        mock_machine.return_value = "x86_64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        with patch('platform.system', return_value=os_name):
            # Reset cache
            PlatformDetector._cached_platform_info = None
            
            info = PlatformDetector.detect()
            
            # Property: is_* methods should match os_name
            if info.os_name == "Windows":
                assert PlatformDetector.is_windows() is True
                assert PlatformDetector.is_macos() is False
                assert PlatformDetector.is_linux() is False
            elif info.os_name == "macOS":
                assert PlatformDetector.is_windows() is False
                assert PlatformDetector.is_macos() is True
                assert PlatformDetector.is_linux() is False
            elif info.os_name == "Linux":
                assert PlatformDetector.is_windows() is False
                assert PlatformDetector.is_macos() is False
                assert PlatformDetector.is_linux() is True
    
    @given(os_name=st.sampled_from(["Windows", "Darwin", "Linux"]))
    @settings(max_examples=100)
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_property_desktop_mobile_mutually_exclusive(
        self,
        mock_is_android,
        mock_impl,
        mock_py_ver,
        mock_machine,
        mock_release,
        os_name
    ):
        """
        Property: is_desktop() and is_mobile() are mutually exclusive.
        
        For any platform, exactly one of is_desktop() or is_mobile() should be True,
        never both or neither.
        """
        mock_is_android.return_value = False
        mock_release.return_value = "1.0.0"
        mock_machine.return_value = "x86_64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        with patch('platform.system', return_value=os_name):
            # Reset cache
            PlatformDetector._cached_platform_info = None
            
            is_desktop = PlatformDetector.is_desktop()
            is_mobile = PlatformDetector.is_mobile()
            
            # Property: Exactly one should be True (XOR)
            assert is_desktop != is_mobile
            assert (is_desktop and not is_mobile) or (not is_desktop and is_mobile)
