#!/usr/bin/env python3
"""Quick test of diagnostic functions."""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("Testing diagnostic imports...")

try:
    from run_diagnostics import (
        DiagnosticRunner,
        test_platform_detection,
        test_pal_backend_factory,
        test_configuration_integrity
    )
    print("✓ All imports successful")
    
    print("\nRunning quick platform detection test...")
    runner = DiagnosticRunner()
    result = runner.run_test("Platform Detection", test_platform_detection)
    
    print(f"\nTest result: {result.status.value}")
    print(f"Message: {result.message}")
    
    if result.status.value == "PASS":
        print("\n✓ Diagnostic system is working correctly")
        sys.exit(0)
    else:
        print("\n✗ Diagnostic test failed")
        sys.exit(1)
        
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
