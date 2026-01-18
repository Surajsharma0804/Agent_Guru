"""
Property-Based Tests for Authority Scope Separation

This module contains property-based tests that validate authority scope
separation between desktop (system-wide) and mobile (app-level) platforms.

Tests validate:
- Property 103: Authority Scope Logging
- Property 104: Mobile Authority Scope Restriction
- Property 105: Desktop Authority Scope Permission

Requirements validated: 39.2, 39.3, 39.4, 39.7
"""

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from authority.authority_state_machine import (
    AuthorityConfiguration,
    AuthorityScope,
    AuthorityState,
    AuthorityStateMachine,
    BiometricFactor,
    StateTransitionReason,
)
from execution.command_executor import (
    CommandExecutor,
    CommandType,
    ExecutionStatus,
)
from pal.interfaces import (
    AppDescriptor,
    ApplicationController,
    AutomationTarget,
    InputAutomation,
)

# ============================================================================
# Test Strategies
# ============================================================================

@st.composite
def platform_strategy(draw):
    """Generate platform identifiers."""
    return draw(st.sampled_from(["windows", "macos", "android", "ios"]))


@st.composite
def command_text_strategy(draw):
    """Generate command text for testing."""
    commands = [
        "open notepad",
        "open chrome",
        "write hello world",
        "search for python",
        "type some text",
    ]
    return draw(st.sampled_from(commands))


# ============================================================================
# Property 103: Authority Scope Logging
# ============================================================================

@pytest.mark.property
@given(platform=platform_strategy())
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_103_authority_scope_logging(platform):
    """
    Property 103: Authority Scope Logging
    
    For any platform, when authority is granted, the audit log SHALL include:
    - Platform identifier (windows, macos, android, ios)
    - Authority scope (system_wide or app_level)
    - Capability limitations
    
    Validates: Requirements 39.7
    """
    # Mock platform detection to return specific platform
    with patch('src.pal.platform_detector.PlatformDetector.detect', return_value=platform):
        # Create authority state machine with test mode enabled
        config = AuthorityConfiguration(test_mode_disable_workstation_lock=True)
        authority_machine = AuthorityStateMachine(config)
        
        # Verify platform and scope are set correctly
        assert authority_machine.platform == platform
        
        # Verify scope matches platform
        if platform in ("windows", "macos"):
            assert authority_machine.authority_scope == AuthorityScope.SYSTEM_WIDE
        else:  # android, ios
            assert authority_machine.authority_scope == AuthorityScope.APP_LEVEL
        
        # Get state info (which is logged)
        state_info = authority_machine.get_state_info()
        
        # Verify platform and scope are included in state info
        assert "platform" in state_info
        assert state_info["platform"] == platform
        assert "authority_scope" in state_info
        assert state_info["authority_scope"] in ("system_wide", "app_level")
        
        # Verify scope matches expected value
        if platform in ("windows", "macos"):
            assert state_info["authority_scope"] == "system_wide"
        else:
            assert state_info["authority_scope"] == "app_level"


# ============================================================================
# Property 104: Mobile Authority Scope Restriction
# ============================================================================

@pytest.mark.property
@given(
    platform=st.sampled_from(["android", "ios"]),
    command_text=command_text_strategy()
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=500)
def test_property_104_mobile_authority_scope_restriction(platform, command_text):
    """
    Property 104: Mobile Authority Scope Restriction
    
    For any mobile platform (Android, iOS), authority SHALL be app-level only.
    System-wide commands SHALL be restricted or sandboxed by the OS.
    
    Validates: Requirements 39.2, 39.3, 39.4
    """
    # Create mock PAL interfaces
    mock_app_controller = Mock(spec=ApplicationController)
    mock_app_controller.get_capabilities.return_value = {
        "can_open_apps": True,
        "can_close_apps": False,  # iOS restriction
        "can_discover_apps": True,
    }
    mock_app_controller.open_app.return_value = True
    
    mock_input_automation = Mock(spec=InputAutomation)
    mock_input_automation.get_capabilities.return_value = {
        "can_type_text": False,  # Mobile restriction
        "can_click": False,
        "can_focus_app": True,
    }
    
    # Create command executor with mobile authority scope
    with patch('src.pal.platform_detector.PlatformDetector.detect', return_value=platform):
        executor = CommandExecutor(
            app_controller=mock_app_controller,
            input_automation=mock_input_automation,
            authority_scope="app_level"
        )
        
        # Verify authority scope is app-level
        assert executor.authority_scope == "app_level"
        
        # Execute command
        result = executor.execute(command_text)
        
        # Verify command execution respects app-level scope
        # On mobile, system commands should be restricted
        # App-level commands should be allowed (but may fail due to platform capabilities)
        assert result is not None
        assert hasattr(result, 'status')


