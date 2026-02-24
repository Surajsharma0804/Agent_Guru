"""
Integration tests for Agent_Guru.platform.platform_detector
Tests real-world usage scenarios and integration with actual platform

These tests run on the actual platform without mocking to verify
real-world behavior.
"""

import pytest
import platform as platform_module

from Agent_Guru.platform.platform_detector import (
    PlatformDetector,
    PlatformInfo,
    UnsupportedPlatformError
)


class TestPlatformDetectorIntegration:
    """Integration tests for platform detection on real system."""
    
    def setup_method(self):
        """Reset cached platform info before each test."""
        PlatformDetector._cached_platform_info = None
    
    def test_detect_current_platform(self):
        """Test detection of current actual platform."""
        info = PlatformDetector.detect()
        
        # Should return valid PlatformInfo
        assert isinstance(info, PlatformInfo)
        
        # OS name should be one of supported platforms
        assert info.os_name in ["Windows", "macOS", "Linux", "Android", "iOS"]
        
        # Version should not be empty
        assert len(info.os_version) > 0
        
        # Architecture should be valid
        assert info.architecture in ["x64", "x86", "ARM64", "ARM"] or len(info.architecture) > 0
        
        # Python version should match actual version
        assert info.python_version == platform_module.python_version()
        
        # Python implementation should match actual implementation
        assert info.python_implementation == platform_module.python_implementation()
    
    def test_is_methods_match_actual_platform(self):
        """Test that is_* methods correctly identify actual platform."""
        info = PlatformDetector.detect()
        
        # Count how many is_* methods return True
        true_count = sum([
            PlatformDetector.is_windows(),
            PlatformDetector.is_macos(),
            PlatformDetector.is_linux(),
            PlatformDetector.is_android(),
            PlatformDetector.is_ios()
        ])
        
        # Exactly one should be True
        assert true_count == 1, "Exactly one platform should be detected"
        
        # The True method should match detected os_name
        if info.os_name == "Windows":
            assert PlatformDetector.is_windows() is True
        elif info.os_name == "macOS":
            assert PlatformDetector.is_macos() is True
        elif info.os_name == "Linux":
            assert PlatformDetector.is_linux() is True
        elif info.os_name == "Android":
            assert PlatformDetector.is_android() is True
        elif info.os_name == "iOS":
            assert PlatformDetector.is_ios() is True
    
    def test_desktop_mobile_classification(self):
        """Test desktop vs mobile classification on actual platform."""
        is_desktop = PlatformDetector.is_desktop()
        is_mobile = PlatformDetector.is_mobile()
        
        # Exactly one should be True (mutually exclusive)
        assert is_desktop != is_mobile
        
        # Verify classification matches OS
        info = PlatformDetector.detect()
        if info.os_name in ["Windows", "macOS", "Linux"]:
            assert is_desktop is True
            assert is_mobile is False
        elif info.os_name in ["Android", "iOS"]:
            assert is_desktop is False
            assert is_mobile is True
    
    def test_caching_performance(self):
        """Test that caching improves performance."""
        import time
        
        # Reset cache
        PlatformDetector._cached_platform_info = None
        
        # First call (uncached)
        start1 = time.perf_counter()
        info1 = PlatformDetector.detect()
        time1 = time.perf_counter() - start1
        
        # Second call (cached)
        start2 = time.perf_counter()
        info2 = PlatformDetector.detect()
        time2 = time.perf_counter() - start2
        
        # Cached call should be faster (or at least not slower)
        # Allow some variance due to system load
        assert time2 <= time1 * 2, "Cached call should not be significantly slower"
        
        # Should return same object
        assert info1 is info2
    
    def test_multiple_calls_consistency(self):
        """Test that multiple calls return consistent results."""
        # Reset cache
        PlatformDetector._cached_platform_info = None
        
        # Call multiple times
        results = [PlatformDetector.detect() for _ in range(10)]
        
        # All should be the same object (cached)
        for result in results[1:]:
            assert result is results[0]
        
        # All should have same values
        for result in results:
            assert result.os_name == results[0].os_name
            assert result.os_version == results[0].os_version
            assert result.architecture == results[0].architecture
    
    def test_platform_info_string_representation(self):
        """Test that PlatformInfo can be converted to string."""
        info = PlatformDetector.detect()
        
        # Should be able to convert to string
        info_str = str(info)
        assert len(info_str) > 0
        
        # Should contain key information
        assert info.os_name in info_str
    
    def test_architecture_is_normalized(self):
        """Test that architecture is properly normalized."""
        info = PlatformDetector.detect()
        
        # Architecture should be one of standard values or a valid string
        valid_architectures = ["x64", "x86", "ARM64", "ARM"]
        
        # Either standard value or non-empty string
        assert info.architecture in valid_architectures or len(info.architecture) > 0
    
    def test_python_version_format(self):
        """Test that Python version has expected format."""
        info = PlatformDetector.detect()
        
        # Python version should have format like "3.11.5"
        parts = info.python_version.split('.')
        assert len(parts) >= 2, "Python version should have at least major.minor"
        
        # First two parts should be numeric
        assert parts[0].isdigit(), "Major version should be numeric"
        assert parts[1].isdigit(), "Minor version should be numeric"
    
    def test_os_version_not_empty(self):
        """Test that OS version is not empty."""
        info = PlatformDetector.detect()
        
        # OS version should not be empty
        assert len(info.os_version) > 0
        assert info.os_version.strip() == info.os_version, "Should not have leading/trailing whitespace"


