#!/usr/bin/env python3
"""
Automated lint error fixer for GURU Desktop Agent.
Fixes all flake8 errors systematically.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import List, Tuple


def remove_unused_imports(file_path: str) -> None:
    """Remove unused imports from a Python file."""
    try:
        subprocess.run(
            ["autoflake", "--in-place", "--remove-all-unused-imports", file_path],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError:
        pass


def fix_trailing_whitespace(file_path: str) -> None:
    """Remove trailing whitespace from a Python file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove trailing whitespace from each line
    lines = content.splitlines()
    fixed_lines = [line.rstrip() for line in lines]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
        if content.endswith('\n'):
            f.write('\n')


def fix_blank_line_whitespace(file_path: str) -> None:
    """Remove whitespace from blank lines."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace blank lines with whitespace with truly blank lines
    content = re.sub(r'^\s+$', '', content, flags=re.MULTILINE)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def fix_bare_except(file_path: str) -> None:
    """Fix bare except clauses."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace bare except with except Exception
    content = re.sub(r'except\s*:', 'except Exception:', content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def fix_fstring_placeholders(file_path: str) -> None:
    """Fix f-strings without placeholders."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for line in lines:
        # Find f-strings without placeholders and convert to regular strings
        if 'f"' in line or "f'" in line:
            # Check if there are no {} in the string
            if '{' not in line:
                line = line.replace('f"', '"').replace("f'", "'")
        fixed_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)


def fix_escape_sequences(file_path: str) -> None:
    """Fix invalid escape sequences in strings."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix common invalid escape sequences
    content = content.replace(r'\.', r'\\.')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def fix_unused_variables(file_path: str) -> None:
    """Prefix unused variables with underscore."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for line in lines:
        # Fix "except Exception as e:" where e is unused
        if 'except' in line and ' as e:' in line:
            line = line.replace(' as e:', ' as _e:')
        # Fix other unused variable assignments
        elif ' = ' in line and 'local variable' not in line:
            # This is a simple heuristic - may need manual review
            pass
        fixed_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)


def get_python_files(directory: str) -> List[str]:
    """Get all Python files in directory."""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ and other cache directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.pytest_cache', '.mypy_cache', 'venv', 'env']]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files


def main():
    """Main function to fix all lint errors."""
    src_dir = Path(__file__).parent / 'src'
    
    print("Finding Python files...")
    python_files = get_python_files(str(src_dir))
    print(f"Found {len(python_files)} Python files")
    
    print("\nFixing lint errors...")
    for i, file_path in enumerate(python_files, 1):
        print(f"[{i}/{len(python_files)}] Processing {file_path}")
        
        try:
            # Apply fixes in order
            remove_unused_imports(file_path)
            fix_trailing_whitespace(file_path)
            fix_blank_line_whitespace(file_path)
            fix_bare_except(file_path)
            fix_fstring_placeholders(file_path)
            fix_unused_variables(file_path)
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\nRunning black formatter...")
    subprocess.run(["black", str(src_dir)], check=False)
    
    print("\nRunning isort...")
    subprocess.run(["isort", str(src_dir)], check=False)
    
    print("\nDone! Please run flake8 again to verify.")


if __name__ == "__main__":
    main()
