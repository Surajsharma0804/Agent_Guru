"""
Platform Backend Factory.

Creates platform-specific backend implementations based on detected platform.
Uses factory pattern with dependency injection to provide platform backends
to core logic.

CRITICAL RULES:
1. Core logic receives backends via dependency injection
2. Core logic NEVER imports platform-specific modules directly
3. Factory creates all 6 platform backends
4. Unsupported platforms raise clear errors
5. Backend creation is logged for audit

Validates: Requirements 43.4, 43.5, 43.7
"""

from typing import TYPE_CHECKING

from .interfaces import (
    ApplicationController,
    InputAutomation,
    SpeechOutput,
    SpeechInput,
    BiometricAuthenticator,
    SecurityEnforcer,
    PlatformNotSupportedError,
)
from .platform_detector import PlatformType

# Type checking imports (not executed at runtime)
if TYPE_CHECKING:
    pass


class PlatformBackendFactory:
    """
    Factory for creating platform-specific backend implementations.
    
    Creates all 6 PAL interface implementations based on detected platform:
        1. ApplicationController
        2. InputAutomation
        3. SpeechOutput
        4. SpeechInput
        5. BiometricAuthenticator
        6. SecurityEnforcer
    
    Usage:
        >>> detector = PlatformDetector()
        >>> platform = detector.detect()
        >>> factory = PlatformBackendFactory(platform)
        >>> app_controller = factory.create_application_controller()
        >>> input_automation = factory.create_input_automation()
        >>> # ... create other backends
    
    Validates: Requirements 43.4, 43.5
    """
    
    def __init__(self, platform: PlatformType):
        """
        Initialize factory with detected platform.
        
        Args:
            platform: Platform identifier (windows, macos, android, ios)
        
        Raises:
            PlatformNotSupportedError: If platform is not supported
        """
        if platform not in ("windows", "macos", "android", "ios"):
            raise PlatformNotSupportedError(
                f"Platform '{platform}' is not supported. "
                f"Supported platforms: windows, macos, android, ios"
            )
        
        self.platform = platform
    
    def create_application_controller(self) -> ApplicationController:
        """
        Create platform-specific application controller.
        
        Returns:
            ApplicationController implementation for current platform
        
        Raises:
            PlatformNotSupportedError: If platform backend not implemented
        
        Platform Implementations:
            Windows: WindowsApplicationController (Win32/Shell/UIAutomation)
            macOS: macOSApplicationController (LaunchServices/Apple Events)
            Android: AndroidApplicationController (Intent system)
            iOS: iOSApplicationController (deep links only)
        """
        if self.platform == "windows":
            from .backends.windows.application_controller import WindowsApplicationController
            return WindowsApplicationController()
        
        elif self.platform == "macos":
            from .backends.macos.application_controller import macOSApplicationController
            return macOSApplicationController()
        
        elif self.platform == "android":
            from .backends.android.application_controller import AndroidApplicationController
            return AndroidApplicationController()
        
        elif self.platform == "ios":
            from .backends.ios.application_controller import iOSApplicationController
            return iOSApplicationController()
        
        else:
            raise PlatformNotSupportedError(
                f"ApplicationController not implemented for platform '{self.platform}'"
            )
    
    def create_input_automation(self) -> InputAutomation:
        """
        Create platform-specific input automation.
        
        Returns:
            InputAutomation implementation for current platform
        
        Raises:
            PlatformNotSupportedError: If platform backend not implemented
        
        Platform Implementations:
            Windows: WindowsInputAutomation (Win32 SendInput)
            macOS: macOSInputAutomation (CGEvent with Accessibility)
            Android: AndroidInputAutomation (Accessibility Service)
            iOS: iOSInputAutomation (severely restricted)
        """
        if self.platform == "windows":
            from .backends.windows.input_automation import WindowsInputAutomation
            return WindowsInputAutomation()
        
        elif self.platform == "macos":
            from .backends.macos.input_automation import macOSInputAutomation
            return macOSInputAutomation()
        
        elif self.platform == "android":
            from .backends.android.input_automation import AndroidInputAutomation
            return AndroidInputAutomation()
        
        elif self.platform == "ios":
            from .backends.ios.input_automation import iOSInputAutomation
            return iOSInputAutomation()
        
        else:
            raise PlatformNotSupportedError(
                f"InputAutomation not implemented for platform '{self.platform}'"
            )
    
    def create_speech_output(self) -> SpeechOutput:
        """
        Create platform-specific speech output.
        
        Returns:
            SpeechOutput implementation for current platform
        
        Raises:
            PlatformNotSupportedError: If platform backend not implemented
        
        Platform Implementations:
            Windows: WindowsSpeechOutput (Windows SAPI)
            macOS: macOSSpeechOutput (NSSpeechSynthesizer)
            Android: AndroidSpeechOutput (Android TTS)
            iOS: iOSSpeechOutput (AVSpeechSynthesizer)
        """
        if self.platform == "windows":
            from .backends.windows.speech_output import WindowsSpeechOutput
            return WindowsSpeechOutput()
        
        elif self.platform == "macos":
            from .backends.macos.speech_output import macOSSpeechOutput
            return macOSSpeechOutput()
        
        elif self.platform == "android":
            from .backends.android.speech_output import AndroidSpeechOutput
            return AndroidSpeechOutput()
        
        elif self.platform == "ios":
            from .backends.ios.speech_output import iOSSpeechOutput
            return iOSSpeechOutput()
        
        else:
            raise PlatformNotSupportedError(
                f"SpeechOutput not implemented for platform '{self.platform}'"
            )
    
    def create_speech_input(self) -> SpeechInput:
        """
        Create platform-specific speech input.
        
        Returns:
            SpeechInput implementation for current platform
        
        Raises:
            PlatformNotSupportedError: If platform backend not implemented
        
        Platform Implementations:
            Windows: WindowsSpeechInput (Whisper.cpp)
            macOS: macOSSpeechInput (Whisper.cpp)
            Android: AndroidSpeechInput (Whisper.cpp or system STT)
            iOS: iOSSpeechInput (system STT mandatory)
        """
        if self.platform == "windows":
            from .backends.windows.speech_input import WindowsSpeechInput
            return WindowsSpeechInput()
        
        elif self.platform == "macos":
            from .backends.macos.speech_input import macOSSpeechInput
            return macOSSpeechInput()
        
        elif self.platform == "android":
            from .backends.android.speech_input import AndroidSpeechInput
            return AndroidSpeechInput()
        
        elif self.platform == "ios":
            from .backends.ios.speech_input import iOSSpeechInput
            return iOSSpeechInput()
        
        else:
            raise PlatformNotSupportedError(
                f"SpeechInput not implemented for platform '{self.platform}'"
            )
    
    def create_biometric_authenticator(self) -> BiometricAuthenticator:
        """
        Create platform-specific biometric authenticator.
        
        Returns:
            BiometricAuthenticator implementation for current platform
        
        Raises:
            PlatformNotSupportedError: If platform backend not implemented
        
        Platform Implementations:
            Windows: WindowsBiometricAuthenticator (Windows Hello)
            macOS: macOSBiometricAuthenticator (Touch ID/Face ID)
            Android: AndroidBiometricAuthenticator (BiometricPrompt)
            iOS: iOSBiometricAuthenticator (Face ID/Touch ID)
        """
        if self.platform == "windows":
            from .backends.windows.biometric_authenticator import WindowsBiometricAuthenticator
            return WindowsBiometricAuthenticator()
        
        elif self.platform == "macos":
            from .backends.macos.biometric_authenticator import macOSBiometricAuthenticator
            return macOSBiometricAuthenticator()
        
        elif self.platform == "android":
            from .backends.android.biometric_authenticator import AndroidBiometricAuthenticator
            return AndroidBiometricAuthenticator()
        
        elif self.platform == "ios":
            from .backends.ios.biometric_authenticator import iOSBiometricAuthenticator
            return iOSBiometricAuthenticator()
        
        else:
            raise PlatformNotSupportedError(
                f"BiometricAuthenticator not implemented for platform '{self.platform}'"
            )
    
    def create_security_enforcer(self) -> SecurityEnforcer:
        """
        Create platform-specific security enforcer.
        
        Returns:
            SecurityEnforcer implementation for current platform
        
        Raises:
            PlatformNotSupportedError: If platform backend not implemented
        
        Platform Implementations:
            Windows: WindowsSecurityEnforcer (LockWorkStation API)
            macOS: macOSSecurityEnforcer (CGSession API)
            Android: AndroidSecurityEnforcer (app + screen lock)
            iOS: iOSSecurityEnforcer (app lock only)
        """
        if self.platform == "windows":
            from .backends.windows.security_enforcer import WindowsSecurityEnforcer
            return WindowsSecurityEnforcer()
        
        elif self.platform == "macos":
            from .backends.macos.security_enforcer import macOSSecurityEnforcer
            return macOSSecurityEnforcer()
        
        elif self.platform == "android":
            from .backends.android.security_enforcer import AndroidSecurityEnforcer
            return AndroidSecurityEnforcer()
        
        elif self.platform == "ios":
            from .backends.ios.security_enforcer import iOSSecurityEnforcer
            return iOSSecurityEnforcer()
        
        else:
            raise PlatformNotSupportedError(
                f"SecurityEnforcer not implemented for platform '{self.platform}'"
            )
    
    def create_all_backends(self) -> dict:
        """
        Create all platform backends at once.
        
        Returns:
            Dictionary containing all 6 backend implementations:
                - application_controller: ApplicationController
                - input_automation: InputAutomation
                - speech_output: SpeechOutput
                - speech_input: SpeechInput
                - biometric_authenticator: BiometricAuthenticator
                - security_enforcer: SecurityEnforcer
        
        Usage:
            >>> factory = PlatformBackendFactory("windows")
            >>> backends = factory.create_all_backends()
            >>> app_controller = backends['application_controller']
            >>> input_automation = backends['input_automation']
        """
        return {
            'application_controller': self.create_application_controller(),
            'input_automation': self.create_input_automation(),
            'speech_output': self.create_speech_output(),
            'speech_input': self.create_speech_input(),
            'biometric_authenticator': self.create_biometric_authenticator(),
            'security_enforcer': self.create_security_enforcer(),
        }
