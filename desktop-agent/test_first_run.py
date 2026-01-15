#!/usr/bin/env python3
"""
Test script for first-run detection and setup wizard flow.

Tests:
- First-run detection
- Setup wizard launch
- Configuration persistence
- Setup completion marker
"""

import sys
from pathlib import Path

# Setup Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("=" * 70)
print("FIRST-RUN DETECTION TEST")
print("=" * 70)

# Test 1: First-run detection
print("\n[TEST 1] First-Run Detection")
print("-" * 70)

from config.first_run_detector import FirstRunDetector

detector = FirstRunDetector()

print(f"Config directory: {detector.config_dir}")
print(f"Config file exists: {detector.config_file.exists()}")
print(f"Setup marker exists: {detector.setup_complete_marker.exists()}")
print(f"Is first run: {detector.is_first_run()}")

# Test 2: Configuration manager
print("\n[TEST 2] Configuration Manager")
print("-" * 70)

from config.user_config import get_config_manager

config_manager = get_config_manager()
print(f"Is first time setup: {config_manager.is_first_time_setup()}")

if not config_manager.is_first_time_setup():
    profile = config_manager.get_profile()
    print(f"User profile found:")
    print(f"  - Username: {profile.user_name}")
    print(f"  - Display name: {profile.display_name}")
    print(f"  - Language: {profile.preferred_language}")
    print(f"  - Biometric enabled: {profile.biometric_enabled}")
    print(f"  - Auto-start: {profile.auto_start}")
else:
    print("No user profile found (first run)")

# Test 3: Biometric availability
print("\n[TEST 3] Biometric Availability")
print("-" * 70)

try:
    from biometric.providers import WindowsHelloProvider, BiometricProviderConfig
    from authority.state import BiometricFactor
    
    config = BiometricProviderConfig()
    provider = WindowsHelloProvider(config)
    
    print(f"Windows Hello available: {provider.is_available()}")
    
    if provider.is_available():
        factors = provider.get_supported_factors()
        print(f"Supported factors: {[f.value for f in factors]}")
        
        if BiometricFactor.FINGERPRINT in factors:
            print("  ✓ Fingerprint sensor detected")
        else:
            print("  ✗ Fingerprint sensor not available")
        
        if BiometricFactor.FACE in factors:
            print("  ✓ Face recognition camera detected")
        else:
            print("  ✗ Face recognition camera not available")
    else:
        print("Windows Hello is not configured on this system")

except Exception as e:
    print(f"Error checking biometric availability: {e}")

# Test 4: Setup wizard availability
print("\n[TEST 4] Setup Wizard Availability")
print("-" * 70)

try:
    from gui.setup_wizard import SetupWizard
    print("✓ Setup wizard module loaded successfully")
    
    try:
        from PyQt6.QtWidgets import QApplication
        print("✓ PyQt6 available")
    except ImportError:
        print("✗ PyQt6 not available (required for setup wizard)")

except Exception as e:
    print(f"✗ Error loading setup wizard: {e}")

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

if detector.is_first_run():
    print("\n[RESULT] First run detected - setup wizard will launch on next start")
    print("\nTo test setup wizard:")
    print("  1. Run: python launch_guru.py")
    print("  2. Complete the setup wizard")
    print("  3. Run this test again to verify setup completion")
else:
    print("\n[RESULT] Setup already completed")
    print("\nTo test first-run again:")
    print("  1. Delete: %USERPROFILE%\\.guru\\user_config.json")
    print("  2. Delete: %USERPROFILE%\\.guru\\.setup_complete")
    print("  3. Run: python launch_guru.py")

print("\n" + "=" * 70)
