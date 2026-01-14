# Design Document: GURU Complete Desktop AI Assistant System

## Overview

GURU is a production-grade, security-first desktop AI assistant that operates as a local authority-gated co-worker. The system provides voice-activated automation, universal application control, biometric authentication, and intelligent conversation capabilities while maintaining military-grade security through cryptographic audit logging and capability-based access control.

### Design Philosophy

1. **Security First**: All operations are authority-gated with cryptographic audit trails
2. **Action Over Conversation**: Commands execute deterministically; LLMs are used only when necessary
3. **Local First**: All processing occurs locally; cloud services are opt-in only
4. **Thread Safety**: Strict separation between background threads and Qt main thread
5. **Graceful Degradation**: Component failures never crash the entire system
6. **Zero Trust**: Every operation is logged, verified, and can be audited

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GURU System                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Voice      │      │   Thread     │      │     GUI      │  │
│  │  Interface   │─────▶│    Safe      │─────▶│   (Qt)       │  │
│  │  (Background)│      │   Bridge     │      │  (Main)      │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         │                                            │           │
│         │                                            │           │
│         ▼                                            ▼           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Intent Pre-Filter Layer                      │  │
│  │  (Regex/Keyword matching - bypasses LLM for actions)     │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                            │           │
│         ├─────────────┬──────────────────────────────┤           │
│         │             │                              │           │
│         ▼             ▼                              ▼           │
│  ┌──────────┐  ┌──────────┐                  ┌──────────┐      │
│  │ Command  │  │   LLM    │                  │   TTS    │      │
│  │ Executor │  │ Adapter  │                  │ Service  │      │
│  └──────────┘  └──────────┘                  └──────────┘      │
│         │             │                              │           │
│         │             │                              │           │
│         ▼             ▼                              ▼           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Authority State Machine                         │  │
│  │  (Capability-based security with biometric auth)          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Audit Logger                                 │  │
│  │  (Cryptographic chain with HMAC-SHA256)                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Intrusion   │  │   Failure    │  │   Memory     │          │
│  │  Detector    │  │ Orchestrator │  │   System     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Cross-Platform Architecture with PAL

```
┌─────────────────────────────────────────────────────────────────┐
│                    GURU Core Logic (Platform-Agnostic)           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Voice Interface │ Intent Pre-Filter │ Authority State Machine   │
│  LLM Adapter     │ Conversation Mgr  │ Audit Logger             │
│  Memory System   │ Failure Orchestrator │ Intrusion Detector    │
│                                                                   │
│  ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲  │
│  │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │  │
└──┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼──┘
   │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │
┌──┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴──┐
│         Platform Abstraction Layer (PAL Interfaces)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Application_Controller │ Input_Automation │ Speech_Output       │
│  Speech_Input │ Biometric_Authenticator │ Security_Enforcer     │
│                                                                   │
│  ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼  │
└──┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬──┘
   │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │
┌──┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴──┐
│                    Platform Backends                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Windows  │  │  macOS   │  │ Android  │  │   iOS    │        │
│  │ Backend  │  │ Backend  │  │ Backend  │  │ Backend  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                   │
│  Win32/SAPI   LaunchSvc    Intent Sys    Deep Links             │
│  UIAutomation NSSpeech     BiometricPr   Face ID                │
│  Win Hello    Touch ID     Accessibility AVSpeech               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**CRITICAL RULE**: Core logic is 100% platform-agnostic. All OS-specific behavior is isolated in platform backends.

## Architecture

### Component Hierarchy

```
GURU System
├── Core Security Layer
│   ├── Authority State Machine
│   ├── Audit Logger
│   ├── Intrusion Detector
│   └── Biometric Provider
├── Input Processing Layer
│   ├── Voice Interface
│   ├── Intent Pre-Filter
│   └── Thread Safe Bridge
├── Intelligence Layer
│   ├── LLM Adapter (Ollama/OpenAI/Gemini)
│   ├── Conversation Manager
│   └── Memory System
├── Execution Layer
│   ├── Command Executor
│   ├── Application Launcher
│   ├── Windows Automation
│   └── Skills Registry
├── Output Layer
│   ├── TTS Service
│   └── GUI (Qt Avatar Window)
└── System Management Layer
    ├── Failure Orchestrator
    ├── Configuration Manager
    └── Diagnostic Tools
```

### Platform Abstraction Layer (PAL)

The PAL is a **mandatory architectural layer** that isolates all OS-specific behavior behind strict contracts. This ensures:

1. **Core logic is 100% platform-agnostic** - no platform-specific imports or API calls
2. **Security invariants hold across all platforms** - same authority model, audit logging, intrusion detection
3. **Predictable behavior** - identical state machines and logic flow on all platforms
4. **Maintainability** - platform-specific code is isolated and testable independently
5. **Honest capability declaration** - explicit documentation of platform limitations

#### PAL Architecture Principles

**Separation Rule**:
```
Core Logic ≠ Platform Backend

Core Logic:
- Voice Interface state machine
- Intent Pre-Filter pattern matching
- Authority State Machine
- Audit Logger cryptographic chain
- LLM Adapter
- Memory System
- Failure Orchestrator
- Intrusion Detector

Platform Backend:
- Application launching
- Input automation (keyboard/mouse)
- Text-to-speech synthesis
- Speech recognition
- Biometric authentication
- Screen/workstation locking
```

**Communication Rule**:
```
Core Logic → PAL Interface → Platform Backend

NEVER:
Core Logic → Platform API directly

ALWAYS:
Core Logic → Abstract Interface → Concrete Platform Implementation
```

#### PAL Interfaces

**1. Application_Controller Interface**:
```python
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class AppDescriptor:
    """Platform-agnostic application descriptor."""
    app_id: str              # Unique identifier
    display_name: str        # User-friendly name
    executable_path: str     # Platform-specific path
    is_running: bool         # Current running status
    platform: str            # windows, macos, android, ios

class ApplicationController(ABC):
    """Platform-agnostic application control interface."""
    
    @abstractmethod
    def open_app(self, app_id: str) -> bool:
        """
        Open application by ID.
        Returns True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def close_app(self, app_id: str) -> bool:
        """
        Close application by ID.
        Returns True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def is_running(self, app_id: str) -> bool:
        """
        Check if application is currently running.
        Returns True if running, False otherwise.
        """
        pass
    
    @abstractmethod
    def discover_apps(self) -> List[AppDescriptor]:
        """
        Discover installed applications.
        Returns list of application descriptors.
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform-specific capabilities.
        Returns dict of capability flags.
        """
        pass
```

**Platform Implementations**:
```
Windows: Win32 CreateProcess, Shell, UIAutomation
macOS: LaunchServices, Apple Events, NSWorkspace
Android: Intent system (startActivity)
iOS: Deep links only (openURL) - LIMITED
```

**2. Input_Automation Interface**:
```python
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

@dataclass
class AutomationTarget:
    """Platform-agnostic automation target."""
    target_type: str         # window, control, coordinate
    identifier: str          # window title, control ID, etc.
    platform_data: dict      # Platform-specific metadata

class InputAutomation(ABC):
    """Platform-agnostic input automation interface."""
    
    @abstractmethod
    def type_text(self, text: str, target: Optional[AutomationTarget] = None) -> bool:
        """
        Type text into focused window or specific target.
        Returns True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def click(self, target: AutomationTarget) -> bool:
        """
        Click on UI element.
        Returns True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def focus_app(self, app_id: str) -> bool:
        """
        Bring application to foreground.
        Returns True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get platform-specific automation capabilities.
        Returns dict of capability flags.
        """
        pass
```

**Platform Implementations**:
```
Windows: Full (keyboard + mouse via Win32 SendInput)
macOS: Full (with Accessibility permission via CGEvent)
Android: Partial (Accessibility Service - requires user grant)
iOS: SEVERELY RESTRICTED (no system automation)
```

**3. Speech_Output Interface**:
```python
from abc import ABC, abstractmethod
from enum import Enum

class TTSPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

class SpeechOutput(ABC):
    """Platform-agnostic text-to-speech interface."""
    
    @abstractmethod
    def speak(self, text: str, priority: TTSPriority = TTSPriority.NORMAL,
             interrupt: bool = False) -> None:
        """
        Queue text for speech synthesis.
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """
        Stop current speech and clear queue.
        """
        pass
    
    @abstractmethod
    def is_speaking(self) -> bool:
        """
        Check if currently speaking.
        """
        pass
    
    @abstractmethod
    def set_volume(self, volume: int) -> None:
        """
        Set volume (0-100).
        """
        pass
    
    @abstractmethod
    def set_rate(self, rate: int) -> None:
        """
        Set speech rate (-10 to 10).
        """
        pass
```

**Platform Implementations**:
```
Windows: Windows SAPI (win32com.client.Dispatch("SAPI.SpVoice"))
macOS: NSSpeechSynthesizer
Android: Android TTS (android.speech.tts.TextToSpeech)
iOS: AVSpeechSynthesizer
```

**4. Speech_Input Interface**:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Transcription:
    """Platform-agnostic transcription result."""
    text: str
    confidence: float
    language: str
    timestamp: datetime
    audio_duration: float

class SpeechInput(ABC):
    """Platform-agnostic speech recognition interface."""
    
    @abstractmethod
    def start_listening(self) -> None:
        """
        Start background listening thread.
        """
        pass
    
    @abstractmethod
    def stop_listening(self) -> None:
        """
        Stop listening and cleanup resources.
        """
        pass
    
    @abstractmethod
    def transcribe(self, audio_data: bytes) -> Transcription:
        """
        Transcribe audio data to text.
        """
        pass
    
    @abstractmethod
    def calibrate_microphone(self) -> float:
        """
        Calibrate for ambient noise.
        Returns energy threshold.
        """
        pass
```

**Platform Implementations**:
```
Windows: Whisper.cpp (local)
macOS: Whisper.cpp (local)
Android: Whisper.cpp or system STT (user choice)
iOS: System STT (mandatory - no local models allowed)
```

**5. Biometric_Authenticator Interface**:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class AuthResultStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"

@dataclass
class AuthResult:
    """Platform-agnostic authentication result."""
    status: AuthResultStatus
    message: str
    platform: str
    timestamp: datetime

class BiometricAuthenticator(ABC):
    """Platform-agnostic biometric authentication interface."""
    
    @abstractmethod
    def authenticate(self, reason: str) -> AuthResult:
        """
        Perform biometric authentication.
        Returns authentication result.
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if biometric authentication is available.
        """
        pass
    
    @abstractmethod
    def get_available_factors(self) -> List[str]:
        """
        Get available biometric factors.
        Returns list of factor names (e.g., ["fingerprint", "face"]).
        """
        pass
```

**Platform Implementations**:
```
Windows: Windows Hello (fingerprint, face, iris)
macOS: Touch ID, Face ID (via LocalAuthentication framework)
Android: BiometricPrompt (fingerprint, face, iris)
iOS: Face ID, Touch ID (via LocalAuthentication framework)
```

**6. Security_Enforcer Interface**:
```python
from abc import ABC, abstractmethod

class SecurityEnforcer(ABC):
    """Platform-agnostic security enforcement interface."""
    
    @abstractmethod
    def lock_session(self, reason: str) -> bool:
        """
        Lock user session.
        Returns True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_lock_scope(self) -> str:
        """
        Get scope of lock operation.
        Returns "system", "screen", or "app".
        """
        pass
