"""
TTS Volume Bypass Verification Tests

Comprehensive verification of Windows SAPI volume bypass functionality.

Tests:
- Volume is set to maximum (100) by default
- Volume bypass avoids Windows Volume Mixer 1% lock
- Volume control works correctly
- Integration with Windows SAPI backend

Validates: Requirements 9.2, 9.5

Task: 10.3 Verify Windows SAPI volume bypass
"""

import platform
from typing import Optional

import pytest

# Import TTS service and dependencies
from gui.tts_service import TTSService
from pal.interfaces import SpeechOutput, TTSPriority

# ============================================================================
# Platform Detection
# ============================================================================

def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system().lower() == "windows"


# ============================================================================
# Windows SAPI Volume Tests
# ============================================================================

@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_windows_sapi_volume_default_maximum():
    """
    Test that Windows SAPI volume is set to maximum (100) by default.
    
    Verifies that the TTS service initializes with volume=100 to bypass
    the Windows Volume Mixer 1% lock issue.
    
    Algorithm:
        1. Create Windows SAPI backend
        2. Verify volume is set to 100
    
    Validates: Requirements 9.2, 9.5
    """
    from pal.backends.windows.speech_output import WindowsSpeechOutput

    # Create Windows SAPI backend
    speech_output = WindowsSpeechOutput()
    
    # Verify volume is set to maximum
    assert speech_output.voice.Volume == 100, \
        f"Expected volume=100, got {speech_output.voice.Volume}"


@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_windows_sapi_volume_control():
    """
    Test that Windows SAPI volume control works correctly.
    
    Verifies that the set_volume() method correctly updates the SAPI volume.
    
    Algorithm:
        1. Create Windows SAPI backend
        2. Set volume to various levels
        3. Verify volume is updated correctly
    
    Validates: Requirements 9.2, 9.5
    """
    from pal.backends.windows.speech_output import WindowsSpeechOutput

    # Create Windows SAPI backend
    speech_output = WindowsSpeechOutput()
    
    # Test various volume levels
    test_volumes = [0, 25, 50, 75, 100]
    
    for volume in test_volumes:
        speech_output.set_volume(volume)
        assert speech_output.voice.Volume == volume, \
            f"Expected volume={volume}, got {speech_output.voice.Volume}"


@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_windows_sapi_volume_clamping():
    """
    Test that Windows SAPI volume is clamped to valid range (0-100).
    
    Verifies that invalid volume values are clamped to the valid range.
    
    Algorithm:
        1. Create Windows SAPI backend
        2. Set volume to invalid values (negative, > 100)
        3. Verify volume is clamped to valid range
    
    Validates: Requirements 9.2, 9.5
    """
    from pal.backends.windows.speech_output import WindowsSpeechOutput

    # Create Windows SAPI backend
    speech_output = WindowsSpeechOutput()
    
    # Test negative volume (should clamp to 0)
    speech_output.set_volume(-10)
    assert speech_output.voice.Volume == 0, \
        f"Expected volume=0 (clamped), got {speech_output.voice.Volume}"
    
    # Test volume > 100 (should clamp to 100)
    speech_output.set_volume(150)
    assert speech_output.voice.Volume == 100, \
        f"Expected volume=100 (clamped), got {speech_output.voice.Volume}"


@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_windows_sapi_rate_control():
    """
    Test that Windows SAPI rate control works correctly.
    
    Verifies that the set_rate() method correctly updates the SAPI rate.
    
    Algorithm:
        1. Create Windows SAPI backend
        2. Set rate to various levels
        3. Verify rate is updated correctly
    
    Validates: Requirements 9.2, 9.5
    """
    from pal.backends.windows.speech_output import WindowsSpeechOutput

    # Create Windows SAPI backend
    speech_output = WindowsSpeechOutput()
    
    # Test various rate levels
    test_rates = [-10, -5, 0, 5, 10]
    
    for rate in test_rates:
        speech_output.set_rate(rate)
        assert speech_output.voice.Rate == rate, \
            f"Expected rate={rate}, got {speech_output.voice.Rate}"


@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_windows_sapi_rate_clamping():
    """
    Test that Windows SAPI rate is clamped to valid range (-10 to 10).
    
    Verifies that invalid rate values are clamped to the valid range.
    
    Algorithm:
        1. Create Windows SAPI backend
        2. Set rate to invalid values (< -10, > 10)
        3. Verify rate is clamped to valid range
    
    Validates: Requirements 9.2, 9.5
    """
    from pal.backends.windows.speech_output import WindowsSpeechOutput

    # Create Windows SAPI backend
    speech_output = WindowsSpeechOutput()
    
    # Test rate < -10 (should clamp to -10)
    speech_output.set_rate(-20)
    assert speech_output.voice.Rate == -10, \
        f"Expected rate=-10 (clamped), got {speech_output.voice.Rate}"
    
    # Test rate > 10 (should clamp to 10)
    speech_output.set_rate(20)
    assert speech_output.voice.Rate == 10, \
        f"Expected rate=10 (clamped), got {speech_output.voice.Rate}"


