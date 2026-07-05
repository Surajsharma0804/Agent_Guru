"""Module: Agent_Guru.platform.platform_detector
Purpose: Ultra-fast platform detection for cross-platform OS control
Author: Agent Guru Team
Date: 2026-02-23.

Performance Requirements:
- Time Complexity: O(1) - single platform.system() call
- Space Complexity: O(1) - fixed data structure
- Latency: <1ms (instant detection)

Design Decisions:
- Use Python's platform module for OS detection (standard library)
- Cache detection result (platform doesn't change during runtime)
- Raise descriptive errors for unsupported platforms
- Support Windows, macOS, Linux, Android, iOS

Supported Platforms:
- Windows: All versions (7, 8, 10, 11, Server)
- macOS: All versions (10.x, 11.x, 12.x+)
- Linux: All distributions (Ubuntu, Debian, Fedora, Arch, etc.)
- Android: Mobile platform (future support)
- iOS: Mobile platform (future support)
"""

import os
import platform
import sys
from dataclasses import dataclass

# Security: subprocess calls in this module use only fixed, non-user-controlled
# arguments (["uname", "-o"]) for platform detection. B603/B607 suppressed.


@dataclass
class PlatformInfo:
    """Platform information data structure.

    Attributes:
        os_name: Operating system name ("Windows", "macOS", "Linux", "Android", "iOS")
        os_version: OS version string (e.g., "10.0.19041", "12.3", "5.15.0")
        architecture: System architecture ("x86", "x64", "ARM64", "ARM")
        python_version: Python version string (e.g., "3.11.5")
        python_implementation: Python implementation ("CPython", "PyPy", "Jython")

    """

    os_name: str
    os_version: str
    architecture: str
    python_version: str
    python_implementation: str


class UnsupportedPlatformError(Exception):
    """Raised when the operating system is not supported.

    Supported platforms: Windows, macOS, Linux, Android, iOS
    """


