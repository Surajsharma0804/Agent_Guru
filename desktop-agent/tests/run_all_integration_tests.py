"""
GURU Complete System - Integration Test Runner

This script runs all integration tests and property-based tests to verify
the complete system functionality.

Task: 28.1 Run full integration test suite
Task: 28.2 Run all property-based tests

Feature: guru-complete-system
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*80}")
    print(f"{description}")
    print(f"{'='*80}\n")
    
    result = subprocess.run(cmd, shell=True, capture_output=False)
    return result.returncode == 0


def main():
    """Run all integration and property-based tests."""
    print("\n" + "="*80)
    print("GURU COMPLETE SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80 + "\n")
    
    tests_passed = []
    tests_failed = []
    
    # List of all test files to run
    test_suites = [
        # PAL and Platform Tests
        ("tests/test_pal_properties.py", "PAL Interface Properties"),
        ("tests/test_platform_detection_properties.py", "Platform Detection Properties"),
        ("tests/test_capability_matrix_properties.py", "Capability Matrix Properties"),
        
        # Core Logic Tests
        ("tests/test_core_logic_refactoring_properties.py", "Core Logic Refactoring Properties"),
        ("tests/test_authority_state_machine_properties.py", "Authority State Machine Properties"),
        ("tests/test_authority_scope_properties.py", "Authority Scope Properties"),
        
        # Security Tests
        ("tests/test_intrusion_detection_properties.py", "Intrusion Detection Properties"),
        ("tests/test_audit_logging_properties.py", "Audit Logging Properties"),
        ("tests/test_permission_model_properties.py", "Permission Model Properties"),
        ("tests/test_skill_permission_properties.py", "Skill Permission Properties"),
        
        # Voice and Command Tests
        ("tests/test_wake_word_stripping_properties.py", "Wake Word Stripping Properties"),
        ("tests/test_dictation_mode_properties.py", "Dictation Mode Properties"),
        ("tests/test_exact_text_dictation_properties.py", "Exact Text Dictation Properties"),
        ("tests/test_response_ownership_properties.py", "Response Ownership Properties"),
        ("tests/test_deterministic_first_properties.py", "Deterministic-First Properties"),
        ("tests/test_speech_contract_properties.py", "Speech Contract Properties"),
        
        # Command Execution Tests
        ("tests/test_whatsapp_automation_properties.py", "WhatsApp Automation Properties"),
        
        # System Tests
        ("tests/test_llm_adapter_properties.py", "LLM Adapter Properties"),
        ("tests/test_tts_service_properties.py", "TTS Service Properties"),
        ("tests/test_memory_system_properties.py", "Memory System Properties"),
        ("tests/test_failure_orchestrator_properties.py", "Failure Orchestrator Properties"),
        ("tests/test_thread_safety_properties.py", "Thread Safety Properties"),
        ("tests/test_error_handling_properties.py", "Error Handling Properties"),
        
        # Platform Backend Tests
        ("tests/test_macos_backend_properties.py", "macOS Backend Properties"),
        ("tests/test_android_backend_properties.py", "Android Backend Properties"),
        ("tests/test_ios_backend_properties.py", "iOS Backend Properties"),
        
        # Integration Tests
        ("tests/security/test_authority.py", "Authority Security Tests"),
        ("tests/security/test_audit.py", "Audit Security Tests"),
        ("tests/test_biometric_authentication_flow.py", "Biometric Authentication Flow"),
        ("tests/test_universal_app_launcher.py", "Universal App Launcher"),
    ]
    
    # Run each test suite
    for test_file, description in test_suites:
        cmd = f"python -m pytest {test_file} -v --tb=short -x"
        success = run_command(cmd, description)
        
        if success:
            tests_passed.append(description)
            print(f"✓ {description} PASSED")
        else:
            tests_failed.append(description)
            print(f"✗ {description} FAILED")
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUITE SUMMARY")
    print("="*80 + "\n")
    
    print(f"Total Test Suites: {len(test_suites)}")
    print(f"Passed: {len(tests_passed)}")
    print(f"Failed: {len(tests_failed)}")
    
    if tests_passed:
        print("\n✓ PASSED TEST SUITES:")
        for test in tests_passed:
            print(f"  - {test}")
    
    if tests_failed:
        print("\n✗ FAILED TEST SUITES:")
        for test in tests_failed:
            print(f"  - {test}")
    
    print("\n" + "="*80)
    
    if len(tests_failed) == 0:
        print("✓ ALL INTEGRATION TESTS PASSED")
        print("="*80 + "\n")
        return 0
    else:
        print("✗ SOME INTEGRATION TESTS FAILED")
        print("="*80 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
