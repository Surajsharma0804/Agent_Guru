#!/usr/bin/env python3
"""
Comprehensive Property Test Execution Script
Runs all 117 property tests and generates detailed report
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# All property test files in execution order
PROPERTY_TEST_FILES = [
    # PAL and Platform Tests (38 tests)
    ("test_pal_properties.py", "PAL Interface Properties", 38),
    ("test_platform_detection_properties.py", "Platform Detection Properties", 3),
    ("test_capability_matrix_properties.py", "Capability Matrix Properties", 1),
    
    # Core Logic Tests (13 tests)
    ("test_core_logic_refactoring_properties.py", "Core Logic Refactoring Properties", 6),
    ("test_authority_state_machine_properties.py", "Authority State Machine Properties", 9),
    ("test_authority_scope_properties.py", "Authority Scope Properties", 4),
    
    # Security Tests (17 tests)
    ("test_intrusion_detection_properties.py", "Intrusion Detection Properties", 4),
    ("test_audit_logging_properties.py", "Audit Logging Properties", 8),
    ("test_permission_model_properties.py", "Permission Model Properties", 3),
    ("test_skill_permission_properties.py", "Skill Permission Properties", 2),
    
    # Voice and Command Tests (18 tests)
    ("test_wake_word_stripping_properties.py", "Wake Word Stripping Properties", 4),
    ("test_dictation_mode_properties.py", "Dictation Mode Properties", 3),
    ("test_exact_text_dictation_properties.py", "Exact Text Dictation Properties", 3),
    ("test_response_ownership_properties.py", "Response Ownership Properties", 5),
    ("test_deterministic_first_properties.py", "Deterministic-First Properties", 4),
    ("test_speech_contract_properties.py", "Speech Contract Properties", 5),
    
    # Command Execution Tests (4 tests)
    ("test_whatsapp_automation_properties.py", "WhatsApp Automation Properties", 4),
    
    # System Tests (21 tests)
    ("test_llm_adapter_properties.py", "LLM Adapter Properties", 3),
    ("test_tts_service_properties.py", "TTS Service Properties", 4),
    ("test_memory_system_properties.py", "Memory System Properties", 7),
    ("test_failure_orchestrator_properties.py", "Failure Orchestrator Properties", 5),
    ("test_thread_safety_properties.py", "Thread Safety Properties", 2),
    ("test_error_handling_properties.py", "Error Handling Properties", 4),
    
    # Platform Backend Tests (13 tests)
    ("test_macos_backend_properties.py", "macOS Backend Properties", 5),
    ("test_android_backend_properties.py", "Android Backend Properties", 4),
    ("test_ios_backend_properties.py", "iOS Backend Properties", 4),
]

def run_test_file(test_file, description, expected_tests):
    """Run a single test file and return results"""
    print(f"\n{'='*80}")
    print(f"Running: {description}")
    print(f"File: {test_file}")
    print(f"Expected Tests: {expected_tests}")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", f"tests/{test_file}", 
             "-v", "--tb=short", "--no-cov", "-q"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout per file
        )
        
        elapsed_time = time.time() - start_time
        
        # Parse output for pass/fail counts
        output = result.stdout + result.stderr
        passed = output.count(" PASSED")
        failed = output.count(" FAILED")
        skipped = output.count(" SKIPPED")
        
        status = "✅ PASS" if result.returncode == 0 else "❌ FAIL"
        
        return {
            "file": test_file,
            "description": description,
            "expected": expected_tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "status": status,
            "time": elapsed_time,
            "returncode": result.returncode,
            "output": output
        }
        
    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        return {
            "file": test_file,
            "description": description,
            "expected": expected_tests,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "status": "⏱️ TIMEOUT",
            "time": elapsed_time,
            "returncode": -1,
            "output": "Test execution timed out after 120 seconds"
        }
    except Exception as e:
        elapsed_time = time.time() - start_time
        return {
            "file": test_file,
            "description": description,
            "expected": expected_tests,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "status": "❌ ERROR",
            "time": elapsed_time,
            "returncode": -1,
            "output": f"Error running test: {str(e)}"
        }

def main():
    """Run all property tests and generate report"""
    print("\n" + "="*80)
    print("GURU PROPERTY TEST SUITE - COMPREHENSIVE EXECUTION")
    print("="*80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Test Files: {len(PROPERTY_TEST_FILES)}")
    print(f"Expected Total Tests: {sum(t[2] for t in PROPERTY_TEST_FILES)}")
    print("="*80)
    
    results = []
    total_start = time.time()
    
    for test_file, description, expected_tests in PROPERTY_TEST_FILES:
        result = run_test_file(test_file, description, expected_tests)
        results.append(result)
        
        # Print immediate result
        print(f"\n{result['status']} {result['description']}")
        print(f"   Passed: {result['passed']}/{result['expected']}, "
              f"Failed: {result['failed']}, Skipped: {result['skipped']}, "
              f"Time: {result['time']:.2f}s")
    
    total_time = time.time() - total_start
    
    # Generate summary report
    print("\n" + "="*80)
    print("EXECUTION SUMMARY")
    print("="*80)
    
    total_passed = sum(r['passed'] for r in results)
    total_failed = sum(r['failed'] for r in results)
    total_skipped = sum(r['skipped'] for r in results)
    total_expected = sum(r['expected'] for r in results)
    
    files_passed = sum(1 for r in results if r['status'] == "✅ PASS")
    files_failed = sum(1 for r in results if r['status'] == "❌ FAIL")
    files_timeout = sum(1 for r in results if r['status'] == "⏱️ TIMEOUT")
    files_error = sum(1 for r in results if r['status'] == "❌ ERROR")
    
    print(f"\nTest Files:")
    print(f"  ✅ Passed: {files_passed}/{len(results)}")
    print(f"  ❌ Failed: {files_failed}/{len(results)}")
    print(f"  ⏱️ Timeout: {files_timeout}/{len(results)}")
    print(f"  ❌ Error: {files_error}/{len(results)}")
    
    print(f"\nIndividual Tests:")
    print(f"  ✅ Passed: {total_passed}/{total_expected}")
    print(f"  ❌ Failed: {total_failed}/{total_expected}")
    print(f"  ⏸️ Skipped: {total_skipped}/{total_expected}")
    
    print(f"\nExecution Time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Detailed results
    print("\n" + "="*80)
    print("DETAILED RESULTS")
    print("="*80)
    
    for result in results:
        print(f"\n{result['status']} {result['description']}")
        print(f"   File: {result['file']}")
        print(f"   Tests: {result['passed']}/{result['expected']} passed, "
              f"{result['failed']} failed, {result['skipped']} skipped")
        print(f"   Time: {result['time']:.2f}s")
        
        if result['failed'] > 0 or result['status'] != "✅ PASS":
            print(f"   Output Preview:")
            lines = result['output'].split('\n')
            for line in lines[-20:]:  # Last 20 lines
                if line.strip():
                    print(f"      {line}")
    
    # Save detailed report
    report_path = Path(__file__).parent / "PROPERTY_TEST_EXECUTION_REPORT.md"
    with open(report_path, 'w') as f:
        f.write("# GURU Property Test Execution Report\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total Execution Time**: {total_time:.2f}s ({total_time/60:.1f} minutes)\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- **Test Files**: {files_passed}/{len(results)} passed\n")
        f.write(f"- **Individual Tests**: {total_passed}/{total_expected} passed\n")
        f.write(f"- **Failed Tests**: {total_failed}\n")
        f.write(f"- **Skipped Tests**: {total_skipped}\n\n")
        
        f.write("## Detailed Results\n\n")
        for result in results:
            f.write(f"### {result['status']} {result['description']}\n\n")
            f.write(f"- **File**: `{result['file']}`\n")
            f.write(f"- **Tests**: {result['passed']}/{result['expected']} passed, "
                   f"{result['failed']} failed, {result['skipped']} skipped\n")
            f.write(f"- **Time**: {result['time']:.2f}s\n")
            f.write(f"- **Return Code**: {result['returncode']}\n\n")
            
            if result['failed'] > 0 or result['status'] != "✅ PASS":
                f.write("**Output**:\n```\n")
                f.write(result['output'][-2000:])  # Last 2000 chars
                f.write("\n```\n\n")
    
    print(f"\n✅ Detailed report saved to: {report_path}")
    
    # Exit with appropriate code
    if files_failed > 0 or files_error > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
