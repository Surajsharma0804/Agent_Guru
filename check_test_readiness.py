#!/usr/bin/env python3
"""
Check if system is ready for testing.
Verifies disk space, dependencies, and configuration.
"""

import sys
from pathlib import Path


def check_disk_space() -> bool:
    """Check if sufficient disk space is available."""
    try:
        import psutil

        disk = psutil.disk_usage(".")
        free_gb = disk.free / (1024**3)

        print(f"💾 Disk Space: {free_gb:.2f} GB free")

        if free_gb < 2.0:
            print("   ❌ CRITICAL: Less than 2GB free")
            print("   ⚠️  Tests will likely crash your system")
            print("   🧹 Run: python cleanup_test_artifacts.py")
            return False
        elif free_gb < 3.0:
            print("   ⚠️  WARNING: Less than 3GB free")
            print("   💡 Recommended: Run cleanup first")
            return True
        elif free_gb < 5.0:
            print("   ✅ OK: Sufficient space for testing")
            return True
        else:
            print("   ✅ EXCELLENT: Plenty of space")
            return True
    except ImportError:
        print("💾 Disk Space: Cannot check (psutil not installed)")
        print("   💡 Install with: pip install psutil")
        return True


def check_test_directory() -> bool:
    """Check if test directory exists."""
    test_dir = Path("Agent_Guru/reasoning/tests")

    if test_dir.exists():
        test_files = list(test_dir.glob("test_*.py"))
        print(f"📁 Test Directory: Found {len(test_files)} test files")
        print("   ✅ OK")
        return True
    else:
        print("📁 Test Directory: Not found")
        print("   ❌ ERROR: Agent_Guru/reasoning/tests/ does not exist")
        return False


def check_pytest_config() -> bool:
    """Check if pytest configuration exists."""
    pytest_ini = Path("pytest.ini")

    if pytest_ini.exists():
        print("⚙️  Pytest Config: Found pytest.ini")

        # Check for space-saving settings
        content = pytest_ini.read_text()
        has_no_cache = "no:cacheprovider" in content
        has_no_db = "database = none" in content

        if has_no_cache and has_no_db:
            print("   ✅ OK: Space-saving settings enabled")
        else:
            print("   ⚠️  WARNING: Space-saving settings not optimal")

        return True
    else:
        print("⚙️  Pytest Config: Not found")
        print("   ⚠️  WARNING: Using default pytest settings")
        return True


def check_cleanup_script() -> bool:
    """Check if cleanup script exists."""
    cleanup_script = Path("cleanup_test_artifacts.py")

    if cleanup_script.exists():
        print("🧹 Cleanup Script: Found")
        print("   ✅ OK: Run with: python cleanup_test_artifacts.py")
        return True
    else:
        print("🧹 Cleanup Script: Not found")
        print("   ❌ ERROR: cleanup_test_artifacts.py missing")
        return False


def check_safe_runner() -> bool:
    """Check if safe test runner exists."""
    safe_runner = Path("run_tests_safe.py")

    if safe_runner.exists():
        print("🚀 Safe Test Runner: Found")
        print("   ✅ OK: Run with: python run_tests_safe.py")
        return True
    else:
        print("🚀 Safe Test Runner: Not found")
        print("   ❌ ERROR: run_tests_safe.py missing")
        return False


def check_hypothesis_cache() -> bool:
    """Check hypothesis cache size."""
    hypothesis_dir = Path(".hypothesis")

    if not hypothesis_dir.exists():
        print("📦 Hypothesis Cache: Not found")
        print("   ✅ OK: No cache to clean")
        return True

    try:
        total_size = 0
        file_count = 0
        for file in hypothesis_dir.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
                file_count += 1

        size_mb = total_size / (1024 * 1024)
        print(f"📦 Hypothesis Cache: {size_mb:.2f} MB ({file_count} files)")

        if size_mb > 100:
            print("   ⚠️  WARNING: Cache is large, consider cleanup")
            return True
        else:
            print("   ✅ OK")
            return True
    except (PermissionError, OSError):
        print("📦 Hypothesis Cache: Cannot check size")
        print("   ⚠️  WARNING: Permission error")
        return True


def main():
    """Run all checks."""
    print("🔍 Checking Test Readiness")
    print("=" * 60)
    print()

    checks = [
        ("Disk Space", check_disk_space()),
        ("Test Directory", check_test_directory()),
        ("Pytest Config", check_pytest_config()),
        ("Cleanup Script", check_cleanup_script()),
        ("Safe Test Runner", check_safe_runner()),
        ("Hypothesis Cache", check_hypothesis_cache()),
    ]

    print()
    print("=" * 60)
    print("📊 Summary")
    print("=" * 60)

    passed = sum(1 for _, result in checks if result)
    total = len(checks)

    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print()
    print(f"Result: {passed}/{total} checks passed")

    if passed == total:
        print()
        print("✅ System is ready for testing!")
        print()
        print("Recommended command:")
        print("  python run_tests_safe.py")
        sys.exit(0)
    else:
        print()
        print("❌ System is NOT ready for testing")
        print()
        print("Actions required:")

        if not checks[0][1]:  # Disk space
            print("  1. Free disk space: python cleanup_test_artifacts.py")
        if not checks[3][1]:  # Cleanup script
            print("  2. Cleanup script missing (critical)")
        if not checks[4][1]:  # Safe runner
            print("  3. Safe test runner missing (critical)")

        sys.exit(1)


if __name__ == "__main__":
    main()
