"""
Windows Platform Backend.

Implements all PAL interfaces for Windows 10/11 using:
    - Win32 API (CreateProcess, SendInput, LockWorkStation)
    - Windows Shell (ShellExecute)
    - UI Automation (for application control)
    - Windows SAPI (for text-to-speech)
    - Whisper.cpp (for speech recognition)
    - Windows Hello (for biometric authentication)

Capabilities:
    - Full desktop control
    - Full input automation
    - System-wide authority
    - Workstation lock

Validates: Requirements 34.5, 35.4, 36.3, 37.4, 38.2, 40.2
"""

from .application_controller import WindowsApplicationController
from .input_automation import WindowsInputAutomation
from .speech_output import WindowsSpeechOutput
from .speech_input import WindowsSpeechInput
from .biometric_authenticator import WindowsBiometricAuthenticator
from .security_enforcer import WindowsSecurityEnforcer

__all__ = [
    'WindowsApplicationController',
    'WindowsInputAutomation',
    'WindowsSpeechOutput',
    'WindowsSpeechInput',
    'WindowsBiometricAuthenticator',
    'WindowsSecurityEnforcer',
]
