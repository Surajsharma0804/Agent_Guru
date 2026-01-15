"""
Intrusion Detection and Response System

This module implements comprehensive intrusion detection capabilities for GURU,
focusing on biometric verification failure detection, pattern analysis, and
automatic response mechanisms.

The intrusion detection system operates on the principle of "fail closed" -
any suspicious activity results in immediate system lockdown rather than
degraded operation.
"""

from .biometric_failure_detector import (
    BiometricFailureDetectionConfig,
    BiometricFailureEvent,
    BiometricFailureSeverity,
    BiometricFailureType,
    EnhancedBiometricFailureDetector,
    create_enhanced_biometric_failure_detector,
)
from .detection import (
    IntrusionDetectionConfig,
    IntrusionDetector,
    IntrusionEvent,
    IntrusionEventType,
    IntrusionSeverity,
    create_intrusion_detector,
)
from .patterns import (
    CryptographicFailurePatternAnalyzer,
    FailurePattern,
    FailurePatternType,
    PatternAnalysisConfig,
    PatternSeverity,
    create_failure_pattern_analyzer,
)
from .workstation_lock import (
    WorkstationLockConfig,
    WorkstationLocker,
    WorkstationLockEvent,
    WorkstationLockResult,
    WorkstationLockTrigger,
    create_workstation_locker,
)

__all__ = [
    "IntrusionDetector",
    "IntrusionEvent",
    "IntrusionEventType",
    "IntrusionSeverity",
    "IntrusionDetectionConfig",
    "create_intrusion_detector",
    "CryptographicFailurePatternAnalyzer",
    "FailurePattern",
    "FailurePatternType",
    "PatternSeverity",
    "PatternAnalysisConfig",
    "create_failure_pattern_analyzer",
    "EnhancedBiometricFailureDetector",
    "BiometricFailureEvent",
    "BiometricFailureType",
    "BiometricFailureSeverity",
    "BiometricFailureDetectionConfig",
    "create_enhanced_biometric_failure_detector",
    "WorkstationLocker",
    "WorkstationLockEvent",
    "WorkstationLockResult",
    "WorkstationLockTrigger",
    "WorkstationLockConfig",
    "create_workstation_locker",
]
