"""
Property-Based Tests for iOS Backend

Feature: guru-complete-system
Task: 6.3 Write property tests for iOS backend

This module contains property-based tests that validate universal correctness
properties of the iOS platform backend. Each property is tested with a
minimum of 100 iterations to ensure comprehensive coverage.

Properties tested:
- Property 104: Mobile Authority Scope Restriction
- Property 106: Security Enforcer Lock Scope Declaration

All tests validate Requirements: 39.2, 40.5
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from typing import List, Dict
from datetime import datetime
import sys
import os

# Import PAL interfaces
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pal.interfaces import (
    SecurityEnforcer,
    PlatformCapabilityError
)

# Import iOS backend implementations
from pal.backends.ios import (
    iOSSecurityEnforcer
)


# ============================================================================
# Property 104: Mobile Authority Scope Restriction
# ============================================================================
# Feature: guru-complete-system, Property 104: Mobile Authority Scope Restriction
# Validates: Requirements 39.2, 39.3

@pytest.mark.properties
class TestProperty104MobileAuthorityScopeRestrictionIOS:
    """
    Property 104: Mobile Authority Scope Restriction (iOS)
    
    For any authority grant on mobile platforms (Android/iOS), the authority
    scope should be app-level only, never system-wide.
    
    iOS has the most restricted authority scope - app-level only with no
    system-wide control capabilities.
    
    Validates: Requirements 39.2, 39.3
    """
    
    @pytest.mark.properties
    @settings(max_examples=100)
    @given(st.just("ios"))
    def test_ios_authority_scope_is_app_level_only(self, platform):
        """
        Test that iOS authority scope is always app-level, never system-wide.
        
        This property ensures that iOS does not claim system-wide authority,
        which would be a security illusion.
        """
        enforcer = iOSSecurityEnforcer()
        capabilities = enforcer.get_capabilities()
        
        # Must return a dictionary
        assert isinstance(capabilities, dict), \
            f"get_capabilities should return dict, got {type(capabilities)}"
        
        # CRITICAL: iOS should NOT have system authority
        assert capabilities.get('has_system_authority', True) == False, \
            "iOS should NOT have system-wide authority (app-level only)"
        
        # CRITICAL: iOS should NOT be able to lock system
        assert capabilities.get('can_lock_system', True) == False, \
            "iOS cannot lock system (iOS security restriction)"
        
        # CRITICAL: iOS should NOT be able to lock screen
        assert capabilities.get('can_lock_screen', True) == False, \
            "iOS cannot lock screen (iOS security restriction)"
        
        # iOS should only be able to lock app
        assert capabilities.get('can_lock_app', False) == True, \
            "iOS should be able to lock GURU app itself"
        
        # Verify lock scope is app-level
        assert capabilities.get('lock_scope', 'system') == 'app', \
            "iOS lock scope should be 'app', not 'system' or 'screen'"
    
    @pytest.mark.properties
    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_ios_lock_session_only_locks_app(self, reason):
        """
        Test that iOS lock_session only locks the app, not the system.
        
        This property ensures that iOS security enforcement is honest about
        its limitations and does not create a security illusion.
        """
        enforcer = iOSSecurityEnforcer()
        
        # Lock session should succeed (locks app)
        result = enforcer.lock_session(reason)
        assert result == True, \
            f"lock_session should succeed (locks app), got {result}"
        
        # Verify lock scope is app-level
        lock_scope = enforcer.get_lock_scope()
        assert lock_scope == "app", \
            f"iOS lock scope should be 'app', got '{lock_scope}'"
        
        # Verify app is locked
        assert enforcer.is_app_locked() == True, \
            "App should be locked after lock_session"
    
    @pytest.mark.properties
    @settings(max_examples=100)
    @given(st.just("ios"))
    def test_ios_declares_severe_platform_limitations(self, platform):
        """
        Test that iOS honestly declares its severe platform limitations.
        
        This property ensures that iOS does not hide its restrictions and
        provides accurate capability information to users.
        """
        enforcer = iOSSecurityEnforcer()
        capabilities = enforcer.get_capabilities()
        
        # iOS should declare severe limitations
        assert capabilities.get('platform_limitations', 'none') == 'severe', \
            "iOS should declare 'severe' platform limitations"
        
        # Verify all system-level capabilities are False
        system_capabilities = [
            'can_lock_system',
            'can_lock_screen',
            'has_system_authority'
        ]
        
        for cap in system_capabilities:
            assert capabilities.get(cap, True) == False, \
                f"iOS should not have {cap} capability"


# ============================================================================
# Property 106: Security Enforcer Lock Scope Declaration
# ============================================================================
# Feature: guru-complete-system, Property 106: Security Enforcer Lock Scope Declaration
# Validates: Requirements 40.2, 40.3, 40.4, 40.5

@pytest.mark.properties
class TestProperty106SecurityEnforcerLockScopeDeclarationIOS:
    """
    Property 106: Security Enforcer Lock Scope Declaration (iOS)
    
    For any platform backend, the Security_Enforcer should accurately report
    its lock scope via get_lock_scope() ("system", "screen", or "app").
    
    iOS has the most restricted lock scope - app-level only.
    
    Validates: Requirements 40.5
    """
    
    @pytest.mark.properties
    @settings(max_examples=100)
    @given(st.just("ios"))
    def test_ios_lock_scope_is_app(self, platform):
        """
        Test that iOS lock scope is always "app".
        
        This property ensures that iOS accurately reports its lock scope
        and does not claim system or screen locking capabilities.
        """
        enforcer = iOSSecurityEnforcer()
        lock_scope = enforcer.get_lock_scope()
        
        # Must return a string
        assert isinstance(lock_scope, str), \
            f"get_lock_scope should return str, got {type(lock_scope)}"
        
        # CRITICAL: iOS lock scope must be "app"
        assert lock_scope == "app", \
            f"iOS lock scope should be 'app', got '{lock_scope}'"
        
        # Verify this is consistent with capabilities
        capabilities = enforcer.get_capabilities()
        assert capabilities.get('lock_scope', 'system') == 'app', \
            "Lock scope in capabilities should match get_lock_scope()"
    
    @pytest.mark.properties
    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_ios_lock_scope_consistent_across_operations(self, reason):
        """
        Test that iOS lock scope remains consistent across operations.
        
        This property ensures that the lock scope does not change based on
        the reason or context of the lock operation.
        """
        enforcer = iOSSecurityEnforcer()
        
        # Get initial lock scope
        initial_scope = enforcer.get_lock_scope()
        
        # Perform lock operation
        enforcer.lock_session(reason)
        
        # Get lock scope after operation
        after_scope = enforcer.get_lock_scope()
        
        # Lock scope should remain consistent
        assert initial_scope == after_scope, \
            f"Lock scope should remain consistent: {initial_scope} != {after_scope}"
        
        # Both should be "app"
        assert initial_scope == "app", \
            f"iOS lock scope should always be 'app', got '{initial_scope}'"
        assert after_scope == "app", \
            f"iOS lock scope should always be 'app', got '{after_scope}'"
    
    @pytest.mark.properties
    @settings(max_examples=100)
    @given(st.just("ios"))
    def test_ios_lock_scope_matches_capabilities(self, platform):
        """
        Test that iOS lock scope matches its declared capabilities.
        
        This property ensures consistency between get_lock_scope() and
        get_capabilities() - they should tell the same story.
        """
        enforcer = iOSSecurityEnforcer()
        
        lock_scope = enforcer.get_lock_scope()
        capabilities = enforcer.get_capabilities()
        
        # If lock scope is "app", should not have system/screen capabilities
        if lock_scope == "app":
            assert capabilities.get('can_lock_system', True) == False, \
                "If lock scope is 'app', should not have can_lock_system"
            assert capabilities.get('can_lock_screen', True) == False, \
                "If lock scope is 'app', should not have can_lock_screen"
            assert capabilities.get('can_lock_app', False) == True, \
                "If lock scope is 'app', should have can_lock_app"
        
        # Verify lock_scope in capabilities matches get_lock_scope()
        assert capabilities.get('lock_scope') == lock_scope, \
            f"Capabilities lock_scope should match get_lock_scope(): " \
            f"{capabilities.get('lock_scope')} != {lock_scope}"


# ============================================================================
# Additional iOS-Specific Tests
# ============================================================================

@pytest.mark.properties
class TestIOSBackendHonestCapabilityDeclaration:
    """
    Additional tests to ensure iOS backend honestly declares all limitations.
    
    These tests verify that iOS does not hide its severe restrictions and
    provides accurate information to prevent security illusions.
    """
    
    @pytest.mark.properties
    @settings(max_examples=100)
    @given(st.just("ios"))
    def test_ios_security_enforcer_honest_declaration(self, platform):
        """
        Test that iOS Security Enforcer provides honest capability declaration.
        
        This ensures users understand the limitations and do not have false
        expectations about iOS security enforcement capabilities.
        """
        enforcer = iOSSecurityEnforcer()
        capabilities = enforcer.get_capabilities()
        
        # Verify all expected keys are present
        expected_keys = [
            'can_lock_system',
            'can_lock_screen',
            'can_lock_app',
            'has_system_authority',
            'lock_scope',
            'platform_limitations'
        ]
        
        for key in expected_keys:
            assert key in capabilities, \
                f"Capabilities should include '{key}' key"
        
        # Verify honest assessment
        assert capabilities['can_lock_system'] == False
        assert capabilities['can_lock_screen'] == False
        assert capabilities['can_lock_app'] == True
        assert capabilities['has_system_authority'] == False
        assert capabilities['lock_scope'] == 'app'
        assert capabilities['platform_limitations'] == 'severe'
    
    @pytest.mark.properties
    @settings(max_examples=100)
    @given(st.text(min_size=1, max_size=100))
    def test_ios_app_lock_unlock_cycle(self, reason):
        """
        Test that iOS app lock/unlock cycle works correctly.
        
        This property ensures that the app lock mechanism functions properly
        even though it cannot lock the system or screen.
        """
        enforcer = iOSSecurityEnforcer()
        
        # Initially not locked
        assert enforcer.is_app_locked() == False, \
            "App should not be locked initially"
        
        # Lock app
        result = enforcer.lock_session(reason)
        assert result == True, \
            "lock_session should succeed"
        
        # Verify locked
        assert enforcer.is_app_locked() == True, \
            "App should be locked after lock_session"
        
        # Unlock app
        enforcer.unlock_app()
        
        # Verify unlocked
        assert enforcer.is_app_locked() == False, \
            "App should be unlocked after unlock_app"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
