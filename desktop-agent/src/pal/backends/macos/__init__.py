"""
macOS Platform Backend.

Implements all PAL interfaces for macOS using:
    - LaunchServices (for application launching)
    - Apple Events (for application control)
    - CGEvent (for input automation with Accessibility)
    - NSSpeechSynthesizer (for text-to-speech)
    - Whisper.cpp (for speech recognition)
    - Touch ID/Face ID (for biometric authentication)
    - CGSession (for screen lock)

Capabilities:
    - Full desktop control (with Accessibility permission)
    - Full input automation (with Accessibility permission)
    - System-wide authority
    - Screen lock

IMPLEMENTATION NOTE:
These are stub implementations. Full implementation will be completed in Task 4.

Validates: Requirements 34.6, 35.5, 36.4, 37.4, 38.3, 40.3
"""

from .application_controller import macOSApplicationController
from .input_automation import macOSInputAutomation
from .speech_output import macOSSpeechOutput
from .speech_input import macOSSpeechInput
from .biometric_authenticator import macOSBiometricAuthenticator
from .security_enforcer import macOSSecurityEnforcer

__all__ = [
    'macOSApplicationController',
    'macOSInputAutomation',
    'macOSSpeechOutput',
    'macOSSpeechInput',
    'macOSBiometricAuthenticator',
    'macOSSecurityEnforcer',
]
