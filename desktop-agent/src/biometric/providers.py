"""
Biometric Providers Compatibility Module

Re-exports biometric providers from biometric_authentication_providers.
"""

from .biometric_authentication_providers import *
# Also re-export BiometricFactor from authority module for compatibility
from authority.authority_state_machine import BiometricFactor