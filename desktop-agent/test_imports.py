#!/usr/bin/env python3
"""
Test script to check imports for failure handling system.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_individual_imports():
    """Test importing individual modules."""
    print("Testing individual module imports...")
    
    try:
        from failure.exceptions import ComponentFailureError
        print("✓ exceptions imported")
    except Exception as e:
        print(f"✗ exceptions failed: {e}")
    
    try:
        from failure.health_monitor import ComponentHealthMonitor
        print("✓ health_monitor imported")
    except Exception as e:
        print(f"✗ health_monitor failed: {e}")
    
    try:
        from failure.failure_detector import FailureType, ComponentFailure
        print("✓ failure_detector imported")
    except Exception as e:
        print(f"✗ failure_detector failed: {e}")
    
    try:
        from failure.safe_degradation import SafeDegradationManager
        print("✓ safe_degradation imported")
    except Exception as e:
        print(f"✗ safe_degradation failed: {e}")
    
    try:
        from failure.dependency_mapper import DependencyMapper
        print("✓ dependency_mapper imported")
    except Exception as e:
        print(f"✗ dependency_mapper failed: {e}")
    
    try:
        from failure.recovery_orchestrator import RecoveryOrchestrator
        print("✓ recovery_orchestrator imported")
    except Exception as e:
        print(f"✗ recovery_orchestrator failed: {e}")
    
    try:
        from failure.system_failure_manager import SystemFailureManager
        print("✓ system_failure_manager imported")
    except Exception as e:
        print(f"✗ system_failure_manager failed: {e}")

if __name__ == "__main__":
    test_individual_imports()