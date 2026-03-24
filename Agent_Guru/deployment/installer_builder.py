"""
Installer Builder for the Guru Deployment System.

Generates platform-specific installer configurations for:
- Windows MSI (WiX Toolset)
- macOS DMG
- Linux DEB/RPM/AppImage
- Android APK/AAB (buildozer)
- iOS IPA (Kivy-iOS/BeeWare)

Note: Actual compilation requires platform-specific toolchains.
This module generates the configuration files and build scripts.
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class WindowsInstallerConfig:
    """Configuration for Windows MSI installer."""

    app_name: str
    version: str
    manufacturer: str
    install_dir: str = r"C:\Program Files\AgentGuru"
    icon_path: Optional[Path] = None
    license_path: Optional[Path] = None
    start_menu_shortcut: bool = True
    desktop_shortcut: bool = True
    auto_start: bool = False
    silent_install: bool = True


@dataclass
class MacOSInstallerConfig:
    """Configuration for macOS DMG installer."""

    app_name: str
    version: str
    bundle_id: str
    icon_path: Optional[Path] = None
    background_path: Optional[Path] = None
    code_sign_identity: Optional[str] = None
    notarize: bool = False
    min_macos_version: str = "11.0"


@dataclass
class LinuxPackageConfig:
    """Configuration for Linux packages (DEB/RPM/AppImage)."""

    app_name: str
    version: str
    maintainer: str
    description: str
    homepage: str = ""
    icon_path: Optional[Path] = None
    categories: list[str] = field(default_factory=lambda: ["Utility", "AI"])
    dependencies: list[str] = field(default_factory=list)


@dataclass
class AndroidBuildConfig:
    """Configuration for Android APK/AAB build."""

    app_name: str
    package_name: str  # e.g., "com.agent.guru"
    version_code: int
    version_name: str
    min_sdk_version: int = 24
    target_sdk_version: int = 34
    permissions: list[str] = field(default_factory=list)
    icon_path: Optional[Path] = None
    splash_screen_path: Optional[Path] = None
    enable_crashlytics: bool = True
    enable_proguard: bool = True


@dataclass
class IOSBuildConfig:
    """Configuration for iOS IPA build."""

    app_name: str
    bundle_identifier: str  # e.g., "com.agent.guru"
    version: str
    build_number: int
    min_ios_version: str = "14.0"
    permissions: dict[str, str] = field(default_factory=dict)
    icon_path: Optional[Path] = None
    launch_screen_path: Optional[Path] = None
    enable_crashlytics: bool = True
    team_id: str = ""
    provisioning_profile_name: str = ""


class InstallerBuilder:
    """
    Generates installer configurations and build scripts.

    Actual compilation requires platform-specific toolchains:
    - Windows: WiX Toolset (candle.exe, light.exe)
    - macOS: hdiutil, codesign, notarytool
    - Linux: dpkg-deb, rpmbuild, appimagetool
    - Android: buildozer, python-for-android
    - iOS: Kivy-iOS, xcodebuild
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Windows MSI
    # ------------------------------------------------------------------

    def generate_windows_wix(self, config: WindowsInstallerConfig) -> Path:
        """
        Generate WiX Toolset XML configuration for Windows MSI.

        Returns path to the generated .wxs file.
        """
        wxs_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Product Id="*"
           Name="{config.app_name}"
           Language="1033"
           Version="{config.version}"
           Manufacturer="{config.manufacturer}"
           UpgradeCode="{{12345678-1234-1234-1234-123456789012}}">

    <Package InstallerVersion="200" Compressed="yes" InstallScope="perMachine" />

    <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />
    <MediaTemplate EmbedCab="yes" />

    <Feature Id="ProductFeature" Title="{config.app_name}" Level="1">
      <ComponentGroupRef Id="ProductComponents" />
    </Feature>

    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="ProgramFilesFolder">
        <Directory Id="INSTALLFOLDER" Name="{config.app_name}" />
      </Directory>
      {self._start_menu_dir(config.app_name) if config.start_menu_shortcut else ""}
    </Directory>

    <ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER">
      <Component Id="MainExecutable" Guid="*">
        <File Id="AgentGuruExe" Source="AgentGuru.exe" KeyPath="yes" />
        {self._registry_entry() if not config.start_menu_shortcut else ""}
      </Component>
    </ComponentGroup>

  </Product>
