#!/usr/bin/env python3
"""Comprehensive fix for test_failure_analyzer_property.py"""

import re

# Read the file
with open('Agent_Guru/self_improvement/tests/test_failure_analyzer_property.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Process line by line
fixed_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    
    # Pattern 1: Fix docstring followed by code on same indentation level
    # Look for: """docstring"""\n\n        analyzer, pool, tmpdir = create_fresh_analyzer()
    if '"""' in line and line.strip().endswith('"""'):
        # This is end of docstring
        fixed_lines.append(line)
        i += 1
        
        # Skip empty lines
        while i < len(lines) and not lines[i].strip():
            fixed_lines.append(lines[i])
            i += 1
        
        # Check if next line is analyzer, pool, tmpdir = create_fresh_analyzer()
        if i < len(lines) and 'analyzer, pool, tmpdir = create_fresh_analyzer()' in lines[i]:
            # This should be indented at function body level (8 spaces typically)
            # Keep it as is
            fixed_lines.append(lines[i])
            i += 1
            
            # Next should be try:
            if i < len(lines) and lines[i].strip() == 'try:':
                fixed_lines.append(lines[i])
                i += 1
                
                # Now we need to ensure everything until finally: is indented properly
                try_indent = len(lines[i-1]) - len(lines[i-1].lstrip())
                body_indent = try_indent + 4
                
                # Process try block body
                while i < len(lines):
                    current_line = lines[i]
                    
                    # Check if we hit finally:
                    if current_line.strip() == 'finally:':
                        # Make sure finally is at same level as try
                        fixed_lines.append(' ' * try_indent + 'finally:\n')
                        i += 1
                        break
                    
                    # Check if line needs indentation fix
                    if current_line.strip():
                        current_indent = len(current_line) - len(current_line.lstrip())
                        
                        # If line is not indented enough, fix it
                        if current_indent < body_indent:
                            fixed_lines.append(' ' * body_indent + current_line.lstrip())
                        else:
                            fixed_lines.append(current_line)
                    else:
                        fixed_lines.append(current_line)
                    
                    i += 1
                
                continue
        
        continue
    
    # Default: keep line as is
    fixed_lines.append(line)
    i += 1

# Write back
with open('Agent_Guru/self_improvement/tests/test_failure_analyzer_property.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print("Applied comprehensive fixes")
