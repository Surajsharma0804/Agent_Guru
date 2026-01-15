"""
GURU Cryptographic Device Pairing Module

Implements cryptographically secure device pairing using QR codes and ECDSA-P256 key exchange.
Enforces cryptographic authority boundaries for establishing trusted communication channels
between GURU desktop and mobile agents with tamper-evident audit trails.

Security Invariants (Cryptographically Enforced):
- ECDSA-P256 key pair generation with hardware-backed storage
- Cryptographically secure pairing tokens with device fingerprint binding
- Token expiration and replay protection with cryptographic proof
- Physical presence verification requirements with tamper detection
- Defense-in-depth security measures preventing unauthorized device pairing
"""

from .device_registry import DeviceIdentity  # Compatibility alias
from .device_registry import DeviceRegistry  # Compatibility alias
from .device_registry import (
    CryptographicDeviceIdentity,
    CryptographicDeviceRegistry,
    CryptographicTrustedDevice,
    DeviceAuthorityStatus,
)
from .key_exchange import (
    AsymmetricKeyExchangeAuthority,
    DeviceKeyPair,
    KeyExchangeMessage,
    KeyExchangeResult,
    KeyExchangeStatus,
)

# Cryptographic aliases for enterprise naming
CryptographicKeyExchangeEngine = AsymmetricKeyExchangeAuthority
CryptographicKeyExchangeResult = KeyExchangeResult
CryptographicKeyExchangeStatus = KeyExchangeStatus
CryptographicDeviceKeyPair = DeviceKeyPair
from .qr_pairing import CryptographicQRPairingAuthority, PairingResult, PairingToken

__all__ = [
    "CryptographicQRPairingAuthority",
    "PairingToken",
    "PairingResult",
    "CryptographicKeyExchangeEngine",
    "AsymmetricKeyExchangeAuthority",  # Compatibility alias
    "KeyExchangeMessage",  # Compatibility alias
    "KeyExchangeResult",  # Compatibility alias
    "KeyExchangeStatus",  # Compatibility alias
    "DeviceKeyPair",  # Compatibility alias
    "CryptographicDeviceKeyPair",
    "CryptographicKeyExchangeResult",
    "CryptographicKeyExchangeStatus",
    "CryptographicDeviceRegistry",
    "DeviceRegistry",  # Compatibility alias
    "CryptographicDeviceIdentity",
    "DeviceIdentity",  # Compatibility alias
    "CryptographicTrustedDevice",
    "DeviceAuthorityStatus",
]
