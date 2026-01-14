"""Android Biometric Authenticator stub. Will be implemented in Task 5."""
from typing import List, Dict
from ...interfaces import BiometricAuthenticator, AuthResult

class AndroidBiometricAuthenticator(BiometricAuthenticator):
    def authenticate(self, reason: str) -> AuthResult:
        raise NotImplementedError("AndroidBiometricAuthenticator will be implemented in Task 5")
    def is_available(self) -> bool:
        raise NotImplementedError("AndroidBiometricAuthenticator will be implemented in Task 5")
    def get_available_factors(self) -> List[str]:
        raise NotImplementedError("AndroidBiometricAuthenticator will be implemented in Task 5")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'has_fingerprint': False, 'has_face': False, 'has_iris': False, 'is_configured': False}
