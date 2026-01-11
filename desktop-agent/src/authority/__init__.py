# Authority Management Module
# Core security and authorization components

from .biometric_integration import (
    BiometricAuthorityVerificationEngine,
    BiometricVerificationBoundaries,
    BiometricVerificationBoundaryViolation,
    create_biometric_authority_verification_engine,
)
from .state import (
    AuthorityConfiguration,
    AuthorityState,
    AuthorityStateMachine,
    create_authority_state_machine,
    get_default_authority_config,
)

__all__ = [
    "AuthorityState",
    "AuthorityConfiguration",
    "AuthorityStateMachine",
    "create_authority_state_machine",
    "get_default_authority_config",
    "BiometricVerificationBoundaryViolation",
    "BiometricVerificationBoundaries",
    "BiometricAuthorityVerificationEngine",
    "create_biometric_authority_verification_engine",
]
