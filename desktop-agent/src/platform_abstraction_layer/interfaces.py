"""
Platform Abstraction Layer (PAL) Interface Definitions.

This module defines the abstract interfaces that all platform backends must implement.
These interfaces form the contract between platform-agnostic core logic and
platform-specific implementations.

CRITICAL RULES:
1. Core logic MUST ONLY interact with these interfaces
2. Core logic MUST NEVER import platform-specific modules
3. All platform backends MUST implement ALL interface methods
4. Security invariants MUST be maintained across all platforms
5. Capability limitations MUST be explicitly declared

Validates: Requirements 33.1, 34.1-34.4, 35.1-35.3, 36.1, 37.1-37.3, 38.1, 40.1
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# ============================================================================
# Exceptions
# ============================================================================


class PlatformNotSupportedError(Exception):
    """Raised when attempting to run on an unsupported platform."""


class PlatformCapabilityError(Exception):
    """Raised when attempting to use an unavailable platform capability."""


# ============================================================================
# Enums
# ============================================================================


class TTSPriority(Enum):
    """Text-to-speech priority levels for queue ordering."""

    CRITICAL = 0  # Security alerts, errors
    HIGH = 1  # Action confirmations, important feedback
    NORMAL = 2  # Standard responses
    LOW = 3  # Background information


class AuthResultStatus(Enum):
    """Biometric authentication result status."""

    SUCCESS = "success"  # Authentication succeeded
    FAILURE = "failure"  # Authentication failed (wrong biometric)
    UNAVAILABLE = "unavailable"  # Biometric hardware not available
    CANCELLED = "cancelled"  # User cancelled authentication
    LOCKED = "locked"  # Too many failures, locked out


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class AppDescriptor:
    """
    Platform-agnostic application descriptor.

    Provides consistent application metadata across all platforms.

    Attributes:
        app_id: Unique identifier (e.g., "notepad", "com.microsoft.word")
        display_name: User-friendly name (e.g., "Notepad", "Microsoft Word")
        executable_path: Platform-specific path to executable
        is_running: Current running status
        platform: Platform identifier (windows, macos, android, ios)
        metadata: Platform-specific additional data
    """

    app_id: str
    display_name: str
    executable_path: str
    is_running: bool
    platform: str
    metadata: Dict[str, Any]


@dataclass
class AutomationTarget:
    """
    Platform-agnostic automation target descriptor.

    Describes a UI element or location for input automation.

    Attributes:
        target_type: Type of target (window, control, coordinate, app)
        identifier: Target identifier (window title, control ID, coordinates)
        platform_data: Platform-specific metadata for targeting
    """

    target_type: str  # "window", "control", "coordinate", "app"
    identifier: str
    platform_data: Dict[str, Any]


@dataclass
class Transcription:
    """
    Platform-agnostic speech transcription result.

    Provides consistent transcription metadata across all platforms.

    Attributes:
        text: Transcribed text
        confidence: Confidence score (0.0 to 1.0)
        language: Detected language code (e.g., "en", "es", "fr")
        timestamp: Transcription timestamp
        audio_duration: Duration of audio in seconds
        metadata: Platform-specific additional data
    """

    text: str
    confidence: float
    language: str
    timestamp: datetime
    audio_duration: float
    metadata: Dict[str, Any]


@dataclass
class AuthResult:
    """
    Platform-agnostic biometric authentication result.

    Provides consistent authentication result across all platforms.

    Attributes:
        status: Authentication status
        message: Human-readable message
        platform: Platform identifier
        timestamp: Authentication timestamp
        factor_used: Biometric factor used (fingerprint, face, iris)
        metadata: Platform-specific additional data
    """

    status: AuthResultStatus
    message: str
    platform: str
    timestamp: datetime
    factor_used: Optional[str] = None
    metadata: Dict[str, Any] = None


# ============================================================================
# Interface 1: Application Controller
# ============================================================================


class ApplicationController(ABC):
    """
    Platform-agnostic application control interface.

    Provides unified interface for launching, closing, and discovering applications
    across Windows, macOS, Android, and iOS.

    Platform Implementations:
        Windows: Win32 CreateProcess, Shell, UIAutomation
        macOS: LaunchServices, Apple Events, NSWorkspace
        Android: Intent system (startActivity)
        iOS: Deep links only (openURL) - LIMITED

    Validates: Requirements 34.1-34.4, 34.9
    """

    @abstractmethod
    def open_app(self, app_id: str) -> bool:
        """
        Open application by ID.

        Args:
            app_id: Unique application identifier

        Returns:
            True if application launched successfully, False otherwise

        Raises:
            PlatformCapabilityError: If platform doesn't support app launching

        Platform Behavior:
            Windows: Full support via CreateProcess/ShellExecute
            macOS: Full support via LaunchServices
            Android: Full support via Intent system
            iOS: Limited to deep links only
        """

    @abstractmethod
    def close_app(self, app_id: str) -> bool:
        """
        Close application by ID.

        Args:
            app_id: Unique application identifier

        Returns:
            True if application closed successfully, False otherwise

        Raises:
            PlatformCapabilityError: If platform doesn't support app closing

        Platform Behavior:
            Windows: Full support via TerminateProcess
            macOS: Full support via Apple Events
            Android: Full support via ActivityManager
            iOS: NOT ALLOWED (platform restriction)
        """

    @abstractmethod
    def is_running(self, app_id: str) -> bool:
        """
        Check if application is currently running.

        Args:
            app_id: Unique application identifier

        Returns:
            True if application is running, False otherwise

        Platform Behavior:
            Windows: Full support via process enumeration
            macOS: Full support via NSWorkspace
            Android: Full support via ActivityManager
            iOS: Limited support (only for registered apps)
        """

    @abstractmethod
    def discover_apps(self) -> List[AppDescriptor]:
        """
        Discover installed applications.

        Returns:
            List of application descriptors for all discovered apps

        Platform Behavior:
            Windows: Full discovery via registry and common paths
            macOS: Full discovery via LaunchServices
            Android: Full discovery via PackageManager
            iOS: Limited discovery (only registered apps)
        """

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform-specific capabilities.

        Returns:
            Dictionary of capability flags:
                - can_open_apps: Can launch applications
                - can_close_apps: Can terminate applications
                - can_discover_apps: Can enumerate installed apps
                - has_full_control: Has complete application control

        Platform Capabilities:
            Windows: All True
            macOS: All True
            Android: All True
            iOS: can_close_apps=False, can_discover_apps=Limited
        """


