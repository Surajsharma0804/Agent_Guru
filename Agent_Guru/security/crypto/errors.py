"""Security error hierarchy for Agent Guru."""


class SecurityError(Exception):
    """Base exception for security system errors."""

    def __init__(self, message: str, error_code: str = "SECURITY_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


class KeyGenerationError(SecurityError):
    """Error during key generation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "KEY_GENERATION_FAILED")


class KeyStorageError(SecurityError):
    """Error during key storage or retrieval."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "KEY_STORAGE_ERROR")


class KeyNotFoundError(SecurityError):
    """Requested key does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "KEY_NOT_FOUND")


class IdentityNotFoundError(SecurityError):
    """Requested identity does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "IDENTITY_NOT_FOUND")


class SignatureError(SecurityError):
    """Error during signature generation or verification."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "SIGNATURE_INVALID")


class ZKProofError(SecurityError):
    """Error during ZK proof generation or verification."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "ZK_PROOF_ERROR")


class ReplayAttackError(ZKProofError):
    """ZK proof timestamp indicates replay attack."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "ZK_PROOF_REPLAY_DETECTED"


class AuditLogError(SecurityError):
    """Error during audit logging."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "AUDIT_LOG_ERROR")


class TrustError(SecurityError):
    """Error during trust operations."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "TRUST_ERROR")


class PolicyViolationError(TrustError):
    """Trust policy not satisfied."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = "TRUST_SCORE_BELOW_THRESHOLD"


class ConfigurationError(SecurityError):
    """Invalid configuration."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "CONFIG_INVALID")
