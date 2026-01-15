"""
Property-Based Tests for Skill Permission Validation

Tests universal properties of skill permission declarations and validation.

Feature: guru-complete-system
Properties: 58, 59
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

from src.authority.permission_model import (
    SkillPermissionValidator,
    create_skill_permission_validator
)


# Generators

@st.composite
def permission_set_strategy(draw):
    """Generate sets of permissions."""
    all_permissions = [
        'filesystem_read',
        'filesystem_write',
        'network_access',
        'ui_automation',
        'system_info',
        'process_control',
        'registry_read',
        'registry_write',
        'audio_capture',
        'screen_capture'
    ]
    
    # Generate a subset of permissions
    num_permissions = draw(st.integers(min_value=1, max_value=len(all_permissions)))
    permissions = draw(st.lists(
        st.sampled_from(all_permissions),
        min_size=num_permissions,
        max_size=num_permissions,
        unique=True
    ))
    
    return set(permissions)


@st.composite
def safe_permission_set_strategy(draw):
    """Generate safe permission sets (no excessive combinations)."""
    safe_permissions = [
        'filesystem_read',
        'system_info',
        'registry_read'
    ]
    
    num_permissions = draw(st.integers(min_value=1, max_value=len(safe_permissions)))
    permissions = draw(st.lists(
        st.sampled_from(safe_permissions),
        min_size=num_permissions,
        max_size=num_permissions,
        unique=True
    ))
    
    return set(permissions)


@st.composite
def excessive_permission_set_strategy(draw):
    """Generate excessive permission combinations."""
    excessive_combinations = [
        {'network_access', 'filesystem_write', 'process_control'},
        {'screen_capture', 'network_access'},
        {'audio_capture', 'network_access'},
        {'registry_write', 'process_control'},
        {'ui_automation', 'network_access', 'filesystem_write'}
    ]
    
    combination = draw(st.sampled_from(excessive_combinations))
    return combination


@st.composite
def skill_id_strategy(draw):
    """Generate skill IDs."""
    prefix = draw(st.sampled_from(['skill', 'plugin', 'extension', 'addon']))
    suffix = draw(st.integers(min_value=1, max_value=1000))
    return f"{prefix}_{suffix}"


@st.composite
def justification_strategy(draw):
    """Generate justifications for permissions."""
    templates = [
        "This skill requires {perm} to perform {action} for {purpose}.",
        "The {perm} permission is needed to {action} which is essential for {purpose}.",
        "{perm} access is required to {action} and provide {purpose} functionality."
    ]
    
    template = draw(st.sampled_from(templates))
    perm = draw(st.sampled_from(['network', 'file', 'process', 'UI', 'registry']))
    action = draw(st.sampled_from(['monitor', 'control', 'manage', 'automate', 'synchronize']))
    purpose = draw(st.sampled_from(['productivity', 'security', 'automation', 'integration', 'monitoring']))
    
    justification = template.format(perm=perm, action=action, purpose=purpose)
    
    # Ensure minimum length
    while len(justification) < 50:
        justification += " Additional context provided for clarity and completeness."
    
    return justification


# Property Tests

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    skill_id=skill_id_strategy(),
    permissions=permission_set_strategy()
)
def test_property_58_skill_permission_declaration(skill_id, permissions):
    """
    Property 58: Skill Permission Declaration
    
    For any loaded skill, it should explicitly declare all required permissions in its manifest.
    
    Validates: Requirements 25.5
    
    Feature: guru-complete-system, Property 58: Skill Permission Declaration
    """
    # Create validator
    validator = create_skill_permission_validator()
    
    # Property: Skills must declare at least one permission
    assert len(permissions) > 0, "Skill must declare at least one permission"
    
    # Validate permissions
    is_valid, errors = validator.validate_skill_permissions(
        skill_id=skill_id,
        permissions=permissions
    )
    
    # Property: Validation should complete without exceptions
    assert isinstance(is_valid, bool)
    assert isinstance(errors, list)
    
    # Property: If permissions are declared, validation should process them
    # (may be valid or invalid depending on combination)
    if is_valid:
        assert len(errors) == 0, "Valid permissions should have no errors"
    else:
        assert len(errors) > 0, "Invalid permissions should have error messages"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    skill_id=skill_id_strategy(),
    permissions=safe_permission_set_strategy()
)
def test_property_58_safe_permissions_accepted(skill_id, permissions):
    """
    Property 58 (Safe Permissions): Safe Permissions Accepted
    
    For any skill with safe permissions, validation should succeed.
    
    Validates: Requirements 25.5
    
    Feature: guru-complete-system, Property 58: Skill Permission Declaration
    """
    # Create validator
    validator = create_skill_permission_validator()
    
    # Validate safe permissions
    is_valid, errors = validator.validate_skill_permissions(
        skill_id=skill_id,
        permissions=permissions
    )
    
    # Property: Safe permissions should be accepted
    assert is_valid, f"Safe permissions should be valid, got errors: {errors}"
    assert len(errors) == 0


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    skill_id=skill_id_strategy(),
    permissions=excessive_permission_set_strategy(),
    justification=justification_strategy()
)
def test_property_59_excessive_permission_rejection(skill_id, permissions, justification):
    """
    Property 59: Excessive Permission Rejection
    
    For any skill requesting excessive permissions without justification,
    the Skills_Registry should reject it.
    
    Validates: Requirements 25.6
    
    Feature: guru-complete-system, Property 59: Excessive Permission Rejection
    """
    # Create validator
    validator = create_skill_permission_validator()
    
    # Validate excessive permissions WITHOUT justification
    is_valid_without, errors_without = validator.validate_skill_permissions(
        skill_id=skill_id,
        permissions=permissions,
        justification=None
    )
    
    # Property: Excessive permissions without justification should be rejected
    assert not is_valid_without, \
        f"Excessive permissions without justification should be rejected: {permissions}"
    assert len(errors_without) > 0, \
        "Rejection should include error messages"
    
    # Validate excessive permissions WITH justification
    is_valid_with, errors_with = validator.validate_skill_permissions(
        skill_id=skill_id,
        permissions=permissions,
        justification=justification
    )
    
    # Property: Excessive permissions with proper justification should be accepted
    # (with warning logged)
    assert is_valid_with, \
        f"Excessive permissions with justification should be accepted: {permissions}"
    assert len(errors_with) == 0


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    skill_id=skill_id_strategy(),
    base_permissions=safe_permission_set_strategy(),
    additional_permissions=st.sets(
        st.sampled_from([
            'network_access',
            'filesystem_write',
            'process_control',
            'ui_automation',
            'screen_capture',
            'audio_capture'
        ]),
        min_size=1,
        max_size=3
    )
)
def test_property_59_permission_escalation_detection(skill_id, base_permissions, additional_permissions):
    """
    Property 59 (Escalation): Permission Escalation Detection
    
    For any skill attempting to escalate permissions, the validator should detect it.
    
    Validates: Requirements 25.6
    
    Feature: guru-complete-system, Property 59: Excessive Permission Rejection
    """
    # Create validator
    validator = create_skill_permission_validator()
    
    # Create old and new permission sets where new is a superset
    old_permissions = base_permissions
    new_permissions = base_permissions | additional_permissions
    
    # Check for permission escalation
    is_escalation, added_perms = validator.check_permission_escalation(
        skill_id=skill_id,
        old_permissions=old_permissions,
        new_permissions=new_permissions
    )
    
    # Property: If new permissions are a superset, escalation should be detected
    if new_permissions > old_permissions:
        assert is_escalation, "Permission escalation should be detected when permissions increase"
        assert len(added_perms) > 0, "Added permissions should be listed"
        
        # Verify added permissions are correct
        expected_added = new_permissions - old_permissions
        assert set(added_perms) == expected_added, \
            f"Added permissions should match: expected {expected_added}, got {set(added_perms)}"
    else:
        # If permissions are the same (additional_permissions was empty or already in base)
        assert not is_escalation, "No escalation if permissions didn't increase"
        assert len(added_perms) == 0, "No added permissions if no escalation"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    skill_id=skill_id_strategy()
)
def test_property_wildcard_permissions_rejected(skill_id):
    """
    Property: Wildcard Permissions Rejected
    
    For any skill requesting wildcard permissions, validation should fail.
    
    Validates: Requirements 25.6
    
    Feature: guru-complete-system, Property 59: Excessive Permission Rejection
    """
    # Create validator
    validator = create_skill_permission_validator()
    
    # Test wildcard permissions
    wildcard_permissions = {'*'}
    is_valid_star, errors_star = validator.validate_skill_permissions(
        skill_id=skill_id,
        permissions=wildcard_permissions
    )
    
    # Property: Wildcard '*' should be rejected
    assert not is_valid_star, "Wildcard '*' permissions should be rejected"
    assert any('wildcard' in err.lower() or '*' in err for err in errors_star), \
        "Error should mention wildcard"
    
    # Test 'all' permissions
    all_permissions = {'all'}
    is_valid_all, errors_all = validator.validate_skill_permissions(
        skill_id=skill_id,
        permissions=all_permissions
    )
    
    # Property: 'all' should be rejected
    assert not is_valid_all, "'all' permissions should be rejected"
    assert any('wildcard' in err.lower() or 'all' in err for err in errors_all), \
        "Error should mention wildcard or 'all'"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    skill_id=skill_id_strategy()
)
def test_property_system_permissions_rejected(skill_id):
    """
    Property: System-Level Permissions Rejected
    
    For any skill requesting system-level permissions, validation should fail.
    
    Validates: Requirements 25.6, 25.7
    
    Feature: guru-complete-system, Property 59: Excessive Permission Rejection
    """
    # Create validator
    validator = create_skill_permission_validator()
    
    # Test system-level permissions
    system_permissions = {'system_access', 'kernel_access', 'driver_access'}
    
    for sys_perm in system_permissions:
        is_valid, errors = validator.validate_skill_permissions(
            skill_id=skill_id,
            permissions={sys_perm}
        )
        
        # Property: System-level permissions should be rejected
        assert not is_valid, f"System permission '{sys_perm}' should be rejected"
        assert any('system' in err.lower() for err in errors), \
            f"Error should mention system-level permissions for '{sys_perm}'"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    skill_id=skill_id_strategy(),
    permissions=permission_set_strategy()
)
def test_property_empty_permissions_rejected(skill_id, permissions):
    """
    Property: Empty Permissions Rejected
    
    For any skill with no permissions declared, validation should fail.
    
    Validates: Requirements 25.5
    
    Feature: guru-complete-system, Property 58: Skill Permission Declaration
    """
    # Create validator
    validator = create_skill_permission_validator()
    
    # Test empty permissions
    is_valid, errors = validator.validate_skill_permissions(
        skill_id=skill_id,
        permissions=set()
    )
    
    # Property: Empty permissions should be rejected
    assert not is_valid, "Empty permissions should be rejected"
    assert len(errors) > 0, "Rejection should include error message"
    assert any('at least one' in err.lower() or 'declare' in err.lower() for err in errors), \
        "Error should mention permission declaration requirement"


# Unit Tests for Edge Cases

def test_permission_validator_initialization():
    """Test permission validator initialization."""
    validator = create_skill_permission_validator()
    
    assert validator is not None
    assert isinstance(validator, SkillPermissionValidator)


def test_short_justification_rejected():
    """Test that short justifications are rejected."""
    validator = create_skill_permission_validator()
    
    excessive_perms = {'network_access', 'filesystem_write', 'process_control'}
    short_justification = "Need it"  # Too short
    
    is_valid, errors = validator.validate_skill_permissions(
        skill_id="test_skill",
        permissions=excessive_perms,
        justification=short_justification
    )
    
    # Should be rejected due to insufficient justification
    assert not is_valid
    assert any('justification' in err.lower() for err in errors)


def test_permission_escalation_no_change():
    """Test permission escalation when permissions don't change."""
    validator = create_skill_permission_validator()
    
    permissions = {'filesystem_read', 'system_info'}
    
    is_escalation, added_perms = validator.check_permission_escalation(
        skill_id="test_skill",
        old_permissions=permissions,
        new_permissions=permissions
    )
    
    # No escalation if permissions are the same
    assert not is_escalation
    assert len(added_perms) == 0


def test_permission_escalation_reduction():
    """Test permission escalation when permissions are reduced."""
    validator = create_skill_permission_validator()
    
    old_permissions = {'filesystem_read', 'system_info', 'network_access'}
    new_permissions = {'filesystem_read', 'system_info'}
    
    is_escalation, added_perms = validator.check_permission_escalation(
        skill_id="test_skill",
        old_permissions=old_permissions,
        new_permissions=new_permissions
    )
    
    # No escalation if permissions are reduced
    assert not is_escalation
    assert len(added_perms) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
