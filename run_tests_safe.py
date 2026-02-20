#!/usr/bin/env python3
"""
Safe test runner that monitors disk space and prevents system crashes.
Runs tests in batches and cleans up between runs.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional


def get_free_space_gb() -> float:
    """Get free disk space in GB."""
    try:
        import psutil
        disk = psutil.disk_usage('.')
        return disk.free / (1024 ** 3)
    except ImportError:
        print("⚠️  Warning: psutil not installed, cannot monitor disk space")
        print("   Install with: pip install psutil")
        return 999.0  # Assume enough space


def cleanup_artifacts() -> None:
    """Run cleanup script to free space."""
    print("\n🧹 Running cleanup...")
    subprocess.run([sys.executable, 'cleanup_test_artifacts.py'], check=False)


def run_test_batch(test_files: List[str], min_space_gb: float = 2.0) -> bool:
    """
    Run a batch of tests with space monitoring.
    
    Args:
        test_files: List of test file paths
        min_space_gb: Minimum free space required (GB)
    
    Returns:
        True if tests passed, False otherwise
    """
    # Check space before running
    free_space = get_free_space_gb()
    if free_space < min_space_gb:
        print(f"\n❌ Insufficient disk space: {free_space:.2f} GB free")
        print(f"   Need at least {min_space_gb:.2f} GB")
        print("\n🧹 Running cleanup to free space...")
        cleanup_artifacts()
        
        free_space = get_free_space_gb()
        if free_space < min_space_gb:
            print(f"\n❌ Still insufficient space after cleanup: {free_space:.2f} GB")
            return False
    
    print(f"\n💾 Free space: {free_space:.2f} GB")
    print(f"📝 Running {len(test_files)} test files...")
    
    # Run tests without coverage to save space
    cmd = [
        sys.executable, '-m', 'pytest',
        '-v',
        '--tb=short',
        '--disable-warnings',
        '-p', 'no:cacheprovider',  # Disable cache
        '--hypothesis-show-statistics',
        *test_files
    ]
    
    result = subprocess.run(cmd, check=False)
    return result.returncode == 0


def discover_test_files() -> List[str]:
    """Discover all test files."""
    test_dir = Path('Agent_Guru/reasoning/tests')
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        return []
    
    test_files = list(test_dir.glob('test_*.py'))
    return [str(f) for f in sorted(test_files)]


def main():
    """Run tests safely with space monitoring."""
    print("🚀 Safe Test Runner for Agent Guru")
    print("=" * 60)
    
    # Initial cleanup
    cleanup_artifacts()
    
    # Discover tests
    test_files = discover_test_files()
    if not test_files:
        print("\n❌ No test files found")
        sys.exit(1)
    
    print(f"\n📋 Found {len(test_files)} test files")
    
    # Group tests into small batches to avoid space issues
    batch_size = 3  # Run 3 test files at a time
    batches = [test_files[i:i+batch_size] for i in range(0, len(test_files), batch_size)]
    
    print(f"📦 Running in {len(batches)} batches of {batch_size} files each")
    
    failed_batches = []
    
    for i, batch in enumerate(batches, 1):
        print(f"\n{'=' * 60}")
        print(f"📦 Batch {i}/{len(batches)}")
        print(f"{'=' * 60}")
        
        success = run_test_batch(batch, min_space_gb=2.0)
        
        if not success:
            failed_batches.append(i)
            print(f"\n❌ Batch {i} failed")
        else:
            print(f"\n✅ Batch {i} passed")
        
        # Cleanup between batches
        if i < len(batches):
            print("\n🧹 Cleaning up before next batch...")
            cleanup_artifacts()
            time.sleep(1)  # Brief pause
    
    # Final summary
    print(f"\n{'=' * 60}")
    print("📊 Test Summary")
    print(f"{'=' * 60}")
    print(f"Total batches: {len(batches)}")
    print(f"Passed: {len(batches) - len(failed_batches)}")
    print(f"Failed: {len(failed_batches)}")
    
    if failed_batches:
        print(f"\n❌ Failed batches: {', '.join(map(str, failed_batches))}")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()
