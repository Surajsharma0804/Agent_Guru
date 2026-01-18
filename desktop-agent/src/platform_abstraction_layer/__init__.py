"""
Platform Abstraction Layer (PAL) Package

Provides platform-specific implementations with a unified interface.
"""

from .platform_detector import PlatformDetector
from .backend_factory import PlatformBackendFactory

__all__ = ['PlatformDetector', 'PlatformBackendFactory']