```

**Platform Implementations**:
```
Windows: Lock workstation (LockWorkStation API)
macOS: Lock screen (CGSession API)
Android: Lock app + screen if allowed (DevicePolicyManager)
iOS: Lock app only (no system lock capability)
```

#### Platform Capability Matrix

**CRITICAL**: This matrix documents **honest capabilities** per platform. No security illusions.

| Feature | Windows | macOS | Android | iOS |
|---------|---------|-------|---------|-----|
| **Application Control** |
| Open apps | ✅ Full | ✅ Full | ✅ Full | ⚠️ Deep links only |
| Close apps | ✅ Full | ✅ Full | ✅ Full | ❌ Not allowed |
| Discover apps | ✅ Full | ✅ Full | ✅ Full | ⚠️ Limited |
| **Input Automation** |
| Type text | ✅ Full | ✅ Full (with perm) | ⚠️ Partial (Accessibility) | ❌ Severely restricted |
| Click UI | ✅ Full | ✅ Full (with perm) | ⚠️ Partial (Accessibility) | ❌ Not allowed |
| Focus apps | ✅ Full | ✅ Full | ✅ Full | ⚠️ Limited |
| **Speech** |
| TTS | ✅ SAPI | ✅ NSSpeech | ✅ Android TTS | ✅ AVSpeech |
| STT | ✅ Whisper.cpp | ✅ Whisper.cpp | ⚠️ Whisper or system | ⚠️ System only |
| Wake word | ✅ Local | ✅ Local | ⚠️ Local or system | ⚠️ System only |
| **Biometrics** |
| Fingerprint | ✅ Windows Hello | ✅ Touch ID | ✅ BiometricPrompt | ✅ Touch ID |
| Face | ✅ Windows Hello | ✅ Face ID | ✅ BiometricPrompt | ✅ Face ID |
| **Security** |
| Lock scope | ✅ Workstation | ✅ Screen | ⚠️ App + screen | ⚠️ App only |
| Authority scope | ✅ System-wide | ✅ System-wide | ⚠️ App-level | ⚠️ App-level |
| **Memory** |
| Encrypted storage | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Vector search | ✅ Full | ✅ Full | ✅ Full | ✅ Full |

**Legend**:
- ✅ Full: Complete functionality
- ⚠️ Partial/Limited: Reduced functionality or requires special permissions
- ❌ Not allowed: Platform restriction

#### Platform Detection and Backend Selection

**CRITICAL**: The system must automatically detect the platform and load the correct backend at runtime.

**Platform Detection**:
```python
import platform
import sys

class PlatformDetector:
    """Detect current platform and return platform identifier."""
    
    @staticmethod
    def detect() -> str:
        """
        Detect platform.
        Returns: "windows", "macos", "android", "ios"
        """
        system = platform.system().lower()
        
        if system == "windows":
            return "windows"
        elif system == "darwin":
            return "macos"
        elif system == "linux":
            # Check if running on Android
            if hasattr(sys, 'getandroidapilevel'):
                return "android"
            else:
                raise PlatformNotSupportedError("Linux desktop not supported")
        elif system == "ios":
            return "ios"
        else:
            raise PlatformNotSupportedError(f"Platform {system} not supported")
```

**Backend Factory**:
```python
class PlatformBackendFactory:
    """Factory for creating platform-specific backends."""
    
    def __init__(self, platform: str):
        """Initialize factory with detected platform."""
        self.platform = platform
    
    def create_application_controller(self) -> ApplicationController:
        """Create platform-specific application controller."""
        if self.platform == "windows":
            from .backends.windows import WindowsApplicationController
            return WindowsApplicationController()
        elif self.platform == "macos":
            from .backends.macos import macOSApplicationController
            return macOSApplicationController()
        elif self.platform == "android":
            from .backends.android import AndroidApplicationController
            return AndroidApplicationController()
        elif self.platform == "ios":
            from .backends.ios import iOSApplicationController
            return iOSApplicationController()
        else:
            raise PlatformNotSupportedError(f"Platform {self.platform} not supported")
    
    def create_input_automation(self) -> InputAutomation:
        """Create platform-specific input automation."""
        if self.platform == "windows":
            from .backends.windows import WindowsInputAutomation
            return WindowsInputAutomation()
        elif self.platform == "macos":
            from .backends.macos import macOSInputAutomation
            return macOSInputAutomation()
        elif self.platform == "android":
            from .backends.android import AndroidInputAutomation
            return AndroidInputAutomation()
        elif self.platform == "ios":
            from .backends.ios import iOSInputAutomation
            return iOSInputAutomation()
        else:
            raise PlatformNotSupportedError(f"Platform {self.platform} not supported")
    
    def create_speech_output(self) -> SpeechOutput:
        """Create platform-specific speech output."""
        if self.platform == "windows":
            from .backends.windows import WindowsSpeechOutput
            return WindowsSpeechOutput()
        elif self.platform == "macos":
            from .backends.macos import macOSSpeechOutput
            return macOSSpeechOutput()
        elif self.platform == "android":
            from .backends.android import AndroidSpeechOutput
            return AndroidSpeechOutput()
        elif self.platform == "ios":
            from .backends.ios import iOSSpeechOutput
            return iOSSpeechOutput()
        else:
            raise PlatformNotSupportedError(f"Platform {self.platform} not supported")
    
    def create_speech_input(self) -> SpeechInput:
        """Create platform-specific speech input."""
        if self.platform == "windows":
            from .backends.windows import WindowsSpeechInput
            return WindowsSpeechInput()
        elif self.platform == "macos":
            from .backends.macos import macOSSpeechInput
            return macOSSpeechInput()
        elif self.platform == "android":
            from .backends.android import AndroidSpeechInput
            return AndroidSpeechInput()
        elif self.platform == "ios":
            from .backends.ios import iOSSpeechInput
            return iOSSpeechInput()
        else:
            raise PlatformNotSupportedError(f"Platform {self.platform} not supported")
    
    def create_biometric_authenticator(self) -> BiometricAuthenticator:
        """Create platform-specific biometric authenticator."""
        if self.platform == "windows":
            from .backends.windows import WindowsBiometricAuthenticator
            return WindowsBiometricAuthenticator()
        elif self.platform == "macos":
            from .backends.macos import macOSBiometricAuthenticator
            return macOSBiometricAuthenticator()
        elif self.platform == "android":
            from .backends.android import AndroidBiometricAuthenticator
            return AndroidBiometricAuthenticator()
        elif self.platform == "ios":
            from .backends.ios import iOSBiometricAuthenticator
            return iOSBiometricAuthenticator()
        else:
            raise PlatformNotSupportedError(f"Platform {self.platform} not supported")
    
    def create_security_enforcer(self) -> SecurityEnforcer:
        """Create platform-specific security enforcer."""
        if self.platform == "windows":
            from .backends.windows import WindowsSecurityEnforcer
            return WindowsSecurityEnforcer()
        elif self.platform == "macos":
            from .backends.macos import macOSSecurityEnforcer
            return macOSSecurityEnforcer()
        elif self.platform == "android":
            from .backends.android import AndroidSecurityEnforcer
            return AndroidSecurityEnforcer()
        elif self.platform == "ios":
            from .backends.ios import iOSSecurityEnforcer
            return iOSSecurityEnforcer()
        else:
            raise PlatformNotSupportedError(f"Platform {self.platform} not supported")
```

**System Initialization**:
```python
class GURUSystem:
    """Main GURU system with platform-agnostic core logic."""
    
    def __init__(self):
        """Initialize GURU system with platform detection."""
        # Detect platform
        self.platform = PlatformDetector.detect()
        
        # Create backend factory
        self.backend_factory = PlatformBackendFactory(self.platform)
        
        # Create platform backends
        self.app_controller = self.backend_factory.create_application_controller()
        self.input_automation = self.backend_factory.create_input_automation()
        self.speech_output = self.backend_factory.create_speech_output()
        self.speech_input = self.backend_factory.create_speech_input()
        self.biometric_auth = self.backend_factory.create_biometric_authenticator()
        self.security_enforcer = self.backend_factory.create_security_enforcer()
        
        # Initialize core logic with platform backends
        self.voice_interface = VoiceInterface(self.speech_input)
        self.tts_service = TTSService(self.speech_output)
        self.command_executor = CommandExecutor(self.app_controller, self.input_automation)
        self.authority_machine = AuthorityStateMachine(self.biometric_auth, self.security_enforcer)
        self.intrusion_detector = IntrusionDetector(self.security_enforcer)
        
        # Log platform and capabilities
        self.audit_logger.log_system_event(
            "system_initialization",
            {
                "platform": self.platform,
                "capabilities": self.app_controller.get_capabilities()
            },
            AuditSeverity.INFO
        )
```

**CRITICAL RULE**: Core logic components receive PAL interfaces via dependency injection. They NEVER import platform-specific modules directly.

#### Authority Scope Separation

**CRITICAL SECURITY RULE**: GURU authority ≠ OS login authority

**Desktop (Windows/macOS)**:
```
GURU Authority = System-wide control
- Can launch any application
- Can automate any window
- Can lock workstation/screen
- Biometric auth unlocks GURU authority
- GURU authority is separate from OS login
```

**Mobile (Android/iOS)**:
```
GURU Authority = App-level only
- Can launch apps via intents/deep links
- CANNOT automate system UI (iOS)
- CANNOT lock device (iOS)
- CAN lock app only
- Biometric auth unlocks GURU authority within app
- NO SYSTEM-WIDE CONTROL
```

**Audit Logging**:
```
All authority grants MUST log:
- Platform: windows, macos, android, ios
- Authority scope: system-wide, app-level
- Capabilities granted: [list]
- Limitations: [list]
```

This prevents **security illusion** on mobile platforms.

### Thread Architecture

```
Main Thread (Qt Event Loop)
├── GUI rendering
├── Avatar animations
└── Signal/slot processing

Background Thread (Voice Interface)
├── Wake word detection
├── Speech recognition
├── Command callbacks
└── Signal emission to main thread

TTS Thread (Dedicated)
├── Priority queue processing
├── SAPI speech synthesis
└── Audio output

LLM Thread Pool (Dynamic)
├── Ollama requests
├── OpenAI API calls
└── Timeout handling

Monitoring Thread (Periodic)
├── Component health checks
├── Failure detection
└── Recovery orchestration
```

## Components and Interfaces

### 1. Voice Interface

**Purpose**: Capture voice input, detect wake word, transcribe speech, manage conversation state.

**State Machine**:
```
States:
- INACTIVE: Not listening (wake word required)
- ACTIVE: Listening and processing commands (COMMAND_MODE)
- IDLE: Listening but no recent speech (5s timeout)
- SUSPENDED: Temporarily paused (e.g., during TTS)
- DICTATION_MODE: Typing exact text without interpretation

Sub-modes within ACTIVE:
- COMMAND_MODE: Normal command processing
- DICTATION_MODE: Exact text typing

