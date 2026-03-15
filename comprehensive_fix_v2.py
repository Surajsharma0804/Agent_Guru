#!/usr/bin/env python3
"""Comprehensive fix for test_failure_analyzer_property.py indentation issues"""

import re

# Read the file
with open('Agent_Guru/self_improvement/tests/test_failure_analyzer_property.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix pattern: After "try:" the next lines should be indented by 4 more spaces
# Pattern to find: try:\n<code at same or less indentation>
# Should be: try:\n<code indented 4 more spaces>

lines = content.split('\n')
fixed_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    fixed_lines.append(line)
    
    # Check if this line is "try:"
    if line.strip() == 'try:':
        try_indent = len(line) - len(line.lstrip())
        expected_body_indent = try_indent + 4
        i += 1
        
        # Process all lines until we hit "finally:" at the same level as "try:"
        while i < len(lines):
            current_line = lines[i]
            
            # Check if we hit "finally:" at try level
            if current_line.strip() == 'finally:':
                current_indent = len(current_line) - len(current_line.lstrip())
                if current_indent == try_indent:
                    # This is the matching finally
                    fixed_lines.append(current_line)
                    i += 1
                    break
            
            # Fix indentation of lines in try block
            if current_line.strip():  # Non-empty line
                current_indent = len(current_line) - len(current_line.lstrip())
                
                # If line is not indented enough, fix it
                if current_indent < expected_body_indent:
                    fixed_lines.append(' ' * expected_body_indent + current_line.lstrip())
                else:
                    fixed_lines.append(current_line)
            else:
                # Empty line
                fixed_lines.append(current_line)
            
            i += 1
        
        continue
    
    i += 1

# Write back
with open('Agent_Guru/self_improvement/tests/test_failure_analyzer_property.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed_lines))

print("Applied comprehensive indentation fixes")
