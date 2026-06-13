"""Security system for Agent Guru."""

from Agent_Guru.security.biometric_auth import BiometricAuthenticator
from Agent_Guru.security.models import AuthenticationResult
from Agent_Guru.security.voice_auth import (
    VoiceAuthenticationError,
    VoiceAuthenticator,
    VoiceProfile,
)


# Conditional import to avoid circular dependencies and torch conflicts during testing
def __getattr__(name: str) -> object:
    """Lazy import for SpeechSecurityIntegration to avoid torch conflicts."""
    if name == "SpeechSecurityIntegration":
        from Agent_Guru.security.speech_integration import SpeechSecurityIntegration

        return SpeechSecurityIntegration
    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)


__all__ = [
    "AuthenticationResult",
    "BiometricAuthenticator",
    "SpeechSecurityIntegration",
    "VoiceAuthenticationError",
    "VoiceAuthenticator",
    "VoiceProfile",
]
