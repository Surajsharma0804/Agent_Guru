"""
Platform Integration System for Agent Guru.

This package provides comprehensive cross-platform OS control, hardware abstraction,
and permission management for the AGENT_GURU AI operating system.

Modules:
    windows: Windows-specific integration using pywin32
    macos: macOS-specific integration using pyobjc
    linux: Linux-specific integration using dbus-python
    android: Android-specific integration using pyjnius
    ios: iOS-specific integration using pyobjus
    hardware: Cross-platform hardware monitoring using psutil and GPUtil
    permissions: Permission validation and management
    controllers: Specialized controllers for various operations
    mobile: Mobile-specific functionality and background services

The system abstracts platform-specific operations behind common interfaces,
allowing AGENT_GURU to control system functions, monitor hardware, and manage
permissions without needing to understand the underlying OS implementation details.

Performance Targets:
    - Platform detection: <10ms
    - Hardware queries: <1s
    - Permission checks: <100ms
    - Command execution: Platform-dependent

Architecture:
    The system uses a strategy pattern where platform-specific implementations
    are abstracted behind common interfaces, with specialized controllers for
    each operation category.
"""

__version__ = "1.0.0"

# Import platform detector for easy access
from Agent_Guru.platform.platform_detector import (
    PlatformDetector,
    PlatformInfo,
    UnsupportedPlatformError
)

__all__ = [
    "PlatformDetector",
    "PlatformInfo",
    "UnsupportedPlatformError",
]
