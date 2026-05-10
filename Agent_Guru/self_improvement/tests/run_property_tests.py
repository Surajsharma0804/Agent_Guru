"""Test runner for property-based database constraint tests.

This script runs the property-based tests with appropriate settings
and generates a summary report.

Usage:
    python run_property_tests.py
"""

import sys

import pytest


def main():
    """Run property-based tests for database constraints."""
    # Run tests with verbose output
    exit_code = pytest.main(
        [
            "Agent_Guru/self_improvement/tests/test_database_constraints_property.py",
            "-v",
            "--tb=short",
            "--hypothesis-show-statistics",
            "-x",  # Stop on first failure
        ],
    )

    if exit_code == 0:
        pass
    else:
        pass

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
