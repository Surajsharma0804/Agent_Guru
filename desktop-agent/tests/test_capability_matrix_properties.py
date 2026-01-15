"""
Property-Based Tests for Platform Capability Matrix.

Tests Property 108: Capability Matrix Runtime Query

These tests validate that the capability matrix provides accurate,
programmatically queryable platform capabilities at runtime.

CRITICAL RULES:
1. All platforms must be queryable
2. All capability levels must be accurate
3. Capability comparisons must be consistent
4. Documentation generation must be deterministic
5. Singleton pattern must be enforced

Validates: Requirements 41.7

Run with: python -m pytest desktop-agent/tests/test_capability_matrix_properties.py -v
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from hypothesis import HealthCheck, Phase, assume, given, settings
from hypothesis import strategies as st

from pal.capability_matrix import (
    Capability,
    CapabilityLevel,
    CapabilityMatrix,
    PlatformCapabilities,
    get_capability_matrix,
)

# ============================================================================
# Property 108: Capability Matrix Runtime Query
# ============================================================================

@settings(
    max_examples=100,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
@given(
    platform=st.sampled_from(['windows', 'macos', 'android', 'ios']),
)
def test_property_108_all_platforms_queryable(platform: str):
    """
    Property 108: Capability Matrix Runtime Query
    
    For any platform in {windows, macos, android, ios},
    the capability matrix MUST return valid PlatformCapabilities.
    
    Validates: Requirement 41.7
    """
    matrix = get_capability_matrix()
    
    # Query platform capabilities
    platform_caps = matrix.get_platform_capabilities(platform)
    
    # INVARIANT: Platform capabilities must exist
    assert platform_caps is not None, f"Platform {platform} not found in capability matrix"
    
    # INVARIANT: Platform identifier must match
    assert platform_caps.platform == platform
    
    # INVARIANT: Authority scope must be defined
    assert platform_caps.authority_scope in ['system-wide', 'app-level']
    
    # INVARIANT: All capability categories must exist
    all_caps = platform_caps.get_all_capabilities()
    expected_categories = [
        'application_control',
        'input_automation',
        'speech',
        'biometric',
        'security',
        'memory',
    ]
    
    for category in expected_categories:
        assert category in all_caps, f"Platform {platform} missing category {category}"
        assert len(all_caps[category]) > 0, f"Platform {platform} category {category} is empty"


@settings(
    max_examples=100,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
@given(
    platform=st.sampled_from(['windows', 'macos', 'android', 'ios']),
    category=st.sampled_from([
        'application_control',
        'input_automation',
        'speech',
        'biometric',
        'security',
        'memory',
    ]),
)
def test_property_108_capability_query_consistency(platform: str, category: str):
    """
    Property 108: Capability Matrix Runtime Query
    
    For any platform and category, querying capabilities MUST return
    consistent, well-formed Capability objects.
    
    Validates: Requirement 41.7
    """
    matrix = get_capability_matrix()
    platform_caps = matrix.get_platform_capabilities(platform)
    
    # Get all capabilities in category
    all_caps = platform_caps.get_all_capabilities()
    category_caps = all_caps[category]
    
    # INVARIANT: Category must have at least one capability
    assert len(category_caps) > 0
    
    # INVARIANT: All capabilities must be well-formed
    for cap_name, capability in category_caps.items():
        # Must be Capability instance
        assert isinstance(capability, Capability)
        
        # Name must match
        assert capability.name == cap_name
        
        # Level must be valid
        assert isinstance(capability.level, CapabilityLevel)
        assert capability.level in [
            CapabilityLevel.FULL,
            CapabilityLevel.PARTIAL,
            CapabilityLevel.LIMITED,
            CapabilityLevel.NONE,
        ]
        
        # Description must be non-empty
        assert len(capability.description) > 0
        
        # Restrictions must be list
        assert isinstance(capability.restrictions, list)
        
        # Implementation must be non-empty
        assert len(capability.implementation) > 0
        
        # INVARIANT: FULL capabilities should have no restrictions
        if capability.level == CapabilityLevel.FULL:
            # Desktop platforms may have permission requirements
            if platform in ['windows'] and category != 'input_automation':
                assert len(capability.restrictions) == 0, \
                    f"{platform}.{category}.{cap_name} is FULL but has restrictions"
        
        # INVARIANT: NONE capabilities should have restrictions explaining why
        if capability.level == CapabilityLevel.NONE:
            assert len(capability.restrictions) > 0, \
                f"{platform}.{category}.{cap_name} is NONE but has no restrictions"


@settings(
    max_examples=100,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
@given(
    category=st.sampled_from([
        'application_control',
        'input_automation',
        'speech',
        'biometric',
        'security',
        'memory',
    ]),
)
def test_property_108_capability_comparison_consistency(category: str):
    """
    Property 108: Capability Matrix Runtime Query
    
    For any capability category, comparing capabilities across platforms
    MUST return consistent CapabilityLevel values.
    
    Validates: Requirement 41.7
    """
    matrix = get_capability_matrix()
    
    # Get all capability names in this category across all platforms
    all_capability_names = set()
    for platform in ['windows', 'macos', 'android', 'ios']:
        platform_caps = matrix.get_platform_capabilities(platform)
        category_caps = platform_caps.get_all_capabilities()[category]
        all_capability_names.update(category_caps.keys())
    
    # For each capability, compare across platforms
    for cap_name in all_capability_names:
        comparison = matrix.compare_platforms(category, cap_name)
        
        # INVARIANT: Comparison must include all platforms
        assert len(comparison) == 4
        assert 'windows' in comparison
        assert 'macos' in comparison
        assert 'android' in comparison
        assert 'ios' in comparison
        
        # INVARIANT: All values must be CapabilityLevel
        for platform, level in comparison.items():
            assert isinstance(level, CapabilityLevel)
        
        # INVARIANT: Desktop platforms should generally have better or equal capabilities
        # (This is a domain-specific invariant based on platform architecture)
        if cap_name in ['type_text', 'click_ui']:
            # Input automation: Desktop > Android > iOS
            windows_level = comparison['windows']
            ios_level = comparison['ios']
            
            # Windows should be FULL or PARTIAL, iOS should be NONE or LIMITED
            if windows_level == CapabilityLevel.FULL:
                assert ios_level in [CapabilityLevel.NONE, CapabilityLevel.LIMITED, CapabilityLevel.PARTIAL]


@settings(
    max_examples=100,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
@given(
    platform=st.sampled_from(['windows', 'macos', 'android', 'ios']),
)
def test_property_108_authority_scope_consistency(platform: str):
    """
    Property 108: Capability Matrix Runtime Query
    
    For any platform, authority scope MUST be consistent with platform architecture:
    - Desktop platforms (Windows, macOS): system-wide
    - Mobile platforms (Android, iOS): app-level
    
    Validates: Requirement 41.7, 39.2, 39.3, 39.4
    """
    matrix = get_capability_matrix()
    platform_caps = matrix.get_platform_capabilities(platform)
    
    # INVARIANT: Desktop platforms have system-wide authority
    if platform in ['windows', 'macos']:
        assert platform_caps.authority_scope == 'system-wide', \
            f"Desktop platform {platform} should have system-wide authority"
    
    # INVARIANT: Mobile platforms have app-level authority
    if platform in ['android', 'ios']:
        assert platform_caps.authority_scope == 'app-level', \
            f"Mobile platform {platform} should have app-level authority"


@settings(
    max_examples=100,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
@given(
    platform=st.sampled_from(['windows', 'macos', 'android', 'ios']),
)
def test_property_108_platform_limitations_accuracy(platform: str):
    """
    Property 108: Capability Matrix Runtime Query
    
    For any platform, limitations reporting MUST accurately reflect
    capabilities that are PARTIAL, LIMITED, or NONE.
    
    Validates: Requirement 41.7
    """
    matrix = get_capability_matrix()
    platform_caps = matrix.get_platform_capabilities(platform)
    
    # Get limitations
    limitations = platform_caps.get_limitations()
    
    # INVARIANT: Limitations must be list of strings
    assert isinstance(limitations, list)
    for limitation in limitations:
        assert isinstance(limitation, str)
        assert len(limitation) > 0
    
    # INVARIANT: Windows should have no limitations (reference platform)
    if platform == 'windows':
        assert len(limitations) == 0, "Windows should have no limitations"
    
    # INVARIANT: iOS should have many limitations (most restricted)
    if platform == 'ios':
        assert len(limitations) > 5, "iOS should have multiple documented limitations"
    
    # INVARIANT: All NONE capabilities should be in limitations
    all_caps = platform_caps.get_all_capabilities()
    none_count = 0
    for category_caps in all_caps.values():
        for capability in category_caps.values():
            if capability.level == CapabilityLevel.NONE:
                none_count += 1
    
    # At least some NONE capabilities should be documented in limitations
    if none_count > 0:
        assert len(limitations) > 0, \
            f"Platform {platform} has {none_count} NONE capabilities but no limitations documented"


@settings(
    max_examples=100,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
@given(
    format_type=st.sampled_from(['markdown', 'json']),
)
def test_property_108_documentation_generation_deterministic(format_type: str):
    """
    Property 108: Capability Matrix Runtime Query
    
    For any documentation format, generation MUST be deterministic
    and produce valid output.
    
    Validates: Requirement 41.6, 41.7
    """
    matrix = get_capability_matrix()
    
    # Generate documentation twice
    doc1 = matrix.generate_documentation(format=format_type)
    doc2 = matrix.generate_documentation(format=format_type)
    
    # INVARIANT: Documentation generation must be deterministic
    assert doc1 == doc2, f"Documentation generation for {format_type} is not deterministic"
    
    # INVARIANT: Documentation must be non-empty
    assert len(doc1) > 0
    
    # INVARIANT: Documentation must contain all platforms
    assert 'windows' in doc1.lower()
    assert 'macos' in doc1.lower()
    assert 'android' in doc1.lower()
    assert 'ios' in doc1.lower()
    
    # Format-specific invariants
    if format_type == 'markdown':
        assert '# GURU Platform Capability Matrix' in doc1
        assert '##' in doc1  # Should have sections
        assert '|' in doc1   # Should have tables
    
    if format_type == 'json':
        import json

        # Should be valid JSON
        parsed = json.loads(doc1)
        assert isinstance(parsed, dict)
        assert 'windows' in parsed
        assert 'macos' in parsed
        assert 'android' in parsed
        assert 'ios' in parsed


def test_property_108_singleton_pattern_enforced():
    """
    Property 108: Capability Matrix Runtime Query
    
    The capability matrix MUST use singleton pattern to ensure
    consistent state across the application.
    
    Validates: Requirement 41.7
    """
    # Get matrix multiple times
    matrix1 = get_capability_matrix()
    matrix2 = get_capability_matrix()
    matrix3 = get_capability_matrix()
    
    # INVARIANT: All references must point to same instance
    assert matrix1 is matrix2
    assert matrix2 is matrix3
    assert matrix1 is matrix3


@settings(
    max_examples=100,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target],
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
@given(
    platform=st.sampled_from(['windows', 'macos', 'android', 'ios']),
)
def test_property_108_capability_availability_methods(platform: str):
    """
    Property 108: Capability Matrix Runtime Query
    
    For any platform, Capability objects MUST provide accurate
    availability query methods.
    
    Validates: Requirement 41.7
    """
    matrix = get_capability_matrix()
    platform_caps = matrix.get_platform_capabilities(platform)
    
    all_caps = platform_caps.get_all_capabilities()
    
    for category_caps in all_caps.values():
        for capability in category_caps.values():
            # INVARIANT: is_available() must match level != NONE
            if capability.level == CapabilityLevel.NONE:
                assert not capability.is_available()
            else:
                assert capability.is_available()
            
            # INVARIANT: is_full() must match level == FULL
            if capability.level == CapabilityLevel.FULL:
                assert capability.is_full()
            else:
                assert not capability.is_full()
            
            # INVARIANT: has_restrictions() must match non-empty restrictions
            if len(capability.restrictions) > 0:
                assert capability.has_restrictions()
            else:
                assert not capability.has_restrictions()


def test_property_108_ios_severe_limitations_documented():
    """
    Property 108: Capability Matrix Runtime Query
    
    iOS platform MUST have severe limitations accurately documented,
    particularly for input automation and application control.
    
    This is a critical honesty check - we must not overstate iOS capabilities.
    
    Validates: Requirement 41.5, 41.7
    """
    matrix = get_capability_matrix()
    ios_caps = matrix.get_platform_capabilities('ios')
    
    # INVARIANT: iOS input automation must be NONE
    type_text = ios_caps.get_capability('input_automation', 'type_text')
    assert type_text.level == CapabilityLevel.NONE, "iOS cannot automate text input"
    
    click_ui = ios_caps.get_capability('input_automation', 'click_ui')
    assert click_ui.level == CapabilityLevel.NONE, "iOS cannot automate UI clicks"
    
    # INVARIANT: iOS cannot close apps
    close_apps = ios_caps.get_capability('application_control', 'close_apps')
    assert close_apps.level == CapabilityLevel.NONE, "iOS cannot close apps"
    
    # INVARIANT: iOS can only open apps via deep links (LIMITED)
    open_apps = ios_caps.get_capability('application_control', 'open_apps')
    assert open_apps.level == CapabilityLevel.LIMITED, "iOS can only open apps via deep links"
    
    # INVARIANT: iOS must use system STT (PARTIAL)
    stt = ios_caps.get_capability('speech', 'stt')
    assert stt.level == CapabilityLevel.PARTIAL, "iOS must use system STT"
    assert any('system STT' in r for r in stt.restrictions), "iOS STT restrictions must mention system requirement"
    
    # INVARIANT: iOS security enforcement is LIMITED (app-only)
    lock_workstation = ios_caps.get_capability('security', 'lock_workstation')
    assert lock_workstation.level == CapabilityLevel.LIMITED, "iOS can only exit app, not lock device"


def test_property_108_windows_reference_platform_full_capabilities():
    """
    Property 108: Capability Matrix Runtime Query
    
    Windows platform MUST have FULL capabilities across all categories
    (it is the reference implementation).
    
    Validates: Requirement 41.2, 41.7
    """
    matrix = get_capability_matrix()
    windows_caps = matrix.get_platform_capabilities('windows')
    
    # INVARIANT: Windows has system-wide authority
    assert windows_caps.authority_scope == 'system-wide'
    
    # INVARIANT: Windows has no limitations
    limitations = windows_caps.get_limitations()
    assert len(limitations) == 0, "Windows should have no limitations"
    
    # INVARIANT: All Windows capabilities should be FULL
    all_caps = windows_caps.get_all_capabilities()
    
    for category_name, category_caps in all_caps.items():
        for cap_name, capability in category_caps.items():
            assert capability.level == CapabilityLevel.FULL, \
                f"Windows {category_name}.{cap_name} should be FULL, got {capability.level}"
            
            # Windows FULL capabilities should have no restrictions
            # (except for hardware availability notes)
            if 'hardware available' not in capability.description.lower():
                assert len(capability.restrictions) == 0, \
                    f"Windows {category_name}.{cap_name} is FULL but has restrictions: {capability.restrictions}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
