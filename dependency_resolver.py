#!/usr/bin/env python3

import sys
import os
import inspect

# Add the desktop-agent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop-agent'))

try:
    from src.intrusion.patterns import PatternAnalysisConfig
    
    print("PatternAnalysisConfig imported successfully")
    print(f"Class location: {PatternAnalysisConfig.__module__}")
    print(f"Class file: {inspect.getfile(PatternAnalysisConfig)}")
    
    # Get the __init__ method signature
    init_signature = inspect.signature(PatternAnalysisConfig.__init__)
    print(f"__init__ parameters: {list(init_signature.parameters.keys())}")
    
    # Print the source code of __init__ method
    try:
        source = inspect.getsource(PatternAnalysisConfig.__init__)
        print("__init__ source code:")
        print(source[:500] + "..." if len(source) > 500 else source)
    except Exception as e:
        print(f"Could not get source: {e}")
        
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()