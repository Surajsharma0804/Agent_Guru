#!/usr/bin/env python3
"""
Test script to check failure_detector imports.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import the module directly
import failure.failure_detector as fd

print("Available classes and functions:")
for name in dir(fd):
    if not name.startswith('_'):
        obj = getattr(fd, name)
        print(f"  {name}: {type(obj)}")

# Try to access specific classes
try:
    print(f"FailureType: {fd.FailureType}")
    print(f"FailureSeverity: {fd.FailureSeverity}")
    print(f"ComponentFailure: {fd.ComponentFailure}")
    print(f"FailureDetector: {fd.FailureDetector}")
except AttributeError as e:
    print(f"AttributeError: {e}")