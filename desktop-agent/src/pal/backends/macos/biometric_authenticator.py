"""macOS Biometric Authenticator stub. Will be implemented in Task 4."""
from typing import List, Dict
from ...interfaces import BiometricAuthenticator, AuthResult

class macOSBiometricAuthenticator(BiometricAuthenticator):
    def authenticate(self, reason: str) -> AuthResult:
        raise NotImplementedError("macOSBiometricAuthenticator will be implemented in Task 4")
    def is_available(self) -> bool:
        raise NotImplementedError("macOSBiometricAuthenticator will be implemented in Task 4")
    def get_available_factors(self) -> List[str]:
        raise NotImplementedError("macOSBiometricAuthenticator will be implemented in Task 4")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'has_fingerprint': False, 'has_face': False, 'has_iris': False, 'is_configured': False}