Transitions:
INACTIVE --[wake_word_detected]--> ACTIVE (COMMAND_MODE)
ACTIVE --[5s_silence]--> IDLE
IDLE --[speech_detected]--> ACTIVE (COMMAND_MODE)
ACTIVE --[stop/sleep/exit]--> INACTIVE
IDLE --[stop/sleep/exit]--> INACTIVE
ACTIVE --[wake_word_detected]--> ACTIVE (ignored)
IDLE --[wake_word_detected]--> IDLE (ignored)
COMMAND_MODE --[write/type/dictate detected]--> DICTATION_MODE
DICTATION_MODE --[2s_silence OR done/stop_writing]--> COMMAND_MODE
```

**Interface**:
```python
class VoiceInterface:
    def __init__(self, wake_word: str, language: str = "en"):
        """Initialize voice interface with wake word and language."""
        
    def start_listening(self) -> None:
        """Start background listening thread."""
        
    def stop_listening(self) -> None:
        """Stop listening and cleanup resources."""
        
    def set_command_callback(self, callback: Callable[[VoiceCommand], None]) -> None:
        """Set callback for voice commands."""
        
    def get_state(self) -> VoiceState:
        """Get current state machine state."""
        
    def calibrate_microphone(self) -> float:
        """Calibrate for ambient noise, return energy threshold."""

class VoiceCommand:
    text: str              # Transcribed text
    confidence: float      # Recognition confidence (0.0-1.0)
    language: str          # Detected language code
    timestamp: datetime    # When command was received
    audio_duration: float  # Duration of audio in seconds
```

**Algorithm: Wake Word Detection**:
```
1. Continuously capture audio in 1-second chunks
2. For each chunk:
   a. Compute energy level
   b. If energy > threshold:
      - Transcribe audio
      - Check if transcription contains wake word
      - If match and state == INACTIVE:
         * Transition to ACTIVE (COMMAND_MODE)
         * Emit wake_detected signal
      - If match and state in [ACTIVE, IDLE]:
         * Ignore (already active)
      - Strip wake word from transcription:
         * Remove "hey guru", "hello guru", "hi guru" (case-insensitive)
         * Pass cleaned text to downstream systems
   c. If energy < threshold:
      - Increment silence counter
      - If silence > 5s and state == ACTIVE:
         * Transition to IDLE
      - If silence > 2s and state == DICTATION_MODE:
         * Transition to COMMAND_MODE
3. If user says stop/sleep/exit:
   - Transition to INACTIVE
4. If user says done/stop writing in DICTATION_MODE:
   - Transition to COMMAND_MODE
```

**Algorithm: Dictation Mode**:
```
1. When command contains "write", "type", or "dictate":
   - Transition to DICTATION_MODE
   - Extract text to be typed
   - Mute TTS_Service
2. While in DICTATION_MODE:
   - Bypass Intent_Pre_Filter
   - Bypass LLM_Adapter
   - Send text directly to Command_Executor
   - Type exact text character-by-character
3. Exit DICTATION_MODE when:
   - 2 seconds of silence detected
   - User says "done" or "stop writing"
4. On exit:
   - Transition to COMMAND_MODE
   - Unmute TTS_Service
   - Speak brief confirmation: "Done"
```

### 2. Intent Pre-Filter Layer

**Purpose**: Fast pattern matching to bypass LLM for deterministic commands.

**Interface**:
```python
class IntentPreFilter:
    def __init__(self):
        """Initialize with action patterns."""
        
    def classify(self, text: str) -> IntentClassification:
        """Classify input as ACTION or CONVERSATION."""
        
    def extract_action(self, text: str) -> Optional[ActionIntent]:
        """Extract structured action from text."""

class IntentClassification(Enum):
    ACTION = "action"           # Deterministic command
    CONVERSATION = "conversation"  # Needs LLM
    AMBIGUOUS = "ambiguous"     # Needs clarification

class ActionIntent:
    verb: str                   # open, write, send, etc.
    target: str                 # application, contact, file
    parameters: Dict[str, Any]  # Additional params
    confidence: float           # Pattern match confidence
```

**Algorithm: Pattern Matching**:
```
1. Normalize input text (lowercase, strip whitespace)
2. CRITICAL: Verify wake word has been stripped
   - If wake word present: Log error and strip it
3. Check action verb patterns:
   - "open [app]" → OPEN_APPLICATION
   - "write [text]" → WRITE_TEXT (triggers DICTATION_MODE)
   - "type [text]" → WRITE_TEXT (triggers DICTATION_MODE)
   - "send [message] to [contact]" → SEND_MESSAGE
   - "search for [query]" → WEB_SEARCH
   - "close [app]" → CLOSE_APPLICATION
4. If pattern matches with confidence ≥ 0.7:
   - Extract parameters using regex groups
   - Return ActionIntent
   - Set bypass_llm = True
5. If pattern matches with confidence 0.5-0.7:
   - Return AMBIGUOUS classification
   - Allow LLM for clarification
6. If no pattern matches or confidence < 0.5:
   - Return CONVERSATION classification
7. Log classification and confidence for monitoring
```

**Deterministic-First Guarantee**:
```
1. If Intent_Pre_Filter confidence ≥ 0.7:
   - Route directly to Command_Executor
   - NEVER call LLM
   - Log: "LLM bypassed (deterministic)"
2. If all action parameters are extractable:
   - Route directly to Command_Executor
   - NEVER call LLM
   - Log: "LLM bypassed (complete parameters)"
3. Only call LLM for:
   - Ambiguous targets ("open that", "send it")
   - Vague pronouns requiring context
   - Follow-up clarification questions
4. Track bypass rate:
   - Target: ≥ 80% of commands bypass LLM
   - Alert if bypass rate drops below 70%
```

**Pattern Definitions**:
```python
PATTERNS = {
    "open_application": [
        r"^(open|launch|start|run)\s+(.+)$",
        r"^(.+)\s+(please|pls)$",  # "notepad please"
    ],
    "write_text": [
        r"^(write|type)\s+(.+)$",
        r"^open\s+(.+)\s+and\s+(write|type)\s+(.+)$",
    ],
    "send_message": [
        r"^send\s+(whatsapp|message|text)\s+to\s+(.+)\s+saying\s+(.+)$",
        r"^message\s+(.+)\s+(.+)$",
    ],
    "web_search": [
        r"^(search|google|find|look\s+up)\s+(.+)$",
    ],
    "close_application": [
        r"^(close|exit|quit)\s+(.+)$",
    ],
}
```

### 3. Thread Safe Bridge

**Purpose**: Enable safe communication between background threads and Qt main thread. Enforce single response ownership.

**Single Response Ownership Rule**:
```
At any time, exactly ONE subsystem may produce a user-facing response.

Ownership Priority:
1. Command_Executor (during action execution)
2. Error_Handler (during failures)
3. Conversation_Manager (only when no action is executing)

Enforcement:
- When Command_Executor is active:
  * Conversation_Manager responses are suppressed
  * TTS is limited to action phrases only
  * LLM responses are queued but not spoken
- When action completes:
  * Only ExecutionResult.message is spoken
  * Conversation_Manager remains suppressed
- When action fails:
  * Only failure reason is spoken
  * No additional conversational responses
```

**Interface**:
```python
class ThreadSafeBridge(QObject):
    # Signals (emitted from any thread, received in main thread)
    set_avatar_state = pyqtSignal(AvatarState)
    speak_text = pyqtSignal(str, bool)  # text, interrupt
    show_message = pyqtSignal(str, str)  # title, message
    update_status = pyqtSignal(str)
    
    def __init__(self):
        """Initialize bridge in main thread."""
        
    def connect_avatar(self, avatar: AvatarWindow) -> None:
        """Connect signals to avatar slots."""
        
    def connect_voice(self, voice: VoiceInterface) -> None:
        """Connect signals to voice interface."""
```

**Thread Safety Guarantees**:
```
1. All signals use Qt::QueuedConnection (default for cross-thread)
2. Signal emission is thread-safe (Qt internal mutex)
3. Slot execution always occurs in receiver's thread
4. No direct Qt widget access from background threads
5. All cross-thread communication goes through signals
```

### 4. Command Executor

**Purpose**: Execute OS-level actions (launch apps, automate input, file operations).

**Interface**:
```python
class CommandExecutor:
    def __init__(self, audit_logger: AuditLogger):
        """Initialize with audit logger."""
        
    def execute(self, action: ActionIntent) -> ExecutionResult:
        """Execute action and return result."""
        
    def open_application(self, app_name: str) -> ExecutionResult:
        """Launch application by name."""
        
    def write_text(self, app_name: str, text: str) -> ExecutionResult:
        """Open app and type text."""
        
    def send_whatsapp_message(self, contact: str, message: str) -> ExecutionResult:
        """Send WhatsApp message."""
        
    def web_search(self, query: str) -> ExecutionResult:
        """Open browser with search query."""

class ExecutionResult:
    success: bool
    message: str
    execution_time: float
    error: Optional[Exception]
```

**Algorithm: Application Launch**:
```
1. Normalize app name (lowercase, remove spaces)
2. Check app_mapping dictionary:
   - If found: Use mapped executable path
   - If not found: Proceed to dynamic discovery
3. Dynamic Discovery:
   a. Search paths in order:
      - C:\Program Files\{app_name}\
      - C:\Program Files (x86)\{app_name}\
      - %LOCALAPPDATA%\Programs\{app_name}\
      - %APPDATA%\Microsoft\Windows\Start Menu\Programs\
      - %LOCALAPPDATA%\Microsoft\WindowsApps\
   b. For each path:
      - List all .exe files
      - Fuzzy match against app_name
      - If match score > 0.8: Use this executable
4. Launch application:
   - Use subprocess.Popen with CREATE_NEW_CONSOLE
   - Set working directory to executable directory
   - Capture stdout/stderr for error handling
5. Verify launch:
   - Wait up to 3 seconds for process to start
   - Check if process is still running
   - Return success/failure
```

**Algorithm: Text Automation (Notepad)**:
```
1. Launch Notepad using open_application()
2. Wait for window to appear (up to 5 seconds):
   - Use win32gui.FindWindow("Notepad", None)
   - Poll every 100ms
3. Bring window to foreground:
   - win32gui.SetForegroundWindow(hwnd)
4. Wait 500ms for window to be ready
5. Type text character by character:
   - Use win32api.SendMessage with WM_CHAR
   - Or use pyautogui.typewrite() for simplicity
   - Delay 10ms between characters
6. Verify text was typed:
   - Read window text using win32gui.GetWindowText()
   - Compare with expected text
7. Return success/failure
```

**Algorithm: WhatsApp Automation**:
```
1. Check if WhatsApp Desktop is installed:
   - Look for %LOCALAPPDATA%\WhatsApp\WhatsApp.exe
   - If not found: Return error with download link
2. Launch WhatsApp Desktop
3. Wait for main window (up to 10 seconds):
   - Use UI Automation to find window
   - If timeout: Fallback to manual prompt
4. Find search box:
   - Use UI Automation to locate search control
   - AutomationId: "side-search"
   - If not found: Fallback to manual prompt