# ============================================================================
# Interface 2: Input Automation
# ============================================================================


class InputAutomation(ABC):
    """
    Platform-agnostic input automation interface.

    Provides unified interface for keyboard/mouse automation across platforms.

    Platform Implementations:
        Windows: Full (keyboard + mouse via Win32 SendInput)
        macOS: Full (with Accessibility permission via CGEvent)
        Android: Partial (Accessibility Service - requires user grant)
        iOS: SEVERELY RESTRICTED (no system automation)

    Validates: Requirements 35.1-35.3, 35.8
    """

    @abstractmethod
    def type_text(self, text: str, target: Optional[AutomationTarget] = None) -> bool:
        """
        Type text into focused window or specific target.

        Args:
            text: Text to type
            target: Optional specific target (window, control)

        Returns:
            True if text typed successfully, False otherwise

        Raises:
            PlatformCapabilityError: If platform doesn't support text automation

        Platform Behavior:
            Windows: Full support via SendInput
            macOS: Full support via CGEvent (requires Accessibility)
            Android: Partial support via Accessibility Service
            iOS: SEVERELY RESTRICTED (no system automation)
        """

    @abstractmethod
    def click(self, target: AutomationTarget) -> bool:
        """
        Click on UI element.

        Args:
            target: Target to click (control, coordinate)

        Returns:
            True if click successful, False otherwise

        Raises:
            PlatformCapabilityError: If platform doesn't support clicking

        Platform Behavior:
            Windows: Full support via SendInput
            macOS: Full support via CGEvent (requires Accessibility)
            Android: Partial support via Accessibility Service
            iOS: NOT ALLOWED (platform restriction)
        """

    @abstractmethod
    def focus_app(self, app_id: str) -> bool:
        """
        Bring application to foreground.

        Args:
            app_id: Application identifier

        Returns:
            True if app focused successfully, False otherwise

        Platform Behavior:
            Windows: Full support via SetForegroundWindow
            macOS: Full support via NSWorkspace
            Android: Full support via Intent flags
            iOS: Limited support (only for registered apps)
        """

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform-specific automation capabilities.

        Returns:
            Dictionary of capability flags:
                - can_type_text: Can type text
                - can_click: Can click UI elements
                - can_focus_apps: Can bring apps to foreground
                - has_full_automation: Has complete automation control
                - requires_permission: Requires special permission

        Platform Capabilities:
            Windows: All True, requires_permission=False
            macOS: All True, requires_permission=True (Accessibility)
            Android: Partial, requires_permission=True (Accessibility Service)
            iOS: All False (severely restricted)
        """


# ============================================================================
# Interface 3: Speech Output
# ============================================================================


class SpeechOutput(ABC):
    """
    Platform-agnostic text-to-speech interface.

    Provides unified interface for speech synthesis across platforms.
    Maintains Human Co-Worker Speech Contract across all platforms.

    Platform Implementations:
        Windows: Windows SAPI (win32com.client.Dispatch("SAPI.SpVoice"))
        macOS: NSSpeechSynthesizer
        Android: Android TTS (android.speech.tts.TextToSpeech)
        iOS: AVSpeechSynthesizer

    Validates: Requirements 36.1, 36.2, 36.7
    """

    @abstractmethod
    def speak(self, text: str, priority: TTSPriority = TTSPriority.NORMAL, interrupt: bool = False) -> None:
        """
        Queue text for speech synthesis.

        Args:
            text: Text to speak
            priority: Priority level for queue ordering
            interrupt: If True, interrupt current speech

        Platform Behavior:
            All platforms: Priority queue with consistent ordering
            Windows: SAPI with volume bypass
            macOS: NSSpeechSynthesizer
            Android: Android TTS
            iOS: AVSpeechSynthesizer
        """

    @abstractmethod
    def stop(self) -> None:
        """
        Stop current speech and clear queue.

        Platform Behavior:
            All platforms: Immediate stop and queue clear
        """

    @abstractmethod
    def is_speaking(self) -> bool:
        """
        Check if currently speaking.

        Returns:
            True if speech is active, False otherwise
        """

    @abstractmethod
    def set_volume(self, volume: int) -> None:
        """
        Set volume (0-100).

        Args:
            volume: Volume level (0=silent, 100=maximum)

        Platform Behavior:
            Windows: Bypasses Volume Mixer to avoid 1% lock
            macOS: System volume control
            Android: Media volume control
            iOS: System volume control
        """

    @abstractmethod
    def set_rate(self, rate: int) -> None:
        """
        Set speech rate (-10 to 10).

        Args:
            rate: Speech rate (-10=slowest, 0=normal, 10=fastest)
        """

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform-specific speech capabilities.

        Returns:
            Dictionary of capability flags:
                - has_priority_queue: Supports priority-based queuing
                - can_interrupt: Can interrupt current speech
                - can_control_volume: Can control volume independently
                - can_control_rate: Can control speech rate

        Platform Capabilities:
            All platforms: All True
        """


