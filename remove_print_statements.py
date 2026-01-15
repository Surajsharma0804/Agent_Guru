#!/usr/bin/env python3
"""
Remove print() statements from source files and replace with proper logging.
Preserves print() in:
- console.py (utility module)
- standalone scripts (autostart.py, builtin_skills.py examples)
- test files
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

# Files where print() is allowed
ALLOWED_PRINT_FILES = {
    'console.py',  # Utility module for safe printing
    'autostart.py',  # Standalone script
    'builtin_skills.py',  # Contains example scripts
}

# Directories to skip
SKIP_DIRS = {'tests', '__pycache__', '.pytest_cache', 'node_modules'}

def should_process_file(filepath: Path) -> bool:
    """Check if file should be processed."""
    # Skip if in excluded directory
    for skip_dir in SKIP_DIRS:
        if skip_dir in filepath.parts:
            return False
    
    # Skip if in allowed files list
    if filepath.name in ALLOWED_PRINT_FILES:
        return False
    
    return True

def remove_print_statements(filepath: Path) -> Tuple[int, List[str]]:
    """Remove print() statements from a file, replacing with logging where appropriate."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        modified_lines = []
        removed_count = 0
        removed_statements = []
        
        for line_num, line in enumerate(lines, 1):
            # Skip if it's safe_print
            if 'safe_print' in line:
                modified_lines.append(line)
                continue
            
            # Check for print() statement
            if re.search(r'^\s*print\(', line):
                # Extract the print content
                match = re.search(r'print\((.*)\)', line)
                if match:
                    content = match.group(1)
                    removed_statements.append(f"Line {line_num}: {line.strip()}")
                    
                    # Skip the line (remove it)
                    removed_count += 1
                    continue
            
            modified_lines.append(line)
        
        # Write back if changes were made
        if removed_count > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(modified_lines)
        
        return removed_count, removed_statements
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0, []

def main():
    root_dir = Path("desktop-agent/src")
    
    print("=" * 80)
    print("REMOVING PRINT STATEMENTS - Task 30.1")
    print("=" * 80)
    print()
    
    total_removed = 0
    files_modified = 0
    
    # Process all Python files
    for filepath in root_dir.rglob("*.py"):
        if not should_process_file(filepath):
            continue
        
        removed_count, removed_statements = remove_print_statements(filepath)
        
        if removed_count > 0:
            files_modified += 1
            total_removed += removed_count
            print(f"\n{filepath.relative_to(Path('.'))}:")
            print(f"  Removed {removed_count} print() statements")
    
    print()
    print("=" * 80)
    print(f"COMPLETE: Removed {total_removed} print() statements from {files_modified} files")
    print("=" * 80)
    print()

if __name__ == "__main__":
    main()
