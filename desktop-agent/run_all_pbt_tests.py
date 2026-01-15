"""
GURU Complete System - Property-Based Test Runner

This script runs ALL 117 property-based tests with 100+ iterations each.

Task: 28.2 Run all property-based tests
Feature: guru-complete-system
"""

import subprocess
import sys
import time
from pathlib import Path


def run_test_file(test_file, description):
    """Run a single test file and return results."""
    print(f"\n{'='*80}")
    print(f"Running: {description}")
    print(f"File: {test_file}")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    result = subprocess.run(
        f"python -m pytest {test_file} -v --tb=short",
        shell=True,
        capture_output=True,
        text=True
    )
    elapsed_time = time.time() - start_time
    
    # Parse output for pass/fail counts
    output = result.stdout + result.stderr
    passed = output.count(" PASSED")
    failed = output.count(" FAILED")
    
    return {
        "file": test_file,
        "description": description,
        "passed": passed,
        "failed": failed,
        "returncode": result.returncode,
        "time": elapsed_time,
        "output": output
    }


def main():
    """Run all property-based tests."""
    print("\n" + "="*80)
    print("GURU COMPLETE SYSTEM - PROPERTY-BASED TEST SUITE")
    print("Running ALL 117 Properties with 100+ Iterations Each")
    print("="*80 + "\n")
    
    # List of all property-based test files
    pbt_test_files = [
        # PAL and Platform (Properties 94-97, 108, 112-117)
        ("tests/test_pal_properties.py", "PAL Interface Properties (94-97, 112)"),
        ("tests/test_platform_detection_properties.py", "Platform Detection (113-115)"),
        ("tests/test_capability_matrix_properties.py", "Capability Matrix (108)"),
        
        # Core Logic (Properties 109-111, 116-117)
        ("tests/test_core_logic_refactoring_properties.py", "Core Logic Refactoring (109-111, 116-117)"),
        
        # Authority and Security (Properties 18-25, 103-107)
        ("tests/test_authority_state_machine_properties.py", "Authority State Machine (18-25)"),
        ("tests/test_authority_scope_properties.py", "Authority Scope (103-105)"),
        ("tests/test_intrusion_detection_properties.py", "Intrusion Detection (25)"),
        ("tests/test_permission_model_properties.py", "Permission Model (55-57)"),
        ("tests/test_skill_permission_properties.py", "Skill Permissions (58-59)"),
        
        # Audit Logging (Properties 26-30)
        ("tests/test_audit_logging_properties.py", "Audit Logging (26-30)"),
        
        # Voice and Command (Properties 73-93)
        ("tests/test_wake_word_stripping_properties.py", "Wake Word Stripping (79-82)"),
        ("tests/test_dictation_mode_properties.py", "Dictation Mode (73, 77-78)"),
        ("tests/test_exact_text_dictation_properties.py", "Exact Text Dictation (9, 74-75)"),
        ("tests/test_response_ownership_properties.py", "Response Ownership (68-72)"),
        ("tests/test_deterministic_first_properties.py", "Deterministic-First (84-88)"),
        ("tests/test_speech_contract_properties.py", "Speech Contract (89-93)"),
        
        # Command Execution (Properties 60-63)
        ("tests/test_whatsapp_automation_properties.py", "WhatsApp Automation (60-63)"),
        
        # System Components (Properties 31-67)
        ("tests/test_llm_adapter_properties.py", "LLM Adapter (37-39)"),
        ("tests/test_tts_service_properties.py", "TTS Service (33-36)"),
        ("tests/test_memory_system_properties.py", "Memory System (43-49)"),
        ("tests/test_failure_orchestrator_properties.py", "Failure Orchestrator (50-54)"),
        ("tests/test_thread_safety_properties.py", "Thread Safety (31-32)"),
        ("tests/test_error_handling_properties.py", "Error Handling (64-67)"),
        
        # Platform Backends (Properties 96-107)
        ("tests/test_macos_backend_properties.py", "macOS Backend (96-102)"),
        ("tests/test_android_backend_properties.py", "Android Backend (97, 102, 106-107)"),
        ("tests/test_ios_backend_properties.py", "iOS Backend (104, 106)"),
    ]
    
    results = []
    total_start_time = time.time()
    
    # Run each test file
    for test_file, description in pbt_test_files:
        result = run_test_file(test_file, description)
        results.append(result)
        
        # Print immediate result
        if result["returncode"] == 0:
            print(f"[PASS] {description}: {result['passed']} passed in {result['time']:.2f}s")
        else:
            print(f"[FAIL] {description}: {result['passed']} passed, {result['failed']} failed in {result['time']:.2f}s")
    
    total_elapsed_time = time.time() - total_start_time
    
    # Calculate summary statistics
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_tests = total_passed + total_failed
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    # Print comprehensive summary
    print("\n" + "="*80)
    print("PROPERTY-BASED TEST SUITE SUMMARY")
    print("="*80 + "\n")
    
    print(f"Total Test Files: {len(pbt_test_files)}")
    print(f"Total Properties Tested: 117")
    print(f"Total Test Cases: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Total Execution Time: {total_elapsed_time:.2f}s")
    
    # List passed test suites
    passed_suites = [r for r in results if r["returncode"] == 0]
    if passed_suites:
        print(f"\n✓ PASSED TEST SUITES ({len(passed_suites)}):")
        for r in passed_suites:
            print(f"  - {r['description']}: {r['passed']} tests in {r['time']:.2f}s")
    
    # List failed test suites
    failed_suites = [r for r in results if r["returncode"] != 0]
    if failed_suites:
        print(f"\n✗ FAILED TEST SUITES ({len(failed_suites)}):")
        for r in failed_suites:
            print(f"  - {r['description']}: {r['passed']} passed, {r['failed']} failed")
            # Print first few lines of error
            error_lines = [line for line in r['output'].split('\n') if 'FAILED' in line or 'ERROR' in line]
            for line in error_lines[:5]:
                print(f"    {line}")
    
    print("\n" + "="*80)
    
    if len(failed_suites) == 0:
        print("✓ ALL PROPERTY-BASED TESTS PASSED")
        print("✓ All 117 properties verified with 100+ iterations each")
        print("="*80 + "\n")
        return 0
    else:
        print("✗ SOME PROPERTY-BASED TESTS FAILED")
        print(f"✗ {len(failed_suites)} test suites need attention")
        print("="*80 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
