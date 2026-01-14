"""Android Platform Backend stubs. Will be implemented in Task 5."""
from .application_controller import AndroidApplicationController
from .input_automation import AndroidInputAutomation
from .speech_output import AndroidSpeechOutput
from .speech_input import AndroidSpeechInput
from .biometric_authenticator import AndroidBiometricAuthenticator
from .security_enforcer import AndroidSecurityEnforcer

__all__ = ['AndroidApplicationController', 'AndroidInputAutomation', 'AndroidSpeechOutput', 
           'AndroidSpeechInput', 'AndroidBiometricAuthenticator', 'AndroidSecurityEnforcer']