</Wix>
"""
        out_path = self._output_dir / "installer.wxs"
        out_path.write_text(wxs_content)
        logger.info("windows_wix_generated", path=str(out_path))
        return out_path

    def build_windows_msi(self, config: WindowsInstallerConfig) -> Optional[Path]:
        """
        Build Windows MSI using WiX Toolset (requires candle.exe + light.exe).

        Returns path to MSI if successful, None if toolchain not available.

        Raises:
            ValueError: If config values contain path traversal sequences.
        """
        wxs_path = self.generate_windows_wix(config)
        # Sanitize version/name before embedding in filenames
        safe_name = self._safe_filename(config.app_name)
        safe_version = self._safe_filename(config.version)
        msi_path = self._output_dir / f"{safe_name}-{safe_version}.msi"

        if platform.system() != "Windows":
            logger.warning("windows_msi_requires_windows")
            return None

        try:
            wixobj = self._output_dir / "installer.wixobj"
            # shell=False (explicit) with a list — no shell interpolation possible.
            # All paths are resolved under self._output_dir; no user-controlled
            # shell expansion.  nosec B603: shell=False, args are internally built.
            subprocess.run(  # nosec B603
                ["candle.exe", str(wxs_path), "-o", str(wixobj)],
                check=True,
                capture_output=True,
                shell=False,  # explicit — never allow shell=True here
            )
            subprocess.run(  # nosec B603
                ["light.exe", str(wixobj), "-o", str(msi_path)],
                check=True,
                capture_output=True,
                shell=False,
            )
            logger.info("windows_msi_built", path=str(msi_path))
            return msi_path
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.warning("windows_msi_build_failed", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # macOS DMG
    # ------------------------------------------------------------------

    def generate_macos_plist(self, config: MacOSInstallerConfig) -> Path:
        """Generate Info.plist for macOS app bundle."""
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{config.app_name}</string>
    <key>CFBundleIdentifier</key>
    <string>{config.bundle_id}</string>
    <key>CFBundleVersion</key>
    <string>{config.version}</string>
    <key>CFBundleShortVersionString</key>
    <string>{config.version}</string>
    <key>CFBundleExecutable</key>
    <string>{config.app_name}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>{config.min_macos_version}</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Agent Guru needs microphone access for voice commands.</string>
    <key>NSCameraUsageDescription</key>
    <string>Agent Guru needs camera access for face recognition.</string>
</dict>
</plist>
"""
        out_path = self._output_dir / "Info.plist"
        out_path.write_text(plist)
        logger.info("macos_plist_generated", path=str(out_path))
        return out_path

    # ------------------------------------------------------------------
    # Linux packages
    # ------------------------------------------------------------------

    def generate_linux_desktop_entry(self, config: LinuxPackageConfig) -> Path:
        """Generate .desktop file for Linux desktop integration."""
        categories = ";".join(config.categories)
        entry = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={config.app_name}
Comment={config.description}
Exec=/usr/bin/agent-guru
Icon=agent-guru
Categories={categories};
Terminal=false
StartupNotify=true
"""
        out_path = self._output_dir / "agent-guru.desktop"
        out_path.write_text(entry)
        logger.info("linux_desktop_entry_generated", path=str(out_path))
        return out_path

    def generate_debian_control(self, config: LinuxPackageConfig) -> Path:
        """Generate Debian control file for DEB package."""
        deps = ", ".join(config.dependencies) if config.dependencies else "python3 (>= 3.11)"
        control = f"""Package: agent-guru
Version: {config.version}
Section: utils
Priority: optional
Architecture: amd64
Depends: {deps}
Maintainer: {config.maintainer}
Description: {config.description}
 Agent Guru is a world-class AI voice assistant.
