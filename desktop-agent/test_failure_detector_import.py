#!/usr/bin/env python3

import sys
import traceback

sys.path.append('.')

try:
    print("Testing failure_detector import...")
    import src.failure.failure_detector as fd
    print("Import successful")
    print(f"Module attributes: {[x for x in dir(fd) if not x.startswith('_')]}")
    print(f"Has FailureDetector: {hasattr(fd, 'FailureDetector')}")
    
    if hasattr(fd, 'FailureDetector'):
        print("FailureDetector class found!")
    else:
        print("FailureDetector class NOT found")
        
except Exception as e:
    print(f"Import failed: {e}")
    print("Full traceback:")
    traceback.print_exc()