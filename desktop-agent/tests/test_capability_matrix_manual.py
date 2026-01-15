"""
Manual test script for Platform Capability Matrix.

This script demonstrates the capability matrix API and validates
that all platforms are correctly defined.

Run with: python -m pytest desktop-agent/tests/test_capability_matrix_manual.py -v
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pal.capability_matrix import (
    CapabilityLevel,
    CapabilityMatrix,
    get_capability_matrix,
)


def test_capability_matrix_initialization():
    """Test that capability matrix initializes correctly."""
    matrix = CapabilityMatrix()
    
    # Verify all platforms are defined
    platforms = matrix.get_all_platforms()
    assert len(platforms) == 4
    assert "windows" in platforms
    assert "macos" in platforms
    assert "android" in platforms
    assert "ios" in platforms
    
    print("✅ All 4 platforms defined")


def test_windows_capabilities():
    """Test Windows platform capabilities."""
    matrix = get_capability_matrix()
    windows = matrix.get_platform_capabilities("windows")
    
    assert windows is not None
    assert windows.platform == "windows"
    assert windows.authority_scope == "system-wide"
    
    # Check application control
    open_apps = windows.get_capability("application_control", "open_apps")
    assert open_apps is not None
    assert open_apps.level == CapabilityLevel.FULL
    assert open_apps.is_full()
    assert not open_apps.has_restrictions()
    
    # Check input automation
    type_text = windows.get_capability("input_automation", "type_text")
    assert type_text is not None
    assert type_text.level == CapabilityLevel.FULL
    
    print("✅ Windows capabilities correct")


def test_macos_capabilities():
    """Test macOS platform capabilities."""
    matrix = get_capability_matrix()
    macos = matrix.get_platform_capabilities("macos")
    
    assert macos is not None
    assert macos.platform == "macos"
    assert macos.authority_scope == "system-wide"
    
    # Check input automation (requires permission)
    type_text = macos.get_capability("input_automation", "type_text")
    assert type_text is not None
    assert type_text.level == CapabilityLevel.FULL
    assert type_text.has_restrictions()  # Requires Accessibility permission
    assert "Accessibility permission" in type_text.restrictions[0]
    
    print("✅ macOS capabilities correct")


def test_android_capabilities():
    """Test Android platform capabilities."""
    matrix = get_capability_matrix()
    android = matrix.get_platform_capabilities("android")
    
    assert android is not None
    assert android.platform == "android"
    assert android.authority_scope == "app-level"
    
    # Check input automation (partial)
    type_text = android.get_capability("input_automation", "type_text")
    assert type_text is not None
    assert type_text.level == CapabilityLevel.PARTIAL
    assert type_text.has_restrictions()
    
    # Check STT (partial - user choice)
    stt = android.get_capability("speech", "stt")
    assert stt is not None
    assert stt.level == CapabilityLevel.PARTIAL
    
    print("✅ Android capabilities correct")


def test_ios_capabilities():
    """Test iOS platform capabilities (most restricted)."""
    matrix = get_capability_matrix()
    ios = matrix.get_platform_capabilities("ios")
    
    assert ios is not None
    assert ios.platform == "ios"
    assert ios.authority_scope == "app-level"
    
    # Check application control (limited)
    open_apps = ios.get_capability("application_control", "open_apps")
    assert open_apps is not None
    assert open_apps.level == CapabilityLevel.LIMITED
    
    close_apps = ios.get_capability("application_control", "close_apps")
    assert close_apps is not None
    assert close_apps.level == CapabilityLevel.NONE
    assert not close_apps.is_available()
    
    # Check input automation (none)
    type_text = ios.get_capability("input_automation", "type_text")
    assert type_text is not None
    assert type_text.level == CapabilityLevel.NONE
    assert not type_text.is_available()
    
    # Check STT (partial - system only)
    stt = ios.get_capability("speech", "stt")
    assert stt is not None
    assert stt.level == CapabilityLevel.PARTIAL
    assert "MUST use system STT" in stt.restrictions[0]
    
    print("✅ iOS capabilities correct (most restricted)")


def test_capability_comparison():
    """Test capability comparison across platforms."""
    matrix = get_capability_matrix()
    
    # Compare type_text capability
    comparison = matrix.compare_platforms("input_automation", "type_text")
    
    assert comparison["windows"] == CapabilityLevel.FULL
    assert comparison["macos"] == CapabilityLevel.FULL
    assert comparison["android"] == CapabilityLevel.PARTIAL
    assert comparison["ios"] == CapabilityLevel.NONE
    
    print("✅ Capability comparison works")


def test_platform_limitations():
    """Test platform limitations reporting."""
    matrix = get_capability_matrix()
    
    # Windows should have no limitations
    windows = matrix.get_platform_capabilities("windows")
    windows_limitations = windows.get_limitations()
    assert len(windows_limitations) == 0
    
    # iOS should have many limitations
    ios = matrix.get_platform_capabilities("ios")
    ios_limitations = ios.get_limitations()
    assert len(ios_limitations) > 0
    
    # Check that close_apps is listed as limitation
    close_apps_limited = any("close_apps" in lim for lim in ios_limitations)
    assert close_apps_limited
    
    print(f"✅ iOS has {len(ios_limitations)} documented limitations")


def test_documentation_generation():
    """Test documentation generation."""
    matrix = get_capability_matrix()
    
    # Generate markdown documentation
    markdown_doc = matrix.generate_documentation(format="markdown")
    assert "# GURU Platform Capability Matrix" in markdown_doc
    assert "Windows" in markdown_doc
    assert "macOS" in markdown_doc
    assert "Android" in markdown_doc
    assert "iOS" in markdown_doc
    
    # Generate JSON documentation
    json_doc = matrix.generate_documentation(format="json")
    assert "windows" in json_doc
    assert "authority_scope" in json_doc
    
    print("✅ Documentation generation works")


def test_singleton_pattern():
    """Test that get_capability_matrix returns singleton."""
    matrix1 = get_capability_matrix()
    matrix2 = get_capability_matrix()
    
    assert matrix1 is matrix2
    
    print("✅ Singleton pattern works")


def test_all_categories_present():
    """Test that all capability categories are present for all platforms."""
    matrix = get_capability_matrix()
    
    expected_categories = [
        'application_control',
        'input_automation',
        'speech',
        'biometric',
        'security',
        'memory',
    ]
    
    for platform in ['windows', 'macos', 'android', 'ios']:
        platform_caps = matrix.get_platform_capabilities(platform)
        all_caps = platform_caps.get_all_capabilities()
        
        for category in expected_categories:
            assert category in all_caps, f"{platform} missing {category}"
            assert len(all_caps[category]) > 0, f"{platform}.{category} is empty"
    
    print("✅ All categories present for all platforms")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Platform Capability Matrix Manual Tests")
    print("="*60 + "\n")
    
    test_capability_matrix_initialization()
    test_windows_capabilities()
    test_macos_capabilities()
    test_android_capabilities()
    test_ios_capabilities()
    test_capability_comparison()
    test_platform_limitations()
    test_documentation_generation()
    test_singleton_pattern()
    test_all_categories_present()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED")
    print("="*60 + "\n")
    
    # Print sample output
    print("\nSample Capability Query:")
    print("-" * 60)
    matrix = get_capability_matrix()
    
    for platform in ['windows', 'macos', 'android', 'ios']:
        caps = matrix.get_platform_capabilities(platform)
        type_cap = caps.get_capability("input_automation", "type_text")
        
        print(f"\n{platform.upper()}:")
        print(f"  Authority Scope: {caps.authority_scope}")
        print(f"  Type Text: {type_cap.level.value}")
        if type_cap.restrictions:
            print(f"  Restrictions: {', '.join(type_cap.restrictions)}")
