"""
Platform Detection Module.

Automatically detects the current platform and returns the appropriate identifier.
Supports Windows, macOS, Android, and iOS.

CRITICAL RULES:
1. Detection must be deterministic and reliable
2. Unsupported platforms must raise clear errors
3. Detection must occur at system startup
4. Platform identifier must be logged for audit

Validates: Requirements 43.1, 43.2, 43.3, 43.6
"""

import platform
import sys
from typing import Literal

from .interfaces import PlatformNotSupportedError

PlatformType = Literal["windows", "macos", "android", "ios"]


class PlatformDetector:
    """
    Detect current platform and return platform identifier.

    Supports:
        - Windows 10/11
        - macOS (all versions)
        - Android (via Python-for-Android)
        - iOS (via Kivy-iOS or similar)

    Raises:
        PlatformNotSupportedError: If platform is not supported

    Validates: Requirements 43.1, 43.2, 43.3
    """

    @staticmethod
    def detect() -> PlatformType:
        """
        Detect platform and return identifier.

        Returns:
            Platform identifier: "windows", "macos", "android", or "ios"

        Raises:
            PlatformNotSupportedError: If platform is not supported

        Detection Logic:
            1. Check platform.system() for base OS
            2. For Linux, check if running on Android
            3. For Darwin, check if running on iOS
            4. Raise error for unsupported platforms

        Examples:
            >>> PlatformDetector.detect()
            'windows'

            >>> PlatformDetector.detect()
            'macos'
        """
        system = platform.system().lower()

        if system == "windows":
            return "windows"

        elif system == "darwin":
            # Check if running on iOS (via Kivy-iOS or similar)
            # iOS detection: check for specific iOS markers
            if hasattr(sys, "platform") and "ios" in sys.platform.lower():
                return "ios"
            # Default to macOS for Darwin
            return "macos"

        elif system == "linux":
            # Check if running on Android
            # Android detection: check for Android-specific attributes
            if hasattr(sys, "getandroidapilevel"):
                return "android"
            else:
                # Linux desktop is not supported
                raise PlatformNotSupportedError(
                    "Linux desktop is not supported. " "GURU supports Windows, macOS, Android, and iOS only."
                )

        else:
            # Unknown or unsupported platform
            raise PlatformNotSupportedError(
                f"Platform '{system}' is not supported. " f"GURU supports Windows, macOS, Android, and iOS only."
            )

    @staticmethod
    def get_platform_info() -> dict:
        """
        Get detailed platform information for logging and diagnostics.

        Returns:
            Dictionary containing:
                - platform: Platform identifier (windows, macos, android, ios)
                - system: System name from platform.system()
                - release: OS release version
                - version: OS version string
                - machine: Machine type (x86_64, arm64, etc.)
                - processor: Processor name
                - python_version: Python version

        Examples:
            >>> PlatformDetector.get_platform_info()
            {
                'platform': 'windows',
                'system': 'Windows',
                'release': '10',
                'version': '10.0.19045',
                'machine': 'AMD64',
                'processor': 'Intel64 Family 6 Model 142 Stepping 12, GenuineIntel',
                'python_version': '3.11.5'
            }
        """
        try:
            detected_platform = PlatformDetector.detect()
        except PlatformNotSupportedError:
            detected_platform = f"unsupported: {str(e)}"

        return {
            "platform": detected_platform,
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }

    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows."""
        try:
            return PlatformDetector.detect() == "windows"
        except PlatformNotSupportedError:
            return False

    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS."""
        try:
            return PlatformDetector.detect() == "macos"
        except PlatformNotSupportedError:
            return False

    @staticmethod
    def is_android() -> bool:
        """Check if running on Android."""
        try:
            return PlatformDetector.detect() == "android"
        except PlatformNotSupportedError:
            return False

    @staticmethod
    def is_ios() -> bool:
        """Check if running on iOS."""
        try:
            return PlatformDetector.detect() == "ios"
        except PlatformNotSupportedError:
            return False

    @staticmethod
    def is_desktop() -> bool:
        """Check if running on desktop platform (Windows or macOS)."""
        try:
            platform_type = PlatformDetector.detect()
            return platform_type in ("windows", "macos")
        except PlatformNotSupportedError:
            return False

    @staticmethod
    def is_mobile() -> bool:
        """Check if running on mobile platform (Android or iOS)."""
        try:
            platform_type = PlatformDetector.detect()
            return platform_type in ("android", "ios")
        except PlatformNotSupportedError:
            return False
