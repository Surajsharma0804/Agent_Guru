"""
Test runner for property-based database constraint tests.

This script runs the property-based tests with appropriate settings
and generates a summary report.

Usage:
    python run_property_tests.py
"""

import sys

import pytest


def main():
    """Run property-based tests for database constraints."""
    print("=" * 80)
    print("Running Property-Based Tests for Database Integrity Constraints")
    print("=" * 80)
    print()
    print("Testing:")
    print("  - CHECK constraints (bounds, enums, relationships)")
    print("  - UNIQUE constraints (prompt_type + version)")
    print("  - Data consistency (total_executions = success_count + failure_count)")
    print("  - Edge cases and boundary conditions")
    print("  - Stateful operations (inserts, updates, deletes)")
    print()
    print("Running 100+ examples per property...")
    print()

    # Run tests with verbose output
    exit_code = pytest.main([
        "Agent_Guru/self_improvement/tests/test_database_constraints_property.py",
        "-v",
        "--tb=short",
        "--hypothesis-show-statistics",
        "-x"  # Stop on first failure
    ])

    print()
    print("=" * 80)
    if exit_code == 0:
        print("✓ All property-based tests passed!")
    else:
        print("✗ Some tests failed. See output above for details.")
    print("=" * 80)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