5. Type contact name:
   - Set focus to search box
   - Type contact name
   - Wait 1 second for results
6. Select first result:
   - Use UI Automation to find first chat item
   - Invoke click action
   - If fails: Fallback to manual prompt
7. Find message input box:
   - AutomationId: "main-message-input"
   - If not found: Fallback to manual prompt
8. Type message:
   - Set focus to input box
   - Type message text
9. Send message:
   - Press Enter key
   - Or click send button (AutomationId: "send-button")
10. Verify sent:
    - Wait for message to appear in chat history
    - Check for checkmark icon
    - If verification fails: Warn user to check manually
11. Return success/failure

Fallback to Manual Prompt:
- Speak: "I've opened WhatsApp. Please send the message manually."
- Display message text in GUI for copy-paste
- Log automation failure to audit logger
- Return partial success
```

### 5. Authority State Machine

**Purpose**: Enforce capability-based security with biometric authentication.

**State Machine**:
```
States:
- UNARMED: No authority granted (default)
- ARMED: Authority granted, commands allowed
- LOCKED: Security violation, workstation locked
- SUSPENDED: Temporarily suspended (e.g., during UAC prompt)

Transitions:
UNARMED --[biometric_success]--> ARMED
ARMED --[15min_timeout]--> UNARMED
ARMED --[manual_revoke]--> UNARMED
ARMED --[security_violation]--> LOCKED
LOCKED --[manual_unlock + biometric]--> UNARMED
ARMED --[uac_prompt]--> SUSPENDED
SUSPENDED --[uac_complete]--> ARMED
```

**Interface**:
```python
class AuthorityStateMachine:
    def __init__(self, config: AuthorityConfiguration):
        """Initialize state machine."""
        
    def grant_authority(self, reason: StateTransitionReason, 
                       metadata: Dict[str, Any]) -> bool:
        """Grant authority after successful authentication."""
        
    def revoke_authority(self, reason: StateTransitionReason,
                        metadata: Dict[str, Any]) -> bool:
        """Revoke authority and return to UNARMED."""
        
    def lock_workstation(self, reason: str) -> bool:
        """Lock workstation and transition to LOCKED."""
        
    def is_armed(self) -> bool:
        """Check if authority is currently granted."""
        
    def get_state_info(self) -> Dict[str, Any]:
        """Get detailed state information."""
        
    def check_timeout(self) -> None:
        """Check for inactivity timeout (called periodically)."""

class StateTransitionReason(Enum):
    BIOMETRIC_SUCCESS = "biometric_success"
    TIMEOUT = "timeout"
    MANUAL_REVOKE = "manual_revoke"
    SECURITY_VIOLATION = "security_violation"
    MANUAL_UNLOCK = "manual_unlock"
    UAC_PROMPT = "uac_prompt"
    UAC_COMPLETE = "uac_complete"
```

**Algorithm: Authority Grant**:
```
1. Check current state:
   - If LOCKED: Reject (must unlock first)
   - If ARMED: Extend timeout, return success
   - If UNARMED: Proceed to authentication
2. Invoke biometric authentication:
   - Call BiometricProvider.authenticate()
   - Wait for result (up to 30 seconds)
3. If authentication succeeds:
   - Generate new session ID (UUID)
   - Set armed_timestamp = now()
   - Set last_activity_timestamp = now()
   - Transition to ARMED state
   - Log to audit logger
   - Return success
4. If authentication fails:
   - Increment failed_attempts counter
   - If failed_attempts >= 3:
      * Trigger security lockout
      * Transition to LOCKED
   - Log to audit logger
   - Return failure
```

**Algorithm: Timeout Check**:
```
1. If state != ARMED: Return (no timeout needed)
2. Calculate time_since_activity = now() - last_activity_timestamp
3. If time_since_activity > 15 minutes:
   - Revoke authority with reason=TIMEOUT
   - Transition to UNARMED
   - Log to audit logger
4. If time_since_activity > 14 minutes:
   - Emit warning signal (1 minute remaining)
```

### 6. Audit Logger

**Purpose**: Cryptographically-secured tamper-evident logging.

**Interface**:
```python
class AuditLogger:
    def __init__(self, log_directory: str, enable_real_time_verification: bool):
        """Initialize audit logger."""
        
    def log_system_event(self, event_type: str, data: Dict[str, Any],
                        severity: AuditSeverity) -> None:
        """Log system event."""
        
    def log_security_event(self, event_type: str, data: Dict[str, Any],
                          severity: AuditSeverity) -> None:
        """Log security event."""
        
    def log_command_execution(self, command: str, result: ExecutionResult,
                             user: str) -> None:
        """Log command execution."""
        
    def log_emergency_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log emergency event (highest priority)."""
        
    def verify_integrity(self) -> Tuple[bool, List[str]]:
        """Verify cryptographic chain integrity."""
        
    def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics."""

class AuditEvent:
    event_id: str          # UUID
    timestamp: datetime    # ISO 8601
    event_type: str        # system_startup, command_execution, etc.
    severity: AuditSeverity
    data: Dict[str, Any]   # Event-specific data
    user: str              # User identifier
    session_id: str        # Authority session ID
    signature: str         # HMAC-SHA256
    previous_signature: str  # Chain link
```

**Algorithm: Log Entry Creation**:
```
1. Generate event_id = UUID()
2. Capture timestamp = now() (ISO 8601)
3. Sanitize data:
   - Remove any PII (passwords, biometric data)
   - Truncate long strings to 1000 chars
   - Redact sensitive fields
4. Create event object:
   - Set all fields from parameters
   - Set previous_signature from last log entry
5. Compute signature:
   - Concatenate: event_id + timestamp + event_type + json(data) + previous_signature
   - signature = HMAC-SHA256(concatenated, secret_key)
6. Write to log file:
   - Append JSON line to current log file
   - Flush to disk immediately
7. Update last_signature = signature
8. If real-time verification enabled:
   - Verify signature matches expected
   - If mismatch: Trigger emergency alert
```

**Algorithm: Integrity Verification**:
```
1. Read all log entries from log directory
2. Sort by timestamp
3. Initialize expected_signature = None
4. For each entry:
   a. Recompute signature:
      - Concatenate fields as in creation
      - signature = HMAC-SHA256(concatenated, secret_key)
   b. Compare with entry.signature:
      - If mismatch: Record tampering at this entry
   c. Verify chain:
      - If entry.previous_signature != expected_signature:
         * Record chain break at this entry
   d. Update expected_signature = entry.signature
5. Return (is_valid, list_of_violations)
```


### 7. LLM Adapter

**Purpose**: Multi-provider AI model integration with intelligent fallback.

**Interface**:
```python
class LLMAdapter:
    def __init__(self, config: LLMConfiguration):
        """Initialize with provider configuration."""
        
    def generate_response(self, prompt: str, context: List[Message],
                         model_type: ModelType, timeout: float = 10.0) -> LLMResponse:
        """Generate response with timeout and fallback."""
        
    def detect_intent(self, text: str) -> IntentDetection:
        """Fast intent detection using 7B model."""
        
    def structure_action(self, text: str) -> ActionStructure:
        """Structure action parameters using 7B model."""
        
    def deep_reasoning(self, question: str, context: str) -> ReasoningResult:
        """Deep reasoning using 14B model (slow, only when needed)."""

class ModelType(Enum):
    CONVERSATION = "conversation"  # qwen2.5:7b-instruct
    INTENT = "intent"              # mistral:7b-instruct
    REASONING = "reasoning"        # qwen2.5:14b-instruct

class LLMResponse:
    text: str
    model_used: str
    latency: float
    tokens_used: int
    fallback_used: bool
```

**Algorithm: Generate Response with Fallback**:
```
1. Start timeout timer (10 seconds default)
2. Create background thread for LLM request:
   a. Select provider based on model_type:
      - CONVERSATION → Ollama qwen2.5:7b-instruct
      - INTENT → Ollama mistral:7b-instruct
      - REASONING → Ollama qwen2.5:14b-instruct
   b. Format prompt with context
   c. Send request to provider
   d. Wait for response
3. In main thread:
   - Wait for either:
     * LLM response arrives
     * Timeout expires (10s)
4. If LLM responds before timeout:
   - Return LLM response
   - Set fallback_used = False
5. If timeout expires:
   - Cancel LLM request
   - Select template response based on intent
   - Return template response
   - Set fallback_used = True
6. Log response metadata to audit logger
```

**Template Responses**:
```python
TEMPLATES = {
    "greeting": [
        "Hello! How can I help you?",
        "Hi there! What can I do for you?",
    ],
    "acknowledgment": [
        "Got it.",
        "Understood.",
        "Okay.",
    ],
    "error": [
        "I'm sorry, I couldn't process that.",
        "Something went wrong. Please try again.",
    ],
    "timeout": [
        "I'm thinking... This is taking longer than expected.",
    ],
}
```

### 8. TTS Service

**Purpose**: Text-to-speech synthesis with priority queue, Windows SAPI integration, and human co-worker speech contract.

**Human Co-Worker Speech Contract**:
```
During Action Execution:
- Use verb-first phrases ≤ 5 words
- Examples: "Opening WhatsApp", "Typing message", "Sending"
- NO questions
- NO explanations

During Idle:
- Natural but brief
- Conversational tone allowed
- Still concise

FORBIDDEN Phrases:
❌ "How can I help you?"
❌ "Sure, I can..."
❌ "Let me know if..."
❌ "Is there anything else?"
❌ "I'd be happy to..."

