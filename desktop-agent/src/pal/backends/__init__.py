"""
PAL Backends Compatibility Module

Re-exports all platform backends from platform_abstraction_layer.
"""

# Import all platform backends
from src.platform_abstraction_layer.backends.windows import *
from src.platform_abstraction_layer.backends.macos import *
from src.platform_abstraction_layer.backends.android import *
from src.platform_abstraction_layer.backends.ios import *