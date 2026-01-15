"""
Pytest configuration and shared fixtures for GURU test suite.

This module provides:
- Mock PAL interface implementations for testing
- Shared test fixtures
- Hypothesis configuration profiles
- Test utilities and helpers
"""

import pytest
from hypothesis import settings, Verbosity
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# Import PAL interfaces
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pal.interfaces import (
    ApplicationController,
    InputAutomation,
    SpeechOutput,
    SpeechInput,
    BiometricAuthenticator,
    SecurityEnforcer,
    AppDescriptor,
    AutomationTarget,
    TTSPriority,
    Transcription,
    AuthResult,
    AuthResultStatus
)


# Hypothesis settings for property-based tests
# Minimum 100 iterations per property as per requirements
settings.register_profile("default", max_examples=100, verbosity=Verbosity.normal)
settings.register_profile("ci", max_examples=200, verbosity=Verbosity.verbose)
settings.register_profile("dev", max_examples=50, verbosity=Verbosity.normal)
settings.load_profile("default")


# Mock PAL Implementations for Testing

class MockApplicationController(ApplicationController):
    """Mock implementation of ApplicationController for testing."""
    
    def __init__(self, platform: str = "mock"):
        self.platform = platform
        self.opened_apps: List[str] = []
        self.closed_apps: List[str] = []
        self.running_apps: Dict[str, bool] = {}
        
    def open_app(self, app_id: str) -> bool:
        self.opened_apps.append(app_id)
        self.running_apps[app_id] = True
        return True
    
    def close_app(self, app_id: str) -> bool:
        self.closed_apps.append(app_id)
        self.running_apps[app_id] = False
        return True
    
    def is_running(self, app_id: str) -> bool:
        return self.running_apps.get(app_id, False)
    
    def discover_apps(self) -> List[AppDescriptor]:
        return [
            AppDescriptor(
                app_id="notepad",
                display_name="Notepad",
                executable_path="/path/to/notepad.exe",
                is_running=False,
                platform=self.platform
            ),
            AppDescriptor(
                app_id="chrome",
                display_name="Google Chrome",
                executable_path="/path/to/chrome.exe",
                is_running=False,
                platform=self.platform
            )
        ]
    
    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "can_open_apps": True,
            "can_close_apps": True,
            "can_discover_apps": True,
            "full_control": self.platform in ["windows", "macos"]
        }


class MockInputAutomation(InputAutomation):
    """Mock implementation of InputAutomation for testing."""
    
    def __init__(self, platform: str = "mock"):
        self.platform = platform
        self.typed_text: List[str] = []
        self.clicked_targets: List[AutomationTarget] = []
        self.focused_apps: List[str] = []
        
    def type_text(self, text: str, target: Optional[AutomationTarget] = None) -> bool:
        self.typed_text.append(text)
        return True
    
    def click(self, target: AutomationTarget) -> bool:
        self.clicked_targets.append(target)
        return True
    
    def focus_app(self, app_id: str) -> bool:
        self.focused_apps.append(app_id)
        return True
    
    def get_capabilities(self) -> Dict[str, bool]:
        capabilities = {
            "can_type_text": True,
            "can_click": True,
            "can_focus_app": True,
            "full_automation": False
        }
        
        if self.platform == "windows":
            capabilities["full_automation"] = True
        elif self.platform == "macos":
            capabilities["full_automation"] = True
            capabilities["requires_accessibility_permission"] = True
        elif self.platform == "android":
            capabilities["full_automation"] = False
            capabilities["requires_accessibility_service"] = True
        elif self.platform == "ios":
            capabilities["can_type_text"] = False
            capabilities["can_click"] = False
            capabilities["full_automation"] = False
            
        return capabilities


class MockSpeechOutput(SpeechOutput):
    """Mock implementation of SpeechOutput for testing."""
    
    def __init__(self, platform: str = "mock"):
        self.platform = platform
        self.speech_queue: List[tuple] = []
        self.speaking = False
        self.volume = 100
        self.rate = 0
        
    def speak(self, text: str, priority: TTSPriority = TTSPriority.NORMAL,
             interrupt: bool = False) -> None:
        if interrupt:
            self.speech_queue.clear()
        self.speech_queue.append((text, priority, interrupt))
        
    def stop(self) -> None:
        self.speech_queue.clear()
        self.speaking = False
        
    def is_speaking(self) -> bool:
        return self.speaking
    
    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, volume))
        
    def set_rate(self, rate: int) -> None:
        self.rate = max(-10, min(10, rate))
    
    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "can_speak": True,
            "supports_priority_queue": True,
            "supports_volume_control": True,
            "supports_rate_control": True
        }