APPROVED Action Phrases:
✅ "Opening [app]"
✅ "Done"
✅ "Typed"
✅ "Sent"
✅ "Failed: [reason]"
✅ "Searching"
✅ "Closing [app]"
```

**Interface**:
```python
class TTSService:
    def __init__(self):
        """Initialize TTS service with dedicated thread."""
        
    def speak(self, text: str, priority: TTSPriority = TTSPriority.NORMAL,
             interrupt: bool = False) -> None:
        """Queue text for speech synthesis."""
        
    def stop(self) -> None:
        """Stop current speech and clear queue."""
        
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        
    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)."""
        
    def set_rate(self, rate: int) -> None:
        """Set speech rate (-10 to 10)."""

class TTSPriority(Enum):
    CRITICAL = 0   # Security alerts, errors
    HIGH = 1       # Action confirmations
    NORMAL = 2     # Responses
    LOW = 3        # Background info
```

**Algorithm: Priority Queue Processing**:
```
1. Dedicated TTS thread runs continuously:
   while not stop_requested:
       a. Check priority queue (blocking wait):
          - Try CRITICAL queue first
          - Then HIGH queue
          - Then NORMAL queue
          - Then LOW queue
       b. If item found:
          - Extract (text, priority)
          - Synthesize speech using SAPI
          - Wait for synthesis to complete
       c. If stop_requested:
          - Break loop
2. Speech synthesis:
   a. Create SAPI voice object:
      - voice = win32com.client.Dispatch("SAPI.SpVoice")
   b. Set voice properties:
      - voice.Volume = 100 (bypass Volume Mixer)
      - voice.Rate = 0 (normal speed)
   c. Speak text:
      - voice.Speak(text, 0)  # 0 = synchronous
   d. Wait for completion
3. If interrupt flag set:
   - Clear all queues
   - Stop current speech
   - Process new item immediately
```

### 9. Memory System

**Purpose**: Encrypted conversation history with vector search. NEVER influences command execution.

**Memory Isolation Guarantee**:
```
CRITICAL RULE: Memory System is READ-ONLY for context retrieval.

Memory SHALL:
- Store conversation history encrypted
- Provide semantic search for context
- Support conversation export

Memory SHALL NEVER:
- Influence command execution logic
- Be queried during action processing
- Store command execution results
- Affect Intent_Pre_Filter decisions
- Affect Command_Executor behavior

Separation:
- Audit logs: Separate database (audit_logs.db)
- Conversations: Separate database (conversations.db)
- Command execution: No memory access
- Action routing: No memory access
```

**Interface**:
```python
class MemorySystem:
    def __init__(self, encryption_key: bytes):
        """Initialize with encryption key derived from biometric."""
        
    def store_conversation(self, user_message: str, assistant_response: str,
                          timestamp: datetime) -> None:
        """Store conversation turn encrypted."""
        
    def search_conversations(self, query: str, limit: int = 10) -> List[ConversationTurn]:
        """Semantic search using vector embeddings."""
        
    def get_recent_context(self, limit: int = 5) -> List[ConversationTurn]:
        """Get recent conversation history."""
        
    def purge_old_conversations(self, days: int = 90) -> int:
        """Delete conversations older than specified days."""
        
    def export_conversations(self, output_path: str) -> None:
        """Export conversations to encrypted file."""

class ConversationTurn:
    turn_id: str
    timestamp: datetime
    user_message: str
    assistant_response: str
    embedding: np.ndarray  # Vector embedding for search
```

**Algorithm: Store Conversation**:
```
1. Generate turn_id = UUID()
2. Compute embedding:
   - Use sentence-transformers model (all-MiniLM-L6-v2)
   - embedding = model.encode(user_message + assistant_response)
3. Create conversation object:
   - Set all fields
4. Encrypt conversation:
   - Serialize to JSON
   - encrypted = AES-256-GCM.encrypt(json, encryption_key, nonce)
5. Store to database:
   - SQLite table: conversations
   - Columns: turn_id, timestamp, encrypted_data, embedding_blob
6. Update vector index:
   - Add embedding to FAISS index
   - Map turn_id to index position
```

**Algorithm: Semantic Search**:
```
1. Compute query embedding:
   - query_embedding = model.encode(query)
2. Search vector index:
   - distances, indices = faiss_index.search(query_embedding, limit)
3. Retrieve conversations:
   - For each index:
     * Get turn_id from mapping
     * Load encrypted_data from database
     * Decrypt using encryption_key
     * Deserialize JSON
4. Sort by relevance (distance)
5. Return top results
```

### 10. Failure Orchestrator

**Purpose**: Component health monitoring and automatic recovery.

**Interface**:
```python
class FailureOrchestrator:
    def __init__(self):
        """Initialize with component registry."""
        
    def register_component(self, component: Component,
                          dependencies: List[str]) -> None:
        """Register component with dependencies."""
        
    def check_health(self) -> Dict[str, ComponentHealth]:
        """Check health of all components."""
        
    def handle_failure(self, component_name: str, error: Exception) -> RecoveryAction:
        """Handle component failure and attempt recovery."""
        
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get component dependency graph."""

class ComponentHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"

class RecoveryAction(Enum):
    RESTART = "restart"
    DEGRADE = "degrade"
    FAILOVER = "failover"
    MANUAL_INTERVENTION = "manual_intervention"
```

**Algorithm: Health Check**:
```
1. For each registered component:
   a. Call component.health_check():
      - Timeout after 5 seconds
   b. If health_check succeeds:
      - Mark as HEALTHY
   c. If health_check fails:
      - Increment failure_count
      - If failure_count < 3:
         * Mark as DEGRADED
         * Attempt restart
      - If failure_count >= 3:
         * Mark as FAILED
         * Check dependencies
   d. If component is FAILED:
      - Get dependent components
      - For each dependent:
         * If dependent is critical:
            - Mark as DEGRADED
            - Disable features that require failed component
         * If dependent is non-critical:
            - Continue normal operation
2. Log health status to audit logger
3. Return health map
```

**Dependency Graph**:
```
Authority State Machine (CRITICAL)
├── Audit Logger (CRITICAL)
├── Biometric Provider (CRITICAL)
└── Intrusion Detector (CRITICAL)

Command Executor (CRITICAL)
├── Authority State Machine (CRITICAL)
└── Audit Logger (CRITICAL)

Voice Interface (CRITICAL)
├── Thread Safe Bridge (CRITICAL)
└── TTS Service (HIGH)

LLM Adapter (HIGH)
└── (no dependencies)

Memory System (MEDIUM)
└── (no dependencies)

Skills Registry (LOW)
├── Authority State Machine (CRITICAL)
└── Audit Logger (CRITICAL)
```

## Data Models

### Configuration Schema

```json
{
  "llm_config": {
    "conversation": {
      "provider": "ollama",
      "model": "qwen2.5:7b-instruct",
      "timeout_seconds": 120,
      "max_retries": 1
    },
    "intent": {
      "provider": "ollama",
      "model": "mistral:7b-instruct",
      "timeout_seconds": 30,
      "max_retries": 1
    },
    "reasoning": {
      "provider": "ollama",
      "model": "qwen2.5:14b-instruct",
      "timeout_seconds": 180,
      "max_retries": 1
    },
    "fallback": {
      "enabled": true,
      "timeout_seconds": 10
    }
  },
  "authority_config": {
    "timeout_minutes": 15,
    "max_failed_attempts": 3,
    "require_biometric": true,
    "test_mode_disable_lock": false
  },
  "voice_config": {
    "wake_word": "hey guru",
    "language": "en",
    "silence_timeout_seconds": 5,
    "energy_threshold": 300
  },
  "tts_config": {
    "volume": 100,
    "rate": 0,
    "voice": "default"
  },
  "memory_config": {
    "retention_days": 90,
    "max_conversations": 10000,
    "enable_vector_search": true
  }
}
```

### Audit Log Schema

```json
{
  "event_id": "uuid",
  "timestamp": "2026-01-14T12:34:56.789Z",
  "event_type": "command_execution",
  "severity": "INFO",
  "user": "username",
  "session_id": "session-uuid",
  "data": {
    "command": "open notepad",
    "result": "success",
    "execution_time_ms": 234
  },
  "signature": "hmac-sha256-hex",
  "previous_signature": "hmac-sha256-hex"
}
```

### Database Schema (SQLite)

```sql
-- Conversations table
CREATE TABLE conversations (
    turn_id TEXT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    encrypted_data BLOB NOT NULL,
    embedding_blob BLOB NOT NULL,
    INDEX idx_timestamp (timestamp)
);

-- Authority sessions table
CREATE TABLE authority_sessions (
    session_id TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    armed_timestamp DATETIME NOT NULL,
    revoked_timestamp DATETIME,
    revoke_reason TEXT,
    INDEX idx_user (user),
    INDEX idx_armed (armed_timestamp)
);

-- Component health table
CREATE TABLE component_health (
    component_name TEXT PRIMARY KEY,
    last_check_timestamp DATETIME NOT NULL,
    health_status TEXT NOT NULL,
    failure_count INTEGER DEFAULT 0,
    last_error TEXT
);

-- Skills registry table
CREATE TABLE skills (
    skill_id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    version TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    permissions TEXT NOT NULL,  -- JSON array
    last_loaded DATETIME
);
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Voice Interface Properties

**Property 1: Wake Word Activation**
*For any* audio input containing the wake word while in INACTIVE state, the Voice_Interface should transition to ACTIVE state and begin processing commands.
**Validates: Requirements 1.1, 22.2**

**Property 2: Continuous Listening Without Re-Activation**
*For any* sequence of voice commands after initial wake word activation, the system should process all commands without requiring the wake word again until deactivation.
**Validates: Requirements 1.2, 22.3**

**Property 3: Idle State Transition Timing**
*For any* period of silence lasting exactly 5 seconds while in ACTIVE state, the Voice_Interface should transition to IDLE state.
**Validates: Requirements 1.3, 22.4**

**Property 4: Deactivation Command Recognition**
*For any* of the deactivation phrases ("stop", "sleep", "exit", "that's all"), the Voice_Interface should transition to INACTIVE state.
**Validates: Requirements 1.4, 22.6**

**Property 5: Wake Word Suppression in Active States**
*For any* audio input containing the wake word while in ACTIVE or IDLE state, the system should ignore the wake word and continue normal processing.
**Validates: Requirements 1.5, 22.7**

**Property 6: State Transition Logging**
*For any* state transition in the Voice_Interface, a log entry should be created with the transition details.
**Validates: Requirements 22.8**

### Command Execution Properties

**Property 7: Application Launch Success**
*For any* application name in the supported database, the Command_Executor should successfully launch the application within 1 second.
**Validates: Requirements 2.1, 2.7**

**Property 8: Dynamic Application Discovery**
*For any* application not in the database but installed in standard paths, the Command_Executor should discover and launch it.
**Validates: Requirements 2.3**

**Property 9: Exact Text Dictation**
*For any* text dictation command, the system should type the exact text without rephrasing, grammar correction, or interpretation.
**Validates: Requirements 2.5, 14, 21.6**

**Property 10: Compound Action Execution**
*For any* compound command like "open [app] and write [text]", the system should execute both actions in sequence.
**Validates: Requirements 2.4**

**Property 11: Web Search Execution**
*For any* search query, the Command_Executor should open the default browser with a Google search for that query.
**Validates: Requirements 2.6**

**Property 12: Text Automation Performance**
*For any* text automation command, the execution should complete within 2 seconds.
**Validates: Requirements 2.8**

### Action Commitment Properties

**Property 13: Action Verb Detection and LLM Bypass**
*For any* user input containing action verbs (open, type, write, delete, click, send, close, remove), the system should bypass the conversation LLM and route directly to Command_Executor.
**Validates: Requirements 21.1, 24.2**

**Property 14: Deterministic Action Execution**
*For any* action command, the system should either execute successfully or return a specific failure reason—never a conversational response.
**Validates: Requirements 21.2**

**Property 15: No Conversational Responses for Actions**
*For any* actionable command, the system response should be action-specific (e.g., "Opening", "Done") and never conversational (e.g., "Sure, I can help with that").
**Validates: Requirements 21.3**

**Property 16: No Unnecessary Follow-Up Questions**
*For any* unambiguous action command, the system should execute without asking follow-up questions.
**Validates: Requirements 21.5**

**Property 17: Brief Action Confirmations**
*For any* completed action, the TTS_Service should speak a brief confirmation (e.g., "Done", "Opened", "Sent") and nothing more.
**Validates: Requirements 21.7, 23.3**

### Authority and Security Properties

**Property 18: Initial State is UNARMED**
*For any* system startup, the Authority_State_Machine should initialize in UNARMED state.
**Validates: Requirements 3.1**

