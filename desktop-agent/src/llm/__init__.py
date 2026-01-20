"""
LLM Compatibility Module

This module provides backward compatibility for imports expecting 'llm'.
All functionality is implemented in 'language_model'.
"""

# Re-export all public symbols from the actual implementation
from ..language_model import *