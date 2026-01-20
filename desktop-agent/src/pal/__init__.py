"""
Platform Abstraction Layer (PAL) - Compatibility Module

This module provides backward compatibility for imports expecting 'pal'.
All functionality is implemented in 'platform_abstraction_layer'.
"""

# Re-export all public symbols from the actual implementation
from src.platform_abstraction_layer.interfaces import *
from src.platform_abstraction_layer.backend_factory import *
from src.platform_abstraction_layer.capability_matrix import *
from src.platform_abstraction_layer.platform_detector import *

# Import backends
from src.platform_abstraction_layer.backends import *