#!/usr/bin/env python3
"""Simple test to check patterns module loading."""

import sys
import os

# Add the desktop-agent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop-agent'))

try:
    print("Testing direct import...")
    exec(open('desktop-agent/src/intrusion/patterns.py').read())
    print("File executed successfully!")
    
    # Check if classes are defined in local scope
    if 'FailurePatternAnalyzer' in locals():
        print("FailurePatternAnalyzer found in locals!")
    else:
        print("FailurePatternAnalyzer NOT found in locals!")
        
    if 'PatternAnalysisConfig' in locals():
        print("PatternAnalysisConfig found in locals!")
    else:
        print("PatternAnalysisConfig NOT found in locals!")

except Exception as e:
    print(f"Error executing file: {e}")
    import traceback
    traceback.print_exc()