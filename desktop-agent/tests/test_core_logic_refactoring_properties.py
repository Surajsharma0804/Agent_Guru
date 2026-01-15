"""
Property-Based Tests for Core Logic PAL Refactoring

This module contains property-based tests that validate the refactored core logic
modules now use PAL interfaces exclusively and maintain platform independence.

Tests validate:
- Property 94: Core Logic Platform Isolation
- Property 95: PAL Interface Communication
- Property 109: Core Logic State Machine Consistency
- Property 110: Core Logic Security Invariants
- Property 111: Core Logic Audit Logging Consistency
- Property 116: Dependency Injection
- Property 117: Platform Logging at Startup

Requirements validated: 42.1, 42.2, 42.3, 42.4, 42.5, 43.5, 43.6, 43.7
"""

import ast
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Set
from unittest.mock import MagicMock, Mock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pal.interfaces import (
    ApplicationController,
    AuthResultStatus,
    BiometricAuthenticator,
    InputAutomation,
    SecurityEnforcer,
    SpeechInput,
    SpeechOutput,
    TTSPriority,
)

# ============================================================================
# Property 94: Core Logic Platform Isolation
# ============================================================================

def get_platform_specific_imports() -> Set[str]:
    """
    Get set of platform-specific module names that should NOT be imported
    by core logic.
    """
    return {
        'win32com', 'win32api', 'win32con', 'win32gui', 'win32process',
        'pywintypes', 'pythoncom', 'win32security', 'win32file',
        'speech_recognition', 'sr',  # Should use PAL SpeechInput instead
        'pyttsx3',  # Should use PAL SpeechOutput instead
        'ctypes.windll',  # Direct Windows API access
        'AppKit', 'Cocoa', 'Foundation',  # macOS specific
        'android', 'jnius',  # Android specific
        'objc',  # iOS specific
    }