class MockSpeechInput(SpeechInput):
    """Mock implementation of SpeechInput for testing."""
    
    def __init__(self, platform: str = "mock"):
        self.platform = platform
        self.listening = False
        self.energy_threshold = 300.0
        
    def start_listening(self) -> None:
        self.listening = True
        
    def stop_listening(self) -> None:
        self.listening = False
        
    def transcribe(self, audio_data: bytes) -> Transcription:
        return Transcription(
            text="mock transcription",
            confidence=0.95,
            language="en",
            timestamp=datetime.now(),
            audio_duration=1.5
        )
    
    def calibrate_microphone(self) -> float:
        self.energy_threshold = 300.0
        return self.energy_threshold
    
    def get_capabilities(self) -> Dict[str, bool]:
        capabilities = {
            "can_transcribe": True,
            "supports_wake_word": True,
            "local_processing": True
        }
        
        if self.platform == "ios":
            capabilities["local_processing"] = False
            capabilities["system_stt_required"] = True
            
        return capabilities


class MockBiometricAuthenticator(BiometricAuthenticator):
    """Mock implementation of BiometricAuthenticator for testing."""
    
    def __init__(self, platform: str = "mock", should_succeed: bool = True):
        self.platform = platform
        self.should_succeed = should_succeed
        self.auth_attempts: List[AuthResult] = []
        
    def authenticate(self, reason: str) -> AuthResult:
        status = AuthResultStatus.SUCCESS if self.should_succeed else AuthResultStatus.FAILURE
        result = AuthResult(
            status=status,
            message=f"Authentication {'succeeded' if self.should_succeed else 'failed'}",
            platform=self.platform,
            timestamp=datetime.now()
        )
        self.auth_attempts.append(result)
        return result
    
    def is_available(self) -> bool:
        return True
    
    def get_available_factors(self) -> List[str]:
        if self.platform == "windows":
            return ["fingerprint", "face", "iris"]
        elif self.platform == "macos":
            return ["fingerprint", "face"]
        elif self.platform == "android":
            return ["fingerprint", "face"]
        elif self.platform == "ios":
            return ["face", "fingerprint"]
        return ["fingerprint"]
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get platform-specific biometric capabilities."""
        return {
            "can_authenticate": True,
            "supports_fingerprint": "fingerprint" in self.get_available_factors(),
            "supports_face": "face" in self.get_available_factors(),
            "supports_iris": "iris" in self.get_available_factors()
        }


class MockSecurityEnforcer(SecurityEnforcer):
    """Mock implementation of SecurityEnforcer for testing."""
    
    def __init__(self, platform: str = "mock"):
        self.platform = platform
        self.lock_attempts: List[str] = []
        
    def lock_session(self, reason: str) -> bool:
        self.lock_attempts.append(reason)
        return True
    
    def get_lock_scope(self) -> str:
        if self.platform == "windows":
            return "workstation"
        elif self.platform == "macos":
            return "screen"
        elif self.platform == "android":
            return "app+screen"
        elif self.platform == "ios":
            return "app"
        return "unknown"
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get platform-specific security enforcement capabilities."""
        return {
            "can_lock_session": True,
            "lock_scope": self.get_lock_scope(),
            "system_wide_lock": self.platform in ["windows", "macos"]
        }


# Pytest Fixtures

@pytest.fixture
def mock_app_controller():
    """Provide a mock ApplicationController for testing."""
    return MockApplicationController()


@pytest.fixture
def mock_input_automation():
    """Provide a mock InputAutomation for testing."""
    return MockInputAutomation()


@pytest.fixture
def mock_speech_output():
    """Provide a mock SpeechOutput for testing."""
    return MockSpeechOutput()


@pytest.fixture
def mock_speech_input():
    """Provide a mock SpeechInput for testing."""
    return MockSpeechInput()


@pytest.fixture
def mock_biometric_auth():
    """Provide a mock BiometricAuthenticator for testing."""
    return MockBiometricAuthenticator()


@pytest.fixture
def mock_security_enforcer():
    """Provide a mock SecurityEnforcer for testing."""
    return MockSecurityEnforcer()


@pytest.fixture
def all_mock_backends():
    """Provide all mock PAL backends for comprehensive testing."""
    return {
        "app_controller": MockApplicationController(),
        "input_automation": MockInputAutomation(),
        "speech_output": MockSpeechOutput(),
        "speech_input": MockSpeechInput(),
        "biometric_auth": MockBiometricAuthenticator(),
        "security_enforcer": MockSecurityEnforcer()
    }


@pytest.fixture(params=["windows", "macos", "android", "ios"])
def platform_name(request):
    """Parametrize tests across all supported platforms."""
    return request.param


@pytest.fixture
def platform_backends(platform_name):
    """Provide platform-specific mock backends."""
    return {
        "app_controller": MockApplicationController(platform_name),
        "input_automation": MockInputAutomation(platform_name),
        "speech_output": MockSpeechOutput(platform_name),
        "speech_input": MockSpeechInput(platform_name),
        "biometric_auth": MockBiometricAuthenticator(platform_name),
        "security_enforcer": MockSecurityEnforcer(platform_name)
    }