Homepage: {config.homepage}
"""
        out_path = self._output_dir / "control"
        out_path.write_text(control)
        logger.info("debian_control_generated", path=str(out_path))
        return out_path

    # ------------------------------------------------------------------
    # Android
    # ------------------------------------------------------------------

    def generate_buildozer_spec(self, config: AndroidBuildConfig) -> Path:
        """Generate buildozer.spec for Android APK/AAB build."""
        permissions = "\n".join(
            f"android.permissions = {p}" for p in config.permissions
        ) if config.permissions else "android.permissions = INTERNET,RECORD_AUDIO,CAMERA"

        spec = f"""[app]
title = {config.app_name}
package.name = {config.package_name.split('.')[-1]}
package.domain = {'.'.join(config.package_name.split('.')[:-1])}
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = {config.version_name}
requirements = python3,kivy

[buildozer]
log_level = 2
warn_on_root = 1

[android]
android.minapi = {config.min_sdk_version}
android.api = {config.target_sdk_version}
android.ndk = 25b
android.accept_sdk_license = True
{permissions}
android.gradle_dependencies = com.google.firebase:firebase-crashlytics:18.6.0
android.enable_androidx = True
"""
        out_path = self._output_dir / "buildozer.spec"
        out_path.write_text(spec)
        logger.info("buildozer_spec_generated", path=str(out_path))
        return out_path

    def generate_android_manifest(self, config: AndroidBuildConfig) -> Path:
        """Generate AndroidManifest.xml template."""
        permissions_xml = "\n    ".join(
            f'<uses-permission android:name="android.permission.{p}" />'
            for p in config.permissions
        )
        manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{config.package_name}"
    android:versionCode="{config.version_code}"
    android:versionName="{config.version_name}">

    <uses-sdk
        android:minSdkVersion="{config.min_sdk_version}"
        android:targetSdkVersion="{config.target_sdk_version}" />

    {permissions_xml}

    <application
        android:label="{config.app_name}"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:allowBackup="true"
        android:theme="@style/AppTheme">

        <activity android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

    </application>
</manifest>
"""
        out_path = self._output_dir / "AndroidManifest.xml"
        out_path.write_text(manifest)
        logger.info("android_manifest_generated", path=str(out_path))
        return out_path

    # ------------------------------------------------------------------
    # iOS
    # ------------------------------------------------------------------

    def generate_ios_info_plist(self, config: IOSBuildConfig) -> Path:
        """Generate Info.plist for iOS app."""
        permissions_xml = "\n    ".join(
            f"<key>{k}</key>\n    <string>{v}</string>"
            for k, v in config.permissions.items()
        )
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{config.app_name}</string>
    <key>CFBundleIdentifier</key>
    <string>{config.bundle_identifier}</string>
    <key>CFBundleVersion</key>
    <string>{config.build_number}</string>
    <key>CFBundleShortVersionString</key>
    <string>{config.version}</string>
    <key>MinimumOSVersion</key>
    <string>{config.min_ios_version}</string>
    <key>UIRequiredDeviceCapabilities</key>
    <array>
        <string>armv7</string>
    </array>
    {permissions_xml}
</dict>
</plist>
"""
        out_path = self._output_dir / "Info.plist"
        out_path.write_text(plist)
        logger.info("ios_info_plist_generated", path=str(out_path))
        return out_path

    def get_supported_platforms(self) -> list[str]:
        """Return list of platforms this builder can generate configs for."""
        return ["windows", "macos", "linux", "android", "ios"]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_filename(value: str) -> str:
        """
        Strip characters that are unsafe in filenames or shell arguments.

        Allows alphanumerics, dots, hyphens, and underscores only.
        Raises ValueError if the result is empty.
        """
        import re
        sanitized = re.sub(r"[^\w.\-]", "_", value)
        if not sanitized:
            raise ValueError(f"Filename component '{value}' is empty after sanitization")
        return sanitized

    @staticmethod
    def _start_menu_dir(app_name: str) -> str:
        return (
            f"<Directory Id='ProgramMenuFolder'>"
            f"<Directory Id='ApplicationProgramsFolder' Name='{app_name}'/>"
            f"</Directory>"
        )

    @staticmethod
    def _registry_entry() -> str:
        return (
            "<RegistryValue Root='HKCU' Key='Software\\AgentGuru' "
            "Name='InstallDir' Type='string' Value='[INSTALLFOLDER]' KeyPath='no' />"
        )