# ============================================================================
# Interface 4: Speech Input
# ============================================================================


class SpeechInput(ABC):
    """
    Platform-agnostic speech recognition interface.

    Provides unified interface for voice recognition and wake word detection.
    Maintains identical state machine behavior across all platforms.

    Platform Implementations:
        Windows: Whisper.cpp (local)
        macOS: Whisper.cpp (local)
        Android: Whisper.cpp or system STT (user choice)
        iOS: System STT (mandatory - no local models allowed)

    Validates: Requirements 37.1-37.3, 37.7
    """

    @abstractmethod
    def start_listening(self) -> None:
        """
        Start background listening thread.

        Platform Behavior:
            Windows/macOS: Whisper.cpp in background thread
            Android: Whisper.cpp or system STT
            iOS: System STT (mandatory)
        """

    @abstractmethod
    def stop_listening(self) -> None:
        """
        Stop listening and cleanup resources.

        Platform Behavior:
            All platforms: Clean shutdown of listening thread
        """

    @abstractmethod
    def transcribe(self, audio_data: bytes) -> Transcription:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes (PCM format)

        Returns:
            Transcription result with text and metadata

        Platform Behavior:
            Windows/macOS: Whisper.cpp local processing
            Android: Whisper.cpp or system STT
            iOS: System STT (mandatory)
        """

    @abstractmethod
    def calibrate_microphone(self) -> float:
        """
        Calibrate for ambient noise.

        Returns:
            Energy threshold for voice detection

        Platform Behavior:
            All platforms: Measure ambient noise for 1 second
        """

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform-specific speech input capabilities.

        Returns:
            Dictionary of capability flags:
                - has_local_processing: Can process locally (Whisper.cpp)
                - requires_cloud: Requires cloud processing
                - supports_wake_word: Supports local wake word detection
                - supports_continuous: Supports continuous listening

        Platform Capabilities:
            Windows/macOS: All True, requires_cloud=False
            Android: Depends on user choice
            iOS: has_local_processing=False, requires_cloud=True
        """