**Property 19: Biometric Authentication Grants Authority**
*For any* successful biometric authentication, the Authority_State_Machine should transition to ARMED state.
**Validates: Requirements 3.2**

**Property 20: Commands Require ARMED State**
*For any* command execution attempt, it should succeed only if the Authority_State_Machine is in ARMED state.
**Validates: Requirements 3.3**

**Property 21: Inactivity Timeout Revokes Authority**
*For any* 15-minute period of inactivity while in ARMED state, the Authority_State_Machine should automatically revoke authority.
**Validates: Requirements 3.4**

**Property 22: Security Violations Trigger Lockdown**
*For any* detected security violation, the Authority_State_Machine should immediately transition to LOCKED state and trigger workstation lock.
**Validates: Requirements 3.5, 6.4**

**Property 23: LOCKED State Blocks All Commands**
*For any* command attempt while in LOCKED state, the system should reject it until manual unlock.
**Validates: Requirements 3.6**

**Property 24: State Transitions Are Logged**
*For any* Authority_State_Machine state transition, an audit log entry should be created.
**Validates: Requirements 3.7**

**Property 25: Failed Authentication Lockout**
*For any* sequence of 3 failed biometric authentication attempts within 5 minutes, the system should trigger security lockout.
**Validates: Requirements 4.5, 6.2**

### Audit Logging Properties

**Property 26: Command Execution Logging Completeness**
*For any* command execution, the Audit_Logger should create a log entry containing timestamp, user, command text, and result.
**Validates: Requirements 5.1**

**Property 27: Cryptographic Signature Integrity**
*For any* audit log entry, it should have a valid HMAC-SHA256 signature computed from its contents.
**Validates: Requirements 5.4**

**Property 28: Signature Chain Integrity**
*For any* pair of consecutive audit log entries, the second entry's previous_signature should match the first entry's signature.
**Validates: Requirements 5.5**

**Property 29: Tamper Detection**
*For any* audit log that has been tampered with, the verify_integrity() function should detect the tampering and report the violated entries.
**Validates: Requirements 5.6**

**Property 30: Sensitive Data Redaction**
*For any* audit log entry, it should never contain passwords, biometric templates, or other sensitive personal information.
**Validates: Requirements 5.8**

### Thread Safety Properties

**Property 31: Cross-Thread Signal Delivery**
*For any* signal emitted from a background thread, it should be delivered to the main thread via Qt's QueuedConnection.
**Validates: Requirements 8.2**

**Property 32: No Direct Widget Access from Background Threads**
*For any* Qt widget operation, it should occur only in the main Qt thread.
**Validates: Requirements 8.3, 8.6**

### TTS Properties

**Property 33: Priority Queue Ordering**
*For any* set of queued TTS requests with different priorities, they should be processed in priority order (CRITICAL > HIGH > NORMAL > LOW).
**Validates: Requirements 9.4**

**Property 34: Silence During Dictation**
*For any* dictation command, the TTS_Service should remain silent while typing occurs.
**Validates: Requirements 23.2**

**Property 35: Concise Action Speech**
*For any* action execution, the TTS_Service should speak only a short verb phrase (e.g., "Opening WhatsApp") and not verbose explanations.
**Validates: Requirements 23.1, 23.6**

**Property 36: No Chatbot Phrases**
*For any* TTS output during action execution, it should never contain chatbot phrases like "How can I help you?" or "Sure, I can do that".
**Validates: Requirements 23.7**

### LLM Integration Properties

**Property 37: Timeout Fallback to Templates**
*For any* LLM request that exceeds 10 seconds, the system should fall back to template responses.
**Validates: Requirements 7.5**

**Property 38: No Cloud Data Without Consent**
*For any* user data, it should never be sent to cloud LLM providers without explicit user consent.
**Validates: Requirements 7.6**

**Property 39: Response Caching**
*For any* duplicate LLM request, the system should return the cached response without making a new API call.
**Validates: Requirements 7.7**

**Property 40: Intent Pre-Filter Performance**
*For any* input text, the Intent_Pre_Filter should complete pattern matching within 10 milliseconds.
**Validates: Requirements 24.5**

**Property 41: LLM Bypass for Known Patterns**
*For any* input matching a known action pattern, the system should bypass the LLM and route directly to Command_Executor.
**Validates: Requirements 24.2, 24.3**

**Property 42: LLM Usage Only for Ambiguity**
*For any* unambiguous action command, the system should not invoke the LLM.
**Validates: Requirements 24.4**

### Memory System Properties

**Property 43: Conversation Encryption**
*For any* stored conversation, it should be encrypted using AES-256-GCM.
**Validates: Requirements 10.1**

**Property 44: Semantic Search Accuracy**
*For any* conversation search query, the returned results should be semantically relevant to the query.
**Validates: Requirements 10.3**

**Property 45: Conversation Retrieval Round-Trip**
*For any* stored conversation, encrypting then decrypting should produce the original conversation data.
**Validates: Requirements 10.4**

**Property 46: Automatic Purging**
*For any* conversation older than 90 days, it should be automatically purged from storage.
**Validates: Requirements 10.5**

**Property 47: No Plaintext Keys**
*For any* encryption key used by the Memory_System, it should never be stored in plaintext.
**Validates: Requirements 10.6**

**Property 48: Memory Isolation from Commands**
*For any* action command execution, the conversation history should not influence the execution logic.
**Validates: Requirements 27.2, 27.3**

**Property 49: Separate Storage for Audit and Conversation**
*For any* audit log entry and conversation entry, they should be stored in separate databases.
**Validates: Requirements 27.6**

### Failure Recovery Properties

**Property 50: Periodic Health Monitoring**
*For any* 30-second interval, the Failure_Orchestrator should perform health checks on all components.
**Validates: Requirements 11.1**

**Property 51: Automatic Component Restart**
*For any* component failure (first or second occurrence), the Failure_Orchestrator should attempt automatic restart.
**Validates: Requirements 11.2**

**Property 52: Permanent Failure After Three Attempts**
*For any* component that fails 3 times, the Failure_Orchestrator should mark it as permanently failed and stop restart attempts.
**Validates: Requirements 11.3**

**Property 53: Graceful Degradation**
*For any* critical component failure, dependent features should gracefully degrade rather than crash.
**Validates: Requirements 11.5**

**Property 54: Failure Logging**
*For any* component failure, the Failure_Orchestrator should log it to the Audit_Logger.
**Validates: Requirements 11.6**

### Permission Model Properties

**Property 55: UAC Prompt for Admin Actions**
*For any* admin-level action request, the system should trigger an OS UAC prompt.
**Validates: Requirements 25.2**

**Property 56: Execution Pause During UAC**
*For any* UAC prompt, the system should pause execution until the user responds.
**Validates: Requirements 25.3**

**Property 57: Permission Elevation Logging**
*For any* permission elevation request, it should be logged to the Audit_Logger.
**Validates: Requirements 25.4**

**Property 58: Skill Permission Declaration**
*For any* loaded skill, it should explicitly declare all required permissions in its manifest.
**Validates: Requirements 25.5**

**Property 59: Excessive Permission Rejection**
*For any* skill requesting excessive permissions without justification, the Skills_Registry should reject it.
**Validates: Requirements 25.6**

### WhatsApp Automation Properties

**Property 60: WhatsApp Desktop Targeting**
*For any* WhatsApp message command, the system should target WhatsApp Desktop application (not web version).
**Validates: Requirements 26.1**

**Property 61: Startup Delay Handling**
*For any* WhatsApp Desktop launch, the system should gracefully handle startup delays up to 10 seconds.
**Validates: Requirements 26.4**

**Property 62: Message Send Verification**
*For any* WhatsApp message send command, the system should verify the message was sent before confirming to the user.
**Validates: Requirements 26.5**

**Property 63: Contact Name Fuzzy Matching**
*For any* contact name with 80% or higher similarity to a stored contact, the system should successfully match and select it.
**Validates: Requirements 26.6**

### Error Handling Properties

**Property 64: Exception Isolation**
*For any* component exception, the system should catch it, log it, and continue operation without crashing the entire application.
**Validates: Requirements 20.1, 20.2**

**Property 65: Actionable Error Messages**
*For any* command failure, the system should speak an error message that explains what went wrong in user-friendly terms.
**Validates: Requirements 20.3, 20.4**

**Property 66: Transient Failure Retry**
*For any* transient failure (network, LLM timeout), the system should automatically retry the operation.
**Validates: Requirements 20.5**

**Property 67: No Security Failure Retry**
*For any* security-related failure (authentication, authorization), the system should never automatically retry.
**Validates: Requirements 20.6**

### Single Response Ownership Properties

**Property 68: Exclusive Response Ownership**
*For any* user command, exactly one subsystem should produce a user-facing response.
**Validates: Requirements 28.1**

**Property 69: Action Execution Suppresses Conversation**
*For any* command being executed by Command_Executor, the Conversation_Manager should not produce any response.
**Validates: Requirements 28.2, 28.4**

**Property 70: Action Success Speaks Only Result**
*For any* successful action execution, only the ExecutionResult.message should be spoken.
**Validates: Requirements 28.5**

**Property 71: Action Failure Speaks Only Reason**
*For any* failed action execution, only the failure reason should be spoken.
**Validates: Requirements 28.6**

**Property 72: No Duplicate Responses**
*For any* single command, the system should never produce both an action confirmation and a conversational response.
**Validates: Requirements 28.7**

### Dictation Mode Properties

**Property 73: Dictation Mode Entry**
*For any* command containing "write", "type", or "dictate", the Voice_Interface should enter DICTATION_MODE.
**Validates: Requirements 29.2**

**Property 74: Intent Pre-Filter Bypass in Dictation**
*For any* input while in DICTATION_MODE, the Intent_Pre_Filter should be bypassed.
**Validates: Requirements 29.3**

**Property 75: LLM Bypass in Dictation**
*For any* input while in DICTATION_MODE, the LLM_Adapter should be bypassed.
**Validates: Requirements 29.4**

**Property 76: TTS Mute in Dictation**
*For any* input while in DICTATION_MODE, the TTS_Service should be muted.
**Validates: Requirements 29.5**

**Property 77: Dictation Mode Exit on Silence**
*For any* 2-second period of silence in DICTATION_MODE, the Voice_Interface should exit to COMMAND_MODE.
**Validates: Requirements 29.6**

**Property 78: Dictation Mode Exit on Command**
*For any* "done" or "stop writing" command in DICTATION_MODE, the Voice_Interface should exit to COMMAND_MODE.
**Validates: Requirements 29.7**

### Wake Word Stripping Properties

**Property 79: Wake Word Removal in Active State**
*For any* transcribed text while in ACTIVE state, the wake word should be removed before downstream processing.
**Validates: Requirements 30.1**

**Property 80: Intent Pre-Filter Never Sees Wake Word**
*For any* input to Intent_Pre_Filter, it should never contain the wake word.
**Validates: Requirements 30.2**

**Property 81: Command Executor Never Sees Wake Word**
*For any* input to Command_Executor, it should never contain the wake word.
**Validates: Requirements 30.3**

**Property 82: LLM Never Sees Wake Word**
*For any* input to LLM_Adapter, it should never contain the wake word.
**Validates: Requirements 30.4**

