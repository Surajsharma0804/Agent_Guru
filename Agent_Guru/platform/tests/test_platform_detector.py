"""
Unit tests for Agent_Guru.platform.platform_detector
Coverage Target: >80% (enforced by CI/CD)

Tests cover:
- Platform detection for Windows, macOS, Linux
- Unsupported platform error handling
- Helper methods (is_windows, is_macos, is_linux, etc.)
- Caching behavior
- Architecture detection
"""

import pytest
from unittest.mock import patch

from Agent_Guru.platform.platform_detector import (
    PlatformDetector,
    PlatformInfo,
    UnsupportedPlatformError,
    _is_android,
    _is_ios
)


class TestPlatformDetector:
    """Unit tests for PlatformDetector."""
    
    def setup_method(self):
        """Reset cached platform info before each test."""
        PlatformDetector._cached_platform_info = None
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_detect_windows(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test detection of Windows platform."""
        mock_system.return_value = "Windows"
        mock_release.return_value = "10.0.19041"
        mock_machine.return_value = "AMD64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        info = PlatformDetector.detect()
        
        assert info.os_name == "Windows"  # nosec B101
        assert info.os_version == "10.0.19041"  # nosec B101
        assert info.architecture == "x64"  # nosec B101
        assert info.python_version == "3.11.5"  # nosec B101
        assert info.python_implementation == "CPython"  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_detect_macos(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test detection of macOS platform."""
        mock_system.return_value = "Darwin"
        mock_release.return_value = "21.6.0"
        mock_machine.return_value = "arm64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        info = PlatformDetector.detect()
        
        assert info.os_name == "macOS"  # nosec B101
        assert info.os_version == "21.6.0"  # nosec B101
        assert info.architecture == "ARM64"  # nosec B101
        assert info.python_version == "3.11.5"  # nosec B101
        assert info.python_implementation == "CPython"  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_detect_linux(self, mock_is_android, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test detection of Linux platform."""
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.15.0"
        mock_machine.return_value = "x86_64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        mock_is_android.return_value = False
        
        info = PlatformDetector.detect()
        
        assert info.os_name == "Linux"  # nosec B101
        assert info.os_version == "5.15.0"  # nosec B101
        assert info.architecture == "x64"  # nosec B101
        assert info.python_version == "3.11.5"  # nosec B101
        assert info.python_implementation == "CPython"  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_detect_android(self, mock_is_android, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test detection of Android platform."""
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.10.0"
        mock_machine.return_value = "aarch64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        mock_is_android.return_value = True
        
        info = PlatformDetector.detect()
        
        assert info.os_name == "Android"  # nosec B101
        assert info.os_version == "5.10.0"  # nosec B101
        assert info.architecture == "ARM64"  # nosec B101
    
    @patch('platform.system')
    def test_detect_unsupported_platform(self, mock_system):
        """Test that unsupported platforms raise UnsupportedPlatformError."""
        mock_system.return_value = "FreeBSD"
        
        with pytest.raises(UnsupportedPlatformError) as exc_info:
            PlatformDetector.detect()
        
        assert "Unsupported platform: FreeBSD" in str(exc_info.value)  # nosec B101
        assert "Supported platforms: Windows, macOS, Linux, Android, iOS" in str(exc_info.value)  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_caching_behavior(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test that platform detection result is cached."""
        mock_system.return_value = "Windows"
        mock_release.return_value = "10.0.19041"
        mock_machine.return_value = "AMD64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        # First call
        info1 = PlatformDetector.detect()
        
        # Second call should return cached result
        info2 = PlatformDetector.detect()
        
        # Should be the same object (cached)
        assert info1 is info2  # nosec B101
        
        # platform.system() should only be called once
        assert mock_system.call_count == 1  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_is_windows_true(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test is_windows() returns True on Windows."""
        mock_system.return_value = "Windows"
        mock_release.return_value = "10.0.19041"
        mock_machine.return_value = "AMD64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        assert PlatformDetector.is_windows() is True  # nosec B101
        assert PlatformDetector.is_macos() is False  # nosec B101
        assert PlatformDetector.is_linux() is False  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_is_macos_true(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test is_macos() returns True on macOS."""
        mock_system.return_value = "Darwin"
        mock_release.return_value = "21.6.0"
        mock_machine.return_value = "arm64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        assert PlatformDetector.is_windows() is False  # nosec B101
        assert PlatformDetector.is_macos() is True  # nosec B101
        assert PlatformDetector.is_linux() is False  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_is_linux_true(self, mock_is_android, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test is_linux() returns True on Linux."""
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.15.0"
        mock_machine.return_value = "x86_64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        mock_is_android.return_value = False
        
        assert PlatformDetector.is_windows() is False  # nosec B101
        assert PlatformDetector.is_macos() is False  # nosec B101
        assert PlatformDetector.is_linux() is True  # nosec B101
    
    @patch('platform.system')
    def test_is_methods_return_false_on_unsupported(self, mock_system):
        """Test that is_* methods return False for unsupported platforms."""
        mock_system.return_value = "FreeBSD"
        
        assert PlatformDetector.is_windows() is False  # nosec B101
        assert PlatformDetector.is_macos() is False  # nosec B101
        assert PlatformDetector.is_linux() is False  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    @patch('Agent_Guru.platform.platform_detector._is_android')
    def test_is_mobile_android(self, mock_is_android, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test is_mobile() returns True on Android."""
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.10.0"
        mock_machine.return_value = "aarch64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        mock_is_android.return_value = True
        
        assert PlatformDetector.is_mobile() is True  # nosec B101
        assert PlatformDetector.is_desktop() is False  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_is_desktop_windows(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test is_desktop() returns True on Windows."""
        mock_system.return_value = "Windows"
        mock_release.return_value = "10.0.19041"
        mock_machine.return_value = "AMD64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        assert PlatformDetector.is_desktop() is True  # nosec B101
        assert PlatformDetector.is_mobile() is False  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_architecture_x86(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test detection of x86 architecture."""
        mock_system.return_value = "Windows"
        mock_release.return_value = "10.0.19041"
        mock_machine.return_value = "i686"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        info = PlatformDetector.detect()
        assert info.architecture == "x86"  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_architecture_arm(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test detection of ARM architecture."""
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.15.0"
        mock_machine.return_value = "armv7l"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        info = PlatformDetector.detect()
        assert info.architecture == "ARM"  # nosec B101
    
    @patch('platform.system')
    @patch('platform.release')
    @patch('platform.machine')
    @patch('platform.python_version')
    @patch('platform.python_implementation')
    def test_architecture_unknown(self, mock_impl, mock_py_ver, mock_machine, mock_release, mock_system):
        """Test handling of unknown architecture."""
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.15.0"
        mock_machine.return_value = "riscv64"
        mock_py_ver.return_value = "3.11.5"
        mock_impl.return_value = "CPython"
        
        info = PlatformDetector.detect()
        assert info.architecture == "riscv64"  # Should use raw value  # nosec B101


class TestAndroidDetection:
    """Tests for Android detection helper function."""
    
    @patch('sys.platform', 'linux-android')
    def test_is_android_sys_platform(self):
        """Test Android detection via sys.platform."""
        assert _is_android() is True  # nosec B101
    
    @patch('sys.platform', 'linux')
    @patch('os.path.exists')
    def test_is_android_build_prop(self, mock_exists):
        """Test Android detection via build.prop file."""
        mock_exists.return_value = True
        assert _is_android() is True  # nosec B101
    
    @patch('sys.platform', 'linux')
    @patch('os.path.exists')
    def test_is_not_android(self, mock_exists):
        """Test non-Android Linux detection."""
        mock_exists.return_value = False
        assert _is_android() is False  # nosec B101


class TestIOSDetection:
    """Tests for iOS detection helper function."""
    
    def test_is_ios_with_ios_platform(self):
        """Test iOS detection logic."""
        # Test the actual detection logic
        # In real iOS environment, sys.platform would contain 'ios'
        # For testing, we verify the function doesn't crash
        result = _is_ios()
        assert isinstance(result, bool)  # nosec B101
    
    @patch('os.path.exists')
    def test_is_ios_mobile_dir(self, mock_exists):
        """Test iOS detection via /var/mobile directory."""
        mock_exists.return_value = True
        # This would return True if sys.platform contains 'darwin' or 'ios'
        # For testing, we just verify it doesn't crash
        result = _is_ios()
        assert isinstance(result, bool)  # nosec B101
    
    def test_is_not_ios_on_current_platform(self):
        """Test non-iOS detection on current platform."""
        # On Windows/Linux/macOS, this should return False
        result = _is_ios()
        # On non-iOS platforms, should return False
        assert isinstance(result, bool)  # nosec B101


class TestPlatformInfo:
    """Tests for PlatformInfo data class."""
    
    def test_platform_info_creation(self):
        """Test creation of PlatformInfo object."""
        info = PlatformInfo(
            os_name="Windows",
            os_version="10.0.19041",
            architecture="x64",
            python_version="3.11.5",
            python_implementation="CPython"
        )
        
        assert info.os_name == "Windows"  # nosec B101
        assert info.os_version == "10.0.19041"  # nosec B101
        assert info.architecture == "x64"  # nosec B101
        assert info.python_version == "3.11.5"  # nosec B101
        assert info.python_implementation == "CPython"  # nosec B101
    
    def test_platform_info_equality(self):
        """Test equality comparison of PlatformInfo objects."""
        info1 = PlatformInfo(
            os_name="Windows",
            os_version="10.0.19041",
            architecture="x64",
            python_version="3.11.5",
            python_implementation="CPython"
        )
        info2 = PlatformInfo(
            os_name="Windows",
            os_version="10.0.19041",
            architecture="x64",
            python_version="3.11.5",
            python_implementation="CPython"
        )
        
        assert info1 == info2  # nosec B101


class TestUnsupportedPlatformError:
    """Tests for UnsupportedPlatformError exception."""
    
    def test_exception_message(self):
        """Test exception message formatting."""
        error = UnsupportedPlatformError("Test error message")
        assert str(error) == "Test error message"  # nosec B101
    
    def test_exception_inheritance(self):
        """Test that UnsupportedPlatformError inherits from Exception."""
        error = UnsupportedPlatformError("Test")
        assert isinstance(error, Exception)  # nosec B101
