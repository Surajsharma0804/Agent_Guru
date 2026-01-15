#!/usr/bin/env python3
"""
Comprehensive lint fixer for GURU Desktop Agent.
Fixes all remaining flake8 errors systematically.
"""

import os
import re
from pathlib import Path
from typing import List


def fix_exception_variables(file_path: str) -> None:
    """Fix exception variable issues - either use them or remove them."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace 'except Exception as _e:' with 'except Exception:'
    # since _e is marked as unused
    content = re.sub(r'except\s+(\w+)\s+as\s+_e:', r'except \1:', content)
    
    # Replace references to undefined 'e' with proper exception handling
    # This is a bit tricky - we need to look at context
    lines = content.splitlines()
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # If line has 'except Exception:' and next lines reference 'e'
        if 'except Exception:' in line:
            fixed_lines.append(line)
            # Look ahead to see if there are references to 'e'
            # If so, change the except line to capture it
            j = i + 1
            has_e_reference = False
            while j < len(lines) and lines[j].startswith(' ' * (len(line) - len(line.lstrip()) + 4)):
                if re.search(r'\be\b', lines[j]) and 'except' not in lines[j]:
                    has_e_reference = True
                    break
                j += 1
            
            if has_e_reference:
                # Change the except line we just added
                fixed_lines[-1] = line.replace('except Exception:', 'except Exception as e:')
        else:
            fixed_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
        if content.endswith('\n'):
            f.write('\n')


def fix_redefined_names(file_path: str) -> None:
    """Fix redefined names by removing duplicate definitions."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Track class/function definitions
    seen_definitions = {}
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # Check for class or function definition
        match = re.match(r'^(class|def)\s+(\w+)', line)
        if match:
            def_type, name = match.groups()
            if name in seen_definitions:
                # Skip this redefinition
                # Find the end of this definition and skip it
                indent = len(line) - len(line.lstrip())
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if next_line.strip() and not next_line.startswith(' ' * (indent + 1)):
                        break
                    j += 1
                # Skip from i to j
                continue
            else:
                seen_definitions[name] = i
        
        fixed_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)


def fix_module_imports(file_path: str) -> None:
    """Fix module level imports not at top of file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Separate imports from rest of code
    imports = []
    docstring_lines = []
    other_lines = []
    
    in_docstring = False
    docstring_char = None
    past_docstring = False
    
    for i, line in enumerate(lines):
        # Handle module docstring
        if i == 0 or (i < 5 and not past_docstring):
            if '"""' in line or "'''" in line:
                if not in_docstring:
                    in_docstring = True
                    docstring_char = '"""' if '"""' in line else "'''"
                    docstring_lines.append(line)
                    if line.count(docstring_char) >= 2:
                        in_docstring = False
                        past_docstring = True
                    continue
                else:
                    docstring_lines.append(line)
                    if docstring_char in line:
                        in_docstring = False
                        past_docstring = True
                    continue
            elif in_docstring:
                docstring_lines.append(line)
                continue
        
        # Check if this is an import line
        if line.strip().startswith(('import ', 'from ')) and not line.strip().startswith('#'):
            imports.append(line)
        else:
            other_lines.append(line)
            past_docstring = True
    
    # Reconstruct file with imports at top
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(docstring_lines)
        if docstring_lines and not docstring_lines[-1].endswith('\n\n'):
            f.write('\n')
        f.writelines(imports)
        if imports:
            f.write('\n')
        f.writelines(other_lines)


def fix_escape_sequences(file_path: str) -> None:
    """Fix invalid escape sequences."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix invalid escape sequences in regex patterns
    # Look for strings with \. and make them raw strings
    lines = content.splitlines()
    fixed_lines = []
    
    for line in lines:
        # If line has a string with \. make it a raw string
        if r'\.' in line and not line.strip().startswith('#'):
            # Check if it's in a string
            if '"' in line or "'" in line:
                # Add r prefix to strings with \.
                line = re.sub(r'(["\'])([^"\']*\\\.)', r'r\1\2', line)
        fixed_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
        if content.endswith('\n'):
            f.write('\n')


def get_python_files(directory: str) -> List[str]:
    """Get all Python files in directory."""
    python_files = []
    for root, dirs, files in os.walk(directory):
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
    
    print("\nFixing exception variables...")
    for i, file_path in enumerate(python_files, 1):
        if i % 20 == 0:
            print(f"  [{i}/{len(python_files)}] Processed...")
        try:
            fix_exception_variables(file_path)
        except Exception as ex:
            print(f"  ERROR in {file_path}: {ex}")
    
    print("\nFixing redefined names...")
    for file_path in python_files:
        try:
            fix_redefined_names(file_path)
        except Exception as ex:
            print(f"  ERROR in {file_path}: {ex}")
    
    print("\nFixing escape sequences...")
    for file_path in python_files:
        try:
            fix_escape_sequences(file_path)
        except Exception as ex:
            print(f"  ERROR in {file_path}: {ex}")
    
    print("\nRunning black formatter...")
    os.system(f'black "{src_dir}"')
    
    print("\nDone! Run flake8 to verify.")


if __name__ == "__main__":
    main()
