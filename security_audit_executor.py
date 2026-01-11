#!/usr/bin/env python3
"""Detailed debug to find the exact issue."""

import sys
import os
import traceback

# Add the desktop-agent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop-agent'))

print("Starting detailed execution test...")

try:
    # Read the file content
    with open('desktop-agent/src/intrusion/patterns.py', 'r') as f:
        content = f.read()
    
    print(f"File read successfully, {len(content)} characters")
    
    # Create a custom globals dict to track what gets defined
    custom_globals = {
        '__name__': '__main__',
        '__file__': 'desktop-agent/src/intrusion/patterns.py'
    }
    
    # Execute line by line to find where it fails
    lines = content.split('\n')
    current_line = 0
    
    try:
        exec(content, custom_globals)
        print("File executed successfully!")
        
        # Check what was defined
        defined_classes = [name for name, obj in custom_globals.items() 
                          if isinstance(obj, type) and not name.startswith('_')]
        defined_enums = [name for name, obj in custom_globals.items() 
                        if hasattr(obj, '__class__') and 'Enum' in str(obj.__class__) and not name.startswith('_')]
        
        print(f"Defined classes: {defined_classes}")
        print(f"Defined enums: {defined_enums}")
        print(f"All custom globals: {[k for k in custom_globals.keys() if not k.startswith('_')]}")
        
        # Check specific classes
        if 'FailurePatternAnalyzer' in custom_globals:
            print("FailurePatternAnalyzer found!")
            print(f"Type: {type(custom_globals['FailurePatternAnalyzer'])}")
        
        if 'PatternAnalysisConfig' in custom_globals:
            print("PatternAnalysisConfig found!")
            print(f"Type: {type(custom_globals['PatternAnalysisConfig'])}")
            
        # Test instantiation
        if 'PatternAnalysisConfig' in custom_globals:
            config_class = custom_globals['PatternAnalysisConfig']
            config = config_class()
            print(f"Config created successfully: {type(config)}")
            print(f"Config attributes: {list(config.__dict__.keys())[:5]}...")  # First 5 attributes
        
    except Exception as e:
        print(f"Execution failed at some point: {e}")
        traceback.print_exc()

except Exception as e:
    print(f"Failed to read or execute file: {e}")
    traceback.print_exc()