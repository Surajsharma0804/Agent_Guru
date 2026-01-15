"""
Platform Capability Matrix.

Provides comprehensive documentation and runtime query API for platform capabilities.
Documents honest, accurate capabilities per platform with no security illusions.

CRITICAL RULES:
1. Capability matrix must be 100% accurate and honest
2. No overstating capabilities (security risk)
3. No understating capabilities (user frustration)
4. All capabilities must be programmatically queryable
5. Capability matrix must be included in user documentation
6. Platform limitations must be explicitly documented

Validates: Requirements 41.1, 41.2, 41.3, 41.4, 41.5, 41.6, 41.7
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Literal, Optional


class CapabilityLevel(Enum):
    """
    Capability level enumeration.

    Levels:
        FULL: Complete functionality with no restrictions
        PARTIAL: Reduced functionality or requires special permissions
        LIMITED: Severely restricted functionality
        NONE: Not available on this platform
    """

    FULL = "full"
    PARTIAL = "partial"
    LIMITED = "limited"
    NONE = "none"


@dataclass(frozen=True)
class Capability:
    """
    Represents a single platform capability.

    Attributes:
        name: Capability name (e.g., "open_apps", "type_text")
        level: Capability level (FULL, PARTIAL, LIMITED, NONE)
        description: Human-readable description of capability
        restrictions: List of restrictions or requirements (empty if FULL)
        implementation: Implementation details (API/framework used)
    """

    name: str
    level: CapabilityLevel
    description: str
    restrictions: List[str]
    implementation: str

    def is_available(self) -> bool:
        """Check if capability is available (not NONE)."""
        return self.level != CapabilityLevel.NONE

    def is_full(self) -> bool:
        """Check if capability is fully available."""
        return self.level == CapabilityLevel.FULL

    def has_restrictions(self) -> bool:
        """Check if capability has restrictions."""
        return len(self.restrictions) > 0


@dataclass(frozen=True)
class PlatformCapabilities:
    """
    Complete capability set for a single platform.

    Organizes capabilities by category:
        - Application Control
        - Input Automation
        - Speech (TTS/STT)
        - Biometric Authentication
        - Security Enforcement
        - Memory & Storage

    Attributes:
        platform: Platform identifier (windows, macos, android, ios)
        application_control: Application control capabilities
        input_automation: Input automation capabilities
        speech: Speech capabilities (TTS/STT)
        biometric: Biometric authentication capabilities
        security: Security enforcement capabilities
        memory: Memory and storage capabilities
        authority_scope: Authority scope (system-wide or app-level)
    """

    platform: Literal["windows", "macos", "android", "ios"]
    application_control: Dict[str, Capability]
    input_automation: Dict[str, Capability]
    speech: Dict[str, Capability]
    biometric: Dict[str, Capability]
    security: Dict[str, Capability]
    memory: Dict[str, Capability]
    authority_scope: Literal["system-wide", "app-level"]

    def get_capability(self, category: str, name: str) -> Optional[Capability]:
        """
        Get a specific capability by category and name.

        Args:
            category: Capability category (application_control, input_automation, etc.)
            name: Capability name within category

        Returns:
            Capability object if found, None otherwise
        """
        category_map = {
            "application_control": self.application_control,
            "input_automation": self.input_automation,
            "speech": self.speech,
            "biometric": self.biometric,
            "security": self.security,
            "memory": self.memory,
        }

        if category not in category_map:
            return None

        return category_map[category].get(name)

    def get_all_capabilities(self) -> Dict[str, Dict[str, Capability]]:
        """Get all capabilities organized by category."""
        return {
            "application_control": self.application_control,
            "input_automation": self.input_automation,
            "speech": self.speech,
            "biometric": self.biometric,
            "security": self.security,
            "memory": self.memory,
        }

    def get_limitations(self) -> List[str]:
        """
        Get list of all platform limitations.

        Returns:
            List of human-readable limitation descriptions
        """
        limitations = []

        for category_name, category_caps in self.get_all_capabilities().items():
            for cap_name, capability in category_caps.items():
                if capability.level == CapabilityLevel.NONE:
                    limitations.append(f"{category_name}.{cap_name}: Not available - {capability.description}")
                elif capability.level in (CapabilityLevel.PARTIAL, CapabilityLevel.LIMITED):
                    limitations.append(
                        f"{category_name}.{cap_name}: {capability.level.value.capitalize()} - "
                        f"{', '.join(capability.restrictions)}"
                    )

        return limitations


class CapabilityMatrix:
    """
    Platform Capability Matrix.

    Provides comprehensive documentation and runtime query API for all platform
    capabilities across Windows, macOS, Android, and iOS.

    CRITICAL: This matrix documents HONEST capabilities per platform.
    No security illusions. No overstating. No understating.

    Usage:
        >>> matrix = CapabilityMatrix()
        >>> windows_caps = matrix.get_platform_capabilities("windows")
        >>> can_type = windows_caps.get_capability("input_automation", "type_text")
        >>> print(can_type.level)
        CapabilityLevel.FULL

        >>> ios_caps = matrix.get_platform_capabilities("ios")
        >>> can_close = ios_caps.get_capability("application_control", "close_apps")
        >>> print(can_close.level)
        CapabilityLevel.NONE

    Validates: Requirements 41.1, 41.2, 41.3, 41.4, 41.5, 41.6, 41.7
    """

    def __init__(self):
        """Initialize capability matrix with all platform definitions."""
        self._platforms: Dict[str, PlatformCapabilities] = {
            "windows": self._define_windows_capabilities(),
            "macos": self._define_macos_capabilities(),
            "android": self._define_android_capabilities(),
            "ios": self._define_ios_capabilities(),
        }

    def get_platform_capabilities(self, platform: str) -> Optional[PlatformCapabilities]:
        """
        Get capabilities for a specific platform.

        Args:
            platform: Platform identifier (windows, macos, android, ios)

        Returns:
            PlatformCapabilities object if platform supported, None otherwise
        """
        return self._platforms.get(platform.lower())

    def get_all_platforms(self) -> List[str]:
        """Get list of all supported platforms."""
        return list(self._platforms.keys())

    def compare_platforms(self, capability_category: str, capability_name: str) -> Dict[str, CapabilityLevel]:
        """
        Compare a specific capability across all platforms.

        Args:
            capability_category: Category (application_control, input_automation, etc.)
            capability_name: Capability name within category

        Returns:
            Dictionary mapping platform to capability level
        """
        comparison = {}

        for platform_name, platform_caps in self._platforms.items():
            capability = platform_caps.get_capability(capability_category, capability_name)
            if capability:
                comparison[platform_name] = capability.level
            else:
                comparison[platform_name] = CapabilityLevel.NONE

        return comparison

    def _define_windows_capabilities(self) -> PlatformCapabilities:
        """
        Define Windows platform capabilities.

        Windows provides FULL desktop control with no restrictions.
        Reference implementation for all PAL interfaces.

        Validates: Requirement 41.2
        """
        return PlatformCapabilities(
            platform="windows",
            authority_scope="system-wide",
            # Application Control - FULL
            application_control={
                "open_apps": Capability(
                    name="open_apps",
                    level=CapabilityLevel.FULL,
                    description="Launch any installed application",
                    restrictions=[],
                    implementation="Win32 ShellExecute, CreateProcess",
                ),
                "close_apps": Capability(
                    name="close_apps",
                    level=CapabilityLevel.FULL,
                    description="Close any running application",
                    restrictions=[],
                    implementation="Win32 TerminateProcess, WM_CLOSE",
                ),
                "discover_apps": Capability(
                    name="discover_apps",
                    level=CapabilityLevel.FULL,
                    description="Discover all installed applications",
                    restrictions=[],
                    implementation="Registry scan, Start Menu enumeration",
                ),
                "is_running": Capability(
                    name="is_running",
                    level=CapabilityLevel.FULL,
                    description="Check if application is running",
                    restrictions=[],
                    implementation="Win32 EnumWindows, Process enumeration",
                ),
                "focus_app": Capability(
                    name="focus_app",
                    level=CapabilityLevel.FULL,
                    description="Bring application to foreground",
                    restrictions=[],
                    implementation="Win32 SetForegroundWindow",
                ),
            },
            # Input Automation - FULL
            input_automation={
                "type_text": Capability(
                    name="type_text",
                    level=CapabilityLevel.FULL,
                    description="Type text into any application",
                    restrictions=[],
                    implementation="Win32 SendInput with keyboard events",
                ),
                "click_ui": Capability(
                    name="click_ui",
                    level=CapabilityLevel.FULL,
                    description="Click UI elements in any application",
                    restrictions=[],
                    implementation="Win32 SendInput with mouse events, UI Automation",
                ),
                "press_keys": Capability(
                    name="press_keys",
                    level=CapabilityLevel.FULL,
                    description="Simulate keyboard shortcuts",
                    restrictions=[],
                    implementation="Win32 SendInput with virtual key codes",
                ),
                "move_mouse": Capability(
                    name="move_mouse",
                    level=CapabilityLevel.FULL,
                    description="Control mouse cursor position",
                    restrictions=[],
                    implementation="Win32 SendInput with mouse movement",
                ),
            },
            # Speech - FULL (local models)
            speech={
                "tts": Capability(
                    name="tts",
                    level=CapabilityLevel.FULL,
                    description="Text-to-speech synthesis",
                    restrictions=[],
                    implementation="Windows SAPI (Speech API)",
                ),
                "stt": Capability(
                    name="stt",
                    level=CapabilityLevel.FULL,
                    description="Speech-to-text recognition (local)",
                    restrictions=[],
                    implementation="Whisper.cpp (local model)",
                ),
                "wake_word": Capability(
                    name="wake_word",
                    level=CapabilityLevel.FULL,
                    description="Local wake word detection",
                    restrictions=[],
                    implementation="Whisper.cpp with custom wake word model",
                ),
                "voice_customization": Capability(
                    name="voice_customization",
                    level=CapabilityLevel.FULL,
                    description="Customize TTS voice and parameters",
                    restrictions=[],
                    implementation="SAPI voice selection and rate/volume control",
                ),
            },
            # Biometric Authentication - FULL
            biometric={
                "fingerprint": Capability(
                    name="fingerprint",
                    level=CapabilityLevel.FULL,
                    description="Fingerprint authentication",
                    restrictions=[],
                    implementation="Windows Hello (if hardware available)",
                ),
                "face": Capability(
                    name="face",
                    level=CapabilityLevel.FULL,
                    description="Face recognition authentication",
                    restrictions=[],
                    implementation="Windows Hello (if hardware available)",
                ),
                "hardware_backed": Capability(
                    name="hardware_backed",
                    level=CapabilityLevel.FULL,
                    description="Hardware-backed biometric storage",
                    restrictions=[],
                    implementation="TPM (Trusted Platform Module)",
                ),
            },
            # Security Enforcement - FULL (system-wide)
            security={
                "lock_workstation": Capability(
                    name="lock_workstation",
                    level=CapabilityLevel.FULL,
                    description="Lock entire workstation",
                    restrictions=[],
                    implementation="Win32 LockWorkStation API",
                ),
                "lock_scope": Capability(
                    name="lock_scope",
                    level=CapabilityLevel.FULL,
                    description="System-wide security enforcement",
                    restrictions=[],
                    implementation="Workstation lock affects all applications",
                ),
                "intrusion_detection": Capability(
                    name="intrusion_detection",
                    level=CapabilityLevel.FULL,
                    description="Detect and respond to intrusion attempts",
                    restrictions=[],
                    implementation="Failed auth tracking + workstation lock",
                ),
            },
            # Memory & Storage - FULL
            memory={
                "encrypted_storage": Capability(
                    name="encrypted_storage",
                    level=CapabilityLevel.FULL,
                    description="AES-256-GCM encrypted conversation storage",
                    restrictions=[],
                    implementation="SQLite with AES-256-GCM encryption",
                ),
                "vector_search": Capability(
                    name="vector_search",
                    level=CapabilityLevel.FULL,
                    description="Semantic search over conversations",
                    restrictions=[],
                    implementation="FAISS vector index with sentence-transformers",
                ),
                "automatic_purging": Capability(
                    name="automatic_purging",
                    level=CapabilityLevel.FULL,
                    description="Automatic data retention enforcement",
                    restrictions=[],
                    implementation="90-day retention policy with scheduled purging",
                ),
            },
        )

    def _define_macos_capabilities(self) -> PlatformCapabilities:
        """
        Define macOS platform capabilities.

        macOS provides FULL desktop control with Accessibility permissions required.
        Equivalent to Windows but requires explicit user permission grants.

        Validates: Requirement 41.3
        """
        return PlatformCapabilities(
            platform="macos",
            authority_scope="system-wide",
            # Application Control - FULL
            application_control={
                "open_apps": Capability(
                    name="open_apps",
                    level=CapabilityLevel.FULL,
                    description="Launch any installed application",
                    restrictions=[],
                    implementation="LaunchServices framework, NSWorkspace",
                ),
                "close_apps": Capability(
                    name="close_apps",
                    level=CapabilityLevel.FULL,
                    description="Close any running application",
                    restrictions=[],
                    implementation="Apple Events (quit command), NSRunningApplication",
                ),
                "discover_apps": Capability(
                    name="discover_apps",
                    level=CapabilityLevel.FULL,
                    description="Discover all installed applications",
                    restrictions=[],
                    implementation="NSWorkspace application enumeration, /Applications scan",
                ),
                "is_running": Capability(
                    name="is_running",
                    level=CapabilityLevel.FULL,
                    description="Check if application is running",
                    restrictions=[],
                    implementation="NSWorkspace runningApplications",
                ),
                "focus_app": Capability(
                    name="focus_app",
                    level=CapabilityLevel.FULL,
                    description="Bring application to foreground",
                    restrictions=[],
                    implementation="NSRunningApplication activateWithOptions",
                ),
            },
            # Input Automation - FULL (requires Accessibility permission)
            input_automation={
                "type_text": Capability(
                    name="type_text",
                    level=CapabilityLevel.FULL,
                    description="Type text into any application",
                    restrictions=["Requires Accessibility permission grant"],
                    implementation="CGEvent keyboard events",
                ),
                "click_ui": Capability(
                    name="click_ui",
                    level=CapabilityLevel.FULL,
                    description="Click UI elements in any application",
                    restrictions=["Requires Accessibility permission grant"],
                    implementation="CGEvent mouse events, AXUIElement",
                ),
                "press_keys": Capability(
                    name="press_keys",
                    level=CapabilityLevel.FULL,
                    description="Simulate keyboard shortcuts",
                    restrictions=["Requires Accessibility permission grant"],
                    implementation="CGEvent with key codes and modifiers",
                ),
                "move_mouse": Capability(
                    name="move_mouse",
                    level=CapabilityLevel.FULL,
                    description="Control mouse cursor position",
                    restrictions=["Requires Accessibility permission grant"],
                    implementation="CGEvent mouse movement",
                ),
            },
            # Speech - FULL (local models)
            speech={
                "tts": Capability(
                    name="tts",
                    level=CapabilityLevel.FULL,
                    description="Text-to-speech synthesis",
                    restrictions=[],
                    implementation="NSSpeechSynthesizer",
                ),
                "stt": Capability(
                    name="stt",
                    level=CapabilityLevel.FULL,
                    description="Speech-to-text recognition (local)",
                    restrictions=[],
                    implementation="Whisper.cpp (local model)",
                ),
                "wake_word": Capability(
                    name="wake_word",
                    level=CapabilityLevel.FULL,
                    description="Local wake word detection",
                    restrictions=[],
                    implementation="Whisper.cpp with custom wake word model",
                ),
                "voice_customization": Capability(
                    name="voice_customization",
                    level=CapabilityLevel.FULL,
                    description="Customize TTS voice and parameters",
                    restrictions=[],
                    implementation="NSSpeechSynthesizer voice selection and rate control",
                ),
            },
            # Biometric Authentication - FULL
            biometric={
                "fingerprint": Capability(
                    name="fingerprint",
                    level=CapabilityLevel.FULL,
                    description="Touch ID authentication",
                    restrictions=[],
                    implementation="LocalAuthentication framework (if hardware available)",
                ),
                "face": Capability(
                    name="face",
                    level=CapabilityLevel.FULL,
                    description="Face ID authentication",
                    restrictions=[],
                    implementation="LocalAuthentication framework (if hardware available)",
                ),
                "hardware_backed": Capability(
                    name="hardware_backed",
                    level=CapabilityLevel.FULL,
                    description="Hardware-backed biometric storage",
                    restrictions=[],
                    implementation="Secure Enclave",
                ),
            },
            # Security Enforcement - FULL (system-wide)
            security={
                "lock_workstation": Capability(
                    name="lock_workstation",
                    level=CapabilityLevel.FULL,
                    description="Lock screen (system-wide)",
                    restrictions=[],
                    implementation="CGSession API (CGSessionCopyCurrentDictionary)",
                ),
                "lock_scope": Capability(
                    name="lock_scope",
                    level=CapabilityLevel.FULL,
                    description="System-wide security enforcement",
                    restrictions=[],
                    implementation="Screen lock affects all applications",
                ),
                "intrusion_detection": Capability(
                    name="intrusion_detection",
                    level=CapabilityLevel.FULL,
                    description="Detect and respond to intrusion attempts",
                    restrictions=[],
                    implementation="Failed auth tracking + screen lock",
                ),
            },
            # Memory & Storage - FULL
            memory={
                "encrypted_storage": Capability(
                    name="encrypted_storage",
                    level=CapabilityLevel.FULL,
                    description="AES-256-GCM encrypted conversation storage",
                    restrictions=[],
                    implementation="SQLite with AES-256-GCM encryption",
                ),
                "vector_search": Capability(
                    name="vector_search",
                    level=CapabilityLevel.FULL,
                    description="Semantic search over conversations",
                    restrictions=[],
                    implementation="FAISS vector index with sentence-transformers",
                ),
                "automatic_purging": Capability(
                    name="automatic_purging",
                    level=CapabilityLevel.FULL,
                    description="Automatic data retention enforcement",
                    restrictions=[],
                    implementation="90-day retention policy with scheduled purging",
                ),
            },
        )

    def _define_android_capabilities(self) -> PlatformCapabilities:
        """
        Define Android platform capabilities.

        Android provides PARTIAL automation via Accessibility Service.
        App-level authority scope only. No system-wide control.

        CRITICAL LIMITATIONS:
        - Input automation requires Accessibility Service permission
        - Authority scope limited to app-level (cannot control system)
        - STT may use system service or local Whisper (user choice)

        Validates: Requirement 41.4
        """
        return PlatformCapabilities(
            platform="android",
            authority_scope="app-level",
            # Application Control - FULL (via Intent system)
            application_control={
                "open_apps": Capability(
                    name="open_apps",
                    level=CapabilityLevel.FULL,
                    description="Launch any installed application",
                    restrictions=[],
                    implementation="Intent system (startActivity)",
                ),
                "close_apps": Capability(
                    name="close_apps",
                    level=CapabilityLevel.FULL,
                    description="Close applications",
                    restrictions=["Can only close apps that support finish() intent"],
                    implementation="ActivityManager, finish() intent",
                ),
                "discover_apps": Capability(
                    name="discover_apps",
                    level=CapabilityLevel.FULL,
                    description="Discover all installed applications",
                    restrictions=[],
                    implementation="PackageManager.getInstalledApplications()",
                ),
                "is_running": Capability(
                    name="is_running",
                    level=CapabilityLevel.FULL,
                    description="Check if application is running",
                    restrictions=["Requires QUERY_ALL_PACKAGES permission (Android 11+)"],
                    implementation="ActivityManager.getRunningAppProcesses()",
                ),
                "focus_app": Capability(
                    name="focus_app",
                    level=CapabilityLevel.FULL,
                    description="Bring application to foreground",
                    restrictions=[],
                    implementation="Intent with FLAG_ACTIVITY_NEW_TASK",
                ),
            },
            # Input Automation - PARTIAL (Accessibility Service required)
            input_automation={
                "type_text": Capability(
                    name="type_text",
                    level=CapabilityLevel.PARTIAL,
                    description="Type text into applications",
                    restrictions=[
                        "Requires Accessibility Service permission",
                        "Only works in apps that support accessibility",
                        "Cannot interact with system UI",
                        "User must manually grant permission",
                    ],
                    implementation="AccessibilityService with ACTION_SET_TEXT",
                ),
                "click_ui": Capability(
                    name="click_ui",
                    level=CapabilityLevel.PARTIAL,
                    description="Click UI elements",
                    restrictions=[
                        "Requires Accessibility Service permission",
                        "Only works in apps that support accessibility",
                        "Cannot interact with system UI",
                        "User must manually grant permission",
                    ],
                    implementation="AccessibilityService with performAction(ACTION_CLICK)",
                ),
                "press_keys": Capability(
                    name="press_keys",
                    level=CapabilityLevel.PARTIAL,
                    description="Simulate keyboard shortcuts",
                    restrictions=[
                        "Requires Accessibility Service permission",
                        "Limited to accessibility-supported actions",
                        "Cannot send arbitrary key events",
                    ],
                    implementation="AccessibilityService with performGlobalAction()",
                ),
                "move_mouse": Capability(
                    name="move_mouse",
                    level=CapabilityLevel.NONE,
                    description="Mouse control not applicable on touchscreen",
                    restrictions=["Android uses touch events, not mouse"],
                    implementation="N/A",
                ),
            },
            # Speech - PARTIAL (system STT option)
            speech={
                "tts": Capability(
                    name="tts",
                    level=CapabilityLevel.FULL,
                    description="Text-to-speech synthesis",
                    restrictions=[],
                    implementation="Android TextToSpeech API",
                ),
                "stt": Capability(
                    name="stt",
                    level=CapabilityLevel.PARTIAL,
                    description="Speech-to-text recognition",
                    restrictions=[
                        "User choice: local Whisper.cpp OR system STT",
                        "System STT requires network and Google services",
                        "Local Whisper requires significant device resources",
                    ],
                    implementation="Whisper.cpp (local) OR SpeechRecognizer API (system)",
                ),
                "wake_word": Capability(
                    name="wake_word",
                    level=CapabilityLevel.PARTIAL,
                    description="Wake word detection",
                    restrictions=[
                        "Local Whisper.cpp if available",
                        "May fall back to system hotword detection",
                        "Battery impact with local processing",
                    ],
                    implementation="Whisper.cpp (local) OR system hotword API",
                ),
                "voice_customization": Capability(
                    name="voice_customization",
                    level=CapabilityLevel.FULL,
                    description="Customize TTS voice and parameters",
                    restrictions=[],
                    implementation="TextToSpeech voice selection and rate/pitch control",
                ),
            },
            # Biometric Authentication - FULL
            biometric={
                "fingerprint": Capability(
                    name="fingerprint",
                    level=CapabilityLevel.FULL,
                    description="Fingerprint authentication",
                    restrictions=[],
                    implementation="BiometricPrompt API (if hardware available)",
                ),
                "face": Capability(
                    name="face",
                    level=CapabilityLevel.FULL,
                    description="Face recognition authentication",
                    restrictions=[],
                    implementation="BiometricPrompt API (if hardware available)",
                ),
                "hardware_backed": Capability(
                    name="hardware_backed",
                    level=CapabilityLevel.FULL,
                    description="Hardware-backed biometric storage",
                    restrictions=[],
                    implementation="Android Keystore with StrongBox (if available)",
                ),
            },
            # Security Enforcement - PARTIAL (app + screen lock)
            security={
                "lock_workstation": Capability(
                    name="lock_workstation",
                    level=CapabilityLevel.PARTIAL,
                    description="Lock screen and exit app",
                    restrictions=[
                        "Can only lock screen, not full device",
                        "User can unlock and access other apps",
                        "Authority scope limited to app-level",
                    ],
                    implementation="DevicePolicyManager.lockNow() + app exit",
                ),
                "lock_scope": Capability(
                    name="lock_scope",
                    level=CapabilityLevel.PARTIAL,
                    description="App-level + screen lock",
                    restrictions=[
                        "Cannot prevent access to other apps after unlock",
                        "Authority scope is app-level only",
                    ],
                    implementation="Screen lock + app state management",
                ),
                "intrusion_detection": Capability(
                    name="intrusion_detection",
                    level=CapabilityLevel.PARTIAL,
                    description="Detect and respond to intrusion attempts",
                    restrictions=["Can only lock screen and exit app", "Cannot enforce system-wide lockdown"],
                    implementation="Failed auth tracking + screen lock + app exit",
                ),
            },
            # Memory & Storage - FULL
            memory={
                "encrypted_storage": Capability(
                    name="encrypted_storage",
                    level=CapabilityLevel.FULL,
                    description="AES-256-GCM encrypted conversation storage",
                    restrictions=[],
                    implementation="SQLite with AES-256-GCM encryption, Android Keystore",
                ),
                "vector_search": Capability(
                    name="vector_search",
                    level=CapabilityLevel.FULL,
                    description="Semantic search over conversations",
                    restrictions=["May be slower on lower-end devices"],
                    implementation="FAISS vector index with sentence-transformers",
                ),
                "automatic_purging": Capability(
                    name="automatic_purging",
                    level=CapabilityLevel.FULL,
                    description="Automatic data retention enforcement",
                    restrictions=[],
                    implementation="90-day retention policy with scheduled purging",
                ),
            },
        )

    def _define_ios_capabilities(self) -> PlatformCapabilities:
        """
        Define iOS platform capabilities.

        iOS has SEVERE limitations due to platform restrictions.
        Command-limited, no system automation, app-level authority only.

        CRITICAL LIMITATIONS:
        - Cannot close apps (iOS restriction)
        - Cannot automate input (iOS restriction)
        - Cannot use local STT models (must use system)
        - Authority scope strictly app-level
        - Can only open apps via deep links (URL schemes)

        HONEST ASSESSMENT: iOS is the most restricted platform.
        Users must have accurate expectations.

        Validates: Requirement 41.5
        """
        return PlatformCapabilities(
            platform="ios",
            authority_scope="app-level",
            # Application Control - LIMITED (deep links only)
            application_control={
                "open_apps": Capability(
                    name="open_apps",
                    level=CapabilityLevel.LIMITED,
                    description="Open apps via deep links only",
                    restrictions=[
                        "Only works for apps with registered URL schemes",
                        "Cannot open arbitrary apps",
                        "Cannot pass complex parameters",
                        "User may see confirmation dialog",
                    ],
                    implementation="UIApplication.openURL with URL schemes",
                ),
                "close_apps": Capability(
                    name="close_apps",
                    level=CapabilityLevel.NONE,
                    description="Cannot close apps (iOS restriction)",
                    restrictions=[
                        "iOS does not allow apps to close other apps",
                        "iOS does not allow apps to close themselves programmatically",
                        "User must manually close apps",
                    ],
                    implementation="N/A - iOS platform restriction",
                ),
                "discover_apps": Capability(
                    name="discover_apps",
                    level=CapabilityLevel.LIMITED,
                    description="Very limited app discovery",
                    restrictions=[
                        "Can only check if specific URL schemes are registered",
                        "Cannot enumerate all installed apps",
                        "Cannot get app names or metadata",
                        "Privacy restriction by iOS",
                    ],
                    implementation="UIApplication.canOpenURL (limited to declared schemes)",
                ),
                "is_running": Capability(
                    name="is_running",
                    level=CapabilityLevel.NONE,
                    description="Cannot check if apps are running (iOS restriction)",
                    restrictions=["iOS does not expose running app information", "Privacy restriction by iOS"],
                    implementation="N/A - iOS platform restriction",
                ),
                "focus_app": Capability(
                    name="focus_app",
                    level=CapabilityLevel.LIMITED,
                    description="Can only open app (which brings it to foreground)",
                    restrictions=["Same limitations as open_apps", "Cannot focus without opening"],
                    implementation="UIApplication.openURL (brings app to foreground)",
                ),
            },
            # Input Automation - NONE (severely restricted)
            input_automation={
                "type_text": Capability(
                    name="type_text",
                    level=CapabilityLevel.NONE,
                    description="Cannot automate text input (iOS restriction)",
                    restrictions=[
                        "iOS does not allow input automation",
                        "No accessibility API for input simulation",
                        "Security restriction by iOS",
                    ],
                    implementation="N/A - iOS platform restriction",
                ),
                "click_ui": Capability(
                    name="click_ui",
                    level=CapabilityLevel.NONE,
                    description="Cannot automate UI interaction (iOS restriction)",
                    restrictions=[
                        "iOS does not allow UI automation from apps",
                        "No accessibility API for UI interaction",
                        "Security restriction by iOS",
                    ],
                    implementation="N/A - iOS platform restriction",
                ),
                "press_keys": Capability(
                    name="press_keys",
                    level=CapabilityLevel.NONE,
                    description="Cannot simulate keyboard input (iOS restriction)",
                    restrictions=["iOS does not allow keyboard simulation", "Security restriction by iOS"],
                    implementation="N/A - iOS platform restriction",
                ),
                "move_mouse": Capability(
                    name="move_mouse",
                    level=CapabilityLevel.NONE,
                    description="Touch events only, no mouse control",
                    restrictions=["iOS uses touch events, not mouse"],
                    implementation="N/A",
                ),
            },
            # Speech - PARTIAL (system STT mandatory)
            speech={
                "tts": Capability(
                    name="tts",
                    level=CapabilityLevel.FULL,
                    description="Text-to-speech synthesis",
                    restrictions=[],
                    implementation="AVSpeechSynthesizer",
                ),
                "stt": Capability(
                    name="stt",
                    level=CapabilityLevel.PARTIAL,
                    description="Speech-to-text (system only)",
                    restrictions=[
                        "MUST use system STT (SFSpeechRecognizer)",
                        "Cannot use local Whisper.cpp models",
                        "Requires network connection",
                        "Requires user permission grant",
                        "Subject to Apple privacy policy",
                    ],
                    implementation="SFSpeechRecognizer (system STT only)",
                ),
                "wake_word": Capability(
                    name="wake_word",
                    level=CapabilityLevel.PARTIAL,
                    description="Wake word detection (system only)",
                    restrictions=[
                        "MUST use system wake word detection",
                        "Cannot use local models",
                        "Limited to system-supported wake words",
                        "Subject to Apple restrictions",
                    ],
                    implementation="System wake word API (limited)",
                ),
                "voice_customization": Capability(
                    name="voice_customization",
                    level=CapabilityLevel.FULL,
                    description="Customize TTS voice and parameters",
                    restrictions=[],
                    implementation="AVSpeechSynthesizer voice selection and rate/pitch control",
                ),
            },
            # Biometric Authentication - FULL
            biometric={
                "fingerprint": Capability(
                    name="fingerprint",
                    level=CapabilityLevel.FULL,
                    description="Touch ID authentication",
                    restrictions=[],
                    implementation="LocalAuthentication framework (if hardware available)",
                ),
                "face": Capability(
                    name="face",
                    level=CapabilityLevel.FULL,
                    description="Face ID authentication",
                    restrictions=[],
                    implementation="LocalAuthentication framework (if hardware available)",
                ),
                "hardware_backed": Capability(
                    name="hardware_backed",
                    level=CapabilityLevel.FULL,
                    description="Hardware-backed biometric storage",
                    restrictions=[],
                    implementation="Secure Enclave",
                ),
            },
            # Security Enforcement - LIMITED (app-only)
            security={
                "lock_workstation": Capability(
                    name="lock_workstation",
                    level=CapabilityLevel.LIMITED,
                    description="Can only exit app (no device lock)",
                    restrictions=[
                        "Cannot lock device from app",
                        "Can only exit GURU app",
                        "User can immediately access other apps",
                        "Authority scope strictly app-level",
                        "iOS platform restriction",
                    ],
                    implementation="App exit only (no device lock capability)",
                ),
                "lock_scope": Capability(
                    name="lock_scope",
                    level=CapabilityLevel.LIMITED,
                    description="App-level only (no system control)",
                    restrictions=[
                        "Cannot enforce system-wide security",
                        "Authority scope strictly app-level",
                        "iOS platform restriction",
                    ],
                    implementation="App state management only",
                ),
                "intrusion_detection": Capability(
                    name="intrusion_detection",
                    level=CapabilityLevel.LIMITED,
                    description="Can only exit app on intrusion",
                    restrictions=[
                        "Cannot lock device",
                        "Can only exit GURU app",
                        "User can immediately reopen app",
                        "Limited security enforcement",
                    ],
                    implementation="Failed auth tracking + app exit",
                ),
            },
            # Memory & Storage - FULL
            memory={
                "encrypted_storage": Capability(
                    name="encrypted_storage",
                    level=CapabilityLevel.FULL,
                    description="AES-256-GCM encrypted conversation storage",
                    restrictions=[],
                    implementation="SQLite with AES-256-GCM encryption, iOS Keychain",
                ),
                "vector_search": Capability(
                    name="vector_search",
                    level=CapabilityLevel.FULL,
                    description="Semantic search over conversations",
                    restrictions=["May be slower on older devices"],
                    implementation="FAISS vector index with sentence-transformers",
                ),
                "automatic_purging": Capability(
                    name="automatic_purging",
                    level=CapabilityLevel.FULL,
                    description="Automatic data retention enforcement",
                    restrictions=[],
                    implementation="90-day retention policy with scheduled purging",
                ),
            },
        )

    def generate_documentation(self, format: str = "markdown") -> str:
        """
        Generate comprehensive capability matrix documentation.

        Args:
            format: Output format ("markdown", "html", "json")

        Returns:
            Formatted documentation string

        Validates: Requirement 41.6 (included in user documentation)
        """
        if format == "markdown":
            return self._generate_markdown_documentation()
        elif format == "json":
            import json

            return json.dumps(self._generate_json_documentation(), indent=2)
        elif format == "html":
            return self._generate_html_documentation()
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_markdown_documentation(self) -> str:
        """Generate Markdown format documentation."""
        lines = [
            "# GURU Platform Capability Matrix",
            "",
            "**CRITICAL**: This matrix documents **honest capabilities** per platform. No security illusions.",
            "",
            "## Legend",
            "",
            "- ✅ **FULL**: Complete functionality with no restrictions",
            "- ⚠️ **PARTIAL**: Reduced functionality or requires special permissions",
            "- 🔶 **LIMITED**: Severely restricted functionality",
            "- ❌ **NONE**: Not available on this platform",
            "",
            "---",
            "",
        ]

        # Generate comparison table for each category
        categories = [
            ("application_control", "Application Control"),
            ("input_automation", "Input Automation"),
            ("speech", "Speech (TTS/STT)"),
            ("biometric", "Biometric Authentication"),
            ("security", "Security Enforcement"),
            ("memory", "Memory & Storage"),
        ]

        for category_key, category_name in categories:
            lines.append(f"## {category_name}")
            lines.append("")

            # Get all capability names in this category
            capability_names = set()
            for platform_caps in self._platforms.values():
                category_caps = getattr(platform_caps, category_key, {})
                capability_names.update(category_caps.keys())

            # Create table header
            lines.append("| Capability | Windows | macOS | Android | iOS |")
            lines.append("|------------|---------|-------|---------|-----|")

            # Create table rows
            for cap_name in sorted(capability_names):
                row = [f"**{cap_name.replace('_', ' ').title()}**"]

                for platform in ["windows", "macos", "android", "ios"]:
                    platform_caps = self._platforms[platform]
                    category_caps = getattr(platform_caps, category_key, {})
                    capability = category_caps.get(cap_name)

                    if capability:
                        if capability.level == CapabilityLevel.FULL:
                            symbol = "✅"
                        elif capability.level == CapabilityLevel.PARTIAL:
                            symbol = "⚠️"
                        elif capability.level == CapabilityLevel.LIMITED:
                            symbol = "🔶"
                        else:
                            symbol = "❌"

                        cell = f"{symbol} {capability.level.value.capitalize()}"
                    else:
                        cell = "❌ None"

                    row.append(cell)

                lines.append("| " + " | ".join(row) + " |")

            lines.append("")

        # Add authority scope comparison
        lines.append("## Authority Scope")
        lines.append("")
        lines.append("| Platform | Authority Scope | Description |")
        lines.append("|----------|-----------------|-------------|")

        for platform in ["windows", "macos", "android", "ios"]:
            platform_caps = self._platforms[platform]
            scope = platform_caps.authority_scope

            if scope == "system-wide":
                desc = "Full system control - can manage all applications and system state"
            else:
                desc = "App-level only - cannot control system or other applications"

            lines.append(f"| **{platform.capitalize()}** | {scope} | {desc} |")

        lines.append("")

        # Add platform limitations section
        lines.append("## Platform Limitations")
        lines.append("")

        for platform in ["windows", "macos", "android", "ios"]:
            platform_caps = self._platforms[platform]
            limitations = platform_caps.get_limitations()

            lines.append(f"### {platform.capitalize()}")
            lines.append("")

            if limitations:
                for limitation in limitations:
                    lines.append(f"- {limitation}")
            else:
                lines.append("- No significant limitations")

            lines.append("")

        return "\n".join(lines)

    def _generate_json_documentation(self) -> dict:
        """Generate JSON format documentation."""
        _result = {}

        for platform_name, platform_caps in self._platforms.items():
            platform_data = {
                "platform": platform_name,
                "authority_scope": platform_caps.authority_scope,
                "capabilities": {},
                "limitations": platform_caps.get_limitations(),
            }

            for category_name, category_caps in platform_caps.get_all_capabilities().items():
                platform_data["capabilities"][category_name] = {}

                for cap_name, capability in category_caps.items():
                    platform_data["capabilities"][category_name][cap_name] = {
                        "level": capability.level.value,
                        "description": capability.description,
                        "restrictions": capability.restrictions,
                        "implementation": capability.implementation,
                    }

            result[platform_name] = platform_data

        return result

    def _generate_html_documentation(self) -> str:
        """Generate HTML format documentation."""
        # Convert markdown to HTML (simplified)
        _markdown_doc = self._generate_markdown_documentation()

        html = """<!DOCTYPE html>
<html>
<head>
    <title>GURU Platform Capability Matrix</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        h1, h2, h3 {{ color: #333; }}
        .full {{ color: green; }}
        .partial {{ color: orange; }}
        .limited {{ color: darkorange; }}
        .none {{ color: red; }}
    </style>
</head>
<body>
    <pre>{markdown_doc}</pre>
</body>
</html>"""

        return html


# Singleton instance for global access
_capability_matrix_instance: Optional[CapabilityMatrix] = None


def get_capability_matrix() -> CapabilityMatrix:
    """
    Get singleton instance of CapabilityMatrix.

    Returns:
        Global CapabilityMatrix instance

    Usage:
        >>> matrix = get_capability_matrix()
        >>> windows_caps = matrix.get_platform_capabilities("windows")
    """
    global _capability_matrix_instance

    if _capability_matrix_instance is None:
        _capability_matrix_instance = CapabilityMatrix()

    return _capability_matrix_instance
