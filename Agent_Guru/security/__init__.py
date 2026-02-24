"""Security system for Agent Guru."""

from Agent_Guru.security.voice_auth import (
    VoiceAuthenticator,
    VoiceProfile,
    VoiceAuthenticationError
)

# Conditional import to avoid circular dependencies and torch conflicts during testing
def __getattr__(name):
    """Lazy import for SpeechSecurityIntegration to avoid torch conflicts."""
    if name == 'SpeechSecurityIntegration':
        from Agent_Guru.security.speech_integration import SpeechSecurityIntegration
        return SpeechSecurityIntegration
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    'VoiceAuthenticator',
    'VoiceProfile',
    'VoiceAuthenticationError',
    'SpeechSecurityIntegration'
]