**Property 83: Wake Word Stripping Example**
*For any* input "hey guru open notepad", the system should process only "open notepad".
**Validates: Requirements 30.5**

### Deterministic-First Properties

**Property 84: High Confidence Bypasses LLM**
*For any* Intent_Pre_Filter classification with confidence ≥ 0.7, the LLM should never be called.
**Validates: Requirements 31.1**

**Property 85: Complete Parameters Bypass LLM**
*For any* action command with fully extractable parameters, the LLM should never be called.
**Validates: Requirements 31.2**

**Property 86: LLM Only for Ambiguity**
*For any* unambiguous action command with clear parameters, the LLM should not be invoked.
**Validates: Requirements 31.3**

**Property 87: LLM Bypass Logging**
*For any* command, the system should log whether the LLM was bypassed.
**Validates: Requirements 31.4**

**Property 88: High Bypass Rate Target**
*For any* set of 100 consecutive commands, at least 80 should bypass the LLM through deterministic routing.
**Validates: Requirements 31.6**

### Speech Contract Properties

**Property 89: Action Speech Brevity**
*For any* action execution, TTS output should be verb-first and ≤ 5 words.
**Validates: Requirements 32.1**

**Property 90: No Questions During Actions**
*For any* action execution, TTS output should never contain questions.
**Validates: Requirements 32.2**

**Property 91: No Chatbot Greeting Phrases**
*For any* TTS output, it should never contain "How can I help you?".
**Validates: Requirements 32.4**

**Property 92: No Chatbot Confirmation Phrases**
*For any* TTS output, it should never contain "Sure, I can..." or "Let me know if...".
**Validates: Requirements 32.5, 32.6**

**Property 93: Approved Action Phrases Only**
*For any* action execution, TTS output should use only approved phrases: "Opening [app]", "Done", "Typed", "Sent", "Failed: [reason]".
**Validates: Requirements 32.7**

### Platform Abstraction Layer Properties

**Property 94: Core Logic Platform Isolation**
*For any* core logic module (Voice Interface, Intent Pre-Filter, Authority State Machine, Audit Logger, LLM Adapter, Memory System), it should not contain platform-specific imports or API calls.
**Validates: Requirements 33.2, 33.3, 33.4, 33.5, 42.1**

**Property 95: PAL Interface Communication**
*For any* interaction between core logic and platform-specific functionality, it should occur through PAL interfaces only.
**Validates: Requirements 33.1, 42.2**

**Property 96: Application Controller Consistency**
*For any* application control operation (open, close, is_running, discover), the Application_Controller should return consistent AppDescriptor objects across all platforms.
**Validates: Requirements 34.9**

**Property 97: Input Automation Capability Declaration**
*For any* platform backend, the Input_Automation should explicitly declare its capability limitations via get_capabilities().
**Validates: Requirements 35.8**

**Property 98: Speech Output Personality Consistency**
*For any* platform backend, the Speech_Output should maintain the Human Co-Worker Speech Contract.
**Validates: Requirements 36.2**

**Property 99: Speech Output Priority Queue Cross-Platform**
*For any* platform backend, the Speech_Output should provide consistent priority queue behavior (CRITICAL > HIGH > NORMAL > LOW).
**Validates: Requirements 36.7**

**Property 100: Speech Input State Machine Consistency**
*For any* platform backend, the Speech_Input should maintain identical state machine behavior (INACTIVE, ACTIVE, IDLE, DICTATION_MODE).
**Validates: Requirements 37.7**

**Property 101: Biometric Authentication Result Consistency**
*For any* platform backend, the Biometric_Authenticator should return consistent AuthResult objects with status, message, platform, and timestamp.
**Validates: Requirements 38.6**

**Property 102: Biometric Failure Lockout Cross-Platform**
*For any* platform backend, the Biometric_Authenticator should maintain identical failure lockout behavior (3 attempts within 5 minutes).
**Validates: Requirements 38.7**

**Property 103: Authority Scope Logging**
*For any* authority grant, the Audit_Logger should log the platform, authority scope (system-wide or app-level), and capability limitations.
**Validates: Requirements 39.7**

**Property 104: Mobile Authority Scope Restriction**
*For any* authority grant on mobile platforms (Android/iOS), the authority scope should be app-level only, never system-wide.
**Validates: Requirements 39.2, 39.3**

**Property 105: Desktop Authority Scope Permission**
*For any* authority grant on desktop platforms (Windows/macOS), the authority scope may include system-level actions.
**Validates: Requirements 39.4**

**Property 106: Security Enforcer Lock Scope Declaration**
*For any* platform backend, the Security_Enforcer should accurately report its lock scope via get_lock_scope() ("system", "screen", or "app").
**Validates: Requirements 40.2, 40.3, 40.4, 40.5**

**Property 107: Security Violation Detection Cross-Platform**
*For any* platform backend, the Security_Enforcer should maintain identical security violation detection logic.
**Validates: Requirements 40.6**

**Property 108: Capability Matrix Runtime Query**
*For any* platform, the system should provide programmatic access to the capability matrix via runtime queries.
**Validates: Requirements 41.7**

**Property 109: Core Logic State Machine Consistency**
*For any* platform, the core logic state machines (Voice Interface, Authority State Machine) should behave identically.
**Validates: Requirements 42.3**

**Property 110: Core Logic Security Invariants**
*For any* platform, the core logic should maintain identical security invariants (authority gating, audit logging, intrusion detection).
**Validates: Requirements 42.4**

**Property 111: Core Logic Audit Logging Consistency**
*For any* platform, the core logic should maintain identical audit logging behavior (signature chain, tamper detection, retention).
**Validates: Requirements 42.5**

**Property 112: Core Logic Platform-Agnostic Testing**
*For any* core logic component, it should be testable without platform-specific dependencies using mock PAL interfaces.
**Validates: Requirements 42.6**

### Platform Detection and Backend Selection Properties

**Property 113: Automatic Platform Detection**
*For any* supported platform (Windows, macOS, Android, iOS), the system should automatically detect it at startup.
**Validates: Requirements 43.1, 43.2**

**Property 114: Unsupported Platform Error**
*For any* unsupported platform, the system should raise PlatformNotSupportedError.
**Validates: Requirements 43.3**

**Property 115: Backend Factory Creation**
*For any* detected platform, the backend factory should create all six platform-specific backends (Application_Controller, Input_Automation, Speech_Output, Speech_Input, Biometric_Authenticator, Security_Enforcer).
**Validates: Requirements 43.4**

**Property 116: Dependency Injection**
*For any* core logic component initialization, platform backends should be injected via constructor parameters, never imported directly.
**Validates: Requirements 43.5, 43.7**

**Property 117: Platform Logging at Startup**
*For any* system initialization, the detected platform and capabilities should be logged to the audit logger.
**Validates: Requirements 43.6**


## Error Handling

### Error Classification

```python
class ErrorSeverity(Enum):
    RECOVERABLE = "recoverable"      # Can retry or degrade
    DEGRADED = "degraded"            # Feature unavailable, system continues
    CRITICAL = "critical"            # Requires immediate attention
    FATAL = "fatal"                  # System cannot continue

class ErrorCategory(Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NETWORK = "network"
    LLM_TIMEOUT = "llm_timeout"
    COMPONENT_FAILURE = "component_failure"
    COMMAND_EXECUTION = "command_execution"
    CONFIGURATION = "configuration"
    SECURITY_VIOLATION = "security_violation"
```

### Error Handling Strategy

**Authentication Errors**:
```
1. Biometric authentication fails:
   - Increment failed_attempts counter
   - If attempts < 3:
      * Speak: "Authentication failed. Please try again."
      * Allow retry
   - If attempts >= 3:
      * Trigger security lockout
      * Speak: "Too many failed attempts. System locked."
      * Log to audit logger with CRITICAL severity
      * Invoke workstation lock
2. Windows Hello unavailable:
   - Speak: "Biometric authentication unavailable. Please configure Windows Hello."
   - Provide setup instructions
   - Fall back to password authentication (if configured)
```

**Command Execution Errors**:
```
1. Application not found:
   - Speak: "I couldn't find [application]. Please check if it's installed."
   - Log to audit logger with INFO severity
   - Do not retry
2. Application launch fails:
   - Speak: "Failed to open [application]. Error: [specific reason]."
   - Log to audit logger with WARNING severity
   - Do not retry
3. Text automation fails:
   - Speak: "I couldn't type the text. The application may not be ready."
   - Log to audit logger with WARNING severity
   - Offer to retry
4. WhatsApp automation fails:
   - Speak: "WhatsApp message failed. [specific reason]."
   - Log to audit logger with WARNING severity
   - Do not retry (user should verify manually)
```

**LLM Errors**:
```
1. LLM timeout (> 10 seconds):
   - Cancel LLM request
   - Fall back to template response
   - Speak template response
   - Log to audit logger with INFO severity
   - Continue operation
2. LLM connection error:
   - Fall back to template response immediately
   - Speak template response
   - Log to audit logger with WARNING severity
   - Continue operation
3. LLM invalid response:
   - Fall back to template response
   - Speak: "I'm having trouble understanding. Please try again."
   - Log to audit logger with WARNING severity
   - Continue operation
```

**Component Failures**:
```
1. TTS Service fails:
   - Log to audit logger with CRITICAL severity
   - Display error message in GUI
   - Continue operation (silent mode)
   - Attempt restart after 30 seconds
2. Voice Interface fails:
   - Log to audit logger with CRITICAL severity
   - Speak: "Voice recognition unavailable. Please restart GURU."
   - Display error message in GUI
   - Attempt restart after 30 seconds
3. Authority State Machine fails:
   - Log to audit logger with FATAL severity
   - Immediately revoke all authority
   - Lock workstation
   - Display critical error message
   - Require manual restart
4. Audit Logger fails:
   - Log to emergency backup file
   - Display critical error message
   - Continue operation (degraded mode)
   - Alert user to check logs
```

**Security Violations**:
```
1. Intrusion detected:
   - Immediately transition to LOCKED state
   - Invoke workstation lock
   - Log to audit logger with CRITICAL severity
   - Send notification to user
   - Require manual unlock with biometric authentication
2. Audit log tampering detected:
   - Log to emergency backup file
   - Display critical security alert
   - Lock workstation
   - Require manual investigation
3. Unauthorized permission escalation attempt:
   - Reject operation immediately
   - Log to audit logger with CRITICAL severity
   - Increment security violation counter
   - If violations >= 3: Trigger lockdown
```

### Error Recovery Procedures

**Automatic Recovery**:
```
1. Transient network errors:
   - Retry up to 3 times with exponential backoff
   - Delays: 1s, 2s, 4s
   - If all retries fail: Fall back to local operation
2. LLM timeouts:
   - No retry (already timed out)
   - Fall back to template responses
   - Continue operation
3. Component failures (first occurrence):
   - Attempt automatic restart
   - Wait up to 10 seconds for restart
   - If restart succeeds: Resume operation
   - If restart fails: Mark as degraded
4. Component failures (second occurrence):
   - Attempt automatic restart again
   - Wait up to 10 seconds for restart
   - If restart succeeds: Resume operation
   - If restart fails: Mark as degraded
5. Component failures (third occurrence):
   - Mark as permanently failed
   - Disable dependent features
   - Log to audit logger with CRITICAL severity
   - Notify user
```

