"""Android Platform Backend stubs. Will be implemented in Task 5."""

from .application_controller import AndroidApplicationController
from .biometric_authenticator import AndroidBiometricAuthenticator
from .input_automation import AndroidInputAutomation
from .security_enforcer import AndroidSecurityEnforcer
from .speech_input import AndroidSpeechInput
from .speech_output import AndroidSpeechOutput

__all__ = [
    "AndroidApplicationController",
    "AndroidInputAutomation",
    "AndroidSpeechOutput",
    "AndroidSpeechInput",
    "AndroidBiometricAuthenticator",
    "AndroidSecurityEnforcer",
]