class TestPlatformDetectorPerformance:
    """Performance tests for platform detection."""
    
    def setup_method(self):
        """Reset cached platform info before each test."""
        PlatformDetector._cached_platform_info = None
    
    def test_detection_latency_under_10ms(self):
        """Test that platform detection completes in <10ms (uncached)."""
        import time
        
        # Measure uncached detection time
        start = time.perf_counter()
        info = PlatformDetector.detect()
        elapsed = time.perf_counter() - start
        
        # Should complete in <10ms (target from design doc)
        assert elapsed < 0.010, f"Detection took {elapsed*1000:.2f}ms, target is <10ms"
    
    def test_cached_detection_latency_under_1ms(self):
        """Test that cached detection is extremely fast (<1ms)."""
        import time
        
        # Prime the cache
        PlatformDetector.detect()
        
        # Measure cached detection time
        start = time.perf_counter()
        info = PlatformDetector.detect()
        elapsed = time.perf_counter() - start
        
        # Cached should be <1ms
        assert elapsed < 0.001, f"Cached detection took {elapsed*1000:.2f}ms, target is <1ms"
    
    def test_is_methods_latency_under_1ms(self):
        """Test that is_* methods complete in <1ms."""
        import time
        
        # Prime the cache
        PlatformDetector.detect()
        
        # Measure is_windows() time
        start = time.perf_counter()
        result = PlatformDetector.is_windows()
        elapsed = time.perf_counter() - start
        
        # Should be <1ms
        assert elapsed < 0.001, f"is_windows() took {elapsed*1000:.2f}ms, target is <1ms"


class TestPlatformDetectorEdgeCases:
    """Edge case tests for platform detection."""
    
    def setup_method(self):
        """Reset cached platform info before each test."""
        PlatformDetector._cached_platform_info = None
    
    def test_repeated_cache_reset(self):
        """Test that cache can be reset and detection still works."""
        # Detect, reset, detect again multiple times
        for _ in range(5):
            info1 = PlatformDetector.detect()
            PlatformDetector._cached_platform_info = None
            info2 = PlatformDetector.detect()
            
            # Should have same values (but different objects)
            assert info1.os_name == info2.os_name
            assert info1.os_version == info2.os_version
            assert info1.architecture == info2.architecture
    
    def test_concurrent_detection_calls(self):
        """Test that concurrent calls don't cause issues."""
        import threading
        
        results = []
        
        def detect_platform():
            info = PlatformDetector.detect()
            results.append(info)
        
        # Reset cache
        PlatformDetector._cached_platform_info = None
        
        # Create multiple threads
        threads = [threading.Thread(target=detect_platform) for _ in range(10)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # All should have same values
        for result in results:
            assert result.os_name == results[0].os_name
            assert result.os_version == results[0].os_version
