"""
Platform Abstraction Layer (PAL) for GURU Desktop AI Assistant.

This module provides platform-agnostic interfaces that isolate all OS-specific
behavior behind strict contracts. The PAL ensures:

1. Core logic is 100% platform-agnostic
2. Security invariants hold across all platforms
3. Predictable behavior regardless of OS
4. Maintainability through isolated platform code
5. Honest capability declaration per platform

Architecture:
    Core Logic → PAL Interface → Platform Backend

Supported Platforms:
    - Windows (full desktop control)
    - macOS (full desktop control with permissions)
    - Android (partial automation via Accessibility)
    - iOS (command-limited, no system automation)

Security:
    All platform backends must maintain identical security invariants:
    - Authority-gated command execution
    - Cryptographic audit logging
    - Biometric authentication
    - Intrusion detection
    - Failure recovery
"""

from .interfaces import (
    # Core interfaces
    ApplicationController,
    InputAutomation,
    SpeechOutput,
    SpeechInput,
    BiometricAuthenticator,
    SecurityEnforcer,
    
    # Data structures
    AppDescriptor,
    AutomationTarget,
    Transcription,
    AuthResult,
    
    # Enums
    TTSPriority,
    AuthResultStatus,
    
    # Exceptions
    PlatformNotSupportedError,
    PlatformCapabilityError,
)

from .platform_detector import PlatformDetector
from .backend_factory import PlatformBackendFactory

__all__ = [
    # Interfaces
    'ApplicationController',
    'InputAutomation',
    'SpeechOutput',
    'SpeechInput',
    'BiometricAuthenticator',
    'SecurityEnforcer',
    
    # Data structures
    'AppDescriptor',
    'AutomationTarget',
    'Transcription',
    'AuthResult',
    
    # Enums
    'TTSPriority',
    'AuthResultStatus',
    
    # Exceptions
    'PlatformNotSupportedError',
    'PlatformCapabilityError',
    
    # Platform detection and factory
    'PlatformDetector',
    'PlatformBackendFactory',
]

__version__ = '1.0.0'
__author__ = 'GURU Development Team'