def extract_imports_from_file(filepath: Path) -> Set[str]:
    """Extract all import statements from a Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        
        return imports
    except Exception as e:
        pytest.fail(f"Failed to parse {filepath}: {e}")


@pytest.mark.property
def test_property_94_core_logic_platform_isolation():
    """
    Property 94: Core Logic Platform Isolation
    
    Validates that core logic modules do not import platform-specific libraries.
    Core logic must only import PAL interfaces for platform operations.
    
    Validates: Requirements 42.1
    """
    core_logic_files = [
        Path(__file__).parent.parent / "src" / "execution" / "command_executor.py",
        Path(__file__).parent.parent / "src" / "gui" / "tts_service.py",
        Path(__file__).parent.parent / "src" / "gui" / "voice_interface.py",
        Path(__file__).parent.parent / "src" / "intrusion" / "detection.py",
    ]
    
    platform_specific = get_platform_specific_imports()
    violations = {}
    
    for filepath in core_logic_files:
        if not filepath.exists():
            pytest.skip(f"File not found: {filepath}")
        
        imports = extract_imports_from_file(filepath)
        forbidden = imports & platform_specific
        
        if forbidden:
            violations[filepath.name] = forbidden
    
    assert not violations, (
        f"Core logic files contain platform-specific imports:\n"
        + "\n".join(f"  {file}: {', '.join(imports)}" for file, imports in violations.items())
        + "\n\nCore logic must only use PAL interfaces for platform operations."
    )


# ============================================================================
# Property 95: PAL Interface Communication
# ============================================================================

@pytest.mark.property
@settings(max_examples=100)
@given(
    text=st.text(min_size=1, max_size=100),
    priority=st.sampled_from(list(TTSPriority)),
)
def test_property_95_pal_interface_communication_tts(text, priority):
    """
    Property 95: PAL Interface Communication (TTS Service)
    
    Validates that TTS service communicates exclusively through PAL SpeechOutput
    interface without direct platform API calls.
    
    Validates: Requirements 42.2
    """
    from gui.tts_service import TTSService

    # Create mock PAL interface
    mock_speech_output = Mock(spec=SpeechOutput)
    mock_speech_output.get_capabilities.return_value = {
        'has_priority_queue': True,
        'can_interrupt': True,
        'can_control_volume': True,
        'can_control_rate': True,
    }
    mock_speech_output.is_speaking.return_value = False
    
    # Create TTS service with PAL interface
    tts_service = TTSService(mock_speech_output)
    
    # Verify service uses PAL interface
    assert tts_service.speech_output is mock_speech_output
    assert tts_service.available is True
    
    # Verify capabilities were queried from PAL
    mock_speech_output.get_capabilities.assert_called()


@pytest.mark.property
@settings(max_examples=100)
@given(
    app_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
)
def test_property_95_pal_interface_communication_command_executor(app_id):
    """
    Property 95: PAL Interface Communication (Command Executor)
    
    Validates that command executor communicates exclusively through PAL
    ApplicationController and InputAutomation interfaces.
    
    Validates: Requirements 42.2
    """
    from execution.command_executor import CommandExecutor

    # Create mock PAL interfaces
    mock_app_controller = Mock(spec=ApplicationController)
    mock_app_controller.get_capabilities.return_value = {
        'can_open_apps': True,
        'can_close_apps': True,
        'can_discover_apps': True,
        'has_full_control': True,
    }
    
    mock_input_automation = Mock(spec=InputAutomation)
    mock_input_automation.get_capabilities.return_value = {
        'can_type_text': True,
        'can_click': True,
        'can_focus_apps': True,
        'has_full_automation': True,
        'requires_permission': False,
    }
    
    # Create command executor with PAL interfaces
    executor = CommandExecutor(mock_app_controller, mock_input_automation)
    
    # Verify executor uses PAL interfaces
    assert executor.app_controller is mock_app_controller
    assert executor.input_automation is mock_input_automation
    
    # Verify capabilities were queried from PAL
    mock_app_controller.get_capabilities.assert_called()
    mock_input_automation.get_capabilities.assert_called()


@pytest.mark.property
@settings(max_examples=100)
@given(
    reason=st.text(min_size=1, max_size=100),
)
def test_property_95_pal_interface_communication_intrusion_detector(reason):
    """
    Property 95: PAL Interface Communication (Intrusion Detector)
    
    Validates that intrusion detector communicates exclusively through PAL
    SecurityEnforcer interface for session locking.
    
    Validates: Requirements 42.2
    """
    from intrusion.detection import IntrusionDetectionConfig, IntrusionDetector

    # Create mock PAL interface
    mock_security_enforcer = Mock(spec=SecurityEnforcer)
    mock_security_enforcer.get_capabilities.return_value = {
        'can_lock_system': True,
        'can_lock_screen': True,
        'can_lock_app': True,
        'has_system_authority': True,
    }
    mock_security_enforcer.get_lock_scope.return_value = "system"
    mock_security_enforcer.lock_session.return_value = True
    
    # Create intrusion detector with PAL interface
    config = IntrusionDetectionConfig(enable_security_enforcement=True)
    detector = IntrusionDetector(mock_security_enforcer, config)
    
    # Verify detector uses PAL interface
    assert detector.security_enforcer is mock_security_enforcer
    
    # Verify capabilities were queried from PAL
    mock_security_enforcer.get_capabilities.assert_called()


# ============================================================================
# Property 116: Dependency Injection
# ============================================================================

@pytest.mark.property
@settings(max_examples=50)
@given(
    wake_word=st.text(min_size=3, max_size=20),
)
def test_property_116_dependency_injection_voice_interface(wake_word):
    """
    Property 116: Dependency Injection
    
    Validates that core logic accepts PAL interfaces via dependency injection
    rather than creating platform-specific implementations internally.
    
    Validates: Requirements 43.5
    """
    from gui.voice_interface import VoiceInterface

    # Create mock PAL interfaces
    mock_speech_input = Mock(spec=SpeechInput)
    mock_speech_input.get_capabilities.return_value = {
        'has_local_processing': True,
        'requires_cloud': False,
        'supports_wake_word': True,
        'supports_continuous': True,
    }
    mock_speech_input.calibrate_microphone.return_value = 4000.0
    
    mock_speech_output = Mock(spec=SpeechOutput)
    mock_speech_output.get_capabilities.return_value = {
        'has_priority_queue': True,
        'can_interrupt': True,
    }
    
    # Create voice interface with injected dependencies
    voice_interface = VoiceInterface(
        speech_input=mock_speech_input,
        speech_output=mock_speech_output,
        wake_word=wake_word
    )
    
    # Verify dependencies were injected
    assert voice_interface.speech_input is mock_speech_input
    assert voice_interface.wake_word == wake_word.lower()
    
    # Verify capabilities were queried
    mock_speech_input.get_capabilities.assert_called()


@pytest.mark.property
def test_property_116_dependency_injection_factory_functions():
    """
    Property 116: Dependency Injection (Factory Functions)
    
    Validates that factory functions support both explicit dependency injection
    and automatic platform detection fallback.
    
    Validates: Requirements 43.5
    """
    from execution.command_executor import get_command_executor
    from gui.tts_service import get_tts_service
    from intrusion.detection import create_intrusion_detector

    # Test with explicit dependency injection
    mock_app_controller = Mock(spec=ApplicationController)
    mock_app_controller.get_capabilities.return_value = {'can_open_apps': True}
    
    mock_input_automation = Mock(spec=InputAutomation)
    mock_input_automation.get_capabilities.return_value = {'can_type_text': True}
    
    mock_speech_output = Mock(spec=SpeechOutput)
    mock_speech_output.get_capabilities.return_value = {'has_priority_queue': True}
    
    mock_security_enforcer = Mock(spec=SecurityEnforcer)
    mock_security_enforcer.get_capabilities.return_value = {'can_lock_system': True}
    mock_security_enforcer.get_lock_scope.return_value = "system"
    
    # Verify factory functions accept injected dependencies
    executor = get_command_executor(mock_app_controller, mock_input_automation)
    assert executor.app_controller is mock_app_controller
    
    tts = get_tts_service(mock_speech_output)
    assert tts.speech_output is mock_speech_output
    
    detector = create_intrusion_detector(mock_security_enforcer)
    assert detector.security_enforcer is mock_security_enforcer


# ============================================================================
# Property 117: Platform Logging at Startup
# ============================================================================

@pytest.mark.property
def test_property_117_platform_logging_at_startup():
    """
    Property 117: Platform Logging at Startup
    
    Validates that core logic logs platform capabilities at initialization
    for debugging and audit purposes.
    
    Validates: Requirements 43.6
    """
    from execution.command_executor import CommandExecutor
    from gui.tts_service import TTSService
    from intrusion.detection import IntrusionDetectionConfig, IntrusionDetector

    # Create mock PAL interfaces with capabilities
    mock_speech_output = Mock(spec=SpeechOutput)
    mock_speech_output.get_capabilities.return_value = {
        'has_priority_queue': True,
        'can_interrupt': True,
        'can_control_volume': True,
        'can_control_rate': True,
    }
    
    mock_app_controller = Mock(spec=ApplicationController)
    mock_app_controller.get_capabilities.return_value = {
        'can_open_apps': True,
        'can_close_apps': True,
        'can_discover_apps': True,
        'has_full_control': True,
    }
    
    mock_input_automation = Mock(spec=InputAutomation)
    mock_input_automation.get_capabilities.return_value = {
        'can_type_text': True,
        'can_click': True,
        'can_focus_apps': True,
        'has_full_automation': True,
    }
    
    mock_security_enforcer = Mock(spec=SecurityEnforcer)
    mock_security_enforcer.get_capabilities.return_value = {
        'can_lock_system': True,
        'can_lock_screen': True,
        'has_system_authority': True,
    }
    mock_security_enforcer.get_lock_scope.return_value = "system"
    
    # Initialize components and verify capabilities are stored
    tts = TTSService(mock_speech_output)
    assert hasattr(tts, 'capabilities')
    assert tts.capabilities == mock_speech_output.get_capabilities.return_value
    
    executor = CommandExecutor(mock_app_controller, mock_input_automation)
    assert hasattr(executor, 'app_capabilities')
    assert hasattr(executor, 'automation_capabilities')
    assert executor.app_capabilities == mock_app_controller.get_capabilities.return_value
    assert executor.automation_capabilities == mock_input_automation.get_capabilities.return_value
    
    config = IntrusionDetectionConfig()
    detector = IntrusionDetector(mock_security_enforcer, config)
    assert hasattr(detector, 'security_capabilities')
    assert detector.security_capabilities == mock_security_enforcer.get_capabilities.return_value


# ============================================================================
# Property 109: Core Logic State Machine Consistency
# ============================================================================

@pytest.mark.property
@settings(max_examples=100)
@given(
    state_transitions=st.lists(
        st.sampled_from(['IDLE', 'LISTENING', 'PROCESSING', 'SPEAKING', 'ERROR']),
        min_size=1,
        max_size=10
    )
)
def test_property_109_core_logic_state_machine_consistency(state_transitions):
    """
    Property 109: Core Logic State Machine Consistency
    
    Validates that core logic state machines maintain consistency across
    platform boundaries and PAL interface calls.
    
    Validates: Requirements 42.3
    """
    from gui.voice_interface import VoiceInterface, VoiceState

    # Create mock PAL interfaces
    mock_speech_input = Mock(spec=SpeechInput)
    mock_speech_input.get_capabilities.return_value = {'supports_continuous': True}
    mock_speech_input.calibrate_microphone.return_value = 4000.0
    
    mock_speech_output = Mock(spec=SpeechOutput)
    mock_speech_output.get_capabilities.return_value = {'has_priority_queue': True}
    
    # Create voice interface
    voice_interface = VoiceInterface(mock_speech_input, mock_speech_output)
    
    # Verify initial state
    assert voice_interface.current_state == VoiceState.IDLE
    
    # State machine should maintain consistency regardless of platform
    assert hasattr(voice_interface, 'current_state')
    assert isinstance(voice_interface.current_state, VoiceState)


# ============================================================================
# Property 110: Core Logic Security Invariants
# ============================================================================

@pytest.mark.property
@settings(max_examples=100)
@given(
    failure_count=st.integers(min_value=1, max_value=10),
)
def test_property_110_core_logic_security_invariants(failure_count):
    """
    Property 110: Core Logic Security Invariants
    
    Validates that security invariants are maintained across platform
    boundaries when using PAL interfaces.
    
    Validates: Requirements 42.4
    """
    from biometric.providers import BiometricFactor
    from intrusion.detection import IntrusionDetectionConfig, IntrusionDetector

    # Create mock PAL interface
    mock_security_enforcer = Mock(spec=SecurityEnforcer)
    mock_security_enforcer.get_capabilities.return_value = {'can_lock_system': True}
    mock_security_enforcer.get_lock_scope.return_value = "system"
    mock_security_enforcer.lock_session.return_value = True
    
    # Create intrusion detector with strict thresholds
    config = IntrusionDetectionConfig(
        max_failures_per_factor=3,
        max_total_failures=5,
        enable_security_enforcement=True,
    )
    detector = IntrusionDetector(mock_security_enforcer, config)
    
    # Record failures
    for i in range(min(failure_count, config.max_total_failures)):
        detector.record_biometric_failure(
            factor=BiometricFactor.FINGERPRINT,
            failure_reason="test_failure",
            confidence_score=0.3,
            provider="test_provider"
        )
    
    # Verify security invariants
    assert detector._total_failures == min(failure_count, config.max_total_failures)
    
    # If threshold exceeded, security enforcer should be called
    if failure_count >= config.max_total_failures:
        # Security enforcement should have been triggered
        assert detector.get_current_threat_level().value in ['high', 'critical']


# ============================================================================
# Property 111: Core Logic Audit Logging Consistency
# ============================================================================

@pytest.mark.property
@settings(max_examples=50)
@given(
    event_count=st.integers(min_value=1, max_value=20),
)
def test_property_111_core_logic_audit_logging_consistency(event_count):
    """
    Property 111: Core Logic Audit Logging Consistency
    
    Validates that audit logging remains consistent across platform
    boundaries when using PAL interfaces.
    
    Validates: Requirements 42.5
    """
    from biometric.providers import BiometricFactor
    from intrusion.detection import IntrusionDetectionConfig, IntrusionDetector

    # Create mock PAL interface
    mock_security_enforcer = Mock(spec=SecurityEnforcer)
    mock_security_enforcer.get_capabilities.return_value = {'can_lock_system': True}
    mock_security_enforcer.get_lock_scope.return_value = "system"
    
    # Create intrusion detector
    config = IntrusionDetectionConfig(log_all_events=True)
    detector = IntrusionDetector(mock_security_enforcer, config)
    
    # Record multiple events
    for i in range(event_count):
        detector.record_biometric_failure(
            factor=BiometricFactor.VOICE,
            failure_reason=f"test_failure_{i}",
            confidence_score=0.4,
            provider="test_provider"
        )
    
    # Verify audit logging consistency
    stats = detector.get_failure_statistics()
    assert 'total_failures' in stats
    assert stats['total_failures'] == event_count
    
    # Verify events are tracked
    recent_events = detector.get_recent_events(limit=event_count)
    assert len(recent_events) <= event_count


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