class PlatformDetector:
    """Ultra-fast platform detector using Python's platform module.

    Time Complexity: O(1) - single system call
    Space Complexity: O(1) - fixed data structure

    This class provides static methods for detecting the current operating system
    and returning structured platform information. Results are cached for performance.

    Example:
        >>> info = PlatformDetector.detect()
        >>> print(f"Running on {info.os_name} {info.os_version}")
        Running on Windows 10.0.19041

        >>> if PlatformDetector.is_windows():
        ...     print("Windows-specific code")
        Windows-specific code

    """

    _cached_platform_info: PlatformInfo | None = None

    @staticmethod
    def detect() -> PlatformInfo:
        """Detect the current operating system.

        Time Complexity: O(1) - cached after first call
        Space Complexity: O(1) - single PlatformInfo object

        Returns:
            PlatformInfo containing OS name, version, and architecture

        Raises:
            UnsupportedPlatformError: If OS is not Windows, macOS, Linux, Android, or iOS

        Example:
            >>> info = PlatformDetector.detect()
            >>> assert info.os_name in ["Windows", "macOS", "Linux", "Android", "iOS"]

        """
        # Return cached result if available (O(1) fast path)
        if PlatformDetector._cached_platform_info is not None:
            return PlatformDetector._cached_platform_info

        # Detect OS using platform.system()
        system = platform.system()

        # Map platform.system() output to standardized OS names
        if system == "Windows":
            os_name = "Windows"
        elif system == "Darwin":
            os_name = "macOS"
        elif system == "Linux":
            # Check if running on Android (Linux kernel but Android userspace)
            os_name = "Android" if _is_android() else "Linux"
        elif system == "Java":
            # Check if running on Android via Jython
            if _is_android():
                os_name = "Android"
            else:
                msg = (
                    f"Unsupported platform: {system}. "
                    f"Supported platforms: Windows, macOS, Linux, Android, iOS"
                )
                raise UnsupportedPlatformError(
                    msg,
                )
        # Check for iOS (not directly detectable via platform.system())
        elif _is_ios():
            os_name = "iOS"
        else:
            msg = (
                f"Unsupported platform: {system}. "
                f"Supported platforms: Windows, macOS, Linux, Android, iOS"
            )
            raise UnsupportedPlatformError(
                msg,
            )

        # Get OS version
        os_version = platform.release()

        # Get architecture
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64"):
            architecture = "x64"
        elif machine in ("i386", "i686", "x86"):
            architecture = "x86"
        elif machine in ("arm64", "aarch64"):
            architecture = "ARM64"
        elif machine.startswith("arm"):
            architecture = "ARM"
        else:
            architecture = machine  # Use raw value if unknown

        # Get Python version and implementation
        python_version = platform.python_version()
        python_implementation = platform.python_implementation()

        # Create PlatformInfo object
        platform_info = PlatformInfo(
            os_name=os_name,
            os_version=os_version,
            architecture=architecture,
            python_version=python_version,
            python_implementation=python_implementation,
        )

        # Cache result for future calls
        PlatformDetector._cached_platform_info = platform_info

        return platform_info

    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows.

        Time Complexity: O(1) - cached detection

        Returns:
            True if running on Windows, False otherwise

        Example:
            >>> if PlatformDetector.is_windows():
            ...     print("Windows detected")

        """
        try:
            return PlatformDetector.detect().os_name == "Windows"
        except UnsupportedPlatformError:
            return False

    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS.

        Time Complexity: O(1) - cached detection

        Returns:
            True if running on macOS, False otherwise

        Example:
            >>> if PlatformDetector.is_macos():
            ...     print("macOS detected")

        """
        try:
            return PlatformDetector.detect().os_name == "macOS"
        except UnsupportedPlatformError:
            return False

    @staticmethod
    def is_linux() -> bool:
        """Check if running on Linux.

        Time Complexity: O(1) - cached detection

        Returns:
            True if running on Linux, False otherwise

        Example:
            >>> if PlatformDetector.is_linux():
            ...     print("Linux detected")

        """
        try:
            return PlatformDetector.detect().os_name == "Linux"
        except UnsupportedPlatformError:
            return False

    @staticmethod
    def is_android() -> bool:
        """Check if running on Android.

        Time Complexity: O(1) - cached detection

        Returns:
            True if running on Android, False otherwise

        Example:
            >>> if PlatformDetector.is_android():
            ...     print("Android detected")

        """
        try:
            return PlatformDetector.detect().os_name == "Android"
        except UnsupportedPlatformError:
            return False

    @staticmethod
    def is_ios() -> bool:
        """Check if running on iOS.

        Time Complexity: O(1) - cached detection

        Returns:
            True if running on iOS, False otherwise

        Example:
            >>> if PlatformDetector.is_ios():
            ...     print("iOS detected")

        """
        try:
            return PlatformDetector.detect().os_name == "iOS"
        except UnsupportedPlatformError:
            return False

    @staticmethod
    def is_mobile() -> bool:
        """Check if running on a mobile platform (Android or iOS).

        Time Complexity: O(1) - cached detection

        Returns:
            True if running on Android or iOS, False otherwise

        Example:
            >>> if PlatformDetector.is_mobile():
            ...     print("Mobile platform detected")

        """
        try:
            os_name = PlatformDetector.detect().os_name
            return os_name in ("Android", "iOS")
        except UnsupportedPlatformError:
            return False

    @staticmethod
    def is_desktop() -> bool:
        """Check if running on a desktop platform (Windows, macOS, or Linux).

        Time Complexity: O(1) - cached detection

        Returns:
            True if running on Windows, macOS, or Linux, False otherwise

        Example:
            >>> if PlatformDetector.is_desktop():
            ...     print("Desktop platform detected")

        """
        try:
            os_name = PlatformDetector.detect().os_name
            return os_name in ("Windows", "macOS", "Linux")
        except UnsupportedPlatformError:
            return False


def _is_android() -> bool:
    """Check if running on Android.

    Android detection is tricky because Android uses the Linux kernel,
    so platform.system() returns "Linux". We need additional checks.

    Returns:
        True if running on Android, False otherwise

    """
    # Check for Android-specific environment variables
    if "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
        return True

    # Check for Android-specific system properties
    try:
        if _os.path.exists("/system/build.prop"):
            return True
    except OSError as exc:
        import logging as _logging

        _logging.getLogger(__name__).debug("Android build.prop check failed: %s", exc)

    # Check sys.platform for Android indicators
    if "android" in sys.platform.lower():
        return True

    return False


def _is_ios() -> bool:
    """Check if running on iOS.

    iOS detection is challenging because iOS apps typically run in a sandbox.
    We check for iOS-specific indicators.

    Returns:
        True if running on iOS, False otherwise

    """
    # Check sys.platform for iOS indicators
    if "ios" in sys.platform.lower() or "darwin" in sys.platform.lower():
        # Additional check: iOS has specific characteristics
        try:
            import os

            # iOS apps run in a sandboxed environment
            if os.path.exists("/var/mobile"):
                return True
        except OSError as exc:
            import logging as _logging

            _logging.getLogger(__name__).debug("iOS /var/mobile check failed: %s", exc)

    return False
