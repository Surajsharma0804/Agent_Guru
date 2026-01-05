# Biometric Authentication Module
# Windows Hello and biometric provider integration

from .providers import (
    BiometricFactor,
    BiometricResult,
    BiometricProvider,
    BiometricProviderConfig,
    MockBiometricProvider,
    WindowsHelloProvider,
    BiometricProviderManager,
    create_biometric_provider_manager,
    get_default_biometric_config
)

__all__ = [
    "BiometricFactor",
    "BiometricResult", 
    "BiometricProvider",
    "BiometricProviderConfig",
    "MockBiometricProvider",
    "WindowsHelloProvider",
    "BiometricProviderManager",
    "create_biometric_provider_manager",
    "get_default_biometric_config"
]