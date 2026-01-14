"""iOS Biometric Authenticator stub. Will be implemented in Task 6."""
from typing import List, Dict
from ...interfaces import BiometricAuthenticator, AuthResult

class iOSBiometricAuthenticator(BiometricAuthenticator):
    def authenticate(self, reason: str) -> AuthResult:
        raise NotImplementedError("iOSBiometricAuthenticator will be implemented in Task 6")
    def is_available(self) -> bool:
        raise NotImplementedError("iOSBiometricAuthenticator will be implemented in Task 6")
    def get_available_factors(self) -> List[str]:
        raise NotImplementedError("iOSBiometricAuthenticator will be implemented in Task 6")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'has_fingerprint': False, 'has_face': False, 'has_iris': False, 'is_configured': False}
