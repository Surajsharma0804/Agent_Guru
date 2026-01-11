#!/usr/bin/env python3
"""Debug script to test patterns.py in isolation."""

import sys
import os

# Add the desktop-agent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop-agent'))

try:
    # Import patterns module directly without going through __init__.py
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "patterns", 
        "desktop-agent/src/intrusion/patterns.py"
    )
    patterns_module = importlib.util.module_from_spec(spec)
    
    # Execute the module
    spec.loader.exec_module(patterns_module)
    
    print("Patterns module loaded successfully!")
    print("Available attributes:", [attr for attr in dir(patterns_module) if not attr.startswith('_')])
    
    # Test specific classes
    if hasattr(patterns_module, 'FailurePatternAnalyzer'):
        print("FailurePatternAnalyzer found!")
        analyzer_class = getattr(patterns_module, 'FailurePatternAnalyzer')
        print(f"FailurePatternAnalyzer type: {type(analyzer_class)}")
    else:
        print("FailurePatternAnalyzer NOT found!")
        
    if hasattr(patterns_module, 'PatternAnalysisConfig'):
        print("PatternAnalysisConfig found!")
        config_class = getattr(patterns_module, 'PatternAnalysisConfig')
        print(f"PatternAnalysisConfig type: {type(config_class)}")
        
        # Test instantiation
        config = config_class()
        print(f"Config attributes: {config.__dict__}")
    else:
        print("PatternAnalysisConfig NOT found!")

except Exception as e:
    print(f"Error loading patterns module: {e}")
    import traceback
    traceback.print_exc()