# ============================================================================
# Interface 5: Biometric Authenticator
# ============================================================================


class BiometricAuthenticator(ABC):
    """
    Platform-agnostic biometric authentication interface.

    Provides unified interface for biometric authentication across platforms.
    Maintains identical failure lockout behavior across all platforms.

    Platform Implementations:
        Windows: Windows Hello (fingerprint, face, iris)
        macOS: Touch ID, Face ID (via LocalAuthentication framework)
        Android: BiometricPrompt (fingerprint, face, iris)
        iOS: Face ID, Touch ID (via LocalAuthentication framework)

    Validates: Requirements 38.1, 38.6, 38.7
    """

    @abstractmethod
    def authenticate(self, reason: str) -> AuthResult:
        """
        Perform biometric authentication.

        Args:
            reason: Human-readable reason for authentication request

        Returns:
            Authentication result with status and metadata

        Platform Behavior:
            Windows: Windows Hello prompt
            macOS: Touch ID/Face ID prompt
            Android: BiometricPrompt dialog
            iOS: Face ID/Touch ID prompt

        Security:
            All platforms: 3 failures → lockout
            All platforms: Cryptographic audit logging
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if biometric authentication is available.

        Returns:
            True if biometric hardware is available and configured

        Platform Behavior:
            Windows: Check Windows Hello configuration
            macOS: Check Touch ID/Face ID availability
            Android: Check BiometricManager
            iOS: Check LocalAuthentication availability
        """

    @abstractmethod
    def get_available_factors(self) -> List[str]:
        """
        Get available biometric factors.

        Returns:
            List of factor names (e.g., ["fingerprint", "face"])

        Platform Behavior:
            Windows: Query Windows Hello factors
            macOS: Query available biometric types
            Android: Query BiometricManager capabilities
            iOS: Query LocalAuthentication biometry type
        """

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform-specific biometric capabilities.

        Returns:
            Dictionary of capability flags:
                - has_fingerprint: Supports fingerprint
                - has_face: Supports face recognition
                - has_iris: Supports iris scanning
                - is_configured: Biometrics are configured

        Platform Capabilities:
            Windows: Depends on hardware
            macOS: Depends on hardware
            Android: Depends on hardware
            iOS: Depends on hardware
        """


# ============================================================================
# Interface 6: Security Enforcer
# ============================================================================


class SecurityEnforcer(ABC):
    """
    Platform-agnostic security enforcement interface.

    Provides unified interface for security lockdown across platforms.
    Maintains identical security violation detection across all platforms.

    Platform Implementations:
        Windows: Lock workstation (LockWorkStation API)
        macOS: Lock screen (CGSession API)
        Android: Lock app + screen if allowed (DevicePolicyManager)
        iOS: Lock app only (no system lock capability)

    Validates: Requirements 40.1, 40.6
    """

    @abstractmethod
    def lock_session(self, reason: str) -> bool:
        """
        Lock user session.

        Args:
            reason: Reason for lock (for audit logging)

        Returns:
            True if lock successful, False otherwise

        Platform Behavior:
            Windows: Lock workstation (system-wide)
            macOS: Lock screen (system-wide)
            Android: Lock app + screen if allowed (app-level)
            iOS: Lock app only (app-level)

        Security:
            All platforms: Cryptographic audit logging
            All platforms: Immediate effect (no delay)
        """

    @abstractmethod
    def get_lock_scope(self) -> str:
        """
        Get scope of lock operation.

        Returns:
            Lock scope: "system", "screen", or "app"

        Platform Behavior:
            Windows: "system" (workstation lock)
            macOS: "screen" (screen lock)
            Android: "app" (app lock, screen if allowed)
            iOS: "app" (app lock only)
        """

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform-specific security capabilities.

        Returns:
            Dictionary of capability flags:
                - can_lock_system: Can lock entire system
                - can_lock_screen: Can lock screen
                - can_lock_app: Can lock application
                - has_system_authority: Has system-wide authority

        Platform Capabilities:
            Windows: can_lock_system=True, has_system_authority=True
            macOS: can_lock_screen=True, has_system_authority=True
            Android: can_lock_app=True, has_system_authority=False
            iOS: can_lock_app=True, has_system_authority=False
        """
