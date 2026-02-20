#!/usr/bin/env python3
"""
Cleanup script to free disk space before running tests.
Removes test artifacts, caches, and temporary files.
"""

import shutil
import os
from pathlib import Path


def get_size_mb(path: Path) -> float:
    """Get size of directory in MB."""
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except (PermissionError, OSError):
        pass
    return total / (1024 * 1024)


def cleanup_directory(path: Path, description: str) -> None:
    """Remove directory and report space freed."""
    if not path.exists():
        print(f"✓ {description}: Not found (already clean)")
        return
    
    size_mb = get_size_mb(path)
    try:
        shutil.rmtree(path)
        print(f"✓ {description}: Freed {size_mb:.2f} MB")
    except (PermissionError, OSError) as e:
        print(f"✗ {description}: Failed to remove ({e})")


def cleanup_files(pattern: str, description: str) -> None:
    """Remove files matching pattern."""
    count = 0
    size_mb = 0
    
    for path in Path('.').rglob(pattern):
        if path.is_file():
            try:
                size_mb += path.stat().st_size / (1024 * 1024)
                path.unlink()
                count += 1
            except (PermissionError, OSError):
                pass
    
    if count > 0:
        print(f"✓ {description}: Removed {count} files, freed {size_mb:.2f} MB")
    else:
        print(f"✓ {description}: No files found")


def main():
    """Run cleanup operations."""
    print("🧹 Cleaning up test artifacts and caches...\n")
    
    # Hypothesis cache (can grow large with examples)
    cleanup_directory(Path('.hypothesis'), 'Hypothesis cache')
    
    # Pytest cache
    cleanup_directory(Path('.pytest_cache'), 'Pytest cache')
    
    # Python cache
    cleanup_files('**/__pycache__', 'Python bytecode cache')
    cleanup_files('**/*.pyc', 'Python compiled files')
    cleanup_files('**/*.pyo', 'Python optimized files')
    
    # Coverage reports
    cleanup_directory(Path('htmlcov'), 'Coverage HTML reports')
    cleanup_files('.coverage*', 'Coverage data files')
    
    # MyPy cache
    cleanup_directory(Path('.mypy_cache'), 'MyPy cache')
    
    # Ruff cache
    cleanup_directory(Path('.ruff_cache'), 'Ruff cache')
    
    # Build artifacts
    cleanup_directory(Path('build'), 'Build directory')
    cleanup_directory(Path('dist'), 'Distribution directory')
    cleanup_files('**/*.egg-info', 'Egg info directories')
    
    # Temporary files
    cleanup_files('**/*.tmp', 'Temporary files')
    cleanup_files('**/*.log', 'Log files')
    
    print("\n✅ Cleanup complete!")
    
    # Show remaining space
    try:
        import psutil
        disk = psutil.disk_usage('.')
        free_gb = disk.free / (1024 ** 3)
        print(f"\n💾 Free disk space: {free_gb:.2f} GB")
    except ImportError:
        print("\n💡 Install psutil to see disk space: pip install psutil")


if __name__ == '__main__':
    main()
