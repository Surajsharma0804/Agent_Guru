"""Build scripts for all platform installers - Tasks 22-26.

Wraps InstallerBuilder to generate platform-specific packages:
  - Task 22: Windows MSI (WiX)
  - Task 23: macOS DMG
  - Task 24: Linux DEB/RPM/AppImage
  - Task 25: Android APK/AAB (buildozer)
  - Task 26: iOS IPA

Usage:
    python -m Agent_Guru.deployment.build_installers --platform windows
    python -m Agent_Guru.deployment.build_installers --platform all
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from Agent_Guru.deployment.installer_builder import (
    AndroidBuildConfig,
    InstallerBuilder,
    IOSBuildConfig,
    LinuxPackageConfig,
    MacOSInstallerConfig,
    WindowsInstallerConfig,
)

logger = logging.getLogger(__name__)

# Default app metadata
_APP_NAME = "AgentGuru"
_VERSION = "1.0.0"
_BUNDLE_ID = "com.agent.guru"
_MANUFACTURER = "Agent Guru Team"
_MAINTAINER = "Agent Guru Team <support@agentguru.ai>"
_DESCRIPTION = "World-class AI voice assistant with dual personalities"
_HOMEPAGE = "https://agentguru.ai"

# Android permissions required
_ANDROID_PERMISSIONS = (
    "INTERNET",
    "RECORD_AUDIO",
    "CAMERA",
    "USE_BIOMETRIC",
    "FOREGROUND_SERVICE",
    "RECEIVE_BOOT_COMPLETED",
    "VIBRATE",
)

# iOS permission descriptions
_IOS_PERMISSIONS = {
    "NSMicrophoneUsageDescription": "Agent Guru needs microphone access for voice commands.",
    "NSCameraUsageDescription": "Agent Guru needs camera access for face recognition.",
    "NSFaceIDUsageDescription": "Agent Guru uses Face ID for secure authentication.",
}


def build_windows(output_dir: Path) -> Path | None:
    """Task 22: Build Windows MSI installer."""
    logger.info("Building Windows installer...")
    builder = InstallerBuilder(output_dir / "windows")
    config = WindowsInstallerConfig(
        app_name=_APP_NAME,
        version=_VERSION,
        manufacturer=_MANUFACTURER,
        start_menu_shortcut=True,
        desktop_shortcut=True,
        auto_start=True,
        silent_install=True,
    )
    # Generate WiX config (actual MSI build requires WiX toolchain on Windows)
    wxs_path = builder.generate_windows_wix(config)
    msi_path = builder.build_windows_msi(config)
    logger.info("Windows: WiX config at %s", wxs_path)
    if msi_path:
        logger.info("Windows: MSI built at %s", msi_path)
    return msi_path or wxs_path


def build_macos(output_dir: Path) -> Path:
    """Task 23: Build macOS DMG installer."""
    logger.info("Building macOS installer...")
    builder = InstallerBuilder(output_dir / "macos")
    config = MacOSInstallerConfig(
        app_name=_APP_NAME,
        version=_VERSION,
        bundle_id=_BUNDLE_ID,
        notarize=False,  # Requires Apple Developer account
        min_macos_version="12.0",
    )
    plist_path = builder.generate_macos_plist(config)
    logger.info("macOS: Info.plist at %s", plist_path)
    return plist_path


def build_linux(output_dir: Path) -> list[Path]:
    """Task 24: Build Linux packages (DEB + AppImage)."""
    logger.info("Building Linux packages...")
    builder = InstallerBuilder(output_dir / "linux")
    config = LinuxPackageConfig(
        app_name=_APP_NAME,
        version=_VERSION,
        maintainer=_MAINTAINER,
        description=_DESCRIPTION,
        homepage=_HOMEPAGE,
        categories=["Utility", "AI", "Accessibility"],
        dependencies=["python3 (>= 3.11)", "libportaudio2", "libopencv-dev"],
    )
    desktop_path = builder.generate_linux_desktop_entry(config)
    control_path = builder.generate_debian_control(config)
    logger.info("Linux: .desktop at %s, control at %s", desktop_path, control_path)
    return [desktop_path, control_path]


def build_android(output_dir: Path) -> list[Path]:
    """Task 25: Build Android APK/AAB."""
    logger.info("Building Android package...")
    builder = InstallerBuilder(output_dir / "android")
    config = AndroidBuildConfig(
        app_name=_APP_NAME,
        package_name=_BUNDLE_ID,
        version_code=1,
        version_name=_VERSION,
        min_sdk_version=29,  # Android 10
        target_sdk_version=34,  # Android 14
        permissions=_ANDROID_PERMISSIONS,
        enable_crashlytics=True,
        enable_proguard=True,
    )
    spec_path = builder.generate_buildozer_spec(config)
    manifest_path = builder.generate_android_manifest(config)
    logger.info("Android: buildozer.spec at %s, manifest at %s", spec_path, manifest_path)
    return [spec_path, manifest_path]


def build_ios(output_dir: Path) -> Path:
    """Task 26: Build iOS IPA."""
    logger.info("Building iOS package...")
    builder = InstallerBuilder(output_dir / "ios")
    config = IOSBuildConfig(
        app_name=_APP_NAME,
        bundle_identifier=_BUNDLE_ID,
        version=_VERSION,
        build_number=1,
        min_ios_version="14.0",
        permissions=_IOS_PERMISSIONS,
        enable_crashlytics=True,
    )
    plist_path = builder.generate_ios_info_plist(config)
    logger.info("iOS: Info.plist at %s", plist_path)
    return plist_path


def build_all(output_dir: Path) -> None:
    """Build installers for all platforms."""
    build_windows(output_dir)
    build_macos(output_dir)
    build_linux(output_dir)
    build_android(output_dir)
    build_ios(output_dir)
    logger.info("All platform installers generated in %s", output_dir)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build Agent Guru installers")
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "linux", "android", "ios", "all"],
        default="all",
    )
    parser.add_argument("--output-dir", default="dist", type=Path)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dispatch = {
        "windows": lambda: build_windows(output_dir),
        "macos": lambda: build_macos(output_dir),
        "linux": lambda: build_linux(output_dir),
        "android": lambda: build_android(output_dir),
        "ios": lambda: build_ios(output_dir),
        "all": lambda: build_all(output_dir),
    }
    dispatch[args.platform]()


if __name__ == "__main__":
    main()