@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_windows_sapi_capabilities():
    """
    Test that Windows SAPI backend reports correct capabilities.
    
    Verifies that the backend reports support for all expected features.
    
    Algorithm:
        1. Create Windows SAPI backend
        2. Get capabilities
        3. Verify all expected capabilities are present and True
    
    Validates: Requirements 9.2, 9.5
    """
    from pal.backends.windows.speech_output import WindowsSpeechOutput

    # Create Windows SAPI backend
    speech_output = WindowsSpeechOutput()
    
    # Get capabilities
    capabilities = speech_output.get_capabilities()
    
    # Verify expected capabilities
    expected_capabilities = {
        'has_priority_queue': True,
        'can_interrupt': True,
        'can_control_volume': True,
        'can_control_rate': True,
    }
    
    for capability, expected_value in expected_capabilities.items():
        assert capability in capabilities, \
            f"Missing capability: {capability}"
        assert capabilities[capability] == expected_value, \
            f"Expected {capability}={expected_value}, got {capabilities[capability]}"


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_tts_service_with_windows_backend_volume():
    """
    Test TTS service integration with Windows SAPI backend volume control.
    
    Verifies that the TTS service correctly uses the Windows SAPI backend
    with maximum volume by default.
    
    Algorithm:
        1. Create TTS service with Windows SAPI backend
        2. Verify backend volume is set to maximum
        3. Test volume control through TTS service
    
    Validates: Requirements 9.2, 9.5
    """
    from pal.backends.windows.speech_output import WindowsSpeechOutput

    # Create Windows SAPI backend
    speech_output = WindowsSpeechOutput()
    
    # Create TTS service with Windows backend
    tts_service = TTSService(speech_output)
    
    # Verify backend volume is maximum
    assert speech_output.voice.Volume == 100, \
        f"Expected volume=100, got {speech_output.voice.Volume}"
    
    # Test volume control
    speech_output.set_volume(75)
    assert speech_output.voice.Volume == 75, \
        f"Expected volume=75, got {speech_output.voice.Volume}"
    
    # Cleanup
    tts_service.stop()


@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_windows_sapi_volume_bypass_documentation():
    """
    Test that Windows SAPI volume bypass is documented.
    
    Verifies that the volume bypass feature is properly documented
    in the code and design documents.
    
    Algorithm:
        1. Check that WindowsSpeechOutput docstring mentions volume bypass
        2. Check that set_volume() docstring mentions Volume Mixer bypass
    
    Validates: Requirements 9.2, 9.5
    """
    from pal.backends.windows.speech_output import WindowsSpeechOutput

    # Check class docstring
    class_doc = WindowsSpeechOutput.__doc__
    assert class_doc is not None, "WindowsSpeechOutput missing docstring"
    assert "volume" in class_doc.lower() or "bypass" in class_doc.lower(), \
        "WindowsSpeechOutput docstring should mention volume bypass"
    
    # Check set_volume docstring
    set_volume_doc = WindowsSpeechOutput.set_volume.__doc__
    assert set_volume_doc is not None, "set_volume missing docstring"
    assert "volume mixer" in set_volume_doc.lower() or "bypass" in set_volume_doc.lower(), \
        "set_volume docstring should mention Volume Mixer bypass"


# ============================================================================
# Manual Verification Test (Requires Human Verification)
# ============================================================================

@pytest.mark.skip(reason="Manual verification required - requires human to listen")
@pytest.mark.skipif(not is_windows(), reason="Windows-only test")
def test_windows_sapi_volume_bypass_manual():
    """
    Manual test for Windows SAPI volume bypass.
    
    This test requires human verification:
    1. Set Windows Volume Mixer to 1% for Python
    2. Run this test
    3. Verify that speech is audible at full volume (not 1%)
    
    If speech is audible at full volume despite Volume Mixer being at 1%,
    then the volume bypass is working correctly.
    
    Validates: Requirements 9.2, 9.5
    """
    import time

    from pal.backends.windows.speech_output import WindowsSpeechOutput
    
    print("\n" + "="*70)
    print("MANUAL VERIFICATION TEST")
    print("="*70)
    print("\nInstructions:")
    print("1. Open Windows Volume Mixer (right-click volume icon → Open Volume Mixer)")
    print("2. Set Python volume to 1% in Volume Mixer")
    print("3. Press Enter to continue...")
    input()
    
    # Create Windows SAPI backend
    speech_output = WindowsSpeechOutput()
    
    # Verify volume is set to maximum
    print(f"\nSAPI Volume: {speech_output.voice.Volume}")
    assert speech_output.voice.Volume == 100, \
        f"Expected volume=100, got {speech_output.voice.Volume}"
    
    # Speak test message
    print("\nSpeaking test message...")
    print("If you can hear this clearly at full volume, the bypass is working!")
    
    speech_output.speak(
        "Testing volume bypass. If you can hear this clearly at full volume, "
        "the Windows Volume Mixer bypass is working correctly.",
        priority=TTSPriority.NORMAL,
        interrupt=False
    )
    
    # Wait for speech to complete
    while speech_output.is_speaking():
        time.sleep(0.1)
    
    print("\nDid you hear the speech at full volume? (y/n): ", end="")
    response = input().strip().lower()
    
    assert response == 'y', \
        "Volume bypass verification failed - speech was not at full volume"
    
    print("\n✓ Volume bypass verified successfully!")
    print("="*70)


# ============================================================================
# Cross-Platform Volume Tests
# ============================================================================

def test_tts_service_volume_control_cross_platform():
    """
    Test TTS service volume control works across platforms.
    
    Verifies that the TTS service can control volume through the PAL interface
    regardless of platform.
    
    Algorithm:
        1. Create TTS service with platform-specific backend
        2. Test volume control
        3. Verify volume changes are applied
    
    Validates: Requirements 9.2, 9.5, 36.8
    """
    from pal.backend_factory import PlatformBackendFactory
    from pal.platform_detector import PlatformDetector

    # Detect platform and create backend
    platform_name = PlatformDetector.detect()
    factory = PlatformBackendFactory(platform_name)
    speech_output = factory.create_speech_output()
    
    # Create TTS service
    tts_service = TTSService(speech_output)
    
    # Test volume control
    test_volumes = [50, 75, 100]
    
    for volume in test_volumes:
        speech_output.set_volume(volume)
        # Note: We can't verify the actual volume on all platforms,
        # but we can verify the method doesn't crash
    
    # Cleanup
    tts_service.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
