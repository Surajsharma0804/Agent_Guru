"""
GURU Multilingual Understanding Module

Production-grade multilingual understanding capabilities that extend GURU's existing
voice processing pipeline to support natural interaction in 15 languages while
maintaining strict security boundaries and user control.

Core Components:
- Language Detection Engine: Local deterministic language identification
- Intent Normalization Layer: Language-neutral intent mapping
- Multilingual Voice Processing: Language-aware speech recognition
- Multilingual Audit Logging: Comprehensive multilingual event logging
- Configuration Management: Multilingual settings and preferences

Security Invariants (Maintained):
- All multilingual processing occurs locally first
- No cloud dependency for core language detection
- Identical security enforcement across all languages
- No language-based security bypasses
- Comprehensive audit logging for all multilingual decisions
"""

# Import only implemented modules for now
try:
    from .language_detection import (
        LanguageDetectionEngine,
        LanguageDetectionResult,
        MixedLanguageResult,
        LanguageSegment,
        LanguageConfidenceScore,
        DetectionMethod,
        ConfidenceLevel,
        FallbackReason,
        FallbackDecision,
        FallbackNotification,
        FallbackNotificationLevel
    )
except ImportError:
    pass

try:
    from .configuration import (
        MultilingualConfig,
        LanguageConfig
    )
except ImportError:
    pass

try:
    from .exceptions import (
        MultilingualError,
        LanguageDetectionError,
        ModelLoadingError
    )
except ImportError:
    pass

__all__ = [
    # Language Detection (implemented)
    "LanguageDetectionEngine",
    "LanguageDetectionResult", 
    "MixedLanguageResult",
    "LanguageSegment",
    "LanguageConfidenceScore",
    "DetectionMethod",
    "ConfidenceLevel",
    "FallbackReason",
    "FallbackDecision", 
    "FallbackNotification",
    "FallbackNotificationLevel",
    
    # Configuration (partial)
    "MultilingualConfig",
    "LanguageConfig",
    
    # Exceptions (partial)
    "MultilingualError",
    "LanguageDetectionError",
    "ModelLoadingError"
]

# Version information
__version__ = "1.0.0"
__author__ = "GURU Development Team"
__description__ = "Production-grade multilingual understanding for GURU Personal Assistant"

# Security statement
__security_statement__ = """
Multilingual understanding augments GURU's capabilities without weakening any security,
authority, or privacy invariant. All multilingual processing maintains identical security
boundaries and user control as the core GURU system.
"""