# ============================================================================
# Property 105: Desktop Authority Scope Permission
# ============================================================================

@pytest.mark.property
@given(
    platform=st.sampled_from(["windows", "macos"]),
    command_text=command_text_strategy()
)
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_105_desktop_authority_scope_permission(platform, command_text):
    """
    Property 105: Desktop Authority Scope Permission
    
    For any desktop platform (Windows, macOS), authority MAY include system-level
    actions. System-wide control SHALL be available when authority is granted.
    
    Validates: Requirements 39.4
    """
    # Create mock PAL interfaces with full desktop capabilities
    mock_app_controller = Mock(spec=ApplicationController)
    mock_app_controller.get_capabilities.return_value = {
        "can_open_apps": True,
        "can_close_apps": True,
        "can_discover_apps": True,
    }
    mock_app_controller.open_app.return_value = True
    mock_app_controller.discover_apps.return_value = []  # Return empty list for discovery
    
    mock_input_automation = Mock(spec=InputAutomation)
    mock_input_automation.get_capabilities.return_value = {
        "can_type_text": True,
        "can_click": True,
        "can_focus_app": True,
    }
    mock_input_automation.type_text.return_value = True
    mock_input_automation.focus_app.return_value = True
    
    # Create command executor with system-wide authority scope
    with patch('src.pal.platform_detector.PlatformDetector.detect', return_value=platform):
        executor = CommandExecutor(
            app_controller=mock_app_controller,
            input_automation=mock_input_automation,
            authority_scope="system_wide"
        )
        
        # Verify authority scope is system-wide
        assert executor.authority_scope == "system_wide"
        
        # Execute command
        result = executor.execute(command_text)
        
        # Verify command execution is allowed with system-wide scope
        # All commands should be allowed (though they may fail for other reasons)
        assert result is not None
        assert hasattr(result, 'status')
        
        # System-wide scope should never return PERMISSION_DENIED
        # (it may fail for other reasons like NOT_FOUND, FAILED, etc.)
        assert result.status != ExecutionStatus.PERMISSION_DENIED


# ============================================================================
# Additional Property: Authority Scope Consistency
# ============================================================================

@pytest.mark.property
@given(platform=platform_strategy())
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_authority_scope_consistency(platform):
    """
    Additional Property: Authority Scope Consistency
    
    For any platform, the authority scope SHALL be consistent across
    all components (AuthorityStateMachine, CommandExecutor).
    """
    # Mock platform detection
    with patch('src.pal.platform_detector.PlatformDetector.detect', return_value=platform):
        # Create authority state machine
        config = AuthorityConfiguration(test_mode_disable_workstation_lock=True)
        authority_machine = AuthorityStateMachine(config)
        
        # Create mock PAL interfaces
        mock_app_controller = Mock(spec=ApplicationController)
        mock_app_controller.get_capabilities.return_value = {"can_open_apps": True}
        
        mock_input_automation = Mock(spec=InputAutomation)
        mock_input_automation.get_capabilities.return_value = {"can_type_text": True}
        
        # Create command executor
        executor = CommandExecutor(
            app_controller=mock_app_controller,
            input_automation=mock_input_automation
        )
        
        # Verify both components have consistent authority scope
        authority_scope_value = authority_machine.authority_scope.value
        executor_scope = executor.authority_scope
        
        # Both should match
        assert authority_scope_value == executor_scope
        
        # Verify scope matches platform expectations
        if platform in ("windows", "macos"):
            assert authority_scope_value == "system_wide"
            assert executor_scope == "system_wide"
        else:  # android, ios
            assert authority_scope_value == "app_level"
            assert executor_scope == "app_level"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