**Manual Recovery**:
```
1. Security lockout:
   - User must manually unlock
   - Requires biometric authentication
   - Resets failed_attempts counter
   - Logs unlock to audit logger
2. Critical component failure:
   - User must restart GURU
   - System performs full initialization
   - Verifies all components healthy
   - Logs restart to audit logger
3. Audit log corruption:
   - User must investigate manually
   - System provides diagnostic tools
   - Backup logs available for recovery
   - May require system reinstall if severe
```

## Testing Strategy

### Dual Testing Approach

GURU uses both unit testing and property-based testing to ensure comprehensive correctness:

- **Unit Tests**: Verify specific examples, edge cases, and error conditions
- **Property Tests**: Verify universal properties across all inputs

Both are complementary and necessary. Unit tests catch concrete bugs, while property tests verify general correctness.

### Unit Testing

**Scope**:
- Specific examples that demonstrate correct behavior
- Integration points between components
- Edge cases and error conditions
- Security boundary enforcement
- Configuration loading and validation

**Example Unit Tests**:
```python
def test_authority_state_machine_initial_state():
    """Verify initial state is UNARMED."""
    machine = create_authority_state_machine()
    assert machine.get_state() == AuthorityState.UNARMED

def test_biometric_authentication_success():
    """Verify successful authentication grants authority."""
    machine = create_authority_state_machine()
    biometric_provider = MockBiometricProvider(success=True)
    result = machine.grant_authority(biometric_provider)
    assert result == True
    assert machine.get_state() == AuthorityState.ARMED

def test_command_execution_requires_authority():
    """Verify commands fail without authority."""
    executor = CommandExecutor()
    machine = create_authority_state_machine()  # UNARMED
    result = executor.execute("open notepad")
    assert result.success == False
    assert "authority" in result.message.lower()

def test_audit_log_signature_chain():
    """Verify signature chain integrity."""
    logger = AuditLogger()
    logger.log_system_event("event1", {})
    logger.log_system_event("event2", {})
    is_valid, violations = logger.verify_integrity()
    assert is_valid == True
    assert len(violations) == 0
```

### Property-Based Testing

**Framework**: Hypothesis (Python)

**Configuration**:
- Minimum 100 iterations per property test
- Each test references its design document property
- Tag format: `# Feature: guru-complete-system, Property N: [property text]`

**Example Property Tests**:
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1))
def test_property_9_exact_text_dictation(text):
    """
    Property 9: Exact Text Dictation
    For any text dictation command, the system should type the exact text
    without rephrasing, grammar correction, or interpretation.
    
    Feature: guru-complete-system, Property 9: Exact Text Dictation
    Validates: Requirements 2.5, 14, 21.6
    """
    executor = CommandExecutor()
    machine = create_authority_state_machine()
    machine.grant_authority_for_testing()
    
    # Execute dictation command
    result = executor.write_text("notepad", text)
    
    # Verify exact text was typed
    actual_text = get_notepad_text()
    assert actual_text == text, f"Expected '{text}', got '{actual_text}'"

@given(st.lists(st.text(min_size=1), min_size=2, max_size=10))
def test_property_2_continuous_listening(commands):
    """
    Property 2: Continuous Listening Without Re-Activation
    For any sequence of voice commands after initial wake word activation,
    the system should process all commands without requiring the wake word again.
    
    Feature: guru-complete-system, Property 2: Continuous Listening
    Validates: Requirements 1.2, 22.3
    """
    voice = create_voice_interface()
    processed_commands = []
    
    def callback(cmd):
        processed_commands.append(cmd.text)
    
    voice.set_command_callback(callback)
    
    # Activate with wake word
    voice.process_audio("hey guru")
    assert voice.get_state() == VoiceState.ACTIVE
    
    # Send commands without wake word
    for command in commands:
        voice.process_audio(command)
    
    # Verify all commands were processed
    assert len(processed_commands) == len(commands)
    for i, cmd in enumerate(commands):
        assert processed_commands[i] == cmd

@given(st.integers(min_value=0, max_value=1000))
def test_property_21_inactivity_timeout(inactivity_seconds):
    """
    Property 21: Inactivity Timeout Revokes Authority
    For any 15-minute period of inactivity while in ARMED state,
    the Authority_State_Machine should automatically revoke authority.
    
    Feature: guru-complete-system, Property 21: Inactivity Timeout
    Validates: Requirements 3.4
    """
    machine = create_authority_state_machine()
    machine.grant_authority_for_testing()
    assert machine.get_state() == AuthorityState.ARMED
    
    # Simulate time passage
    machine.simulate_time_passage(inactivity_seconds)
    machine.check_timeout()
    
    # Verify authority state based on inactivity duration
    if inactivity_seconds >= 900:  # 15 minutes
        assert machine.get_state() == AuthorityState.UNARMED
    else:
        assert machine.get_state() == AuthorityState.ARMED

@given(st.lists(st.tuples(st.text(), st.sampled_from(TTSPriority)), min_size=2, max_size=20))
def test_property_33_priority_queue_ordering(tts_requests):
    """
    Property 33: Priority Queue Ordering
    For any set of queued TTS requests with different priorities,
    they should be processed in priority order (CRITICAL > HIGH > NORMAL > LOW).
    
    Feature: guru-complete-system, Property 33: Priority Queue Ordering
    Validates: Requirements 9.4
    """
    tts = get_tts_service()
    processed_order = []
    
    # Mock the speak function to record order
    original_speak = tts._speak_internal
    def mock_speak(text, priority):
        processed_order.append((text, priority))
    tts._speak_internal = mock_speak
    
    # Queue all requests
    for text, priority in tts_requests:
        tts.speak(text, priority)
    
    # Wait for processing
    tts.wait_until_empty()
    
    # Verify priority ordering
    for i in range(len(processed_order) - 1):
        current_priority = processed_order[i][1]
        next_priority = processed_order[i + 1][1]
        assert current_priority.value <= next_priority.value, \
            f"Priority violation: {current_priority} processed before {next_priority}"

@given(st.text(min_size=1))
def test_property_28_signature_chain_integrity(event_data):
    """
    Property 28: Signature Chain Integrity
    For any pair of consecutive audit log entries, the second entry's
    previous_signature should match the first entry's signature.
    
    Feature: guru-complete-system, Property 28: Signature Chain Integrity
    Validates: Requirements 5.5
    """
    logger = AuditLogger()
    
    # Log first event
    logger.log_system_event("event1", {"data": event_data})
    entries = logger.get_all_entries()
    first_entry = entries[-1]
    
    # Log second event
    logger.log_system_event("event2", {"data": event_data})
    entries = logger.get_all_entries()
    second_entry = entries[-1]
    
    # Verify chain integrity
    assert second_entry.previous_signature == first_entry.signature

@given(st.text(min_size=1, max_size=100))
def test_property_41_llm_bypass_for_known_patterns(command_text):
    """
    Property 41: LLM Bypass for Known Patterns
    For any input matching a known action pattern, the system should
    bypass the LLM and route directly to Command_Executor.
    
    Feature: guru-complete-system, Property 41: LLM Bypass
    Validates: Requirements 24.2, 24.3
    """
    pre_filter = IntentPreFilter()
    llm_adapter = MockLLMAdapter()
    
    # Add action verb to make it a known pattern
    action_command = f"open {command_text}"
    
    # Process command
    classification = pre_filter.classify(action_command)
    
    # Verify LLM was not called
    if classification == IntentClassification.ACTION:
        assert llm_adapter.call_count == 0, \
            "LLM was called for a known action pattern"
```

### Integration Testing

**Scope**:
- End-to-end command execution flows
- Component interaction and communication
- Thread safety and concurrency
- Security boundary enforcement
- Failure recovery scenarios

**Example Integration Tests**:
```python
def test_full_voice_command_flow():
    """Test complete flow from voice input to action execution."""
    # Setup
    system = create_guru_system()
    system.start()
    
    # Grant authority
    system.authority_machine.grant_authority_for_testing()
    
    # Simulate voice command
    system.voice_interface.process_audio("hey guru")
    system.voice_interface.process_audio("open notepad")
    
    # Wait for execution
    time.sleep(2)
    
    # Verify notepad is open
    assert is_application_running("notepad.exe")
    
    # Verify audit log
    logs = system.audit_logger.get_recent_entries(1)
    assert logs[0].event_type == "command_execution"
    assert "notepad" in logs[0].data["command"]

def test_security_lockout_flow():
    """Test security lockout after failed authentication attempts."""
    system = create_guru_system()
    system.start()
    
    # Simulate 3 failed authentication attempts
    for i in range(3):
        result = system.authority_machine.grant_authority(
            MockBiometricProvider(success=False)
        )
        assert result == False
    
    # Verify system is locked
    assert system.authority_machine.get_state() == AuthorityState.LOCKED
    
    # Verify workstation lock was triggered
    assert system.intrusion_detector.workstation_locked == True
    
    # Verify audit log
    logs = system.audit_logger.get_recent_entries(4)
    assert logs[-1].event_type == "security_lockout"
    assert logs[-1].severity == AuditSeverity.CRITICAL

def test_component_failure_recovery():
    """Test automatic recovery from component failure."""
    system = create_guru_system()
    system.start()
    
    # Simulate TTS service failure
    system.tts_service.simulate_failure()
    
    # Wait for health check
    time.sleep(35)  # Health check every 30s + processing time
    
    # Verify recovery attempt
    assert system.failure_orchestrator.get_recovery_attempts("tts_service") == 1
    
    # Verify TTS service restarted
    assert system.tts_service.is_running() == True
    
    # Verify audit log
    logs = system.audit_logger.get_recent_entries(2)
    assert any(log.event_type == "component_failure" for log in logs)
    assert any(log.event_type == "component_recovery" for log in logs)
```

### Performance Testing

**Metrics**:
- Application launch time: < 1 second
- Text automation time: < 2 seconds
- Intent pre-filter time: < 10 milliseconds
- TTS synthesis time: < 5 seconds for typical responses
- LLM response time: < 10 seconds (with fallback)
- Health check time: < 5 seconds per component

**Load Testing**:
- 100 consecutive commands without degradation
- 1000 audit log entries without performance impact
- 10,000 conversation history entries with fast search
- 24-hour continuous operation without memory leaks

### Security Testing

**Penetration Testing**:
- Attempt to bypass authority checks
- Attempt to tamper with audit logs
- Attempt to inject malicious commands
- Attempt to escalate privileges
- Attempt to access encrypted data without keys

**Compliance Testing**:
- Verify no sensitive data in logs
- Verify encryption key protection
- Verify workstation lock on security violations
- Verify audit trail completeness
- Verify permission model enforcement

### Test Coverage Goals

- Unit test coverage: > 80%
- Property test coverage: 100% of correctness properties
- Integration test coverage: All critical paths
- Security test coverage: All security boundaries
- Performance test coverage: All performance requirements

