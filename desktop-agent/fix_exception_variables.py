#!/usr/bin/env python3
"""
Fix exception variable references after renaming e to _e.
"""

import os
import re
from pathlib import Path


def fix_exception_references(file_path: str) -> None:
    """Fix exception variable references in a Python file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern: except Exception as _e: followed by references to 'e' (not '_e')
    # We need to change those 'e' references back to '_e' or just use the exception inline
    
    lines = content.splitlines()
    fixed_lines = []
    in_except_block = False
    except_var = None
    
    for i, line in enumerate(lines):
        # Check if this is an except line
        if 'except' in line and ' as _e:' in line:
            in_except_block = True
            except_var = '_e'
            fixed_lines.append(line)
        elif 'except' in line and ' as e:' in line:
            # Change to _e if e is not used
            in_except_block = True
            except_var = 'e'
            fixed_lines.append(line)
        else:
            # If we're in an except block, fix references
            if in_except_block and except_var:
                # Check if line references the old variable name
                if except_var == '_e' and re.search(r'\be\b', line) and '_e' not in line:
                    # Replace 'e' with '_e' in this line
                    line = re.sub(r'\be\b', '_e', line)
                
            fixed_lines.append(line)
            
            # Check if we've exited the except block (dedented)
            if in_except_block and line and not line[0].isspace() and line.strip():
                in_except_block = False
                except_var = None
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
        if content.endswith('\n'):
            f.write('\n')


def get_python_files(directory: str) -> list:
    """Get all Python files in directory."""
    python_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.pytest_cache', '.mypy_cache']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files


def main():
    """Main function."""
    src_dir = Path(__file__).parent / 'src'
    
    print("Finding Python files...")
    python_files = get_python_files(str(src_dir))
    print(f"Found {len(python_files)} Python files")
    
    print("\nFixing exception variable references...")
    for i, file_path in enumerate(python_files, 1):
        print(f"[{i}/{len(python_files)}] Processing {file_path}")
        try:
            fix_exception_references(file_path)
        except Exception as ex:
            print(f"  ERROR: {ex}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
