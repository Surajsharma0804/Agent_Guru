#!/usr/bin/env python3
"""
Test script to check dependencies of failure_detector.
"""

import sys
import os
import importlib.util

def load_module_direct(name, path):
    """Load a module directly from file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module, None
    except Exception as e:
        return None, e

# Load dependencies first
base_path = os.path.join(os.path.dirname(__file__), 'src', 'failure')

print("Loading exceptions...")
exceptions_mod, err = load_module_direct("exceptions", os.path.join(base_path, "exceptions.py"))
if err:
    print(f"Error loading exceptions: {err}")
else:
    print("✓ exceptions loaded")

print("Loading health_monitor...")
health_mod, err = load_module_direct("health_monitor", os.path.join(base_path, "health_monitor.py"))
if err:
    print(f"Error loading health_monitor: {err}")
else:
    print("✓ health_monitor loaded")

# Now try to load failure_detector with dependencies in sys.modules
if exceptions_mod:
    sys.modules['failure.exceptions'] = exceptions_mod
if health_mod:
    sys.modules['failure.health_monitor'] = health_mod

print("Loading failure_detector...")
fd_mod, err = load_module_direct("failure_detector", os.path.join(base_path, "failure_detector.py"))
if err:
    print(f"Error loading failure_detector: {err}")
    import traceback
    traceback.print_exc()
else:
    print("✓ failure_detector loaded")
    print("Available attributes:")
    for name in dir(fd_mod):
        if not name.startswith('_'):
            print(f"  {name}")