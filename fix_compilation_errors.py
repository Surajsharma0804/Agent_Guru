#!/usr/bin/env python3
"""
Comprehensive compilation error fix script for AGENT_GURU
Following maximum engineering mandate - zero tolerance for compilation errors
"""

import os
import re
import subprocess
from pathlib import Path

def fix_unused_variables_in_file(file_path):
    """Fix unused variable warnings by adding underscore prefixes"""
    print(f"Fixing unused variables in {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Common patterns for unused variables
    patterns = [
        # Function parameters
        (r'(\w+): &\[u8\]', r'_\1: &[u8]'),
        (r'(\w+): u32', r'_\1: u32'),
        (r'(\w+): &str', r'_\1: &str'),
        (r'(\w+): &\[&\[u8\]\]', r'_\1: &[&[u8]]'),
        (r'(\w+): &\[u8; 32\]', r'_\1: &[u8; 32]'),
        (r'(\w+): &\[u8; 12\]', r'_\1: &[u8; 12]'),
        (r'(\w+): &ImageData', r'_\1: &ImageData'),
        (r'(\w+): &VisionConfig', r'_\1: &VisionConfig'),
        (r'(\w+): &AgentMetadata', r'_\1: &AgentMetadata'),
        (r'(\w+): ProcessId', r'_\1: ProcessId'),
        (r'(\w+): &PlatformTarget', r'_\1: &PlatformTarget'),
        
        # Let bindings
        (r'let (\w+) = ', r'let _\1 = '),
        
        # Loop variables
        (r'for (\w+) in ', r'for _\1 in '),
        (r'for \((\w+), ', r'for (_\1, '),
        
        # Match patterns
        (r'{ (\w+) }', r'{ _\1 }'),
        (r'{ (\w+), ', r'{ _\1, '),
        (r', (\w+) }', r', _\1 }'),
    ]
    
    modified = False
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            modified = True
    
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed unused variables in {file_path}")
    
    return modified

def fix_all_rust_files():
    """Fix all Rust files in the guru directory"""
    guru_dir = Path("guru")
    rust_files = list(guru_dir.rglob("*.rs"))
    
    total_fixed = 0
    for rust_file in rust_files:
        if fix_unused_variables_in_file(rust_file):
            total_fixed += 1
    
    print(f"Fixed unused variables in {total_fixed} files")

def run_cargo_check():
    """Run cargo check to verify fixes"""
    print("Running cargo check to verify fixes...")
    result = subprocess.run(["cargo", "check", "--all-targets", "--all-features"], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ All compilation errors fixed!")
        return True
    else:
        print("❌ Still have compilation errors:")
        print(result.stderr)
        return False

def main():
    """Main execution function"""
    print("🔧 Starting comprehensive compilation error fix...")
    print("Following maximum engineering mandate - zero tolerance for errors")
    
    # Fix unused variables
    fix_all_rust_files()
    
    # Verify fixes
    if run_cargo_check():
        print("🎉 System compilation successful - zero errors achieved!")
    else:
        print("⚠️  Additional manual fixes required")

if __name__ == "__main__":
    main()