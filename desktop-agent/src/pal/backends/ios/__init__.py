"""
iOS Platform Backend Implementation

PLATFORM LIMITATIONS (iOS Sandbox Restrictions):
This is the most restricted platform supported by GURU due to iOS security policies.

CAPABILITIES:
✅ Biometric Authentication: Full support (Face ID/Touch ID)
✅ Text-to-Speech: Full support (AVSpeechSynthesizer)
✅ Speech Recognition: System STT only (requires internet)
⚠️ Application Control: Deep links only (no close/discover)
❌ Input Automation: NOT SUPPORTED (iOS restriction)
⚠️ Security Enforcement: App-level only (no system lock)

HONEST ASSESSMENT:
iOS is supported for conversational AI use cases only.
Desktop automation, system control, and multi-app workflows are NOT supported.

For full GURU capabilities, use Windows or macOS.

See docs/IOS_LIMITATIONS.md for complete documentation.

Requirements: 34.8, 35.7, 36.6, 37.6, 38.5, 39.2, 39.3, 39.6, 40.5, 41.5
"""
from .application_controller import iOSApplicationController
from .input_automation import iOSInputAutomation
from .speech_output import iOSSpeechOutput
from .speech_input import iOSSpeechInput
from .biometric_authenticator import iOSBiometricAuthenticator
from .security_enforcer import iOSSecurityEnforcer

__all__ = ['iOSApplicationController', 'iOSInputAutomation', 'iOSSpeechOutput', 
           'iOSSpeechInput', 'iOSBiometricAuthenticator', 'iOSSecurityEnforcer']
