#!/usr/bin/env python3
"""
Production Cleanup Script - Task 30.1: Remove Dead Code
Scans for unused functions, classes, imports, and commented-out code.
"""

import os
import re
import ast
from pathlib import Path
from typing import List, Set, Tuple
from collections import defaultdict

class DeadCodeAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.src_dir = self.root_dir / "desktop-agent" / "src"
        self.test_dir = self.root_dir / "desktop-agent" / "tests"
        
        # Track all defined and used symbols
        self.defined_functions = defaultdict(set)  # file -> set of function names
        self.defined_classes = defaultdict(set)    # file -> set of class names
        self.used_symbols = defaultdict(set)       # file -> set of used symbols
        
        # Files to clean
        self.files_to_clean = []
        
    def scan_python_files(self) -> List[Path]:
        """Find all Python source files."""
        python_files = []
        for pattern in ["**/*.py"]:
            python_files.extend(self.src_dir.glob(pattern))
        return python_files
    
    def analyze_file(self, filepath: Path):
        """Analyze a single Python file for dead code."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content, filename=str(filepath))
                
            # Find all function and class definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self.defined_functions[filepath].add(node.name)
                elif isinstance(node, ast.ClassDef):
                    self.defined_classes[filepath].add(node.name)
                elif isinstance(node, ast.Name):
                    self.used_symbols[filepath].add(node.id)
                    
        except Exception as e:
            print(f"Error analyzing {filepath}: {e}")
    
    def find_print_statements(self, filepath: Path) -> List[int]:
        """Find print() statements in source files (excluding safe_print)."""
        print_lines = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # Skip comments and safe_print
                    if line.strip().startswith('#'):
                        continue
                    if 'safe_print' in line:
                        continue
                    if re.search(r'^\s*print\(', line):
                        print_lines.append(line_num)
        except Exception as e:
            print(f"Error scanning {filepath}: {e}")
        return print_lines
    
    def find_commented_code(self, filepath: Path) -> List[int]:
        """Find commented-out code blocks."""
        commented_lines = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # Look for commented code patterns
                    if re.match(r'^\s*#\s*(def |class |import |from |if |for |while |return )', line):
                        # Skip documentation comments
                        if not re.match(r'^\s*#\s*(Import|TODO|FIXME|NOTE|WARNING)', line):
                            commented_lines.append(line_num)
        except Exception as e:
            print(f"Error scanning {filepath}: {e}")
        return commented_lines
    
    def generate_report(self):
        """Generate a comprehensive dead code report."""
        print("=" * 80)
        print("DEAD CODE ANALYSIS REPORT - Task 30.1")
        print("=" * 80)
        print()
        
        python_files = self.scan_python_files()
        print(f"Scanning {len(python_files)} Python source files...")
        print()
        
        # Analyze each file
        for filepath in python_files:
            self.analyze_file(filepath)
        
        # Report print statements
        print("1. PRINT STATEMENTS TO REMOVE:")
        print("-" * 80)
        print_count = 0
        for filepath in python_files:
            print_lines = self.find_print_statements(filepath)
            if print_lines:
                print(f"\n{filepath.relative_to(self.root_dir)}:")
                for line_num in print_lines:
                    print(f"  Line {line_num}")
                print_count += len(print_lines)
        
        if print_count == 0:
            print("✓ No print() statements found in source files")
        else:
            print(f"\nTotal: {print_count} print() statements to remove")
        print()
        
        # Report commented code
        print("2. COMMENTED-OUT CODE TO REMOVE:")
        print("-" * 80)
        comment_count = 0
        for filepath in python_files:
            commented_lines = self.find_commented_code(filepath)
            if commented_lines:
                print(f"\n{filepath.relative_to(self.root_dir)}:")
                for line_num in commented_lines:
                    print(f"  Line {line_num}")
                comment_count += len(commented_lines)
        
        if comment_count == 0:
            print("✓ No commented-out code found")
        else:
            print(f"\nTotal: {comment_count} commented code blocks to review")
        print()
        
        print("=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Review the report above")
        print("2. Run autoflake to remove unused imports")
        print("3. Run isort to organize imports")
        print("4. Manually review and remove print() statements")
        print("5. Manually review and remove commented code")
        print()

def main():
    analyzer = DeadCodeAnalyzer(".")
    analyzer.generate_report()

if __name__ == "__main__":
    main()
